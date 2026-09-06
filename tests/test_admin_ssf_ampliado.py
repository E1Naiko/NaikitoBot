"""Pruebas de los comandos administrativos nuevos de SeptSinFP.

Cubren ``/admin ssf estado``, ``desafio``, ``participantes``, ``eliminar``,
``cerrar`` y ``ranking``, además del inicio con fechas configurables.
"""

import asyncio
from datetime import datetime

import pytest

from tests.harness import (
    Choice,
    InteraccionFalsa,
    UsuarioFalso,
    construir_cog,
)

GUILD = 1
ADMIN = 1
USUARIO = 42
USUARIO_2 = 43
CANAL = 99

NOMBRE = "SeptSinFP 2026"
INICIO = "2026-09-01"
FIN = "2026-09-30"


class CanalFalso:
    """Doble mínimo de ``discord.TextChannel`` para /admin ssf iniciar."""

    def __init__(self, canal_id=CANAL):
        self.id = canal_id
        self.mention = f"<#{canal_id}>"


@pytest.fixture
def ssf_db(base_datos_limpia):
    """Deja la base de SSF creada y limpia."""

    from modules.ssf.database import inicializar_db

    inicializar_db()
    return True


@pytest.fixture
def desafio_ssf(ssf_db):
    """Crea el desafío de septiembre."""

    from modules.ssf.services import iniciar_desafio

    resultado = iniciar_desafio(
        GUILD,
        NOMBRE,
        INICIO,
        FIN,
        CANAL,
    )
    assert resultado["exitoso"]
    return resultado["desafio_id"]


@pytest.fixture
def admin_ids(monkeypatch):
    monkeypatch.setattr(
        "core.permissions.ADMIN_USER_IDS",
        {ADMIN},
    )


@pytest.fixture
def cog_admin(desafio_ssf, admin_ids):
    from commands.admin.cog import Admin

    return construir_cog(Admin)


@pytest.fixture
def hoy_5_sep(monkeypatch):
    """Fija el reloj de los comandos /admin ssf en el 5/9/2026."""

    import importlib

    modulo = importlib.import_module("commands.admin.ssf")

    monkeypatch.setattr(
        modulo,
        "ahora",
        lambda: datetime(2026, 9, 5, 12, 0),
    )


def ejecutar(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coro
    )


def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return ejecutar(metodo(cog, interaccion, *args))


def interaccion_admin():
    return InteraccionFalsa(
        GUILD,
        ADMIN,
        nombre="Admin",
    )


def mediodia(dia):
    return datetime(2026, 9, dia, 12, 0)


def registrar(user_id=USUARIO, nombre="Tester", dia=1):
    from modules.ssf.services import registrar_usuario

    resultado = registrar_usuario(
        GUILD,
        user_id,
        nombre,
        mediodia(dia),
    )
    assert resultado["exitoso"]
    return resultado


def sobrevivir(dias, user_id=USUARIO):
    from modules.ssf.services import registrar_sobrevivi

    for dia in dias:
        resultado = registrar_sobrevivi(
            GUILD,
            user_id,
            mediodia(dia),
        )
        assert resultado["exitoso"], f"día {dia}: {resultado!r}"


def marcar_eliminado(user_id=USUARIO, fecha="2026-09-03"):
    """Marca eliminado directo en la base (para poblar el listado)."""

    from modules.ssf.database import eliminar_participante, obtener_desafio_activo

    desafio_id = obtener_desafio_activo(GUILD)[0]
    eliminar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha_eliminacion=fecha,
    )


# ============================================================
# SSF - ESTADO
# ============================================================

def test_estado_muestra_detalle_de_otro_usuario(cog_admin):
    registrar()
    sobrevivir([2, 3])

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_estado",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
    )

    assert "Estado de Tester" in interaccion.texto
    assert "Rango" in interaccion.texto
    assert "Racha actual" in interaccion.texto
    assert "Mejor racha" in interaccion.texto


def test_estado_a_no_participante_informa(cog_admin):
    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_estado",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
    )

    assert "no está registrado" in interaccion.texto


def test_estado_sin_desafio_informa(ssf_db, admin_ids):
    from commands.admin.cog import Admin

    cog = construir_cog(Admin)

    interaccion = interaccion_admin()

    llamar(
        cog,
        "ssf_estado",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
    )

    assert "No hay un desafío SeptSinFP activo" in interaccion.texto


# ============================================================
# SSF - DESAFIO
# ============================================================

def test_desafio_muestra_el_estado_global(cog_admin):
    registrar()
    sobrevivir([2, 3])
    registrar(USUARIO_2, "Rival", dia=1)

    interaccion = interaccion_admin()

    llamar(cog_admin, "ssf_desafio", interaccion)

    texto = interaccion.texto
    assert NOMBRE in texto
    assert "2" in texto
    assert f"`{INICIO}` → `{FIN}`" in texto
    assert "Activos" in texto
    assert "Eliminados" in texto


def test_desafio_sin_activo_informa(ssf_db, admin_ids):
    from commands.admin.cog import Admin

    cog = construir_cog(Admin)
    interaccion = interaccion_admin()

    llamar(cog, "ssf_desafio", interaccion)

    assert "No hay un desafío" in interaccion.texto


# ========================================================
# SSF - PARTICIPANTES
# ========================================================

def test_participantes_lista_activos_y_eliminados(cog_admin):
    registrar()
    sobrevivir([2, 3])
    registrar(USUARIO_2, "Rival", dia=1)
    marcar_eliminado(USUARIO_2, "2026-09-02")

    interaccion = interaccion_admin()

    llamar(cog_admin, "ssf_participantes", interaccion)

    texto = interaccion.texto
    assert "**Tester**" in texto
    assert "**Rival**" in texto
    assert "💀" in texto
    assert "🟢" in texto


# ========================================================
# SSF - ELIMINAR
# ========================================================

def test_eliminar_marca_eliminado_por_dia_faltado(
    cog_admin,
    hoy_5_sep,
):
    registrar()
    sobrevivir([2, 3])

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_eliminar",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
        "2026-09-04",
    )

    assert "eliminado correctamente" in interaccion.texto

    from modules.ssf.database import obtener_participante, obtener_desafio_activo

    participante = obtener_participante(
        obtener_desafio_activo(GUILD)[0],
        USUARIO,
    )
    assert participante[4] == 1
    assert participante[5] == "2026-09-04"


def test_eliminar_con_registro_ese_dia_informa(cog_admin, hoy_5_sep):
    registrar()
    sobrevivir([2, 3])

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_eliminar",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
        "2026-09-03",
    )

    assert "tiene registrado el día **2026-09-03**" in interaccion.texto
    assert "ssf quitar" in interaccion.texto


def test_eliminar_fecha_futura_rechaza(cog_admin, hoy_5_sep):
    registrar()

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_eliminar",
        interaccion,
        UsuarioFalso(USUARIO, "Tester"),
        "2026-09-10",
    )

    assert "día futuro" in interaccion.texto


# ========================================================
# SSF - CERRAR
# ========================================================

def test_cerrar_sin_confirmacion_cancela(cog_admin):
    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_cerrar",
        interaccion,
        Choice("NO"),
    )

    assert "Operación cancelada" in interaccion.texto

    from modules.ssf.database import obtener_desafio_activo

    assert obtener_desafio_activo(GUILD) is not None


def test_cerrar_confirma_y_deja_de_haber_activo(cog_admin):
    registrar()
    sobrevivir([2, 3])

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_cerrar",
        interaccion,
        Choice("SI"),
    )

    assert "cerrado correctamente" in interaccion.texto

    from modules.ssf.database import obtener_desafio_activo

    assert obtener_desafio_activo(GUILD) is None


# ========================================================
# SSF - RANKING
# ========================================================

def test_ranking_muestra_al_mejor_participante(cog_admin):
    registrar()
    sobrevivir([2, 3, 4, 5])
    registrar(USUARIO_2, "Rival", dia=1)
    sobrevivir([2, 3], user_id=USUARIO_2)

    interaccion = interaccion_admin()

    llamar(cog_admin, "ssf_ranking", interaccion)

    texto = interaccion.texto
    assert "Ranking de" in texto
    assert "(en curso)" in texto
    assert "**Tester**" in texto
    assert "**Rival**" in texto


def test_ranking_sin_desafios_informa(ssf_db, admin_ids):
    from commands.admin.cog import Admin

    cog = construir_cog(Admin)
    interaccion = interaccion_admin()

    llamar(cog, "ssf_ranking", interaccion)

    assert "Todavía no hay desafíos" in interaccion.texto


# ========================================================
# SSF - INICIAR CON FECHAS
# ========================================================

def test_iniciar_acepta_fechas_y_nombre_propios(ssf_db, admin_ids):
    from commands.admin.cog import Admin

    cog = construir_cog(Admin)
    interaccion = interaccion_admin()

    llamar(
        cog,
        "ssf_iniciar",
        interaccion,
        CanalFalso(CANAL),
        "2026-10-01",
        "2026-10-31",
        "OctubreSinFP",
    )

    assert "OctubreSinFP" in interaccion.texto
    assert "**2026-10-01**" in interaccion.texto
    assert "**2026-10-31**" in interaccion.texto


def test_iniciar_fechas_invalidas_rechaza(ssf_db, admin_ids):
    from commands.admin.cog import Admin

    cog = construir_cog(Admin)
    interaccion = interaccion_admin()

    llamar(
        cog,
        "ssf_iniciar",
        interaccion,
        CanalFalso(CANAL),
        "no-es-fecha",
        "2026-10-31",
    )

    assert "Las fechas no son válidas" in interaccion.texto


def test_iniciar_con_inicio_posterior_al_fin_rechaza(ssf_db, admin_ids):
    from commands.admin.cog import Admin

    cog = construir_cog(Admin)
    interaccion = interaccion_admin()

    llamar(
        cog,
        "ssf_iniciar",
        interaccion,
        CanalFalso(CANAL),
        "2026-10-31",
        "2026-10-01",
    )

    assert "no puede ser posterior" in interaccion.texto
