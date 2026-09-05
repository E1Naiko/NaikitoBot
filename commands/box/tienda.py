"""Tienda de Box: catálogo y compras de mejoras, equipamiento y tratamientos."""

import discord
from discord import app_commands

from commands.box.base import solo_servidor
from core.utils import ahora
from modules.box.services import (
    EQUIPAMIENTO,
    MEJORAS,
    NIVEL_MAXIMO_EQUIPAMIENTO,
    TRATAMIENTOS,
    calidad_equipamiento,
    comprar_equipamiento_progresivo,
    comprar_mejora,
    comprar_tratamiento,
    es_nivel_maximo,
    obtener_equipo,
    obtener_nivel_mejora,
    precio_equipamiento,
    precio_mejora,
)

CATEGORIAS = ("mejora", "equipamiento", "tratamiento")


def _opciones(catalogo) -> str:
    return ", ".join(f"`{clave}`" for clave in catalogo)


class TiendaMixin:
    """Catálogo de la tienda y los comandos de compra."""

    @app_commands.command(
        name="tienda",
        description="Muestra todas las compras disponibles en la tienda.",
    )
    async def tienda(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        lineas = ["🛒 **Tienda de Box**", "\n**Mejoras**"]

        for clave, mejora in MEJORAS.items():
            nivel = obtener_nivel_mejora(
                interaction.guild.id,
                interaction.user.id,
                clave,
            )
            lineas.append(
                f"{mejora['emoji']} **{mejora['nombre']}** — "
                f"{mejora['descripcion']} | "
                f"Nivel **{nivel}/{mejora['maximo']}** | "
                f"Siguiente nivel: **{precio_mejora(mejora['precio'], nivel)}**"
            )

        lineas.append("\n**Equipamiento**")
        equipo = obtener_equipo(interaction.guild.id, interaction.user.id)
        for clave, pieza in EQUIPAMIENTO.items():
            nivel_actual = equipo[clave] if equipo else 0
            calidad_actual = calidad_equipamiento(clave, nivel_actual)

            if es_nivel_maximo(clave, nivel_actual):
                detalle = " **(Máximo nivel)**"
            else:
                siguiente = precio_equipamiento(
                    pieza["precio_base"],
                    nivel_actual + 1,
                )
                detalle = (
                    f" → Siguiente: "
                    f"**{calidad_equipamiento(clave, nivel_actual + 1)}** "
                    f"({siguiente}$)"
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

        await interaction.response.send_message("\n".join(lineas))

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

        clave = articulo.lower()
        manejadores = {
            "mejora": self._comprar_mejora,
            "equipamiento": self._comprar_equipamiento,
            "tratamiento": self._comprar_tratamiento,
        }
        manejador = manejadores.get(tipo.value)

        if manejador is None:
            await interaction.response.send_message(
                f"⚠️ Categoría no válida. Opciones: "
                f"{', '.join(f'`{c}`' for c in CATEGORIAS)}",
                ephemeral=True,
            )
            return

        await manejador(interaction, clave)

    async def _comprar_mejora(self, interaction, clave):
        if clave not in MEJORAS:
            await interaction.response.send_message(
                f"⚠️ Mejora no válida. Opciones: {_opciones(MEJORAS)}",
                ephemeral=True,
            )
            return

        configuracion = MEJORAS[clave]
        estado, saldo, nivel = comprar_mejora(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            mejora=clave,
            precio_base=configuracion["precio"],
            nivel_maximo=configuracion["maximo"],
        )

        if estado == "insuficiente":
            await interaction.response.send_message(
                f"⚠️ Necesitas el siguiente precio "
                f"(**{precio_mejora(configuracion['precio'], nivel)}**) "
                f"y tienes **{saldo}**.",
                ephemeral=True,
            )
            return

        if estado == "maximo":
            await interaction.response.send_message(
                f"⚠️ Ya alcanzaste el nivel máximo (**{nivel}**).",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Compraste un nivel de **{configuracion['nombre']}**. "
            f"Nivel actual: **{nivel}**. Saldo restante: **{saldo}**."
        )

    async def _comprar_equipamiento(self, interaction, clave):
        if clave not in EQUIPAMIENTO:
            await interaction.response.send_message(
                f"⚠️ Equipamiento no válido. Opciones: {_opciones(EQUIPAMIENTO)}",
                ephemeral=True,
            )
            return

        configuracion = EQUIPAMIENTO[clave]
        estado, saldo, nivel = comprar_equipamiento_progresivo(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            tipo_equipo=clave,
            precio_base=configuracion["precio_base"],
            nivel_maximo=NIVEL_MAXIMO_EQUIPAMIENTO,
        )

        if estado == "insuficiente":
            precio = precio_equipamiento(
                configuracion["precio_base"],
                nivel,
            )
            await interaction.response.send_message(
                f"⚠️ Necesitas **{precio}** y tienes **{saldo}**.",
                ephemeral=True,
            )
            return

        if estado == "maximo":
            await interaction.response.send_message(
                f"⚠️ Ya alcanzaste la calidad máxima "
                f"(**{calidad_equipamiento(clave, nivel)}**).",
                ephemeral=True,
            )
            return

        # En "comprado", nivel es el nivel ya incrementado.
        calidad_anterior = configuracion["calidades"][nivel - 1]
        calidad_nueva = configuracion["calidades"][nivel]
        await interaction.response.send_message(
            f"✅ ¡Compraste una mejora de equipamiento!\n"
            f"{configuracion['emoji']} **{configuracion['nombre']}**: "
            f"{calidad_anterior} → {calidad_nueva}\n"
            f"💰 Saldo restante: **{saldo}$**"
        )

    async def _comprar_tratamiento(self, interaction, clave):
        if clave not in TRATAMIENTOS:
            await interaction.response.send_message(
                f"⚠️ Tratamiento no válido. Opciones: {_opciones(TRATAMIENTOS)}",
                ephemeral=True,
            )
            return

        estado, saldo = self._aplicar_tratamiento(interaction, clave)

        if estado == "insuficiente":
            await interaction.response.send_message(
                f"⚠️ Necesitas **{TRATAMIENTOS[clave]['precio']}** "
                f"y tienes **{saldo}**.",
                ephemeral=True,
            )
            return

        if estado == "no_lesionado":
            await interaction.response.send_message(
                "⚠️ No estás lesionado.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Compraste **{TRATAMIENTOS[clave]['nombre']}**. "
            f"Saldo restante: **{saldo}**."
        )

    @staticmethod
    def _aplicar_tratamiento(interaction, clave):
        """Compra el tratamiento indicado y devuelve ``(estado, saldo)``."""

        configuracion = TRATAMIENTOS[clave]
        return comprar_tratamiento(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            precio=configuracion["precio"],
            ahora=ahora(),
            reinicia_probabilidad=configuracion["reinicia_probabilidad"],
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

        await self._comprar_tratamiento(interaction, tipo.value)
