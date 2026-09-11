"""Pruebas de regresión del balance de Box configurado por .env.

Todo el balance de Box (precios de la tienda, lesiones, desafíos,
sponsors y estadísticas iniciales) se lee en ``config/settings.py``
desde variables ``BOX_*`` en el momento de la importación. Como el
proceso de pruebas ya tiene el módulo cargado con los valores por
defecto, estas pruebas corren un subproceso con su propio entorno para
reproducir lo que pasa al cambiar el .env y reiniciar el bot:

- otro juego de variables cambia precios, multiplicador, lesiones,
  desafíos, sponsors y estadísticas iniciales;
- los valores por defecto documentados en .env.example mantienen el
  balance histórico;
- un valor inválido impide arrancar con un error claro.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Configuración alternativa: sube el multiplicador de la tienda,
# encarece las mejoras, acorta la lesión, alarga el desafío y cambia
# la curva de sponsors.
ENTORNO_ALTERNATIVO = {
    "BOX_PRECIO_MULTIPLICADOR": "1.5",
    "BOX_PRECIO_MEJORA_CRECIMIENTO": "3.0",
    "BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO": "3.0",
    "BOX_PRECIO_MEJORA_ENTRENAMIENTO": "800",
    "BOX_PRECIO_EQUIPAMIENTO_CASCO": "1000",
    "BOX_PRECIO_SUMINISTRO_VIDA": "2000",
    "BOX_MEJORA_NIVEL_MAXIMO": "15",
    "BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL": "7",
    "BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL": "9",
    "BOX_MINUTOS_MAXIMO": "720",
    "BOX_LESION_HORAS": "2.5",
    "BOX_LESION_PROBABILIDAD_POR_HORA": "2.0",
    "BOX_LESION_PROBABILIDAD_MAXIMA": "80",
    "BOX_LESION_DECAIMIENTO_POR_HORA": "0.5",
    "BOX_DESAFIO_VENTANA_HORAS": "0.5",
    "BOX_DESAFIO_DURACION_HORAS": "1.5",
    "BOX_DESAFIO_EXP_SPARRING": "8",
    "BOX_DESAFIO_EXP_PELEA": "12",
    "BOX_DESAFIO_RECOMPENSA_POR_MEJORA": "9",
    "BOX_PROMOCION_PROBABILIDAD": "1=50,3=75,6=100",
    "BOX_SPONSOR_PROBABILIDAD": "redes=40,radio=30,equipamiento=20,medico=10",
    "BOX_SPONSOR_DURACION_DIAS": "redes=3,radio=3,equipamiento=5,medico=15",
    "BOX_SPONSOR_PAGO": "redes=750,radio=1500",
    "BOX_SPONSOR_MAXIMO": "redes=4,radio=4",
    "BOX_SPONSOR_CICLO_PAGO_HORAS": "12",
    "BOX_MEDICO_CICLO_HORAS": "6",
    "BOX_SPONSOR_EQUIPAMIENTO_BONUS": "25",
    "BOX_MEDICO_REDUCCION": "75",
    "BOX_VIDA_INICIAL": "50",
    "BOX_CANSANCIO_INICIAL": "30",
    "BOX_DANO_INICIAL": "2",
    "BOX_DANO_MAXIMO": "40",
    "BOX_DEFENSA_INICIAL": "3",
    "BOX_DEFENSA_MAXIMO": "35",
}

# Los valores por defecto documentados en .env.example: tienen que
# mantener el balance histórico.
ENTORNO_POR_DEFECTO = {
    "BOX_EXPERIENCIA_POR_MINUTO": "10",
    "BOX_DINERO_POR_MINUTO": "100",
    "BOX_MINUTOS_MINIMO": "1",
    "BOX_MINUTOS_MAXIMO": "1440",
    "BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL": "5",
    "BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL": "50",
    "BOX_MEJORA_NIVEL_MAXIMO": "10",
    "BOX_PRECIO_MULTIPLICADOR": "1.0",
    "BOX_PRECIO_MEJORA_CRECIMIENTO": "1.25",
    "BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO": "2.0",
    "BOX_PRECIO_MEJORA_ENTRENAMIENTO": "1000",
    "BOX_PRECIO_MEJORA_TRABAJO": "1000",
    "BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO": "10000",
    "BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS": "50000",
    "BOX_PRECIO_SUMINISTRO_VIDA": "1500",
    "BOX_PRECIO_SUMINISTRO_CANSANCIO": "1500",
    "BOX_PRECIO_SUMINISTRO_DEFENSA": "3000",
    "BOX_PRECIO_SUMINISTRO_LESION": "60000",
    "BOX_PRECIO_EQUIPAMIENTO_CASCO": "1000",
    "BOX_PRECIO_EQUIPAMIENTO_GUANTES": "1000",
    "BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL": "600",
    "BOX_PRECIO_EQUIPAMIENTO_SHORT": "600",
    "BOX_PRECIO_EQUIPAMIENTO_BOTAS": "800",
    "BOX_LESION_HORAS": "3",
    "BOX_LESION_PROBABILIDAD_POR_HORA": "1.0",
    "BOX_LESION_PROBABILIDAD_MAXIMA": "100",
    "BOX_LESION_DECAIMIENTO_POR_HORA": "0.01",
    "BOX_DESAFIO_VENTANA_HORAS": "1",
    "BOX_DESAFIO_DURACION_HORAS": "1",
    "BOX_DESAFIO_EXP_SPARRING": "5",
    "BOX_DESAFIO_EXP_PELEA": "10",
    "BOX_DESAFIO_RECOMPENSA_POR_MEJORA": "5",
    "BOX_PROMOCION_PROBABILIDAD": "1=5,2=10,4=20,8=40,12=60,16=80,24=100",
    "BOX_SPONSOR_PROBABILIDAD": "redes=50,radio=30,equipamiento=15,medico=5",
    "BOX_SPONSOR_DURACION_DIAS": "redes=7,radio=7,equipamiento=14,medico=30",
    "BOX_SPONSOR_PAGO": "redes=500,radio=1000",
    "BOX_SPONSOR_MAXIMO": "redes=10,radio=10",
    "BOX_SPONSOR_CICLO_PAGO_HORAS": "24",
    "BOX_MEDICO_CICLO_HORAS": "24",
    "BOX_SPONSOR_EQUIPAMIENTO_BONUS": "10",
    "BOX_MEDICO_REDUCCION": "50",
    "BOX_VIDA_INICIAL": "32",
    "BOX_CANSANCIO_INICIAL": "25",
    "BOX_DANO_INICIAL": "1",
    "BOX_DANO_MAXIMO": "25",
    "BOX_DEFENSA_INICIAL": "1",
    "BOX_DEFENSA_MAXIMO": "22",
}

# Importa la configuración, los catálogos y la lógica de Box en un
# proceso limpio y devuelve todo lo relevante como JSON.
SCRIPT_VALORES = """
import json

import config
from modules.box import constants
from modules.box import database
from modules.box.logic import (
    precio_equipamiento,
    precio_mejora,
    texto_horas,
)

curva = database.PROBABILIDAD_PROMOCION

print(json.dumps({
    "limites_minutos": [
        constants.MINUTOS_MINIMO,
        constants.MINUTOS_MAXIMO,
    ],
    "multiplicador": config.BOX_PRECIO_MULTIPLICADOR,
    "crecimientos": [
        config.BOX_PRECIO_MEJORA_CRECIMIENTO,
        config.BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO,
    ],
    "precio_mejoras": {
        clave: [mejora["precio"], mejora["maximo"]]
        for clave, mejora in constants.MEJORAS.items()
    },
    "descripcion_mejoras": [
        constants.MEJORAS["entrenamiento"]["descripcion"],
        constants.MEJORAS["trabajo"]["descripcion"],
    ],
    "precio_tratamientos": {
        clave: tratamiento["precio"]
        for clave, tratamiento in constants.TRATAMIENTOS.items()
    },
    "precio_suministros": {
        clave: tipo["precio"]
        for clave, tipo in constants.TIPOS_SUMINISTRO.items()
    },
    "precio_equipamiento": {
        clave: pieza["precio_base"]
        for clave, pieza in constants.EQUIPAMIENTO.items()
    },
    "precios_por_nivel": [
        precio_mejora(constants.MEJORAS["entrenamiento"]["precio"], 2),
        precio_equipamiento(constants.EQUIPAMIENTO["casco"]["precio_base"], 1),
    ],
    "lesion": [
        config.BOX_LESION_HORAS,
        config.BOX_LESION_PROBABILIDAD_POR_HORA,
        config.BOX_LESION_PROBABILIDAD_MAXIMA,
        config.BOX_LESION_DECAIMIENTO_POR_HORA,
    ],
    "texto_lesion": texto_horas(config.BOX_LESION_HORAS),
    "desafio": [
        config.BOX_DESAFIO_DURACION_HORAS,
        config.BOX_DESAFIO_EXP_SPARRING,
        config.BOX_DESAFIO_EXP_PELEA,
        config.BOX_DESAFIO_RECOMPENSA_POR_MEJORA,
    ],
    "ventana_desafio": config.BOX_DESAFIO_VENTANA_HORAS,
    "texto_ventana": texto_horas(config.BOX_DESAFIO_VENTANA_HORAS),
    "ventana_desafio_segundos": (
        config.BOX_DESAFIO_VENTANA_HORAS * 3600
    ),
    "texto_desafio": texto_horas(config.BOX_DESAFIO_DURACION_HORAS),
    "duracion_desafio_segundos": (
        config.BOX_DESAFIO_DURACION_HORAS * 3600
    ),
    "curva_promocion": [[horas, prob] for horas, prob in curva],
    "probabilidad_promocion": [
        database._probabilidad_promocion(minutos)
        for minutos in (30, 120, 720)
    ],
    "sponsors": {
        "probabilidad": config.BOX_SPONSOR_PROBABILIDAD,
        "duracion_dias": config.BOX_SPONSOR_DURACION_DIAS,
        "pago": config.BOX_SPONSOR_PAGO,
        "maximo": config.BOX_SPONSOR_MAXIMO,
        "ciclo_pago_horas": config.BOX_SPONSOR_CICLO_PAGO_HORAS,
        "ciclo_medico_horas": config.BOX_MEDICO_CICLO_HORAS,
        "bonus_equipamiento": config.BOX_SPONSOR_EQUIPAMIENTO_BONUS,
        "reduccion_medico": config.BOX_MEDICO_REDUCCION,
    },
    "stats_iniciales": [
        config.BOX_VIDA_INICIAL,
        config.BOX_CANSANCIO_INICIAL,
        config.BOX_DANO_INICIAL,
        config.BOX_DANO_MAXIMO,
        config.BOX_DEFENSA_INICIAL,
        config.BOX_DEFENSA_MAXIMO,
    ],
}))
"""

SCRIPT_ARRANQUE = "import config"


def correr_subproceso(script, variables):
    """Corre un script en un subproceso con su propio entorno BOX_*.

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

def test_el_multiplicador_encarece_toda_la_tienda():
    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    # 800 x 1.5 = 1200 para la mejora de entrenamiento; la de trabajo
    # mantiene su precio base de 1000 x 1.5 = 1500.
    assert datos["precio_mejoras"]["entrenamiento"] == [1200, 15]
    assert datos["precio_mejoras"]["trabajo"] == [1500, 15]

    # 2000 x 1.5 = 3000 para el suministro de vida.
    assert datos["precio_suministros"]["vida"] == 3000

    # 1000 x 1.5 = 1500 de base y x3 por nivel de calidad.
    assert datos["precio_equipamiento"]["casco"] == 1500
    assert datos["precios_por_nivel"] == [
        1200 * 3 ** 2,  # mejora: crecimiento compuesto sobre el precio ya multiplicado
        1500 * 3,  # equipamiento: siguiente calidad
    ]


def test_el_env_cambia_lesiones_desafios_y_sponsors():
    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    assert datos["limites_minutos"] == [1, 720]

    assert datos["lesion"] == pytest.approx([2.5, 2.0, 80, 0.5])
    assert datos["texto_lesion"] == "2.5 horas"

    assert datos["desafio"] == [1.5, 8, 12, 9]
    assert datos["ventana_desafio"] == 0.5
    assert datos["texto_ventana"] == "0.5 horas"
    assert datos["ventana_desafio_segundos"] == 1800
    assert datos["texto_desafio"] == "1.5 horas"
    assert datos["duracion_desafio_segundos"] == 5400

    assert datos["curva_promocion"] == [[1.0, 50.0], [3.0, 75.0], [6.0, 100.0]]

    # 30 minutos -> primer punto; 2 horas -> interpolado; 12 horas -> último.
    assert datos["probabilidad_promocion"] == pytest.approx([50.0, 62.5, 100.0])

    assert datos["sponsors"] == {
        "probabilidad": {
            "redes": 40.0,
            "radio": 30.0,
            "equipamiento": 20.0,
            "medico": 10.0,
        },
        "duracion_dias": {
            "redes": 3.0,
            "radio": 3.0,
            "equipamiento": 5.0,
            "medico": 15.0,
        },
        "pago": {"redes": 750, "radio": 1500},
        "maximo": {"redes": 4, "radio": 4},
        "ciclo_pago_horas": 12.0,
        "ciclo_medico_horas": 6.0,
        "bonus_equipamiento": 25.0,
        "reduccion_medico": 75.0,
    }


def test_el_env_cambia_las_descripciones_de_la_tienda():
    """La descripción de cada mejora refleja su ganancia configurada."""

    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    assert datos["descripcion_mejoras"] == [
        "+7 EXP por minuto de entrenamiento",
        "+9 dinero por minuto de trabajo",
    ]


def test_el_env_cambia_las_estadisticas_iniciales():
    datos = obtener_valores(ENTORNO_ALTERNATIVO)

    assert datos["stats_iniciales"] == [50, 30, 2, 40, 3, 35]


# ============================================================
# .env CON LOS VALORES POR DEFECTO
# ============================================================

def test_valores_por_defecto_mantienen_el_balance_historico():
    datos = obtener_valores(ENTORNO_POR_DEFECTO)

    assert datos["limites_minutos"] == [1, 1440]

    assert datos["multiplicador"] == 1.0
    assert datos["crecimientos"] == pytest.approx([1.25, 2.0])

    assert datos["precio_mejoras"] == {
        "entrenamiento": [1000, 10],
        "trabajo": [1000, 10],
    }

    assert datos["precio_tratamientos"] == {
        "fisioterapeutico": 10000,
        "cinco_estrellas": 50000,
    }

    assert datos["precio_suministros"] == {
        "vida": 1500,
        "cansancio": 1500,
        "defensa": 3000,
        "lesion": 60000,
    }

    assert datos["precio_equipamiento"] == {
        "casco": 1000,
        "guantes": 1000,
        "protector_bucal": 600,
        "short": 600,
        "botas": 800,
    }

    assert datos["precios_por_nivel"] == [1563, 2000]

    assert datos["lesion"] == pytest.approx([3.0, 1.0, 100.0, 0.01])
    assert datos["texto_lesion"] == "3 horas"

    assert datos["desafio"] == [1.0, 5, 10, 5]
    assert datos["ventana_desafio"] == 1.0
    assert datos["texto_ventana"] == "1 hora"
    assert datos["ventana_desafio_segundos"] == 3600
    assert datos["texto_desafio"] == "1 hora"
    assert datos["duracion_desafio_segundos"] == 3600

    assert datos["curva_promocion"] == [
        [1.0, 5.0],
        [2.0, 10.0],
        [4.0, 20.0],
        [8.0, 40.0],
        [12.0, 60.0],
        [16.0, 80.0],
        [24.0, 100.0],
    ]

    assert datos["probabilidad_promocion"] == pytest.approx(
        [5.0, 10.0, 60.0]
    )

    assert datos["sponsors"]["probabilidad"] == {
        "redes": 50.0,
        "radio": 30.0,
        "equipamiento": 15.0,
        "medico": 5.0,
    }
    assert datos["sponsors"]["duracion_dias"] == {
        "redes": 7.0,
        "radio": 7.0,
        "equipamiento": 14.0,
        "medico": 30.0,
    }
    assert datos["sponsors"]["pago"] == {"redes": 500, "radio": 1000}
    assert datos["sponsors"]["maximo"] == {"redes": 10, "radio": 10}
    assert datos["sponsors"]["ciclo_pago_horas"] == 24.0
    assert datos["sponsors"]["ciclo_medico_horas"] == 24.0
    assert datos["sponsors"]["bonus_equipamiento"] == 10.0
    assert datos["sponsors"]["reduccion_medico"] == 50.0

    assert datos["stats_iniciales"] == [32, 25, 1, 25, 1, 22]


# ============================================================
# VALORES INVÁLIDOS
# ============================================================

@pytest.mark.parametrize(
    "variable,valor",
    [
        # Multiplicador y crecimientos de la tienda.
        ("BOX_PRECIO_MULTIPLICADOR", "0"),
        ("BOX_PRECIO_MULTIPLICADOR", "-1"),
        ("BOX_PRECIO_MULTIPLICADOR", "gratis"),
        ("BOX_PRECIO_MEJORA_CRECIMIENTO", "0.5"),
        ("BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO", "0"),
        ("BOX_MEJORA_NIVEL_MAXIMO", "0"),
        # Precios negativos o no numéricos.
        ("BOX_PRECIO_MEJORA_ENTRENAMIENTO", "-5"),
        ("BOX_PRECIO_SUMINISTRO_LESION", "mucho"),
        # Límites de minutos desordenados.
        ("BOX_MINUTOS_MAXIMO", "0"),
        ("BOX_MINUTOS_MINIMO", "2000"),
        # Lesiones.
        ("BOX_LESION_HORAS", "0"),
        ("BOX_LESION_PROBABILIDAD_POR_HORA", "150"),
        ("BOX_LESION_PROBABILIDAD_MAXIMA", "-1"),
        ("BOX_LESION_DECAIMIENTO_POR_HORA", "-0.01"),
        # Desafíos.
        ("BOX_DESAFIO_VENTANA_HORAS", "0"),
        ("BOX_DESAFIO_DURACION_HORAS", "0"),
        ("BOX_DESAFIO_EXP_SPARRING", "-5"),
        ("BOX_DESAFIO_RECOMPENSA_POR_MEJORA", "cinco"),
        # Curva de promoción.
        ("BOX_PROMOCION_PROBABILIDAD", "1=5"),
        ("BOX_PROMOCION_PROBABILIDAD", "1=alto,3=bajo"),
        ("BOX_PROMOCION_PROBABILIDAD", "0=5,2=10"),
        ("BOX_PROMOCION_PROBABILIDAD", "1=150,3=200"),
        ("BOX_PROMOCION_PROBABILIDAD", "sin igualdades"),
        # Mapas de sponsors.
        ("BOX_SPONSOR_PROBABILIDAD", "redes=50"),
        ("BOX_SPONSOR_PROBABILIDAD", "redes=50,radio=30,equipamiento=15,medico=200"),
        ("BOX_SPONSOR_DURACION_DIAS", "redes=0,radio=7,equipamiento=14,medico=30"),
        ("BOX_SPONSOR_DURACION_DIAS", "redes=7,radio=7,equipamiento=14"),
        ("BOX_SPONSOR_PAGO", "futbol=500,radio=1000"),
        ("BOX_SPONSOR_MAXIMO", "redes=-1,radio=10"),
        # Ciclos y bonus.
        ("BOX_SPONSOR_CICLO_PAGO_HORAS", "0"),
        ("BOX_MEDICO_CICLO_HORAS", "0"),
        ("BOX_SPONSOR_EQUIPAMIENTO_BONUS", "-10"),
        ("BOX_MEDICO_REDUCCION", "150"),
        # Estadísticas iniciales.
        ("BOX_VIDA_INICIAL", "0"),
        ("BOX_CANSANCIO_INICIAL", "-5"),
        ("BOX_DANO_INICIAL", "30"),
        ("BOX_DEFENSA_INICIAL", "0"),
    ],
)
def test_valor_invalido_falla_al_arrancar(variable, valor):
    """El bot no arranca y el error nombra la variable culpable."""

    variables = dict(ENTORNO_POR_DEFECTO)
    variables[variable] = valor

    proceso = correr_subproceso(SCRIPT_ARRANQUE, variables)

    assert proceso.returncode != 0, (
        f"{variable}={valor} se aceptó al arrancar y debería ser inválido."
    )

    assert "Configuración inválida" in proceso.stderr
    assert variable in proceso.stderr


def test_mapa_con_valor_no_numerico_falla_al_arrancar():
    variables = dict(ENTORNO_POR_DEFECTO)
    variables["BOX_SPONSOR_PROBABILIDAD"] = (
        "redes=mitad,radio=30,equipamiento=15,medico=5"
    )

    proceso = correr_subproceso(SCRIPT_ARRANQUE, variables)

    assert proceso.returncode != 0
    assert "Configuración inválida" in proceso.stderr
    assert "BOX_SPONSOR_PROBABILIDAD" in proceso.stderr
