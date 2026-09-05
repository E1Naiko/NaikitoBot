"""Tienda de Box: catálogo, botones de compra y comandos de compra.

Los botones llevan el estado en su ``custom_id`` (``box_comprar:owner:cat:clave``)
y se parsean con :class:`discord.ui.DynamicItem`. Así sobreviven a un reinicio
del bot: ``setup`` registra la plantilla y Discord vuelve a encauzar los clics
aunque el mensaje sea anterior al arranque.
"""

import re

import discord
from discord import app_commands

from commands.box.base import solo_servidor
from commands.box.compras import CATALOGOS, ejecutar_compra
from modules.box.services import (
    EQUIPAMIENTO,
    MEJORAS,
    TRATAMIENTOS,
    calidad_equipamiento,
    es_nivel_maximo,
    obtener_equipo,
    obtener_nivel_mejora,
    precio_equipamiento,
    precio_mejora,
)

PREFIJO_CUSTOM_ID = "box_comprar"

# owner_id y las claves pueden llevar guion bajo (protector_bucal, cinco_estrellas).
PLANTILLA_CUSTOM_ID = re.compile(
    rf"{PREFIJO_CUSTOM_ID}:"
    r"(?P<owner_id>\d+):"
    r"(?P<categoria>[a-z]+):"
    r"(?P<clave>[a-z_]+)"
)

# Orden en que aparecen los botones, igual que las secciones del mensaje.
ORDEN_CATALOGOS = ("mejora", "equipamiento", "tratamiento")

# Discord permite 5 botones por fila y 5 filas.
BOTONES_POR_FILA = 5


def custom_id_de(owner_id: int, categoria: str, clave: str) -> str:
    return f"{PREFIJO_CUSTOM_ID}:{owner_id}:{categoria}:{clave}"


class BotonCompra(discord.ui.DynamicItem[discord.ui.Button], template=PLANTILLA_CUSTOM_ID):
    """Botón de un artículo; sabe a quién pertenece la tienda que lo muestra."""

    def __init__(
        self,
        owner_id: int,
        categoria: str,
        clave: str,
        row: int | None = None,
    ):
        configuracion = CATALOGOS[categoria][clave]
        boton = discord.ui.Button(
            emoji=configuracion["emoji"],
            label=configuracion["nombre"],
            style=discord.ButtonStyle.secondary,
            custom_id=custom_id_de(owner_id, categoria, clave),
        )
        super().__init__(boton, row=row)
        self.owner_id = owner_id
        self.categoria = categoria
        self.clave = clave

    @classmethod
    async def from_custom_id(cls, interaction, item, match):
        """Reconstruye el botón a partir del ``custom_id`` que mandó Discord."""

        return cls(
            int(match["owner_id"]),
            match["categoria"],
            match["clave"],
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "⚠️ Esta tienda no es tuya. Usá `/box tienda` para abrir la tuya.",
                ephemeral=True,
            )
            return

        resultado = ejecutar_compra(
            interaction.guild.id,
            interaction.user.id,
            self.categoria,
            self.clave,
        )
        await interaction.response.send_message(
            resultado.texto,
            ephemeral=True,
        )


class TiendaView(discord.ui.View):
    """Vista con un botón por artículo, propiedad de un solo usuario."""

    def __init__(self, owner_id: int):
        # timeout=None: la tienda debe seguir funcionando mientras exista el
        # mensaje, incluso después de un reinicio del bot.
        super().__init__(timeout=None)
        self.owner_id = owner_id

        for posicion, (categoria, clave) in enumerate(iterar_articulos()):
            self.add_item(
                BotonCompra(
                    owner_id,
                    categoria,
                    clave,
                    row=posicion // BOTONES_POR_FILA,
                )
            )


def iterar_articulos():
    """Pares ``(categoría, clave)`` en el orden en que se muestran."""

    for categoria in ORDEN_CATALOGOS:
        for clave in CATALOGOS[categoria]:
            yield categoria, clave


class TiendaMixin:
    """Catálogo de la tienda y los comandos de compra."""

    @app_commands.command(
        name="tienda",
        description="Muestra todas las compras disponibles en la tienda.",
    )
    async def tienda(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        await interaction.response.send_message(
            construir_catalogo(interaction),
            view=TiendaView(interaction.user.id),
        )

    @app_commands.command(
        name="comprar",
        description="Compra mejoras, equipamiento o tratamientos con tu dinero.",
    )
    @app_commands.describe(
        tipo="Categoría de compra",
        articulo="Artículo que quieres comprar.",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="Mejora", value="mejora"),
            app_commands.Choice(name="Equipamiento", value="equipamiento"),
            app_commands.Choice(name="Tratamiento", value="tratamiento"),
        ]
    )
    async def comprar(
        self,
        interaction: discord.Interaction,
        tipo: app_commands.Choice[str],
        articulo: str,
    ):
        if not await solo_servidor(interaction):
            return

        resultado = ejecutar_compra(
            interaction.guild.id,
            interaction.user.id,
            tipo.value,
            articulo,
        )
        await interaction.response.send_message(
            resultado.texto,
            ephemeral=not resultado.exitoso,
        )

    @app_commands.command(
        name="tratamiento",
        description="Compra un tratamiento para quitar una lesión.",
    )
    @app_commands.describe(tipo="Tratamiento que quieres comprar.")
    @app_commands.choices(
        tipo=[
            app_commands.Choice(
                name="Tratamiento Fisioterapeutico",
                value="fisioterapeutico",
            ),
            app_commands.Choice(
                name="Tratamiento 5 estrellas",
                value="cinco_estrellas",
            ),
        ]
    )
    async def tratamiento(
        self,
        interaction: discord.Interaction,
        tipo: app_commands.Choice[str],
    ):
        if not await solo_servidor(interaction):
            return

        resultado = ejecutar_compra(
            interaction.guild.id,
            interaction.user.id,
            "tratamiento",
            tipo.value,
        )
        await interaction.response.send_message(
            resultado.texto,
            ephemeral=not resultado.exitoso,
        )


def construir_catalogo(interaction) -> str:
    """Arma el texto del catálogo con los niveles actuales del usuario."""

    guild_id = interaction.guild.id
    user_id = interaction.user.id

    lineas = ["🛒 **Tienda de Box**", "\n**Mejoras**"]

    for clave, mejora in MEJORAS.items():
        nivel = obtener_nivel_mejora(guild_id, user_id, clave)
        lineas.append(
            f"{mejora['emoji']} **{mejora['nombre']}** — "
            f"{mejora['descripcion']} | "
            f"Nivel **{nivel}/{mejora['maximo']}** | "
            f"Siguiente nivel: **{precio_mejora(mejora['precio'], nivel)}**"
        )

    lineas.append("\n**Equipamiento**")
    equipo = obtener_equipo(guild_id, user_id)
    for clave, pieza in EQUIPAMIENTO.items():
        nivel_actual = equipo[clave] if equipo else 0
        calidad_actual = calidad_equipamiento(clave, nivel_actual)

        if es_nivel_maximo(clave, nivel_actual):
            detalle = " **(Máximo nivel)**"
        else:
            detalle = (
                f" → Siguiente: "
                f"**{calidad_equipamiento(clave, nivel_actual + 1)}** "
                f"({precio_equipamiento(pieza['precio_base'], nivel_actual + 1)}$)"
            )

        lineas.append(
            f"{pieza['emoji']} **{pieza['nombre']}** — "
            f"Actual: **{calidad_actual}**{detalle}"
        )

    lineas.append("\n**Tratamientos**")
    for tratamiento in TRATAMIENTOS.values():
        lineas.append(
            f"{tratamiento['emoji']} **{tratamiento['nombre']}** — "
            f"Precio fijo: **{tratamiento['precio']}**"
        )

    lineas.append(
        "\n💡 Tocá el botón de un artículo para comprarlo. "
        "Los botones de esta tienda solo funcionan para vos."
    )

    return "\n".join(lineas)
