"""Consulta y gestión del perfil de Box: saldo, stats, equipo, ranking y ayuda."""

from datetime import datetime

import discord
from discord import app_commands

from commands.box.base import solo_servidor
from modules.box.services import (
    EQUIPAMIENTO,
    TEXTO_AYUDA,
    calidad_equipamiento,
    descansar,
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
            "✅ Te envié la ayuda de Box por mensaje directo.",
            ephemeral=True,
        )

    @app_commands.command(
        name="saldo",
        description="Muestra tu experiencia y dinero de Box.",
    )
    async def saldo(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        experiencia, dinero = obtener_saldo(
            interaction.guild.id,
            interaction.user.id,
        )
        await interaction.response.send_message(
            f"📊 **Saldo de {interaction.user.display_name}**\n"
            f"⭐ Experiencia: **{experiencia}**\n"
            f"💰 Dinero: **{dinero}**"
        )

    @app_commands.command(
        name="stats",
        description="Muestra tus estadísticas privadas de Box.",
    )
    async def stats(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        estadisticas = obtener_estadisticas_box(
            interaction.guild.id,
            interaction.user.id,
        )
        accion = obtener_accion_activa(
            interaction.guild.id,
            interaction.user.id,
        )

        accion_texto = "Ninguna"
        if accion is not None:
            final = int(datetime.fromisoformat(accion[1]).timestamp())
            accion_texto = f"{accion[0].lower()} hasta <t:{final}:R>"

        await interaction.response.send_message(
            f"📊 **Stats de {interaction.user.display_name}**\n"
            f"⭐ Experiencia: **{estadisticas['experiencia']}**\n"
            f"💰 Dinero: **{estadisticas['dinero']}**\n"
            f"🥊 Desafíos: **{estadisticas['ganadas']}/"
            f"{estadisticas['perdidas']}** ratio: "
            f"**{formato_ratio(estadisticas['ratio'])}**\n"
            f"📈 Creatina: nivel **{estadisticas['nivel_entrenamiento']}**\n"
            f"☕ Cafe: nivel **{estadisticas['nivel_trabajo']}**\n"
            f"🩹 Probabilidad de lesión: "
            f"**{estadisticas['probabilidad_lesion']:.2f}%**\n"
            f"⏳ Acción actual: **{accion_texto}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="equipo",
        description="Muestra tu equipo y estadísticas de combate.",
    )
    async def equipo(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        equipo_datos = obtener_equipo(
            interaction.guild.id,
            interaction.user.id,
        )

        if equipo_datos is None:
            await interaction.response.send_message(
                "⚠️ Error al obtener el equipo.",
                ephemeral=True,
            )
            return

        equipamiento = "\n".join(
            f"{pieza['emoji']} **{pieza['nombre']}:** "
            f"{calidad_equipamiento(clave, equipo_datos[clave])}"
            for clave, pieza in EQUIPAMIENTO.items()
        )

        await interaction.response.send_message(
            f"🥊 **Equipo de {interaction.user.display_name}**\n\n"
            f"**Combate**\n"
            f"❤️ **Vida:** {equipo_datos['vida']}/"
            f"{equipo_datos['vida_maxima']}\n"
            f"💥 **Daño:** {equipo_datos['dano']}/"
            f"{equipo_datos['dano_maximo']}\n"
            f"🛡️ **Defensa:** {equipo_datos['defensa']}/"
            f"{equipo_datos['defensa_maxima']}\n"
            f"😴 **Cansancio:** {equipo_datos['cansancio']}/"
            f"{equipo_datos['cansancio_maximo']}\n\n"
            f"**Habilidad**\n"
            f"⭐ **Puntos Habilidad:** {equipo_datos['puntos_habilidad']}\n\n"
            f"**Equipamiento**\n"
            f"{equipamiento}"
        )

    @app_commands.command(
        name="descanso",
        description="Reinicia tu probabilidad de lesión a cero.",
    )
    async def descanso(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        if obtener_accion_activa(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message(
                "⚠️ No puedes descansar mientras realizas una acción.",
                ephemeral=True,
            )
            return

        # Descansar está permitido incluso estando lesionado.
        descansar(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            "🛌 Tu probabilidad de lesión volvió a **0%**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="topdesafios",
        description="Muestra el ranking histórico de desafíos.",
    )
    async def topdesafios(self, interaction: discord.Interaction):
        if not await solo_servidor(interaction):
            return

        ranking = obtener_top_desafios(interaction.guild.id)
        if not ranking:
            await interaction.response.send_message(
                "🏆 Todavía no hay desafíos finalizados."
            )
            return

        lineas = ["🏆 **TOP DE DESAFÍOS**"]
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

        await interaction.response.send_message("\n".join(lineas))
