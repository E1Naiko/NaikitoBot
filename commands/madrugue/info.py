"""Consultas de Madrugue: estadísticas, ranking y ayuda."""

import discord
from discord import app_commands

from commands.madrugue.base import solo_servidor
from modules.madrugue.services import (
    obtener_stats_madrugue,
    obtener_top_madrugue,
)


class InfoMixin:
    """Comandos de consulta del ranking de madrugadores."""

    @app_commands.command(
        name="madrugue_stats",
        description="Muestra tus estadísticas de Madrugue.",
    )
    async def stats(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra las estadísticas de Madrugue."""

        if not await solo_servidor(interaction):
            return

        stats = obtener_stats_madrugue(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        await interaction.response.send_message(
            f"📊 **Estadísticas de "
            f"{interaction.user.display_name}**\n\n"
            f"🏆 Puntos acumulados: "
            f"**{stats['total_puntos']:.1f}**\n"
            f"🔥 Mejor racha: "
            f"**{stats['mejor_racha']} días**"
        )

    @app_commands.command(
        name="madrugue_top",
        description="Muestra el TOP de Madrugue del servidor.",
    )
    async def top(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el ranking histórico de Madrugue."""

        if not await solo_servidor(interaction):
            return

        resultados = obtener_top_madrugue(
            interaction.guild.id,
            limite=10,
        )

        if not resultados:
            await interaction.response.send_message(
                "🏆 Todavía no hay madrugadores registrados."
            )
            return

        embed = discord.Embed(
            title="🏆 TOP Madrugadores",
            description="Ranking histórico del servidor.",
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
                f"**{puntos:.0f} puntos**"
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
            embed=embed
        )

    @app_commands.command(
        name="madrugue_ayuda",
        description="Muestra los comandos de Madrugue.",
    )
    async def ayuda(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra la ayuda del sistema Madrugue."""

        embed = discord.Embed(
            title="🌅 Ayuda de Madrugue",
            description=(
                "Sistema de registro y ranking de madrugadores."
            ),
        )

        embed.add_field(
            name="🌅 /madrugue",
            value=(
                "Registra tu madrugada y obtiene los puntos "
                "correspondientes a la hora."
            ),
            inline=False,
        )

        embed.add_field(
            name="📊 /madrugue_stats",
            value=(
                "Muestra tus puntos acumulados y tu mejor racha."
            ),
            inline=False,
        )

        embed.add_field(
            name="🏆 /madrugue_top",
            value=(
                "Muestra el ranking histórico de madrugadores "
                "del servidor."
            ),
            inline=False,
        )

        embed.add_field(
            name="⏰ Horarios",
            value=(
                "**05:30 – 06:59** → 100 puntos\n"
                "**07:00 – 08:59** → 25 puntos\n"
                "**09:00 – 09:59** → 5 puntos\n"
                "**10:00 en adelante** → fuera de horario"
            ),
            inline=False,
        )

        embed.add_field(
            name="⭐ Multiplicador",
            value=(
                "Cuanto más temprano registres tu madrugada, "
                "mayor será el multiplicador."
            ),
            inline=False,
        )

        embed.set_footer(
            text=(
                f"Servidor: {interaction.guild.name}"
                if interaction.guild
                else "Madrugue"
            )
        )

        await interaction.response.send_message(
            embed=embed
        )
