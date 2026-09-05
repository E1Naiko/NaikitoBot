"""Pruebas de la lógica pura de Madrugue (sin base de datos ni Discord)."""

from datetime import date, time, timedelta

import pytest

from modules.madrugue.logic import (
    calcular_mejor_racha,
    calcular_multiplicador_horario,
    calcular_racha_actual,
    calcular_racha_para_nuevo_registro,
    obtener_puntos_base,
)


# ============================================================
# PUNTOS BASE
# ============================================================

@pytest.mark.parametrize(
    "hora, esperado",
    [
        (time(0, 0), 0),
        (time(5, 29), 0),
        (time(5, 30), 100),
        (time(6, 59), 100),
        (time(7, 0), 25),
        (time(8, 59), 25),
        (time(9, 0), 5),
        (time(9, 59), 5),
        (time(10, 0), 0),
        (time(23, 59), 0),
    ],
)
def test_puntos_base_por_horario(hora, esperado):
    assert obtener_puntos_base(hora) == esperado


# ============================================================
# MULTIPLICADOR HORARIO
# ============================================================

def test_multiplicador_maximo_al_abrir():
    assert calcular_multiplicador_horario(time(5, 30)) == pytest.approx(1.100)


def test_multiplicador_minimo_al_cerrar():
    assert calcular_multiplicador_horario(time(9, 59)) == pytest.approx(
        1.001,
        abs=0.001,
    )


@pytest.mark.parametrize(
    "hora",
    [time(0, 0), time(5, 29), time(10, 0), time(15, 0)],
)
def test_multiplicador_neutro_fuera_de_horario(hora):
    assert calcular_multiplicador_horario(hora) == 1.0


def test_multiplicador_decrece_con_la_hora():
    assert (
        calcular_multiplicador_horario(time(5, 30))
        > calcular_multiplicador_horario(time(7, 0))
        > calcular_multiplicador_horario(time(9, 0))
        > 1.0
    )


# ============================================================
# RACHAS
# ============================================================

HOY = date(2026, 9, 5)


def dias_atras(*dias):
    return [HOY - timedelta(days=dia) for dia in dias]


def test_racha_actual_sin_registros_es_cero():
    assert calcular_racha_actual([], HOY) == 0


def test_racha_actual_requiere_registro_hoy():
    assert calcular_racha_actual(dias_atras(1, 2), HOY) == 0


def test_racha_actual_cuenta_consecutivos():
    assert calcular_racha_actual(dias_atras(0, 1, 2), HOY) == 3
    assert calcular_racha_actual(dias_atras(0, 5), HOY) == 1


def test_mejor_racha_sin_registros_es_cero():
    assert calcular_mejor_racha([]) == 0


def test_mejor_racha():
    assert calcular_mejor_racha(dias_atras(0)) == 1
    assert calcular_mejor_racha(dias_atras(0, 1, 2, 3, 4)) == 5
    assert calcular_mejor_racha(dias_atras(0, 1, 3, 4, 5)) == 3


def test_racha_para_nuevo_registro_sin_ayer_arranca_en_uno():
    assert calcular_racha_para_nuevo_registro(dias_atras(2, 5), HOY) == 1
    assert calcular_racha_para_nuevo_registro([], HOY) == 1


def test_racha_para_nuevo_registro_continua_la_racha():
    assert calcular_racha_para_nuevo_registro(dias_atras(1), HOY) == 2
    assert calcular_racha_para_nuevo_registro(dias_atras(1, 2, 3), HOY) == 4
