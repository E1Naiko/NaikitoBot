from datetime import date, datetime, timedelta

from config import (
    MADRUGUE_BONUS_MAXIMO,
    MADRUGUE_BONUS_MINIMO,
    MADRUGUE_FIN,
    MADRUGUE_INICIO_100,
    MADRUGUE_INICIO_25,
    MADRUGUE_INICIO_5,
    MADRUGUE_PUNTOS_100,
    MADRUGUE_PUNTOS_25,
    MADRUGUE_PUNTOS_5,
)


# ============================================================
# PUNTOS BASE
# ============================================================

def obtener_puntos_base(hora_actual):
    """
    Determina los puntos según la hora.

    INICIO_100 hasta INICIO_25 = puntos de la primera ventana
    INICIO_25 hasta INICIO_5 = puntos de la segunda ventana
    INICIO_5 hasta FIN = puntos de la última ventana
    Fuera de horario = 0

    Las ventanas y los puntos se configuran desde el .env.
    """

    if MADRUGUE_INICIO_100 <= hora_actual < MADRUGUE_INICIO_25:
        return MADRUGUE_PUNTOS_100

    if MADRUGUE_INICIO_25 <= hora_actual < MADRUGUE_INICIO_5:
        return MADRUGUE_PUNTOS_25

    if MADRUGUE_INICIO_5 <= hora_actual < MADRUGUE_FIN:
        return MADRUGUE_PUNTOS_5

    return 0


# ============================================================
# BONUS HORARIO
# ============================================================

def calcular_bonus_horario(hora_actual):
    """
    Calcula el bonus según la hora de registro.

    El bonus disminuye linealmente desde BONUS_MAXIMO al abrir
    la madrugada hasta BONUS_MINIMO al cerrarla.

    Fuera del horario válido -> 0.
    """

    inicio = datetime.combine(
        date.today(),
        MADRUGUE_INICIO_100,
    )

    fin = datetime.combine(
        date.today(),
        MADRUGUE_FIN,
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

    bonus = MADRUGUE_BONUS_MAXIMO - (
        proporcion *
        (MADRUGUE_BONUS_MAXIMO - MADRUGUE_BONUS_MINIMO)
    )

    return max(
        MADRUGUE_BONUS_MINIMO,
        min(
            MADRUGUE_BONUS_MAXIMO,
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