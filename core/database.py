"""Esquema y utilidades para el archivo SQLite del bot."""

from pathlib import Path
import re

import config
from core.sqlite import conectar

_RUTA_ESQUEMA = Path(__file__).with_name("esquema.sql")


def esquema_sql():
    """Carga el esquema con los valores iniciales configurados para Box."""
    valores = {
        nombre: getattr(config, nombre)
        for nombre in (
            "BOX_VIDA_INICIAL", "BOX_DANO_INICIAL", "BOX_DANO_MAXIMO",
            "BOX_DEFENSA_INICIAL", "BOX_DEFENSA_MAXIMO", "BOX_CANSANCIO_INICIAL",
        )
    }
    return _RUTA_ESQUEMA.read_text(encoding="utf-8").format(**valores)


async def inicializar_db():
    """Crea las tablas faltantes sin borrar ni modificar los datos existentes."""
    async with conectar() as conexion:
        await conexion.executescript(esquema_sql())
        await conexion.commit()


async def vaciar_db():
    """Borra y recrea las tablas del bot. Solo para pruebas automatizadas."""
    esquema = esquema_sql()
    nombres = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", esquema)
    async with conectar() as conexion:
        # La lista proviene exclusivamente de nuestro esquema, no de datos externos.
        for nombre in reversed(nombres):
            await conexion.execute(f'DROP TABLE IF EXISTS "{nombre}"')
        await conexion.commit()
        await conexion.executescript(esquema)
        await conexion.commit()
