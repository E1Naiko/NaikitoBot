import discord

from datetime import timedelta

from discord.ext import commands, tasks

from config import GUILD_TEST, PREFIX

from core.utils import ahora

from modules.ssf.services import (
    procesar_eliminaciones_diarias,
    cerrar_desafios_finalizados,
)

from modules.ssf.database import inicializar_db

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

    async def setup_hook(self):
        """Carga los módulos, sincroniza comandos e inicia tareas."""

        print("Configurando Naikito Bot...")

        print("Configurando Naikito Bot...")

        # ====================================================
        # INICIALIZAR BASE DE DATOS SSF
        # ====================================================
        
        inicializar_db()
        
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

        await self.load_extension(
            "commands.ssf"
        )

        # ====================================================
        # SINCRONIZAR COMANDOS
        # ====================================================

        if GUILD_TEST:
            guild = discord.Object(
                id=GUILD_TEST
            )

            self.tree.copy_global_to(
                guild=guild
            )

            comandos = await self.tree.sync(
                guild=guild
            )
            
            print("COMANDOS REGISTRADOS:")

            for comando in comandos:
                print(
                    f"- {comando.name} | "
                    f"tipo={type(comando).__name__}"
                )
            
                if hasattr(comando, "commands"):
                    for subcomando in comando.commands:
                        print(
                            f"    └── {subcomando.name}"
                        )

            print(
                "Comandos sincronizados en servidor "
                f"de prueba: {len(comandos)}"
            )

        else:
            comandos = await self.tree.sync()

            print(
                "Comandos sincronizados globalmente: "
                f"{len(comandos)}"
            )

        # ====================================================
        # INICIAR TAREA AUTOMÁTICA DE SSF
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
        - Publica el resumen en el canal correspondiente.
        - Cierra desafíos que hayan finalizado.
        """

        ahora_actual = ahora()

        # ====================================================
        # ANTES DE LAS 00:05 NO HACER NADA
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
        # EVITAR PROCESAR LA MISMA FECHA DOS VECES
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
            # PROCESAR CADA DESAFÍO
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
                # BUSCAR SERVIDOR
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
                # BUSCAR CANAL
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
                    continue

                # =============================================
                # CREAR EMBED
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
            # CERRAR DESAFÍOS FINALIZADOS
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
            # MARCAR FECHA COMO PROCESADA
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
        """Espera hasta que el bot esté conectado."""

        await self.wait_until_ready()

    # ========================================================
    # READY
    # ========================================================

    async def on_ready(self):
        """Se ejecuta cuando el bot está conectado."""

        print(
            f"Naikito Bot conectado como {self.user}"
        )

        print(
            f"ID: {self.user.id}"
        )