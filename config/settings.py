import os
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


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

# 05:30 - 06:59 = 100 puntos
# 07:00 - 08:59 = 25 puntos
# 09:00 - 09:59 = 5 puntos
# 10:00 en adelante = fuera de horario

PUNTOS_100_DESDE = time(5, 30)
PUNTOS_25_DESDE = time(7, 0)
PUNTOS_5_DESDE = time(9, 0)

FIN_MADRUGADA = time(10, 0)


# ============================================================
# MULTIPLICADOR DE MADRUGUE
# ============================================================

# El bonus disminuye linealmente a medida que avanza
# la madrugada.
#
# 05:30 = +0.100 -> x1.100
# 10:00 = +0.001 -> x1.001
#
# La racha no modifica el multiplicador.

BONUS_MAXIMO = 0.100
BONUS_MINIMO = 0.001


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