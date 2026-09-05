"""Pruebas de los comandos de Madrugue ejecutados de punta a punta.

Cada comando se invoca a través de su callback real con una interacción falsa,
así que estas pruebas recorren el mismo camino que Discord.
"""

from datetime import datetime

import pytest

from modules.madrugue.services import registrar_madrugue
from tests.harness import InteraccionFalsa, construir_cog

GUILD = 1
USUARIO = 42


@pytest.fixture
def cog(base_datos_limpia):
    from commands.madrugue.cog import Madrugue
    from modules.madrugue.database import inicializar_db

    inicializar_db()

    return construir_cog(Madrugue)


def ejecutar(coro):
    import asyncio

    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coro
    )


def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return ejecutar(metodo(cog, interaccion, *args))


def fijar_hora(monkeypatch, hora, minuto=0):
    """Fija la hora que ve `/madrugue` (los puntos dependen de ella)."""

    import importlib

    # No se usa la forma de texto ("commands.madrugue.registro.ahora"):
    # load_extension registra el módulo en sys.modules sin colgarlo del
    # paquete padre, y si otro test cargó la extensión antes, la ruta con
    # puntos no se resuelve.
    registro = importlib.import_module("commands.madrugue.registro")

    monkeypatch.setattr(
        registro,
        "ahora",
        lambda: datetime(2026, 9, 5, hora, minuto),
    )


def registrar_servicio(hora, minuto=0, user_id=USUARIO, nombre="Tester"):
    return registrar_madrugue(
        GUILD,
        user_id,
        nombre,
        datetime(2026, 9, 5, hora, minuto),
    )


# ============================================================
# RESPUESTA BÁSICA
# ============================================================

@pytest.mark.parametrize(
    "comando",
    ["madrugue", "stats", "top", "ayuda"],
)
def test_comandos_responden(cog, comando):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, comando, interaccion)

    assert interaccion.cantidad_respuestas == 1, (
        f"/madrugue {comando} no respondió nada: Discord mostraría "
        "'la aplicación no responde'"
    )


def test_comandos_rechazan_mensajes_directos(cog):
    for comando in ("madrugue", "stats", "top"):
        interaccion = InteraccionFalsa(GUILD, USUARIO, en_servidor=False)

        llamar(cog, comando, interaccion)

        assert "dentro de un servidor" in interaccion.texto


def test_ayuda_funciona_por_mensaje_directo(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO, en_servidor=False)

    llamar(cog, "ayuda", interaccion)

    assert interaccion.cantidad_respuestas == 1


def test_extension_registra_comandos_de_primer_nivel(base_datos_limpia):
    """Los comandos conservan sus nombres: el árbol filtra por prefijo."""

    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    async def cargar():
        await bot.load_extension("commands.madrugue")

    ejecutar(cargar())

    nombres = {
        comando.qualified_name for comando in bot.tree.walk_commands()
    }

    assert nombres == {
        "madrugue",
        "madrugue_stats",
        "madrugue_top",
        "madrugue_ayuda",
    }


# ============================================================
# /madrugue
# ============================================================

def test_madrugue_registra(cog, monkeypatch):
    fijar_hora(monkeypatch, 5, 45)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "madrugue", interaccion)

    assert "Madrugaste" in interaccion.texto
    assert "**100**" in interaccion.texto
    assert "1 días" in interaccion.texto


def test_madrugue_dos_veces_informa(cog, monkeypatch):
    fijar_hora(monkeypatch, 5, 45)
    llamar(cog, "madrugue", InteraccionFalsa(GUILD, USUARIO))
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "madrugue", interaccion)

    assert "ya registraste" in interaccion.texto


def test_madrugue_fuera_de_horario_informa(cog, monkeypatch):
    fijar_hora(monkeypatch, 11, 0)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "madrugue", interaccion)

    assert "todavía no" in interaccion.texto
    assert "05:30 a 10:00" in interaccion.texto


# ============================================================
# CONSULTAS
# ============================================================

def test_stats_muestra_puntos_y_racha(cog):
    registrar_servicio(5, 45)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "stats", interaccion)

    assert "Puntos acumulados" in interaccion.texto
    assert "Mejor racha" in interaccion.texto
    assert "1 días" in interaccion.texto


def test_top_sin_registros_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "top", interaccion)

    assert "Todavía no hay madrugadores" in interaccion.texto


def test_top_muestra_ranking(cog):
    registrar_servicio(5, 45, user_id=USUARIO, nombre="Tester")
    registrar_servicio(8, 0, user_id=7, nombre="Otro")
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "top", interaccion)

    embed = interaccion.respuestas[-1].kwargs["embed"]

    assert embed.title == "🏆 TOP Madrugadores"
    assert "Tester" in embed.fields[0].value
    assert "Otro" in embed.fields[0].value


def test_ayuda_muestra_los_comandos(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "ayuda", interaccion)

    embed = interaccion.respuestas[-1].kwargs["embed"]

    assert embed.title == "🌅 Ayuda de Madrugue"
    assert "/madrugue" in embed.fields[0].name
