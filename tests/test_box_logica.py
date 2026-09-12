"""Pruebas de la lógica pura de Box (sin base de datos ni Discord)."""

from datetime import datetime, timedelta

import pytest

from modules.box.logic import (
    calidad_equipamiento,
    estadisticas_de_combate,
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


# ============================================================
# ESTADÍSTICAS DE COMBATE (el equipamiento, esta vez, sí pesa)
# ============================================================

SIN_EQUIPO = {"vida_maxima": 32, "dano": 12, "defensa": 8}


def test_sin_equipamiento_las_estadisticas_quedan_igual():
    salida = estadisticas_de_combate(SIN_EQUIPO, {})

    assert salida["vida_maxima"] == 32
    assert salida["dano"] == 12
    assert salida["defensa"] == 8
    assert salida["fatiga"] == 1.0
    assert salida["fuerza"] == 1.0


def test_guantes_suben_el_dano_y_casco_la_defensa():
    con_equipo = estadisticas_de_combate(
        SIN_EQUIPO, {"guantes": 2, "casco": 2}, por_nivel=0.05
    )

    assert con_equipo["dano"] == 13      # 12 * 1,10 -> 13,2 -> 13
    assert con_equipo["defensa"] == 9    # 8 * 1,10 -> 8,8 -> 9
    assert con_equipo["vida_maxima"] == 32


def test_las_botas_retrasan_la_fatiga_sin_hacerlo_inmune():
    con_botas = estadisticas_de_combate(SIN_EQUIPO, {"botas": 4}, por_nivel=0.05)
    extremas = estadisticas_de_combate(
        SIN_EQUIPO, {"botas": 4}, por_nivel=0.9
    )

    assert con_botas["fatiga"] < 1.0
    # Un peso absurdo de configuración no puede convertir a alguien en
    # incorreggable: el piso del multiplicador es 0,4.
    assert extremas["fatiga"] == 0.4


@pytest.mark.parametrize(
    "niveles",
    [
        {"guantes": 99},
        {
            "guantes": 99,
            "casco": 99,
            "protector_bucal": 99,
            "short": 99,
            "botas": 99,
        },
    ],
)
def test_un_nivel_fuera_de_rango_no_explota_el_bono(niveles):
    """El techo es ``NIVEL_MAXIMO_EQUIPAMIENTO`` por pieza, no lo que diga la fila.

    La fila se escribe con un ``UPDATE`` administrativo: si se trustara, alguien
    podría comprarse daño x100 con un ``puntos_habilidad`` mal puesto.
    """

    tope = 4
    salida = estadisticas_de_combate(SIN_EQUIPO, niveles, por_nivel=0.05)

    assert salida["dano"] <= round(12 * (1 + 0.05 * tope))
    assert salida["fuerza"] <= 1 + 0.2 * tope * 5


def test_la_fuerza_suma_por_piece_no_por_estadistica():
    """Cinco piezas al máximo pesan más que una al máximo."""

    una = estadisticas_de_combate(SIN_EQUIPO, {"guantes": 4}, fuerza_por_nivel=0.02)
    cinco = estadisticas_de_combate(
        SIN_EQUIPO,
        {
            "guantes": 4,
            "casco": 4,
            "protector_bucal": 4,
            "short": 4,
            "botas": 4,
        },
        fuerza_por_nivel=0.02,
    )

    assert una["fuerza"] == pytest.approx(1.08)
    assert cinco["fuerza"] == pytest.approx(1.4)


def test_el_interruptor_de_equipamiento_desconecta_todo():
    """Con ``BOX_COMBATE_EQUIPO_ACTIVO=0`` se vuelve al comportamiento viejo."""

    salida = estadisticas_de_combate(
        SIN_EQUIPO,
        {"guantes": 4, "casco": 4, "botas": 4},
        activo=False,
    )

    assert salida["dano"] == 12
    assert salida["defensa"] == 8
    assert salida["fatiga"] == 1.0
    assert salida["fuerza"] == 1.0


def test_una_fila_de_equipamiento_incompleta_no_revienta():
    """Los niveles ``NULL`` o ``0`` se leen como "sin equipar".

    Un ``INSERT INTO box_equipo (guild_id, user_id)`` deja ceros, y un
    administrativo puede haber dejado un ``NULL`` suelto antes de la migración.
    """

    salida = estadisticas_de_combate(SIN_EQUIPO, {"casco": None, "botas": 0})

    assert salida["fuerza"] == 1.0
