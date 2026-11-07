"""Pruebas de las líneas de terminal del canal 420.

Se verifica qué se imprime (y qué no) cuando hay novedades del ranking: el
registro en vivo, el podio, el alta manual y el resumen al cerrar cada
ventana.
"""

from datetime import datetime

import pytest

from config import TIMEZONE
from tests.harness import InteraccionFalsa, construir_cog

GUILD = 1
USUARIO = 42
OTRO = 43
CANAL_420 = 420


def local(hora=16, minuto=20, segundo=0, dia=5):
    return datetime(2026, 9, dia, hora, minuto, segundo, tzinfo=TIMEZONE)


class Autor:
    def __init__(self, user_id, nombre, bot=False):
        self.id = user_id
        self.display_name = nombre
        self.bot = bot


class Canal:
    def __init__(self, canal_id):
        self.id = canal_id


class Guild:
    def __init__(self, guild_id):
        self.id = guild_id


class Mensaje:
    _siguiente_id = 5000

    def __init__(self, contenido, momento, user_id=USUARIO, nombre="Tester", canal=CANAL_420):
        Mensaje._siguiente_id += 1
        self.id = Mensaje._siguiente_id
        self.content = contenido
        self.created_at = momento
        self.author = Autor(user_id, nombre)
        self.channel = Canal(canal)
        self.guild = Guild(GUILD)
        self.reacciones = []

    async def add_reaction(self, emoji):
        self.reacciones.append(emoji)


@pytest.fixture
async def cog(base_datos_limpia, monkeypatch):
    from commands.lahora.cog import LaHora
    from modules.lahora.database import inicializar_db

    await inicializar_db()
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_420})

    return construir_cog(LaHora)


async def enviar(cog, mensaje):
    await type(cog).on_message(cog, mensaje)
    return mensaje


# ============================================================
# LÍNEAS DE LA TERMINAL
# ============================================================

def test_linea_registro_incluye_nombre_puntos_y_posicion():
    from core.lahora_logs import linea_registro
    from modules.lahora.services import ResultadoLaHora

    resultado = ResultadoLaHora(
        exitoso=True,
        motivo="registrado",
        momento=local(segundo=5),
        ventana="16:20",
        segundos=5,
        posicion=2,
        puntos_finales=17.5,
    )

    linea = linea_registro(resultado, "Tester", USUARIO, mensaje_id=99)

    assert "[420] ✅ Tester (42)" in linea
    assert "05/09 16:20:05" in linea
    assert "ventana=16:20" in linea
    assert "posicion=2" in linea
    assert "puntos=17.5" in linea
    assert "mensaje=99" in linea


def test_linea_registro_marca_los_manuales():
    from core.lahora_logs import linea_registro
    from modules.lahora.services import ResultadoLaHora

    resultado = ResultadoLaHora(
        exitoso=True, motivo="registrado", momento=local(), ventana="16:20",
    )

    assert "manual=true" in linea_registro(resultado, "Tester", USUARIO, manual=True)


def test_linea_podio_solo_para_los_tres_primeros():
    from core.lahora_logs import linea_podio
    from modules.lahora.services import ResultadoLaHora

    def resultado(posicion):
        return ResultadoLaHora(
            exitoso=True, motivo="registrado", momento=local(), ventana="16:20",
            posicion=posicion, puntos_finales=10,
        )

    assert "🥇 podio" in linea_podio(resultado(1), "Tester", USUARIO)
    assert "🥈 podio" in linea_podio(resultado(2), "Tester", USUARIO)
    assert "🥉 podio" in linea_podio(resultado(3), "Tester", USUARIO)
    assert linea_podio(resultado(4), "Tester", USUARIO) is None


def test_linea_resumen_ventana_lista_el_podio():
    from core.lahora_logs import linea_resumen_ventana

    filas = [
        (1, "Primero", 2, 20.0),
        (2, "Segundo", 5, 18.0),
        (3, "Tercero", 9, 15.0),
        (4, "Cuarto", 15, 12.0),
    ]

    linea = linea_resumen_ventana(datetime(2026, 9, 5).date(), "16:20", filas)

    assert "📊 cierre 05/09 ventana=16:20" in linea
    assert "participantes=4" in linea
    assert "1. Primero 20 pts" in linea
    assert "3. Tercero 15 pts" in linea
    assert "Cuarto" not in linea


def test_linea_resumen_ventana_vacia_no_imprime():
    from core.lahora_logs import linea_resumen_ventana

    assert linea_resumen_ventana(local().date(), "16:20", []) is None


@pytest.mark.parametrize(
    "momento, esperada",
    [
        (local(hora=16, minuto=21, segundo=5), "16:20"),
        (local(hora=4, minuto=21, segundo=5), "04:20"),
        # El latido es cada 60 s: la tolerancia llega hasta los 90 s.
        (local(hora=16, minuto=22, segundo=20), "16:20"),
        (local(hora=16, minuto=23, segundo=30), None),
        (local(hora=15, minuto=59), None),
    ],
)
def test_ventana_recien_cerrada(momento, esperada):
    from core.lahora_logs import ventana_recien_cerrada

    cerrada = ventana_recien_cerrada(momento)

    assert (cerrada[1].strftime("%H:%M") if cerrada else None) == esperada


# ============================================================
# LISTENER
# ============================================================

async def test_el_420_valido_se_imprime_con_nombre_y_podio(cog, capsys):
    await enviar(cog, Mensaje("420", local(segundo=3), nombre="Tester"))
    capsys.readouterr()

    await enviar(cog, Mensaje("420", local(segundo=8), user_id=OTRO, nombre="Otro"))
    salida = capsys.readouterr().out

    assert "[420] ✅ Otro (43)" in salida
    assert "posicion=2" in salida
    assert "🥈 podio" in salida


async def test_fuera_de_horario_no_ensucia_la_terminal(cog, capsys):
    await enviar(cog, Mensaje("420", local(hora=12, minuto=0)))
    assert capsys.readouterr().out == ""


async def test_repetido_no_ensucia_la_terminal(cog, capsys):
    await enviar(cog, Mensaje("420", local(segundo=1)))
    capsys.readouterr()

    await enviar(cog, Mensaje("420", local(segundo=30)))
    assert capsys.readouterr().out == ""


async def test_mensaje_que_no_es_420_no_se_imprime(cog, capsys):
    await enviar(cog, Mensaje("hola 420 gente", local()))
    assert capsys.readouterr().out == ""


async def test_el_sancionado_deja_una_linea_clara(cog, capsys):
    from modules.sanciones.services import aplicar_sancion

    await aplicar_sancion(GUILD, USUARIO, "lahora", "trampa")

    mensaje = await enviar(cog, Mensaje("420", local(), nombre="Tramposo"))
    salida = capsys.readouterr().out

    assert "[420] ⛔ sanción vigente Tramposo (42)" in salida
    assert "420 no registrado" in salida
    assert mensaje.reacciones == []


# ============================================================
# ALTA MANUAL
# ============================================================

async def test_el_alta_manual_queda_en_la_terminal(cog, monkeypatch, capsys):
    from commands.admin.cog import Admin
    from core.utils import ahora

    monkeypatch.setattr("core.permissions.ADMIN_USER_IDS", {USUARIO})

    momento = ahora().replace(hour=16, minute=20, second=7, microsecond=0)
    monkeypatch.setattr("commands.admin.lahora.ahora", lambda: momento)

    admin = construir_cog(Admin)
    interaccion = InteraccionFalsa(GUILD, USUARIO, nombre="Admin")
    usuario = type("M", (), {"id": OTRO, "display_name": "Manual", "mention": "<@43>"})()

    await type(admin).lahora_manualadd.callback(
        admin, interaccion, usuario, momento.strftime("%Y-%m-%d"), "16:20:07",
    )

    salida = capsys.readouterr().out

    assert "[420] ✅ Manual (43)" in salida
    assert "manual=true" in salida
    assert "🥇 podio" in salida


# ============================================================
# RESUMEN DE LA VENTANA AL CERRAR
# ============================================================

async def test_la_ventana_cerrada_se_resume_una_sola_vez(cog, monkeypatch, capsys):
    from commands.lahora import tareas as modulo_tareas
    from modules.lahora.services import registrar_lahora

    await registrar_lahora(GUILD, USUARIO, "Primero", local(segundo=2))
    await registrar_lahora(GUILD, OTRO, "Segundo", local(segundo=9))
    capsys.readouterr()

    monkeypatch.setattr(
        modulo_tareas, "ahora", lambda: local(hora=16, minuto=21, segundo=1)
    )

    class GuildFalso:
        id = GUILD

    monkeypatch.setattr(
        cog,
        "bot",
        type("B", (), {"guilds": [GuildFalso()]})(),
    )

    await type(cog).resumir_ventanas.coro(cog)
    salida = capsys.readouterr().out

    assert "[420] 📊 cierre 05/09 ventana=16:20" in salida
    assert "participantes=2" in salida
    assert "Primero" in salida
    assert f"servidor={GUILD}" in salida

    # Un segundo latido no vuelve a imprimir la misma ventana.
    await type(cog).resumir_ventanas.coro(cog)
    assert capsys.readouterr().out == ""


async def test_ventana_sin_participantes_no_imprime(cog, monkeypatch, capsys):
    from commands.lahora import tareas as modulo_tareas

    monkeypatch.setattr(
        modulo_tareas, "ahora", lambda: local(hora=16, minuto=21, segundo=1)
    )
    monkeypatch.setattr(
        cog,
        "bot",
        type("B", (), {"guilds": [type("G", (), {"id": GUILD})()]})(),
    )

    await type(cog).resumir_ventanas.coro(cog)

    assert capsys.readouterr().out == ""


async def test_la_tarea_arranca_y_se_cancela_con_el_cog(base_datos_limpia, monkeypatch):
    """Registrar el cog arranca el resumen; descargarlo lo detiene."""

    import discord
    from discord.ext import commands, tasks

    from commands.lahora.cog import LaHora

    iniciadas = []
    monkeypatch.setattr(
        tasks.Loop, "start", lambda self, *args, **kwargs: iniciadas.append(self)
    )
    monkeypatch.setattr(tasks.Loop, "cancel", lambda self: iniciadas.remove(self))

    bot = commands.Bot(command_prefix="$!", intents=discord.Intents.default())
    cog = LaHora(bot)

    await cog.cog_load()

    assert cog.resumir_ventanas in iniciadas
    assert cog._ventanas_resumidas == set()

    cog.cog_unload()

    assert iniciadas == []
