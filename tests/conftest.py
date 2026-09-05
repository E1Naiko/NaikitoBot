"""Configuración compartida de las pruebas.

Fija la base de datos a un archivo temporal ANTES de importar ``config``,
que lee la variable de entorno ``DATABASE`` en el momento de la importación.
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


@pytest.fixture
def base_datos_limpia():
    """Deja la base de datos vacía y con el esquema de Box creado."""

    if os.environ["DATABASE"] and os.path.exists(os.environ["DATABASE"]):
        os.remove(os.environ["DATABASE"])

    from modules.box.database import inicializar_db

    inicializar_db()
    return os.environ["DATABASE"]
