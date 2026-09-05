"""Extensión de Discord del sistema Box.

``core/bot.py`` carga esta extensión con ``load_extension("commands.box")``,
así que el punto de entrada sigue siendo ``setup``.
"""

from discord.ext import commands

from commands.box.cog import Box
from modules.box.database import inicializar_db


async def setup(bot: commands.Bot):
    """Crea el esquema de Box y registra sus comandos."""

    inicializar_db()
    await bot.add_cog(Box(bot))
