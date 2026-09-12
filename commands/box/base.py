"""Ayudas compartidas por los comandos de Box."""

import discord

from core.mensajes import responder_error

TEXTO_SOLO_SERVIDOR = (
    "Este comando solo puede utilizarse dentro de un servidor."
)


async def solo_servidor(interaction) -> bool:
    """Responde un aviso y devuelve ``False`` si no hay servidor.

    Uso::

        if not await solo_servidor(interaction):
            return
    """

    if interaction.guild is not None:
        return True

    await responder_error(
        interaction,
        "⚠️ Sin servidor",
        TEXTO_SOLO_SERVIDOR,
    )
    return False


def es_canal(objeto) -> bool:
    """Si el objeto sabe mandar mensajes.

    Se pregunta por ``send`` y no por ``isinstance(..., Messageable)``: los
    dobles de las pruebas no heredan de las clases de discord.py y el área ya
    trabaja con esa forma de canal.
    """

    return callable(getattr(objeto, "send", None))


async def resolver_canal(bot, canal_id):
    """Canal por id: de la caché del bot o pedido a Discord, o ``None``."""

    if bot is None or canal_id is None:
        return None

    canal = bot.get_channel(canal_id)

    if es_canal(canal):
        return canal

    try:
        canal = await bot.fetch_channel(canal_id)
    except discord.HTTPException:
        return None

    return canal if es_canal(canal) else None


async def canal_de_la_interaccion(bot, interaction):
    """Canal donde se ejecutó el comando, o ``None`` si no se puede resolver.

    Hace falta para publicar lo que tiene que ver todo el servidor (la tarjeta
    de un desafío, por ejemplo): lo que sale por ``interaction.followup`` viaja
    atado a la interacción y, si el comando difirió efímero para no perder la
    ventana de tres segundos, por ahí no lo ve nadie más que quien ejecutó el
    comando.

    ``interaction.channel`` suele venir resuelto en el propio payload; con la
    caché fría se cae a ``resolver_canal``.
    """

    canal = getattr(interaction, "channel", None)

    if es_canal(canal):
        return canal

    return await resolver_canal(bot, getattr(interaction, "channel_id", None))
