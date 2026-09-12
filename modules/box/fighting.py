"""Pelea del desafío (``/box desafio``): reglas de balance y planificación.

El motor de simulación está en :mod:`modules.box.combate` y la traducción de
sus eventos a frases en :mod:`modules.box.narracion`. Acá solamente se arma
el ``Reglas`` con la configuración de ``BOX_COMBATE_*`` y se fija qué hace
distinta a una pelea de un sparring: hay nocaut, hay corte del corner y hay
ganador (que es el que ya sorteó ``aceptar_desafio``).
"""

from dataclasses import replace

from config import (
    BOX_COMBATE_COMPRESION,
    BOX_COMBATE_DIALOGOS_POR_ROUND,
    BOX_COMBATE_ESCALA_DANO,
    BOX_COMBATE_KO_BASE,
    BOX_COMBATE_KO_DESDE_ASALTO,
    BOX_COMBATE_KO_POR_BRECHA,
    BOX_COMBATE_NEUTRALES,
    BOX_COMBATE_PROB_PISO,
    BOX_COMBATE_PROB_TOPE,
    BOX_COMBATE_ROUNDS_MAXIMO,
    BOX_COMBATE_ROUNDS_MINIMO,
    BOX_COMBATE_SUELO_EXP,
    BOX_VIDA_INICIAL,
)

from modules.box.combate import (
    METODO_DECISION,
    METODO_KO,
    Plan,
    Reglas,
    asaltos_programados,
    planificar,
    probabilidad_victoria,
)


REGLAS_PELEA = Reglas(
    rounds_maximo=BOX_COMBATE_ROUNDS_MAXIMO,
    rounds_minimo=BOX_COMBATE_ROUNDS_MINIMO,
    dialogos_por_round=BOX_COMBATE_DIALOGOS_POR_ROUND,
    # Un asalto de pelea tiene de 3 a 6 golpes útiles: la cantidad es
    # aleatoria para que los asaltos no se lean todos iguales.
    intercambios_min=3,
    intercambios_max=6,
    neutrales=BOX_COMBATE_NEUTRALES,
    prob_piso=BOX_COMBATE_PROB_PISO,
    prob_tope=BOX_COMBATE_PROB_TOPE,
    suelo_exp=BOX_COMBATE_SUELO_EXP,
    compresion=BOX_COMBATE_COMPRESION,
    ko_base=BOX_COMBATE_KO_BASE,
    ko_por_brecha=BOX_COMBATE_KO_POR_BRECHA,
    ko_desde_asalto=BOX_COMBATE_KO_DESDE_ASALTO,
    # Con la vida por debajo de este valor el corner puede parar la pelea.
    escala_asaltos=BOX_COMBATE_ESCALA_DANO,
    vida_para_corte=max(4, round(BOX_VIDA_INICIAL * 0.35)),
    admite_ganador=True,
    puede_cortarse=True,
)


def planificar_pelea(
    *,
    nombres: tuple[str, str],
    experiencia: tuple[int, int],
    vida_maxima: tuple[int, int],
    dano: tuple[int, int],
    defensa: tuple[int, int],
    semilla: int,
    ganador_forzado: int | None = None,
    reglas: Reglas | None = None,
    fatiga: tuple[float, float] = (1.0, 1.0),
    bono_fuerza: tuple[float, float] = (1.0, 1.0),
) -> Plan:
    """Planifica una pelea a partir del estado actual de los dos peleadores.

    ``ganador_forzado`` recibe el ``ganador_id`` que ya sorteó
    ``aceptar_desafio`` traducido a índice (``0`` retador, ``1``
    contrincante), para que la narración y la recompensa nunca se
    contradigan.
    """

    return planificar(
        modo="FIGHTING",
        nombres=nombres,
        experiencia=experiencia,
        vida_maxima=vida_maxima,
        dano=dano,
        defensa=defensa,
        reglas=reglas or REGLAS_PELEA,
        semilla=semilla,
        ganador_forzado=ganador_forzado,
        fatiga=fatiga,
        bono_fuerza=bono_fuerza,
    )


def regalar_reglas(**cambios) -> Reglas:
    """Copia las reglas de la pelea con cambios, para pruebas y eventos."""

    return replace(REGLAS_PELEA, **cambios)


__all__ = [
    "METODO_DECISION",
    "METODO_KO",
    "REGLAS_PELEA",
    "Plan",
    "asaltos_programados",
    "planificar_pelea",
    "probabilidad_victoria",
    "regalar_reglas",
]
