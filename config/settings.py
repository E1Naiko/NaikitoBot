import os
import re
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


__all__ = [
    "PREFIX",
    "TIMEZONE",
    "DATABASE",
    "MADRUGUE_INICIO_100",
    "MADRUGUE_INICIO_25",
    "MADRUGUE_INICIO_5",
    "MADRUGUE_FIN",
    "MADRUGUE_PUNTOS_100",
    "MADRUGUE_PUNTOS_25",
    "MADRUGUE_PUNTOS_5",
    "MADRUGUE_BONUS_MAXIMO",
    "MADRUGUE_BONUS_MINIMO",
    "ADMIN_USER_IDS",
    "GUILD_ID",
    "GENERAL_CHANNEL_IDS",
    "MADRUGUE_CHANNEL_IDS",
    "BOX_CHANNEL_IDS",
    "SSF_CANALES_ID",
    "SSF_FECHA_INICIO",
    "SSF_FECHA_FIN",
    "BOX_EXPERIENCIA_POR_MINUTO",
    "BOX_DINERO_POR_MINUTO",
]


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# LECTURA Y VALIDACIÓN DE VARIABLES
# ============================================================

def _leer_hora(nombre, defecto):
    """Lee una variable ``HH:MM`` y falla con un error claro si no valida.

    El formato es estricto: dos dígitos para la hora, dos para los
    minutos (``05:30`` sí, ``5:30`` no).
    """

    valor = os.getenv(nombre, defecto).strip()

    hora = None

    if re.fullmatch("[0-9]{2}:[0-9]{2}", valor):
        try:
            hora = datetime.strptime(
                valor,
                "%H:%M",
            ).time()

        except ValueError:
            hora = None

    if hora is None:
        raise RuntimeError(
            f"Configuración inválida: {nombre} debe ser una hora en "
            f"formato HH:MM (por ejemplo 05:30), pero se recibió "
            f"'{valor}'."
        )

    return hora


def _leer_entero(nombre, defecto):
    """Lee una variable entera y falla con un error claro si no valida."""

    valor = os.getenv(nombre, str(defecto)).strip()

    try:
        return int(valor)

    except ValueError:
        raise RuntimeError(
            f"Configuración inválida: {nombre} debe ser un número "
            f"entero (por ejemplo {defecto}), pero se recibió "
            f"'{valor}'."
        ) from None


def _leer_decimal(nombre, defecto):
    """Lee una variable decimal y falla con un error claro si no valida."""

    valor = os.getenv(nombre, str(defecto)).strip()

    try:
        return float(valor)

    except ValueError:
        raise RuntimeError(
            f"Configuración inválida: {nombre} debe ser un número "
            f"decimal (por ejemplo {defecto}), pero se recibió "
            f"'{valor}'."
        ) from None


def _comprobar(valida, detalle):
    """Aborta el arranque con un error claro si no se cumple algo."""

    if not valida:
        raise RuntimeError(
            f"Configuración inválida: {detalle}"
        )


def _hhmm(hora: time) -> str:
    return hora.strftime("%H:%M")


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

PREFIX = "$!"

TIMEZONE = ZoneInfo(
    os.getenv(
        "TIMEZONE",
        "America/Argentina/Buenos_Aires",
    )
)


# ============================================================
# BASE DE DATOS
# ============================================================

DATABASE = os.getenv("DATABASE", "naikito.db")


# ============================================================
# CONFIGURACIÓN DE MADRUGUE
# ============================================================

# Ventanas de puntos, fin de la madrugada y bonus horario. Todo se
# configura desde el .env con variables MADRUGUE_* (formato HH:MM para
# las horas) y se valida al arrancar: un valor inválido impide que el
# bot arranque con un error que nombra la variable culpable.

MADRUGUE_INICIO_100 = _leer_hora(
    "MADRUGUE_INICIO_100",
    "05:30",
)

MADRUGUE_INICIO_25 = _leer_hora(
    "MADRUGUE_INICIO_25",
    "07:00",
)

MADRUGUE_INICIO_5 = _leer_hora(
    "MADRUGUE_INICIO_5",
    "09:00",
)

MADRUGUE_FIN = _leer_hora(
    "MADRUGUE_FIN",
    "10:00",
)

MADRUGUE_PUNTOS_100 = _leer_entero(
    "MADRUGUE_PUNTOS_100",
    100,
)

MADRUGUE_PUNTOS_25 = _leer_entero(
    "MADRUGUE_PUNTOS_25",
    25,
)

MADRUGUE_PUNTOS_5 = _leer_entero(
    "MADRUGUE_PUNTOS_5",
    5,
)

MADRUGUE_BONUS_MAXIMO = _leer_decimal(
    "MADRUGUE_BONUS_MAXIMO",
    0.100,
)

MADRUGUE_BONUS_MINIMO = _leer_decimal(
    "MADRUGUE_BONUS_MINIMO",
    0.001,
)

# Validaciones cruzadas: las ventanas tienen que abrir y cerrar en
# orden, los puntos ser positivos y el bonus no invertirse.

_comprobar(
    MADRUGUE_INICIO_100
    < MADRUGUE_INICIO_25
    < MADRUGUE_INICIO_5
    < MADRUGUE_FIN,
    "los horarios de Madrugue deben ir en orden y sin repetirse: "
    "MADRUGUE_INICIO_100 < MADRUGUE_INICIO_25 < MADRUGUE_INICIO_5 "
    f"< MADRUGUE_FIN, pero se recibió {_hhmm(MADRUGUE_INICIO_100)} < "
    f"{_hhmm(MADRUGUE_INICIO_25)} < {_hhmm(MADRUGUE_INICIO_5)} < "
    f"{_hhmm(MADRUGUE_FIN)}.",
)

for _nombre, _puntos in (
    ("MADRUGUE_PUNTOS_100", MADRUGUE_PUNTOS_100),
    ("MADRUGUE_PUNTOS_25", MADRUGUE_PUNTOS_25),
    ("MADRUGUE_PUNTOS_5", MADRUGUE_PUNTOS_5),
):
    _comprobar(
        _puntos >= 1,
        f"{_nombre} debe ser un número entero mayor o igual que 1, "
        f"pero se recibió {_puntos}.",
    )

_comprobar(
    0
    <= MADRUGUE_BONUS_MINIMO
    <= MADRUGUE_BONUS_MAXIMO,
    "el bonus de Madrugue debe cumplir 0 <= MADRUGUE_BONUS_MINIMO "
    "<= MADRUGUE_BONUS_MAXIMO, pero se recibió mínimo "
    f"{MADRUGUE_BONUS_MINIMO} y máximo {MADRUGUE_BONUS_MAXIMO}.",
)


# ============================================================
# USUARIOS CON ACCESO ADMINISTRATIVO
# ============================================================

ADMIN_USER_IDS = {
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_USER_IDS", "").split(",")
    if user_id.strip()
}


# ============================================================
# SERVIDORES DE DISCORD
# ============================================================

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

GENERAL_CHANNEL_IDS = {
    int(canal_id.strip())
    for canal_id in os.getenv(
        "GENERAL_CHANNEL_ID",
        os.getenv("BOX_CHANNEL_ID", ""),
    ).split(",")
    if canal_id.strip()
}

MADRUGUE_CHANNEL_IDS = {
    int(canal_id.strip())
    for canal_id in os.getenv("MADRUGUE_CHANNEL_ID", "").split(",")
    if canal_id.strip()
}

BOX_CHANNEL_IDS = {
    int(canal_id.strip())
    for canal_id in os.getenv("BOX_CHANNEL_ID", "").split(",")
    if canal_id.strip()
}

# ============================================================
# CONFIGURACIÓN DE SEPTIEMBRESINFAP
# ============================================================

SSF_CANALES_ID = {
    int(canal_id.strip())
    for canal_id in os.getenv("SSF_CANALES_ID", "").split(",")
    if canal_id.strip()
}

SSF_FECHA_INICIO = os.getenv(
    "SSF_FECHA_INICIO",
    "2026-09-01",
)

SSF_FECHA_FIN = os.getenv(
    "SSF_FECHA_FIN",
    "2026-09-30",
)

# ============================================================
# CONFIGURACIÓN DE BOX
# ============================================================

BOX_EXPERIENCIA_POR_MINUTO = int(
    os.getenv("BOX_EXPERIENCIA_POR_MINUTO", "10")
)

BOX_DINERO_POR_MINUTO = int(
    os.getenv("BOX_DINERO_POR_MINUTO", "100")
)