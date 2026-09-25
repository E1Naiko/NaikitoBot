"""Extensión de Discord del sistema laHora (canal 420).

``core/bot.py`` la carga con ``load_extension("commands.lahora")``.
"""

from discord.ext import commands

from commands.lahora.cog import LaHora
from modules.lahora.database import inicializar_db


async def setup(bot: commands.Bot):
    """Crea el esquema de laHora y registra sus comandos y el listener."""

    await inicializar_db()

    await bot.add_cog(LaHora(bot))
