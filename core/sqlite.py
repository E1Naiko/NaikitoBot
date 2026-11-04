"""Conexiones SQLite al mismo archivo persistente del bot.

Cada operación abre su propia conexión. Las escrituras deben confirmar la
transacción explícitamente; al cerrar sin confirmar, SQLite la revierte.
"""

from contextlib import contextmanager
import sqlite3

import aiosqlite

from config import DATABASE


def conectar():
    """Devuelve una conexión asíncrona al archivo configurado."""
    return aiosqlite.connect(DATABASE, timeout=30)


@contextmanager
def conectar_sync():
    """Conexión bloqueante para operaciones ejecutadas fuera del event loop."""
    conexion = sqlite3.connect(DATABASE, timeout=30)
    try:
        yield conexion
    finally:
        conexion.close()
