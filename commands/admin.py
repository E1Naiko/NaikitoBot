import discord
from discord import app_commands
from discord.ext import commands

from modules.madrugue.database import (
    obtener_estadisticas_servidor,
    obtener_top_madrugadores,
)

from config import ADMIN_USER_IDS, GUILD_SERVIDOR, GUILD_TEST


class Admin(commands.GroupCog, group_name="admin"):
    """Comandos administrativos del bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

async def setup(bot: commands.Bot):
    """Carga el Cog administrativo."""

    await bot.add_cog(
        Admin(bot)
    )