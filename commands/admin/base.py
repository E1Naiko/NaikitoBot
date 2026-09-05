"""Ayudas compartidas por los comandos administrativos."""

from core.permissions import es_admin

TEXTO_SOLO_ADMIN = (
    "⛔ No tienes permisos para utilizar este comando."
)

TEXTO_SOLO_SERVIDOR = (
    "⚠️ Este comando solo puede utilizarse dentro de un servidor."
)


async def solo_admin(interaction) -> bool:
    """Responde un aviso y devuelve ``False`` si no es administrador.

    Uso::

        if not await solo_admin(interaction):
            return
    """

    if es_admin(interaction.user.id):
        return True

    await interaction.response.send_message(
        TEXTO_SOLO_ADMIN,
        ephemeral=True,
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

    await interaction.response.send_message(
        TEXTO_SOLO_SERVIDOR,
        ephemeral=True,
    )
    return False
