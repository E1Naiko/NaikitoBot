"""Restricción por canal de los comandos de Box.

Verifica que los usuarios que no son admin solo puedan ejecutar comandos de
Box en los canales de ``BOX_CHANNEL_ID``, que los administradores queden
exentos y que los botones de tienda/desafío no sean un bypass.
"""

import asyncio

import discord
from discord.ext import commands
import pytest

import core.bot as bot_mod
from core.bot import RestrictedCommandTree

GENERAL = 100
BOX = 200
MADRUGUE = 300
SSF = 400
OTRO = 500
ADMIN = 999
USUARIO = 42


class RespuestaFalsa:
    def __init__(self):
        self.mensajes = []

    async def send_message(self, content=None, **kwargs):
        self.mensajes.append((content, kwargs))


class InteraccionFalsa:
    def __init__(self, data, canal, user_id, guild=True):
        self.data = data
        self.channel_id = canal
        self.user = type("Usuario", (), {"id": user_id})()
        self.guild = type("Guild", (), {"id": 1})() if guild else None
        self.response = RespuestaFalsa()
        self.command_failed = False


@pytest.fixture
def config_canales(monkeypatch):
    """Fija los canales y los administradores sin depender de `.env`."""

    monkeypatch.setattr(bot_mod, "GENERAL_CHANNEL_IDS", {GENERAL})
    monkeypatch.setattr(bot_mod, "BOX_CHANNEL_IDS", {BOX})
    monkeypatch.setattr(bot_mod, "MADRUGUE_CHANNEL_IDS", {MADRUGUE})
    monkeypatch.setattr(bot_mod, "SSF_CANALES_ID", {SSF})
    monkeypatch.setattr("core.permissions.ADMIN_USER_IDS", {ADMIN})


def arbol():
    return commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
        tree_cls=RestrictedCommandTree,
    ).tree


def ejecutar(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coro
    )


def comprobar(tree, data, canal, user_id):
    interaccion = InteraccionFalsa(data, canal, user_id)
    permitido = ejecutar(tree.interaction_check(interaccion))
    return permitido, interaccion.response.mensajes


BOX_SALDO = {
    "name": "box",
    "options": [{"type": 1, "name": "saldo", "options": []}],
}


# ============================================================
# /box
# ============================================================

def test_box_solo_en_canal_designado(config_canales):
    permitido, _ = comprobar(arbol(), BOX_SALDO, BOX, USUARIO)
    assert permitido


@pytest.mark.parametrize("canal", [GENERAL, MADRUGUE, SSF, OTRO])
def test_box_rechaza_fuera_del_canal_designado(config_canales, canal):
    permitido, mensajes = comprobar(arbol(), BOX_SALDO, canal, USUARIO)
    assert not permitido
    assert mensajes
    assert "solo permite comandos de Box" in mensajes[-1][0]


def test_box_admin_exento_de_canal(config_canales):
    permitido, _ = comprobar(arbol(), BOX_SALDO, OTRO, ADMIN)
    assert permitido


# ============================================================
# El resto de los comandos sigue restringido
# ============================================================

def test_ping_solo_en_general(config_canales):
    data = {"name": "ping", "options": []}

    permitido, _ = comprobar(arbol(), data, GENERAL, USUARIO)
    assert permitido

    permitido, _ = comprobar(arbol(), data, OTRO, USUARIO)
    assert not permitido


def test_madrugue_solo_en_su_canal(config_canales):
    data = {"name": "madrugue", "options": []}

    permitido, _ = comprobar(arbol(), data, MADRUGUE, USUARIO)
    assert permitido

    permitido, _ = comprobar(arbol(), data, OTRO, USUARIO)
    assert not permitido


def test_ssf_solo_en_su_canal(config_canales):
    data = {"name": "ssf", "options": [{"type": 1, "name": "registrar", "options": []}]}

    permitido, _ = comprobar(arbol(), data, SSF, USUARIO)
    assert permitido

    permitido, _ = comprobar(arbol(), data, OTRO, USUARIO)
    assert not permitido


# ============================================================
# Botones: no deben ser una vía alternativa
# ============================================================

def test_boton_tienda_rechaza_fuera_del_canal(config_canales):
    from commands.box.tienda import BotonCompra

    boton = BotonCompra(USUARIO, "mejora", "entrenamiento")
    interaccion = InteraccionFalsa(
        {},
        OTRO,
        USUARIO,
    )

    ejecutar(boton.callback(interaccion))

    assert interaccion.response.mensajes
    assert "solo puede usarse en el canal de Box" in interaccion.response.mensajes[-1][0]


def test_boton_tienda_admin_exento(base_datos_limpia, config_canales):
    from commands.box.tienda import BotonCompra

    boton = BotonCompra(ADMIN, "mejora", "entrenamiento")
    interaccion = InteraccionFalsa(
        {},
        OTRO,
        ADMIN,
    )

    ejecutar(boton.callback(interaccion))

    # Al estar exento pasa al chequeo de propiedad/compra, no recibe el aviso
    # de canal; y como el botón pertenece al propio admin, intenta comprar.
    assert not any(
        "solo puede usarse en el canal de Box" in m[0]
        for m in interaccion.response.mensajes
    )


def test_boton_desafio_rechaza_fuera_del_canal(config_canales):
    from commands.box.desafios import ChallengeView

    class Caja:
        async def _aceptar_desafio(self, *args, **kwargs):
            return {"estado": "aceptado"}

    vista = ChallengeView(Caja(), 1, USUARIO, "SPARRING")
    interaccion = InteraccionFalsa(
        {},
        OTRO,
        USUARIO,
    )

    ejecutar(vista.aceptar.callback(interaccion))

    assert interaccion.response.mensajes
    assert "solo puede aceptarse en el canal de Box" in interaccion.response.mensajes[-1][0]
