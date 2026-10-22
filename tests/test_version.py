"""Versión de Naikito Bot (``core.version``)."""

import subprocess

import core.version as version_module
from core.version import version_bot


def test_formato_con_git_disponible(monkeypatch):
    """Con git disponible, usa la fecha real del último commit."""

    class _Resultado:
        stdout = "20260915\n"

    monkeypatch.setattr(
        version_module.subprocess,
        "run",
        lambda *args, **kwargs: _Resultado(),
    )
    monkeypatch.setattr(version_module, "VERSION_FUNCION", 5)
    monkeypatch.setattr(version_module, "VERSION_REVISION", 0)

    assert version_bot() == "NaikitoBot1.5.0.20260915"


def test_usa_la_fecha_de_hoy_si_git_falla(monkeypatch, capsys):
    """Si git no está disponible (o falla), cae a la fecha de hoy y avisa."""

    def _reventar(*args, **kwargs):
        raise FileNotFoundError("git no instalado")

    monkeypatch.setattr(version_module.subprocess, "run", _reventar)
    monkeypatch.setattr(version_module, "VERSION_FUNCION", 5)
    monkeypatch.setattr(version_module, "VERSION_REVISION", 0)

    import datetime

    hoy = datetime.date.today().strftime("%Y%m%d")
    resultado = version_bot()

    assert resultado == f"NaikitoBot1.5.0.{hoy}"
    assert "no se pudo leer la fecha del último commit" in capsys.readouterr().out


def test_usa_la_fecha_de_hoy_si_git_devuelve_error(monkeypatch):
    """``git log`` puede existir pero fallar (por ejemplo, sin ``.git``)."""

    def _fallar(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(version_module.subprocess, "run", _fallar)

    import datetime

    hoy = datetime.date.today().strftime("%Y%m%d")

    assert version_bot().endswith(hoy)


def test_formato_completo_contra_el_repositorio_real():
    """Sin mockear nada: valida el formato real contra el repo del proyecto."""

    import re

    assert re.fullmatch(r"NaikitoBot\d+\.\d+\.\d+\.\d{8}", version_bot())
