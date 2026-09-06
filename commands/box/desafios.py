"""Desafíos entre usuarios: sparring y pelea, con su vista de botones."""

from datetime import datetime, timedelta

import discord
from discord import app_commands

from commands.box.base import solo_servidor
from config import BOX_CHANNEL_IDS, BOX_EXPERIENCIA_POR_MINUTO
from core.mensajes import crear_embed, responder, responder_error, seccion
from core.permissions import es_admin
from core.utils import ahora
from modules.box.services import (
    aceptar_desafio,
    crear_desafio,
    obtener_accion_activa,
    obtener_estado_box,
)

DURACION_DESAFIO = timedelta(hours=1)

MENSAJES_DESAFIO_NO_DISPONIBLE = {
    "expirado": "⌛ El desafío ya expiró.",
    "ocupado": "⚠️ Uno de los dos usuarios ya tiene una acción activa.",
    "lesionado": "🚑 Uno de los dos usuarios está lesionado.",
}


class ChallengeView(discord.ui.View):
    """Permite que solo el contrincante acepte un desafío."""

    def __init__(
        self,
        box,
        desafio_id: int,
        contrincante_id: int,
        tipo: str,
    ):
        super().__init__(timeout=3600)
        self.box = box
        self.desafio_id = desafio_id
        self.contrincante_id = contrincante_id
        self.tipo = tipo
        self.message = None

    @discord.ui.button(
        label="Aceptar desafío",
        style=discord.ButtonStyle.success,
    )
    async def aceptar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if (
            not es_admin(interaction.user.id)
            and interaction.channel_id not in BOX_CHANNEL_IDS
        ):
            await responder_error(
                interaction,
                "⚠️ Canal incorrecto",
                "Este desafío solo puede aceptarse en el canal de Box.",
            )
            return

        if interaction.user.id != self.contrincante_id:
            await responder_error(
                interaction,
                "⚠️ No autorizado",
                "Solo el contrincante puede aceptar este desafío.",
            )
            return

        resultado = await self.box._aceptar_desafio(
            interaction,
            self.desafio_id,
            self.contrincante_id,
            self.tipo,
        )

        if resultado["estado"] == "aceptado":
            button.disabled = True
            nombre = self.tipo.lower()
            embed = crear_embed(
                "🥊 ¡Desafío aceptado!",
                f"Ambos competirán durante 1 hora.",
                color_area="box",
            )
            seccion(embed, "Modalidad", f"**{nombre}**")
            await interaction.response.edit_message(
                embed=embed,
                view=self,
            )
            self.stop()
            return

        embed = crear_embed(
            "⚠️ Desafío no disponible",
            MENSAJES_DESAFIO_NO_DISPONIBLE.get(
                resultado["estado"],
                "El desafío ya no está disponible.",
            ),
            color_area="error",
        )
        await interaction.response.edit_message(
            embed=embed,
            view=None,
        )
        self.stop()

    async def on_timeout(self):
        if self.message is not None:
            embed = crear_embed(
                "⌛ Desafío expirado",
                "El desafío de sparring expiró.",
                color_area="aviso",
            )
            await self.message.edit(
                embed=embed,
                view=None,
            )


class DesafiosMixin:
    """Crear y aceptar desafíos de sparring y de pelea."""

    async def _aceptar_desafio(
        self,
        interaction: discord.Interaction,
        desafio_id: int,
        contrincante_id: int,
        tipo: str,
    ):
        if interaction.guild is None:
            return {"estado": "invalido"}

        return aceptar_desafio(
            desafio_id=desafio_id,
            guild_id=interaction.guild.id,
            contrincante_id=contrincante_id,
            ahora=ahora(),
            recompensa=60 * BOX_EXPERIENCIA_POR_MINUTO,
            tipo=tipo,
            multiplicador_experiencia=10 if tipo == "FIGHTING" else 5,
            recompensa_por_mejora=5,
        )

    async def _crear_desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
        tipo: str,
    ):
        if not await solo_servidor(interaction):
            return

        if contrincante.id == interaction.user.id:
            await responder_error(
                interaction,
                "⚠️ Desafío inválido",
                "No puedes desafiarte a ti mismo.",
            )
            return

        if obtener_accion_activa(interaction.guild.id, interaction.user.id):
            await responder_error(
                interaction,
                "⚠️ Acción activa",
                "Ya tienes una acción activa.",
            )
            return

        _, lesionado_hasta = obtener_estado_box(
            interaction.guild.id,
            interaction.user.id,
        )
        if lesionado_hasta and datetime.fromisoformat(lesionado_hasta) > ahora():
            await responder_error(
                interaction,
                "🚑 Lesión activa",
                "No puedes desafiar a otro usuario mientras estás lesionado.",
            )
            return

        inicio = ahora()
        desafio_id = crear_desafio(
            guild_id=interaction.guild.id,
            retador_id=interaction.user.id,
            contrincante_id=contrincante.id,
            ahora=inicio,
            expira_en=inicio + DURACION_DESAFIO,
        )
        if desafio_id is None:
            await responder_error(
                interaction,
                "⚠️ Desafío pendiente",
                "Ya existe un desafío pendiente con ese usuario.",
            )
            return

        view = ChallengeView(self, desafio_id, contrincante.id, tipo)
        embed = crear_embed(
            "🥊 ¡Nuevo desafío!",
            f"{contrincante.mention}, {interaction.user.mention} "
            "te desafía.",
            color_area="box",
        )
        seccion(embed, "Modalidad", f"**{tipo.lower()}**")
        seccion(embed, "Tiempo", "Tienes **1 hora** para aceptar.")
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="sparring",
        description="Desafía a otro usuario a un sparring de una hora.",
    )
    @app_commands.describe(contrincante="Usuario al que quieres desafiar.")
    async def sparring(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
    ):
        await self._crear_desafio(interaction, contrincante, "SPARRING")

    @app_commands.command(
        name="desafio",
        description="Desafía a otro usuario a una pelea de una hora.",
    )
    @app_commands.describe(contrincante="Usuario al que quieres desafiar.")
    async def desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
    ):
        await self._crear_desafio(interaction, contrincante, "FIGHTING")
