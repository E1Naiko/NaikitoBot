"""Consultas de SeptSinFP: estado, participantes y ayuda."""

import discord
from discord import app_commands

from commands.ssf.base import solo_servidor
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
            await interaction.user.send(TEXTO_AYUDA)
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ No pude enviarte un mensaje directo. "
                "Activa los mensajes directos de este servidor "
                "e inténtalo otra vez.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "✅ Te envié la ayuda de SeptSinFP por mensaje directo.",
            ephemeral=True,
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
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "no_participante": (
                    "ℹ️ No estás registrado en el desafío.\n"
                    "Usa `/ssf registrar` primero."
                ),
            }

            await interaction.response.send_message(
                motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo obtener tu estado.",
                ),
                ephemeral=True,
            )
            return

        texto = (
            f"📊 **Estado de {interaction.user.display_name} "
            f"en {resultado['nombre']}**\n\n"
            f"🫡 Rango: **{resultado['rango']}**\n"
            f"🔥 Racha actual: **{resultado['racha_actual']} días**\n"
            f"🏆 Mejor racha: **{resultado['mejor_racha']} días**"
        )

        if resultado["eliminado"]:
            texto += (
                f"\n\n💀 Eliminado el "
                f"**{resultado['fecha_eliminacion']}**."
            )

        await interaction.response.send_message(
            texto,
            ephemeral=True,
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
            await interaction.response.send_message(
                "⚠️ No hay un desafío SeptSinFP activo.",
                ephemeral=True,
            )
            return

        lista = obtener_lista_participantes(
            interaction.guild.id,
        )

        if not lista:
            await interaction.response.send_message(
                "📋 Todavía no hay participantes registrados."
            )
            return

        lineas = [
            f"📋 **Participantes de {desafio['nombre']}** — "
            f"{desafio['activos']} activos, "
            f"{desafio['eliminados']} eliminados"
        ]

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

            if eliminado:
                lineas.append(
                    f"💀 **{username}** — "
                    f"🔥 {racha_actual} días — "
                    f"{rango}"
                )
            else:
                lineas.append(
                    f"🟢 **{username}** — "
                    f"🔥 {racha_actual} días — "
                    f"{rango}"
                )

        await interaction.response.send_message("\n".join(lineas))
