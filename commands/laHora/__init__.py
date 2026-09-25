"""Extensión de Discord del sistema laHora.

``core/bot.py`` carga esta extensión con ``load_extension("commands.madrugue")``,
así que el punto de entrada sigue siendo ``setup``.
"""

from discord.ext import commands

from commands.madrugue.cog import Madrugue
from modules.madrugue.database import inicializar_db


async def setup(bot: commands.Bot):
    """Crea el esquema de laHora y registra sus comandos."""

    await inicializar_db()

    await bot.add_cog(laHora(bot))
