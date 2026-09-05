from datetime import date, datetime, timedelta

from modules.madrugue.constants import (
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


# ============================================================
# RACHA ACTUAL
# ============================================================

def calcular_racha_actual(
    fechas_registradas,
    fecha_actual,
):
    """
    Calcula la racha actual a partir de un conjunto
    de fechas registradas.

    La racha solo está activa si existe un registro
    para la fecha actual.
    """

    if not fechas_registradas:
        return 0

    fechas = set(fechas_registradas)

    if fecha_actual not in fechas:
        return 0

    racha = 0
    fecha_comprobar = fecha_actual

    while fecha_comprobar in fechas:

        racha += 1

        fecha_comprobar -= timedelta(
            days=1
        )

    return racha

# ============================================================
# MEJOR RACHA
# ============================================================

def calcular_mejor_racha(
    fechas_registradas,
):
    """
    Calcula la mejor racha histórica
    a partir de las fechas registradas.
    """

    if not fechas_registradas:
        return 0

    fechas = sorted(fechas_registradas)

    mejor = 1
    actual = 1

    for i in range(
        1,
        len(fechas),
    ):

        diferencia = (
            fechas[i] -
            fechas[i - 1]
        )

        if diferencia == timedelta(days=1):

            actual += 1

        else:

            actual = 1

        mejor = max(
            mejor,
            actual,
        )

    return mejor

# ============================================================
# RACHA PARA NUEVO REGISTRO
# ============================================================

def calcular_racha_para_nuevo_registro(
    fechas_registradas,
    fecha,
):
    """
    Calcula la racha que tendrá un nuevo registro.

    Si existe un registro ayer, cuenta hacia atrás
    desde ayer para determinar la racha anterior
    y suma el registro nuevo.

    Si no existe registro ayer, la racha comienza
    en 1.
    """

    ayer = fecha - timedelta(days=1)

    fechas = set(fechas_registradas)

    if ayer not in fechas:
        return 1

    racha = 1
    fecha_comprobar = ayer

    while fecha_comprobar in fechas:

        racha += 1

        fecha_comprobar -= timedelta(
            days=1
        )

    return racha