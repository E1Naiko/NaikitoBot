"""Acciones temporizadas: entrenar, trabajar, promoverse y descansar."""

import discord
from discord import app_commands
from discord.ext import tasks

from commands.box.base import solo_servidor
from config import (
    BOX_CHANNEL_IDS,
    BOX_DESCANSO_REDUCCION_POR_HORA,
    BOX_DINERO_POR_MINUTO,
    BOX_EXPERIENCIA_POR_MINUTO,
    BOX_LESION_HORAS,
    BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL,
    BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL,
    BOX_MINUTOS_MAXIMO,
    BOX_MINUTOS_MINIMO,
)
from core.mensajes import crear_embed, responder, responder_error, seccion
from core.utils import ahora
from modules.box.constants import NOMBRES_ACCIONES, NOMBRES_SPONSORS
from modules.box.logic import texto_horas
from modules.box.services import (
    completar_acciones_vencidas,
    iniciar_accion,
    obtener_accion_activa,
    obtener_estado_box,
    obtener_nivel_mejora,
    reducir_probabilidad_lesion_inactivos,
    resolver_duracion,
)

MENSAJES_DURACION = {
    "ambas": "⚠️ Indica minutos o una hora de finalización, no ambas opciones.",
    "formato_hora": (
        "⚠️ La hora debe tener el formato HH:MM, por ejemplo 18:30."
    ),
    "falta_duracion": "⚠️ Debes indicar minutos o una hora de finalización.",
    "fuera_rango": (
        f"⚠️ La duración debe estar entre {BOX_MINUTOS_MINIMO} y "
        f"{BOX_MINUTOS_MAXIMO} minutos."
    ),
}

UNIDAD_RECOMPENSA = {
    "ENTRENANDO": "EXP",
    "TRABAJANDO": "$",
}


def formato_puntos_porcentuales(valor: float) -> str:
    """Muestra una tasa con precisión útil, sin ceros decimales sobrantes."""

    return f"{valor:.3f}".rstrip("0").rstrip(".")


def texto_recompensa(
    tipo: str,
    recompensa: float,
    dinero_recompensa: int,
) -> str:
    """Describe el resultado que recibió el usuario al terminar una acción."""

    if tipo == "DESCANSANDO":
        if recompensa <= 0:
            return "La probabilidad de lesión ya estaba en **0%**."

        puntos = formato_puntos_porcentuales(recompensa)
        return (
            "Redujo su probabilidad de lesión en "
            f"**{puntos} puntos porcentuales**."
        )

    if tipo == "TRABAJANDO":
        return f"**{dinero_recompensa} $**"

    if tipo == "PROMOVIENDO":
        return "🎯 búsqueda de sponsor"

    texto = f"**{recompensa} EXP**"
    if dinero_recompensa:
        texto += f" y recibió **{dinero_recompensa} $**"

    return texto


class AccionesMixin:
    """Acciones temporizadas y su liquidación periódica."""

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
        ) in await completar_acciones_vencidas(ahora()):
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
            embed = crear_embed(
                "✅ Acción finalizada",
                f"{usuario.mention} terminó de **{nombre_accion}**.",
                color_area="box",
            )
            seccion(
                embed,
                "🛌 Recuperación" if tipo == "DESCANSANDO" else "Recompensa",
                texto_recompensa(tipo, recompensa, dinero_recompensa),
            )
            if se_lesiona:
                seccion(
                    embed,
                    "🚑 Lesión",
                    "Se lastimó y estará lesionado durante "
                    f"{texto_horas(BOX_LESION_HORAS)}.",
                )
            await canal.send(embed=embed)

    @comprobar_acciones.before_loop
    async def esperar_bot(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def reducir_probabilidad_lesion(self):
        """Baja la probabilidad de lesión de los usuarios inactivos.

        Cada hora, los usuarios sin acción en curso (estén o no lesionados)
        reducen su probabilidad en 0.01 puntos porcentuales, sin pasar de 0.
        """

        cantidad = await reducir_probabilidad_lesion_inactivos()

        if cantidad:
            print(
                f"[BOX] probabilidad reducida a {cantidad} "
                "usuarios sin acción activa",
                flush=True,
            )

    @reducir_probabilidad_lesion.before_loop
    async def esperar_bot_probabilidad(self):
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
            embed = crear_embed(
                "🎉 ¡Sponsor conseguido!",
                f"{usuario.mention} terminó de **promocionarse** "
                "y consiguió un sponsor.",
                color_area="box",
            )
            seccion(embed, "Sponsor", f"**{nombre_sponsor}**")
            await canal.send(embed=embed)
            return

        embed = crear_embed(
            "📢 Promoción finalizada",
            f"{usuario.mention} terminó de **promocionarse**, "
            "pero no consiguió ningún sponsor esta vez.",
            color_area="box",
        )
        await canal.send(embed=embed)

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

        # Validar y registrar una acción requiere varias operaciones de base.
        # Se confirma primero para no perder la ventana de 3 segundos de
        # Discord si PostgreSQL está lento. También cubre descanso.
        if not interaction.response.is_done():
            await interaction.response.defer()

        _, lesionado_hasta = await obtener_estado_box(
            interaction.guild.id,
            interaction.user.id,
        )

        if (
            not permitir_lesionado
            and lesionado_hasta
            and lesionado_hasta > ahora()
        ):
            final = lesionado_hasta
            await responder_error(
                interaction,
                "🚑 Lesión activa",
                f"Estás lesionado hasta <t:{int(final.timestamp())}:R>.",
            )
            return

        iniciado_en = ahora()
        duracion, motivo = resolver_duracion(minutos, hasta, iniciado_en)
        if duracion is None:
            await responder_error(
                interaction,
                "⚠️ Duración inválida",
                MENSAJES_DURACION[motivo],
            )
            return

        accion = await obtener_accion_activa(
            interaction.guild.id,
            interaction.user.id,
        )
        if accion is not None:
            tipo_actual, finaliza_en, _ = accion
            timestamp = int(finaliza_en.timestamp())
            await responder_error(
                interaction,
                "⚠️ Acción activa",
                f"Ya estás **{tipo_actual.lower()}**. "
                f"Tu acción termina <t:{timestamp}:R>.",
            )
            return

        recompensa = duracion.minutos * recompensa_por_minuto

        if not await iniciar_accion(
            interaction.guild.id,
            interaction.user.id,
            tipo,
            iniciado_en,
            duracion.finaliza_en,
            recompensa,
        ):
            await responder_error(
                interaction,
                "⚠️ Acción activa",
                "Ya tienes otra acción activa.",
            )
            return

        finaliza = int(duracion.finaliza_en.timestamp())

        if tipo == "DESCANSANDO":
            reduccion = (
                duracion.minutos
                / 60
                * BOX_DESCANSO_REDUCCION_POR_HORA
            )
            await responder(
                interaction,
                "🛌 Comenzaste a descansar",
                color_area="box",
                secciones_=[
                    ("⏱️ Duración", f"**{duracion.minutos} minutos**"),
                    ("⏰ Finaliza", f"<t:{finaliza}:R>"),
                    (
                        "🩹 Recuperación al finalizar",
                        "Hasta **"
                        f"{formato_puntos_porcentuales(reduccion)} puntos "
                        "porcentuales** menos de probabilidad de lesión.",
                    ),
                ],
            )
            return

        if tipo == "PROMOVIENDO":
            await responder(
                interaction,
                "📢 Comenzaste a promocionarte",
                color_area="box",
                secciones_=[
                    ("⏱️ Duración", f"**{duracion.minutos} minutos**"),
                    ("⏰ Finaliza", f"<t:{finaliza}:R>"),
                    (
                        "🎯 Objetivo",
                        "Cuanto más tiempo te promociones, "
                        "mayores serán tus chances de conseguir "
                        "un sponsor.",
                    ),
                ],
            )
            return

        unidad = UNIDAD_RECOMPENSA.get(tipo, "EXP")
        await responder(
            interaction,
            f"✅ Comenzaste a {tipo.lower()}",
            color_area="box",
            secciones_=[
                ("🥊 Acción", f"**{tipo.lower()}**"),
                ("⏱️ Duración", f"**{duracion.minutos} minutos**"),
                ("⏰ Finaliza", f"<t:{finaliza}:R>"),
                ("🎁 Recompensa", f"**{recompensa} {unidad}**"),
            ],
        )

    @app_commands.command(
        name="entrenar",
        description="Entrena durante un tiempo para obtener experiencia.",
    )
    @app_commands.describe(
        minutos=f"Cantidad de minutos de entrenamiento ({BOX_MINUTOS_MINIMO}-{BOX_MINUTOS_MAXIMO}).",
        hasta="Hora a la que quieres terminar, formato HH:MM.",
    )
    async def entrenar(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        nivel = (
            await obtener_nivel_mejora(
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
            BOX_EXPERIENCIA_POR_MINUTO
            + nivel * BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL,
            hasta,
        )

    @app_commands.command(
        name="trabajar",
        description="Trabaja durante un tiempo para obtener dinero.",
    )
    @app_commands.describe(
        minutos=f"Cantidad de minutos de trabajo ({BOX_MINUTOS_MINIMO}-{BOX_MINUTOS_MAXIMO}).",
        hasta="Hora a la que quieres terminar, formato HH:MM.",
    )
    async def trabajar(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        nivel = (
            await obtener_nivel_mejora(
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
            BOX_DINERO_POR_MINUTO
            + nivel * BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL,
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
        minutos=f"Cantidad de minutos que quieres promocionarte ({BOX_MINUTOS_MINIMO}-{BOX_MINUTOS_MAXIMO}).",
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

    @app_commands.command(
        name="descanso",
        description="Descansa para reducir tu probabilidad de lesión.",
    )
    @app_commands.describe(
        minutos=(
            "Cantidad de minutos de descanso "
            f"({BOX_MINUTOS_MINIMO}-{BOX_MINUTOS_MAXIMO})."
        ),
        hasta="Hora a la que quieres terminar, formato HH:MM.",
    )
    async def descanso(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        """Inicia un descanso temporizado, incluso si el usuario está lesionado."""

        await self._comenzar_accion(
            interaction,
            minutos,
            "DESCANSANDO",
            0,
            hasta,
            permitir_lesionado=True,
        )
