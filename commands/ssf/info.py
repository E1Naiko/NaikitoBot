"""Consultas de SeptSinFP: estado, participantes y ayuda."""

import discord
from discord import app_commands

from commands.ssf.base import solo_servidor
from core.mensajes import crear_embed, responder, responder_error, responder_ok
from modules.ssf.services import (
    TEXTO_AYUDA,
    calcular_rango,
    obtener_estado_desafio,
    obtener_estado_usuario,
    obtener_lista_participantes,
)


class InfoMixin:
    """Comandos de consulta del desafío y sus participantes."""

    @app_commands.command(
        name="ayuda",
        description="Envía por mensaje directo la ayuda de SeptSinFP.",
    )
    async def ayuda(self, interaction: discord.Interaction):
        try:
            await interaction.user.send(
                embed=crear_embed(
                    "SeptSinFP — Ayuda",
                    TEXTO_AYUDA,
                    color_area="ssf",
                )
            )
        except discord.Forbidden:
            await responder_error(
                interaction,
                "⚠️ Mensaje directo bloqueado",
                "No pude enviarte un mensaje directo. Activa los "
                "mensajes directos de este servidor e inténtalo otra vez.",
            )
            return

        await responder_ok(
            interaction,
            "✅ Ayuda enviada",
            "Te envié la ayuda de SeptSinFP por mensaje directo.",
        )

    @app_commands.command(
        name="estado",
        description="Muestra tu estado, rachas y rango en el desafío.",
    )
    async def estado(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        resultado = obtener_estado_usuario(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        if not resultado["exitoso"]:
            motivos = {
                "sin_desafio": "No hay un desafío SeptSinFP activo.",
                "no_participante": (
                    "No estás registrado en el desafío. "
                    "Usa `/ssf registrar` primero."
                ),
            }
            await responder_error(
                interaction,
                "⚠️ Estado no disponible",
                motivos.get(
                    resultado["motivo"],
                    "No se pudo obtener tu estado.",
                ),
            )
            return

        secciones_ = [
            ("🫡 Rango", f"**{resultado['rango']}**"),
            ("🔥 Racha actual", f"**{resultado['racha_actual']} días**"),
            ("🏆 Mejor racha", f"**{resultado['mejor_racha']} días**"),
        ]
        if resultado["eliminado"]:
            secciones_.append(
                (
                    "💀 Eliminado",
                    f"El **{resultado['fecha_eliminacion']}**.",
                )
            )

        await responder(
            interaction,
            f"📊 Estado de {interaction.user.display_name} "
            f"en {resultado['nombre']}",
            color_area="ssf",
            ephemeral=True,
            secciones_=secciones_,
        )

    @app_commands.command(
        name="participantes",
        description="Muestra los participantes del desafío.",
    )
    async def participantes(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        desafio = obtener_estado_desafio(
            interaction.guild.id,
        )

        if desafio is None:
            await responder_error(
                interaction,
                "⚠️ Sin desafío",
                "No hay un desafío SeptSinFP activo.",
            )
            return

        lista = obtener_lista_participantes(
            interaction.guild.id,
        )

        if not lista:
            await responder(
                interaction,
                "📋 Participantes",
                "Todavía no hay participantes registrados.",
                color_area="ssf",
            )
            return

        lineas = []
        for participante in lista:
            (
                _user_id,
                username,
                _fecha_registro,
                eliminado,
                _fecha_eliminacion,
                racha_actual,
                _mejor_racha,
            ) = participante

            rango = calcular_rango(racha_actual)

            estado = "💀" if eliminado else "🟢"
            lineas.append(
                f"{estado} **{username}** — "
                f"🔥 {racha_actual} días — {rango}"
            )

        await responder(
            interaction,
            f"📋 Participantes de {desafio['nombre']}",
            f"{desafio['activos']} activos, "
            f"{desafio['eliminados']} eliminados.",
            color_area="ssf",
            secciones_=[
                ("Listado", "\n".join(lineas), False),
            ],
        )
