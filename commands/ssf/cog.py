"""Cog de SeptSinFP: compone los mixins de comandos en un único grupo ``/ssf``.

Se usa un solo ``GroupCog`` porque discord.py no permite registrar dos cogs
con el mismo ``group_name`` (falla con ``CommandAlreadyRegistered``). Por eso
cada área vive en su propio mixin y se combinan acá.

Los comandos administrativos (``/admin ssf revivir`` e ``/admin ssf iniciar``)
viven en ``commands/admin.py`` bajo el grupo ``/admin`` y no chocan con este.
"""

from discord.ext import commands

from commands.ssf.info import InfoMixin
from commands.ssf.registro import RegistroMixin
from commands.ssf.tareas import TareasMixin


class Ssf(
    RegistroMixin,
    InfoMixin,
    TareasMixin,
    commands.GroupCog,
    group_name="ssf",
):
    """Desafío de supervivencia diaria SeptSinFP."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ssf_ultima_revision = None
        self.procesar_ssf_automatico.start()

    def cog_unload(self):
        self.procesar_ssf_automatico.cancel()
