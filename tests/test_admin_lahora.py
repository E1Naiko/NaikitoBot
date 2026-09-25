"""Administración del canal 420: importación del historial y altas/bajas.

Los comandos se invocan por su callback real con interacciones falsas;
el historial del canal se simula con un canal que implementa
``history()`` igual que discord.py (iterable asíncrono, en orden).
"""

from datetime import date, datetime, timezone

import pytest

from config import TIMEZONE
from modules.lahora.services import (
    importar_mensajes,
    obtener_hoy_lahora,
    obtener_top_lahora,
    registrar_lahora,
)
from tests.harness import (
    Choice,
    GuildFalso,
    InteraccionFalsa,
    UsuarioFalso,
    construir_cog,
    prohibido,
)

GUILD = 1
ADMIN = 1
USUARIO = 42
CANAL_420 = 420


def local(hora, minuto, segundo=0, dia=5, micro=0):
    return datetime(2026, 9, dia, hora, minuto, segundo, micro, tzinfo=TIMEZONE)


# ============================================================
# DOBLES
# ============================================================

class _Autor:
    def __init__(self, user_id, nombre, bot=False):
        self.id = user_id
        self.display_name = nombre
        self.bot = bot


class MensajeHistorial:
    _siguiente = 5000

    def __init__(self, contenido, momento, user_id=USUARIO, nombre="Tester",
                 bot=False, editado=None):
        MensajeHistorial._siguiente += 1
        self.id = MensajeHistorial._siguiente
        self.content = contenido
        self.created_at = momento.astimezone(timezone.utc)
        self.edited_at = editado.astimezone(timezone.utc) if editado else None
        self.author = _Autor(user_id, nombre, bot)


class CanalConHistorial:
    """Canal con ``history`` como el de discord.py."""

    def __init__(self, mensajes, canal_id=CANAL_420, error=None):
        self.id = canal_id
        self._mensajes = mensajes
        self._error = error
        self.llamadas = []

    def history(self, limit=None, after=None, oldest_first=None):
        self.llamadas.append({"limit": limit, "after": after, "oldest_first": oldest_first})

        async def generar():
            ordenados = sorted(self._mensajes, key=lambda m: m.created_at)
            for mensaje in ordenados:
                if after is not None and mensaje.created_at <= after:
                    continue
                yield mensaje
            if self._error is not None:
                raise self._error

        return generar()


async def iterar(lista):
    for elemento in lista:
        yield elemento


@pytest.fixture
def admin_ids(monkeypatch):
    monkeypatch.setattr("core.permissions.ADMIN_USER_IDS", {ADMIN})


@pytest.fixture
async def cog(base_datos_limpia, admin_ids):
    from commands.admin.cog import Admin
    from modules.lahora.database import inicializar_db

    await inicializar_db()
    return construir_cog(Admin)


def interaccion_admin(canal=None):
    interaccion = InteraccionFalsa(GUILD, ADMIN, nombre="Admin")
    if canal is not None:
        interaccion.guild = GuildFalso(GUILD, canales={canal.id: canal})
    return interaccion


async def llamar(cog, nombre, interaccion, *args):
    return await getattr(type(cog), nombre).callback(cog, interaccion, *args)


def usuario(user_id=USUARIO, nombre="Tester"):
    return UsuarioFalso(user_id, nombre)


# ============================================================
# SERVICIO DE IMPORTACIÓN
# ============================================================

async def test_importa_solo_los_420_validos(cog):
    mensajes = [
        MensajeHistorial("420", local(16, 20, 3), user_id=1, nombre="Uno"),
        MensajeHistorial("4:20 🌿", local(16, 20, 8), user_id=2, nombre="Dos"),
        MensajeHistorial("420", local(16, 20, 9), user_id=1),  # repetido
        MensajeHistorial("420", local(16, 21, 0), user_id=3),  # tarde
        MensajeHistorial("hola", local(16, 20, 1), user_id=4),  # no es 420
        MensajeHistorial("420", local(16, 20, 1), user_id=5, bot=True),
        MensajeHistorial("420", local(4, 20, 30, dia=6), user_id=2, nombre="Dos"),
    ]

    resumen = await importar_mensajes(GUILD, iterar(mensajes))

    assert resumen.revisados == 7
    assert resumen.detectados == 5
    assert resumen.importados == 3
    assert resumen.repetidos == 1
    assert resumen.fuera_de_horario == 1
    assert resumen.primero.date() == date(2026, 9, 5)
    assert resumen.ultimo.date() == date(2026, 9, 6)

    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert [(p, n) for p, n, _, _ in hoy["16:20"]] == [(1, "Uno"), (2, "Dos")]


async def test_importar_dos_veces_no_duplica(cog):
    mensajes = [MensajeHistorial("420", local(16, 20, 3))]

    await importar_mensajes(GUILD, iterar(mensajes))
    segundo = await importar_mensajes(GUILD, iterar(mensajes))

    assert segundo.importados == 0
    assert segundo.repetidos == 1
    assert len(await obtener_top_lahora(GUILD)) == 1


async def test_reordena_con_registros_en_vivo(cog):
    """El bot registró en vivo al que llegó 2º; el importador trae al 1º."""

    await registrar_lahora(GUILD, 2, "EnVivo", local(16, 20, 10))

    await importar_mensajes(
        GUILD,
        iterar([
            MensajeHistorial("420", local(16, 20, 2), user_id=1, nombre="Viejo"),
            MensajeHistorial("420", local(16, 20, 10), user_id=2, nombre="EnVivo"),
        ]),
    )

    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert [(p, n) for p, n, _, _ in hoy["16:20"]] == [(1, "Viejo"), (2, "EnVivo")]
    # El bonus del primero pasó al que realmente llegó antes.
    puntos = {n: pts for _, n, _, pts in hoy["16:20"]}
    assert puntos["Viejo"] > 15
    assert puntos["EnVivo"] < 15


async def test_mismo_segundo_ordena_por_milisegundos(cog):
    await importar_mensajes(
        GUILD,
        iterar([
            MensajeHistorial("420", local(16, 20, 5, micro=900000), user_id=2, nombre="Lento"),
            MensajeHistorial("420", local(16, 20, 5, micro=100000), user_id=1, nombre="Rápido"),
        ]),
    )

    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert [n for _, n, _, _ in hoy["16:20"]] == ["Rápido", "Lento"]


async def test_editado_despues_de_la_ventana_no_cuenta(cog):
    mensajes = [
        MensajeHistorial("420", local(16, 20, 3), user_id=1,
                         editado=local(18, 0)),
        MensajeHistorial("420", local(16, 20, 4), user_id=2,
                         editado=local(16, 20, 30)),
    ]

    resumen = await importar_mensajes(GUILD, iterar(mensajes))

    assert resumen.editados == 1
    assert resumen.importados == 1


async def test_llama_al_progreso(cog):
    llamadas = []

    async def progreso(resumen):
        llamadas.append(resumen.revisados)

    mensajes = [MensajeHistorial("hola", local(12, 0)) for _ in range(5)]
    await importar_mensajes(GUILD, iterar(mensajes), al_progresar=progreso, cada=2)

    assert llamadas == [2, 4]


# ============================================================
# /admin 420 importar
# ============================================================

async def test_comando_importar_usa_el_canal_configurado(cog, monkeypatch):
    canal = CanalConHistorial([
        MensajeHistorial("420", local(16, 20, 3), user_id=1, nombre="Uno"),
        MensajeHistorial("420", local(4, 20, 3, dia=6), user_id=2, nombre="Dos"),
    ])
    monkeypatch.setattr("config.LAHORA_CANALES_ID", {CANAL_420})
    interaccion = interaccion_admin(canal)

    await llamar(cog, "lahora_importar", interaccion)

    assert canal.llamadas[0]["limit"] is None
    assert canal.llamadas[0]["oldest_first"] is True
    assert "Importación terminada" in interaccion.texto
    assert "Importados: **2**" in interaccion.texto
    assert "05/09/2026" in interaccion.texto
    assert len(await obtener_top_lahora(GUILD)) == 2


async def test_comando_importar_filtra_desde(cog):
    canal = CanalConHistorial([
        MensajeHistorial("420", local(16, 20, 3, dia=1), user_id=1),
        MensajeHistorial("420", local(16, 20, 3, dia=5), user_id=2),
    ])
    interaccion = interaccion_admin(canal)

    await llamar(cog, "lahora_importar", interaccion, canal, "2026-09-03")

    assert canal.llamadas[0]["after"] == datetime(2026, 9, 3, tzinfo=TIMEZONE)
    assert "Importados: **1**" in interaccion.texto


async def test_comando_importar_sin_permiso_avisa(cog):
    canal = CanalConHistorial([], error=prohibido())
    interaccion = interaccion_admin(canal)

    await llamar(cog, "lahora_importar", interaccion, canal)

    assert "Importación con avisos" in interaccion.texto
    assert "permiso para leer el historial" in interaccion.texto


async def test_comando_importar_corte_parcial_conserva_lo_leido(cog):
    import discord

    from tests.harness import _Respuesta404

    canal = CanalConHistorial(
        [MensajeHistorial("420", local(16, 20, 3))],
        error=discord.HTTPException(_Respuesta404(), "se cortó"),
    )
    interaccion = interaccion_admin(canal)

    await llamar(cog, "lahora_importar", interaccion, canal)

    assert "Importados: **1**" in interaccion.texto
    assert "cortó la lectura" in interaccion.texto


async def test_comando_importar_sin_canal_configurado(cog, monkeypatch):
    monkeypatch.setattr("config.LAHORA_CANALES_ID", set())
    interaccion = interaccion_admin()

    await llamar(cog, "lahora_importar", interaccion)

    assert "LAHORA_CANALES_ID" in interaccion.texto


async def test_comando_importar_fecha_invalida(cog):
    interaccion = interaccion_admin()

    await llamar(cog, "lahora_importar", interaccion, None, "25/09/2026")

    assert "Fecha inválida" in interaccion.texto


async def test_comando_importar_requiere_admin(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "lahora_importar", interaccion)

    assert "Sin permisos" in interaccion.texto


# ============================================================
# /admin 420 manualadd
# ============================================================

async def test_manualadd_registra(cog):
    interaccion = interaccion_admin()

    await llamar(cog, "lahora_manualadd", interaccion, usuario(), "2026-09-05", "16:20:07")

    assert "420 registrado" in interaccion.texto
    assert "Posición: **1**" in interaccion.texto
    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert hoy["16:20"][0][2] == 7


async def test_manualadd_anterior_desplaza_al_primero(cog):
    await registrar_lahora(GUILD, 7, "Otro", local(16, 20, 10))

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_manualadd", interaccion, usuario(), "2026-09-05", "16:20:02")

    assert "Posición: **1**" in interaccion.texto
    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert [(p, n) for p, n, _, _ in hoy["16:20"]] == [(1, "Tester"), (2, "Otro")]


async def test_manualadd_hora_sin_segundos(cog):
    interaccion = interaccion_admin()

    await llamar(cog, "lahora_manualadd", interaccion, usuario(), "2026-09-05", "04:20")

    assert "Segundo: **0**" in interaccion.texto


@pytest.mark.parametrize(
    "fecha, hora, esperado",
    [
        ("2026-09-05", "16:21:00", "Fuera de horario"),
        ("05/09/2026", "16:20", "Fecha inválida"),
        ("2026-09-05", "4.20", "Hora inválida"),
        ("2999-01-01", "16:20", "futuro"),
    ],
)
async def test_manualadd_valida(cog, fecha, hora, esperado):
    interaccion = interaccion_admin()

    await llamar(cog, "lahora_manualadd", interaccion, usuario(), fecha, hora)

    assert esperado in interaccion.texto
    assert await obtener_top_lahora(GUILD) == []


async def test_manualadd_ya_registrado(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 10))

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_manualadd", interaccion, usuario(), "2026-09-05", "16:20:30")

    assert "ya tiene un 420" in interaccion.texto


# ============================================================
# BAJAS, VER Y STATS
# ============================================================

async def test_resetdia_una_ventana_promueve_al_segundo(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 1))
    await registrar_lahora(GUILD, 7, "Otro", local(16, 20, 5))
    await registrar_lahora(GUILD, USUARIO, "Tester", local(4, 20, 5))

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_resetdia", interaccion, usuario(), "2026-09-05", Choice("16:20"))

    assert "Se borraron **1**" in interaccion.texto
    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert [(p, n) for p, n, _, _ in hoy["16:20"]] == [(1, "Otro")]
    assert hoy["16:20"][0][3] > 15  # ahora tiene el bonus del primero
    assert "04:20" in hoy


async def test_resetdia_todo_el_dia(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 1))
    await registrar_lahora(GUILD, USUARIO, "Tester", local(4, 20, 5))

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_resetdia", interaccion, usuario(), "2026-09-05", None)

    assert "Se borraron **2**" in interaccion.texto


async def test_resetdia_sin_registros(cog):
    interaccion = interaccion_admin()

    await llamar(cog, "lahora_resetdia", interaccion, usuario(), "2026-09-05", None)

    assert "no tiene 420" in interaccion.texto


async def test_ver_lista_registros(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 4), mensaje_id=99)
    interaccion = interaccion_admin()
    await llamar(cog, "lahora_manualadd", interaccion, usuario(), "2026-09-04", "04:20:09")

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_ver", interaccion, usuario())

    texto = interaccion.texto
    assert "05/09/2026" in texto and "16:20" in texto
    assert "04/09/2026" in texto and "manual" in texto
    assert texto.index("05/09/2026") < texto.index("04/09/2026")


async def test_resetusuario_recalcula(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 1))
    await registrar_lahora(GUILD, 7, "Otro", local(16, 20, 5))

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_resetusuario", interaccion, usuario())

    assert "Se borraron **1**" in interaccion.texto
    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert hoy["16:20"][0][:2] == (1, "Otro")


async def test_resettotal_requiere_confirmacion(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 1))

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_resettotal", interaccion, Choice("NO"))
    assert "cancelada" in interaccion.texto
    assert len(await obtener_top_lahora(GUILD)) == 1

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_resettotal", interaccion, Choice("SI"))
    assert "Se borraron **1**" in interaccion.texto
    assert await obtener_top_lahora(GUILD) == []


async def test_stats(cog):
    await registrar_lahora(GUILD, USUARIO, "Tester", local(16, 20, 0))
    await registrar_lahora(GUILD, 7, "Otro", local(16, 20, 30))

    interaccion = interaccion_admin()
    await llamar(cog, "lahora_stats", interaccion)

    assert "Usuarios: **2**" in interaccion.texto
    assert "420 registrados: **2**" in interaccion.texto


# ============================================================
# fileexecute
# ============================================================

@pytest.fixture
async def cog_en_arbol(base_datos_limpia, admin_ids):
    import discord
    from discord.ext import commands

    from modules.lahora.database import inicializar_db

    await inicializar_db()
    bot = commands.Bot(command_prefix="$!", intents=discord.Intents.default())
    await bot.load_extension("commands.admin")
    return bot.get_cog("Admin")


class AdjuntoFalso:
    def __init__(self, contenido):
        self.filename = "comandos.txt"
        self._contenido = contenido.encode("utf-8")
        self.size = len(self._contenido)

    async def read(self):
        return self._contenido


async def test_fileexecute_carga_varios_420(cog_en_arbol):
    interaccion = interaccion_admin()
    interaccion.guild = GuildFalso(
        GUILD,
        {USUARIO: usuario(), 7: usuario(7, "Otro")},
    )

    await llamar(
        cog_en_arbol,
        "fileexecute",
        interaccion,
        AdjuntoFalso(
            "420 manualadd 42 2026-09-05 16:20:09\n"
            "420 manualadd <@7> 2026-09-05 16:20:02\n"
            "420 importar\n"
        ),
    )

    assert "✅ Línea 1" in interaccion.texto
    assert "✅ Línea 2" in interaccion.texto
    assert "❌ Línea 3" in interaccion.texto
    hoy = await obtener_hoy_lahora(GUILD, date(2026, 9, 5))
    assert [(p, n) for p, n, _, _ in hoy["16:20"]] == [(1, "Otro"), (2, "Tester")]
