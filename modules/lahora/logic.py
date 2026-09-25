"""Lógica pura del módulo laHora: sin Discord ni base de datos."""

import re
from datetime import date, datetime, timedelta

from config import (
    LAHORA_BONUS_PRIMERO,
    LAHORA_BONUS_VELOCIDAD,
    LAHORA_DURACION_MINUTOS,
    LAHORA_HORAS,
    LAHORA_PUNTOS_BASE,
)


# ============================================================
# DETECCIÓN DEL MENSAJE
# ============================================================

# Formas aceptadas una vez que se sacan espacios, signos y emojis:
# "420", "4:20", "04:20", "4.20", "16:20", "420!!", "420 🌿"...
_FORMAS_420 = {"420", "0420", "1620"}

# Emojis personalizados de Discord (<:nombre:id> o <a:nombre:id>): se
# descartan enteros para que su ID numérico no se mezcle con el texto.
_EMOJI_PERSONALIZADO = re.compile(r"<a?:\w+:\d+>")


def es_mensaje_420(texto):
    """Indica si un mensaje es un "420".

    El mensaje tiene que ser solo el 420 (con cualquier puntuación o
    emoji alrededor): "420", "4:20", "16:20!!", "420 🌿". Un mensaje que
    solo menciona el número dentro de una frase no cuenta.
    """

    if not texto:
        return False

    limpio = _EMOJI_PERSONALIZADO.sub("", texto)
    limpio = "".join(
        caracter
        for caracter in limpio
        if caracter.isascii() and caracter.isalnum()
    )

    return limpio in _FORMAS_420


# ============================================================
# VENTANAS
# ============================================================

def _como_datetime(hora):
    return datetime.combine(date(2000, 1, 1), hora)


def formatear_ventana(ventana):
    """Texto HH:MM de la hora de apertura de una ventana."""

    return ventana.strftime("%H:%M")


def ventana_activa(hora_actual):
    """Devuelve la ventana abierta a esa hora o ``None``.

    Cada ventana abre en una hora de ``LAHORA_HORAS`` y dura
    ``LAHORA_DURACION_MINUTOS`` (por defecto: solo el minuto 04:20 y el
    minuto 16:20, es decir de 16:20:00 a 16:20:59).
    """

    actual = _como_datetime(hora_actual.replace(tzinfo=None))
    duracion = timedelta(minutes=LAHORA_DURACION_MINUTOS)

    for ventana in LAHORA_HORAS:
        inicio = _como_datetime(ventana)

        if inicio <= actual < inicio + duracion:
            return ventana

    return None


def segundos_desde_apertura(hora_actual, ventana):
    """Segundos enteros desde que abrió la ventana."""

    diferencia = (
        _como_datetime(hora_actual.replace(tzinfo=None))
        - _como_datetime(ventana)
    )

    return max(0, int(diferencia.total_seconds()))


# ============================================================
# PUNTOS
# ============================================================

def calcular_multiplicador(segundos):
    """Multiplicador por velocidad dentro de la ventana.

    Arranca en ``1 + LAHORA_BONUS_VELOCIDAD`` en el segundo 0 y baja
    linealmente hasta ``1`` al cerrar la ventana.
    """

    duracion = LAHORA_DURACION_MINUTOS * 60
    restante = max(0, duracion - segundos) / duracion

    return round(1 + LAHORA_BONUS_VELOCIDAD * restante, 3)


def calcular_bonus_posicion(posicion):
    """Puntos extra para el primero de cada ventana."""

    return LAHORA_BONUS_PRIMERO if posicion == 1 else 0


def calcular_puntos(segundos, posicion):
    """Devuelve ``(puntos_base, multiplicador, bonus, puntos_finales)``."""

    multiplicador = calcular_multiplicador(segundos)
    bonus = calcular_bonus_posicion(posicion)
    finales = round(LAHORA_PUNTOS_BASE * multiplicador + bonus, 1)

    return LAHORA_PUNTOS_BASE, multiplicador, bonus, finales


# ============================================================
# RACHAS (días seguidos con al menos un 420)
# ============================================================

def calcular_mejor_racha(fechas_registradas):
    """Mejor racha histórica de días consecutivos."""

    fechas = sorted(set(fechas_registradas))

    if not fechas:
        return 0

    mejor = actual = 1

    for anterior, siguiente in zip(fechas, fechas[1:]):
        if siguiente - anterior == timedelta(days=1):
            actual += 1
        else:
            actual = 1

        mejor = max(mejor, actual)

    return mejor


def calcular_racha_actual(fechas_registradas, hoy):
    """Racha vigente: días seguidos que terminan hoy o ayer.

    Si todavía no dijo 420 hoy, la racha de ayer sigue viva hasta que
    termine el día.
    """

    fechas = set(fechas_registradas)

    if hoy in fechas:
        dia = hoy
    elif hoy - timedelta(days=1) in fechas:
        dia = hoy - timedelta(days=1)
    else:
        return 0

    racha = 0

    while dia in fechas:
        racha += 1
        dia -= timedelta(days=1)

    return racha


def texto_ventanas():
    """Líneas «**HH:MM – HH:MM**» con las ventanas configuradas."""

    lineas = []

    for ventana in LAHORA_HORAS:
        cierre = (
            _como_datetime(ventana)
            + timedelta(minutes=LAHORA_DURACION_MINUTOS)
            - timedelta(seconds=1)
        ).time()

        lineas.append(
            f"**{formatear_ventana(ventana)}:00 – "
            f"{cierre.strftime('%H:%M:%S')}**"
        )

    return "\n".join(lineas)


__all__ = [
    "calcular_bonus_posicion",
    "calcular_mejor_racha",
    "calcular_multiplicador",
    "calcular_puntos",
    "calcular_racha_actual",
    "es_mensaje_420",
    "formatear_ventana",
    "segundos_desde_apertura",
    "texto_ventanas",
    "ventana_activa",
]
