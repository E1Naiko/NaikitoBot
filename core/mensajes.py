"""Presentación de mensajes del bot con embeds y secciones.

Centraliza el formato para que todas las áreas (Box, Madrugue, SeptSinFP,
admin y generales) mantengan el mismo estilo: un título, una descripción
corta y campos/secciones ordenados.
"""

from __future__ import annotations

import discord


# ============================================================
# COLORES POR ÁREA
# ============================================================

COLOR_GENERAL = discord.Color.blurple()
COLOR_BOX = discord.Color.dark_red()
COLOR_MADRUGUE = discord.Color.gold()
COLOR_SSF = discord.Color.teal()
COLOR_ADMIN = discord.Color.dark_grey()

COLOR_OK = discord.Color.green()
COLOR_ERROR = discord.Color.red()
COLOR_AVISO = discord.Color.orange()

COLORES = {
    "general": COLOR_GENERAL,
    "box": COLOR_BOX,
    "madrugue": COLOR_MADRUGUE,
    "ssf": COLOR_SSF,
    "admin": COLOR_ADMIN,
    "ok": COLOR_OK,
    "error": COLOR_ERROR,
    "aviso": COLOR_AVISO,
}


def color(nombre: str) -> discord.Color:
    """Devuelve el color de un área o un color por defecto si no existe."""
    return COLORES.get(nombre, COLOR_GENERAL)


# ============================================================
# EMBED
# ============================================================

def crear_embed(
    titulo: str,
    descripcion: str | None = None,
    color_area: str = "general",
    pie: str | None = None,
) -> discord.Embed:
    """Crea un embed con el estilo compartido del bot."""
    embed = discord.Embed(
        title=titulo,
        description=descripcion,
        color=color(color_area),
    )
    if pie:
        embed.set_footer(text=pie)
    return embed


def seccion(
    embed: discord.Embed,
    nombre: str,
    valor: str,
    inline: bool = False,
) -> discord.Embed:
    """Agrega una sección (campo) al embed."""
    embed.add_field(name=nombre, value=valor, inline=inline)
    return embed


def secciones(
    embed: discord.Embed,
    items: list,
) -> discord.Embed:
    """Agrega varias secciones: ``(nombre, valor)`` o ``(nombre, valor, inline)``."""
    for item in items:
        if len(item) == 3:
            nombre, valor, inline = item
        else:
            nombre, valor = item
            inline = False
        seccion(embed, nombre, valor, inline)
    return embed


# ============================================================
# RESPUESTAS A INTERACCIONES
# ============================================================

async def responder(
    interaction: discord.Interaction,
    titulo: str,
    descripcion: str | None = None,
    secciones_: list[tuple[str, str, bool]] | None = None,
    color_area: str = "general",
    pie: str | None = None,
    ephemeral: bool = False,
    view: discord.ui.View | None = None,
) -> None:
    """Envía una respuesta de interacción como embed con secciones."""
    embed = crear_embed(titulo, descripcion, color_area, pie)
    if secciones_:
        secciones(embed, secciones_)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)


async def responder_error(
    interaction: discord.Interaction,
    titulo: str,
    detalle: str,
    *,
    ephemeral: bool = True,
) -> None:
    """Envía un aviso de error con un único detalle."""
    await responder(
        interaction,
        titulo,
        detalle,
        color_area="error",
        ephemeral=ephemeral,
    )


async def responder_ok(
    interaction: discord.Interaction,
    titulo: str,
    detalle: str,
    *,
    ephemeral: bool = True,
) -> None:
    """Envía una confirmación con un único detalle."""
    await responder(
        interaction,
        titulo,
        detalle,
        color_area="ok",
        ephemeral=ephemeral,
    )


def _titulo_automatico(texto: str, color_area: str) -> str:
    """Deriva un título corto a partir del texto de una respuesta simple."""
    for prefijo, titulo in (
        ("✅", "Operación exitosa"),
        ("❌", "Operación fallida"),
        ("⚠️", "Aviso"),
        ("ℹ️", "Información"),
        ("💰", "Economía"),
        ("⭐", "Experiencia"),
        ("📢", "Notificación"),
        ("♻️", "Reinicio"),
        ("🗑️", "Eliminación"),
        ("🛑", "Cancelación"),
        ("🩹", "Curar"),
        ("🚑", "Salud"),
    ):
        if texto.lstrip().startswith(prefijo):
            return titulo
    return "Naikito Bot"


async def responder_texto(
    interaction: discord.Interaction,
    texto: str,
    *,
    color_area: str = "general",
    ephemeral: bool = False,
    view: discord.ui.View | None = None,
) -> None:
    """Envía una respuesta simple con el texto original y un título sugerido."""
    await responder(
        interaction,
        _titulo_automatico(texto, color_area),
        texto,
        color_area=color_area,
        ephemeral=ephemeral,
        view=view,
    )
