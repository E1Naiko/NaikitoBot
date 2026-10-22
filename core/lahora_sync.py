"""Sincronización automática del canal 420 al reconectar.

Mientras el bot está offline (caída, reinicio, mantenimiento) no recibe
los mensajes "420" en vivo: ``on_message`` simplemente no se dispara para
lo que pasó mientras tanto. Este módulo repasa el historial de cada canal
420 configurado, en cada servidor donde está el bot, desde el último
momento que se revisó, y carga los que se hayan perdido con las mismas
reglas que el registro en vivo (:func:`modules.lahora.services.importar_mensajes`).

Se usa desde dos lugares:

* ``core.bot.NaikitoBot.on_ready``: corre sola al reconectar.
* ``/admin 420 sincronizar``: la dispara un administrador a mano.

Ambos comparten el mismo candado (``candado_sincronizacion``) para que no
se pisen entre sí ni con ``/admin 420 importar``.
"""

import asyncio
from dataclasses import dataclass

import discord

import config
from core.utils import ahora
from modules.lahora.database import guardar_ultimo_chequeo, obtener_ultimo_chequeo
from modules.lahora.services import ResumenImportacion, importar_mensajes

__all__ = [
    "ResultadoCanalSincronizado",
    "candado_sincronizacion",
    "sincronizar_lahora",
]


# Comparte el candado con cualquier importación manual en curso: recorrer
# el mismo canal desde dos lugares a la vez no rompe nada (el registro es
# idempotente), pero sí puede duplicar llamadas a la API de Discord y
# confundir los contadores de progreso.
candado_sincronizacion = asyncio.Lock()


@dataclass
class ResultadoCanalSincronizado:
    """Resultado de repasar un canal 420 durante la sincronización."""

    guild_id: int
    canal_id: int
    resumen: ResumenImportacion | None = None
    error: str | None = None


async def _resolver_canales(bot, guild) -> list[discord.abc.Messageable]:
    """Canales 420 configurados que existen en ``guild``."""

    canales = []

    for canal_id in sorted(config.LAHORA_CANALES_ID):
        canal = guild.get_channel(canal_id)

        if canal is None:
            try:
                canal = await bot.fetch_channel(canal_id)
            except discord.HTTPException:
                continue

            # fetch_channel no está acotado a un guild: un ID de otro
            # servidor (o un DM) no debe colarse acá.
            if getattr(canal, "guild", None) is None or canal.guild.id != guild.id:
                continue

        canales.append(canal)

    return canales


async def _sincronizar_canal(guild_id, canal) -> ResultadoCanalSincronizado:
    """Repasa un único canal desde su último chequeo y actualiza la marca."""

    desde = await obtener_ultimo_chequeo(canal.id)
    momento_inicio = ahora()

    async def historial():
        async for mensaje in canal.history(
            limit=None,
            after=desde,
            oldest_first=True,
        ):
            yield mensaje

    try:
        resumen = await importar_mensajes(guild_id, historial())
    except discord.Forbidden:
        return ResultadoCanalSincronizado(
            guild_id,
            canal.id,
            error="el bot no tiene permiso para leer el historial.",
        )
    except discord.HTTPException as error:
        return ResultadoCanalSincronizado(
            guild_id,
            canal.id,
            error=f"Discord cortó la lectura ({error}).",
        )

    # Se guarda el momento en que arrancó este chequeo (no el del último
    # mensaje encontrado): si el canal estuvo mudo, igual hay que avanzar
    # la marca para no repasar el mismo tramo vacío en cada reconexión.
    await guardar_ultimo_chequeo(guild_id, canal.id, momento_inicio)

    return ResultadoCanalSincronizado(guild_id, canal.id, resumen=resumen)


async def sincronizar_lahora(bot) -> list[ResultadoCanalSincronizado]:
    """Repasa los canales 420 configurados en todos los servidores del bot.

    Devuelve un resultado por cada canal encontrado. Si ya hay una
    sincronización en curso, no hace nada y devuelve una lista vacía en
    vez de esperar: evita encolar corridas repetidas en cada reconexión.
    """

    if candado_sincronizacion.locked():
        return []

    async with candado_sincronizacion:
        resultados = []

        for guild in bot.guilds:
            for canal in await _resolver_canales(bot, guild):
                resultados.append(
                    await _sincronizar_canal(guild.id, canal)
                )

        return resultados
