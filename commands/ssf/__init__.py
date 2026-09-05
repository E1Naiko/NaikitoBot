"""Extensión de Discord del sistema SeptSinFP.

``core/bot.py`` carga esta extensión con ``load_extension("commands.ssf")``,
así que el punto de entrada sigue siendo ``setup``.
"""

from discord.ext import commands

from commands.ssf.cog import Ssf
from modules.ssf.database import inicializar_db


async def setup(bot: commands.Bot):
    """Crea el esquema de SeptSinFP y registra sus comandos."""

    inicializar_db()

    await bot.add_cog(Ssf(bot))
