from datetime import date, datetime

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


# ============================================================
# COG ADMIN
# ============================================================

@app_commands.default_permissions()
class Admin(commands.GroupCog, group_name="admin"):
    """Comandos administrativos del bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        hora="Hora de la madrugada en formato HH:MM.",
    )
    async def manualadd(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
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
        # FECHA ACTUAL
        # ----------------------------------------------------

        fecha = ahora().date()

        # ----------------------------------------------------
        # COMPROBAR REGISTRO EXISTENTE
        # ----------------------------------------------------

        registro_existente = obtener_registro_del_dia(
            interaction.guild.id,
            usuario.id,
            fecha,
        )

        if registro_existente:
            hora_anterior, puntos = registro_existente

            await interaction.response.send_message(
                "⚠️ **EL USUARIO YA TIENE REGISTRO HOY**\n\n"
                f"👤 Usuario: **{usuario.display_name}**\n"
                f"📅 Fecha: **{fecha.isoformat()}**\n"
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
            fecha,
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
            fecha=fecha,
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
            f"📅 Fecha: **{fecha.isoformat()}**\n"
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
