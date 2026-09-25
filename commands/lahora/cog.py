"""Cog de laHora (canal 420): compone los mixins.

Como en Madrugue, los comandos son de primer nivel (``/420_top``,
``/420_stats``…) y el ``CommandTree`` los reconoce por el prefijo
``420`` para filtrar por canal.
"""

from discord.ext import commands

from commands.lahora.info import InfoMixin
from commands.lahora.registro import RegistroMixin


class LaHora(
    RegistroMixin,
    InfoMixin,
    commands.Cog,
    name="LaHora",
):
    """Registro y ranking del canal 420."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
