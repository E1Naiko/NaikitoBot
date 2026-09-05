"""Registro diario de Madrugue."""

import discord
from discord import app_commands

from commands.madrugue.base import solo_servidor
from core.utils import ahora
from modules.madrugue.services import registrar_madrugue


class RegistroMixin:
    """Comando para registrar la madrugada."""

    @app_commands.command(
        name="madrugue",
        description="Registra tu madrugada.",
    )
    async def madrugue(
        self,
        interaction: discord.Interaction,
    ):
        """Registra directamente una madrugada."""

        if not await solo_servidor(interaction):
            return

        resultado = registrar_madrugue(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            ahora=ahora(),
        )

        if resultado.motivo == "fuera_de_horario":
            await interaction.response.send_message(
                f"🌙 {interaction.user.mention} todavía no "
                "es hora de madrugar para el ranking.\n"
                "El horario válido es de **05:30 a 10:00**.\n"
                f"🇦🇷 Hora actual: "
                f"**{resultado.hora.strftime('%H:%M')}**"
            )
            return

        if resultado.motivo == "ya_registrado":
            await interaction.response.send_message(
                f"⚠️ {interaction.user.mention} ya registraste "
                "tu madrugada de hoy a las "
                f"**{resultado.hora_anterior}**.\n"
                f"Obtuviste "
                f"**{resultado.puntos_anterior:.0f} puntos**."
            )
            return

        if resultado.puntos_base == 100:
            emoji = "🥇"
        elif resultado.puntos_base == 25:
            emoji = "🥈"
        else:
            emoji = "🥉"

        await interaction.response.send_message(
            f"🌅 **¡Madrugaste, "
            f"{interaction.user.mention}!**\n\n"
            f"{emoji} Hora: "
            f"**{resultado.hora.strftime('%H:%M')}**\n"
            f"💰 Puntos base: "
            f"**{resultado.puntos_base}**\n"
            f"🔥 Racha: "
            f"**{resultado.racha} días**\n"
            f"⭐ Multiplicador: "
            f"**×{resultado.multiplicador:.3f}**\n"
            f"🏆 Puntos obtenidos: "
            f"**{resultado.puntos_finales:.1f}**\n"
            f"📊 Puntos acumulados: "
            f"**{resultado.total_puntos:.1f}**"
        )
