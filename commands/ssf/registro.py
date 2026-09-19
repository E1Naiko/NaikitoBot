"""Registro de participantes y supervivencia diaria de SeptSinFP."""

import discord
from discord import app_commands

from commands.ssf.base import solo_servidor
from core.mensajes import responder, responder_error
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

        resultado = await registrar_usuario(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            ahora=ahora(),
        )

        if not resultado["exitoso"]:
            if resultado["motivo"] == "fuera_de_fecha":
                detalle = (
                    f"**{resultado['nombre']}** "
                    "no está en período de inscripción."
                )
                titulo = "⚠️ Fuera de inscripción"
            else:
                motivos = {
                    "sin_desafio": "No hay un desafío SeptSinFP activo.",
                    "eliminado": "💀 Ya estás eliminado de este desafío.",
                    "ya_registrado": "ℹ️ Ya estás registrado en el desafío.",
                }
                detalle = motivos.get(
                    resultado["motivo"],
                    "No pudiste registrarte en el desafío.",
                )
                titulo = "⚠️ Registro no disponible"

            await responder_error(
                interaction,
                titulo,
                detalle,
            )
            return

        await responder(
            interaction,
            f"🎯 ¡{interaction.user.display_name} se registró!",
            color_area="ssf",
            secciones_=[
                ("🗓️ Desafío", f"**{resultado['nombre']}**"),
                (
                    "📅 Período",
                    f"**{resultado['fecha_inicio']}** → "
                    f"**{resultado['fecha_fin']}**",
                ),
                ("🔥 Racha actual", f"**{resultado['racha']} días**"),
                ("🫡 Rango", f"**{resultado['rango']}**"),
                (
                    "💡 Recordatorio",
                    "Registrarse cuenta como haber sobrevivido hoy. "
                    "No olvides usar `/ssf sobrevivi` cada día.",
                ),
            ],
        )

    @app_commands.command(
        name="sobrevivi",
        description="Registra que sobreviviste el día.",
    )
    async def sobrevivi(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        resultado = await registrar_sobrevivi(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            ahora=ahora(),
        )

        if not resultado["exitoso"]:
            motivos = {
                "sin_desafio": "No hay un desafío SeptSinFP activo.",
                "fuera_de_fecha": "Hoy no es un día del desafío.",
                "no_participante": (
                    "No estás registrado en el desafío. "
                    "Usa `/ssf registrar` primero."
                ),
                "eliminado": "💀 Estás eliminado de este desafío.",
                "ya_registrado": "ℹ️ Ya registraste tu supervivencia de hoy.",
            }

            await responder_error(
                interaction,
                "⚠️ Supervivencia no registrada",
                motivos.get(
                    resultado["motivo"],
                    "No se pudo registrar tu supervivencia.",
                ),
            )
            return

        await responder(
            interaction,
            f"🔥 ¡{interaction.user.display_name} sobrevivió el día "
            f"{resultado['fecha'].strftime('%d/%m')}!",
            color_area="ssf",
            secciones_=[
                ("🔥 Racha actual", f"**{resultado['racha']} días**"),
                ("🏆 Mejor racha", f"**{resultado['mejor_racha']} días**"),
                ("🫡 Rango", f"**{resultado['rango']}**"),
            ],
        )
