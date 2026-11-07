"""Tarea que deja en la terminal el resultado de cada ventana 420.

El registro en vivo imprime cada 420 y el podio, pero el ranking completo de
la ventana solo se ve pidiendo ``/420_hoy``. Esta tarea, al cerrar cada
ventana configurada, imprime quién ganó y cuántos participaron.

No publica nada en Discord: es solo para la consola del servidor.
"""

from discord.ext import tasks

import config
from core.lahora_logs import linea_resumen_ventana, ventana_recien_cerrada
from core.utils import ahora
from modules.lahora.services import obtener_ventana_cerrada

# Cada cuántos segundos se mira si terminó una ventana.
INTERVALO_SEGUNDOS = 60


class ResumenVentanasMixin:
    """Imprime en la terminal el podio de cada ventana al terminar."""

    async def cog_load(self):
        """Arranca el resumen cuando discord.py registra el cog.

        No se hace en ``__init__`` porque este mixin no tiene un
        ``__init__`` previo en la cadena (``commands.Cog`` no define uno) y
        llamar a ``super().__init__`` terminaría en ``object``.
        """

        # Ventanas ya resumidas, para no repetirlas en el siguiente latido.
        self._ventanas_resumidas = set()
        self.resumir_ventanas.start()

    def cog_unload(self):
        self.resumir_ventanas.cancel()

    @tasks.loop(seconds=INTERVALO_SEGUNDOS)
    async def resumir_ventanas(self):
        """Busca ventanas recién cerradas y resume cada una una sola vez."""

        cerrada = ventana_recien_cerrada(ahora())

        if cerrada is None:
            return

        fecha, ventana = cerrada
        clave = (fecha, ventana.strftime("%H:%M"))

        # ``cog_load`` normalmente ya creó el conjunto; el respaldo cubre los
        # casos donde el loop se dispara antes (o en pruebas).
        if not hasattr(self, "_ventanas_resumidas"):
            self._ventanas_resumidas = set()

        if clave in self._ventanas_resumidas:
            return

        self._ventanas_resumidas.add(clave)

        # La lista de ventanas resumidas no debe crecer para siempre: con dos
        # ventanas por día alcanza con recordar las últimas de hoy.
        self._ventanas_resumidas = {
            guardada for guardada in self._ventanas_resumidas if guardada[0] == fecha
        }

        for guild in list(self.bot.guilds):
            filas = await obtener_ventana_cerrada(guild.id, fecha, clave[1])
            linea = linea_resumen_ventana(fecha, clave[1], filas)

            if linea:
                print(f"{linea} servidor={guild.id}", flush=True)

    @resumir_ventanas.before_loop
    async def antes_de_resumir(self):
        await self.bot.wait_until_ready()
        # Sin canales configurados la tarea no tiene qué resumir.
        if not config.LAHORA_CANALES_ID:
            self.resumir_ventanas.cancel()
