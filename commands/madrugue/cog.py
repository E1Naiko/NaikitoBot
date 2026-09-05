"""Cog de Madrugue: compone los mixins de comandos.

A diferencia de Box y SSF, acá no se usa ``GroupCog``: los comandos de
Madrugue son de primer nivel (``/madrugue``, ``/madrugue_stats``…) y el
``CommandTree`` los reconoce por ese prefijo para filtrar por canal.
Agruparlos cambiaría sus nombres y rompería ese filtro.
"""

from discord.ext import commands

from commands.madrugue.info import InfoMixin
from commands.madrugue.registro import RegistroMixin


class Madrugue(
    RegistroMixin,
    InfoMixin,
    commands.Cog,
):
    """Comandos del sistema Madrugue."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
