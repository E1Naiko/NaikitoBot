"""Configuración compartida de las pruebas.

Fija la base de datos a un archivo SQLite temporal ANTES de importar
``config``, que arma la URL de la base en el momento de la importación.
La capa de datos usa SQLite tanto en producción como en pruebas.
"""

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_BASE = Path(tempfile.mkdtemp(prefix="naikito_test_"))
os.environ["DATABASE"] = str(_BASE / "test_box.db")
os.environ["DATABASE_URL"] = ""

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _pausa_http_aislada(monkeypatch):
    """Un 429 simulado no deja pausadas las pruebas siguientes."""

    from core.discord_http import PausaDiscord
    from core import discord_http

    monkeypatch.setattr(discord_http, "pausa_discord", PausaDiscord())


@pytest.fixture(autouse=True)
def _temporada_en_pruebas_historicas(request, monkeypatch):
    """Los ejemplos históricos de estas pruebas ocurren durante septiembre de 2026.

    Los límites reales y los reinicios se prueban sin este reloj en
    test_temporada.py; aquí se conservan los escenarios originales de 2026.
    """
    archivos = {
        "test_admin_comandos.py", "test_admin_lahora.py", "test_admin_ssf_ampliado.py",
        "test_core_lahora_sync.py", "test_lahora_comandos.py",
        "test_lahora_logs.py", "test_sqlite_configuracion.py",
    }
    if request.path.name not in archivos:
        return
    from datetime import datetime
    from config import TIMEZONE
    corte = datetime(2025, 10, 3, tzinfo=TIMEZONE)
    for modulo in (
        "commands.admin.lahora", "commands.admin.madrugue", "commands.admin.ssf",
        "modules.lahora.services", "modules.madrugue.database", "core.lahora_sync",
    ):
        monkeypatch.setattr(f"{modulo}.inicio_temporada", lambda *_args: corte)


@pytest.fixture
async def base_datos_limpia():
    """Deja la base de datos vacía y con el esquema completo creado."""

    from core.database import vaciar_db

    await vaciar_db()
    return os.environ["DATABASE"]
