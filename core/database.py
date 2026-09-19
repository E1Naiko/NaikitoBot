"""Conexión a la base de datos de Naikito Bot con SQLAlchemy asíncrono.

El motor se elige con ``DATABASE_URL`` en el ``.env``:

* Producción: PostgreSQL con asyncpg
  (``postgresql+asyncpg://usuario:clave@host:5432/naikito``).
* Desarrollo y pruebas: SQLite con aiosqlite
  (``sqlite+aiosqlite:///naikito.db``), que es el valor por defecto.

Toda la capa de datos del bot usa sesiones asíncronas: cada función de
base de datos abre su propia sesión corta, equivalente a la vieja
``conectar_db()`` de SQLite.
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from config import DATABASE_URL, TIMEZONE


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos del bot."""


class TZDateTime(TypeDecorator):
    """Fecha y hora con zona horaria guardada como texto ISO.

    El tipo ``DateTime`` de SQLAlchemy pierde el offset al guardar en
    SQLite (su dialecto no serializa la zona horaria), y al leer queda
    una fecha ingenua que no se puede comparar con ``ahora()``. Este
    tipo guarda el ISO completo (con offset) y lo reinterpreta al leer,
    así el comportamiento es idéntico al viejo esquema de texto.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        if value.tzinfo is None:
            value = value.replace(tzinfo=TIMEZONE)

        return value.isoformat()

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return datetime.fromisoformat(value)


# En PostgreSQL se usa el tipo nativo ``TIMESTAMP WITH TIME ZONE``;
# en SQLite (desarrollo y pruebas) cae al texto ISO con offset.
FECHA_HORA = DateTime(timezone=True).with_variant(TZDateTime(), "sqlite")


# El motor asíncrono no abre conexiones hasta que se usa por primera
# vez, así que es seguro crearlo al importar el módulo. En SQLite se
# alarga el timeout de escritura para las pruebas, que mezclan la
# sesión asíncrona con conexiones sincrónicas de los helpers.
_kwargs = {}

if DATABASE_URL.startswith("sqlite"):
    _kwargs["connect_args"] = {"timeout": 30}

engine = create_async_engine(DATABASE_URL, **_kwargs)

crear_sesion = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def registrar_modelos():
    """Importa los módulos que definen modelos.

    SQLAlchemy solo conoce las tablas de los modelos ya importados;
    esto garantiza que ``Base.metadata`` esté completo antes de crear
    el esquema o de vaciar la base en las pruebas.
    """

    from modules.box import models as _box  # noqa: F401
    from modules.madrugue import models as _madrugue  # noqa: F401
    from modules.ssf import models as _ssf  # noqa: F401


async def inicializar_db():
    """Crea todas las tablas definidas por los modelos."""

    registrar_modelos()

    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)


async def vaciar_db():
    """Borra todas las tablas y las vuelve a crear.

    Solo lo usan las pruebas automatizadas para arrancar cada test con
    la base limpia.
    """

    registrar_modelos()

    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
        await conexion.run_sync(Base.metadata.create_all)
