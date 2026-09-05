"""Extensión de Discord del sistema Box.

``core/bot.py`` carga esta extensión con ``load_extension("commands.box")``,
así que el punto de entrada sigue siendo ``setup``.
"""

from discord.ext import commands

from commands.box.cog import Box
from commands.box.tienda import BotonCompra
from modules.box.database import inicializar_db


async def setup(bot: commands.Bot):
    """Crea el esquema de Box y registra sus comandos."""

    inicializar_db()

    # Los botones de la tienda guardan su estado en el custom_id, así que se
    # registran por patrón: siguen funcionando en mensajes anteriores al
    # arranque del bot.
    bot.add_dynamic_items(BotonCompra)

    await bot.add_cog(Box(bot))
