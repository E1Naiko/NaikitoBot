"""Registro de participantes y supervivencia diaria de SeptSinFP."""

import discord
from discord import app_commands

from commands.ssf.base import solo_servidor
from core.utils import ahora
from modules.ssf.services import (
    registrar_sobrevivi,
    registrar_usuario,
)


class RegistroMixin:
    """Comandos para anotarse y registrar la supervivencia diaria."""

    @app_commands.command(
        name="registrar",
        description="Regístrate como participante de SeptSinFP.",
    )
    async def registrar(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        resultado = registrar_usuario(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            ahora=ahora(),
        )

        if not resultado["exitoso"]:
            if resultado["motivo"] == "fuera_de_fecha":
                mensaje = (
                    f"⚠️ **{resultado['nombre']}** "
                    "no está en período de inscripción."
                )
            else:
                motivos = {
                    "sin_desafio": (
                        "⚠️ No hay un desafío SeptSinFP activo."
                    ),
                    "eliminado": (
                        "💀 Ya estás eliminado de este desafío."
                    ),
                    "ya_registrado": (
                        "ℹ️ Ya estás registrado en el desafío."
                    ),
                }

                mensaje = motivos.get(
                    resultado["motivo"],
                    "⚠️ No pudiste registrarte en el desafío.",
                )

            await interaction.response.send_message(
                mensaje,
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🎯 **¡{interaction.user.mention} se registró en "
            f"{resultado['nombre']}!**\n\n"
            f"🗓️ Desafío: **{resultado['fecha_inicio']}** → "
            f"**{resultado['fecha_fin']}**\n"
            f"🔥 Racha actual: **{resultado['racha']} días**\n"
            f"🫡 Rango: **{resultado['rango']}**\n\n"
            "Registrarse cuenta como haber sobrevivido hoy. "
            "No olvides usar `/ssf sobrevivi` cada día."
        )

    @app_commands.command(
        name="sobrevivi",
        description="Registra que sobreviviste el día.",
    )
    async def sobrevivi(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        resultado = registrar_sobrevivi(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            ahora=ahora(),
        )

        if not resultado["exitoso"]:
            motivos = {
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "fuera_de_fecha": (
                    "⚠️ Hoy no es un día del desafío."
                ),
                "no_participante": (
                    "ℹ️ No estás registrado en el desafío.\n"
                    "Usa `/ssf registrar` primero."
                ),
                "eliminado": (
                    "💀 Estás eliminado de este desafío."
                ),
                "ya_registrado": (
                    "ℹ️ Ya registraste tu supervivencia de hoy."
                ),
            }

            await interaction.response.send_message(
                motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo registrar tu supervivencia.",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🔥 **¡{interaction.user.mention} sobrevivió el día "
            f"{resultado['fecha'].strftime('%d/%m')}!**\n\n"
            f"🔥 Racha actual: **{resultado['racha']} días**\n"
            f"🏆 Mejor racha: **{resultado['mejor_racha']} días**\n"
            f"🫡 Rango: **{resultado['rango']}**"
        )
