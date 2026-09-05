import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from modules.madrugue.constants import (
    BONUS_MAXIMO,
    BONUS_MINIMO,
    FIN_MADRUGADA,
    PUNTOS_100_DESDE,
    PUNTOS_25_DESDE,
    PUNTOS_5_DESDE,
)


__all__ = [
    "PREFIX",
    "TIMEZONE",
    "DATABASE",
    "PUNTOS_100_DESDE",
    "PUNTOS_25_DESDE",
    "PUNTOS_5_DESDE",
    "FIN_MADRUGADA",
    "BONUS_MAXIMO",
    "BONUS_MINIMO",
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

# Los horarios de puntos y el bonus horario viven en
# modules/madrugue/constants.py y se reexportan desde acá para no romper
# `from config import ...`.


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