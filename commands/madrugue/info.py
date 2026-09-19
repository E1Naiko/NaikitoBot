"""Consultas de Madrugue: estadísticas, ranking y ayuda."""

import discord
from discord import app_commands

from commands.madrugue.base import solo_servidor
from core.mensajes import crear_embed, responder, seccion
from modules.madrugue.services import (
    obtener_stats_madrugue,
    obtener_top_madrugue,
    texto_ventanas_puntos,
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

        stats = await obtener_stats_madrugue(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        await responder(
            interaction,
            f"📊 Estadísticas de {interaction.user.display_name}",
            color_area="madrugue",
            secciones_=[
                ("🏆 Puntos acumulados", f"**{stats['total_puntos']:.1f}**"),
                ("🔥 Mejor racha", f"**{stats['mejor_racha']} días**"),
            ],
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

        resultados = await obtener_top_madrugue(
            interaction.guild.id,
            limite=10,
        )

        if not resultados:
            await responder(
                interaction,
                "🏆 TOP Madrugadores",
                "Todavía no hay madrugadores registrados.",
                color_area="madrugue",
            )
            return

        embed = crear_embed(
            "🏆 TOP Madrugadores",
            "Ranking histórico del servidor.",
            color_area="madrugue",
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

        seccion(embed, "Ranking", "\n".join(lineas))

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
            value=texto_ventanas_puntos(),
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
