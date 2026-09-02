from datetime import date, datetime
import re
import shlex
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

from core.utils import ahora

from modules.madrugue.database import (
    guardar_registro,
    eliminar_registros_usuario,
    eliminar_registros_servidor,
    eliminar_registro_del_dia,
    obtener_estadisticas_servidor,
    obtener_registro_del_dia_admin,
    obtener_registro_del_dia,
    obtener_fechas_registradas,
    obtener_resumen_usuario,
    obtener_top_madrugadores,
)

from config import (
    ADMIN_USER_IDS,
    GUILD_ID,
)

from modules.madrugue.logic import (
    calcular_multiplicador_horario,
    calcular_racha_para_nuevo_registro,
    obtener_puntos_base,
)

from modules.ssf.services import (
    revivir_participante,
    iniciar_desafio,
)


class _FileExecutionResponse:
    """Redirige las respuestas de comandos hacia el followup original."""

    def __init__(self, interaction: discord.Interaction):
        self._interaction = interaction

    def is_done(self) -> bool:
        return True

    async def send_message(self, *args, **kwargs):
        return await self._interaction.followup.send(*args, **kwargs)


class _FileExecutionInteraction:
    """Proxy de interacción para ejecutar varios comandos en una respuesta."""

    def __init__(self, interaction: discord.Interaction):
        self._interaction = interaction
        self.response = _FileExecutionResponse(interaction)

    def __getattr__(self, name):
        return getattr(self._interaction, name)


# ============================================================
# COG ADMIN
# ============================================================

@app_commands.default_permissions()
class Admin(commands.GroupCog, group_name="admin"):
    """Comandos administrativos del bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resolver_miembro(
        self,
        interaction: discord.Interaction,
        valor: str,
    ) -> discord.Member:
        """Resuelve un miembro desde una mención, un ID o un nombre."""

        if interaction.guild is None:
            raise ValueError("El comando requiere un servidor.")

        valor = valor.strip()
        coincidencia = re.fullmatch(r"<@!?([0-9]+)>|([0-9]+)", valor)

        if coincidencia is not None:
            miembro_id = int(coincidencia.group(1) or coincidencia.group(2))
            miembro = interaction.guild.get_member(miembro_id)

            if miembro is None:
                try:
                    miembro = await interaction.guild.fetch_member(miembro_id)
                except discord.HTTPException as error:
                    raise ValueError(f"No se encontró el miembro: {valor}") from error

            return miembro

        nombre = re.fullmatch(r"<@?([^>]+)>|@(.+)", valor)
        nombre = (nombre.group(1) or nombre.group(2)) if nombre else valor
        nombre = nombre.strip()

        miembros = list(interaction.guild.members)

        if not any(
            any(
                candidato is not None
                and candidato.casefold() == nombre.casefold()
                for candidato in {
                    miembro.name,
                    miembro.display_name,
                    miembro.global_name,
                }
            )
            for miembro in miembros
        ):
            try:
                miembros.extend(
                    await interaction.guild.query_members(
                        query=nombre,
                        limit=100,
                    )
                )
            except discord.DiscordException:
                pass

        for miembro in miembros:
            nombres = {
                miembro.name,
                miembro.display_name,
                miembro.global_name,
            }
            if any(
                candidato is not None
                and candidato.casefold() == nombre.casefold()
                for candidato in nombres
            ):
                return miembro

        raise ValueError(f"No se encontró el miembro: {valor}")

    def _resolver_comando_admin(
        self,
        ruta: list[str],
    ) -> app_commands.Command:
        """Obtiene un comando del grupo admin sin permitir rutas arbitrarias."""

        grupo_admin = self.bot.tree.get_command("admin")

        if not isinstance(grupo_admin, app_commands.Group):
            raise ValueError("El grupo admin no está disponible.")

        if not ruta:
            raise ValueError("Falta el nombre del comando.")

        comando: app_commands.Command | app_commands.Group | None = grupo_admin

        for nombre in ruta:
            if not isinstance(comando, app_commands.Group):
                raise ValueError("La ruta del comando no es válida.")

            comando = comando.get_command(nombre)

            if comando is None:
                raise ValueError(f"Comando admin desconocido: {' '.join(ruta)}")

        if not isinstance(comando, app_commands.Command):
            raise ValueError("La línea debe apuntar a un comando ejecutable.")

        return comando

    async def _ejecutar_linea_archivo(
        self,
        interaction: discord.Interaction,
        linea: str,
    ) -> None:
        """Parsea y ejecuta una única línea de comandos admin."""

        try:
            argumentos = shlex.split(linea, comments=True, posix=True)
        except ValueError as error:
            raise ValueError(f"Sintaxis inválida: {error}") from error

        if not argumentos:
            return

        if argumentos[0].startswith("/"):
            argumentos[0] = argumentos[0][1:]

        if argumentos[0].lower() == "admin":
            argumentos.pop(0)

        if not argumentos:
            raise ValueError("Falta el nombre del comando admin.")

        ruta = [argumentos.pop(0)]

        if ruta[0].lower() == "ssf":
            if not argumentos:
                raise ValueError("Falta el subcomando de admin ssf.")

            ruta.append(argumentos.pop(0))

        comando = self._resolver_comando_admin(ruta)
        nombre = comando.name
        parametros: dict[str, object] = {}

        if nombre in {"info", "stats", "top", "resettotal"}:
            if nombre == "resettotal":
                if len(argumentos) != 1:
                    raise ValueError("resettotal requiere SI o NO.")

                parametros["confirmar"] = app_commands.Choice(
                    name=argumentos[0].upper(),
                    value=argumentos[0].upper(),
                )
            elif argumentos:
                raise ValueError(f"{nombre} no acepta argumentos.")

        elif nombre in {"manualadd", "resetdia", "resetusuario"}:
            if not argumentos:
                raise ValueError(f"Faltan argumentos para {nombre}.")

            parametros["usuario"] = await self._resolver_miembro(
                interaction,
                argumentos.pop(0),
            )

            if nombre in {"manualadd", "resetdia"}:
                if not argumentos:
                    raise ValueError(f"Falta la fecha para {nombre}.")

                parametros["fecha"] = argumentos.pop(0)

            if nombre == "manualadd":
                if not argumentos:
                    raise ValueError("Falta la hora para manualadd.")

                parametros["hora"] = argumentos.pop(0)

            if argumentos:
                raise ValueError(f"Sobran argumentos para {nombre}.")

        elif nombre == "revivir":
            if len(argumentos) != 2:
                raise ValueError("revivir requiere miembro y fecha.")

            parametros["usuario"] = await self._resolver_miembro(
                interaction,
                argumentos[0],
            )
            parametros["fecha"] = argumentos[1]

        elif nombre == "iniciar":
            if len(argumentos) != 1 or interaction.guild is None:
                raise ValueError("iniciar requiere el ID de un canal.")

            canal_id = argumentos[0].strip("<#>")

            if not canal_id.isdigit():
                raise ValueError(f"Canal inválido: {argumentos[0]}")

            canal = interaction.guild.get_channel(int(canal_id))

            if not isinstance(canal, discord.TextChannel):
                raise ValueError(f"No se encontró el canal de texto: {argumentos[0]}")

            parametros["canal"] = canal

        else:
            raise ValueError(f"Comando no permitido: {' '.join(ruta)}")

        await comando._do_call(
            cast(
                discord.Interaction,
                _FileExecutionInteraction(interaction),
            ),
            parametros,
        )

    @app_commands.command(
        name="fileexecute",
        description="Ejecuta comandos admin desde un archivo TXT, línea por línea.",
    )
    @app_commands.describe(
        archivo="Archivo TXT con un comando admin por línea.",
    )
    async def fileexecute(
        self,
        interaction: discord.Interaction,
        archivo: discord.Attachment,
    ):
        """Ejecuta únicamente comandos del grupo admin desde un TXT."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        if not archivo.filename.lower().endswith(".txt"):
            await interaction.response.send_message(
                "⚠️ El archivo debe tener extensión `.txt`.",
                ephemeral=True,
            )
            return

        if archivo.size > 1024 * 1024:
            await interaction.response.send_message(
                "⚠️ El archivo no puede superar 1 MiB.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        contenido = (await archivo.read()).decode("utf-8-sig")
        lineas = [linea.strip() for linea in contenido.splitlines()]
        lineas = [linea for linea in lineas if linea and not linea.startswith("#")]

        if len(lineas) > 50:
            await interaction.followup.send(
                "⚠️ El archivo no puede contener más de 50 comandos.",
                ephemeral=True,
            )
            return

        resultados = []

        for numero, linea in enumerate(lineas, start=1):
            try:
                await self._ejecutar_linea_archivo(interaction, linea)
            except (ValueError, discord.DiscordException) as error:
                resultados.append(f"❌ Línea {numero}: {error}")
            else:
                resultados.append(f"✅ Línea {numero}: ejecutada")

        await interaction.followup.send(
            "**Ejecución finalizada**\n" + "\n".join(resultados),
            ephemeral=True,
        )

    # ========================================================
    # GRUPO SSF
    # ========================================================

    ssf = app_commands.Group(
        name="ssf",
        description="Comandos administrativos de SeptSinFP.",
    )

    # ========================================================
    # INFO
    # ========================================================

    @app_commands.command(
        name="info",
        description="Muestra información de configuración del bot.",
    )
    async def info(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra información administrativa."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="⚙️ Información de Naikito Bot",
            description="Configuración administrativa.",
        )

        embed.add_field(
            name="👤 Administradores",
            value=str(len(ADMIN_USER_IDS)),
            inline=True,
        )

        embed.add_field(
            name="🏠 Servidor configurado",
            value=(
                str(GUILD_ID)
                if GUILD_ID
                else "No configurado"
            ),
            inline=True,
        )

        if interaction.guild:
            embed.add_field(
                name="📍 Servidor actual",
                value=(
                    f"{interaction.guild.name}\n"
                    f"`{interaction.guild.id}`"
                ),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # ========================================================
    # STATS
    # ========================================================

    @app_commands.command(
        name="stats",
        description="Muestra las estadísticas de Madrugue del servidor.",
    )
    async def stats(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra estadísticas generales."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        madrugadores, registros, puntos = (
            obtener_estadisticas_servidor(
                interaction.guild.id
            )
        )

        embed = discord.Embed(
            title="📊 Estadísticas de Madrugue",
            description=(
                f"Estadísticas generales de "
                f"**{interaction.guild.name}**."
            ),
        )

        embed.add_field(
            name="👥 Madrugadores",
            value=f"**{madrugadores}**",
            inline=True,
        )

        embed.add_field(
            name="🌅 Registros",
            value=f"**{registros}**",
            inline=True,
        )

        embed.add_field(
            name="🏆 Puntos acumulados",
            value=f"**{puntos:.1f}**",
            inline=True,
        )

        embed.set_footer(
            text=f"Servidor: {interaction.guild.name}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # ========================================================
    # TOP
    # ========================================================

    @app_commands.command(
        name="top",
        description="Muestra el TOP de Madrugue del servidor.",
    )
    async def top(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el ranking histórico."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        resultados = obtener_top_madrugadores(
            interaction.guild.id,
            limite=10,
        )

        if not resultados:
            await interaction.response.send_message(
                "🏆 Todavía no hay madrugadores registrados.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🏆 TOP Madrugadores",
            description=(
                f"Ranking histórico de **{interaction.guild.name}**."
            ),
        )

        medallas = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        lineas = []

        for posicion, (
            user_id,
            username,
            puntos,
        ) in enumerate(resultados, start=1):

            medalla = medallas.get(
                posicion,
                f"**{posicion}.**",
            )

            lineas.append(
                f"{medalla} **{username}** — "
                f"**{puntos:.1f} puntos**"
            )

        embed.add_field(
            name="Ranking",
            value="\n".join(lineas),
            inline=False,
        )

        embed.set_footer(
            text=f"Servidor: {interaction.guild.name}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # ========================================================
    # RESET DÍA
    # ========================================================

    @app_commands.command(
        name="resetdia",
        description="Elimina el registro de Madrugue de un usuario para una fecha.",
    )
    @app_commands.describe(
        usuario="Usuario cuyo registro quieres eliminar.",
        fecha="Fecha del registro en formato YYYY-MM-DD.",
    )
    async def resetdia(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Elimina un registro diario."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await interaction.response.send_message(
                "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-08-31`.",
                ephemeral=True,
            )
            return

        registro = obtener_registro_del_dia_admin(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if registro is None:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** no tiene "
                f"un registro el **{fecha}**.",
                ephemeral=True,
            )
            return

        hora, puntos = registro

        eliminado = eliminar_registro_del_dia(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if eliminado == 0:
            await interaction.response.send_message(
                "⚠️ No se pudo eliminar el registro.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🗑️ Registro eliminado correctamente.\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Fecha: **{fecha}**\n"
            f"⏰ Hora registrada: **{hora}**\n"
            f"🏆 Puntos eliminados: **{puntos:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # RESET USUARIO
    # ========================================================

    @app_commands.command(
        name="resetusuario",
        description="Elimina todos los registros de Madrugue de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyos registros quieres eliminar.",
    )
    async def resetusuario(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Elimina todos los registros de un usuario."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        resumen = obtener_resumen_usuario(
            interaction.guild.id,
            usuario.id,
        )

        cantidad_registros = resumen[0]
        puntos_totales = resumen[1]

        if cantidad_registros == 0:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** no tiene "
                "registros en este servidor.",
                ephemeral=True,
            )
            return

        eliminado = eliminar_registros_usuario(
            interaction.guild.id,
            usuario.id,
        )

        if eliminado == 0:
            await interaction.response.send_message(
                "⚠️ No se pudo eliminar ningún registro.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🗑️ Registros eliminados correctamente.\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📋 Registros eliminados: **{eliminado}**\n"
            f"🏆 Puntos eliminados: **{puntos_totales:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # RESET TOTAL
    # ========================================================

    @app_commands.command(
        name="resettotal",
        description="Elimina todos los registros de Madrugue del servidor.",
    )
    @app_commands.describe(
        confirmar="Confirma el borrado total.",
    )
    @app_commands.choices(
        confirmar=[
            app_commands.Choice(name="SI", value="SI"),
            app_commands.Choice(name="NO", value="NO"),
        ]
    )
    async def resettotal(
        self,
        interaction: discord.Interaction,
        confirmar: app_commands.Choice[str],
    ):
        """Elimina todos los registros del servidor."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        if confirmar.value != "SI":
            await interaction.response.send_message(
                "🛑 Operación cancelada. "
                "No se eliminó ningún registro.",
                ephemeral=True,
            )
            return

        madrugadores, registros, puntos = (
            obtener_estadisticas_servidor(
                interaction.guild.id
            )
        )

        if registros == 0:
            await interaction.response.send_message(
                "ℹ️ No hay registros de Madrugue para eliminar en este servidor.",
                ephemeral=True,
            )
            return

        eliminado = eliminar_registros_servidor(
            interaction.guild.id
        )

        await interaction.response.send_message(
            f"🗑️ **Borrado total completado.**\n\n"
            f"🏠 Servidor: **{interaction.guild.name}**\n"
            f"👥 Madrugadores afectados: **{madrugadores}**\n"
            f"📋 Registros eliminados: **{eliminado}**\n"
            f"🏆 Puntos eliminados: **{puntos:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # SSF - REVIVIR
    # ========================================================

    @ssf.command(
        name="revivir",
        description="Revive a un participante eliminado de SeptSinFP.",
    )
    @app_commands.describe(
        usuario="Usuario eliminado que quieres revivir.",
        fecha="Día que olvidó registrar, en formato YYYY-MM-DD.",
    )
    async def ssf_revivir(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Revive un participante."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await interaction.response.send_message(
                "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-09-01`.",
                ephemeral=True,
            )
            return

        resultado = revivir_participante(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            fecha=fecha_obj,
        )

        if not resultado["exitoso"]:

            motivos = {
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "fuera_de_fecha": (
                    "⚠️ La fecha indicada está fuera "
                    "del período del desafío."
                ),
                "no_participante": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está registrado como participante "
                    "de SeptSinFP."
                ),
                "no_eliminado": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está eliminado.\n"
                    "No es necesario revivirlo."
                ),
                "ya_registrado": (
                    f"ℹ️ **{usuario.display_name}** "
                    f"ya tiene registrado el día **{fecha}**."
                ),
            }

            await interaction.response.send_message(
                motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo revivir al participante.",
                ),
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            f"💚 **Participante revivido correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Día recuperado: **{fecha}**\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n\n"
            f"🫡 **{usuario.display_name}** puede "
            "volver a utilizar `/ssf sobrevivi` normalmente."
        )

    # ========================================================
    # SSF - INICIAR
    # ========================================================

    @ssf.command(
        name="iniciar",
        description="Inicia un nuevo desafío SeptSinFP.",
    )
    @app_commands.describe(
        canal="Canal donde se utilizarán los comandos de SeptSinFP.",
    )
    async def ssf_iniciar(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
    ):
        """Inicia un nuevo desafío."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        fecha_inicio = "2026-09-01"
        fecha_fin = "2026-09-30"

        resultado = iniciar_desafio(
            guild_id=interaction.guild.id,
            nombre="SeptSinFP 2026",
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            canal_id=canal.id,
        )

        if not resultado["exitoso"]:

            if resultado["motivo"] == "ya_existe":
                mensaje = (
                    "⚠️ Ya existe un desafío SeptSinFP "
                    "activo en este servidor."
                )
            else:
                mensaje = (
                    "⚠️ No se pudo iniciar el desafío."
                )

            await interaction.response.send_message(
                mensaje,
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            f"🎯 **SeptSinFP iniciado correctamente.**\n\n"
            f"📋 Desafío: **SeptSinFP 2026**\n"
            f"🗓️ Inicio: **{fecha_inicio}**\n"
            f"🏁 Fin: **{fecha_fin}**\n"
            f"📢 Canal: {canal.mention}\n"
            f"🆔 ID del desafío: "
            f"**{resultado['desafio_id']}**\n\n"
            f"Los participantes ya pueden utilizar "
            f"**/ssf registrar** en {canal.mention}."
        )

    # ========================================================
    # MANUAL ADD
    # ========================================================

    @app_commands.command(
        name="manualadd",
        description="Agrega manualmente la madrugada de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario al que se le agregará el registro.",
        fecha="Fecha del registro en formato YYYY-MM-DD.",
        hora="Hora de la madrugada en formato HH:MM.",
    )
    async def manualadd(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
        hora: str,
    ):
        """Agrega manualmente una madrugada."""

        # ----------------------------------------------------
        # VERIFICAR PERMISOS
        # ----------------------------------------------------

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # VERIFICAR SERVIDOR
        # ----------------------------------------------------

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # VALIDAR FECHA
        # ----------------------------------------------------

        try:
            fecha_obj = datetime.strptime(
                fecha,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            await interaction.response.send_message(
                "❌ Fecha inválida.\n"
                "Usá el formato **YYYY-MM-DD**.\n\n"
                "Ejemplo: `2026-07-01`",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # RECHAZAR FECHAS FUTURAS
        # ----------------------------------------------------

        fecha_actual = ahora().date()

        if fecha_obj > fecha_actual:
            await interaction.response.send_message(
                "❌ No podés registrar una fecha futura.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # VALIDAR HORA
        # ----------------------------------------------------

        try:
            hora_obj = datetime.strptime(
                hora,
                "%H:%M",
            ).time()

        except ValueError:
            await interaction.response.send_message(
                "❌ Hora inválida.\n"
                "Usá el formato **HH:MM**.\n\n"
                "Ejemplo: `05:45`",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # COMPROBAR REGISTRO EXISTENTE
        # ----------------------------------------------------

        registro_existente = obtener_registro_del_dia(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if registro_existente:
            hora_anterior, puntos = registro_existente

            await interaction.response.send_message(
                "⚠️ **EL USUARIO YA TIENE REGISTRO EN ESA FECHA**\n\n"
                f"👤 Usuario: **{usuario.display_name}**\n"
                f"📅 Fecha: **{fecha_obj.isoformat()}**\n"
                f"⏰ Hora registrada: **{hora_anterior}**\n"
                f"🏆 Puntos: **{puntos:.1f}**\n\n"
                "Si querés modificarlo, primero eliminá "
                "el registro del día.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # CALCULAR PUNTOS BASE
        # ----------------------------------------------------

        puntos_base = obtener_puntos_base(
            hora_obj
        )

        if puntos_base == 0:
            await interaction.response.send_message(
                "❌ La hora indicada está fuera "
                "del horario válido.\n\n"
                "El horario permitido es "
                "**05:30 a 10:00**.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # CALCULAR RACHA
        # ----------------------------------------------------

        fechas_registradas = obtener_fechas_registradas(
            interaction.guild.id,
            usuario.id,
        )

        racha = calcular_racha_para_nuevo_registro(
            fechas_registradas,
            fecha_obj,
        )

        # ----------------------------------------------------
        # CALCULAR MULTIPLICADOR
        # ----------------------------------------------------

        multiplicador = calcular_multiplicador_horario(
            hora_obj
        )

        puntos_finales = (
            puntos_base * multiplicador
        )

        # ----------------------------------------------------
        # GUARDAR REGISTRO
        # ----------------------------------------------------

        guardar_registro(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            username=usuario.display_name,
            fecha=fecha_obj,
            hora=hora_obj.strftime("%H:%M"),
            puntos_base=puntos_base,
            multiplicador=multiplicador,
            puntos_finales=puntos_finales,
        )

        # ----------------------------------------------------
        # EMOJI
        # ----------------------------------------------------

        if puntos_base == 100:
            emoji = "🥇"
        elif puntos_base == 25:
            emoji = "🥈"
        else:
            emoji = "🥉"

        # ----------------------------------------------------
        # CONFIRMACIÓN
        # ----------------------------------------------------

        await interaction.response.send_message(
            "🔧 **REGISTRO MANUAL AGREGADO**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🆔 ID: `{usuario.id}`\n"
            f"📅 Fecha: **{fecha_obj.isoformat()}**\n"
            f"⏰ Hora registrada: "
            f"**{hora_obj.strftime('%H:%M')}**\n\n"
            f"{emoji} Puntos base: **{puntos_base}**\n"
            f"🔥 Racha: **{racha} días**\n"
            f"⭐ Multiplicador: "
            f"**×{multiplicador:.3f}**\n"
            f"🏆 Puntos obtenidos: "
            f"**{puntos_finales:.3f}**",
            ephemeral=True,
        )


# ============================================================
# SETUP
# ============================================================

async def setup(bot: commands.Bot):
    """Carga el Cog administrativo."""

    await bot.add_cog(
        Admin(bot)
    )
