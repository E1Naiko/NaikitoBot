import discord
from discord import app_commands
from discord.ext import commands


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
        """Registra un madrugue."""

        await interaction.response.send_message(
            "🌅 Sistema Madrugue en migración."
        )


async def setup(bot: commands.Bot):
    """Carga el Cog de Madrugue."""

    await bot.add_cog(
        Madrugue(bot)
    )