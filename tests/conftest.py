"""Configuración compartida de las pruebas.

Fija la base de datos a un archivo SQLite temporal ANTES de importar
``config``, que arma la URL de la base en el momento de la importación.
La capa de datos usa SQLAlchemy asíncrono: en producción corre sobre
PostgreSQL (asyncpg) y en las pruebas sobre SQLite (aiosqlite).
"""

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_BASE = Path(tempfile.mkdtemp(prefix="naikito_test_"))
os.environ["DATABASE"] = str(_BASE / "test_box.db")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _pausa_http_aislada(monkeypatch):
    """Un 429 simulado no deja pausadas las pruebas siguientes."""

    from core.discord_http import PausaDiscord
    from core import discord_http

    monkeypatch.setattr(discord_http, "pausa_discord", PausaDiscord())


@pytest.fixture
async def base_datos_limpia():
    """Deja la base de datos vacía y con el esquema completo creado."""

    from core.database import vaciar_db

    await vaciar_db()
    return os.environ["DATABASE"]
