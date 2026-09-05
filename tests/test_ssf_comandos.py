"""Pruebas de los comandos de SeptSinFP ejecutados de punta a punta.

Cada comando se invoca a través de su callback real con una interacción falsa,
así que estas pruebas recorren el mismo camino que Discord.
"""

from datetime import date, datetime, timedelta

import pytest

from modules.ssf.services import (
    eliminar_faltantes,
    iniciar_desafio,
    registrar_sobrevivi,
    registrar_usuario,
)
from tests.harness import InteraccionFalsa, construir_cog

GUILD = 1
USUARIO = 42
CANAL = 99

NOMBRE = "SeptiembreSinFAP"


@pytest.fixture
def cog(base_datos_limpia):
    from commands.ssf.cog import Ssf
    from modules.ssf.database import inicializar_db

    inicializar_db()

    hoy = date.today()

    resultado = iniciar_desafio(
        GUILD,
        NOMBRE,
        (hoy - timedelta(days=6)).isoformat(),
        (hoy + timedelta(days=30)).isoformat(),
        CANAL,
    )

    assert resultado["exitoso"]

    return construir_cog(Ssf)


@pytest.fixture
def cog_sin_desafio(base_datos_limpia):
    from commands.ssf.cog import Ssf
    from modules.ssf.database import inicializar_db

    inicializar_db()

    return construir_cog(Ssf)


def ejecutar(coro):
    import asyncio

    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coro
    )


def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return ejecutar(metodo(cog, interaccion, *args))


def mediodia(hace_dias):
    return datetime.combine(
        date.today() - timedelta(days=hace_dias),
        datetime.min.time(),
    ).replace(hour=12)


def registrar_servicio(hace_dias=0, user_id=USUARIO, nombre="Tester"):
    return registrar_usuario(
        GUILD,
        user_id,
        nombre,
        mediodia(hace_dias),
    )


def sobrevivir_servicio(hace_dias, user_id=USUARIO):
    resultado = registrar_sobrevivi(
        GUILD,
        user_id,
        mediodia(hace_dias),
    )
    assert resultado["exitoso"], f"hace {hace_dias} días: {resultado!r}"


def escenario_eliminado_con_racha_6():
    """Registra hace 6 días, cumple 5 más y pierde hoy por faltar."""

    registrar_servicio(hace_dias=6)

    for hace_dias in (5, 4, 3, 2, 1):
        sobrevivir_servicio(hace_dias)

    assert eliminar_faltantes(GUILD, date.today()) == 1


# ============================================================
# RESPUESTA BÁSICA
# ============================================================

@pytest.mark.parametrize(
    "comando",
    ["registrar", "sobrevivi", "estado", "participantes", "ayuda"],
)
def test_comandos_responden(cog, comando):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, comando, interaccion)

    assert interaccion.cantidad_respuestas == 1, (
        f"/ssf {comando} no respondió nada: Discord mostraría "
        "'la aplicación no responde'"
    )
    assert interaccion.texto


def test_comandos_rechazan_mensajes_directos(cog):
    for comando in ("registrar", "sobrevivi", "estado", "participantes"):
        interaccion = InteraccionFalsa(GUILD, USUARIO, en_servidor=False)

        llamar(cog, comando, interaccion)

        assert "dentro de un servidor" in interaccion.texto


def test_extensiones_ssf_y_admin_conviven(base_datos_limpia):
    """El grupo /ssf de usuarios coexiste con /admin ssf."""

    import asyncio
    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    # El cog de SSF arranca su revisión diaria al cargarse; se usa un loop
    # propio para cancelarla y cerrarlo sin dejar tareas pendientes.
    loop = asyncio.new_event_loop()

    try:
        async def cargar():
            await bot.load_extension("commands.admin")
            await bot.load_extension("commands.ssf")

        loop.run_until_complete(cargar())

        nombres = {
            comando.qualified_name for comando in bot.tree.walk_commands()
        }

        for comando in (
            "registrar",
            "sobrevivi",
            "estado",
            "participantes",
            "ayuda",
        ):
            assert f"ssf {comando}" in nombres

        assert "admin ssf revivir" in nombres
        assert "admin ssf iniciar" in nombres
    finally:
        bot.get_cog("Ssf").procesar_ssf_automatico.cancel()
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


# ============================================================
# /ssf registrar
# ============================================================

def test_registrar_anota_al_usuario(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "registrar", interaccion)

    assert "se registró" in interaccion.texto
    assert NOMBRE in interaccion.texto
    assert "1 días" in interaccion.texto


def test_registrar_dos_veces_informa(cog):
    llamar(cog, "registrar", InteraccionFalsa(GUILD, USUARIO))
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "registrar", interaccion)

    assert "Ya estás registrado" in interaccion.texto


def test_registrar_sin_desafio_informa(cog_sin_desafio):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog_sin_desafio, "registrar", interaccion)

    assert "No hay un desafío SeptSinFP activo" in interaccion.texto


# ============================================================
# /ssf sobrevivi
# ============================================================

def test_sobrevivi_sin_registro_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "sobrevivi", interaccion)

    assert "No estás registrado" in interaccion.texto


def test_sobrevivi_el_dia_de_registro_no_duplica(cog):
    llamar(cog, "registrar", InteraccionFalsa(GUILD, USUARIO))
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "sobrevivi", interaccion)

    assert "Ya registraste tu supervivencia de hoy" in interaccion.texto


def test_sobrevivi_al_dia_siguiente_suma_racha(cog):
    registrar_servicio(hace_dias=1)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "sobrevivi", interaccion)

    assert "sobrevivió" in interaccion.texto
    assert "2 días" in interaccion.texto


# ============================================================
# /ssf estado
# ============================================================

def test_estado_muestra_rango_y_rachas(cog):
    registrar_servicio(hace_dias=1)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "estado", interaccion)

    assert "Soldado 🪖" in interaccion.texto
    assert "1 días" in interaccion.texto
    assert interaccion.respuestas[-1].efimero


def test_estado_sin_registro_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "estado", interaccion)

    assert "No estás registrado" in interaccion.texto


def test_estado_del_eliminado_conserva_racha_y_rango(cog):
    escenario_eliminado_con_racha_6()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "estado", interaccion)

    assert "Tercer Sargento 🥉" in interaccion.texto
    assert "6 días" in interaccion.texto
    assert "Eliminado" in interaccion.texto


# ============================================================
# /ssf participantes
# ============================================================

def test_participantes_sin_desafio_informa(cog_sin_desafio):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog_sin_desafio, "participantes", interaccion)

    assert "No hay un desafío SeptSinFP activo" in interaccion.texto


def test_participantes_sin_lista_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "participantes", interaccion)

    assert "Todavía no hay participantes" in interaccion.texto


def test_participantes_muestra_activos_y_rangos(cog):
    registrar_servicio(hace_dias=0, user_id=USUARIO, nombre="Tester")
    registrar_servicio(hace_dias=1, user_id=7, nombre="Otro")
    sobrevivir_servicio(0, user_id=7)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "participantes", interaccion)

    assert "2 activos, 0 eliminados" in interaccion.texto
    assert "Tester" in interaccion.texto
    assert "Otro" in interaccion.texto
    assert "Soldado 🪖" in interaccion.texto


def test_participantes_muestra_eliminado_con_su_racha(cog):
    escenario_eliminado_con_racha_6()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "participantes", interaccion)

    assert "0 activos, 1 eliminados" in interaccion.texto
    assert "💀" in interaccion.texto
    assert "Tester" in interaccion.texto
    assert "6 días" in interaccion.texto
    assert "Tercer Sargento 🥉" in interaccion.texto


# ============================================================
# /ssf ayuda
# ============================================================

def test_ayuda_envia_mensaje_directo(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "ayuda", interaccion)

    assert interaccion.user.mensajes_directos
    assert "Ayuda de SeptSinFP" in interaccion.user.mensajes_directos[0]
    assert "mensaje directo" in interaccion.texto


def test_ayuda_sin_mensajes_directos_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)
    interaccion.user.dm_abierto = False

    llamar(cog, "ayuda", interaccion)

    assert "No pude enviarte un mensaje directo" in interaccion.texto
