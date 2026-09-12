"""Sparring (``/box sparring``): reglas de balance y planificación.

Comparte el motor de :mod:`modules.box.combate` con la pelea y cambia solo
el balance. Las diferencias no son cosméticas:

* no hay nocaut ni corte del corner (``puede_cortarse=False``), porque un
  sparring se para por seguridad, no por un golpe;
* no hay ganador: el combate queda en ``ganador=-1`` y el plan solo deja un
  "destacado" para el comentario del corner, que no se escribe en
  ``box_desafios_historial`` ni cobra premio;
* la diferencia de nivel **no acorta** la sesión tanto como en la pelea: en
  un sparring el novato aprende más cuanto más tiempo lo mete el DT, así que
  el piso de asaltos es alto y la pendiente suave.
"""

from dataclasses import replace

from config import (
    BOX_COMBATE_COMPRESION,
    BOX_COMBATE_DIALOGOS_POR_ROUND,
    BOX_COMBATE_ESCALA_DANO,
    BOX_COMBATE_NEUTRALES,
    BOX_COMBATE_PROB_PISO,
    BOX_COMBATE_PROB_TOPE,
    BOX_COMBATE_ROUNDS_MAXIMO,
    BOX_COMBATE_SUELO_EXP,
    BOX_VIDA_INICIAL,
)

from modules.box.combate import (
    METODO_ENTRENAMIENTO,
    Plan,
    Reglas,
    planificar,
    probabilidad_victoria,
)


REGLAS_SPARRING = Reglas(
    rounds_maximo=min(BOX_COMBATE_ROUNDS_MAXIMO, 7),
    # Piso alto a propósito: cortar un sparring por paliza le quita
    # justamente el entrenamiento al que más lo necesita.
    rounds_minimo=5,
    dialogos_por_round=BOX_COMBATE_DIALOGOS_POR_ROUND,
    # Menos intercambios y más comentario: es una sesión técnica, con el DT
    # corrigiendo, no una pelea.
    intercambios_min=2,
    intercambios_max=4,
    neutrales=min(0.6, BOX_COMBATE_NEUTRALES + 0.15),
    prob_piso=BOX_COMBATE_PROB_PISO,
    prob_tope=BOX_COMBATE_PROB_TOPE,
    suelo_exp=BOX_COMBATE_SUELO_EXP,
    compresion=BOX_COMBATE_COMPRESION,
    ko_base=0.0,
    ko_por_brecha=0.0,
    ko_desde_asalto=99,
    escala_asaltos=BOX_COMBATE_ESCALA_DANO,
    vida_para_corte=max(4, round(BOX_VIDA_INICIAL * 0.35)),
    admite_ganador=False,
    puede_cortarse=False,
)


def planificar_sparring(
    *,
    nombres: tuple[str, str],
    experiencia: tuple[int, int],
    vida_maxima: tuple[int, int],
    dano: tuple[int, int],
    defensa: tuple[int, int],
    semilla: int,
    reglas: Reglas | None = None,
    fatiga: tuple[float, float] = (1.0, 1.0),
    bono_fuerza: tuple[float, float] = (1.0, 1.0),
) -> Plan:
    """Planifica una sesión de sparring entre dos peleadores."""

    return planificar(
        modo="SPARRING",
        nombres=nombres,
        experiencia=experiencia,
        vida_maxima=vida_maxima,
        dano=dano,
        defensa=defensa,
        reglas=reglas or REGLAS_SPARRING,
        semilla=semilla,
        fatiga=fatiga,
        bono_fuerza=bono_fuerza,
        # En el sparring nadie gana: se sortea el resultado para repartir
        # los asaltos, pero el plan queda sin ganador declarado.
        ganador_forzado=None,
    )


def regalar_reglas(**cambios) -> Reglas:
    """Copia las reglas del sparring con cambios, para pruebas y eventos."""

    return replace(REGLAS_SPARRING, **cambios)


__all__ = [
    "METODO_ENTRENAMIENTO",
    "REGLAS_SPARRING",
    "Plan",
    "planificar_sparring",
    "probabilidad_victoria",
    "regalar_reglas",
]
