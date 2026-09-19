"""Flujo de interacción de /box desafio: defer temprano, followups y botón.

La respuesta inicial de una interacción solo se acepta durante los primeros
3 segundos, y este camino toca la base varias veces (acción activa, lesión,
candado; contra el bot, la resolución completa del plan). Si la base se
demora (lock, disco, antivirus), el comando debe tardar —no reviente con
10062 "Unknown interaction". Para eso el comando defiere al toque y
responde con followups.
"""

from dataclasses import dataclass
from datetime import timedelta

import pytest
from discord.utils import MISSING

from commands.box.cog import Box
from commands.box.desafios import ChallengeView
from tests.harness import conectar_db
from core.utils import ahora
from modules.box.database import ESTADO_VIVO, crear_desafio

from tests.harness import InteraccionFalsa, UsuarioFalso, construir_cog

GUILD = 1
RETADOR = 11
CONTRINCANTE = 22
BOT_ID = 99
CANAL = 77





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


async def test_desafio_defiere_y_publica_la_tarjeta_en_el_canal(base):
    """La tarjeta con el botón la tiene que ver el desafiado.

    El comando difiere la interacción como efímera para que la base no gaste
    la ventana de tres segundos; si la tarjeta saliera por ``followup`` viajaría
    atada a esa interacción y solo la vería el que desafió, que es justamente
    quien no tiene nada que aceptar. Por eso va al canal, y el que desafió
    recibe por separado su confirmación privada.
    """

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR, canal=CANAL)
    rival = UsuarioFalso(CONTRINCANTE, "Rival")

    await cog._crear_desafio(interaccion, rival, "FIGHTING")

    respuestas = interaccion.respuestas

    assert interaccion.response.is_done()
    assert len(respuestas) == 2

    # 1. La primera respuesta es el defer (efímero: sin burbuja en el canal)
    assert respuestas[0].contenido is None
    assert respuestas[0].kwargs.get("ephemeral") is True

    # 2. La tarjeta sale por el canal: pública, con el botón y la view
    #    apuntándola para poder retirarla después
    [tarjeta] = interaccion.channel.mensajes

    assert "🥊 ¡Nuevo desafío!" in tarjeta.texto
    assert rival.mention in tarjeta.texto, "la tarjeta nombra al desafiado"
    # ...y lo nombra en el contenido, que es lo único que notifica: una
    # mención dentro del embed se ve pero no le llega a nadie.
    assert rival.mention in (tarjeta.contenido or "")
    assert tarjeta.efimero is False

    view = tarjeta.kwargs.get("view")

    assert isinstance(view, ChallengeView)
    assert view.message is tarjeta
    assert view.retador_id == RETADOR
    assert view.contrincante_id == CONTRINCANTE
    assert view.tipo == "FIGHTING"

    # 3. El que desafió recibe su acuse privado (y así se cierra el defer)
    aviso = respuestas[-1]

    assert "Solicitud enviada" in aviso.texto
    assert aviso.efimero is True

    with conectar_db() as db:
        fila = db.execute(
            """
            SELECT tipo, canal_id, mensaje_id
            FROM box_desafios
            WHERE guild_id = ? AND retador_id = ?
            """,
            (GUILD, RETADOR),
        ).fetchone()

    # La fila anota la modalidad y la tarjeta: es lo que necesita
    # /box cancelar para describir y retirar la solicitud sin depender de la
    # view, que es memoria del proceso.
    assert fila == ("FIGHTING", CANAL, tarjeta.id)


async def test_el_sparring_tambien_se_publica_en_el_canal(base):
    """La modalidad cambia el rótulo, no la visibilidad de la tarjeta."""

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR, canal=CANAL)
    rival = UsuarioFalso(CONTRINCANTE, "Rival")

    await cog._crear_desafio(interaccion, rival, "SPARRING")

    [tarjeta] = interaccion.channel.mensajes

    assert "**sparring**" in tarjeta.texto
    assert "🥊 ¡Nuevo desafío!" in tarjeta.texto

    with conectar_db() as db:
        tipo = db.execute(
            "SELECT tipo FROM box_desafios WHERE guild_id = ?", (GUILD,)
        ).fetchone()[0]

    assert tipo == "SPARRING"


async def test_sin_canal_no_queda_una_solicitud_invisible(base, monkeypatch):
    """Si no se puede publicar la tarjeta, no se deja nada pendiente.

    Una solicitud que nadie ve es una trampa: bloquea el par
    (retador, contrincante) en la base y no se puede aceptar ni cancelar.
    """

    import commands.box.desafios as desafios_mod

    async def sin_canal(bot, interaction):
        return None

    monkeypatch.setattr(desafios_mod, "canal_de_la_interaccion", sin_canal)

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR, canal=CANAL)
    rival = UsuarioFalso(CONTRINCANTE, "Rival")

    await cog._crear_desafio(interaccion, rival, "FIGHTING")

    assert "No se pudo publicar el desafío" in interaccion.texto

    with conectar_db() as db:
        pendientes = db.execute("SELECT COUNT(*) FROM box_desafios").fetchone()[0]

    assert pendientes == 0


async def test_un_canal_sin_permisos_tampoco_deja_solicitud(base):
    """Lo mismo cuando el canal existe pero el bot no puede escribir ahí."""

    from tests.harness import prohibido

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR, canal=CANAL)

    async def sin_permiso(*args, **kwargs):
        raise prohibido()

    interaccion.channel.send = sin_permiso

    await cog._crear_desafio(interaccion, UsuarioFalso(CONTRINCANTE, "Rival"), "SPARRING")

    assert "No se pudo publicar el desafío" in interaccion.texto

    with conectar_db() as db:
        pendientes = db.execute("SELECT COUNT(*) FROM box_desafios").fetchone()[0]

    assert pendientes == 0


async def test_error_despues_de_defer_ir_por_followup(base):
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

    await cog._crear_desafio(interaccion, rival, "FIGHTING")

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


async def test_desafiar_al_bot_defiere_y_acepta_inmediato(base):
    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=RETADOR)
    bot = UsuarioFalso(BOT_ID, "NaikitoBot")
    bot.bot = True

    await cog._crear_desafio(interaccion, bot, "FIGHTING")

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


async def test_aceptar_defiere_y_edita_el_mensaje_del_boton(base, monkeypatch):
    import commands.box.desafios as desafios_mod

    monkeypatch.setattr(desafios_mod, "BOX_CHANNEL_IDS", (CANAL,))

    inicio = ahora().replace(microsecond=0)
    desafio_id = await crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    cog = construir_cog(Box)
    view = ChallengeView(cog, desafio_id, RETADOR, CONTRINCANTE, "FIGHTING")

    interaccion = InteraccionFalsa(guild_id=GUILD, user_id=CONTRINCANTE, canal=CANAL)
    mensaje_desafio = MensajeDelDesafio()
    interaccion.message = mensaje_desafio

    # La misma llamada que hace el framework: (view, interaccion, botón)
    await view.aceptar.callback(interaccion)

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
