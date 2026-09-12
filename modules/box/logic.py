"""Lógica pura de Box.

Reglas de negocio que no tocan la base de datos ni Discord: precios, calidades,
formato de textos y cálculo de duraciones. Al ser funciones puras, se pueden
probar sin dobles ni fixtures.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from config import (
    BOX_COMBATE_EQUIPO_ACTIVO,
    BOX_COMBATE_EQUIPO_FUERZA,
    BOX_COMBATE_EQUIPO_POR_NIVEL,
    BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO,
    BOX_PRECIO_MEJORA_CRECIMIENTO,
)

from modules.box.constants import (
    EQUIPAMIENTO,
    EQUIPAMIENTO_COMBATE,
    MINUTOS_MAXIMO,
    MINUTOS_MINIMO,
    NIVEL_MAXIMO_EQUIPAMIENTO,
)


# ============================================================
# PRECIOS
# ============================================================

def precio_mejora(precio_base: int, nivel: int) -> int:
    """Precio del siguiente nivel de una mejora.

    Crece un ``BOX_PRECIO_MEJORA_CRECIMIENTO`` compuesto por nivel
    (con el valor por defecto, +25 %).
    """

    return math.ceil(precio_base * BOX_PRECIO_MEJORA_CRECIMIENTO ** nivel)


def precio_equipamiento(precio_base: int, nivel: int) -> int:
    """Precio de la siguiente pieza de equipamiento.

    Se multiplica por ``BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO`` en cada
    nivel (con el valor por defecto, se duplica).
    """

    return math.ceil(precio_base * BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO ** nivel)


# ============================================================
# EQUIPAMIENTO
# ============================================================

def calidad_equipamiento(tipo: str, nivel: int) -> str:
    """Traduce el nivel numérico de una pieza a su nombre de calidad."""

    return EQUIPAMIENTO[tipo]["calidades"][nivel]


def es_nivel_maximo(tipo: str, nivel: int) -> bool:
    """Indica si la pieza ya está en su última calidad."""

    return nivel >= len(EQUIPAMIENTO[tipo]["calidades"]) - 1


# ============================================================
# COMBATE
# ============================================================

def estadisticas_de_combate(
    base,
    niveles,
    *,
    activo=BOX_COMBATE_EQUIPO_ACTIVO,
    por_nivel=BOX_COMBATE_EQUIPO_POR_NIVEL,
    fuerza_por_nivel=BOX_COMBATE_EQUIPO_FUERZA,
):
    """Estadísticas efectivas de un peleador, con su equipamiento aplicado.

    ``base`` es lo que dice ``box_equipo`` (``vida_maxima``, ``dano``,
    ``defensa``) y ``niveles`` los niveles de cada pieza. Se devuelven los
    mismos tres números más dos derivados que entiende el motor:

    - ``fatiga``: con cuánto se acumula el propio cansancio por asalto. Menos
      cansancio propio es recibir menos daño con el paso de los rounds, porque
      el motor castiga al que ya no mueve la cabeza.
    - ``fuerza``: cuánto pesa el peleador en el sorteo de la probabilidad. Es
      lo único del equipamiento que puede inclinar *quién* gana; el resto
      inclina *cómo* gana (por nocaut o a los puntos, y en qué asalto).

    El techo de niveles es ``NIVEL_MAXIMO_EQUIPAMIENTO`` por pieza, así el
    bonus máximo queda acotado aunque alguien tenga ``puntos_habilidad`` de
    sobra: equipo Legendario completo contra alguien con la mitad de
    experiencia no convierte al peor en favorito, solamente en un rival
    incómodo.
    """

    salida = {
        "vida_maxima": max(1, int(base.get("vida_maxima") or 1)),
        "dano": max(1, int(base.get("dano") or 1)),
        "defensa": max(1, int(base.get("defensa") or 1)),
        "fatiga": 1.0,
        "fuerza": 1.0,
    }

    if not activo:
        return salida

    niveles_totales = 0

    for tipo, (estadistica, peso) in EQUIPAMIENTO_COMBATE.items():
        nivel = int(niveles.get(tipo) or 0)
        nivel = max(0, min(nivel, NIVEL_MAXIMO_EQUIPAMIENTO))

        if nivel == 0:
            continue

        factor = 1 + por_nivel * peso * nivel

        if estadistica == "fatiga":
            # Un peleador con buen calzado no deja de cansarse nunca: se le
            # pone un piso para que las botas no lo vuelvan inmune al 12º
            # asalto.
            salida["fatiga"] = max(0.4, salida["fatiga"] * factor)
        else:
            salida[estadistica] = max(
                1, round(salida[estadistica] * factor)
            )

        niveles_totales += nivel

    salida["fuerza"] = 1 + fuerza_por_nivel * niveles_totales

    return salida


# ============================================================
# FORMATO
# ============================================================

def texto_horas(horas: float) -> str:
    """Formatea una cantidad de horas como «1 hora» o «1.5 horas»."""

    valor = f"{horas:g}"
    unidad = "hora" if valor == "1" else "horas"

    return f"{valor} {unidad}"


def formato_ratio(ratio: float) -> str:
    """Formatea el ratio de desafíos; infinito se muestra como ∞."""

    if ratio == float("inf"):
        return "∞"

    return f"{ratio:.2f}"


# ============================================================
# DURACIÓN DE LAS ACCIONES
# ============================================================

@dataclass(frozen=True)
class Duracion:
    """Duración resuelta de una acción."""

    minutos: int
    finaliza_en: datetime


def resolver_duracion(
    minutos: int | None,
    hasta: str | None,
    iniciado_en: datetime,
) -> tuple[Duracion | None, str | None]:
    """Resuelve minutos o una hora HH:MM a una duración concreta.

    Devuelve ``(Duracion, None)`` si todo es válido, o ``(None, motivo)`` con
    uno de: ``ambas``, ``formato_hora``, ``falta_duracion``, ``fuera_rango``.
    """

    if minutos is not None and hasta is not None:
        return None, "ambas"

    if hasta is not None:
        try:
            hora_fin = datetime.strptime(hasta.strip(), "%H:%M").time()
        except ValueError:
            return None, "formato_hora"

        finaliza_en = datetime.combine(
            iniciado_en.date(),
            hora_fin,
            tzinfo=iniciado_en.tzinfo,
        )
        if finaliza_en <= iniciado_en:
            finaliza_en += timedelta(days=1)

        minutos = math.ceil(
            (finaliza_en - iniciado_en).total_seconds() / 60
        )
    elif minutos is None:
        return None, "falta_duracion"
    else:
        finaliza_en = iniciado_en + timedelta(minutes=minutos)

    if not MINUTOS_MINIMO <= minutos <= MINUTOS_MAXIMO:
        return None, "fuera_rango"

    return Duracion(minutos=minutos, finaliza_en=finaliza_en), None
