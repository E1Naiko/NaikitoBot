"""Pruebas del comando administrativo ``/admin madrugue ver``.

Se ejecuta el callback real con una interacción falsa, igual que el resto
de las pruebas de comandos del repositorio.
"""

import asyncio
from datetime import date

import pytest

from tests.harness import InteraccionFalsa, UsuarioFalso, construir_cog

GUILD = 1
ADMIN = 1
USUARIO = 42


@pytest.fixture
def admin_ids(monkeypatch):
    """Deja un único administrador determinístico, sin depender del .env."""

    monkeypatch.setattr(
        "core.permissions.ADMIN_USER_IDS",
        {ADMIN},
    )


@pytest.fixture
def cog(base_datos_limpia, admin_ids):
    """Cog /admin con la tabla de Madrugue creada."""

    from modules.madrugue.database import inicializar_db

    inicializar_db()

    from commands.admin.cog import Admin

    return construir_cog(Admin)


def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        metodo(cog, interaccion, *args)
    )


def interaccion_admin():
    return InteraccionFalsa(
        GUILD,
        ADMIN,
        nombre="Admin",
    )


def guardar(fecha: date, hora: str, puntos_finales: float):
    """Guarda un registro de Madrugue directamente en la base."""

    from modules.madrugue.database import guardar_registro

    guardar_registro(
        guild_id=GUILD,
        user_id=USUARIO,
        username="Tester",
        fecha=fecha,
        hora=hora,
        puntos_base=100,
        multiplicador=1.0,
        puntos_finales=puntos_finales,
    )


def test_ver_sin_registros_informa(cog):
    interaccion = interaccion_admin()

    llamar(
        cog,
        "madrugue_ver",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
    )

    assert "no tiene" in interaccion.texto
    assert "registros de Madrugue" in interaccion.texto


def test_ver_muestra_resumen_y_ultimos_registros(cog):
    guardar(date(2026, 9, 1), "05:45", 100.0)
    guardar(date(2026, 9, 2), "06:30", 87.5)

    interaccion = interaccion_admin()

    llamar(
        cog,
        "madrugue_ver",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
    )

    texto = interaccion.texto

    assert "🌅 Madrugue — Tester" in texto
    assert "**2** en total" in texto
    assert "**187.5**" in texto
    assert "Mejor racha" in texto
    assert "`2026-09-01` → `2026-09-02`" in texto
    assert "**2026-09-02**" in texto
    assert "`06:30`" in texto


def test_ver_no_filtra_por_canal_ni_requiere_dm(cog):
    """Un admin puede consultar desde cualquier canal; solo requiere servidor."""

    interaccion = interaccion_admin()

    llamar(
        cog,
        "madrugue_ver",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
    )

    assert interaccion.cantidad_respuestas == 1
    assert interaccion.respuestas[-1].efimero
