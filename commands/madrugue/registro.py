"""Registro diario de Madrugue."""

import discord
from discord import app_commands

from commands.madrugue.base import solo_servidor
from core.mensajes import responder, responder_error
from core.utils import ahora
from modules.madrugue.services import registrar_madrugue


class RegistroMixin:
    """Comando para registrar la madrugada."""

    @app_commands.command(
        name="madrugue",
        description="Registra tu madrugada.",
    )
    async def madrugue(
        self,
        interaction: discord.Interaction,
    ):
        """Registra directamente una madrugada."""

        if not await solo_servidor(interaction):
            return

        resultado = registrar_madrugue(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            ahora=ahora(),
        )

        if resultado.motivo == "fuera_de_horario":
            await responder(
                interaction,
                "🌙 Fuera de horario",
                f"{interaction.user.mention} todavía no es hora de "
                "madrugar para el ranking.",
                color_area="madrugue",
                secciones_=[
                    (
                        "⏰ Horario válido",
                        "**05:30 a 10:00**",
                    ),
                    (
                        "🇦🇷 Hora actual",
                        f"**{resultado.hora.strftime('%H:%M')}**",
                    ),
                ],
            )
            return

        if resultado.motivo == "ya_registrado":
            await responder(
                interaction,
                "⚠️ Ya registrado",
                f"{interaction.user.mention} ya registraste tu "
                "madrugada de hoy.",
                color_area="aviso",
                secciones_=[
                    ("⏰ Hora registrada", f"**{resultado.hora_anterior}**"),
                    (
                        "📊 Puntos obtenidos",
                        f"**{resultado.puntos_anterior:.0f}**",
                    ),
                ],
            )
            return

        await responder(
            interaction,
            f"🌅 ¡Madrugaste, {interaction.user.mention}!",
            color_area="madrugue",
            secciones_=[
                ("⏰ Hora", f"**{resultado.hora.strftime('%H:%M')}**"),
                ("💰 Puntos base", f"**{resultado.puntos_base}**"),
                ("🔥 Racha", f"**{resultado.racha} días**"),
                ("⭐ Multiplicador", f"**×{resultado.multiplicador:.3f}**"),
                ("🏆 Puntos obtenidos", f"**{resultado.puntos_finales:.1f}**"),
                ("📊 Puntos acumulados", f"**{resultado.total_puntos:.1f}**"),
            ],
        )
