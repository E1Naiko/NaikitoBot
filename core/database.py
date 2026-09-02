import sqlite3
from contextlib import contextmanager

from config import DATABASE


@contextmanager
def conectar_db():
    """Abre una conexión con la base de datos de Naikito Bot."""
    db = sqlite3.connect(DATABASE)
    try:
        yield db
    finally:
        db.close()