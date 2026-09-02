import discord

from datetime import timedelta

from discord import app_commands
from discord.ext import commands, tasks

from config import GUILD_ID, PREFIX

from core.utils import ahora

from modules.ssf.services import (
    procesar_eliminaciones_diarias,
    cerrar_desafios_finalizados,
)

from modules.madrugue.database import (
    inicializar_db as inicializar_db_madrugue,
)

from modules.ssf.database import (
    inicializar_db as inicializar_db_ssf,
)

class NaikitoBot(commands.Bot):
    """Clase principal del bot."""

    def __init__(self):

        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
        )

        # Última fecha procesada por el sistema automático de SSF.
        self.ssf_ultima_revision = None

    # ========================================================
    # SETUP
    # ========================================================

    async def setup_hook(self):
        """Carga módulos, sincroniza comandos e inicia tareas."""

        print("Configurando Naikito Bot...")

        # ====================================================
        # BASE DE DATOS SSF
        # ====================================================

        inicializar_db_madrugue()
        print("Base de datos Madrugue inicializada.")

        inicializar_db_ssf()
        print("Base de datos SSF inicializada.")
        
        # ====================================================
        # CARGAR COMANDOS
        # ====================================================

        await self.load_extension(
            "commands.general"
        )

        await self.load_extension(
            "commands.madrugue"
        )

        await self.load_extension(
            "commands.admin"
        )
        
        admin_cog = self.get_cog("Admin")

        print()
        print("========== ADMIN LOCAL ==========")
        
        if admin_cog:
            print("Admin encontrado:", admin_cog)
        
            print("App commands del Admin:")
        
            for comando in admin_cog.walk_app_commands():
                print(
                    f"- {comando.qualified_name} | "
                    f"tipo={type(comando).__name__}"
                )
        
        print("=================================")
        print()

        await self.load_extension(
            "commands.ssf"
        )

        # ====================================================
        # SINCRONIZAR COMANDOS
        # ====================================================

        if GUILD_ID:

            guild = discord.Object(
                id=GUILD_ID
            )

            self.tree.copy_global_to(
                guild=guild
            )

            manualadd = self.tree.get_command(
                "admin"
            )
            
            print()
            print("========== DEBUG MANUALADD ==========")
            
            if isinstance(manualadd, app_commands.Group):
                print("Admin encontrado en Tree")

                for subcomando in manualadd.commands:
                    print(
                        f"Subcomando: {subcomando.name}"
                    )

                    if (
                        subcomando.name == "manualadd"
                        and isinstance(subcomando, app_commands.Command)
                    ):
                        print("PARÁMETROS MANUALADD:")

                        for parametro in subcomando.parameters:
                            print(
                                f"- {parametro.name} | "
                                f"requerido={parametro.required} | "
                                f"tipo={parametro.type}"
                            )
            
            print("=====================================")

            print()
            comandos = await self.tree.sync(
                guild=guild
            )

            print("COMANDOS REGISTRADOS EN DISCORD:")
            print("=" * 60)

            for comando in comandos:
                print(f"- {comando.name}")

                if isinstance(comando, app_commands.Group):
                    for subcomando in comando.commands:
                        print(f"  └── {subcomando.name}")

                        if isinstance(subcomando, app_commands.Command):
                            print("      OPCIONES:")

                            for opcion in subcomando.parameters:
                                print(
                                    f"      - {opcion.name} | "
                                    f"tipo={opcion.type} | "
                                    f"requerido={opcion.required}"
                                )

            print("=" * 60)

            print(
                "Comandos sincronizados en GUILD_ID: "
                f"{GUILD_ID} ({len(comandos)} comandos)"
            )

        else:

            comandos = await self.tree.sync()

            print(
                "Comandos sincronizados globalmente: "
                f"{len(comandos)}"
            )

            print()
            print("COMANDOS REGISTRADOS:")
            print("=" * 60)

            for comando in comandos:

                print(
                    f"- {comando.name} | "
                    f"tipo={type(comando).__name__}"
                )

                if isinstance(
                    comando,
                    app_commands.Group,
                ):

                    for subcomando in comando.commands:

                        print(
                            f"    └── {subcomando.name} | "
                            f"tipo={type(subcomando).__name__}"
                        )

                        if isinstance(
                            subcomando,
                            app_commands.Group,
                        ):

                            for subsubcomando in subcomando.commands:

                                print(
                                    f"        └── "
                                    f"{subsubcomando.name} | "
                                    f"tipo={type(subsubcomando).__name__}"
                                )

            print("=" * 60)
            print()

        # ====================================================
        # INICIAR TAREA AUTOMÁTICA
        # ====================================================

        self.procesar_ssf_automatico.start()

    # ========================================================
    # SSF AUTOMÁTICO
    # ========================================================

    @tasks.loop(minutes=1)
    async def procesar_ssf_automatico(self):
        """
        Procesa automáticamente SSF una vez por día.

        Después de las 00:05:
        - Revisa el día anterior.
        - Elimina participantes que no sobrevivieron.
        - Publica el resumen.
        - Cierra desafíos finalizados.
        """

        ahora_actual = ahora()

        # ====================================================
        # ANTES DE LAS 00:05
        # ====================================================

        if (
            ahora_actual.hour == 0
            and ahora_actual.minute < 5
        ):
            return

        # ====================================================
        # FECHA A REVISAR
        # ====================================================

        fecha_a_revisar = (
            ahora_actual.date()
            - timedelta(days=1)
        )

        # ====================================================
        # EVITAR DUPLICADOS
        # ====================================================

        if self.ssf_ultima_revision == fecha_a_revisar:
            return

        print(
            "[SSF] Iniciando revisión automática de "
            f"{fecha_a_revisar}..."
        )

        try:

            # =================================================
            # PROCESAR ELIMINACIONES
            # =================================================

            resultados = (
                procesar_eliminaciones_diarias(
                    fecha_a_revisar
                )
            )

            # =================================================
            # PROCESAR DESAFÍOS
            # =================================================

            for resultado in resultados:

                eliminados = resultado["eliminados"]

                print(
                    "[SSF] Desafío "
                    f"{resultado['desafio_id']} "
                    f"(servidor "
                    f"{resultado['guild_id']}): "
                    f"{len(eliminados)} eliminado(s)."
                )

                # =============================================
                # SERVIDOR
                # =============================================

                guild = self.get_guild(
                    resultado["guild_id"]
                )

                if guild is None:

                    print(
                        "[SSF] ⚠️ No se encontró el "
                        f"servidor {resultado['guild_id']}."
                    )

                    continue

                # =============================================
                # CANAL
                # =============================================

                canal = guild.get_channel(
                    resultado["canal_id"]
                )

                if canal is None:

                    print(
                        "[SSF] ⚠️ No se encontró el "
                        f"canal {resultado['canal_id']} "
                        f"en {guild.name}."
                    )

                if not isinstance(canal, discord.abc.Messageable):
                    continue

                # =============================================
                # EMBED
                # =============================================

                embed = discord.Embed(
                    title="🎯 SeptSinFP — Revisión diaria",
                    description=(
                        "Revisión correspondiente al "
                        f"**{fecha_a_revisar.strftime('%d/%m/%Y')}**."
                    ),
                )

                if eliminados:

                    nombres = []

                    for participante in eliminados:

                        nombres.append(
                            f"💀 **{participante['username']}**"
                        )

                    embed.add_field(
                        name=(
                            f"💀 Eliminados "
                            f"({len(eliminados)})"
                        ),
                        value="\n".join(nombres),
                        inline=False,
                    )

                    embed.add_field(
                        name="📋 Motivo",
                        value=(
                            "No registraron "
                            "**/ssf sobrevivi** durante el día."
                        ),
                        inline=False,
                    )

                else:

                    embed.add_field(
                        name="🟢 Resultado",
                        value=(
                            "No hubo eliminaciones. "
                            "Todos los participantes "
                            "registraron su supervivencia."
                        ),
                        inline=False,
                    )

                embed.set_footer(
                    text=(
                        f"Desafío: {resultado['nombre']}"
                    )
                )

                # =============================================
                # PUBLICAR
                # =============================================

                try:

                    await canal.send(
                        embed=embed
                    )

                    print(
                        "[SSF] 📢 Resumen publicado en "
                        f"#{canal.name} "
                        f"({guild.name})."
                    )

                except discord.Forbidden:

                    print(
                        "[SSF] ❌ No tengo permisos para "
                        f"escribir en #{canal.name}."
                    )

                except discord.HTTPException as error:

                    print(
                        "[SSF] ❌ Error enviando el resumen: "
                        f"{error}"
                    )

            # =================================================
            # CERRAR DESAFÍOS
            # =================================================

            try:

                cerrados = cerrar_desafios_finalizados(
                    ahora_actual.date()
                )

                if cerrados:

                    print(
                        "[SSF] 🔒 Desafíos finalizados cerrados: "
                        f"{cerrados}"
                    )

            except Exception as error:

                print(
                    "[SSF] ⚠️ Error cerrando desafíos "
                    f"finalizados: {error}"
                )

            # =================================================
            # MARCAR COMO PROCESADO
            # =================================================

            self.ssf_ultima_revision = fecha_a_revisar

            print(
                "[SSF] Revisión completada. "
                f"Fecha: {fecha_a_revisar}."
            )

        except Exception as error:

            print(
                "[SSF] ❌ Error durante la revisión "
                f"automática: {error}"
            )

    # ========================================================
    # ESPERAR CONEXIÓN
    # ========================================================

    @procesar_ssf_automatico.before_loop
    async def antes_de_procesar_ssf(self):

        await self.wait_until_ready()

    # ========================================================
    # READY
    # ========================================================

    async def on_ready(self):

        print(
            f"Naikito Bot conectado como {self.user}"
        )

        if self.user is not None:
            print(
                f"ID: {self.user.id}"
            )