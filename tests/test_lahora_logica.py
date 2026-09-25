"""Lógica pura de laHora (canal 420) con la configuración por defecto.

Valores por defecto: ventanas 04:20 y 16:20 de 1 minuto, 10 puntos base,
bonus de velocidad 0.5 y +5 al primero.
"""

from datetime import date, time

import pytest

from modules.lahora.logic import (
    calcular_mejor_racha,
    calcular_multiplicador,
    calcular_puntos,
    calcular_racha_actual,
    es_mensaje_420,
    segundos_desde_apertura,
    texto_ventanas,
    ventana_activa,
)


# ============================================================
# DETECCIÓN DEL MENSAJE
# ============================================================

@pytest.mark.parametrize(
    "texto",
    [
        "420",
        " 420 ",
        "4:20",
        "04:20",
        "4.20",
        "4 20",
        "16:20",
        "1620",
        "420!!!",
        "¡420!",
        "420 🌿",
        "🌿🌿 420 🌿🌿",
        "420 <:hoja:123456789012345678>",
        "**420**",
    ],
)
def test_detecta_420(texto):
    assert es_mensaje_420(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "",
        None,
        "42",
        "4200",
        "421",
        "hola 420",
        "son las 420",
        "420 gente",
        "<:420:123456789012345678>",
        "15:20",
    ],
)
def test_no_detecta_otros_mensajes(texto):
    assert not es_mensaje_420(texto)


# ============================================================
# VENTANAS
# ============================================================

@pytest.mark.parametrize(
    "hora, esperada",
    [
        (time(4, 19, 59), None),
        (time(4, 20, 0), time(4, 20)),
        (time(4, 20, 59), time(4, 20)),
        (time(4, 21, 0), None),
        (time(16, 19, 59), None),
        (time(16, 20, 0), time(16, 20)),
        (time(16, 20, 30, 500000), time(16, 20)),
        (time(16, 20, 59, 999999), time(16, 20)),
        (time(16, 21, 0), None),
        (time(0, 0), None),
        (time(12, 20), None),
    ],
)
def test_ventana_activa(hora, esperada):
    assert ventana_activa(hora) == esperada


def test_segundos_desde_apertura():
    assert segundos_desde_apertura(time(16, 20, 0), time(16, 20)) == 0
    assert segundos_desde_apertura(time(16, 20, 42, 900000), time(16, 20)) == 42


def test_texto_ventanas_usa_la_configuracion():
    texto = texto_ventanas()

    assert "04:20:00 – 04:20:59" in texto
    assert "16:20:00 – 16:20:59" in texto


# ============================================================
# PUNTOS
# ============================================================

def test_multiplicador_maximo_al_abrir():
    assert calcular_multiplicador(0) == 1.5


def test_multiplicador_minimo_al_cerrar():
    assert calcular_multiplicador(60) == 1.0


def test_multiplicador_decrece():
    valores = [calcular_multiplicador(segundo) for segundo in range(60)]

    assert valores == sorted(valores, reverse=True)


def test_puntos_del_primero_incluyen_bonus():
    assert calcular_puntos(0, 1) == (10, 1.5, 5, 20.0)


def test_puntos_sin_bonus_de_posicion():
    assert calcular_puntos(30, 2) == (10, 1.25, 0, 12.5)


# ============================================================
# RACHAS
# ============================================================

def test_mejor_racha_sin_registros():
    assert calcular_mejor_racha([]) == 0


def test_mejor_racha_ignora_dos_ventanas_el_mismo_dia():
    fechas = [
        date(2026, 9, 1),
        date(2026, 9, 1),
        date(2026, 9, 2),
        date(2026, 9, 3),
        date(2026, 9, 5),
    ]

    assert calcular_mejor_racha(fechas) == 3


def test_racha_actual_sigue_viva_si_fue_ayer():
    fechas = [date(2026, 9, 3), date(2026, 9, 4)]

    assert calcular_racha_actual(fechas, date(2026, 9, 5)) == 2


def test_racha_actual_incluye_hoy():
    fechas = [date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 5)]

    assert calcular_racha_actual(fechas, date(2026, 9, 5)) == 3


def test_racha_actual_se_corta():
    fechas = [date(2026, 9, 1), date(2026, 9, 2)]

    assert calcular_racha_actual(fechas, date(2026, 9, 5)) == 0
