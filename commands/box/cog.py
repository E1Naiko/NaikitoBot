"""Cog de Box: compone los mixins de comandos en un único grupo ``/box``.

Se usa un solo ``GroupCog`` porque discord.py no permite registrar dos cogs
con el mismo ``group_name`` (falla con ``CommandAlreadyRegistered``). Por eso
cada área vive en su propio mixin y se combinan acá.
"""

from discord.ext import commands

from commands.box.acciones import AccionesMixin
from commands.box.desafios import DesafiosMixin
from commands.box.info import InfoMixin
from commands.box.tienda import TiendaMixin


class Box(
    AccionesMixin,
    DesafiosMixin,
    InfoMixin,
    TiendaMixin,
    commands.GroupCog,
    group_name="box",
):
    """Acciones temporizadas de progreso y economía."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.comprobar_acciones.start()

    def cog_unload(self):
        self.comprobar_acciones.cancel()
