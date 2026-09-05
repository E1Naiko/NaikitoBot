"""Fachada del módulo Madrugue.

Los cogs importan desde acá y no directamente de ``database`` ni ``logic``,
igual que en los módulos Box y SSF.
"""

from dataclasses import dataclass
from datetime import datetime

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
    # Servicios
    "ResultadoMadrugue",
    "obtener_stats_madrugue",
    "obtener_top_madrugue",
    "registrar_madrugue",
]


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


def registrar_madrugue(
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

    registro_existente = obtener_registro_del_dia(
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

    fechas = obtener_fechas_registradas(
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

    guardar_registro(
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

    total_puntos = obtener_total_puntos(
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

def obtener_stats_madrugue(
    guild_id,
    user_id,
):
    """
    Obtiene las estadísticas de Madrugue de un usuario.
    """

    total_puntos = obtener_total_puntos(
        guild_id,
        user_id,
    )

    fechas = obtener_fechas_registradas(
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
    
def obtener_top_madrugue(
    guild_id,
    limite=10,
):
    """
    Obtiene el TOP de Madrugue de un servidor.
    """

    return obtener_top_madrugadores(
        guild_id,
        limite,
    )