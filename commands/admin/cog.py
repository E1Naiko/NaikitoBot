"""Cog administrativo: compone los mixins en el único grupo ``/admin``.

Se usa un solo ``GroupCog`` porque discord.py no permite registrar dos cogs
con el mismo ``group_name`` (falla con ``CommandAlreadyRegistered``). Por eso
cada área vive en su propio mixin y se combinan acá.
"""

from discord.ext import commands

from commands.admin.box import BoxAdminMixin
from commands.admin.madrugue import MadrugueAdminMixin
from commands.admin.sistema import SistemaMixin
from commands.admin.ssf import SsfAdminMixin


class Admin(
    BoxAdminMixin,
    MadrugueAdminMixin,
    SistemaMixin,
    SsfAdminMixin,
    commands.GroupCog,
    group_name="admin",
):
    """Comandos administrativos del bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
