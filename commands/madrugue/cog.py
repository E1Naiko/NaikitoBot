"""Cog de Madrugue: compone los mixins de comandos.

A diferencia de Box y SSF, acá no se usa ``GroupCog``: los comandos de
Madrugue son de primer nivel (``/madrugue``, ``/madrugue_stats``…) y el
``CommandTree`` los reconoce por ese prefijo para filtrar por canal.
Agruparlos cambiaría sus nombres y rompería ese filtro.
"""

import discord
from discord.ext import commands

import config
from commands.madrugue.info import InfoMixin
from commands.madrugue.registro import RegistroMixin
from core.permissions import es_admin
from modules.madrugue.services import obtener_puntos_base, registrar_madrugue
from modules.sanciones.database import sancion_vigente


class Madrugue(
    RegistroMixin,
    InfoMixin,
    commands.Cog,
):
    """Comandos del sistema Madrugue."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_message(self, mensaje: discord.Message):
        """Registra el primer mensaje válido del usuario en el canal de Madrugue."""
        if (mensaje.guild is None or mensaje.author.bot or mensaje.webhook_id is not None
                or mensaje.is_system() or mensaje.channel.id not in config.MADRUGUE_CHANNEL_IDS):
            return
        momento = mensaje.created_at.astimezone(config.TIMEZONE)
        if not obtener_puntos_base(momento.time()):
            return
        if not es_admin(mensaje.author.id) and await sancion_vigente(
            mensaje.guild.id, mensaje.author.id, "madrugue", momento,
        ):
            return
        await registrar_madrugue(
            guild_id=mensaje.guild.id,
            user_id=mensaje.author.id,
            username=mensaje.author.display_name,
            ahora=momento,
        )
