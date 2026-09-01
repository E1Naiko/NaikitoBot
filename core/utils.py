from datetime import datetime

from config import TIMEZONE


def ahora():
    """Devuelve la fecha y hora actual según la zona horaria configurada."""
    return datetime.now(TIMEZONE)