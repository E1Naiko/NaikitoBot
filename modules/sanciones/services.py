"""Fachada de sanciones: lo único que importan los módulos de cada minijuego.

Los minijuegos no tocan ``database`` ni ``logic`` directamente, igual que en
Madrugue, laHora, SSF y Box. El punto de entrada habitual es
:func:`revisar_sancion`, que responde al usuario con un aviso efímero y
devuelve ``True`` cuando puede seguir jugando.
"""

from core.mensajes import responder
from core.permissions import es_admin
from modules.sanciones.database import (
    eliminar_sancion,
    guardar_sancion,
    levantar_sancion,
    limpiar_vencidas,
    listar_sanciones,
    obtener_sancion,
    sancion_vigente,
    sanciones_vigentes,
    usuarios_vigentes,
)
from modules.sanciones.logic import (
    ESTADO_ACTIVA,
    ESTADO_LEVANTADA,
    ESTADO_VENCIDA,
    MINIJUEGOS,
    calcular_expiracion,
    estado_sancion,
    formatear_restante,
    nombre_minijuego,
    ahora_local,
    parsear_duracion,
    texto_sancion_activa,
    texto_vencimiento,
)

__all__ = [
    "ESTADO_ACTIVA",
    "ESTADO_LEVANTADA",
    "ESTADO_VENCIDA",
    "MINIJUEGOS",
    "calcular_expiracion",
    "eliminar_sancion",
    "esta_sancionado",
    "formatear_restante",
    "guardar_sancion",
    "levantar_sancion",
    "limpiar_vencidas",
    "listar_sanciones",
    "nombre_minijuego",
    "obtener_sancion",
    "parsear_duracion",
    "revisar_sancion",
    "sancion_vigente",
    "sanciones_vigentes",
    "texto_sancion_activa",
    "texto_vencimiento",
    "usuarios_vigentes",
]

TITULO_SANCION = "⛔ Sanción por trampa"


def _momento(momento):
    """Normaliza el momento de consulta; ``None`` usa la hora del bot."""

    return momento if momento is not None else ahora_local()


async def esta_sancionado(guild_id, user_id, minijuego, momento=None):
    """``True`` si el usuario no puede participar en ese minijuego ahora."""

    if guild_id is None or user_id is None:
        return False

    return await sancion_vigente(guild_id, user_id, minijuego, _momento(momento)) is not None


async def revisar_sancion(interaction, minijuego, momento=None, exento=None):
    """Guardián de los comandos y botones de cada minijuego.

    Devuelve ``True`` si el usuario puede jugar. Si está sancionado responde
    un aviso efímero con el temporizador restante y devuelve ``False``.

    Los administradores quedan exentos: son quienes levantan una sanción
    equivocada y no pueden quedar encerrados fuera de su propio bot. Si se
    quiere sancionar a un administrador hace falta sacarlo de
    ``ADMIN_USER_IDS``.

    Uso::

        if not await revisar_sancion(interaction, "madrugue"):
            return
    """

    if exento is None:
        exento = es_admin(interaction.user.id)

    if exento:
        return True

    guild = getattr(interaction, "guild", None)

    if guild is None:
        # Los comandos que llegan acá ya validaron el servidor; si no hay
        # servidor no hay a quién comparar contra ``sanciones``.
        return True

    sancion = await sancion_vigente(
        guild.id,
        interaction.user.id,
        minijuego,
        _momento(momento),
    )

    if sancion is None:
        return True

    _, expiracion = sancion

    await responder(
        interaction,
        TITULO_SANCION,
        texto_sancion_activa(minijuego, expiracion, momento),
        color_area="error",
        ephemeral=True,
    )

    return False


async def aplicar_sancion(
    guild_id,
    user_id,
    minijuego,
    motivo,
    duracion=None,
    creada_por=None,
    momento=None,
):
    """Registra (o reemplaza) la sanción de un usuario en un minijuego.

    ``duracion`` es un ``timedelta`` o ``None`` para permanente; el comando
    puede usar :func:`parsear_duracion` para convertir el texto del admin.
    """

    momento = _momento(momento)
    expiracion = calcular_expiracion(momento, duracion)

    return await guardar_sancion(
        guild_id,
        user_id,
        minijuego,
        motivo,
        expira_en=expiracion,
        creada_en=momento,
        creada_por=creada_por,
    )


def resumen_para_texto(sancion, momento=None):
    """Línea legible de una sanción, con su temporizador."""

    if sancion is None:
        return ""

    nombre = nombre_minijuego(sancion["minijuego"])
    estado = sancion.get("estado")

    if estado == ESTADO_LEVANTADA:
        detalle = "levantada por un administrador"
    elif estado == ESTADO_VENCIDA:
        detalle = f"vencida el {texto_vencimiento(sancion['expira_en'])}"
    elif sancion["expira_en"] is None:
        detalle = "permanente"
    else:
        detalle = (
            f"faltan {formatear_restante(sancion['expira_en'], momento)} "
            f"({texto_vencimiento(sancion['expira_en'])})"
        )

    return f"{nombre} · {detalle}"


def segundos_restantes(expiracion, momento=None):
    """Segundos que faltan para el vencimiento; ``None`` si es permanente."""

    if expiracion is None:
        return None

    restante = expiracion - _momento(momento)

    return max(0, int(restante.total_seconds()))


def texto_duracion(duracion):
    """Describe la duración elegida por el admin en el aviso de alta."""

    if duracion is None:
        return "permanente (sin vencimiento)"

    return formatear_restante(ahora_local() + duracion)


def estado_legible(sancion):
    """Nombre del estado de una sanción para los listados."""

    return estado_sancion(sancion.get("expira_en"), sancion.get("levantada_en"))

