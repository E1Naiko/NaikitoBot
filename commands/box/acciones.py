"""Comandos de acciones temporizadas: entrenar, trabajar y promoverse."""

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import tasks

from commands.box.base import solo_servidor
from config import (
    BOX_CHANNEL_IDS,
    BOX_DINERO_POR_MINUTO,
    BOX_EXPERIENCIA_POR_MINUTO,
)
from core.utils import ahora
from modules.box.constants import NOMBRES_ACCIONES, NOMBRES_SPONSORS
from modules.box.services import (
    completar_acciones_vencidas,
    iniciar_accion,
    obtener_accion_activa,
    obtener_estado_box,
    obtener_nivel_mejora,
    resolver_duracion,
)

MENSAJES_DURACION = {
    "ambas": "⚠️ Indica minutos o una hora de finalización, no ambas opciones.",
    "formato_hora": (
        "⚠️ La hora debe tener el formato HH:MM, por ejemplo 18:30."
    ),
    "falta_duracion": "⚠️ Debes indicar minutos o una hora de finalización.",
    "fuera_rango": "⚠️ La duración debe estar entre 1 y 1440 minutos.",
}

UNIDAD_RECOMPENSA = {
    "ENTRENANDO": "EXP",
    "TRABAJANDO": "$",
}


def texto_recompensa(tipo: str, recompensa: int, dinero_recompensa: int) -> str:
    """Describe lo que el usuario recibió al terminar una acción."""

    if tipo == "TRABAJANDO":
        return f"**{dinero_recompensa} $**"

    if tipo == "PROMOVIENDO":
        return "🎯 búsqueda de sponsor"

    texto = f"**{recompensa} EXP**"
    if dinero_recompensa:
        texto += f" y recibió **{dinero_recompensa} $**"

    return texto


class AccionesMixin:
    """Entrenar, trabajar y promoverse, más la liquidación periódica."""

    @tasks.loop(seconds=15)
    async def comprobar_acciones(self):
        """Liquida acciones vencidas y avisa en el canal disponible.

        Las acciones se liquidan siempre, haya o no canal donde anunciarlas:
        el progreso del usuario no puede depender de la configuración.
        """

        canal = self._canal_box()

        for (
            guild_id,
            user_id,
            tipo,
            recompensa,
            dinero_recompensa,
            se_lesiona,
            _probabilidad_sponsor,
            sponsor,
        ) in completar_acciones_vencidas(ahora()):
            if canal is None:
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            usuario = guild.get_member(user_id)
            if usuario is None:
                try:
                    usuario = await guild.fetch_member(user_id)
                except discord.HTTPException:
                    continue

            if tipo == "PROMOVIENDO":
                await self._anunciar_promocion(canal, usuario, sponsor)
                continue

            nombre_accion = NOMBRES_ACCIONES.get(tipo, tipo.lower())
            await canal.send(
                f"✅ {usuario.mention} terminó de "
                f"**{nombre_accion}** y recibió "
                f"{texto_recompensa(tipo, recompensa, dinero_recompensa)}."
            )

            if se_lesiona:
                await canal.send(
                    f"🚑 {usuario.mention} se lesionó y estará "
                    "lesionado durante 3 horas."
                )

    @comprobar_acciones.before_loop
    async def esperar_bot(self):
        await self.bot.wait_until_ready()

    def _canal_box(self):
        """Primer canal configurado de Box que acepta mensajes."""

        for canal_id in BOX_CHANNEL_IDS:
            canal = self.bot.get_channel(canal_id)
            if isinstance(canal, discord.abc.Messageable):
                return canal

        return None

    @staticmethod
    async def _anunciar_promocion(canal, usuario, sponsor):
        if sponsor:
            nombre_sponsor = NOMBRES_SPONSORS.get(
                sponsor,
                sponsor.capitalize(),
            )
            await canal.send(
                f"🎉 {usuario.mention} terminó de "
                f"**promocionarse** y consiguió un sponsor: "
                f"**{nombre_sponsor}**."
            )
            return

        await canal.send(
            f"📢 {usuario.mention} terminó de "
            f"**promocionarse**, pero no consiguió "
            "ningún sponsor esta vez."
        )

    async def _comenzar_accion(
        self,
        interaction: discord.Interaction,
        minutos: int | None,
        tipo: str,
        recompensa_por_minuto: int,
        hasta: str | None = None,
        permitir_lesionado: bool = False,
    ):
        """Valida el estado del usuario y registra la acción."""

        if not await solo_servidor(interaction):
            return

        _, lesionado_hasta = obtener_estado_box(
            interaction.guild.id,
            interaction.user.id,
        )

        if (
            not permitir_lesionado
            and lesionado_hasta
            and datetime.fromisoformat(lesionado_hasta) > ahora()
        ):
            final = datetime.fromisoformat(lesionado_hasta)
            await interaction.response.send_message(
                f"🚑 Estás lesionado hasta <t:{int(final.timestamp())}:R>.",
                ephemeral=True,
            )
            return

        iniciado_en = ahora()
        duracion, motivo = resolver_duracion(minutos, hasta, iniciado_en)
        if duracion is None:
            await interaction.response.send_message(
                MENSAJES_DURACION[motivo],
                ephemeral=True,
            )
            return

        accion = obtener_accion_activa(
            interaction.guild.id,
            interaction.user.id,
        )
        if accion is not None:
            tipo_actual, finaliza_en, _ = accion
            timestamp = int(datetime.fromisoformat(finaliza_en).timestamp())
            await interaction.response.send_message(
                f"⚠️ Ya estás **{tipo_actual.lower()}**. "
                f"Tu acción termina <t:{timestamp}:R>.",
                ephemeral=True,
            )
            return

        recompensa = duracion.minutos * recompensa_por_minuto

        if not iniciar_accion(
            interaction.guild.id,
            interaction.user.id,
            tipo,
            iniciado_en,
            duracion.finaliza_en,
            recompensa,
        ):
            await interaction.response.send_message(
                "⚠️ Ya tienes otra acción activa.",
                ephemeral=True,
            )
            return

        finaliza = int(duracion.finaliza_en.timestamp())

        if tipo == "PROMOVIENDO":
            await interaction.response.send_message(
                f"📢 Comenzaste a **promocionarte** durante "
                f"**{duracion.minutos} minutos**.\n"
                f"⏰ Finaliza <t:{finaliza}:R>.\n"
                f"🎯 Cuanto más tiempo te promociones, mayores serán tus "
                f"chances de conseguir un sponsor."
            )
            return

        unidad = UNIDAD_RECOMPENSA.get(tipo, "EXP")
        await interaction.response.send_message(
            f"✅ Comenzaste a **{tipo.lower()}** durante "
            f"**{duracion.minutos} minutos**.\n"
            f"⏰ Finaliza <t:{finaliza}:R>.\n"
            f"🎁 Recompensa: **{recompensa} {unidad}**.",
        )

    @app_commands.command(
        name="entrenar",
        description="Entrena durante un tiempo para obtener experiencia.",
    )
    @app_commands.describe(
        minutos="Cantidad de minutos de entrenamiento (1-1440).",
        hasta="Hora a la que quieres terminar, formato HH:MM.",
    )
    async def entrenar(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        nivel = (
            obtener_nivel_mejora(
                interaction.guild.id,
                interaction.user.id,
                "entrenamiento",
            )
            if interaction.guild
            else 0
        )

        await self._comenzar_accion(
            interaction,
            minutos,
            "ENTRENANDO",
            BOX_EXPERIENCIA_POR_MINUTO + nivel * 5,
            hasta,
        )

    @app_commands.command(
        name="trabajar",
        description="Trabaja durante un tiempo para obtener dinero.",
    )
    @app_commands.describe(
        minutos="Cantidad de minutos de trabajo (1-1440).",
        hasta="Hora a la que quieres terminar, formato HH:MM.",
    )
    async def trabajar(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        nivel = (
            obtener_nivel_mejora(
                interaction.guild.id,
                interaction.user.id,
                "trabajo",
            )
            if interaction.guild
            else 0
        )

        await self._comenzar_accion(
            interaction,
            minutos,
            "TRABAJANDO",
            BOX_DINERO_POR_MINUTO + nivel * 50,
            hasta,
        )

    @app_commands.command(
        name="promoverme",
        description=(
            "Promocionate durante un tiempo para intentar "
            "conseguir un sponsor."
        ),
    )
    @app_commands.describe(
        minutos="Cantidad de minutos que quieres promocionarte (1-1440).",
        hasta="Hora a la que quieres terminar, formato HH:MM.",
    )
    async def promoverme(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        await self._comenzar_accion(
            interaction,
            minutos,
            "PROMOVIENDO",
            0,
            hasta,
            permitir_lesionado=True,
        )
