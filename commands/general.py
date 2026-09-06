import discord
from discord import app_commands
from discord.ext import commands

from core.mensajes import responder


class General(commands.Cog):
    """Comandos generales de Naikito Bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Comprueba si Naikito Bot está funcionando.",
    )
    async def ping(self, interaction: discord.Interaction):
        """Responde con la latencia del bot."""

        latency = round(self.bot.latency * 1000)

        await responder(
            interaction,
            "🏓 Pong!",
            color_area="general",
            secciones_=[
                ("Latencia", f"`{latency} ms`"),
            ],
        )


async def setup(bot: commands.Bot):
    """Carga el Cog de comandos generales."""

    await bot.add_cog(
        General(bot)
    )