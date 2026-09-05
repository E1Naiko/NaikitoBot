"""Administración de SeptSinFP: revivir participantes e iniciar desafíos."""

from datetime import date

import discord
from discord import app_commands

from commands.admin.base import solo_admin, solo_servidor
from modules.ssf.services import (
    revivir_participante,
    iniciar_desafio,
)


class SsfAdminMixin:
    """Comandos administrativos de SeptSinFP bajo ``/admin ssf``."""

    # ========================================================
    # GRUPO SSF
    # ========================================================

    ssf = app_commands.Group(
        name="ssf",
        description="Comandos administrativos de SeptSinFP.",
    )

    # ========================================================
    # SSF - REVIVIR
    # ========================================================

    @ssf.command(
        name="revivir",
        description="Revive a un participante eliminado de SeptSinFP.",
    )
    @app_commands.describe(
        usuario="Usuario eliminado que quieres revivir.",
        fecha="Día que olvidó registrar, en formato YYYY-MM-DD.",
    )
    async def ssf_revivir(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Revive un participante."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await interaction.response.send_message(
                "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-09-01`.",
                ephemeral=True,
            )
            return

        resultado = revivir_participante(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            fecha=fecha_obj,
        )

        if not resultado["exitoso"]:

            motivos = {
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "fuera_de_fecha": (
                    "⚠️ La fecha indicada está fuera "
                    "del período del desafío."
                ),
                "no_participante": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está registrado como participante "
                    "de SeptSinFP."
                ),
                "no_eliminado": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está eliminado.\n"
                    "No es necesario revivirlo."
                ),
                "ya_registrado": (
                    f"ℹ️ **{usuario.display_name}** "
                    f"ya tiene registrado el día **{fecha}**."
                ),
            }

            await interaction.response.send_message(
                motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo revivir al participante.",
                ),
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            f"💚 **Participante revivido correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Día recuperado: **{fecha}**\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n\n"
            f"🫡 **{usuario.display_name}** puede "
            "volver a utilizar `/ssf sobrevivi` normalmente."
        )

    # ========================================================
    # SSF - INICIAR
    # ========================================================

    @ssf.command(
        name="iniciar",
        description="Inicia un nuevo desafío SeptSinFP.",
    )
    @app_commands.describe(
        canal="Canal donde se utilizarán los comandos de SeptSinFP.",
    )
    async def ssf_iniciar(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
    ):
        """Inicia un nuevo desafío."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        fecha_inicio = "2026-09-01"
        fecha_fin = "2026-09-30"

        resultado = iniciar_desafio(
            guild_id=interaction.guild.id,
            nombre="SeptSinFP 2026",
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            canal_id=canal.id,
        )

        if not resultado["exitoso"]:

            if resultado["motivo"] == "ya_existe":
                mensaje = (
                    "⚠️ Ya existe un desafío SeptSinFP "
                    "activo en este servidor."
                )
            else:
                mensaje = (
                    "⚠️ No se pudo iniciar el desafío."
                )

            await interaction.response.send_message(
                mensaje,
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            f"🎯 **SeptSinFP iniciado correctamente.**\n\n"
            f"📋 Desafío: **SeptSinFP 2026**\n"
            f"🗓️ Inicio: **{fecha_inicio}**\n"
            f"🏁 Fin: **{fecha_fin}**\n"
            f"📢 Canal: {canal.mention}\n"
            f"🆔 ID del desafío: "
            f"**{resultado['desafio_id']}**\n\n"
            f"Los participantes ya pueden utilizar "
            f"**/ssf registrar** en {canal.mention}."
        )
