from datetime import date, datetime

from config import (
    BONUS_MAXIMO,
    BONUS_MINIMO,
    FIN_MADRUGADA,
    PUNTOS_100_DESDE,
    PUNTOS_25_DESDE,
    PUNTOS_5_DESDE,
)


# ============================================================
# PUNTOS BASE
# ============================================================

def obtener_puntos_base(hora_actual):
    """
    Determina los puntos según la hora.

    05:30 - 06:59 = 100 puntos
    07:00 - 08:59 = 25 puntos
    09:00 - 09:59 = 5 puntos
    Fuera de horario = 0
    """

    if PUNTOS_100_DESDE <= hora_actual < PUNTOS_25_DESDE:
        return 100

    if PUNTOS_25_DESDE <= hora_actual < PUNTOS_5_DESDE:
        return 25

    if PUNTOS_5_DESDE <= hora_actual < FIN_MADRUGADA:
        return 5

    return 0


# ============================================================
# BONUS HORARIO
# ============================================================

def calcular_bonus_horario(hora_actual):
    """
    Calcula el bonus según la hora de registro.

    El bonus disminuye linealmente:

        05:30 -> +0.100
        10:00 -> +0.001

    Fuera del horario válido -> 0.
    """

    inicio = datetime.combine(
        date.today(),
        PUNTOS_100_DESDE,
    )

    fin = datetime.combine(
        date.today(),
        FIN_MADRUGADA,
    )

    hora = datetime.combine(
        date.today(),
        hora_actual,
    )

    if hora < inicio or hora >= fin:
        return 0.0

    duracion_total = (
        fin - inicio
    ).total_seconds()

    tiempo_transcurrido = (
        hora - inicio
    ).total_seconds()

    proporcion = (
        tiempo_transcurrido /
        duracion_total
    )

    bonus = BONUS_MAXIMO - (
        proporcion *
        (BONUS_MAXIMO - BONUS_MINIMO)
    )

    return max(
        BONUS_MINIMO,
        min(
            BONUS_MAXIMO,
            bonus,
        ),
    )


# ============================================================
# MULTIPLICADOR HORARIO
# ============================================================

def calcular_multiplicador_horario(hora_actual):
    """
    Devuelve el multiplicador correspondiente
    a la hora de registro.
    """

    return 1.0 + calcular_bonus_horario(
        hora_actual
    )