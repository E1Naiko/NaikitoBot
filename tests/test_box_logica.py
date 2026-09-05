"""Pruebas de la lógica pura de Box (sin base de datos ni Discord)."""

from datetime import datetime, timedelta

import pytest

from modules.box.logic import (
    calidad_equipamiento,
    formato_ratio,
    precio_equipamiento,
    precio_mejora,
    resolver_duracion,
)


# ============================================================
# PRECIOS
# ============================================================

def test_precio_mejora_nivel_cero_es_el_precio_base():
    assert precio_mejora(1000, 0) == 1000


def test_precio_mejora_aplica_aumento_compuesto_del_25():
    assert precio_mejora(1000, 1) == 1250
    assert precio_mejora(1000, 2) == 1563  # 1562.5 -> techo


def test_precio_equipamiento_se_duplica_por_nivel():
    assert precio_equipamiento(1000, 0) == 1000
    assert precio_equipamiento(1000, 1) == 2000
    assert precio_equipamiento(600, 2) == 2400


def test_calidad_equipamiento_mapea_nivel_a_nombre():
    assert calidad_equipamiento("casco", 0) == "Basico"
    assert calidad_equipamiento("casco", 4) == "Legendario"


def test_calidad_equipamiento_desconocido_lanza():
    with pytest.raises(KeyError):
        calidad_equipamiento("armadura", 0)


# ============================================================
# RATIO
# ============================================================

@pytest.mark.parametrize(
    "ratio, esperado",
    [
        (float("inf"), "∞"),
        (2.0, "2.00"),
        (0.333333, "0.33"),
        (0.0, "0.00"),
    ],
)
def test_formato_ratio(ratio, esperado):
    assert formato_ratio(ratio) == esperado


# ============================================================
# DURACIÓN DE LAS ACCIONES
# ============================================================

INICIO = datetime(2026, 9, 5, 10, 0)


def test_resolver_duracion_por_minutos():
    duracion, error = resolver_duracion(90, None, INICIO)

    assert error is None
    assert duracion.minutos == 90
    assert duracion.finaliza_en == INICIO + timedelta(minutes=90)


def test_resolver_duracion_por_hora_mismo_dia():
    duracion, error = resolver_duracion(None, "18:30", INICIO)

    assert error is None
    assert duracion.minutos == 510
    assert duracion.finaliza_en == datetime(2026, 9, 5, 18, 30)


def test_resolver_duracion_por_hora_cruza_medianoche():
    """Si la hora ya pasó, se agenda para el día siguiente."""

    duracion, error = resolver_duracion(None, "02:00", INICIO)

    assert error is None
    assert duracion.finaliza_en == datetime(2026, 9, 6, 2, 0)
    assert duracion.minutos == 960


def test_resolver_duracion_rechaza_minutos_y_hora_juntos():
    duracion, error = resolver_duracion(60, "18:00", INICIO)

    assert duracion is None
    assert error == "ambas"


def test_resolver_duracion_rechaza_hora_mal_formada():
    duracion, error = resolver_duracion(None, "18:99", INICIO)

    assert duracion is None
    assert error == "formato_hora"


def test_resolver_duracion_rechaza_ausencia_de_datos():
    duracion, error = resolver_duracion(None, None, INICIO)

    assert duracion is None
    assert error == "falta_duracion"


@pytest.mark.parametrize("minutos", [0, -5, 1441])
def test_resolver_duracion_rechaza_minutos_fuera_de_rango(minutos):
    duracion, error = resolver_duracion(minutos, None, INICIO)

    assert duracion is None
    assert error == "fuera_rango"


def test_resolver_duracion_acepta_los_extremos_validos():
    assert resolver_duracion(1, None, INICIO)[1] is None
    assert resolver_duracion(1440, None, INICIO)[1] is None
