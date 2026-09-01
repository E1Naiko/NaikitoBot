import discord
from discord import app_commands
from discord.ext import commands

from modules.madrugue.database import (
    eliminar_registros_usuario,
    eliminar_registros_servidor,
    eliminar_registro_del_dia,
    obtener_estadisticas_servidor,
    obtener_registro_del_dia_admin,
    obtener_resumen_usuario,
    obtener_top_madrugadores,
)

from config import (
    ADMIN_USER_IDS,
    GUILD_SERVIDOR,
    GUILD_TEST,
)


class Admin(commands.GroupCog, group_name="admin"):
    """Comandos administrativos del bot."""

    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

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
            name="🏠 Servidor principal",
            value=(
                str(GUILD_SERVIDOR)
                if GUILD_SERVIDOR
                else "No configurado"
            ),
            inline=True,
        )

        embed.add_field(
            name="🧪 Servidor de pruebas",
            value=(
                str(GUILD_TEST)
                if GUILD_TEST
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
        """Muestra estadísticas generales del servidor."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
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
        """Muestra el ranking histórico del servidor."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
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
        description=(
            "Elimina el registro de Madrugue de "
            "un usuario para una fecha."
        ),
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
        """Elimina el registro de un usuario para una fecha."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
                ephemeral=True,
            )
            return

        from datetime import date

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
        description=(
            "Elimina todos los registros de Madrugue "
            "de un usuario."
        ),
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
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
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
        description=(
            "Elimina todos los registros de "
            "Madrugue del servidor."
        ),
    )
    @app_commands.describe(
        confirmar="Confirma el borrado total.",
    )
    @app_commands.choices(
        confirmar=[
            app_commands.Choice(
                name="SI",
                value="SI",
            ),
            app_commands.Choice(
                name="NO",
                value="NO",
            ),
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
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
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
                "ℹ️ No hay registros de Madrugue "
                "para eliminar en este servidor.",
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


# ============================================================
# SETUP
# ============================================================

async def setup(
    bot: commands.Bot,
):
    """Carga el Cog administrativo."""

    await bot.add_cog(
        Admin(bot)
    )