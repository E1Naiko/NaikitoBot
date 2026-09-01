import os
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


load_dotenv()


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

DATABASE = "naikito.db"


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

GUILD_SERVIDOR = int(os.getenv("GUILD_SERVIDOR", "0"))
GUILD_TEST = int(os.getenv("GUILD_TEST", "0"))