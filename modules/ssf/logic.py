from datetime import date, timedelta

from modules.ssf.constants import RANGOS


def calcular_rango(dias_racha):
    """Devuelve el rango correspondiente a los días de racha."""

    rango = RANGOS[0][1]

    for dias_minimos, nombre in RANGOS:
        if dias_racha < dias_minimos:
            break
        rango = nombre

    return rango


def calcular_racha(
    fechas_registradas,
    fecha_actual,
):
    """
    Calcula la racha consecutiva hasta una fecha determinada.
    """

    if not fechas_registradas:
        return 0

    fechas = set(fechas_registradas)

    if fecha_actual not in fechas:
        return 0

    racha = 0
    fecha = fecha_actual

    while fecha in fechas:
        racha += 1
        fecha -= timedelta(days=1)

    return racha


def calcular_mejor_racha(
    fechas_registradas,
):
    """
    Calcula la mejor racha histórica.
    """

    if not fechas_registradas:
        return 0

    fechas = sorted(set(fechas_registradas))

    mejor = 1
    actual = 1

    for i in range(1, len(fechas)):

        if fechas[i] == fechas[i - 1] + timedelta(days=1):
            actual += 1
        else:
            actual = 1

        mejor = max(
            mejor,
            actual,
        )

    return mejor


def fecha_dentro_del_desafio(
    fecha,
    fecha_inicio,
    fecha_fin,
):
    """
    Comprueba si una fecha está dentro del período
    del desafío, incluyendo ambos extremos.
    """

    inicio = date.fromisoformat(
        fecha_inicio
    )

    fin = date.fromisoformat(
        fecha_fin
    )

    return inicio <= fecha <= fin


def fecha_anterior(
    fecha,
):
    """Devuelve el día anterior."""

    return fecha - timedelta(days=1)