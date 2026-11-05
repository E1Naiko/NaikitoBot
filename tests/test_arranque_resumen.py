"""El arranque informa carga real sin enumerar todo el árbol de comandos."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from core.bot import NaikitoBot
from tests.harness import GuildFalso


@pytest.mark.parametrize("guild_id", [None, 123456789])
async def test_setup_y_resumen_de_arranque(base_datos_limpia, monkeypatch, capsys, guild_id):
    monkeypatch.setattr("core.bot.GUILD_ID", guild_id)
    monkeypatch.setattr("core.bot.version_bot", lambda: "NaikitoBot2.0.1.prueba")
    bot = NaikitoBot()
    # Evita que discord.py retire los módulos de sys.modules al cerrar: otras
    # pruebas ya tienen referencias a las mismas clases durante la colección.
    monkeypatch.setattr(bot, "unload_extension", AsyncMock())
    monkeypatch.setattr(type(bot), "guilds", property(lambda _: [
        GuildFalso(22, nombre="Zeta"), GuildFalso(11, nombre="Alfa"),
    ]))
    monkeypatch.setattr(bot.tree, "sync", AsyncMock(return_value=[object(), object()]))
    monkeypatch.setattr(bot, "_sincronizar_lahora_al_conectar", AsyncMock())

    async with bot:
        await bot.setup_hook()
        # El setup no imprime árboles, nombres de comandos ni opciones.
        assert capsys.readouterr().out == ""
        await bot.on_ready()
        await asyncio.sleep(0)
        salida = capsys.readouterr().out
        assert "NaikitoBot2.0.1.prueba" in salida
        assert "Base de datos: inicializada" in salida
        assert "Funciones (estado de carga local)" in salida
        for nombre in ("General", "Madrugue", "420", "Administración", "SeptSinFP", "Box"):
            assert f"{nombre}: cargado" in salida
        assert "Box acciones=activa" in salida
        assert "SSF revisión=activa" in salida
        alcance = f"servidor {guild_id}" if guild_id else "global"
        assert f"sincronizados ({alcance}, 2 de primer nivel)" in salida
        assert "Servidores conectados: 2" in salida
        assert salida.index("Alfa (ID: 11)") < salida.index("Zeta (ID: 22)")
        assert "COMANDOS REGISTRADOS" not in salida
        assert "OPCIONES:" not in salida
        bot._sincronizar_lahora_al_conectar.assert_awaited_once()
        if guild_id:
            assert bot.tree.sync.await_args.kwargs["guild"].id == guild_id
            # La sincronización dirigida conserva la copia de comandos globales.
            assert bot.tree.get_command("box", guild=bot.tree.sync.await_args.kwargs["guild"])
        else:
            bot.tree.sync.assert_awaited_once_with()


async def test_resumen_muestra_faltantes_y_servidores_vacios(monkeypatch, capsys):
    bot = NaikitoBot()
    monkeypatch.setattr("core.bot.version_bot", lambda: "versión de prueba")
    bot._imprimir_resumen_inicio()
    salida = capsys.readouterr().out
    assert "Base de datos: no inicializada" in salida
    assert "General: no cargado" in salida
    assert "Box: no cargado" in salida
    assert "Box acciones=no disponible" in salida
    assert "sincronización no confirmada" in salida
    assert "Servidores conectados: 0" in salida


async def test_resumen_detecta_comando_y_canales_faltantes(base_datos_limpia, monkeypatch):
    bot = NaikitoBot()
    monkeypatch.setattr(bot, "unload_extension", AsyncMock())
    async with bot:
        await bot.load_extension("commands.general")
        assert bot._estado_sistema("commands.general", "General", "ping", set()) == (
            "cargado; sin canales configurados"
        )
        bot.tree.remove_command("ping")
        assert bot._estado_sistema("commands.general", "General", "ping", {1}) == (
            "sin comando principal"
        )


async def test_error_de_carga_sigue_fallando_y_muestra_sistema(base_datos_limpia, monkeypatch, capsys):
    bot = NaikitoBot()
    monkeypatch.setattr(bot, "load_extension", AsyncMock(side_effect=RuntimeError("falló")))
    async with bot:
        with pytest.raises(RuntimeError, match="falló"):
            await bot.setup_hook()
    salida = capsys.readouterr().out
    assert "[INICIO] Error al cargar General: RuntimeError" in salida
    assert bot._sincronizacion_comandos is None


async def test_error_de_sincronizacion_no_se_marca_como_exitosa(
    base_datos_limpia, monkeypatch, capsys
):
    bot = NaikitoBot()
    monkeypatch.setattr("core.bot.GUILD_ID", None)
    monkeypatch.setattr(bot, "load_extension", AsyncMock())
    monkeypatch.setattr(bot.tree, "sync", AsyncMock(side_effect=RuntimeError("falló sync")))
    async with bot:
        with pytest.raises(RuntimeError, match="falló sync"):
            await bot.setup_hook()
    assert bot._base_inicializada
    assert bot._sincronizacion_comandos is None
    assert "Error al sincronizar comandos: RuntimeError" in capsys.readouterr().out


def test_estado_tarea_distingue_detenida_desactivada_y_cancelada():
    from types import SimpleNamespace

    tarea_detenida = SimpleNamespace(is_running=lambda: False)
    cog = SimpleNamespace(narrar_combates=tarea_detenida)
    assert NaikitoBot._estado_tarea(cog, "narrar_combates") == "detenida"
    assert NaikitoBot._estado_tarea(cog, "narrar_combates", habilitada=False) == (
        "desactivada por configuración"
    )
    tarea_cancelada = SimpleNamespace(
        is_running=lambda: True, is_being_cancelled=lambda: True
    )
    cog.narrar_combates = tarea_cancelada
    assert NaikitoBot._estado_tarea(cog, "narrar_combates") == "detenida"
