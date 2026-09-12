"""Pruebas del combate en vivo: la fila en sqlite y el latido del narrador.

Cubren el camino que no se puede probar con lógica pura: aceptar un desafío
deja un combate planificado en ``box_combates``, un latido revela un diálogo,
un asalto es un solo mensaje que se edita, y el combate se cierra cuando se
queda sin acción (por ejemplo porque un administrador la finalizó).

Discord se simula con dobles locales: al narrador solo le interesan ``send``,
``edit`` y ``fetch_message``.
"""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

import discord
import pytest

from config import BOX_COMBATE_CANTICOS, BOX_VIDA_INICIAL
from commands.box.narracion import NarracionMixin

from core.utils import ahora
from modules.box.combate import Plan
from modules.box.database import (
    ESTADO_CANCELADO,
    ESTADO_TERMINADO,
    ESTADO_VIVO,
    aceptar_desafio,
    asaltos_publicados,
    cerrar_combate,
    combate_en_curso,
    crear_desafio,
    fijar_canticos,
    obtener_canticos,
    latido_de,
    obtener_combates_vivos,
    conectar_db,
    ultimos_combates,
    reclamar_asalto,
    tiene_accion_activa,
)

GUILD = 1
OTRO_GUILD = 2
CANAL = 77
RETADOR = 11
CONTRINCANTE = 22


# ============================================================
# Dobles de Discord
# ============================================================


class _Respuesta404:
    """Respuesta HTTP mínima para construir ``discord.NotFound``.

    ``discord.py`` lee ``response.status`` al armar la excepción, así que
    ``None`` no sirve: reventaría con ``AttributeError`` en vez de ``NotFound``
    y la prueba no ejercitaría la rama que quiere ejercitar.
    """

    status = 404
    reason = "Not Found"


def _no_encontrado(mensaje="Not Found"):
    return discord.NotFound(_Respuesta404(), mensaje)


@dataclass
class MensajeFalso:
    id: int
    embed: object = None
    ediciones: int = 0
    borrado: bool = False

    async def edit(self, *, embed=None, **kwargs):
        if self.borrado:
            raise _no_encontrado()

        self.embed = embed
        self.ediciones += 1
        return self


class CanalFalso:
    def __init__(self):
        self.mensajes: list[MensajeFalso] = []

    async def send(self, content=None, *, embed=None, **kwargs):
        mensaje = MensajeFalso(len(self.mensajes) + 1, embed)
        self.mensajes.append(mensaje)
        return mensaje

    async def fetch_message(self, mensaje_id):
        for mensaje in self.mensajes:
            if mensaje.id == mensaje_id:
                return mensaje

        raise _no_encontrado()

    @property
    def textos(self):
        def plano(embed):
            if embed is None:
                return ""

            partes = [embed.title or "", embed.description or ""]
            partes += [f"{c.name}:{c.value}" for c in embed.fields]

            if embed.footer and embed.footer.text:
                partes.append(embed.footer.text)

            return "\n".join(partes)

        return [plano(mensaje.embed) for mensaje in self.mensajes]


class MiembroFalso:
    def __init__(self, user_id, nombre):
        self.id = user_id
        self.display_name = nombre

    @property
    def mention(self):
        return f"<@{self.id}>"


class GuildFalso:
    """El guild del narrador: resuelve miembros y el canal del combate."""

    id = GUILD

    def __init__(self, miembros=None, canal=None):
        self._miembros = miembros or {}
        self._canal = canal

    def get_member(self, user_id):
        return self._miembros.get(user_id)

    async def fetch_member(self, user_id):
        return self._miembros.get(user_id)

    def get_channel(self, channel_id):
        return self._canal if channel_id == CANAL else None


class BotFalso:
    def __init__(self, canal=None, miembros=None, guild=None):
        self._canal = canal
        self._guild = (
            guild if guild is not None else GuildFalso(miembros or {}, canal)
        )

    def get_channel(self, canal_id):
        return self._canal if canal_id == CANAL else None

    def get_guild(self, guild_id):
        return self._guild if guild_id == GUILD else None


class Narrador(NarracionMixin):
    """Cog mínimo: el mixin de narración con su canal de Box."""

    def __init__(self, canal, miembros):
        self.bot = BotFalso(canal, miembros)
        self._canal = canal

    def _canal_box(self):
        return self._canal


def correr(coro):
    loop = asyncio.new_event_loop()

    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def inicio():
    return ahora().replace(microsecond=0)


@pytest.fixture
def combate(base_datos_limpia, inicio):
    """Acepta un desafío de verdad y devuelve el combate que dejó registrado."""

    for user_id in (RETADOR, CONTRINCANTE):
        with __import__("core.database", fromlist=["conectar_db"]).conectar_db() as db:
            db.execute(
                """
                INSERT INTO box_usuarios (guild_id, user_id, experiencia)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET experiencia = excluded.experiencia
                """,
                (GUILD, user_id, 400_000 if user_id == RETADOR else 90_000),
            )
            db.commit()

    # Ventana de aceptación abierta: si expirara justo en "ahora",
    # ``aceptar_desafio`` respondería "expirado" por la comparación <=.
    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )
    resultado = aceptar_desafio(
        desafio_id,
        GUILD,
        CONTRINCANTE,
        inicio,
        recompensa=1000,
        tipo="FIGHTING",
        canal_id=CANAL,
    )

    assert resultado["estado"] == "aceptado"

    vivos = obtener_combates_vivos(inicio)

    assert len(vivos) == 1

    return vivos[0]


@pytest.fixture
def narrador(monkeypatch, combate):
    """El narrador, con un reloj que manejamos desde la prueba."""

    import commands.box.narracion as modulo

    reloj = {"ahora": combate["iniciado_en"]}

    monkeypatch.setattr(modulo, "ahora", lambda: reloj["ahora"])

    miembros = {
        RETADOR: MiembroFalso(RETADOR, "Rojo"),
        CONTRINCANTE: MiembroFalso(CONTRINCANTE, "Azul"),
    }
    canal = CanalFalso()
    narrador = Narrador(canal, miembros)

    def adelantar(latidos, momento_base=None):
        base = momento_base or combate["iniciado_en"]
        reloj["ahora"] = base + timedelta(
            seconds=latidos * combate["latido_segundos"]
        )

    return narrador, canal, reloj, adelantar


# ============================================================
# La fila en la base de datos
# ============================================================


def test_aceptar_un_desafio_deja_un_combate_planificado(combate, inicio):
    plan = Plan.de_json(combate["plan"])

    assert plan.modo == "FIGHTING"
    assert plan.latidos > 0
    assert combate["latidos_totales"] == plan.latidos
    assert combate["estado"] == ESTADO_VIVO
    assert combate["fin_narracion_en"] > inicio
    assert combate["canal_id"] == CANAL


def test_el_sparring_tambien_deja_su_combate(base_datos_limpia, inicio):
    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    aceptar_desafio(
        desafio_id,
        GUILD,
        CONTRINCANTE,
        inicio,
        recompensa=100,
        tipo="SPARRING",
        canal_id=CANAL,
    )

    plan = Plan.de_json(obtener_combates_vivos(inicio)[0]["plan"])

    assert plan.modo == "SPARRING"
    assert plan.ganador == -1
    assert plan.metodo == "ENTRENAMIENTO"


def test_sin_ganador_forzado_el_sparring_no_escribe_historial(base_datos_limpia, inicio):
    from core.database import conectar_db

    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    aceptar_desafio(desafio_id, GUILD, CONTRINCANTE, inicio, 100, tipo="SPARRING")

    with conectar_db() as db:
        assert db.execute("SELECT COUNT(*) FROM box_desafios_historial").fetchone()[0] == 0


def test_el_desafio_normal_no_se_rompe_por_la_narracion(base_datos_limpia, inicio):
    """Las acciones y la recompensa siguen siendo responsabilidad del desafío."""

    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    resultado = aceptar_desafio(desafio_id, GUILD, CONTRINCANTE, inicio, 1000, tipo="FIGHTING")

    from core.database import conectar_db

    with conectar_db() as db:
        acciones = db.execute(
            "SELECT COUNT(*) FROM box_acciones WHERE guild_id = ?", (GUILD,)
        ).fetchone()[0]

    assert acciones == 2
    assert resultado["ganador_id"] in (RETADOR, CONTRINCANTE)
    assert resultado["combate_id"]


# ============================================================
# Premio contra el bot
# ============================================================


def _dar_experiencia(user_id, valor):
    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id, experiencia)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET experiencia = excluded.experiencia
            """,
            (GUILD, user_id, valor),
        )
        db.commit()


def _dinero_de_accion(user_id):
    with conectar_db() as db:
        fila = db.execute(
            """
            SELECT dinero_recompensa
            FROM box_acciones
            WHERE guild_id = ?
            AND user_id = ?
            AND tipo = 'FIGHTING'
            """,
            (GUILD, user_id),
        ).fetchone()

    return fila[0] if fila is not None else None


def test_pelear_contra_el_bot_paga_un_cuarto_del_premio(
    base_datos_limpia, inicio
):
    """La pelea contra el bot reduce el premio a BOX_DESAFIO_PREMIO_VS_BOT.

    Ganarle a otro jugador paga la suma de las dos experiencias; ganarle a
    la casa paga un cuarto de eso, y la acción del ganador cobra exactamente
    lo que avisó el desafío.
    """

    _dar_experiencia(RETADOR, 1000)
    _dar_experiencia(CONTRINCANTE, 3000)

    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    resultado = aceptar_desafio(
        desafio_id,
        GUILD,
        CONTRINCANTE,
        inicio,
        recompensa=1000,
        tipo="FIGHTING",
        contrincante_es_bot=True,
    )

    assert resultado["estado"] == "aceptado"

    # El premio contra un jugador sería 1000 + 3000: contra el bot, un cuarto.
    assert resultado["premio_dinero"] == 1000

    ganador_id = resultado["ganador_id"]
    perdedor_id = CONTRINCANTE if ganador_id == RETADOR else RETADOR

    assert _dinero_de_accion(ganador_id) == 1000
    assert _dinero_de_accion(perdedor_id) == 0


def test_pelear_contra_otro_jugador_mantiene_el_premio_completo(
    base_datos_limpia, inicio
):
    """Sin marca de bot, el premio sigue siendo la suma de experiencias."""

    _dar_experiencia(RETADOR, 1000)
    _dar_experiencia(CONTRINCANTE, 3000)

    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    resultado = aceptar_desafio(
        desafio_id,
        GUILD,
        CONTRINCANTE,
        inicio,
        recompensa=1000,
        tipo="FIGHTING",
    )

    assert resultado["premio_dinero"] == 4000
    assert _dinero_de_accion(resultado["ganador_id"]) == 4000


def test_pelear_contra_el_bot_sin_experiencia_no_inventa_premio(
    base_datos_limpia, inicio
):
    """Con premio 0 la fracción del bot no fabrica dinero de la nada."""

    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )

    resultado = aceptar_desafio(
        desafio_id,
        GUILD,
        CONTRINCANTE,
        inicio,
        recompensa=1000,
        tipo="FIGHTING",
        contrincante_es_bot=True,
    )

    assert resultado["premio_dinero"] == 0
    assert _dinero_de_accion(resultado["ganador_id"]) == 0


def test_la_tarjeta_del_asalto_no_revela_el_tono(narrador, combate):
    """La sección "Pelea pactada" ya no anuncia el tono: era un spoiler.

    Un "tono remontada" del primer asalto le contaba al canal cómo iba a
    terminar la pelea antes de que terminara.
    """

    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    adelantar(0)
    correr(narrador._narrar_combate(combate))

    embed = canal.mensajes[0].embed
    pactada = next(
        campo for campo in embed.fields if campo.name == "Pelea pactada"
    )

    assert pactada.value == f"{plan.asaltos_pactados} asaltos"


def test_reclamar_un_asalto_dos_veces_no_duplica_el_mensaje(combate):
    primera = reclamar_asalto(combate["id"], 0, ahora())
    segunda = reclamar_asalto(combate["id"], 0, ahora())

    assert primera is True
    assert segunda is False
    assert asaltos_publicados(combate["id"]) == {0}


def test_cerrar_un_combate_lo_saca_de_los_vivos(combate):
    cerrar_combate(combate["id"], ESTADO_TERMINADO, ahora(), "terminado por prueba")

    assert obtener_combates_vivos(ahora()) == []


def test_latido_de_avanza_con_el_reloj(combate):
    inicio = combate["iniciado_en"]
    paso = combate["latido_segundos"]

    assert latido_de(combate, inicio) == 0
    assert latido_de(combate, inicio + timedelta(seconds=paso)) == 1
    assert latido_de(combate, inicio - timedelta(seconds=paso)) == 0


# ============================================================
# El latido del narrador
# ============================================================


def test_un_latido_revela_un_dialogo_y_no_manda_un_mensaje_nuevo(narrador, combate):
    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    correr(narrador._narrar_combate(combate))

    assert len(canal.mensajes) == 1, "el primer latido abre el mensaje del asalto"
    assert "Asalto 1 de" in canal.textos[0]
    assert f"1/{plan.dialogos_por_round} diálogos" in canal.textos[0]

    adelantar(1)
    correr(narrador._narrar_combate(combate))

    assert len(canal.mensajes) == 1, "un asalto es un solo mensaje"
    assert canal.mensajes[0].ediciones == 1


def test_el_asalto_se_edita_hasta_el_veredicto(narrador, combate):
    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    for latido in range(1, plan.dialogos_por_round + 1):
        adelantar(latido)
        correr(narrador._narrar_combate(combate))

    assert len(canal.mensajes) == 1
    assert "Asalto 1 para" in canal.textos[0] or "el corner corrige" in canal.textos[0]


def test_cada_asalto_tiene_su_mensaje(narrador, combate):
    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    # Hasta el último latido del segundo asalto: todavía no empezó el tercero.
    for latido in range(0, plan.ciclo * 2):
        adelantar(latido)
        correr(narrador._narrar_combate(combate))

    assert len(canal.mensajes) == 2, "un asalto, un mensaje"
    assert [m.id for m in canal.mensajes] == [1, 2]
    assert canal.mensajes[0].ediciones > 0
    assert canal.mensajes[1].ediciones > 0


def test_los_nombres_reales_reemplazan_los_del_plan(narrador, combate):
    narrador, canal, reloj, adelantar = narrador

    adelantar(0)
    correr(narrador._narrar_combate(combate))

    assert "Retador" not in canal.textos[0]
    assert "Rojo" in canal.textos[0] or "Azul" in canal.textos[0]


def test_el_combate_se_cierra_al_terminar_el_plan(narrador, combate):
    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    adelantar(plan.latidos)
    enviados = correr(narrador._narrar_combate(combate))

    assert enviados >= 1
    assert obtener_combates_vivos(reloj["ahora"]) == []
    assert "🏁" in canal.textos[-1]


def test_un_asalto_ya_publicado_no_se_vuelve_a_mandar(narrador, combate):
    """El catch-up no repite un asalto que el canal ya tiene."""

    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    # El asalto 0 ya está publicado (con un mensaje inventado del canal).
    reclamar_asalto(combate["id"], 0, reloj["ahora"])

    adelantar(plan.ciclo)  # arranca el asalto 1
    correr(narrador._narrar_combate(combate))

    assert len(canal.mensajes) == 1, "solo se abre el asalto nuevo"


def test_la_accion_cancelada_clausura_el_combate(narrador, combate):
    from core.database import conectar_db

    narrador, canal, reloj, adelantar = narrador

    with conectar_db() as db:
        db.execute("DELETE FROM box_acciones WHERE guild_id = ?", (GUILD,))
        db.commit()

    assert tiene_accion_activa(GUILD, RETADOR) is False

    correr(narrador._narrar_combate(combate))

    assert canal.mensajes == [], "una pelea cancelada no se narra"
    assert obtener_combates_vivos(reloj["ahora"]) == []

    with conectar_db() as db:
        estado = db.execute(
            "SELECT estado FROM box_combates WHERE id = ?", (combate["id"],)
        ).fetchone()[0]

    assert estado == ESTADO_CANCELADO
    assert ultimos_combates(GUILD)[0]["resumen"] == (
        "el combate se canceló antes del campanazo final"
    )


def test_un_mensaje_borrado_se_vuelve_a_publicar(narrador, combate):
    narrador, canal, reloj, adelantar = narrador

    adelantar(0)
    correr(narrador._narrar_combate(combate))

    canal.mensajes[0].borrado = True

    adelantar(2)
    correr(narrador._narrar_combate(combate))

    assert len(canal.mensajes) == 2, "si alguien borró el asalto, se reenvía"


def test_terminar_la_narracion_no_libera_la_accion(narrador, combate):
    """La pelea puede terminar en 12 minutos; la acción sigue bloqueando 24 h.

    Si liberar la acción dependiera del relato, ganarle al bot en el primer
    asalto sería una granja de experiencia.
    """

    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    adelantar(plan.latidos)
    correr(narrador._narrar_combate(combate))

    assert obtener_combates_vivos(reloj["ahora"]) == []
    assert tiene_accion_activa(GUILD, RETADOR) is True


# ============================================================
# /box combate
# ============================================================


def _cog_box(bot=None):
    from commands.box.cog import Box
    from tests.harness import construir_cog

    return construir_cog(Box, bot=bot)


def _llamar(cog, nombre, interaccion, *args):
    metodo = getattr(type(cog), nombre).callback

    return correr(metodo(cog, interaccion, *args))


def test_combate_sin_pelea_avisa(base_datos_limpia):
    from tests.harness import InteraccionFalsa

    interaccion = InteraccionFalsa(GUILD, RETADOR)

    _llamar(_cog_box(), "combate", interaccion)

    assert "Sin combate en vivo" in interaccion.texto


def test_combate_muestra_la_tarjeta_del_asalto(base_datos_limpia, inicio):
    from tests.harness import InteraccionFalsa

    desafio_id = crear_desafio(
        GUILD, RETADOR, CONTRINCANTE, inicio, inicio + timedelta(hours=1)
    )
    aceptar_desafio(
        desafio_id,
        GUILD,
        CONTRINCANTE,
        inicio,
        recompensa=1000,
        tipo="FIGHTING",
        canal_id=CANAL,
    )

    interaccion = InteraccionFalsa(GUILD, RETADOR)

    _llamar(_cog_box(), "combate", interaccion)

    texto = interaccion.texto

    assert "Asalto 1 de" in texto
    assert "Marcador" not in texto
    assert "Asaltos" in texto and "Estado físico" in texto
    assert "próxima línea en" in texto


def test_box_combate_se_lee_igual_que_el_mensaje_del_canal(narrador, combate):
    """El comando y el narrador comparten el render: no hay dos versiones.

    Si /box combate armara su propio texto, cualquier diferencia de formato
    (un recorte distinto, un marcador mal acumulado) se vería recién en el
    canal, que es justamente donde no se puede depurar.
    """

    from tests.harness import InteraccionFalsa

    narrador, canal, reloj, adelantar = narrador

    adelantar(3)
    correr(narrador._narrar_combate(combate))

    descripcion = canal.mensajes[0].embed.description

    guild = GuildFalso(
        {
            RETADOR: MiembroFalso(RETADOR, "Rojo"),
            CONTRINCANTE: MiembroFalso(CONTRINCANTE, "Azul"),
        }
    )
    interaccion = InteraccionFalsa(GUILD, RETADOR)
    interaccion.guild = guild

    # Los nombres los resuelve el bot, no la interacción: es lo que hace el
    # narrador con el canal, y el comando tiene que coincidir con él.
    _llamar(_cog_box(BotFalso(guild=guild)), "combate", interaccion)

    for linea in [l for l in descripcion.split("\n") if l.strip()]:
        assert linea in interaccion.texto, f"falta en /box combate: {linea}"


def test_el_historial_guarda_la_tarjeta_del_combate(narrador, combate):
    """``cerrar_combate`` persiste el resumen: es lo único que queda en claro."""

    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    adelantar(plan.latidos)
    correr(narrador._narrar_combate(combate))

    [ultimo] = ultimos_combates(GUILD)

    assert ultimo["estado"] == ESTADO_TERMINADO
    assert ultimo["modo"] == "FIGHTING"
    assert ultimo["retador_id"] == RETADOR
    assert ultimo["contrincante_id"] == CONTRINCANTE

    # Se guarda la tarjeta tal como se leyó en el canal, con los apodos del
    # momento: el historial es una transcripción, no un join vivo (si mañana
    # alguien se cambia el nombre, la crónica de esa pelea no se reescribe).
    tarjeta = [
        campo.value
        for campo in canal.mensajes[-1].embed.fields
        if campo.name == "Tarjeta"
    ][0]

    assert ultimo["resumen"] == tarjeta
    assert "por decision" in ultimo["resumen"] or "por ko" in ultimo["resumen"]

    # La tarjeta se lee desde el ganador: "X gana 2-1", no el marcador (A, B).
    tarjeta_puntaje = "-".join(str(n) for n in sorted(plan.marcador, reverse=True))

    assert tarjeta_puntaje in ultimo["resumen"]

# ============================================================
# Un solo combate a la vez
# ============================================================


def _desafiar(inicio, retador, contrincante, guild=GUILD, tipo="FIGHTING"):
    """Crea y acepta un desafío, sin pasar por Discord."""

    for user_id in (retador, contrincante):
        with conectar_db() as db:
            db.execute(
                """
                INSERT INTO box_usuarios (guild_id, user_id, experiencia)
                VALUES (?, ?, 200000)
                ON CONFLICT(guild_id, user_id) DO NOTHING
                """,
                (guild, user_id),
            )
            db.commit()

    desafio_id = crear_desafio(
        guild, retador, contrincante, inicio, inicio + timedelta(hours=1)
    )

    return desafio_id, aceptar_desafio(
        desafio_id,
        guild,
        contrincante,
        inicio,
        recompensa=1000,
        tipo=tipo,
        canal_id=CANAL,
    )


def test_una_pelea_en_curso_bloquea_la_siguiente(combate, inicio):
    _, resultado = _desafiar(inicio, 33, 44)

    assert resultado["estado"] == "combate_en_curso"
    assert resultado["combate"]["retador_id"] == RETADOR
    assert resultado["combate"]["contrincante_id"] == CONTRINCANTE
    assert resultado["combate"]["modo"] == "FIGHTING"

    en_curso = combate_en_curso(GUILD)

    assert en_curso is not None
    assert en_curso["id"] == combate["id"]


def test_el_desafio_bloqueado_sigue_pendiente(combate, inicio):
    """Rechazar por velada ocupada no quema el desafío: se puede aceptar después."""

    desafio_id, resultado = _desafiar(inicio, 33, 44)

    assert resultado["estado"] == "combate_en_curso"

    with conectar_db() as db:
        pendiente = db.execute(
            "SELECT COUNT(*) FROM box_desafios WHERE id = ?", (desafio_id,)
        ).fetchone()[0]

    assert pendiente == 1

    # Y al cerrar la pelea que estorbaba, entra solo.
    cerrar_combate(combate["id"], ESTADO_TERMINADO, ahora(), "cierre de prueba")
    segundo = aceptar_desafio(
        desafio_id,
        GUILD,
        44,
        inicio + timedelta(minutes=1),
        recompensa=1000,
        tipo="FIGHTING",
        canal_id=CANAL,
    )

    assert segundo["estado"] == "aceptado"


def test_sin_pelea_en_curso_no_hay_candado(base_datos_limpia, inicio):
    assert combate_en_curso(GUILD) is None

    _, resultado = _desafiar(inicio, 11, 22)

    assert resultado["estado"] == "aceptado"


def test_el_candado_global_mira_todos_los_servidores(combate, inicio):
    """Con el default (bot de servidores privados) otro guild tampoco entra."""

    _, resultado = _desafiar(inicio, 33, 44, guild=OTRO_GUILD)

    assert resultado["estado"] == "combate_en_curso"

    # El candado global responde por cualquiera: preguntes por el guild que
    # preguntes, te dice cuál es la pelea que está ocupando el bot.
    assert combate_en_curso(OTRO_GUILD)["guild_id"] == GUILD
    assert combate_en_curso() is not None


def test_el_candado_por_servidor_deja_pelear_al_resto(combate, inicio, monkeypatch):
    monkeypatch.setattr(
        "modules.box.database.BOX_COMBATE_UNICO_GLOBAL", False
    )

    _, resultado = _desafiar(inicio, 33, 44, guild=OTRO_GUILD)

    assert resultado["estado"] == "aceptado"
    assert combate_en_curso(OTRO_GUILD) is not None

    # Y en su propio servidor, el segundo todavía choca contra el primero.
    _, otro = _desafiar(inicio, 55, 66)

    assert otro["estado"] == "combate_en_curso"


def test_un_canal_perdido_no_deja_el_candado_colgado(combate, narrador, inicio):
    """Sin canal no se narra, pero la fila tampoco puede quedar viva para siempre.

    El candado de "una pelea a la vez" convierte un canal borrado en un bot
    inútil si la fila no se cierra nunca: por eso, pasada la ventana de
    narración con el canal introutable, el combate se da por cancelado.
    """

    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    sin_canal = Narrador(None, {})

    adelantar(plan.latidos + 40)
    correr(sin_canal._narrar_combate(combate))

    assert combate_en_curso(GUILD) is None
    assert canal.mensajes == []
    assert ultimos_combates(GUILD)[0]["resumen"] == (
        "el canal de narración no volvió a estar disponible"
    )


def test_un_canal_incontactable_a_mitad_de_la_pelea_espera(base_datos_limpia, narrador, combate):
    """Lo mismo, pero todavía dentro de la ventana: no se cierra nada.

    Un ``get_channel`` que devuelve ``None`` porque el guild todavía no está
    cachado tras un reinicio es transitorio; cerraría una pelea que está
    a medio contar.
    """

    narrador, canal, reloj, adelantar = narrador
    plan = Plan.de_json(combate["plan"])

    assert 2 < plan.latidos, "el latido 2 ya sería el final: nada que esperar"

    sin_canal = Narrador(None, {})

    adelantar(2)
    correr(sin_canal._narrar_combate(combate))

    assert combate_en_curso(GUILD) is not None
    assert obtener_combates_vivos(reloj["ahora"])[0]["estado"] == ESTADO_VIVO
    assert canal.mensajes == []


# ============================================================
# El equipamiento, del box_equipo al plan guardado
# ============================================================


def test_el_equipamiento_de_la_tienda_llega_al_plan(base_datos_limpia, inicio):
    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_equipo (guild_id, user_id, protector_bucal, guantes)
            VALUES (?, ?, 4, 4)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                protector_bucal = 4, guantes = 4
            """,
            (GUILD, 11),
        )
        db.commit()

    _desafiar(inicio, 11, 22)
    plan = Plan.de_json(obtener_combates_vivos(inicio)[0]["plan"])

    # El retador viene mejor preparado: más vida pactada y no es el vencido
    # en la comparación de fuerza.
    assert plan.vida_maxima[0] > plan.vida_maxima[1]
    assert plan.probabilidad > 0.5


def test_sin_equipar_las_vidas_son_las_de_configuracion(base_datos_limpia, inicio):
    _, resultado = _desafiar(inicio, 11, 22)
    plan = Plan.de_json(obtener_combates_vivos(inicio)[0]["plan"])

    assert plan.vida_maxima == (BOX_VIDA_INICIAL, BOX_VIDA_INICIAL)
    assert resultado["estado"] == "aceptado"


# ============================================================
# El consentimiento del servidor para los cánticos
# ============================================================


def test_mientras_nadie_decide_rige_la_configuracion(base_datos_limpia):
    assert obtener_canticos(GUILD) is None


def test_la_decision_del_servidor_se_guarda_y_se_lee(base_datos_limpia):
    fijar_canticos(GUILD, True, 999, ahora())

    assert obtener_canticos(GUILD) is True

    fijar_canticos(GUILD, False, 999, ahora())

    assert obtener_canticos(GUILD) is False


def test_el_narrador_respeta_la_decision_del_servidor(narrador):
    """El flag que usa el latido sale de la base de datos, no del entorno.

    Es el conducto del consentimiento: si el narrador leyera la constante de
    configuración directamente, un servidor que dijo "no" seguiría escuchando
    apodos propios en cuanto otro pidiera los cánticos.
    """

    narrador, canal, reloj, adelantar = narrador

    fijar_canticos(GUILD, True, 999, ahora())

    assert correr(narrador._cantos_del_servidor(GUILD)) is True

    fijar_canticos(GUILD, False, 999, ahora())

    assert correr(narrador._cantos_del_servidor(GUILD)) is False

    # Sin decisión del servidor se cae al default del entorno, que en el repo
    # está apagado.
    with conectar_db() as db:
        db.execute("DELETE FROM box_config_guild")
        db.commit()

    assert correr(narrador._cantos_del_servidor(GUILD)) == BOX_COMBATE_CANTICOS
