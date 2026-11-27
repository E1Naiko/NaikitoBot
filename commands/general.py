import discord
from discord import app_commands
from discord.ext import commands

from core.mensajes import responder


class General(commands.Cog):
    """Comandos generales de Naikito Bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ayuda",
        description="Muestra una guía general de los comandos de NaikitoBot.",
    )
    async def ayuda(self, interaction: discord.Interaction):
        """Muestra los comandos principales y dónde encontrar ayuda detallada."""
        await responder(
            interaction,
            "Ayuda de NaikitoBot",
            color_area="general",
            secciones_=[
                ("Correlativas", "`/correlativas planes`, `unirse`, `materias`, `aprobar`, `cursando`, `siguientes`, `en_curso`, `faltantes` y `progreso`. Podés consultar y seguir varios planes."),
                ("Otros sistemas", "`/madrugue_ayuda` explica Madrugue; `/420_ayuda`, el registro 420; `/box ayuda`, Box; y `/ssf ayuda`, SeptSinFP."),
                ("General y administración", "`/ping` comprueba que el bot responde. Los comandos `/admin` son solo para administradores."),
            ],
        )

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