"""Configuración de laHora (canal 420) leída desde el .env.

Como ``config`` se lee al importar, cada caso corre en un subproceso
con su propio entorno, igual que las pruebas de Madrugue.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

SCRIPT = """
import json
from datetime import time

import config
from modules.lahora.logic import calcular_puntos, ventana_activa

print(json.dumps({
    "horas": [h.strftime("%H:%M") for h in config.LAHORA_HORAS],
    "canales": sorted(config.LAHORA_CANALES_ID),
    "a_las_1622": str(ventana_activa(time(16, 22, 30))),
    "a_las_1625": str(ventana_activa(time(16, 25))),
    "puntos": calcular_puntos(0, 1),
}))
"""


def ejecutar(entorno_extra):
    entorno = {
        clave: valor
        for clave, valor in os.environ.items()
        if not clave.startswith("LAHORA_")
    }
    entorno.update(entorno_extra)

    return subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_el_env_cambia_ventanas_y_puntos():
    proceso = ejecutar(
        {
            "LAHORA_HORAS": "16:20,04:20",
            "LAHORA_DURACION_MINUTOS": "5",
            "LAHORA_PUNTOS_BASE": "100",
            "LAHORA_BONUS_VELOCIDAD": "1",
            "LAHORA_BONUS_PRIMERO": "0",
            "LAHORA_CANALES_ID": "111, 222",
        }
    )

    assert proceso.returncode == 0, proceso.stderr
    datos = json.loads(proceso.stdout)

    assert datos["horas"] == ["04:20", "16:20"]
    assert datos["canales"] == [111, 222]
    assert datos["a_las_1622"] == "16:20:00"
    assert datos["a_las_1625"] == "None"
    assert datos["puntos"] == [100, 2.0, 0, 200.0]


@pytest.mark.parametrize(
    "variable, valor",
    [
        ("LAHORA_HORAS", "4:20"),
        ("LAHORA_HORAS", "16:20,25:00"),
        ("LAHORA_HORAS", ","),
        ("LAHORA_HORAS", "16:20,16:20"),
        ("LAHORA_HORAS", "23:59"),
        ("LAHORA_DURACION_MINUTOS", "0"),
        ("LAHORA_DURACION_MINUTOS", "60"),
        ("LAHORA_PUNTOS_BASE", "0"),
        ("LAHORA_BONUS_VELOCIDAD", "-1"),
        ("LAHORA_BONUS_PRIMERO", "-5"),
        ("LAHORA_BONUS_PRIMERO", "mucho"),
    ],
)
def test_valor_invalido_falla_al_arrancar(variable, valor):
    entorno = {variable: valor}

    if valor == "23:59":
        entorno["LAHORA_DURACION_MINUTOS"] = "2"

    proceso = ejecutar(entorno)

    assert proceso.returncode != 0
    assert "Configuración inválida" in proceso.stderr
    assert variable in proceso.stderr


def test_ventanas_superpuestas_fallan():
    proceso = ejecutar(
        {
            "LAHORA_HORAS": "16:20,16:22",
            "LAHORA_DURACION_MINUTOS": "5",
        }
    )

    assert proceso.returncode != 0
    assert "se superponen" in proceso.stderr
