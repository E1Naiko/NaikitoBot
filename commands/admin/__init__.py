"""Extensión de Discord con los comandos administrativos.

``core/bot.py`` carga esta extensión con ``load_extension("commands.admin")``,
así que el punto de entrada sigue siendo ``setup``.
"""

from discord.ext import commands

from commands.admin.cog import Admin


async def setup(bot: commands.Bot):
    """Registra los comandos administrativos."""

    await bot.add_cog(Admin(bot))
