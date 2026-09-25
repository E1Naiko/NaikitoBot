"""Consultas de laHora: estadísticas, ranking, registros del día y ayuda."""

import discord
from discord import app_commands

import config
from commands.lahora.base import medalla, solo_servidor
from core.mensajes import responder
from core.utils import ahora
from modules.lahora.services import (
    obtener_hoy_lahora,
    obtener_stats_lahora,
    obtener_top_lahora,
    texto_ventanas,
)

COLOR = "lahora"


def _texto_dias(cantidad: int) -> str:
    return f"{cantidad} día" if cantidad == 1 else f"{cantidad} días"


class InfoMixin:
    """Comandos de consulta del canal 420."""

    @app_commands.command(
        name="420_stats",
        description="Muestra tus estadísticas del canal 420 (o las de otro usuario).",
    )
    @app_commands.describe(usuario="Usuario a consultar (por defecto, vos).")
    async def stats(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member | None = None,
    ):
        """Muestra las estadísticas de laHora de un usuario."""

        if not await solo_servidor(interaction):
            return

        objetivo = usuario or interaction.user

        stats = await obtener_stats_lahora(
            guild_id=interaction.guild.id,
            user_id=objetivo.id,
            hoy=ahora().date(),
        )

        if stats["cantidad"] == 0:
            await responder(
                interaction,
                f"🌿 Estadísticas de {objetivo.display_name}",
                "Todavía no tiene ningún 420 registrado.",
                color_area=COLOR,
            )
            return

        mejor_tiempo = (
            f"**{stats['mejor_segundos']} s**"
            if stats["mejor_segundos"] is not None
            else "—"
        )

        await responder(
            interaction,
            f"🌿 Estadísticas de {objetivo.display_name}",
            color_area=COLOR,
            secciones_=[
                ("🏆 Puntos acumulados", f"**{stats['total_puntos']:.1f}**", True),
                ("🌿 420 registrados", f"**{stats['cantidad']}**", True),
                ("🥇 Veces primero", f"**{stats['veces_primero']}**", True),
                ("🔥 Racha actual", f"**{_texto_dias(stats['racha_actual'])}**", True),
                ("📈 Mejor racha", f"**{_texto_dias(stats['mejor_racha'])}**", True),
                ("⚡ Mejor tiempo", mejor_tiempo, True),
            ],
        )

    @app_commands.command(
        name="420_top",
        description="Muestra el TOP del canal 420 del servidor.",
    )
    async def top(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el ranking histórico de laHora."""

        if not await solo_servidor(interaction):
            return

        resultados = await obtener_top_lahora(
            interaction.guild.id,
            limite=10,
        )

        if not resultados:
            await responder(
                interaction,
                "🏆 TOP 420",
                "Todavía nadie dijo 420 a tiempo.",
                color_area=COLOR,
            )
            return

        lineas = [
            f"{medalla(posicion)} **{username}** — "
            f"**{puntos:.0f} puntos** · {cantidad} × 420"
            for posicion, (_, username, puntos, cantidad) in enumerate(
                resultados,
                start=1,
            )
        ]

        await responder(
            interaction,
            "🏆 TOP 420",
            "Ranking histórico del servidor.",
            color_area=COLOR,
            pie=f"Servidor: {interaction.guild.name}",
            secciones_=[("Ranking", "\n".join(lineas))],
        )

    @app_commands.command(
        name="420_hoy",
        description="Muestra quiénes dijeron 420 hoy y en qué orden.",
    )
    async def hoy(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra los registros del día por ventana."""

        if not await solo_servidor(interaction):
            return

        fecha = ahora().date()
        por_ventana = await obtener_hoy_lahora(interaction.guild.id, fecha)

        if not por_ventana:
            await responder(
                interaction,
                "🌿 420 de hoy",
                "Hoy todavía nadie dijo 420 a tiempo.",
                color_area=COLOR,
                secciones_=[("⏰ Horarios", texto_ventanas())],
            )
            return

        secciones_ = []

        for ventana in sorted(por_ventana):
            lineas = [
                f"{medalla(posicion)} **{username}** — "
                f"{segundos} s · **{puntos:.1f} pts**"
                for posicion, username, segundos, puntos in por_ventana[ventana]
            ]
            secciones_.append((f"🕓 {ventana}", "\n".join(lineas)[:1024]))

        await responder(
            interaction,
            "🌿 420 de hoy",
            f"Registros del {fecha.strftime('%d/%m/%Y')}.",
            color_area=COLOR,
            secciones_=secciones_,
        )

    @app_commands.command(
        name="420_ayuda",
        description="Explica cómo funciona el canal 420.",
    )
    async def ayuda(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra la ayuda del sistema laHora."""

        canales = ", ".join(
            f"<#{canal_id}>" for canal_id in sorted(config.LAHORA_CANALES_ID)
        ) or "el canal 420"

        await responder(
            interaction,
            "🌿 Ayuda del canal 420",
            (
                f"Escribí **420** en {canales} justo a la hora y sumá "
                "puntos. No hace falta ningún comando: si cuenta, el bot "
                "reacciona con 🌿 (y con 🥇 si fuiste el primero)."
            ),
            color_area=COLOR,
            pie=(
                f"Servidor: {interaction.guild.name}"
                if interaction.guild
                else "Canal 420"
            ),
            secciones_=[
                ("⏰ Horarios válidos", texto_ventanas()),
                (
                    "💰 Puntos",
                    (
                        f"Base: **{config.LAHORA_PUNTOS_BASE}** puntos.\n"
                        f"⚡ Velocidad: hasta **×{1 + config.LAHORA_BONUS_VELOCIDAD:g}** "
                        "si lo decís apenas abre la ventana; baja con cada segundo.\n"
                        f"🥇 El primero de cada ventana suma **+{config.LAHORA_BONUS_PRIMERO}**."
                    ),
                ),
                (
                    "✍️ Qué cuenta",
                    "`420`, `4:20`, `04:20`, `16:20`, `420!!`, `420 🌿`… "
                    "Un 420 por persona en cada ventana.",
                ),
                (
                    "📋 Comandos",
                    (
                        "`/420_stats` — tus puntos, rachas y mejor tiempo.\n"
                        "`/420_top` — ranking histórico del servidor.\n"
                        "`/420_hoy` — quiénes lo dijeron hoy y en qué orden."
                    ),
                ),
            ],
        )
