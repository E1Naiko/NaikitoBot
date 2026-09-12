"""Flujo de interacción de /box desafio: defer temprano, followups y botón.

La respuesta inicial de una interacción solo se acepta durante los primeros
3 segundos, y este camino toca la base varias veces (acción activa, lesión,
candado; contra el bot, la resolución completa del plan). Si la base se
demora (lock, disco, antivirus), el comando debe tardar —no reviente con
10062 "Unknown interaction". Para eso el comando defiere al toque y
responde con followups.
"""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

import pytest
from discord.utils import MISSING

from commands.box.cog import Box
from commands.box.desafios import ChallengeView
from core.database import conectar_db
from core.utils import ahora
from modules.box.database import ESTADO_VIVO, crear_desafio

from tests.harness import InteraccionFalsa, UsuarioFalso, construir_cog

GUILD = 1
RETADOR = 11
CONTRINCANTE = 22
BOT_ID = 99
CANAL = 77


def correr(coro):
    loop = asyncio.new_event_loop()

    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def plano(embed) -> str:
    """Texto plano de un embed, para afirmar sin depender de campos sueltos."""

    if embed is None:
        return ""

    partes = [embed.title or "", embed.description or ""]
    partes += [f"{campo.name}:{campo.value}" for campo in embed.fields]

    return "\n".join(partes)


@pytest.fixture
def base(base_datos_limpia):
    """La base vacía con el retador (y el contrincante) con experiencia."""

    with conectar_db() as db:
        for user_id, exp in ((RETADOR, 400_000), (CONTRINCANTE, 90_000)):
            db.execute(
                """
                INSERT INTO box_usuarios (guild_id, user_id, experiencia)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id)
                DO UPDATE SET experiencia = excluded.experiencia
                """,
                (GUILD, user_id, exp),
            )
        db.commit()


# ============================================================
# /box desafio: caso normal
# ============================================================


def test_desafio_defiere_y_responde_con_followup(base):
    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR)
    rival = UsuarioFalso(CONTRINCANTE, "Rival")

    correr(cog._crear_desafio(interaccion, rival, "FIGHTING"))

    respuestas = interaccion.respuestas

    assert interaccion.response.is_done()
    assert len(respuestas) == 2

    # 1. La primera respuesta es el defer (efímero: sin burbuja en el canal)
    assert respuestas[0].contenido is None
    assert respuestas[0].kwargs.get("ephemeral") is True

    # 2. La tarjeta con el botón va por followup y la view la apunta
    tarjeta = respuestas[1]

    assert "🥊 ¡Nuevo desafío!" in tarjeta.texto

    view = tarjeta.kwargs.get("view")

    assert isinstance(view, ChallengeView)
    assert view.message is tarjeta

    with conectar_db() as db:
        pendientes = db.execute(
            "SELECT COUNT(*) FROM box_desafios WHERE guild_id = ? AND retador_id = ?",
            (GUILD, RETADOR),
        ).fetchone()[0]

    assert pendientes == 1


def test_error_despues_de_defer_ir_por_followup(base):
    """Con acción activa el rechazo es un followup efímero, no un response.

    ``response.send_message`` sobre una interacción ya atendida revienta con
    ``InteractionResponded``; el helper ``responder`` tiene que elegir el
    followup solo porque la interacción se defirió.
    """

    ahora_ = ahora()

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_acciones (
                guild_id, user_id, tipo, iniciado_en, finaliza_en, recompensa
            )
            VALUES (?, ?, 'ENTRENANDO', ?, ?, 100)
            """,
            (GUILD, RETADOR, ahora_.isoformat(), ahora_.isoformat()),
        )
        db.commit()

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR)
    rival = UsuarioFalso(CONTRINCANTE, "Rival")

    correr(cog._crear_desafio(interaccion, rival, "FIGHTING"))

    assert len(interaccion.respuestas) == 2

    aviso = interaccion.respuestas[1]

    assert "⚠️ Acción activa" in aviso.texto
    assert aviso.efimero is True

    with conectar_db() as db:
        pendientes = db.execute("SELECT COUNT(*) FROM box_desafios").fetchone()[0]

    assert pendientes == 0


# ============================================================
# /box desafio @Bot: auto-acepta
# ============================================================


def test_desafiar_al_bot_defiere_y_acepta_inmediato(base):
    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR)
    bot = UsuarioFalso(BOT_ID, "NaikitoBot")
    bot.bot = True

    correr(cog._crear_desafio(interaccion, bot, "FIGHTING"))

    respuestas = interaccion.respuestas

    # El defer va primero: la resolución del plan no gasta la ventana de 3 s
    assert respuestas[0].kwargs.get("ephemeral") is True

    # ...y la tarjeta de aceptación llega igual, por followup
    assert "🤖 ¡El bot aceptó tu desafío!" in respuestas[-1].texto

    with conectar_db() as db:
        peleadores = sorted(
            fila[0]
            for fila in db.execute(
                "SELECT user_id FROM box_acciones WHERE guild_id = ?",
                (GUILD,),
            )
        )
        vivos = db.execute(
            "SELECT COUNT(*) FROM box_combates WHERE estado = ?",
            (ESTADO_VIVO,),
        ).fetchone()[0]
        pendientes = db.execute("SELECT COUNT(*) FROM box_desafios").fetchone()[0]

    assert peleadores == [RETADOR, BOT_ID]
    assert vivos == 1
    assert pendientes == 0


# ============================================================
# Botón Aceptar del desafío
# ============================================================


@dataclass
class MensajeDelDesafio:
    """El mensaje que lleva el botón, con estado observable."""

    embed: object = None
    view: object = None
    ediciones: int = 0

    async def edit(self, *, embed=None, view=MISSING, **kwargs):
        if embed is not MISSING:
            self.embed = embed
        if view is not MISSING:
            self.view = view
        self.ediciones += 1
        return self


def test_aceptar_defiere_y_edita_el_mensaje_del_boton(base, monkeypatch):
    import commands.box.desafios as desafios_mod

    monkeypatch.setattr(desafios_mod, "BOX_CHANNEL_IDS", (CANAL,))

    inicio = ahora().replace(microsecond=0)
    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    cog = construir_cog(Box)
    view = ChallengeView(cog, desafio_id, CONTRINCANTE, "FIGHTING")

    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=CONTRINCANTE, canal=CANAL)
    mensaje_desafio = MensajeDelDesafio()
    interaccion.message = mensaje_desafio

    # La misma llamada que hace el framework: (view, interaccion, botón)
    correr(view.aceptar.callback(interaccion))

    # 1. Se defirió antes de resolver el plan
    assert interaccion.response.is_done()
    assert interaccion.respuestas[0].kwargs.get("ephemeral") is True

    # 2. Después de un defer, response.edit_message revienta con
    #    InteractionResponded: se editó el mensaje que lleva el botón
    assert mensaje_desafio.ediciones == 1
    assert "🥊 ¡Desafío aceptado!" in plano(mensaje_desafio.embed)
    assert mensaje_desafio.view is view
    assert view.aceptar.disabled is True

    # 3. El desafío se consumió y la pelea quedó planificada
    with conectar_db() as db:
        pendientes = db.execute(
            "SELECT COUNT(*) FROM box_desafios WHERE id = ?", (desafio_id,)
        ).fetchone()[0]
        vivos = db.execute(
            "SELECT COUNT(*) FROM box_combates WHERE estado = ?", (ESTADO_VIVO,)
        ).fetchone()[0]

    assert pendientes == 0
    assert vivos == 1
