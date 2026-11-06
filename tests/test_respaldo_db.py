"""Respaldos de la base SQLite y rutas de la base en el despliegue."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _crear_base(ruta: Path) -> None:
    with sqlite3.connect(ruta) as db:
        db.execute("CREATE TABLE prueba (valor TEXT)")
        db.execute("INSERT INTO prueba VALUES ('dato')")


def _leer_base(ruta: Path) -> int:
    with sqlite3.connect(ruta) as db:
        return db.execute("SELECT COUNT(*) FROM prueba").fetchone()[0]


def test_respaldo_copia_y_rota(tmp_path):
    from scripts.respaldar_db import respaldar

    origen = tmp_path / "naikito-v2.db"
    destino = tmp_path / "respaldos"
    _crear_base(origen)

    for _ in range(3):
        copia, _eliminadas = respaldar(origen, destino, conservar=2)
        assert _leer_base(copia) == 1

    copias = sorted(destino.glob("naikito-v2-*.db"))
    assert len(copias) == 2
    # La copia no se vuelve a escribir.
    assert copias[-1].stat().st_mode & 0o222 == 0


def test_respaldo_borra_sobrantes(tmp_path):
    from scripts.respaldar_db import respaldar

    origen = tmp_path / "naikito-v2.db"
    destino = tmp_path / "respaldos"
    destino.mkdir()
    _crear_base(origen)

    # Copias de días anteriores que deben rotar.
    for sello in ("20260101-000000", "20260102-000000", "20260103-000000"):
        (destino / f"naikito-v2-{sello}.db").write_bytes(b"")

    copia, eliminadas = respaldar(origen, destino, conservar=2)
    assert len(eliminadas) == 2
    assert copia.exists()
    assert len(list(destino.glob("naikito-v2-*.db"))) == 2


def test_respaldo_falla_sin_base(tmp_path):
    from scripts.respaldar_db import respaldar

    try:
        respaldar(tmp_path / "no-existe.db", tmp_path / "respaldos")
    except FileNotFoundError as error:
        assert "no-existe.db" in str(error)
    else:  # pragma: no cover - el caso contrario no debería ocurrir
        raise AssertionError("Se esperaba FileNotFoundError")


def test_respaldo_por_linea_de_comandos(tmp_path):
    origen = tmp_path / "base.db"
    destino = tmp_path / "respaldos"
    _crear_base(origen)

    entorno = os.environ.copy()
    entorno.update(DATABASE_URL="", DATABASE=str(origen))
    resultado = subprocess.run(
        [
            sys.executable, "-m", "scripts.respaldar_db",
            "--destino", str(destino), "--conservar", "1",
        ],
        cwd=RAIZ, env=entorno, text=True, capture_output=True, check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "[RESPALDO] copia=" in resultado.stdout
    assert len(list(destino.glob("base-*.db"))) == 1


def test_database_relativa_se_resuelve_contra_el_proyecto(tmp_path):
    """El cwd del servicio (WorkingDirectory) no debe cambiar el archivo usado."""

    entorno = os.environ.copy()
    entorno.update(
        DATABASE_URL="", DATABASE="base-relativa.db",
        PYTHONPATH=str(RAIZ),
    )
    resultado = subprocess.run(
        [sys.executable, "-c", "import config; print(config.DATABASE)"],
        cwd=tmp_path, env=entorno, text=True, capture_output=True, check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert Path(resultado.stdout.strip()) == RAIZ / "base-relativa.db"
    assert not (tmp_path / "base-relativa.db").exists()


def test_database_absoluta_no_se_modifica(tmp_path):
    ruta = tmp_path / "datos" / "base.db"
    entorno = os.environ.copy()
    entorno.update(
        DATABASE_URL="", DATABASE=str(ruta), PYTHONPATH=str(RAIZ)
    )
    resultado = subprocess.run(
        [sys.executable, "-c", "import config; print(config.DATABASE)"],
        cwd=tmp_path, env=entorno, text=True, capture_output=True, check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert Path(resultado.stdout.strip()) == ruta
