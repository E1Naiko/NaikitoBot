"""Ayudas compartidas por los comandos de Madrugue."""

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
