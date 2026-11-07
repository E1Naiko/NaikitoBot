"""Administración de sanciones por trampa: aplicar, levantar y consultar.

El minijuego es la unidad de la sanción: quien hizo trampa en Box puede
seguir jugando Madrugue. Cada sanción tiene su propio temporizador y, salvo
que se indique lo contrario, no vence por sí sola: solo un administrador la
levanta.
"""

from datetime import timedelta

import discord
from discord import app_commands

from commands.admin.base import solo_admin, solo_servidor
from core.mensajes import responder, responder_texto
from core.utils import ahora
from modules.sanciones.logic import (
    MINIJUEGOS,
    nombre_minijuego,
    texto_vencimiento,
)
from modules.sanciones.services import (
    aplicar_sancion,
    formatear_restante,
    levantar_sancion,
    limpiar_vencidas,
    listar_sanciones,
    parsear_duracion,
)

# Un listado con demasiadas filas deja de ser legible en un embed.
MAXIMO_LISTADO = 20

OPCIONES_MINIJUEGO = [
    app_commands.Choice(name=nombre, value=clave)
    for clave, nombre in MINIJUEGOS.items()
]


async def _cancelar_accion_de_box(guild_id, user_id):
    """Corta la acción que el sancionado tenía en marcha en Box.

    Una acción (entrenar, trabajar…) cobra la recompensa al terminar. Si el
    ban es por trampa, dejarla corriendo premiaría justo lo que se está
    castigando. Se importa dentro de la función para que este módulo no
    dependa de Box al cargarse y para no tocar Box si la sanción es de otro
    minijuego.
    """

    from modules.box.services import admin_cancelar_accion

    accion = await admin_cancelar_accion(guild_id, user_id)

    return accion is not None


class SancionAdminMixin:
    """Comandos administrativos de sanciones bajo ``/admin sanciones``."""

    sanciones = app_commands.Group(
        name="sanciones",
        description="Bloquea por trampa a un usuario en un minijuego.",
    )

    # ========================================================
    # APLICAR
    # ========================================================

    @sanciones.command(
        name="aplicar",
        description="Sanciona a un usuario por trampa en un minijuego.",
    )
    @app_commands.describe(
        usuario="Usuario que hizo trampa.",
        minijuego="Minijuego en el que no podrá participar.",
        motivo="Qué hizo; queda guardado en la sanción.",
        duracion="Temporizador: 30m, 12h, 7d, 2d12h o permanente (por defecto).",
    )
    @app_commands.choices(minijuego=OPCIONES_MINIJUEGO)
    async def sanciones_aplicar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        minijuego: app_commands.Choice[str],
        motivo: str,
        duracion: str = "permanente",
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            delta = parsear_duracion(duracion)
        except ValueError as error:
            await responder_texto(interaction, str(error), ephemeral=True)
            return

        motivo = motivo.strip()

        if not motivo:
            await responder_texto(
                interaction,
                "⚠️ El motivo no puede estar vacío: es lo que queda guardado "
                "para justificar la sanción.",
                ephemeral=True,
            )
            return

        momento = ahora()
        sancion = await aplicar_sancion(
            interaction.guild.id,
            usuario.id,
            minijuego.value,
            motivo,
            duracion=delta,
            creada_por=interaction.user.id,
            momento=momento,
        )

        expiracion = sancion["expira_en"]
        accion_cancelada = (
            await _cancelar_accion_de_box(interaction.guild.id, usuario.id)
            if minijuego.value == "box"
            else False
        )

        secciones = [
            ("⛔ Minijuego", f"**{nombre_minijuego(minijuego.value)}**"),
            ("📝 Motivo", motivo),
            ("⏱️ Duración", _texto_duracion(delta)),
            ("📅 Termina", texto_vencimiento(expiracion)),
        ]

        if expiracion is not None:
            secciones.append((
                "⌛ Falta",
                f"**{formatear_restante(expiracion, momento)}**",
            ))

        if accion_cancelada:
            secciones.append((
                "🛑 Acción de Box",
                "Se le canceló la acción que tenía en marcha: si no, cobraba "
                "la recompensa al terminar.",
            ))

        secciones.append((
            "🔓 Para revertirla",
            f"`/admin sanciones levantar usuario:{usuario.display_name} "
            f"minijuego:{minijuego.value}`",
        ))

        await responder(
            interaction,
            f"⛔ Sanción aplicada a {usuario.display_name}",
            color_area="error",
            secciones_=secciones,
        )

    # ========================================================
    # LEVANTAR
    # ========================================================

    @sanciones.command(
        name="levantar",
        description="Levanta la sanción de un usuario en un minijuego.",
    )
    @app_commands.describe(
        usuario="Usuario al que se le retira la sanción.",
        minijuego="Minijuego del que se lo desbloquea.",
    )
    @app_commands.choices(minijuego=OPCIONES_MINIJUEGO)
    async def sanciones_levantar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        minijuego: app_commands.Choice[str],
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        levantada = await levantar_sancion(
            interaction.guild.id,
            usuario.id,
            minijuego.value,
            levantada_por=interaction.user.id,
            momento=ahora(),
        )

        if not levantada:
            await responder_texto(
                interaction,
                f"ℹ️ **{usuario.display_name}** no tiene una sanción vigente "
                f"en **{nombre_minijuego(minijuego.value)}**.",
                ephemeral=True,
            )
            return

        await responder(
            interaction,
            "🔓 Sanción levantada",
            f"**{usuario.display_name}** puede volver a participar en "
            f"**{nombre_minijuego(minijuego.value)}**.",
            color_area="ok",
            secciones_=[
                ("👮 Levantada por", interaction.user.mention),
            ],
        )

    # ========================================================
    # VER
    # ========================================================

    @sanciones.command(
        name="ver",
        description="Lista las sanciones vigentes de un usuario o del servidor.",
    )
    @app_commands.describe(
        usuario="Usuario a consultar. Si se omite, se listan todas.",
        historicas="Incluir las levantadas y las vencidas.",
    )
    async def sanciones_ver(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member | None = None,
        historicas: bool = False,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        momento = ahora()
        sanciones = await listar_sanciones(
            interaction.guild.id,
            incluir_historicas=historicas,
            momento=momento,
        )

        if usuario is not None:
            sanciones = [
                sancion
                for sancion in sanciones
                if sancion["user_id"] == usuario.id
            ]

        if not sanciones:
            detalle = (
                f"**{usuario.display_name}** no tiene sanciones "
                if usuario is not None
                else "El servidor no tiene sanciones "
            )
            detalle += "registradas." if historicas else "vigentes."
            await responder_texto(interaction, f"✅ {detalle}", ephemeral=True)
            return

        if usuario is not None:
            # Con un usuario puntual alcanza con el temporizador de cada
            # minijuego: es lo que necesita saber para saber cuándo vuelve.
            lineas = []
            for sancion in sanciones:
                lineas.append(
                    f"· **{nombre_minijuego(sancion['minijuego'])}** · "
                    f"{_texto_estado(sancion, momento)}\n"
                    f"   {sancion['motivo']}"
                )
            descripcion = "\n".join(lineas)
            titulo = f"⛔ Sanciones de {usuario.display_name}"
        else:
            lineas = [
                f"· <@{sancion['user_id']}> en "
                f"**{nombre_minijuego(sancion['minijuego'])}** · "
                f"{_texto_estado(sancion, momento)}"
                for sancion in sanciones[:MAXIMO_LISTADO]
            ]
            descripcion = "\n".join(lineas)

            if len(sanciones) > MAXIMO_LISTADO:
                descripcion += (
                    f"\n\n… y **{len(sanciones) - MAXIMO_LISTADO}** más."
                )

            titulo = "⛔ Sanciones del servidor"

        await responder(
            interaction,
            titulo,
            descripcion[:4000],
            color_area="error",
            pie="Las sanciones vencidas no bloquean; se conservan como historial.",
            ephemeral=True,
        )

    # ========================================================
    # LIMPIAR
    # ========================================================

    @sanciones.command(
        name="limpiar",
        description="Borra las sanciones que ya vencieron.",
    )
    async def sanciones_limpiar(self, interaction: discord.Interaction):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        borradas = await limpiar_vencidas(interaction.guild.id)

        await responder_texto(
            interaction,
            f"🧹 Se borraron **{borradas}** sanciones vencidas."
            if borradas
            else "ℹ️ No había sanciones vencidas para borrar.",
            ephemeral=True,
        )


# ============================================================
# TEXTOS
# ============================================================

def _texto_duracion(delta: timedelta | None):
    """Convierte la duración elegida en "2 días 12 h" o "permanente"."""

    if delta is None:
        return "permanente (sin vencimiento)"

    segundos = int(delta.total_seconds())
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)

    partes = []
    if dias:
        partes.append(f"{dias} día{'s' if dias != 1 else ''}")
    if horas:
        partes.append(f"{horas} h")
    if minutos and not dias:
        partes.append(f"{minutos} min")

    return " ".join(partes) or f"{segundos} s"


def _texto_estado(sancion, momento):
    """Estado y temporizador de una fila de ``sanciones``."""

    if sancion["levantada_en"] is not None:
        return "levantada"

    expiracion = sancion["expira_en"]

    if not sancion["vigente"]:
        return f"vencida {texto_vencimiento(expiracion)}"

    if expiracion is None:
        return "permanente"

    return (
        f"faltan {formatear_restante(expiracion, momento)} "
        f"({texto_vencimiento(expiracion)})"
    )
