"""Fachada del módulo Madrugue.

Los cogs importan desde acá y no directamente de ``database`` ni ``logic``,
igual que en los módulos Box y SSF.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from config import (
    MADRUGUE_FIN,
    MADRUGUE_INICIO_100,
    MADRUGUE_INICIO_25,
    MADRUGUE_INICIO_5,
    MADRUGUE_PUNTOS_100,
    MADRUGUE_PUNTOS_25,
    MADRUGUE_PUNTOS_5,
)

from modules.madrugue.database import (
    eliminar_registro_del_dia,
    eliminar_registros_servidor,
    eliminar_registros_usuario,
    guardar_registro,
    obtener_estadisticas_servidor,
    obtener_fechas_registradas,
    obtener_registro_del_dia,
    obtener_registro_del_dia_admin,
    obtener_resumen_usuario,
    obtener_top_madrugadores,
    obtener_total_puntos,
    obtener_ultimos_registros,
)

from modules.madrugue.logic import (
    calcular_mejor_racha,
    calcular_multiplicador_horario,
    calcular_racha_para_nuevo_registro,
    obtener_puntos_base,
)

__all__ = [
    # Lógica pura
    "calcular_mejor_racha",
    "calcular_multiplicador_horario",
    "calcular_racha_para_nuevo_registro",
    "obtener_puntos_base",
    # Persistencia
    "eliminar_registro_del_dia",
    "eliminar_registros_servidor",
    "eliminar_registros_usuario",
    "guardar_registro",
    "obtener_estadisticas_servidor",
    "obtener_fechas_registradas",
    "obtener_registro_del_dia",
    "obtener_registro_del_dia_admin",
    "obtener_resumen_usuario",
    "obtener_top_madrugadores",
    "obtener_total_puntos",
    "obtener_ultimos_registros",
    # Servicios
    "ResultadoMadrugue",
    "obtener_stats_madrugue",
    "obtener_top_madrugue",
    "registrar_madrugue",
    # Textos de horario
    "texto_horario_valido",
    "texto_ventanas_puntos",
]


# ============================================================
# TEXTOS DE HORARIO
# ============================================================

def _formatear_hora(hora):
    """Da formato HH:MM a una hora de la configuración."""

    return hora.strftime("%H:%M")


def _minuto_anterior(hora):
    """Devuelve la hora de un minuto antes, para cerrar una ventana."""

    cierre = (
            datetime.combine(
                date(2000, 1, 1),
                hora,
            )
            - timedelta(minutes=1)
    )

    return cierre.time()


def texto_horario_valido():
    """
    Texto «HH:MM a HH:MM» con el horario válido.

    Se arma con los valores configurados en el .env para que los
    mensajes de los comandos no queden desactualizados si cambian
    las ventanas.
    """

    return (
        f"{_formatear_hora(MADRUGUE_INICIO_100)} "
        f"a {_formatear_hora(MADRUGUE_FIN)}"
    )


def texto_ventanas_puntos():
    """
    Líneas «**HH:MM – HH:MM** → N puntos» para la ayuda.

    Como ``texto_horario_valido``, se arma con los valores
    configurados en el .env.
    """

    ventanas = (
        (
            MADRUGUE_INICIO_100,
            MADRUGUE_INICIO_25,
            MADRUGUE_PUNTOS_100,
        ),
        (
            MADRUGUE_INICIO_25,
            MADRUGUE_INICIO_5,
            MADRUGUE_PUNTOS_25,
        ),
        (
            MADRUGUE_INICIO_5,
            MADRUGUE_FIN,
            MADRUGUE_PUNTOS_5,
        ),
    )

    lineas = [
        f"**{_formatear_hora(desde)} – "
        f"{_formatear_hora(_minuto_anterior(hasta))}** → "
        f"{puntos} puntos"
        for desde, hasta, puntos in ventanas
    ]

    lineas.append(
        f"**{_formatear_hora(MADRUGUE_FIN)} en adelante** "
        "→ fuera de horario"
    )

    return "\n".join(lineas)


@dataclass
class ResultadoMadrugue:
    """Resultado de un intento de registro."""

    exitoso: bool
    motivo: str
    hora: datetime
    puntos_base: int = 0
    multiplicador: float = 1.0
    puntos_finales: float = 0.0
    racha: int = 0
    total_puntos: float = 0.0
    hora_anterior: str | None = None
    puntos_anterior: float = 0.0


async def registrar_madrugue(
        guild_id,
        user_id,
        username,
        ahora,
):
    """
    Registra una madrugada para un usuario.

    Esta función contiene la lógica de negocio del registro,
    pero no depende de Discord.
    """

    fecha = ahora.date()
    hora = ahora.time()

    # ========================================================
    # PUNTOS BASE
    # ========================================================

    puntos_base = obtener_puntos_base(hora)

    if puntos_base == 0:
        return ResultadoMadrugue(
            exitoso=False,
            motivo="fuera_de_horario",
            hora=ahora,
        )

    # ========================================================
    # COMPROBAR REGISTRO EXISTENTE
    # ========================================================

    registro_existente = await obtener_registro_del_dia(
        guild_id,
        user_id,
        fecha,
    )

    if registro_existente:
        hora_anterior, puntos_anterior = registro_existente

        return ResultadoMadrugue(
            exitoso=False,
            motivo="ya_registrado",
            hora=ahora,
            hora_anterior=hora_anterior,
            puntos_anterior=puntos_anterior,
        )

    # ========================================================
    # RACHA
    # ========================================================

    fechas = await obtener_fechas_registradas(
        guild_id,
        user_id,
    )

    racha = calcular_racha_para_nuevo_registro(
        fechas,
        fecha,
    )

    # ========================================================
    # MULTIPLICADOR
    # ========================================================

    multiplicador = calcular_multiplicador_horario(
        hora
    )

    puntos_finales = (
            puntos_base *
            multiplicador
    )

    # ========================================================
    # GUARDAR
    # ========================================================

    await guardar_registro(
        guild_id=guild_id,
        user_id=user_id,
        username=username,
        fecha=fecha,
        hora=ahora.strftime("%H:%M"),
        puntos_base=puntos_base,
        multiplicador=multiplicador,
        puntos_finales=puntos_finales,
    )

    # ========================================================
    # TOTAL
    # ========================================================

    total_puntos = await obtener_total_puntos(
        guild_id,
        user_id,
    )

    return ResultadoMadrugue(
        exitoso=True,
        motivo="registrado",
        hora=ahora,
        puntos_base=puntos_base,
        multiplicador=multiplicador,
        puntos_finales=puntos_finales,
        racha=racha,
        total_puntos=total_puntos,
    )


async def obtener_stats_madrugue(
        guild_id,
        user_id,
):
    """
    Obtiene las estadísticas de Madrugue de un usuario.
    """

    total_puntos = await obtener_total_puntos(
        guild_id,
        user_id,
    )

    fechas = await obtener_fechas_registradas(
        guild_id,
        user_id,
    )

    mejor_racha = calcular_mejor_racha(
        fechas,
    )

    return {
        "total_puntos": total_puntos,
        "mejor_racha": mejor_racha,
    }


async def obtener_top_madrugue(
        guild_id,
        limite=10,
):
    """
    Obtiene el TOP de Madrugue de un servidor.
    """

    return await obtener_top_madrugadores(
        guild_id,
        limite,
    )