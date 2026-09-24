"""Consulta y gestión del perfil de Box: saldo, stats, equipo, ranking y ayuda."""

import discord
from discord import app_commands

from commands.box.base import solo_servidor
from core.mensajes import crear_embed, responder, responder_error, responder_ok
from modules.box.services import (
    EQUIPAMIENTO,
    TEXTO_AYUDA,
    calidad_equipamiento,
    formato_ratio,
    obtener_accion_activa,
    obtener_equipo,
    obtener_estadisticas_box,
    obtener_saldo,
    obtener_top_desafios,
)


class InfoMixin:
    """Comandos de consulta del perfil y el ranking de Box."""

    @app_commands.command(
        name="ayuda",
        description="Envía por mensaje directo la ayuda de Box.",
    )
    async def ayuda(self, interaction: discord.Interaction):
        try:
            await interaction.user.send(
                embed=crear_embed(
                    "🥊 Ayuda de Box",
                    TEXTO_AYUDA,
                    color_area="box",
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
            "Te envié la ayuda de Box por mensaje directo.",
        )

    @app_commands.command(
        name="saldo",
        description="Muestra tu experiencia y dinero de Box.",
    )
    async def saldo(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        experiencia, dinero = await obtener_saldo(
            interaction.guild.id,
            interaction.user.id,
        )
        await responder(
            interaction,
            f"📊 Saldo de {interaction.user.display_name}",
            color_area="box",
            secciones_=[
                ("⭐ Experiencia", f"**{experiencia}**"),
                ("💰 Dinero", f"**{dinero}$**"),
            ],
        )

    @app_commands.command(
        name="stats",
        description="Muestra tus estadísticas privadas de Box.",
    )
    async def stats(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        estadisticas = await obtener_estadisticas_box(
            interaction.guild.id,
            interaction.user.id,
        )
        accion = await obtener_accion_activa(
            interaction.guild.id,
            interaction.user.id,
        )

        accion_texto = "Ninguna"
        if accion is not None:
            final = int(accion[1].timestamp())
            accion_texto = f"{accion[0].lower()} hasta <t:{final}:R>"

        await responder(
            interaction,
            f"📊 Stats de {interaction.user.display_name}",
            color_area="box",
            ephemeral=True,
            secciones_=[
                (
                    "Economía",
                    f"⭐ **{estadisticas['experiencia']} EXP**\n"
                    f"💰 **{estadisticas['dinero']}$**",
                    True,
                ),
                (
                    "Desafíos",
                    f"🥊 **{estadisticas['ganadas']}/"
                    f"{estadisticas['perdidas']}**\n"
                    f"Ratio: **"
                    f"{formato_ratio(estadisticas['ratio'])}**",
                    True,
                ),
                (
                    "Mejoras",
                    f"📈 Creatina: **"
                    f"{estadisticas['nivel_entrenamiento']}**\n"
                    f"☕ Cafe: **"
                    f"{estadisticas['nivel_trabajo']}**",
                    True,
                ),
                (
                    "Lesión",
                    f"🩹 **"
                    f"{estadisticas['probabilidad_lesion']:.2f}%**",
                    True,
                ),
                ("⏳ Acción actual", f"**{accion_texto}**", False),
            ],
        )

    @app_commands.command(
        name="equipo",
        description="Muestra tu equipo y estadísticas de combate.",
    )
    async def equipo(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        equipo_datos = await obtener_equipo(
            interaction.guild.id,
            interaction.user.id,
        )

        if equipo_datos is None:
            await responder_error(
                interaction,
                "⚠️ Error",
                "No se pudo obtener el equipo.",
            )
            return

        equipamiento = "\n".join(
            f"{pieza['emoji']} **{pieza['nombre']}:** "
            f"{calidad_equipamiento(clave, equipo_datos[clave])}"
            for clave, pieza in EQUIPAMIENTO.items()
        )

        await responder(
            interaction,
            f"🥊 Equipo de {interaction.user.display_name}",
            color_area="box",
            secciones_=[
                (
                    "Combate",
                    f"❤️ Vida: **{equipo_datos['vida']}/"
                    f"{equipo_datos['vida_maxima']}**\n"
                    f"💥 Daño: **{equipo_datos['dano']}/"
                    f"{equipo_datos['dano_maximo']}**\n"
                    f"🛡️ Defensa: **{equipo_datos['defensa']}/"
                    f"{equipo_datos['defensa_maxima']}**\n"
                    f"😴 Cansancio: **{equipo_datos['cansancio']}/"
                    f"{equipo_datos['cansancio_maximo']}**",
                ),
                (
                    "Habilidad",
                    f"⭐ Puntos Habilidad: **"
                    f"{equipo_datos['puntos_habilidad']}**",
                    True,
                ),
                ("Equipamiento", equipamiento, False),
            ],
        )

    @app_commands.command(
        name="topdesafios",
        description="Muestra el ranking histórico de desafíos.",
    )
    async def topdesafios(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        ranking = await obtener_top_desafios(interaction.guild.id)
        if not ranking:
            await responder(
                interaction,
                "🏆 Desafíos",
                "Todavía no hay desafíos finalizados.",
                color_area="box",
            )
            return

        lineas = []
        for posicion, (user_id, ganadas, perdidas, ratio) in enumerate(
            ranking,
            start=1,
        ):
            usuario = interaction.guild.get_member(user_id)
            nombre = usuario.display_name if usuario else f"Usuario {user_id}"
            lineas.append(
                f"{posicion}) **{nombre}** {ganadas}/{perdidas} "
                f"ratio: **{formato_ratio(ratio)}**"
            )

        await responder(
            interaction,
            "🏆 Top desafíos",
            color_area="box",
            secciones_=[
                ("Ranking", "\n".join(lineas), False),
            ],
        )
