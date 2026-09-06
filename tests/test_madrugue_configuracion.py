"""Pruebas de regresión de la puntuación de Madrugue configurada por .env.

La puntuación (ventanas, puntos y bonus) se lee en ``config/settings.py``
desde variables ``MADRUGUE_*`` en el momento de la importación, igual que
el resto de la configuración. Como el proceso de pruebas ya tiene el módulo
cargado con los valores por defecto, estas pruebas corren un subproceso con
su propio entorno para reproducir lo que pasa al cambiar el .env y
reiniciar el bot:

- otro juego de variables cambia ventanas, puntos y multiplicador;
- los valores por defecto mantienen la puntuación histórica;
- un valor inválido impide arrancar con un error claro.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Configuración alternativa: corrimos las ventanas, cambiamos los
# puntos de cada una y achicamos el bonus.
ENTORNO_ALTERNATIVO = {
    "MADRUGUE_INICIO_100": "06:00",
    "MADRUGUE_INICIO_25": "07:30",
    "MADRUGUE_INICIO_5": "08:30",
    "MADRUGUE_FIN": "11:00",
    "MADRUGUE_PUNTOS_100": "50",
    "MADRUGUE_PUNTOS_25": "10",
    "MADRUGUE_PUNTOS_5": "2",
    "MADRUGUE_BONUS_MAXIMO": "0.5",
    "MADRUGUE_BONUS_MINIMO": "0.25",
}

# Los valores por defecto documentados en .env.example: tienen que
# reproducir la puntuación histórica fija de modules/madrugue/constants.py.
ENTORNO_POR_DEFECTO = {
    "MADRUGUE_INICIO_100": "05:30",
    "MADRUGUE_INICIO_25": "07:00",
    "MADRUGUE_INICIO_5": "09:00",
    "MADRUGUE_FIN": "10:00",
    "MADRUGUE_PUNTOS_100": "100",
    "MADRUGUE_PUNTOS_25": "25",
    "MADRUGUE_PUNTOS_5": "5",
    "MADRUGUE_BONUS_MAXIMO": "0.100",
    "MADRUGUE_BONUS_MINIMO": "0.001",
}

# Importa la configuración y la lógica de Madrugue en un proceso limpio
# y devuelve todo lo relevante como JSON.
SCRIPT_VALORES = """
import json
from datetime import date, datetime, timedelta

import config
from modules.madrugue.logic import (
    calcular_multiplicador_horario,
    obtener_puntos_base,
)
from modules.madrugue.services import (
    texto_horario_valido,
    texto_ventanas_puntos,
)

minuto_anterior = lambda hora: (
    datetime.combine(date(2000, 1, 1), hora) - timedelta(minutes=1)
).time()

horas = [
    "00:00", "05:29", "05:30", "05:59", "06:00", "07:00", "07:29",
    "07:30", "08:29", "08:30", "08:59", "09:00", "09:59", "10:00",
    "10:59", "11:00", "23:59",
]

print(json.dumps({
    "ventanas": [
        config.MADRUGUE_INICIO_100.isoformat(),
        config.MADRUGUE_INICIO_25.isoformat(),
        config.MADRUGUE_INICIO_5.isoformat(),
        config.MADRUGUE_FIN.isoformat(),
    ],
    "puntos": [
        config.MADRUGUE_PUNTOS_100,
        config.MADRUGUE_PUNTOS_25,
        config.MADRUGUE_PUNTOS_5,
    ],
    "bonus": [
        config.MADRUGUE_BONUS_MAXIMO,
        config.MADRUGUE_BONUS_MINIMO,
    ],
    "puntos_base": {
        hora: obtener_puntos_base(
            datetime.strptime(hora, "%H:%M").time()
        )
        for hora in horas
    },
    "multiplicador_apertura": calcular_multiplicador_horario(
        config.MADRUGUE_INICIO_100
    ),
    "multiplicador_cierre": calcular_multiplicador_horario(
        minuto_anterior(config.MADRUGUE_FIN)
    ),
    "horario_valido": texto_horario_valido(),
    "texto_ventanas": texto_ventanas_puntos(),
}))
"""

SCRIPT_ARRANQUE = "import config"


def correr_subproceso(script, variables):
    """Corre un script en un subproceso con su propio entorno MADRUGUE_*.

    Las variables se pasan como variables de entorno reales, así que
    ganan sobre cualquier .env del proyecto (``load_dotenv`` no pisa
    variables ya definidas) y configuran el mismo ``os.getenv`` que
    usa ``config/settings.py``.
    """

    entorno = dict(os.environ)
    entorno.update(variables)

    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=RAIZ,
        env=entorno,
        capture_output=True,
        text=True,
    )


def obtener_valores(variables):
    """Importa la configuración en un subproceso y devuelve su resumen."""

    proceso = correr_subproceso(SCRIPT_VALORES, variables)

    assert proceso.returncode == 0, (
        f"El subproceso falló al importar la configuración:\n"
        f"{proceso.stderr}"
    )

    return json.loads(proceso.stdout)


# ============================================================
# .env CON OTROS VALORES
# ============================================================

def test_el_env_cambia_ventanas_puntos_y_bonus():
    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    assert datos["ventanas"] == [
        "06:00:00",
        "07:30:00",
        "08:30:00",
        "11:00:00",
    ]

    assert datos["puntos"] == [50, 10, 2]

    assert datos["bonus"] == pytest.approx([0.5, 0.25])


def test_el_env_cambia_los_puntos_base_por_hora():
    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    assert datos["puntos_base"] == {
        "00:00": 0,
        "05:29": 0,
        "05:30": 0,
        "05:59": 0,
        "06:00": 50,
        "07:00": 50,
        "07:29": 50,
        "07:30": 10,
        "08:29": 10,
        "08:30": 2,
        "08:59": 2,
        "09:00": 2,
        "09:59": 2,
        "10:00": 2,
        "10:59": 2,
        "11:00": 0,
        "23:59": 0,
    }


def test_el_env_cambia_el_multiplicador():
    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    assert datos["multiplicador_apertura"] == pytest.approx(1.5)

    assert datos["multiplicador_cierre"] == pytest.approx(
        1.25,
        abs=0.001,
    )


def test_el_env_cambia_los_textos_de_horario():
    """Los textos de /madrugue, /madrugue_ayuda y /admin manualadd."""

    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    assert datos["horario_valido"] == "06:00 a 11:00"

    assert datos["texto_ventanas"] == (
        "**06:00 – 07:29** → 50 puntos\n"
        "**07:30 – 08:29** → 10 puntos\n"
        "**08:30 – 10:59** → 2 puntos\n"
        "**11:00 en adelante** → fuera de horario"
    )


# ============================================================
# .env CON LOS VALORES POR DEFECTO
# ============================================================

def test_valores_por_defecto_mantienen_la_puntuacion_historica():
    """05:30/07:00/09:00/10:00 con 100/25/5 y bonus 0.100 a 0.001."""

    datos = obtener_valores(ENTORNO_POR_DEFECTO)

    assert datos["ventanas"] == [
        "05:30:00",
        "07:00:00",
        "09:00:00",
        "10:00:00",
    ]

    assert datos["puntos"] == [100, 25, 5]

    assert datos["bonus"] == pytest.approx([0.100, 0.001])

    assert datos["puntos_base"] == {
        "00:00": 0,
        "05:29": 0,
        "05:30": 100,
        "05:59": 100,
        "06:00": 100,
        "07:00": 25,
        "07:29": 25,
        "07:30": 25,
        "08:29": 25,
        "08:30": 25,
        "08:59": 25,
        "09:00": 5,
        "09:59": 5,
        "10:00": 0,
        "10:59": 0,
        "11:00": 0,
        "23:59": 0,
    }

    assert datos["multiplicador_apertura"] == pytest.approx(1.100)

    assert datos["multiplicador_cierre"] == pytest.approx(
        1.001,
        abs=0.001,
    )

    assert datos["horario_valido"] == "05:30 a 10:00"

    assert datos["texto_ventanas"] == (
        "**05:30 – 06:59** → 100 puntos\n"
        "**07:00 – 08:59** → 25 puntos\n"
        "**09:00 – 09:59** → 5 puntos\n"
        "**10:00 en adelante** → fuera de horario"
    )


# ============================================================
# VALORES INVÁLIDOS
# ============================================================

@pytest.mark.parametrize(
    "variable,valor",
    [
        # Horas fuera del formato HH:MM.
        ("MADRUGUE_INICIO_100", "madrugón"),
        ("MADRUGUE_INICIO_25", "7:00"),
        ("MADRUGUE_INICIO_5", "9 "),
        ("MADRUGUE_FIN", "10:30:00"),
        ("MADRUGUE_FIN", "25:00"),
        ("MADRUGUE_FIN", ""),
        # Puntos que no son enteros o no son positivos.
        ("MADRUGUE_PUNTOS_100", "cien"),
        ("MADRUGUE_PUNTOS_25", "12.5"),
        ("MADRUGUE_PUNTOS_5", "-1"),
        # Bonus que no son decimales.
        ("MADRUGUE_BONUS_MAXIMO", "alto"),
        ("MADRUGUE_BONUS_MINIMO", "0,001"),
    ],
)
def test_valor_invalido_falla_al_arrancar(variable, valor):
    """El bot no arranca y el error nombra la variable culpable."""

    variables = dict(ENTORNO_ALTERNATIVO)
    variables[variable] = valor

    proceso = correr_subproceso(SCRIPT_ARRANQUE, variables)

    assert proceso.returncode != 0, (
        f"{variable}={valor} se aceptó al arrancar y debería ser inválido."
    )

    assert "Configuración inválida" in proceso.stderr
    assert variable in proceso.stderr


def test_ventanas_desordenadas_fallan_al_arrancar():
    variables = dict(ENTORNO_ALTERNATIVO)
    variables["MADRUGUE_INICIO_25"] = "05:00"

    proceso = correr_subproceso(SCRIPT_ARRANQUE, variables)

    assert proceso.returncode != 0
    assert "Configuración inválida" in proceso.stderr
    assert "MADRUGUE_INICIO_100 < MADRUGUE_INICIO_25" in proceso.stderr


def test_ventanas_repetidas_fallan_al_arrancar():
    variables = dict(ENTORNO_ALTERNATIVO)
    variables["MADRUGUE_INICIO_5"] = "07:30"

    proceso = correr_subproceso(SCRIPT_ARRANQUE, variables)

    assert proceso.returncode != 0
    assert "Configuración inválida" in proceso.stderr
    assert "sin repetirse" in proceso.stderr


def test_bonus_invertido_falla_al_arrancar():
    variables = dict(ENTORNO_ALTERNATIVO)
    variables["MADRUGUE_BONUS_MINIMO"] = "0.9"

    proceso = correr_subproceso(SCRIPT_ARRANQUE, variables)

    assert proceso.returncode != 0
    assert "Configuración inválida" in proceso.stderr
    assert "MADRUGUE_BONUS_MINIMO" in proceso.stderr
    assert "MADRUGUE_BONUS_MAXIMO" in proceso.stderr
