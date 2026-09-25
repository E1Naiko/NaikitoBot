"""laHora (canal 420) de punta a punta: servicio, listener y comandos.

El listener ``on_message`` se ejecuta con mensajes falsos y los slash
commands a través de su callback real, igual que en Madrugue.
"""

import asyncio
import importlib
from datetime import datetime, timedelta, timezone

import discord
import pytest

from config import TIMEZONE
from modules.lahora.services import registrar_lahora
from tests.harness import InteraccionFalsa, construir_cog

GUILD = 1
CANAL_420 = 420
OTRO_CANAL = 999
USUARIO = 42


def local(hora, minuto, segundo=0, dia=5):
    return datetime(2026, 9, dia, hora, minuto, segundo, tzinfo=TIMEZONE)


@pytest.fixture
async def cog(base_datos_limpia, monkeypatch):
    from commands.lahora.cog import LaHora
    from modules.lahora.database import inicializar_db

    await inicializar_db()
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_420})

    return construir_cog(LaHora)


async def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return await metodo(cog, interaccion, *args)


def fijar_hoy(monkeypatch, momento):
    """Fija la fecha que ven /420_stats y /420_hoy."""

    info = importlib.import_module("commands.lahora.info")
    monkeypatch.setattr(info, "ahora", lambda: momento)


# ============================================================
# DOBLES DE MENSAJE
# ============================================================

class _Autor:
    def __init__(self, user_id, nombre, bot=False):
        self.id = user_id
        self.display_name = nombre
        self.bot = bot


class _Canal:
    def __init__(self, canal_id):
        self.id = canal_id


class _Guild:
    def __init__(self, guild_id):
        self.id = guild_id


class MensajeFalso:
    _siguiente_id = 1000

    def __init__(
        self,
        contenido,
        momento,
        user_id=USUARIO,
        nombre="Tester",
        canal=CANAL_420,
        bot=False,
        en_servidor=True,
        falla_reaccion=False,
    ):
        MensajeFalso._siguiente_id += 1
        self.id = MensajeFalso._siguiente_id
        self.content = contenido
        # Discord entrega created_at en UTC.
        self.created_at = momento.astimezone(timezone.utc)
        self.author = _Autor(user_id, nombre, bot)
        self.channel = _Canal(canal)
        self.guild = _Guild(GUILD) if en_servidor else None
        self.reacciones = []
        self._falla_reaccion = falla_reaccion

    async def add_reaction(self, emoji):
        if self._falla_reaccion:
            from tests.harness import prohibido

            raise prohibido()
        self.reacciones.append(emoji)


async def enviar(cog, mensaje):
    await type(cog).on_message(cog, mensaje)
    return mensaje


# ============================================================
# SERVICIO
# ============================================================

async def test_registra_dentro_de_la_ventana(cog):
    resultado = await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 0))

    assert resultado.exitoso
    assert resultado.ventana == "16:20"
    assert resultado.posicion == 1
    assert resultado.puntos_finales == 20.0


async def test_convierte_utc_a_hora_local(cog):
    # 19:20 UTC == 16:20 en Argentina (UTC-3).
    momento_utc = datetime(2026, 9, 5, 19, 20, 10, tzinfo=timezone.utc)

    resultado = await registrar_lahora(GUILD, USUARIO, "Tester", momento_utc)

    assert resultado.exitoso
    assert resultado.ventana == "16:20"
    assert resultado.segundos == 10


@pytest.mark.parametrize(
    "momento",
    [local(16, 19, 59), local(16, 21, 0), local(12, 0)],
)
async def test_fuera_de_horario(cog, momento):
    resultado = await registrar_lahora(GUILD, USUARIO, "Tester", momento)

    assert not resultado.exitoso
    assert resultado.motivo == "fuera_de_horario"


async def test_un_420_por_ventana(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 1))
    repetido = await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 5))

    assert repetido.motivo == "ya_registrado"


async def test_dos_ventanas_el_mismo_dia(cog):
    manana = await registrar_lahora(GUILD, USUARIO, "Tester", local(4, 20, 3))
    tarde = await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 3))

    assert manana.exitoso and tarde.exitoso
    assert (manana.ventana, tarde.ventana) == ("04:20", "16:20")


async def test_posiciones_por_orden_de_llegada(cog):
    primero = await registrar_lahora(GUILD, 1, "Uno", local(16, 20, 2))
    segundo = await registrar_lahora(GUILD, 2, "Dos", local(16, 20, 3))

    assert (primero.posicion, segundo.posicion) == (1, 2)
    assert primero.bonus_posicion == 5
    assert segundo.bonus_posicion == 0


async def test_mensajes_simultaneos_no_repiten_posicion(cog):
    resultados = await asyncio.gather(
        *(
            registrar_lahora(GUILD, user_id, f"U{user_id}", local(16, 20, 5))
            for user_id in range(1, 6)
        )
    )

    assert sorted(resultado.posicion for resultado in resultados) == [1, 2, 3, 4, 5]


async def test_mismo_usuario_simultaneo_se_registra_una_vez(cog):
    resultados = await asyncio.gather(
        registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 5)),
        registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 6)),
    )

    assert sum(resultado.exitoso for resultado in resultados) == 1


# ============================================================
# LISTENER on_message
# ============================================================

async def test_mensaje_valido_reacciona_y_registra(cog):
    mensaje = await enviar(cog, MensajeFalso("420", local(16, 20, 1)))

    assert mensaje.reacciones == ["🌿", "🥇"]


async def test_segundo_en_llegar_no_recibe_medalla(cog):
    await enviar(cog, MensajeFalso("420", local(16, 20, 1), user_id=1))
    mensaje = await enviar(cog, MensajeFalso("4:20", local(16, 20, 2), user_id=2))

    assert mensaje.reacciones == ["🌿"]


async def test_repetido_no_reacciona(cog):
    await enviar(cog, MensajeFalso("420", local(16, 20, 1)))
    mensaje = await enviar(cog, MensajeFalso("420", local(16, 20, 9)))

    assert mensaje.reacciones == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"contenido": "420", "momento": local(16, 21, 0)},
        {"contenido": "hola", "momento": local(16, 20, 1)},
        {"contenido": "420", "momento": local(16, 20, 1), "canal": OTRO_CANAL},
        {"contenido": "420", "momento": local(16, 20, 1), "bot": True},
        {"contenido": "420", "momento": local(16, 20, 1), "en_servidor": False},
    ],
    ids=["fuera_de_horario", "no_es_420", "otro_canal", "bot", "dm"],
)
async def test_mensajes_ignorados(cog, kwargs):
    from modules.lahora.services import obtener_top_lahora

    mensaje = await enviar(cog, MensajeFalso(**kwargs))

    assert mensaje.reacciones == []
    assert await obtener_top_lahora(GUILD) == []


async def test_sin_permiso_de_reaccion_igual_registra(cog):
    from modules.lahora.services import obtener_top_lahora

    await enviar(
        cog,
        MensajeFalso("420", local(16, 20, 1), falla_reaccion=True),
    )

    assert len(await obtener_top_lahora(GUILD)) == 1


async def test_usa_la_hora_del_mensaje_y_no_la_de_procesamiento(cog):
    """Un 420 de 16:20:59 cuenta aunque se procese a las 16:21."""

    mensaje = await enviar(cog, MensajeFalso("420", local(16, 20, 59)))

    assert mensaje.reacciones == ["🌿", "🥇"]


# ============================================================
# SLASH COMMANDS
# ============================================================

@pytest.mark.parametrize("comando", ["stats", "top", "hoy", "ayuda"])
async def test_comandos_responden_sin_datos(cog, monkeypatch, comando):
    fijar_hoy(monkeypatch, local(18, 0))
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, comando, interaccion)

    assert interaccion.cantidad_respuestas == 1


async def test_top_ordena_por_puntos(cog):
    await registrar_lahora(GUILD, 1, "Rápido", local(16, 20, 0))
    await registrar_lahora(GUILD, 2, "Lento", local(16, 20, 50))
    await registrar_lahora(GUILD, 2, "Lento", local(4, 20, 50, dia=6))

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "top", interaccion)

    texto = interaccion.texto
    assert texto.index("Lento") < texto.index("Rápido")
    assert "2 × 420" in texto


async def test_top_no_duplica_si_cambia_el_apodo(cog):
    await registrar_lahora(GUILD, USUARIO, "Viejo", local(16, 20, 0))
    await registrar_lahora(GUILD, USUARIO, "Nuevo", local(16, 20, 0, dia=6))

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "top", interaccion)

    assert "Nuevo" in interaccion.texto
    assert "Viejo" not in interaccion.texto


async def test_stats_muestra_rachas_y_primeros(cog, monkeypatch):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 0, dia=4))
    await registrar_lahora(GUILD, USUARIO, "Tester", local(4, 20, 7, dia=5))
    await registrar_lahora(GUILD, 7, "Otro", local(16, 20, 1, dia=5))
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 9, dia=5))
    fijar_hoy(monkeypatch, local(18, 0))

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "stats", interaccion)

    texto = interaccion.texto
    assert "420 registrados: **3**" in texto
    assert "Veces primero: **2**" in texto
    assert "Racha actual: **2 días**" in texto
    assert "Mejor tiempo: **0 s**" in texto


async def test_hoy_lista_por_ventana(cog, monkeypatch):
    await registrar_lahora(GUILD, 1, "Mañanero", local(4, 20, 3))
    await registrar_lahora(GUILD, 2, "Tardero", local(16, 20, 4))
    await registrar_lahora(GUILD, 3, "Ayer", local(16, 20, 4) - timedelta(days=1))
    fijar_hoy(monkeypatch, local(18, 0))

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "hoy", interaccion)

    texto = interaccion.texto
    assert "04:20" in texto and "Mañanero" in texto
    assert "16:20" in texto and "Tardero" in texto
    assert "Ayer" not in texto


def test_nombres_de_comandos_validos():
    from commands.lahora.cog import LaHora

    nombres = {comando.name for comando in LaHora.__cog_app_commands__}

    assert nombres == {"420_stats", "420_top", "420_hoy", "420_ayuda"}


def test_color_propio():
    from core.mensajes import COLOR_LAHORA, color

    assert color("lahora") == COLOR_LAHORA
    assert isinstance(COLOR_LAHORA, discord.Color)
