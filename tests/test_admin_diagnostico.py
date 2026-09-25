"""Pruebas del diagnóstico seguro ``/admin test``."""

from types import SimpleNamespace

import pytest

from commands.admin.diagnostico import (
    Comprobacion,
    ESTADO_ERROR,
    ESTADO_OK,
)
from tests.harness import InteraccionFalsa, construir_cog

GUILD = 1
ADMIN = 1
USUARIO = 42


@pytest.fixture
def admin_ids(monkeypatch):
    monkeypatch.setattr("core.permissions.ADMIN_USER_IDS", {ADMIN})


@pytest.fixture
def cog(base_datos_limpia, admin_ids):
    from commands.admin.cog import Admin

    return construir_cog(Admin)


async def llamar_test(cog, interaccion):
    return await type(cog).test.callback(cog, interaccion)


def contar_filas(base_datos):
    """Fotografía todas las tablas para detectar cualquier escritura."""

    import sqlite3

    with sqlite3.connect(base_datos) as conexion:
        tablas = [
            fila[0]
            for fila in conexion.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        return {
            tabla: conexion.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
            for tabla in tablas
        }


async def test_test_difiere_responde_efimero_y_no_escribe(cog, base_datos_limpia):
    antes = contar_filas(base_datos_limpia)
    interaccion = InteraccionFalsa(GUILD, ADMIN)

    await llamar_test(cog, interaccion)

    despues = contar_filas(base_datos_limpia)
    assert despues == antes
    assert interaccion.cantidad_respuestas == 2
    assert all(respuesta.efimero for respuesta in interaccion.respuestas)
    assert interaccion.respuestas[0].contenido is None

    texto = interaccion.texto
    assert "Test administrativo" in texto
    assert "Diagnóstico de solo lectura" in texto
    assert "Base de datos" in texto
    assert "Árbol de comandos" in texto
    assert "Canales y permisos" in texto
    assert "Tareas automáticas" in texto
    assert "Box" in texto
    assert "Madrugue" in texto
    assert "SeptSinFP" in texto
    assert "Completado en" in texto


async def test_test_aisla_un_subsistema_roto_y_continua(cog, monkeypatch):
    async def saldo_roto(*_args):
        raise RuntimeError("box fuera de servicio")

    monkeypatch.setattr(
        "commands.admin.diagnostico.obtener_saldo",
        saldo_roto,
    )
    interaccion = InteraccionFalsa(GUILD, ADMIN)

    await llamar_test(cog, interaccion)

    assert "❌ Box" in interaccion.texto
    assert "box fuera de servicio" in interaccion.texto
    assert "✅ Base de datos" in interaccion.texto
    assert "✅ Madrugue" in interaccion.texto
    assert "✅ SeptSinFP" in interaccion.texto


async def test_test_puede_informar_todo_operativo(cog, monkeypatch):
    clase = type(cog)

    monkeypatch.setattr(
        clase,
        "_diagnosticar_arbol",
        lambda _self: Comprobacion("Árbol de comandos", ESTADO_OK, "correcto"),
    )
    monkeypatch.setattr(
        clase,
        "_diagnosticar_discord",
        lambda _self, _interaccion: Comprobacion("Discord", ESTADO_OK, "correcto"),
    )
    monkeypatch.setattr(
        clase,
        "_diagnosticar_tareas",
        lambda _self: Comprobacion("Tareas automáticas", ESTADO_OK, "correcto"),
    )

    def diagnostico_async(nombre):
        async def ejecutar(*_args):
            return Comprobacion(nombre, ESTADO_OK, "correcto")

        return ejecutar

    monkeypatch.setattr(clase, "_diagnosticar_base", diagnostico_async("Base de datos"))
    monkeypatch.setattr(clase, "_diagnosticar_box", diagnostico_async("Box"))
    monkeypatch.setattr(clase, "_diagnosticar_madrugue", diagnostico_async("Madrugue"))
    monkeypatch.setattr(clase, "_diagnosticar_ssf", diagnostico_async("SeptSinFP"))
    monkeypatch.setattr(
        clase,
        "_diagnosticar_canales",
        diagnostico_async("Canales y permisos"),
    )

    interaccion = InteraccionFalsa(GUILD, ADMIN)
    await llamar_test(cog, interaccion)

    assert "✅ Todo operativo" in interaccion.texto
    assert "0 errores · 0 avisos" in interaccion.texto
    assert len(interaccion.respuestas[-1].embed.fields) == 8


async def test_diagnostico_de_canales_revisa_permisos_sin_enviar(cog, monkeypatch):
    import commands.admin.diagnostico as diagnostico

    class CanalConPermisosInsuficientes:
        id = 10
        guild = SimpleNamespace(me=object())

        def __init__(self):
            self.envios = 0

        async def send(self, *_args, **_kwargs):
            self.envios += 1

        def permissions_for(self, _miembro):
            return SimpleNamespace(send_messages=False, embed_links=True)

    canal = CanalConPermisosInsuficientes()
    monkeypatch.setattr(diagnostico, "GENERAL_CHANNEL_IDS", {canal.id})
    monkeypatch.setattr(diagnostico, "MADRUGUE_CHANNEL_IDS", set())
    monkeypatch.setattr(diagnostico, "LAHORA_CANALES_ID", set())
    monkeypatch.setattr(diagnostico, "BOX_CHANNEL_IDS", set())
    monkeypatch.setattr(diagnostico, "SSF_CANALES_ID", set())
    monkeypatch.setattr(cog.bot, "get_channel", lambda canal_id: canal)

    resultado = await cog._diagnosticar_canales(
        InteraccionFalsa(GUILD, ADMIN),
    )

    assert resultado.estado == ESTADO_ERROR
    assert "send_messages" in resultado.detalle
    assert canal.envios == 0


async def test_manifiesto_coincide_con_el_arbol_real(
    base_datos_limpia,
    monkeypatch,
):
    """Evita que el diagnóstico quede desactualizado al cambiar comandos."""

    from discord.ext import tasks

    from commands.admin.cog import Admin
    from commands.box.cog import Box
    from commands.general import General
    from commands.lahora.cog import LaHora
    from commands.madrugue.cog import Madrugue
    from commands.ssf.cog import Ssf
    from core.bot import NaikitoBot

    # Registrar los cogs directamente evita descargar y volver a importar los
    # módulos al cerrar el bot de prueba (eso cambiaría la identidad de las
    # clases que otros tests importaron durante la colección).
    monkeypatch.setattr(tasks.Loop, "start", lambda *_args, **_kwargs: None)
    bot = NaikitoBot()
    try:
        for clase in (General, Madrugue, LaHora, Admin, Ssf, Box):
            await bot.add_cog(clase(bot))

        resultado = bot.get_cog("Admin")._diagnosticar_arbol()
        assert resultado.estado == ESTADO_OK, resultado.detalle
    finally:
        await bot.close()
