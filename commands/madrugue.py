import discord
from discord import app_commands
from discord.ext import commands

from core.utils import ahora

from modules.madrugue.services import (
    registrar_madrugue,
)


class Madrugue(commands.Cog):
    """Comandos del sistema Madrugue."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="madrugue",
        description="Registra tu madrugue.",
    )
    async def madrugue(
        self,
        interaction: discord.Interaction,
    ):
        """Registra una madrugada."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor."
            )
            return

        resultado = registrar_madrugue(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            ahora=ahora(),
        )

        # ====================================================
        # FUERA DE HORARIO
        # ====================================================

        if resultado.motivo == "fuera_de_horario":
            await interaction.response.send_message(
                f"🌙 {interaction.user.mention} todavía no "
                "es hora de madrugar para el ranking.\n"
                "El horario válido es de **05:30 a 10:00**.\n"
                f"🇦🇷 Hora actual: "
                f"**{resultado.hora.strftime('%H:%M')}**"
            )
            return

        # ====================================================
        # YA REGISTRADO
        # ====================================================

        if resultado.motivo == "ya_registrado":
            await interaction.response.send_message(
                f"⚠️ {interaction.user.mention} ya registraste "
                "tu madrugada de hoy a las "
                f"**{resultado.hora_anterior}**.\n"
                f"Obtuviste "
                f"**{resultado.puntos_anterior:.0f} puntos**."
            )
            return

        # ====================================================
        # REGISTRO EXITOSO
        # ====================================================

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
            f"**{resultado.puntos_finales:.0f}**\n"
            f"📊 Puntos acumulados: "
            f"**{resultado.total_puntos:.0f}**"
        )


async def setup(bot: commands.Bot):
    """Carga el Cog de Madrugue."""

    await bot.add_cog(
        Madrugue(bot)
    )