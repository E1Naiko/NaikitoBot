"""Ayudas compartidas por los comandos administrativos."""

from core.mensajes import responder_error
from core.permissions import es_admin

TEXTO_SOLO_ADMIN = "No tienes permisos para utilizar este comando."
TEXTO_SOLO_SERVIDOR = "Este comando solo puede utilizarse dentro de un servidor."


async def solo_admin(interaction) -> bool:
    """Responde un aviso y devuelve ``False`` si no es administrador.

    Uso::

        if not await solo_admin(interaction):
            return
    """

    if es_admin(interaction.user.id):
        return True

    await responder_error(
        interaction,
        "⛔ Sin permisos",
        TEXTO_SOLO_ADMIN,
    )
    return False


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
