"""Extensión de Discord del sistema Madrugue.

``core/bot.py`` carga esta extensión con ``load_extension("commands.madrugue")``,
así que el punto de entrada sigue siendo ``setup``.
"""

from discord.ext import commands

from commands.madrugue.cog import Madrugue
from modules.madrugue.database import inicializar_db


async def setup(bot: commands.Bot):
    """Crea el esquema de Madrugue y registra sus comandos."""

    inicializar_db()

    await bot.add_cog(Madrugue(bot))
