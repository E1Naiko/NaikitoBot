"""Lógica pura de Box.

Reglas de negocio que no tocan la base de datos ni Discord: precios, calidades,
formato de textos y cálculo de duraciones. Al ser funciones puras, se pueden
probar sin dobles ni fixtures.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from modules.box.constants import (
    EQUIPAMIENTO,
    MINUTOS_MAXIMO,
    MINUTOS_MINIMO,
)


# ============================================================
# PRECIOS
# ============================================================

def precio_mejora(precio_base: int, nivel: int) -> int:
    """Precio del siguiente nivel de una mejora: +25 % compuesto."""

    return math.ceil(precio_base * 2 ** nivel)


def precio_equipamiento(precio_base: int, nivel: int) -> int:
    """Precio de la siguiente pieza: se duplica en cada nivel."""

    return precio_base * (2 ** nivel)


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
# FORMATO
# ============================================================

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
