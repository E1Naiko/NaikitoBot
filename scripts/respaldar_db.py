"""Respaldo del archivo SQLite del bot, con rotación de copias.

Usa la API de respaldo de ``sqlite3`` (``Connection.backup``), que copia de
forma consistente aunque el bot esté escribiendo: no hace falta detenerlo.

    python -m scripts.respaldar_db                 # copia y conserva 14
    python -m scripts.respaldar_db --conservar 30  # cambia la retención
    python -m scripts.respaldar_db --destino /mnt/respaldos

La ruta de origen es la misma que usa el bot (``DATABASE`` en el ``.env`` o
en el entorno). Los respaldos se guardan por defecto en un subdirectorio
``respaldos`` junto a la base, con el nombre
``<base>-YYYYMMDD-HHMMSS.db`` y permisos de solo lectura.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import os
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATABASE  # noqa: E402

__all__ = ["respaldar", "limpiar_respaldos"]

_CONSERVAR_POR_DEFECTO = 14


def _bases_en(destino: Path, prefijo: str) -> list[Path]:
    """Copias conocidas del destino, de la más nueva a la más vieja."""

    return sorted(
        destino.glob(f"{prefijo}-*.db"),
        key=lambda ruta: ruta.name,
        reverse=True,
    )


def limpiar_respaldos(destino: Path, prefijo: str, conservar: int) -> list[Path]:
    """Borra las copias más viejas y devuelve las eliminadas."""

    if conservar < 1:
        raise ValueError("La cantidad a conservar debe ser 1 o más.")

    sobrantes = _bases_en(destino, prefijo)[conservar:]
    eliminadas = []
    for ruta in sobrantes:
        ruta.unlink()
        eliminadas.append(ruta)
    return eliminadas


def respaldar(
    origen: str | Path,
    destino: str | Path | None = None,
    *,
    conservar: int = _CONSERVAR_POR_DEFECTO,
) -> tuple[Path, list[Path]]:
    """Copia ``origen`` en ``destino`` y aplica la retención.

    Devuelve la copia creada y la lista de copias borradas.
    """

    origen = Path(origen)
    if not origen.is_file():
        raise FileNotFoundError(f"No existe el archivo de la base: {origen}")

    destino = Path(destino) if destino is not None else origen.parent / "respaldos"
    destino.mkdir(parents=True, exist_ok=True)

    prefijo = origen.stem
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    copia = destino / f"{prefijo}-{sello}.db"
    # Un nombre repetido (dos respaldos en el mismo segundo) no debe pisar
    # la copia anterior.
    contador = 1
    while copia.exists():
        copia = destino / f"{prefijo}-{sello}-{contador}.db"
        contador += 1

    with sqlite3.connect(origen, timeout=30) as fuente:
        with sqlite3.connect(copia) as salida:
            fuente.backup(salida)

    # La copia no se vuelve a escribir: que nadie la modifique por error.
    os.chmod(copia, 0o440)

    eliminadas = limpiar_respaldos(destino, prefijo, conservar)
    return copia, eliminadas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Respalda el archivo SQLite del bot y rota los respaldos.",
    )
    parser.add_argument(
        "--origen",
        default=DATABASE,
        help="Archivo SQLite a respaldar (por defecto, DATABASE).",
    )
    parser.add_argument(
        "--destino",
        default=None,
        help="Carpeta de respaldos (por defecto, 'respaldos' junto a la base).",
    )
    parser.add_argument(
        "--conservar",
        type=int,
        default=_CONSERVAR_POR_DEFECTO,
        help=f"Copias a conservar ({_CONSERVAR_POR_DEFECTO} por defecto).",
    )
    args = parser.parse_args(argv)

    if args.conservar < 1:
        parser.error("--conservar debe ser 1 o más.")

    try:
        copia, eliminadas = respaldar(
            args.origen, args.destino, conservar=args.conservar
        )
    except (OSError, sqlite3.Error) as error:
        print(f"[RESPALDO] error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    print(f"[RESPALDO] copia={copia} bytes={copia.stat().st_size}", flush=True)
    if eliminadas:
        print(
            f"[RESPALDO] rotación: {len(eliminadas)} copia(s) anterior(es) borrada(s)",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
