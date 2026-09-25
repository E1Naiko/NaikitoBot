"""Ayudas compartidas por los comandos de laHora."""

from core.mensajes import responder_error

TEXTO_SOLO_SERVIDOR = (
    "Este comando solo puede utilizarse dentro de un servidor."
)

MEDALLAS = {
    1: "🥇",
    2: "🥈",
    3: "🥉",
}


def medalla(posicion: int) -> str:
    """Medalla del podio o el número en negrita."""

    return MEDALLAS.get(posicion, f"**{posicion}.**")


async def solo_servidor(interaction) -> bool:
    """Responde un aviso y devuelve ``False`` si no hay servidor."""

    if interaction.guild is not None:
        return True

    await responder_error(
        interaction,
        "⚠️ Sin servidor",
        TEXTO_SOLO_SERVIDOR,
    )
    return False
