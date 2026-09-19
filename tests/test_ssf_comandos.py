"""Pruebas de los comandos de SeptSinFP ejecutados de punta a punta.

Cada comando se invoca a través de su callback real con una interacción falsa,
así que estas pruebas recorren el mismo camino que Discord.
"""

from datetime import datetime, timedelta

import pytest

from core.utils import ahora
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


def hoy():
    """Fecha local del bot, igual que la que usan los comandos."""

    return ahora().date()


@pytest.fixture
async def cog(base_datos_limpia):
    from commands.ssf.cog import Ssf
    from modules.ssf.database import inicializar_db

    await inicializar_db()

    hoy_actual = hoy()

    resultado = await iniciar_desafio(
        GUILD,
        NOMBRE,
        hoy_actual - timedelta(days=6),
        hoy_actual + timedelta(days=30),
        CANAL,
    )

    assert resultado["exitoso"]

    return construir_cog(Ssf)


@pytest.fixture
async def cog_sin_desafio(base_datos_limpia):
    from commands.ssf.cog import Ssf
    from modules.ssf.database import inicializar_db

    await inicializar_db()

    return construir_cog(Ssf)





async def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return await metodo(cog, interaccion, *args)


def mediodia(hace_dias):
    return datetime.combine(
        hoy() - timedelta(days=hace_dias),
        datetime.min.time(),
    ).replace(hour=12)


async def registrar_servicio(hace_dias=0, user_id=USUARIO, nombre="Tester"):
    return await registrar_usuario(
        GUILD,
        user_id,
        nombre,
        mediodia(hace_dias),
    )


async def sobrevivir_servicio(hace_dias, user_id=USUARIO):
    resultado = await registrar_sobrevivi(
        GUILD,
        user_id,
        mediodia(hace_dias),
    )
    assert resultado["exitoso"], f"hace {hace_dias} días: {resultado!r}"


async def escenario_eliminado_con_racha_6():
    """Registra hace 6 días, cumple 5 más y pierde hoy por faltar."""

    await registrar_servicio(hace_dias=6)

    for hace_dias in (5, 4, 3, 2, 1):
        await sobrevivir_servicio(hace_dias)

    assert await eliminar_faltantes(GUILD, hoy()) == 1


# ============================================================
# RESPUESTA BÁSICA
# ============================================================

@pytest.mark.parametrize(
    "comando",
    ["registrar", "sobrevivi", "estado", "participantes", "ayuda"],
)
async def test_comandos_responden(cog, comando):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, comando, interaccion)

    assert interaccion.cantidad_respuestas == 1, (
        f"/ssf {comando} no respondió nada: Discord mostraría "
        "'la aplicación no responde'"
    )
    assert interaccion.texto


async def test_comandos_rechazan_mensajes_directos(cog):
    for comando in ("registrar", "sobrevivi", "estado", "participantes"):
        interaccion = InteraccionFalsa(GUILD, USUARIO, en_servidor=False)

        await llamar(cog, comando, interaccion)

        assert "dentro de un servidor" in interaccion.texto


async def test_extensiones_ssf_y_admin_conviven(base_datos_limpia):
    """El grupo /ssf de usuarios coexiste con /admin ssf."""

    import asyncio
    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    # El cog de SSF arranca su revisión diaria al cargarse; se la cancela al
    # final para no dejar tareas pendientes.
    try:
        await bot.load_extension("commands.admin")
        await bot.load_extension("commands.ssf")

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
        await asyncio.sleep(0)


# ============================================================
# /ssf registrar
# ============================================================

async def test_registrar_anota_al_usuario(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "registrar", interaccion)

    assert "se registró" in interaccion.texto
    assert NOMBRE in interaccion.texto
    assert "1 días" in interaccion.texto


async def test_registrar_muestra_el_nombre_del_servidor(cog):
    """La confirmación muestra el nombre/apodo del servidor, no el ID."""

    interaccion = InteraccionFalsa(GUILD, USUARIO, nombre="ApodoEnServer")

    await llamar(cog, "registrar", interaccion)

    assert "ApodoEnServer" in interaccion.texto
    assert "<@" not in interaccion.texto


async def test_registrar_dos_veces_informa(cog):
    await llamar(cog, "registrar", InteraccionFalsa(GUILD, USUARIO))
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "registrar", interaccion)

    assert "Ya estás registrado" in interaccion.texto


async def test_registrar_sin_desafio_informa(cog_sin_desafio):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog_sin_desafio, "registrar", interaccion)

    assert "No hay un desafío SeptSinFP activo" in interaccion.texto


# ============================================================
# /ssf sobrevivi
# ============================================================

async def test_sobrevivi_sin_registro_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "sobrevivi", interaccion)

    assert "No estás registrado" in interaccion.texto


async def test_sobrevivi_el_dia_de_registro_no_duplica(cog):
    await llamar(cog, "registrar", InteraccionFalsa(GUILD, USUARIO))
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "sobrevivi", interaccion)

    assert "Ya registraste tu supervivencia de hoy" in interaccion.texto


async def test_sobrevivi_al_dia_siguiente_suma_racha(cog):
    await registrar_servicio(hace_dias=1)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "sobrevivi", interaccion)

    assert "sobrevivió" in interaccion.texto
    assert "2 días" in interaccion.texto


async def test_sobrevivi_muestra_el_nombre_del_servidor(cog):
    """La confirmación muestra el nombre/apodo del servidor, no el ID."""

    await registrar_servicio(hace_dias=1)
    interaccion = InteraccionFalsa(GUILD, USUARIO, nombre="ApodoEnServer")

    await llamar(cog, "sobrevivi", interaccion)

    assert "¡ApodoEnServer sobrevivió" in interaccion.texto
    assert "<@" not in interaccion.texto


# ============================================================
# /ssf estado
# ============================================================

async def test_estado_muestra_rango_y_rachas(cog):
    await registrar_servicio(hace_dias=1)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "estado", interaccion)

    assert "Soldado 🪖" in interaccion.texto
    assert "1 días" in interaccion.texto
    assert interaccion.respuestas[-1].efimero


async def test_estado_sin_registro_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "estado", interaccion)

    assert "No estás registrado" in interaccion.texto


async def test_estado_del_eliminado_conserva_racha_y_rango(cog):
    await escenario_eliminado_con_racha_6()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "estado", interaccion)

    assert "Tercer Sargento 🥉" in interaccion.texto
    assert "6 días" in interaccion.texto
    assert "Eliminado" in interaccion.texto


# ============================================================
# /ssf participantes
# ============================================================

async def test_participantes_sin_desafio_informa(cog_sin_desafio):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog_sin_desafio, "participantes", interaccion)

    assert "No hay un desafío SeptSinFP activo" in interaccion.texto


async def test_participantes_sin_lista_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "participantes", interaccion)

    assert "Todavía no hay participantes" in interaccion.texto


async def test_participantes_muestra_activos_y_rangos(cog):
    await registrar_servicio(hace_dias=0, user_id=USUARIO, nombre="Tester")
    await registrar_servicio(hace_dias=1, user_id=7, nombre="Otro")
    await sobrevivir_servicio(0, user_id=7)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "participantes", interaccion)

    assert "2 activos, 0 eliminados" in interaccion.texto
    assert "Tester" in interaccion.texto
    assert "Otro" in interaccion.texto
    assert "Soldado 🪖" in interaccion.texto


async def test_participantes_muestra_eliminado_con_su_racha(cog):
    await escenario_eliminado_con_racha_6()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "participantes", interaccion)

    assert "0 activos, 1 eliminados" in interaccion.texto
    assert "💀" in interaccion.texto
    assert "Tester" in interaccion.texto
    assert "6 días" in interaccion.texto
    assert "Tercer Sargento 🥉" in interaccion.texto


# ============================================================
# /ssf ayuda
# ============================================================

async def test_ayuda_envia_mensaje_directo(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "ayuda", interaccion)

    assert interaccion.user.mensajes_directos
    assert "Ayuda de SeptSinFP" in interaccion.user.mensajes_directos[0]
    assert "mensaje directo" in interaccion.texto


async def test_ayuda_sin_mensajes_directos_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)
    interaccion.user.dm_abierto = False

    await llamar(cog, "ayuda", interaccion)

    assert "No pude enviarte un mensaje directo" in interaccion.texto
