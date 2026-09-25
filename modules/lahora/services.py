"""Fachada del módulo laHora.

Los cogs importan desde acá y no directamente de ``database`` ni
``logic``, igual que en Madrugue, Box y SSF.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from config import TIMEZONE
from modules.lahora.database import (
    contar_registros_ventana,
    eliminar_registros,
    eliminar_registros_servidor,
    eliminar_registros_usuario,
    guardar_registro,
    obtener_detalle_registro,
    obtener_estadisticas_servidor,
    obtener_fechas_registradas,
    obtener_registro,
    obtener_registros_del_dia,
    obtener_registros_usuario,
    obtener_resumen_usuario,
    obtener_top,
    obtener_ventanas_usuario,
    recalcular_ventana,
)
from modules.lahora.logic import (
    calcular_mejor_racha,
    calcular_puntos,
    calcular_racha_actual,
    es_mensaje_420,
    formatear_ventana,
    segundos_desde_apertura,
    texto_ventanas,
    ventana_activa,
)

__all__ = [
    "ResultadoLaHora",
    "ResumenImportacion",
    "agregar_manual",
    "borrar_dia",
    "borrar_servidor",
    "borrar_usuario",
    "es_mensaje_420",
    "importar_mensajes",
    "obtener_estadisticas_servidor",
    "obtener_registros_usuario",
    "obtener_hoy_lahora",
    "obtener_stats_lahora",
    "obtener_top_lahora",
    "registrar_lahora",
    "texto_ventanas",
]


# Los mensajes se procesan concurrentemente: el candado evita que dos
# "420" casi simultáneos calculen la misma posición en la ventana.
_candado_registro = asyncio.Lock()


@dataclass
class ResultadoLaHora:
    """Resultado de un intento de registro."""

    exitoso: bool
    motivo: str
    momento: datetime
    ventana: str | None = None
    segundos: int = 0
    posicion: int = 0
    puntos_base: int = 0
    multiplicador: float = 1.0
    bonus_posicion: int = 0
    puntos_finales: float = 0.0


def _a_hora_local(momento):
    """Pasa el momento a la zona horaria del bot.

    ``message.created_at`` llega en UTC: sin esta conversión un 420 de
    las 16:20 en Argentina se leería como 19:20.
    """

    if momento.tzinfo is None:
        return momento.replace(tzinfo=TIMEZONE)

    return momento.astimezone(TIMEZONE)


async def registrar_lahora(
    guild_id,
    user_id,
    username,
    momento,
    mensaje_id=None,
):
    """Registra un 420 dicho en ``momento``.

    No depende de Discord. Motivos posibles del resultado:
    ``fuera_de_horario``, ``ya_registrado`` y ``registrado``.
    """

    momento = _a_hora_local(momento)
    fecha = momento.date()
    ventana = ventana_activa(momento.time())

    if ventana is None:
        return ResultadoLaHora(
            exitoso=False,
            motivo="fuera_de_horario",
            momento=momento,
        )

    texto_ventana = formatear_ventana(ventana)

    async with _candado_registro:

        if await obtener_registro(guild_id, user_id, fecha, texto_ventana):
            return ResultadoLaHora(
                exitoso=False,
                motivo="ya_registrado",
                momento=momento,
                ventana=texto_ventana,
            )

        segundos = segundos_desde_apertura(momento.time(), ventana)
        posicion = await contar_registros_ventana(
            guild_id,
            fecha,
            texto_ventana,
        ) + 1

        puntos_base, multiplicador, bonus, finales = calcular_puntos(
            segundos,
            posicion,
        )

        guardado = await guardar_registro(
            guild_id=guild_id,
            user_id=user_id,
            username=username,
            fecha=fecha,
            ventana=texto_ventana,
            momento=momento,
            segundos=segundos,
            posicion=posicion,
            puntos_base=puntos_base,
            multiplicador=multiplicador,
            bonus_posicion=bonus,
            puntos_finales=finales,
            mensaje_id=mensaje_id,
        )

    if not guardado:
        return ResultadoLaHora(
            exitoso=False,
            motivo="ya_registrado",
            momento=momento,
            ventana=texto_ventana,
        )

    return ResultadoLaHora(
        exitoso=True,
        motivo="registrado",
        momento=momento,
        ventana=texto_ventana,
        segundos=segundos,
        posicion=posicion,
        puntos_base=puntos_base,
        multiplicador=multiplicador,
        bonus_posicion=bonus,
        puntos_finales=finales,
    )


async def obtener_stats_lahora(
    guild_id,
    user_id,
    hoy,
):
    """Estadísticas de un usuario en el canal 420."""

    total, cantidad, veces_primero, mejor_segundos = await obtener_resumen_usuario(
        guild_id,
        user_id,
    )
    fechas = await obtener_fechas_registradas(guild_id, user_id)

    return {
        "total_puntos": float(total or 0),
        "cantidad": int(cantidad or 0),
        "veces_primero": int(veces_primero or 0),
        "mejor_segundos": mejor_segundos,
        "racha_actual": calcular_racha_actual(fechas, hoy),
        "mejor_racha": calcular_mejor_racha(fechas),
    }


async def obtener_top_lahora(
    guild_id,
    limite=10,
):
    """TOP histórico del servidor."""

    return await obtener_top(guild_id, limite)


async def obtener_hoy_lahora(
    guild_id,
    fecha,
):
    """Registros del día agrupados por ventana, en orden de llegada."""

    por_ventana = {}

    for ventana, posicion, username, segundos, puntos in await obtener_registros_del_dia(
        guild_id,
        fecha,
    ):
        por_ventana.setdefault(ventana, []).append(
            (posicion, username, segundos, puntos)
        )

    return por_ventana


# ============================================================
# ADMINISTRACIÓN
# ============================================================

async def _recalcular(guild_id, ventanas):
    """Recalcula posiciones y puntos de cada ``(fecha, ventana)``."""

    for fecha, ventana in sorted(set(ventanas)):
        await recalcular_ventana(guild_id, fecha, ventana, calcular_puntos)


async def agregar_manual(
    guild_id,
    user_id,
    username,
    momento,
):
    """Registra a mano un 420 dicho en ``momento`` (hora local o con zona).

    Sigue las mismas reglas que el registro automático (ventana válida y
    uno por ventana) y después reordena la ventana: si el 420 agregado es
    anterior a otros, les corre la posición y el bonus del primero.
    Devuelve un :class:`ResultadoLaHora` con la posición y los puntos ya
    recalculados.
    """

    resultado = await registrar_lahora(guild_id, user_id, username, momento)

    if not resultado.exitoso:
        return resultado

    fecha = resultado.momento.date()
    await _recalcular(guild_id, [(fecha, resultado.ventana)])

    segundos, posicion, puntos = await obtener_detalle_registro(
        guild_id,
        user_id,
        fecha,
        resultado.ventana,
    )
    resultado.posicion = posicion
    resultado.bonus_posicion = calcular_puntos(segundos, posicion)[2]
    resultado.puntos_finales = puntos

    return resultado


async def borrar_dia(
    guild_id,
    user_id,
    fecha,
    ventana=None,
):
    """Borra los 420 de un usuario en una fecha (o una sola ventana).

    Devuelve cuántos borró y reordena las ventanas afectadas.
    """

    afectadas = [
        (dia, vent)
        for dia, vent in await obtener_ventanas_usuario(guild_id, user_id, fecha)
        if ventana is None or vent == ventana
    ]

    borrados = await eliminar_registros(guild_id, user_id, fecha, ventana)
    await _recalcular(guild_id, afectadas)

    return borrados


async def borrar_usuario(
    guild_id,
    user_id,
):
    """Borra todos los 420 de un usuario y reordena sus ventanas."""

    afectadas = await obtener_ventanas_usuario(guild_id, user_id)
    borrados = await eliminar_registros_usuario(guild_id, user_id)
    await _recalcular(guild_id, afectadas)

    return borrados


async def borrar_servidor(
    guild_id,
):
    """Borra todos los 420 del servidor."""

    return await eliminar_registros_servidor(guild_id)


# ============================================================
# IMPORTACIÓN DEL HISTORIAL
# ============================================================

@dataclass
class ResumenImportacion:
    """Contadores de una importación del historial del canal."""

    revisados: int = 0
    detectados: int = 0
    importados: int = 0
    repetidos: int = 0
    fuera_de_horario: int = 0
    editados: int = 0
    primero: datetime | None = None
    ultimo: datetime | None = None
    ventanas: set = field(default_factory=set)


def _editado_fuera_de_ventana(mensaje, momento, ventana):
    """Indica si el mensaje se editó después de cerrar su ventana.

    En vivo solo cuenta el texto original. En el historial solo se ve el
    texto actual: si se editó más tarde, no se puede saber si a las 16:20
    decía 420, así que no se cuenta (evita la trampa de editar después).
    """

    editado = getattr(mensaje, "edited_at", None)

    if editado is None:
        return False

    editado = _a_hora_local(editado)

    return (
        editado.date() != momento.date()
        or ventana_activa(editado.time()) != ventana
    )


async def importar_mensajes(
    guild_id,
    mensajes,
    al_progresar=None,
    cada=500,
):
    """Importa los 420 de un historial de mensajes (iterable asíncrono).

    Aplica las mismas reglas que el registro en vivo y se puede correr
    varias veces: lo que ya estaba registrado se cuenta como repetido.
    Al terminar reordena todas las ventanas tocadas, así las posiciones
    quedan por hora real del mensaje aunque algunos se hayan registrado
    en vivo antes de importar.

    ``al_progresar(resumen)`` se llama cada ``cada`` mensajes revisados.
    """

    resumen = ResumenImportacion()

    async for mensaje in mensajes:
        resumen.revisados += 1

        if al_progresar is not None and resumen.revisados % cada == 0:
            await al_progresar(resumen)

        if getattr(mensaje.author, "bot", False):
            continue

        if not es_mensaje_420(mensaje.content):
            continue

        resumen.detectados += 1
        momento = _a_hora_local(mensaje.created_at)
        ventana = ventana_activa(momento.time())

        if ventana is None:
            resumen.fuera_de_horario += 1
            continue

        if _editado_fuera_de_ventana(mensaje, momento, ventana):
            resumen.editados += 1
            continue

        resultado = await registrar_lahora(
            guild_id=guild_id,
            user_id=mensaje.author.id,
            username=mensaje.author.display_name,
            momento=momento,
            mensaje_id=mensaje.id,
        )

        # Aunque sea repetido, la ventana se reordena: puede haber un
        # registro en vivo con posición calculada sin los mensajes viejos.
        resumen.ventanas.add((momento.date(), resultado.ventana))

        if resultado.exitoso:
            resumen.importados += 1
            resumen.primero = min(filter(None, (resumen.primero, momento)))
            resumen.ultimo = max(filter(None, (resumen.ultimo, momento)))
        else:
            resumen.repetidos += 1

    await _recalcular(guild_id, resumen.ventanas)

    return resumen
