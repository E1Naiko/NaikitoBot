"""Sincronización automática del canal 420 (``core.lahora_sync``).

Cubre lo que el comando admin no ejercita directamente: varios servidores
a la vez, resolución de canales por ``fetch_channel`` y la tarea que
dispara ``on_ready``.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from config import TIMEZONE
from core.lahora_sync import sincronizar_lahora
from modules.lahora.database import guardar_ultimo_chequeo, obtener_ultimo_chequeo
from modules.lahora.services import obtener_top_lahora
from tests.harness import GuildFalso, prohibido

GUILD_UNO = 1
GUILD_DOS = 2
CANAL_UNO = 420
CANAL_DOS = 421


def local(hora, minuto, segundo=0, dia=5, mes=9, anio=2026):
    return datetime(anio, mes, dia, hora, minuto, segundo, tzinfo=TIMEZONE)


class _Autor:
    def __init__(self, user_id, nombre, bot=False):
        self.id = user_id
        self.display_name = nombre
        self.bot = bot


class MensajeHistorial:
    _siguiente = 9000

    def __init__(self, contenido, momento, user_id=1, nombre="Tester", bot=False):
        MensajeHistorial._siguiente += 1
        self.id = MensajeHistorial._siguiente
        self.content = contenido
        self.created_at = momento.astimezone(timezone.utc)
        self.edited_at = None
        self.author = _Autor(user_id, nombre, bot)


class CanalConHistorial:
    def __init__(self, mensajes, canal_id=CANAL_UNO, guild=None):
        self.id = canal_id
        self.guild = guild
        self._mensajes = list(mensajes)
        self.llamadas = []

    def agregar(self, mensaje):
        self._mensajes.append(mensaje)

    def history(self, limit=None, after=None, oldest_first=None):
        self.llamadas.append({"limit": limit, "after": after, "oldest_first": oldest_first})

        async def generar():
            ordenados = sorted(self._mensajes, key=lambda m: m.created_at)
            for mensaje in ordenados:
                if after is not None and mensaje.created_at <= after:
                    continue
                yield mensaje

        return generar()


class CanalProhibido(CanalConHistorial):
    def history(self, limit=None, after=None, oldest_first=None):
        async def generar():
            raise prohibido()
            yield  # pragma: no cover - nunca se ejecuta

        return generar()


class _GuildConFachada(GuildFalso):
    """``GuildFalso`` con ``get_channel`` que devuelve ``None`` a propósito."""


class BotFalso:
    def __init__(self, guilds, canales_externos=None):
        self.guilds = guilds
        self._canales_externos = canales_externos or {}

    async def fetch_channel(self, canal_id):
        canal = self._canales_externos.get(canal_id)

        if canal is None:
            raise prohibido()

        return canal


@pytest.fixture(autouse=True)
async def _db(base_datos_limpia):
    from modules.lahora.database import inicializar_db

    await inicializar_db()


# ============================================================
# CHECKPOINT (persistencia)
# ============================================================

async def test_checkpoint_nuevo_es_none():
    assert await obtener_ultimo_chequeo(CANAL_UNO) is None


async def test_checkpoint_se_guarda_y_se_actualiza():
    momento = local(16, 20, 0)
    await guardar_ultimo_chequeo(GUILD_UNO, CANAL_UNO, momento)
    assert await obtener_ultimo_chequeo(CANAL_UNO) == momento

    mas_tarde = local(16, 25, 0)
    await guardar_ultimo_chequeo(GUILD_UNO, CANAL_UNO, mas_tarde)
    assert await obtener_ultimo_chequeo(CANAL_UNO) == mas_tarde


# ============================================================
# SINCRONIZACIÓN
# ============================================================

async def test_sincroniza_varios_servidores_y_canales(monkeypatch):
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_UNO, CANAL_DOS})

    canal_uno = CanalConHistorial(
        [MensajeHistorial("420", local(16, 20, 3), user_id=1, nombre="Uno")],
        canal_id=CANAL_UNO,
    )
    canal_dos = CanalConHistorial(
        [MensajeHistorial("4:20", local(4, 20, 1, dia=6), user_id=2, nombre="Dos")],
        canal_id=CANAL_DOS,
    )
    guild_uno = GuildFalso(GUILD_UNO, canales={CANAL_UNO: canal_uno})
    guild_dos = GuildFalso(GUILD_DOS, canales={CANAL_DOS: canal_dos})
    bot = BotFalso([guild_uno, guild_dos])

    resultados = await sincronizar_lahora(bot)

    assert len(resultados) == 2
    assert {r.guild_id for r in resultados} == {GUILD_UNO, GUILD_DOS}
    assert all(r.error is None and r.resumen.importados == 1 for r in resultados)
    assert len(await obtener_top_lahora(GUILD_UNO)) == 1
    assert len(await obtener_top_lahora(GUILD_DOS)) == 1


async def test_segunda_corrida_solo_mira_los_mensajes_nuevos(monkeypatch):
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_UNO})

    canal = CanalConHistorial([
        MensajeHistorial("420", local(16, 20, 3), user_id=1, nombre="Uno"),
    ])
    guild = GuildFalso(GUILD_UNO, canales={CANAL_UNO: canal})
    bot = BotFalso([guild])

    primera = await sincronizar_lahora(bot)
    assert primera[0].resumen.importados == 1
    assert primera[0].resumen.revisados == 1

    # Nada pasó todavía: la segunda corrida no debería reimportar nada.
    segunda = await sincronizar_lahora(bot)
    assert segunda[0].resumen.importados == 0
    assert segunda[0].resumen.revisados == 0
    assert len(await obtener_top_lahora(GUILD_UNO)) == 1

    # Llega un 420 mientras el bot está "offline" otra vez.
    canal.agregar(
        MensajeHistorial("420", local(16, 20, 4, dia=6, anio=2099), user_id=2, nombre="Dos")
    )
    tercera = await sincronizar_lahora(bot)
    assert tercera[0].resumen.importados == 1
    assert len(await obtener_top_lahora(GUILD_UNO)) == 2


async def test_sin_canales_configurados_no_hace_nada(monkeypatch):
    monkeypatch.setattr("config.LAHORA_CANALES_ID", set())
    bot = BotFalso([GuildFalso(GUILD_UNO)])

    assert await sincronizar_lahora(bot) == []


async def test_canal_no_cacheado_se_resuelve_con_fetch_channel(monkeypatch):
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_UNO})

    guild = GuildFalso(GUILD_UNO, canales={})  # get_channel no lo tiene
    canal = CanalConHistorial(
        [MensajeHistorial("420", local(16, 20, 3))],
        canal_id=CANAL_UNO,
        guild=guild,
    )
    bot = BotFalso([guild], canales_externos={CANAL_UNO: canal})

    resultados = await sincronizar_lahora(bot)

    assert len(resultados) == 1
    assert resultados[0].resumen.importados == 1


async def test_canal_de_otro_guild_no_se_usa(monkeypatch):
    """``fetch_channel`` no filtra por guild: el bot sí lo hace."""

    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_UNO})

    otro_guild = GuildFalso(99)
    canal_de_otro_guild = CanalConHistorial(
        [MensajeHistorial("420", local(16, 20, 3))],
        canal_id=CANAL_UNO,
        guild=otro_guild,
    )
    guild = GuildFalso(GUILD_UNO, canales={})
    bot = BotFalso([guild], canales_externos={CANAL_UNO: canal_de_otro_guild})

    resultados = await sincronizar_lahora(bot)

    assert resultados == []


async def test_canal_sin_permiso_no_rompe_la_corrida(monkeypatch):
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_UNO})

    canal = CanalProhibido([], canal_id=CANAL_UNO)
    guild = GuildFalso(GUILD_UNO, canales={CANAL_UNO: canal})
    bot = BotFalso([guild])

    resultados = await sincronizar_lahora(bot)

    assert len(resultados) == 1
    assert resultados[0].error is not None
    assert "permiso" in resultados[0].error
    # Un canal sin permiso no deja marca: se reintenta en la próxima corrida.
    assert await obtener_ultimo_chequeo(CANAL_UNO) is None


async def test_no_corre_dos_veces_en_simultaneo(monkeypatch):
    from core.lahora_sync import candado_sincronizacion

    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_UNO})
    bot = BotFalso([GuildFalso(GUILD_UNO)])

    async with candado_sincronizacion:
        assert await sincronizar_lahora(bot) == []


# ============================================================
# AUTO-SINCRONIZACIÓN AL CONECTAR (on_ready)
# ============================================================

async def test_on_ready_dispara_la_sincronizacion(monkeypatch):
    """``NaikitoBot.on_ready`` debe disparar la recuperación automática."""

    import discord
    from discord.ext import tasks

    from core.bot import NaikitoBot

    monkeypatch.setattr(tasks.Loop, "start", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_UNO})

    canal = CanalConHistorial([MensajeHistorial("420", local(16, 20, 3))])
    guild = GuildFalso(GUILD_UNO, canales={CANAL_UNO: canal})

    bot = NaikitoBot()
    monkeypatch.setattr(type(bot), "guilds", property(lambda self: [guild]))

    await bot.on_ready()

    # on_ready dispara la sincronización en una tarea aparte: hay que
    # esperar a que el loop la procese antes de afirmar sobre el resultado.
    tareas = [
        tarea
        for tarea in asyncio.all_tasks()
        if tarea.get_coro().cr_code.co_name == "_sincronizar_lahora_al_conectar"
    ]
    for tarea in tareas:
        await tarea

    assert len(await obtener_top_lahora(GUILD_UNO)) == 1
