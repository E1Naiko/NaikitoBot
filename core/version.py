"""Versión de Naikito Bot, impresa al final del arranque.

Formato: ``NaikitoBot{mayor}.{funcion}.{revision}.{YYYYMMDD}``

* ``{mayor}``: versión mayor del bot, fija (``1``).
* ``{funcion}``: número de la última función/sistema implementado. Se
  sube a mano (``VERSION_FUNCION`` abajo) cada vez que se agrega un
  sistema o una función nueva importante. Ahora mismo es la 5ª: la
  sincronización automática del canal 420 al reconectar
  (``core/lahora_sync.py``).
* ``{revision}``: ajustes sobre esa misma función. Arranca en ``0`` y se
  sube a mano (``VERSION_REVISION``) con cada corrección o retoque menor
  que no agregue una función nueva; vuelve a ``0`` cuando se sube
  ``VERSION_FUNCION``.
* ``{YYYYMMDD}``: fecha del último commit del repositorio. Se lee sola
  con ``git log`` en vez de mantenerse a mano; si no se puede leer (por
  ejemplo, un deploy sin ``.git`` o sin el binario de git), se usa la
  fecha de hoy y se avisa por consola.
"""

import subprocess
from datetime import date
from pathlib import Path

__all__ = ["version_bot"]

# Subir a mano con cada función/sistema nuevo importante (y resetear
# VERSION_REVISION a 0 al subir este número).
VERSION_FUNCION = 5

# Subir a mano con cada ajuste menor sobre la última función.
VERSION_REVISION = 0

_VERSION_MAYOR = 1
_RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


def _fecha_ultimo_commit() -> str:
    """Fecha (``YYYYMMDD``) del último commit, o la de hoy si no se puede leer."""

    try:
        resultado = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d"],
            cwd=_RAIZ_PROYECTO,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        fecha = resultado.stdout.strip()

        if fecha:
            return fecha

    except (OSError, subprocess.SubprocessError):
        pass

    print(
        "[VERSION] no se pudo leer la fecha del último commit (¿falta "
        "'.git' o el binario de git en este deploy?); se usa la fecha de "
        "hoy.",
        flush=True,
    )

    return date.today().strftime("%Y%m%d")


def version_bot() -> str:
    """Arma el string de versión de Naikito Bot."""

    return (
        f"NaikitoBot{_VERSION_MAYOR}."
        f"{VERSION_FUNCION}."
        f"{VERSION_REVISION}."
        f"{_fecha_ultimo_commit()}"
    )
