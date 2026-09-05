"""Pruebas de registro y eliminación en SeptSinFP.

Bug 1: ``eliminar_participante`` pisaba ``racha_actual`` con 0, así que el
eliminado caía a ``Soldado 🪖`` en ``/ssf estado`` y ``/ssf participantes``.

Bug 2: ``registrar_usuario`` no creaba la entrada en ``ssf_registros``, así
que registrarse el 1/9 y cumplir del 2 al 6 daba racha 5 en vez de 6.
"""

from datetime import date, datetime

import pytest

from modules.ssf.database import (
    obtener_participante,
    tiene_registro,
)
from modules.ssf.logic import calcular_rango
from modules.ssf.services import (
    eliminar_faltantes,
    iniciar_desafio,
    obtener_estado_usuario,
    obtener_lista_participantes,
    registrar_sobrevivi,
    registrar_usuario,
)

GUILD = 1
USUARIO = 42
CANAL = 99

NOMBRE = "SeptiembreSinFAP"
INICIO = "2026-09-01"
FIN = "2026-09-30"

RANGO_SEIS_DIAS = "Tercer Sargento 🥉"


@pytest.fixture
def desafio_ssf(base_datos_limpia):
    """Crea el desafío de septiembre sobre una base limpia."""

    from modules.ssf.database import inicializar_db

    inicializar_db()

    resultado = iniciar_desafio(
        GUILD,
        NOMBRE,
        INICIO,
        FIN,
        CANAL,
    )

    assert resultado["exitoso"]

    return resultado["desafio_id"]


def mediodia(dia):
    return datetime(2026, 9, dia, 12, 0)


def registrar_el_primero():
    return registrar_usuario(
        GUILD,
        USUARIO,
        "Tester",
        mediodia(1),
    )


def sobrevivir(dias):
    for dia in dias:
        resultado = registrar_sobrevivi(
            GUILD,
            USUARIO,
            mediodia(dia),
        )
        assert resultado["exitoso"], f"día {dia}: {resultado!r}"


# ============================================================
# BUG 2 — REGISTRARSE CUENTA COMO EL DÍA 1
# ============================================================

def test_registrarse_crea_el_registro_del_dia(desafio_ssf):
    resultado = registrar_el_primero()

    assert resultado["exitoso"]
    assert resultado["racha"] == 1
    assert resultado["mejor_racha"] == 1
    assert resultado["rango"] == calcular_rango(1)

    assert tiene_registro(desafio_ssf, USUARIO, INICIO)

    participante = obtener_participante(desafio_ssf, USUARIO)
    assert participante[6] == 1  # racha_actual
    assert participante[7] == 1  # mejor_racha


def test_registrarse_el_1_y_cumplir_del_2_al_6_da_racha_6(desafio_ssf):
    registrar_el_primero()
    sobrevivir([2, 3, 4, 5, 6])

    estado = obtener_estado_usuario(GUILD, USUARIO)

    assert estado["exitoso"]
    assert estado["racha_actual"] == 6
    assert estado["mejor_racha"] == 6
    assert estado["rango"] == RANGO_SEIS_DIAS


def test_sobrevivi_el_dia_de_registro_no_cuenta_doble(desafio_ssf):
    registrar_el_primero()

    resultado = registrar_sobrevivi(GUILD, USUARIO, mediodia(1))

    assert resultado == {
        "exitoso": False,
        "motivo": "ya_registrado",
    }

    estado = obtener_estado_usuario(GUILD, USUARIO)
    assert estado["racha_actual"] == 1


# ============================================================
# BUG 1 — ELIMINAR CONSERVA LA RACHA Y EL RANGO
# ============================================================

def test_eliminar_conserva_racha_y_rango(desafio_ssf):
    registrar_el_primero()
    sobrevivir([2, 3, 4, 5, 6])

    eliminados = eliminar_faltantes(GUILD, date(2026, 9, 7))

    assert eliminados == 1

    estado = obtener_estado_usuario(GUILD, USUARIO)

    assert estado["exitoso"]
    assert estado["eliminado"] is True
    assert estado["racha_actual"] == 6
    assert estado["mejor_racha"] == 6
    assert estado["rango"] == RANGO_SEIS_DIAS


def test_participantes_muestra_la_racha_del_eliminado(desafio_ssf):
    registrar_el_primero()
    sobrevivir([2, 3, 4, 5, 6])
    eliminar_faltantes(GUILD, date(2026, 9, 7))

    participantes = obtener_lista_participantes(GUILD)

    assert len(participantes) == 1

    (
        _user_id,
        _username,
        _fecha_registro,
        eliminado,
        _fecha_eliminacion,
        racha_actual,
        mejor_racha,
    ) = participantes[0]

    assert eliminado == 1
    assert racha_actual == 6
    assert mejor_racha == 6
