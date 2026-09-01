import sqlite3

from config import DATABASE


def conectar_db():
    """Abre una conexión con la base de datos de Naikito Bot."""
    return sqlite3.connect(DATABASE)