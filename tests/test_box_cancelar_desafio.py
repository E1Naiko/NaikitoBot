"""``/box cancelar`` y el ciclo de vida de la tarjeta del desafío.

La tarjeta con el botón se publica en el canal: la ve el desafiado, que es
quien puede aceptarla, y no solo el que ejecutó el comando. La fila de
``box_desafios`` anota la modalidad y dónde quedó publicada, así
``/box cancelar`` puede retirar la solicitud y reemplazar la tarjeta incluso
después de un reinicio del bot, cuando la view del botón ya no está en
memoria.
"""

from datetime import timedelta

import pytest

import commands.box.desafios as desafios_mod
from commands.box.cog import Box
from commands.box.desafios import ChallengeView
from tests.harness import conectar_db
from core.utils import ahora
from modules.box.database import (
    aceptar_desafio,
    cancelar_desafio,
    crear_desafio,
    desafio_registrado,
    desafios_pendientes,
    inicializar_db,
    registrar_mensaje_desafio,
)

from tests.harness import (
    CanalFalso,
    InteraccionFalsa,
    UsuarioFalso,
    construir_cog,
)

GUILD = 1
RETADOR = 11
CONTRINCANTE = 22
OTRO = 33
CUARTO = 44
CANAL = 77


class BotFalso:
    """Bot mínimo: alcanza con que sepa resolver el canal de la tarjeta."""

    user = None

    def __init__(self, *canales):
        self._canales = {canal.id: canal for canal in canales}

    def get_channel(self, canal_id):
        return self._canales.get(canal_id)





async def _llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return await metodo(cog, interaccion, *args)


# ============================================================
# Fixtures y ayudas
# ============================================================


@pytest.fixture
def base(base_datos_limpia):
    """Los cuatro peleadores con experiencia, como en el flujo real."""

    with conectar_db() as db:
        for user_id in (RETADOR, CONTRINCANTE, OTRO, CUARTO):
            db.execute(
                """
                INSERT INTO box_usuarios (guild_id, user_id, experiencia)
                VALUES (?, ?, 200000)
                ON CONFLICT(guild_id, user_id)
                DO UPDATE SET experiencia = excluded.experiencia
                """,
                (GUILD, user_id),
            )
        db.commit()


@pytest.fixture
def canal(base):
    """El canal de Box: uno solo, compartido por el bot y las interacciones."""

    return CanalFalso(CANAL)


@pytest.fixture
def cog(canal):
    return construir_cog(Box, bot=BotFalso(canal))


def interaccion(canal, user_id):
    """Interacción de ``user_id`` en el canal compartido."""

    return InteraccionFalsa(
        guild_id=GUILD,
        user_id=user_id,
        canal=CANAL,
        canal_obj=canal,
    )


async def desafiar(cog, canal, retador=RETADOR, rival=CONTRINCANTE, tipo="FIGHTING"):
    """Crea una solicitud por el camino real y devuelve su tarjeta."""

    origen = interaccion(canal, retador)

    await cog._crear_desafio(origen, UsuarioFalso(rival, "Rival"), tipo)

    tarjeta = canal.ultimo

    assert tarjeta is not None, "la solicitud tendría que haberse publicado"

    return tarjeta


def pendientes():
    with conectar_db() as db:
        return db.execute("SELECT COUNT(*) FROM box_desafios").fetchone()[0]


# ============================================================
# /box cancelar
# ============================================================


async def test_cancelar_retira_la_solicitud_y_su_tarjeta(cog, canal):
    """El que propuso puede retirar lo que mandó."""

    tarjeta = await desafiar(cog, canal)

    aviso = interaccion(canal, RETADOR)
    await _llamar(cog, "cancelar", aviso)

    assert pendientes() == 0

    # El aviso va en privado y dice qué se canceló
    assert "🛑 Solicitud cancelada" in aviso.texto
    assert "**pelea**" in aviso.texto
    assert aviso.respuestas[-1].efimero is True

    # Y la tarjeta del canal queda sin botón: nadie puede aceptarla de más
    assert "🛑 Solicitud cancelada" in tarjeta.texto
    assert tarjeta.kwargs.get("view") is None
    assert tarjeta.ediciones == 1


async def test_el_desafiado_puede_rechazar_la_solicitud(cog, canal):
    """Recibirla también habilita a sacarla de en medio."""

    tarjeta = await desafiar(cog, canal)

    aviso = interaccion(canal, CONTRINCANTE)
    await _llamar(cog, "cancelar", aviso)

    assert pendientes() == 0
    assert "🛑 Solicitud rechazada" in aviso.texto
    assert "🛑 Solicitud cancelada" in tarjeta.texto


async def test_el_sparring_se_cancela_igual(cog, canal):
    tarjeta = await desafiar(cog, canal, tipo="SPARRING")

    aviso = interaccion(canal, RETADOR)
    await _llamar(cog, "cancelar", aviso)

    assert pendientes() == 0
    assert "**sparring**" in aviso.texto
    assert "sparring" in tarjeta.texto


async def test_cancelar_sin_solicitudes_avisa(cog, canal):
    aviso = interaccion(canal, RETADOR)

    await _llamar(cog, "cancelar", aviso)

    assert "Sin solicitudes pendientes" in aviso.texto
    assert aviso.respuestas[-1].efimero is True


async def test_con_varias_solicitudes_pide_elegir(cog, canal):
    """Con más de una pendiente no se adivina: se cancela la que se señala."""

    await desafiar(cog, canal, rival=CONTRINCANTE)
    await desafiar(cog, canal, rival=OTRO)

    aviso = interaccion(canal, RETADOR)
    await _llamar(cog, "cancelar", aviso)

    assert "varias solicitudes" in aviso.texto
    assert pendientes() == 2, "no se canceló nada sin saber cuál era"

    elegido = interaccion(canal, RETADOR)
    await _llamar(cog, "cancelar", elegido, UsuarioFalso(OTRO, "Otro"))

    assert "🛑 Solicitud cancelada" in elegido.texto

    with conectar_db() as db:
        contrincantes = [
            fila[0] for fila in db.execute("SELECT contrincante_id FROM box_desafios")
        ]

    assert contrincantes == [CONTRINCANTE]


async def test_una_solicitud_vencida_no_se_lista(cog, canal):
    """Vencida ya no es una solicitud: no hay nada que cancelar."""

    inicio = ahora()

    await crear_desafio(
        GUILD,
        RETADOR,
        CONTRINCANTE,
        inicio,
        inicio - timedelta(minutes=5),
        tipo="FIGHTING",
        canal_id=CANAL,
    )

    aviso = interaccion(canal, RETADOR)
    await _llamar(cog, "cancelar", aviso)

    assert "Sin solicitudes pendientes" in aviso.texto


async def test_cancelar_una_solicitud_que_ya_no_esta_avisa(cog, canal, monkeypatch):
    """Carrera con el botón: entre la lectura y el borrado alguien aceptó."""

    await desafiar(cog, canal)
    async def _sin_solicitud(*args):
        return None

    monkeypatch.setattr(desafios_mod, "cancelar_desafio", _sin_solicitud)

    aviso = interaccion(canal, RETADOR)
    await _llamar(cog, "cancelar", aviso)

    assert "Ya no se puede cancelar" in aviso.texto


# ============================================================
# La tarjeta después de cancelada
# ============================================================


async def test_aceptar_una_solicitud_cancelada_no_arranca_nada(cog, canal, monkeypatch):
    """El botón de una tarjeta vieja no puede abrir una pelea inexistente."""

    monkeypatch.setattr(desafios_mod, "BOX_CHANNEL_IDS", (CANAL,))

    tarjeta = await desafiar(cog, canal)
    [desafio_id] = [
        pendiente["id"] for pendiente in await desafios_pendientes(GUILD, RETADOR, ahora())
    ]

    await _llamar(cog, "cancelar", interaccion(canal, RETADOR))

    boton = interaccion(canal, CONTRINCANTE)
    boton.message = tarjeta
    view = ChallengeView(cog, desafio_id, RETADOR, CONTRINCANTE, "FIGHTING")

    await view.aceptar.callback(boton)

    assert "Desafío no disponible" in boton.texto

    with conectar_db() as db:
        combates = db.execute("SELECT COUNT(*) FROM box_combates").fetchone()[0]
        acciones = db.execute("SELECT COUNT(*) FROM box_acciones").fetchone()[0]

    assert combates == 0
    assert acciones == 0


async def test_el_timeout_no_pisa_una_tarjeta_ya_retirada(cog, canal):
    """La view vive en memoria hasta una hora: no puede contradecir al canal.

    Si el timeout escribiera igual, una solicitud cancelada terminaría
    mostrando "expirado" una hora después, que es otra cosa.
    """

    tarjeta = await desafiar(cog, canal)
    view = tarjeta.kwargs.get("view")

    await _llamar(cog, "cancelar", interaccion(canal, RETADOR))

    assert tarjeta.ediciones == 1

    await view.on_timeout()

    assert tarjeta.ediciones == 1, "el timeout volvió a editar la tarjeta"
    assert "⌛ Desafío expirado" not in tarjeta.texto


async def test_una_pelea_en_curso_conserva_el_boton(cog, canal, monkeypatch):
    """Motivo transitorio: la solicitud sigue pendiente y el botón también.

    Antes el motivo se escribía en la tarjeta y se la dejaba sin view, así que
    el "volvé a aceptar cuando termine esta pelea" no tenía con qué hacerse.
    """

    monkeypatch.setattr(desafios_mod, "BOX_CHANNEL_IDS", (CANAL,))

    inicio = ahora().replace(microsecond=0)
    primera = await crear_desafio(
        GUILD,
        OTRO,
        CUARTO,
        inicio,
        inicio + timedelta(hours=1),
        tipo="FIGHTING",
        canal_id=CANAL,
    )

    tarjeta = await desafiar(cog, canal)
    view = tarjeta.kwargs.get("view")

    # Recién después se pone una pelea en el ring: al revés, /box desafio no
    # llegaría a crear la solicitud que queremos probar.
    assert (await aceptar_desafio(
        primera, GUILD, CUARTO, inicio, recompensa=1000, tipo="FIGHTING"
    ))["estado"] == "aceptado"

    boton = interaccion(canal, CONTRINCANTE)
    boton.message = tarjeta

    await view.aceptar.callback(boton)

    assert "Todavía no se puede aceptar" in boton.texto
    assert "En el ring" in boton.texto
    assert boton.respuestas[-1].efimero is True

    # La tarjeta no se tocó y la view sigue esperando el próximo intento
    assert tarjeta.ediciones == 0
    assert view.is_finished() is False
    assert len(await desafios_pendientes(GUILD, RETADOR, ahora())) == 1


async def test_aceptar_le_responde_al_que_apreto_el_boton(cog, canal, monkeypatch):
    """El desafiado recibe su propia confirmación, no solo la tarjeta editada.

    La interacción del botón se difiere efímera: si no llega una respuesta
    propia, se queda con la burbuja de "pensando" colgada.
    """

    monkeypatch.setattr(desafios_mod, "BOX_CHANNEL_IDS", (CANAL,))

    tarjeta = await desafiar(cog, canal)
    view = tarjeta.kwargs.get("view")

    boton = interaccion(canal, CONTRINCANTE)
    boton.message = tarjeta

    await view.aceptar.callback(boton)

    assert "🥊 ¡Desafío aceptado!" in tarjeta.texto
    assert "Aceptaste el desafío" in boton.texto
    assert boton.respuestas[-1].efimero is True
    assert view.is_finished() is True


# ============================================================
# La fila en la base
# ============================================================


async def test_desafios_pendientes_mira_los_dos_roles(base):
    inicio = ahora()

    viva = await crear_desafio(
        GUILD,
        RETADOR,
        CONTRINCANTE,
        inicio,
        inicio + timedelta(hours=1),
        tipo="FIGHTING",
        canal_id=CANAL,
    )
    await crear_desafio(
        GUILD,
        OTRO,
        CUARTO,
        inicio,
        inicio - timedelta(minutes=5),
        tipo="SPARRING",
        canal_id=CANAL,
    )

    del_retador = await desafios_pendientes(GUILD, RETADOR, inicio)
    del_desafiado = await desafios_pendientes(GUILD, CONTRINCANTE, inicio)
    del_ajeno = await desafios_pendientes(GUILD, CUARTO, inicio)

    assert [fila["id"] for fila in del_retador] == [viva]
    assert [fila["id"] for fila in del_desafiado] == [viva]
    assert del_ajeno == [], "la vencida no le aparece a nadie"
    assert del_retador[0]["tipo"] == "FIGHTING"
    assert del_retador[0]["canal_id"] == CANAL
    assert del_retador[0]["mensaje_id"] is None


async def test_cancelar_desafio_solo_lo_cancela_quien_participa(base):
    inicio = ahora()
    desafio_id = await crear_desafio(
        GUILD,
        RETADOR,
        CONTRINCANTE,
        inicio,
        inicio + timedelta(hours=1),
        tipo="SPARRING",
        canal_id=CANAL,
    )

    assert await cancelar_desafio(desafio_id, GUILD, CUARTO, inicio) is None
    assert await desafio_registrado(desafio_id) is True

    cancelado = await cancelar_desafio(desafio_id, GUILD, CONTRINCANTE, inicio)

    assert cancelado["tipo"] == "SPARRING"
    assert cancelado["retador_id"] == RETADOR
    assert cancelado["contrincante_id"] == CONTRINCANTE
    assert await desafio_registrado(desafio_id) is False
    assert await cancelar_desafio(desafio_id, GUILD, RETADOR, inicio) is None


async def test_cancelar_no_toca_las_solicitudes_de_otro_servidor(base):
    inicio = ahora()
    desafio_id = await crear_desafio(
        GUILD,
        RETADOR,
        CONTRINCANTE,
        inicio,
        inicio + timedelta(hours=1),
        tipo="FIGHTING",
    )

    assert await cancelar_desafio(desafio_id, 999, RETADOR, inicio) is None
    assert await desafio_registrado(desafio_id) is True


async def test_registrar_la_tarjeta_deja_anotado_donde_quedo(base):
    inicio = ahora()
    desafio_id = await crear_desafio(
        GUILD,
        RETADOR,
        CONTRINCANTE,
        inicio,
        inicio + timedelta(hours=1),
        tipo="FIGHTING",
        canal_id=CANAL,
    )

    await registrar_mensaje_desafio(desafio_id, 123456)

    fila = (await desafios_pendientes(GUILD, RETADOR, inicio))[0]

    assert fila["mensaje_id"] == 123456


async def test_inicializar_db_es_idempotente_y_recrea_tablas(base_datos_limpia):
    """El esquema lo maneja el ORM: ``inicializar_db`` crea lo que falta.

    El viejo sistema de ``ALTER TABLE`` desapareció con la migración a
    SQLAlchemy; una base que arranca de cero o a la que le falta una tabla
    se pone al día con ``create_all``, y lo que ya existe queda intacto.
    """

    await crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, ahora(), ahora() + timedelta(hours=1)
    )

    with conectar_db() as db:
        db.execute("DROP TABLE box_acciones")
        db.commit()

    await inicializar_db()

    with conectar_db() as db:
        columnas = {
            fila[1] for fila in db.execute("PRAGMA table_info(box_acciones)")
        }
        desafio = db.execute(
            "SELECT retador_id, contrincante_id FROM box_desafios"
        ).fetchone()

    assert {"id", "guild_id", "user_id", "tipo", "iniciado_en"} <= columnas
    assert desafio == (RETADOR, CONTRINCANTE)
