"""Pruebas de la reparación manual de SeptSinFP.

Cubre el incidente del 5/9/2026: tres participantes eliminados por el código
anterior (que pisaba ``racha_actual`` con 0) quedaron mostrando 0 días aunque
sus registros de los días 1, 2 y 3 seguían intactos, y una participante
revivida con la fecha de hoy en vez del día perdido quedó con racha 1.

Los servicios ``agregar_dia`` / ``quitar_dia`` / ``recalcular_rachas`` y sus
comandos ``/admin ssf`` permiten corregir esos casos a mano.
"""

from datetime import date, datetime

import pytest

from modules.ssf.database import (
    guardar_registro,
    obtener_participante,
    registrar_participante,
    tiene_registro,
)
from modules.ssf.services import (
    agregar_dia,
    eliminar_faltantes,
    iniciar_desafio,
    obtener_estado_usuario,
    quitar_dia,
    recalcular_rachas,
    registrar_sobrevivi,
    registrar_usuario,
    revivir_participante,
)
from tests.harness import (
    GuildFalso,
    InteraccionFalsa,
    UsuarioFalso,
    construir_cog,
)

GUILD = 1
ADMIN = 1
USUARIO = 42
CANAL = 99

NOMBRE = "SeptiembreSinFAP"
INICIO = "2026-09-01"
FIN = "2026-09-30"

HOY = date(2026, 9, 5)

RANGO_CABO = "Cabo 🎗️"
RANGO_SOLDADO = "Soldado 🪖"
RANGO_SARGENTO = "Tercer Sargento 🥉"


@pytest.fixture
def desafio_ssf(base_datos_limpia):
    """Crea el desafío de septiembre sobre una base limpia."""

    from modules.ssf.database import inicializar_db

    inicializar_db()

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
    """Deja un único administrador determinístico, sin depender del .env."""

    monkeypatch.setattr(
        "core.permissions.ADMIN_USER_IDS",
        {ADMIN},
    )


@pytest.fixture
def cog_admin(desafio_ssf, admin_ids):
    """Cog /admin sobre un desafío SSF ya creado."""

    from commands.admin.cog import Admin

    return construir_cog(Admin)


@pytest.fixture
def hoy_5_sep(monkeypatch):
    """Fija el reloj de los comandos en el mediodía del 5/9/2026."""

    # Se importa el objeto módulo en vez de usar la ruta en string:
    # load_extension() deja commands.admin en sys.modules sin el
    # atributo padre, y la resolución por string de monkeypatch falla.
    import importlib

    modulo = importlib.import_module("commands.admin.ssf")

    monkeypatch.setattr(
        modulo,
        "ahora",
        lambda: datetime(2026, 9, 5, 12, 0),
    )


def ejecutar(coro):
    import asyncio

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


def registrar(dia, user_id=USUARIO, nombre="Tester"):
    return registrar_usuario(
        GUILD,
        user_id,
        nombre,
        mediodia(dia),
    )


def sobrevivir(dias, user_id=USUARIO):
    for dia in dias:
        resultado = registrar_sobrevivi(
            GUILD,
            user_id,
            mediodia(dia),
        )
        assert resultado["exitoso"], f"día {dia}: {resultado!r}"


def miembro(user_id=USUARIO, nombre="Tester"):
    return UsuarioFalso(user_id, nombre)


def desafio_id_activo():
    from modules.ssf.database import obtener_desafio_activo

    return obtener_desafio_activo(GUILD)[0]


# ============================================================
# AGREGAR DÍA
# ============================================================

def test_agregar_dia_suma_el_dia_faltante(desafio_ssf):
    registrar(1)
    sobrevivir([2, 3])

    resultado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 4),
        HOY,
    )

    assert resultado["exitoso"]
    assert resultado["racha"] == 4
    assert resultado["mejor_racha"] == 4
    assert resultado["rango"] == RANGO_CABO
    assert tiene_registro(desafio_ssf, USUARIO, "2026-09-04")


def test_agregar_dia_guarda_hora_admin(desafio_ssf):
    from core.database import conectar_db

    registrar(1)
    sobrevivir([2, 3])

    agregar_dia(GUILD, USUARIO, date(2026, 9, 4), HOY)

    with conectar_db() as db:
        hora = db.execute("""
            SELECT hora
            FROM ssf_registros
            WHERE desafio_id = ?
            AND user_id = ?
            AND fecha = ?
        """, (
            desafio_ssf,
            USUARIO,
            "2026-09-04",
        )).fetchone()[0]

    assert hora == "ADMIN"


def test_agregar_dia_rellena_un_hueco_intermedio(desafio_ssf):
    registrar(1)
    sobrevivir([2, 3, 5])

    estado = obtener_estado_usuario(GUILD, USUARIO)
    assert estado["racha_actual"] == 1

    resultado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 4),
        HOY,
    )

    assert resultado["exitoso"]
    assert resultado["racha"] == 5
    assert resultado["mejor_racha"] == 5
    assert resultado["rango"] == RANGO_SARGENTO


def test_agregar_dia_rechaza_eliminado(desafio_ssf):
    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    resultado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 5),
        HOY,
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "eliminado",
    }


def test_agregar_dia_rechaza_fecha_futura(desafio_ssf):
    registrar(1)
    sobrevivir([2, 3])

    resultado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 6),
        HOY,
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "futura",
    }


def test_agregar_dia_rechaza_duplicado(desafio_ssf):
    registrar(1)
    sobrevivir([2, 3])

    resultado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 3),
        HOY,
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "ya_registrado",
    }


def test_agregar_dia_rechaza_fuera_de_fecha(desafio_ssf):
    registrar(1)

    resultado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 10, 1),
        HOY,
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "fuera_de_fecha",
    }


def test_agregar_dia_rechaza_no_participante(desafio_ssf):
    resultado = agregar_dia(
        GUILD,
        777,
        date(2026, 9, 4),
        HOY,
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "no_participante",
    }


def test_agregar_dia_sin_desafio(desafio_ssf):
    resultado = agregar_dia(
        999,
        USUARIO,
        date(2026, 9, 4),
        HOY,
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "sin_desafio",
    }


# ============================================================
# QUITAR DÍA
# ============================================================

def test_quitar_dia_baja_la_racha(desafio_ssf):
    registrar(1)
    sobrevivir([2, 3, 4])

    resultado = quitar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 4),
    )

    assert resultado["exitoso"]
    assert resultado["racha"] == 3
    assert resultado["mejor_racha"] == 3
    assert resultado["rango"] == RANGO_CABO
    assert resultado["eliminado"] is False
    assert not tiene_registro(desafio_ssf, USUARIO, "2026-09-04")


def test_quitar_dia_acepta_eliminados_sin_revivir(desafio_ssf):
    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    resultado = quitar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 3),
    )

    assert resultado["exitoso"]
    assert resultado["racha"] == 2
    assert resultado["mejor_racha"] == 2
    assert resultado["eliminado"] is True

    participante = obtener_participante(desafio_ssf, USUARIO)
    assert participante[4] == 1


def test_quitar_dia_deja_cero_sin_registros(desafio_ssf):
    registrar(1)

    resultado = quitar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 1),
    )

    assert resultado["exitoso"]
    assert resultado["racha"] == 0
    assert resultado["mejor_racha"] == 0
    assert resultado["rango"] == RANGO_SOLDADO


def test_quitar_dia_borra_registros_fuera_del_desafio(desafio_ssf):
    registrar(1)
    guardar_registro(
        desafio_id=desafio_ssf,
        user_id=USUARIO,
        fecha="2026-10-05",
        hora="00:00:00",
    )

    resultado = quitar_dia(
        GUILD,
        USUARIO,
        date(2026, 10, 5),
    )

    assert resultado["exitoso"]
    assert not tiene_registro(desafio_ssf, USUARIO, "2026-10-05")


def test_quitar_dia_sin_registro_informa(desafio_ssf):
    registrar(1)

    resultado = quitar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 4),
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "sin_registro",
    }


def test_quitar_dia_rechaza_no_participante(desafio_ssf):
    resultado = quitar_dia(
        GUILD,
        777,
        date(2026, 9, 4),
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "no_participante",
    }


def test_quitar_dia_sin_desafio(desafio_ssf):
    resultado = quitar_dia(
        999,
        USUARIO,
        date(2026, 9, 4),
    )

    assert resultado == {
        "exitoso": False,
        "motivo": "sin_desafio",
    }


# ============================================================
# RECALCULAR RACHAS
# ============================================================

def test_recalcular_repara_eliminado_con_racha_en_cero(desafio_ssf):
    from modules.ssf.database import actualizar_participante

    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    # Simula el código anterior al refactor, que pisaba la racha con 0.
    actualizar_participante(
        desafio_id=desafio_ssf,
        user_id=USUARIO,
        racha_actual=0,
        mejor_racha=0,
    )

    resultado = recalcular_rachas(GUILD, USUARIO)

    assert resultado["exitoso"]
    assert resultado["racha"] == 3
    assert resultado["mejor_racha"] == 3
    assert resultado["rango"] == RANGO_CABO
    assert resultado["eliminado"] is True

    participante = obtener_participante(desafio_ssf, USUARIO)
    assert participante[4] == 1
    assert participante[6] == 3
    assert participante[7] == 3


def test_recalcular_no_cambia_el_estado_activo(desafio_ssf):
    from modules.ssf.database import actualizar_participante

    registrar(1)
    sobrevivir([2, 3, 4])

    actualizar_participante(
        desafio_id=desafio_ssf,
        user_id=USUARIO,
        racha_actual=0,
        mejor_racha=0,
    )

    resultado = recalcular_rachas(GUILD, USUARIO)

    assert resultado["exitoso"]
    assert resultado["racha"] == 4
    assert resultado["mejor_racha"] == 4
    assert resultado["eliminado"] is False


def test_recalcular_sin_registros_da_cero(desafio_ssf):
    registrar_participante(
        desafio_id=desafio_ssf,
        user_id=USUARIO,
        username="Tester",
        fecha_registro=mediodia(1).isoformat(),
    )

    resultado = recalcular_rachas(GUILD, USUARIO)

    assert resultado["exitoso"]
    assert resultado["racha"] == 0
    assert resultado["mejor_racha"] == 0
    assert resultado["rango"] == RANGO_SOLDADO


def test_recalcular_rechaza_no_participante(desafio_ssf):
    resultado = recalcular_rachas(GUILD, 777)

    assert resultado == {
        "exitoso": False,
        "motivo": "no_participante",
    }


def test_recalcular_sin_desafio(desafio_ssf):
    resultado = recalcular_rachas(999, USUARIO)

    assert resultado == {
        "exitoso": False,
        "motivo": "sin_desafio",
    }


# ============================================================
# RECETA DEL INCIDENTE: REVIVE CON FECHA EQUIVOCADA
# ============================================================

def test_receta_revive_equivocado_se_corrige_quitando_y_agregando(
    desafio_ssf,
):
    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    # El admin revive con la fecha de hoy en vez del día perdido.
    revivido = revivir_participante(
        GUILD,
        USUARIO,
        date(2026, 9, 5),
    )
    assert revivido["exitoso"]
    assert revivido["racha"] == 1

    # Se quita el día mal cargado y se agrega el día perdido.
    quitado = quitar_dia(GUILD, USUARIO, date(2026, 9, 5))
    assert quitado["exitoso"]
    assert quitado["racha"] == 3

    agregado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 4),
        HOY,
    )
    assert agregado["exitoso"]
    assert agregado["racha"] == 4
    assert agregado["mejor_racha"] == 4

    estado = obtener_estado_usuario(GUILD, USUARIO)
    assert estado["exitoso"]
    assert estado["eliminado"] is False
    assert estado["racha_actual"] == 4
    assert estado["mejor_racha"] == 4
    assert estado["rango"] == RANGO_CABO


def test_agregar_sobre_revive_equivocado_perdona_el_dia_de_hoy(
    desafio_ssf,
):
    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    revivido = revivir_participante(
        GUILD,
        USUARIO,
        date(2026, 9, 5),
    )
    assert revivido["exitoso"]

    # Sin quitar el día de hoy, agregarlo directo deja racha 5.
    agregado = agregar_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 4),
        HOY,
    )

    assert agregado["exitoso"]
    assert agregado["racha"] == 5
    assert agregado["mejor_racha"] == 5


# ============================================================
# COMANDOS /admin ssf
# ============================================================

def test_comando_agregar_responde_exito(cog_admin, hoy_5_sep):
    registrar(1)
    sobrevivir([2, 3])

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_agregar",
        interaccion,
        miembro(),
        "2026-09-04",
    )

    assert "Día agregado" in interaccion.texto
    assert "4 días" in interaccion.texto
    assert RANGO_CABO in interaccion.texto
    assert interaccion.respuestas[-1].efimero


def test_comando_agregar_con_fecha_invalida_informa(
    cog_admin,
    hoy_5_sep,
):
    registrar(1)

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_agregar",
        interaccion,
        miembro(),
        "04-09-2026",
    )

    assert "no es válida" in interaccion.texto


def test_comando_agregar_a_eliminado_sugiere_revivir(
    cog_admin,
    hoy_5_sep,
):
    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_agregar",
        interaccion,
        miembro(),
        "2026-09-04",
    )

    assert "revivir" in interaccion.texto


def test_comando_quitar_responde_exito(cog_admin):
    registrar(1)
    sobrevivir([2, 3, 4])

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_quitar",
        interaccion,
        miembro(),
        "2026-09-04",
    )

    assert "Día quitado" in interaccion.texto
    assert "3 días" in interaccion.texto
    assert interaccion.respuestas[-1].efimero


def test_comando_quitar_a_eliminado_aclara_que_sigue_eliminado(
    cog_admin,
):
    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_quitar",
        interaccion,
        miembro(),
        "2026-09-03",
    )

    assert "Día quitado" in interaccion.texto
    assert "sigue eliminado" in interaccion.texto


def test_comando_recalcular_responde_exito(cog_admin):
    from modules.ssf.database import actualizar_participante

    registrar(1)
    sobrevivir([2, 3])
    assert eliminar_faltantes(GUILD, date(2026, 9, 4)) == 1

    actualizar_participante(
        desafio_id=desafio_id_activo(),
        user_id=USUARIO,
        racha_actual=0,
        mejor_racha=0,
    )

    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_recalcular",
        interaccion,
        miembro(),
    )

    assert "recalculadas" in interaccion.texto
    assert "3 días" in interaccion.texto
    assert RANGO_CABO in interaccion.texto
    assert "Eliminado" in interaccion.texto


def test_comando_recalcular_a_no_participante_informa(cog_admin):
    interaccion = interaccion_admin()

    llamar(
        cog_admin,
        "ssf_recalcular",
        interaccion,
        miembro(777, "Nadie"),
    )

    assert "no está registrado" in interaccion.texto


# ============================================================
# FILEEXECUTE
# ============================================================

class AdjuntoFalso:
    """Doble mínimo de ``discord.Attachment`` para fileexecute."""

    def __init__(self, contenido=""):
        self.filename = "comandos.txt"
        self._contenido = contenido.encode("utf-8")
        self.size = len(self._contenido)

    async def read(self):
        return self._contenido


@pytest.fixture
def cog_en_arbol_ssf(desafio_ssf, admin_ids):
    """Cog /admin registrado en un árbol real, con desafío SSF creado."""

    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    async def cargar():
        await bot.load_extension("commands.admin")

    ejecutar(cargar())

    return bot.get_cog("Admin")


def interaccion_admin_con_miembro():
    interaccion = interaccion_admin()
    interaccion.guild = GuildFalso(
        GUILD,
        {USUARIO: miembro()},
    )
    return interaccion


def test_fileexecute_ejecuta_ssf_agregar_y_recalcular(
    cog_en_arbol_ssf,
    hoy_5_sep,
):
    registrar(1)
    sobrevivir([2, 3])

    interaccion = interaccion_admin_con_miembro()

    llamar(
        cog_en_arbol_ssf,
        "fileexecute",
        interaccion,
        AdjuntoFalso(
            "ssf agregar 42 2026-09-04\n"
            "ssf recalcular 42"
        ),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "✅ Línea 1" in interaccion.texto
    assert "✅ Línea 2" in interaccion.texto

    estado = obtener_estado_usuario(GUILD, USUARIO)
    assert estado["racha_actual"] == 4


def test_fileexecute_ejecuta_ssf_quitar(cog_en_arbol_ssf):
    registrar(1)
    sobrevivir([2, 3, 4])

    interaccion = interaccion_admin_con_miembro()

    llamar(
        cog_en_arbol_ssf,
        "fileexecute",
        interaccion,
        AdjuntoFalso("ssf quitar 42 2026-09-04"),
    )

    assert "✅ Línea 1" in interaccion.texto

    estado = obtener_estado_usuario(GUILD, USUARIO)
    assert estado["racha_actual"] == 3


def test_fileexecute_rechaza_ssf_quitar_sin_fecha(cog_en_arbol_ssf):
    registrar(1)

    interaccion = interaccion_admin_con_miembro()

    llamar(
        cog_en_arbol_ssf,
        "fileexecute",
        interaccion,
        AdjuntoFalso("ssf quitar 42"),
    )

    assert "requiere miembro y fecha" in interaccion.texto


def test_fileexecute_rechaza_ssf_recalcular_sin_miembro(
    cog_en_arbol_ssf,
):
    interaccion = interaccion_admin_con_miembro()

    llamar(
        cog_en_arbol_ssf,
        "fileexecute",
        interaccion,
        AdjuntoFalso("ssf recalcular"),
    )

    assert "requiere un miembro" in interaccion.texto
