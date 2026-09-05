"""Ayudas compartidas por los comandos de Box."""

TEXTO_SOLO_SERVIDOR = (
    "⚠️ Este comando solo puede utilizarse dentro de un servidor."
)


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
