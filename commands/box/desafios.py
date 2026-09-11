"""Desafíos entre usuarios: sparring y pelea, con su vista de botones."""

from datetime import datetime, timedelta

import discord
from discord import app_commands

from commands.box.base import solo_servidor
from config import (
    BOX_CHANNEL_IDS,
    BOX_DESAFIO_DURACION_HORAS,
    BOX_DESAFIO_VENTANA_HORAS,
    BOX_DESAFIO_EXP_PELEA,
    BOX_DESAFIO_EXP_SPARRING,
    BOX_DESAFIO_RECOMPENSA_POR_MEJORA,
    BOX_EXPERIENCIA_POR_MINUTO,
)
from core.mensajes import crear_embed, responder, responder_error, seccion
from core.permissions import es_admin
from core.utils import ahora
from modules.box.logic import texto_horas
from modules.box.services import (
    aceptar_desafio,
    crear_desafio,
    obtener_accion_activa,
    obtener_estado_box,
    preparar_bot_para_desafio,
)

VENTANA_DESAFIO = timedelta(hours=BOX_DESAFIO_VENTANA_HORAS)
DURACION_DESAFIO = timedelta(hours=BOX_DESAFIO_DURACION_HORAS)

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
        super().__init__(timeout=int(BOX_DESAFIO_VENTANA_HORAS * 3600))
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
                "Ambos competirán durante "
                f"{texto_horas(BOX_DESAFIO_DURACION_HORAS)}.",
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
            recompensa=(
                int(BOX_DESAFIO_DURACION_HORAS * 60)
                * BOX_EXPERIENCIA_POR_MINUTO
            ),
            tipo=tipo,
            multiplicador_experiencia=(
                BOX_DESAFIO_EXP_PELEA
                if tipo == "FIGHTING"
                else BOX_DESAFIO_EXP_SPARRING
            ),
            recompensa_por_mejora=BOX_DESAFIO_RECOMPENSA_POR_MEJORA,
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

        # ------------------------------------------------------------
        # CASO ESPECIAL: desafiar al bot -> auto-acepta con stats random
        # ------------------------------------------------------------
        es_bot = getattr(contrincante, "bot", False)
        if not es_bot and self.bot.user is not None:
            es_bot = contrincante.id == self.bot.user.id

        if es_bot:
            inicio = ahora()

            # Randomiza stats del bot entre los extremos del servidor
            # (min por stat = jugador más bajo, max = jugador más alto)
            info_bot = preparar_bot_para_desafio(
                interaction.guild.id,
                contrincante.id,
            )

            # Asegurar que no quede un desafío pendiente duplicado previo
            # (preparar_bot ya limpia, pero reforzamos para el par exacto)
            try:
                from core.database import conectar_db

                with conectar_db() as _db:
                    _db.execute(
                        """
                        DELETE FROM box_desafios
                        WHERE guild_id = ?
                        AND retador_id = ?
                        AND contrincante_id = ?
                        """,
                        (
                            interaction.guild.id,
                            interaction.user.id,
                            contrincante.id,
                        ),
                    )
                    _db.commit()
            except Exception:
                pass

            desafio_id = crear_desafio(
                guild_id=interaction.guild.id,
                retador_id=interaction.user.id,
                contrincante_id=contrincante.id,
                ahora=inicio,
                expira_en=inicio + VENTANA_DESAFIO,
            )
            if desafio_id is None:
                await responder_error(
                    interaction,
                    "⚠️ Desafío pendiente",
                    "Ya existe un desafío pendiente con ese usuario.",
                )
                return

            resultado = await self._aceptar_desafio(
                interaction,
                desafio_id,
                contrincante.id,
                tipo,
            )

            if resultado["estado"] == "aceptado":
                vals = info_bot["valores"]
                rangos = info_bot["rangos_equipo"]
                embed = crear_embed(
                    "🤖 ¡El bot aceptó tu desafío!",
                    f"Has desafiado al bot y **aceptó al instante**.\n"
                    f"Ambos competirán durante {texto_horas(BOX_DESAFIO_DURACION_HORAS)}.",
                    color_area="box",
                )
                seccion(embed, "Modalidad", f"**{tipo.lower()}**")
                seccion(
                    embed,
                    "Stats del bot (randomizados)",
                    (
                        f"❤️ Vida: **{vals['vida']}/{vals['vida_maxima']}** "
                        f"(rango server {rangos['vida'][0]}-{rangos['vida'][1]})\n"
                        f"💥 Daño: **{vals['dano']}/{vals['dano_maximo']}** "
                        f"(rango {rangos['dano'][0]}-{rangos['dano'][1]})\n"
                        f"🛡️ Defensa: **{vals['defensa']}/{vals['defensa_maxima']}** "
                        f"(rango {rangos['defensa'][0]}-{rangos['defensa'][1]})\n"
                        f"⚡ Cansancio: **{vals['cansancio']}/{vals['cansancio_maximo']}** "
                        f"(rango {rangos['cansancio'][0]}-{rangos['cansancio'][1]})\n"
                        f"⭐ Exp: **{info_bot['experiencia']}** "
                        f"(rango {info_bot['rango_experiencia'][0]}-{info_bot['rango_experiencia'][1]})\n"
                        f"🎒 Equipamiento: casco **{vals['casco']}**, guantes **{vals['guantes']}**, "
                        f"bucal **{vals['protector_bucal']}**, short **{vals['short']}**, botas **{vals['botas']}**"
                    ),
                )
                if resultado.get("ganador_id") is not None:
                    ganador_mencion = (
                        contrincante.mention
                        if resultado["ganador_id"] == contrincante.id
                        else interaction.user.mention
                    )
                    seccion(
                        embed,
                        "Pelea — ganador sorteado",
                        f"{ganador_mencion} se lleva **${resultado['premio_dinero']:,}**",
                    )
                await interaction.response.send_message(embed=embed)
                return

            # Si el bot no pudo aceptar (ej. error inesperado), mapear a mensaje humano
            mensaje = MENSAJES_DESAFIO_NO_DISPONIBLE.get(
                resultado["estado"],
                "El desafío al bot no pudo completarse.",
            )
            await responder_error(
                interaction,
                "⚠️ Desafío no disponible",
                mensaje,
            )
            return

        inicio = ahora()
        desafio_id = crear_desafio(
            guild_id=interaction.guild.id,
            retador_id=interaction.user.id,
            contrincante_id=contrincante.id,
            ahora=inicio,
            expira_en=inicio + VENTANA_DESAFIO,
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
        seccion(
            embed,
            "Tiempo",
            f"Tienes **{texto_horas(BOX_DESAFIO_VENTANA_HORAS)}** para aceptar.",
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="sparring",
        description=(
            "Desafía a otro usuario a un sparring de "
            f"{texto_horas(BOX_DESAFIO_DURACION_HORAS)}."
        ),
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
        description=(
            "Desafía a otro usuario a una pelea de "
            f"{texto_horas(BOX_DESAFIO_DURACION_HORAS)}."
        ),
    )
    @app_commands.describe(contrincante="Usuario al que quieres desafiar.")
    async def desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
    ):
        await self._crear_desafio(interaction, contrincante, "FIGHTING")
