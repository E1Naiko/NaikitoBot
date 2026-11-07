"""Pruebas del sistema de sanciones por trampa.

Cubren tres capas: la lógica pura del temporizador, la persistencia en
SQLite y el bloqueo real de cada minijuego a través de sus comandos.
"""

from datetime import datetime, timedelta

import pytest

from config import TIMEZONE
from tests.harness import InteraccionFalsa, construir_cog

GUILD = 1
ADMIN = 1
USUARIO = 42
USUARIO_2 = 43
CANAL_420 = 420


def local(dia=5, hora=16, minuto=20, segundo=0):
    return datetime(2026, 9, dia, hora, minuto, segundo, tzinfo=TIMEZONE)


@pytest.fixture
async def sanciones_db(base_datos_limpia):
    """Esquema completo (incluida ``sanciones``) sobre una base vacía."""

    from modules.sanciones.database import inicializar_db

    await inicializar_db()
    return True


@pytest.fixture
def admin_ids(monkeypatch):
    monkeypatch.setattr("core.permissions.ADMIN_USER_IDS", {ADMIN})


@pytest.fixture
def cog_admin(sanciones_db, admin_ids):
    from commands.admin.cog import Admin

    return construir_cog(Admin)


async def llamar(cog, nombre_metodo, interaccion, *args, **kwargs):
    metodo = getattr(type(cog), nombre_metodo).callback
    return await metodo(cog, interaccion, *args, **kwargs)


def interaccion_admin(user_id=ADMIN, nombre="Admin"):
    return InteraccionFalsa(GUILD, user_id, nombre=nombre)


class MiembroFalso:
    """Doble mínimo de ``discord.Member`` para los comandos administrativos."""

    def __init__(self, user_id=USUARIO, nombre="Tramposo"):
        self.id = user_id
        self.display_name = nombre
        self.mention = f"<@{user_id}>"


class OpcionFalsa:
    """Doble de ``app_commands.Choice``: los comandos leen ``.value``."""

    def __init__(self, valor):
        self.value = valor


# ============================================================
# LÓGICA: TEMPORIZADOR
# ============================================================

@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("30m", timedelta(minutes=30)),
        ("12h", timedelta(hours=12)),
        ("7d", timedelta(days=7)),
        ("2d12h", timedelta(days=2, hours=12)),
        ("90s", timedelta(seconds=90)),
    ],
)
def test_parsear_duracion_convierte_unidades(texto, esperado):
    from modules.sanciones.logic import parsear_duracion

    assert parsear_duracion(texto) == esperado


@pytest.mark.parametrize(
    "texto", [None, "", "permanente", "PERM", "nunca", "siempre", "  "]
)
def test_parsear_duracion_permanente(texto):
    from modules.sanciones.logic import parsear_duracion

    assert parsear_duracion(texto) is None


@pytest.mark.parametrize(
    "texto", ["7", "d", "7x", "0d", "abc", "7d3h2m", "-5d", "3y"]
)
def test_parsear_duracion_rechaza_formatos_invalidos(texto):
    from modules.sanciones.logic import parsear_duracion

    with pytest.raises(ValueError):
        parsear_duracion(texto)


def test_parsear_duracion_rechaza_temporizadores_absurdos():
    from modules.sanciones.logic import MAXIMO_DIAS, parsear_duracion

    with pytest.raises(ValueError):
        parsear_duracion(f"{MAXIMO_DIAS + 1}d")


def test_esta_vigente_respeta_el_vencimiento():
    from modules.sanciones.logic import esta_vigente

    ahora = local()
    assert esta_vigente(None, ahora)
    assert esta_vigente(ahora + timedelta(seconds=1), ahora)
    assert not esta_vigente(ahora, ahora)
    assert not esta_vigente(ahora - timedelta(days=1), ahora)


def test_formatear_restante_arma_el_temporizador():
    from modules.sanciones.logic import formatear_restante

    ahora = local()

    assert formatear_restante(None, ahora) == "sin vencimiento"
    assert formatear_restante(ahora + timedelta(days=2, hours=3), ahora) == "2d 3h"
    assert formatear_restante(ahora + timedelta(hours=5, minutes=30), ahora) == "5h 30m"
    assert formatear_restante(ahora + timedelta(seconds=45), ahora) == "45s"
    assert formatear_restante(ahora - timedelta(seconds=1), ahora) == "vencida"


def test_texto_sancion_activa_incluye_el_temporizador():
    from modules.sanciones.logic import texto_sancion_activa

    ahora = local()
    texto = texto_sancion_activa("madrugue", ahora + timedelta(hours=4), ahora)

    assert "Madrugue" in texto
    assert "faltan" in texto
    assert "4h" in texto

    permanente = texto_sancion_activa("box", None, ahora)
    assert "sin fecha de fin" in permanente


# ============================================================
# BASE DE DATOS
# ============================================================

async def test_guardar_y_consultar_sancion_permanente(sanciones_db):
    from modules.sanciones.database import guardar_sancion, sancion_vigente

    guardada = await guardar_sancion(
        GUILD, USUARIO, "madrugue", "duplicó registros", creada_por=ADMIN,
    )

    assert guardada["expira_en"] is None
    assert guardada["estado"] == "activa"

    vigente = await sancion_vigente(GUILD, USUARIO, "madrugue", local())
    assert vigente == ("madrugue", None)


async def test_sancion_vence_y_deja_de_bloquear(sanciones_db):
    from modules.sanciones.database import guardar_sancion, sancion_vigente

    creada = local()
    await guardar_sancion(
        GUILD, USUARIO, "box", "trampa", expira_en=creada + timedelta(hours=1),
        creada_en=creada,
    )

    assert await sancion_vigente(GUILD, USUARIO, "box", creada) is not None
    assert await sancion_vigente(
        GUILD, USUARIO, "box", creada + timedelta(hours=1, seconds=1)
    ) is None


async def test_la_sancion_es_por_minijuego(sanciones_db):
    from modules.sanciones.database import guardar_sancion, sancion_vigente

    await guardar_sancion(GUILD, USUARIO, "box", "trampa")

    assert await sancion_vigente(GUILD, USUARIO, "box", local()) is not None
    assert await sancion_vigente(GUILD, USUARIO, "madrugue", local()) is None
    assert await sancion_vigente(GUILD, USUARIO, "lahora", local()) is None
    assert await sancion_vigente(GUILD, USUARIO, "ssf", local()) is None


async def test_la_sancion_no_cruza_servidores(sanciones_db):
    from modules.sanciones.database import guardar_sancion, sancion_vigente

    await guardar_sancion(GUILD, USUARIO, "box", "trampa")

    assert await sancion_vigente(2, USUARIO, "box", local()) is None


async def test_reemplazar_sancion_actualiza_el_temporizador(sanciones_db):
    from modules.sanciones.database import (
        guardar_sancion,
        obtener_sancion,
        sancion_vigente,
    )

    creada = local()
    await guardar_sancion(GUILD, USUARIO, "box", "primera", creada_en=creada)
    await guardar_sancion(
        GUILD, USUARIO, "box", "segunda", expira_en=creada + timedelta(days=1),
        creada_en=creada,
    )

    sancion = await obtener_sancion(GUILD, USUARIO, "box")
    assert sancion["motivo"] == "segunda"
    assert sancion["expira_en"] is not None
    assert await sancion_vigente(GUILD, USUARIO, "box", creada) is not None

    # No debería haber quedado una fila duplicada.
    from modules.sanciones.database import listar_sanciones

    assert len(await listar_sanciones(GUILD, incluir_historicas=True)) == 1


async def test_levantar_sancion_la_deja_en_historial(sanciones_db):
    from modules.sanciones.database import (
        guardar_sancion,
        levantar_sancion,
        listar_sanciones,
        obtener_sancion,
        sancion_vigente,
    )

    await guardar_sancion(GUILD, USUARIO, "box", "trampa")

    assert await levantar_sancion(GUILD, USUARIO, "box", levantada_por=ADMIN)
    assert not await levantar_sancion(GUILD, USUARIO, "box", levantada_por=ADMIN)
    assert await sancion_vigente(GUILD, USUARIO, "box", local()) is None

    sancion = await obtener_sancion(GUILD, USUARIO, "box")
    assert sancion["estado"] == "levantada"
    assert sancion["levantada_por"] == ADMIN

    assert await listar_sanciones(GUILD) == []
    assert len(await listar_sanciones(GUILD, incluir_historicas=True)) == 1


async def test_listar_solo_vigentes_por_defecto(sanciones_db):
    from modules.sanciones.database import guardar_sancion, listar_sanciones

    creada = local()
    await guardar_sancion(GUILD, USUARIO, "box", "vigente", creada_en=creada)
    await guardar_sancion(
        GUILD, USUARIO_2, "ssf", "vieja",
        expira_en=creada - timedelta(days=1), creada_en=creada - timedelta(days=2),
    )

    vigentes = await listar_sanciones(GUILD, momento=creada)
    assert [sancion["minijuego"] for sancion in vigentes] == ["box"]

    historicas = await listar_sanciones(
        GUILD, incluir_historicas=True, momento=creada
    )
    assert len(historicas) == 2


async def test_limpiar_vencidas_no_toca_las_permanentes(sanciones_db):
    from modules.sanciones.database import (
        guardar_sancion,
        limpiar_vencidas,
        listar_sanciones,
    )

    creada = local()
    await guardar_sancion(GUILD, USUARIO, "box", "permanente", creada_en=creada)
    await guardar_sancion(
        GUILD, USUARIO_2, "ssf", "vencida",
        expira_en=creada - timedelta(minutes=1), creada_en=creada - timedelta(days=1),
    )

    assert await limpiar_vencidas(GUILD, momento=creada) == 1

    quedan = await listar_sanciones(GUILD, incluir_historicas=True, momento=creada)
    assert [sancion["minijuego"] for sancion in quedan] == ["box"]


async def test_las_sanciones_sobreviven_al_corte_de_temporada(sanciones_db):
    """Quien hizo trampa sigue bloqueado aunque cambie el año."""

    import sqlite3

    from config import DATABASE
    from modules.sanciones.database import guardar_sancion, sancion_vigente

    await guardar_sancion(GUILD, USUARIO, "box", "trampa")

    with sqlite3.connect(DATABASE) as conexion:
        conexion.execute("UPDATE temporada SET inicio = '1999-10-03'")

    from core.temporada import verificar_temporada

    verificar_temporada()

    assert await sancion_vigente(GUILD, USUARIO, "box", local()) is not None


# ============================================================
# GUARDIÁN COMPARTIDO
# ============================================================

async def test_revisar_sancion_avisa_con_el_temporizador(sanciones_db, admin_ids):
    from modules.sanciones.services import aplicar_sancion, revisar_sancion

    await aplicar_sancion(
        GUILD, USUARIO, "madrugue", "trampa", duracion=timedelta(hours=3),
        momento=local(),
    )

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    assert not await revisar_sancion(interaccion, "madrugue", momento=local())

    assert interaccion.respuestas
    assert interaccion.respuestas[-1].efimero
    assert "Madrugue" in interaccion.texto
    assert "3h" in interaccion.texto


async def test_revisar_sancion_deja_pasar_a_quien_no_esta_sancionado(
    sanciones_db, admin_ids
):
    from modules.sanciones.services import revisar_sancion

    interaccion = InteraccionFalsa(GUILD, USUARIO)

    assert await revisar_sancion(interaccion, "box", momento=local())
    assert interaccion.respuestas == []


async def test_revisar_sancion_deja_pasar_a_los_administradores(
    sanciones_db, admin_ids
):
    from modules.sanciones.services import aplicar_sancion, revisar_sancion

    await aplicar_sancion(GUILD, ADMIN, "box", "prueba")

    interaccion = InteraccionFalsa(GUILD, ADMIN)
    assert await revisar_sancion(interaccion, "box", momento=local())


# ============================================================
# COMANDOS ADMINISTRATIVOS
# ============================================================

async def test_aplicar_sancion_permanente_desde_el_comando(cog_admin, sanciones_db):
    from modules.sanciones.database import sancion_vigente

    interaccion = interaccion_admin()

    await llamar(
        cog_admin,
        "sanciones_aplicar",
        interaccion,
        MiembroFalso(),
        OpcionFalsa("box"),
        "duplicó desafíos",
    )

    assert not interaccion.respuestas[-1].efimero
    assert "Sanción aplicada" in interaccion.texto
    assert "permanente" in interaccion.texto

    sancion = await sancion_vigente(GUILD, USUARIO, "box")
    assert sancion == ("box", None)


async def test_aplicar_sancion_con_duracion_calcula_el_vencimiento(cog_admin, sanciones_db):
    from modules.sanciones.database import obtener_sancion

    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(
        cog_admin,
        "sanciones_aplicar",
        interaccion,
        usuario,
        OpcionFalsa("lahora"),
        "420 editado",
        "2d12h",
    )

    sancion = await obtener_sancion(GUILD, USUARIO, "lahora")
    restante = sancion["expira_en"] - sancion["creada_en"]

    assert restante == timedelta(days=2, hours=12)
    assert "2 días 12 h" in interaccion.texto


async def test_aplicar_sancion_rechaza_duracion_invalida(cog_admin, sanciones_db):
    from modules.sanciones.database import obtener_sancion

    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(
        cog_admin,
        "sanciones_aplicar",
        interaccion,
        usuario,
        OpcionFalsa("box"),
        "trampa",
        "siete días",
    )

    assert interaccion.respuestas[-1].efimero
    assert "Formato de duración inválido" in interaccion.texto
    assert await obtener_sancion(GUILD, USUARIO, "box") is None


async def test_aplicar_sancion_exige_motivo(cog_admin, sanciones_db):
    from modules.sanciones.database import obtener_sancion

    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(
        cog_admin,
        "sanciones_aplicar",
        interaccion,
        usuario,
        OpcionFalsa("box"),
        "   ",
    )

    assert interaccion.respuestas[-1].efimero
    assert await obtener_sancion(GUILD, USUARIO, "box") is None


async def test_aplicar_sancion_cancela_la_accion_de_box(cog_admin, sanciones_db):
    from datetime import timedelta as _timedelta

    from modules.box.services import iniciar_accion, tiene_accion_activa

    await iniciar_accion(
        GUILD, USUARIO, "ENTRENANDO",
        local(), local() + _timedelta(minutes=30), 10, 0,
    )
    assert await tiene_accion_activa(GUILD, USUARIO)

    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(
        cog_admin,
        "sanciones_aplicar",
        interaccion,
        usuario,
        OpcionFalsa("box"),
        "trampa",
    )

    assert not await tiene_accion_activa(GUILD, USUARIO)
    assert "canceló la acción" in interaccion.texto


async def test_levantar_sancion_desde_el_comando(cog_admin, sanciones_db):
    from modules.sanciones.database import (
        guardar_sancion,
        obtener_sancion,
        sancion_vigente,
    )

    await guardar_sancion(GUILD, USUARIO, "ssf", "trampa", creada_por=ADMIN)

    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(
        cog_admin, "sanciones_levantar", interaccion, usuario,
        OpcionFalsa("ssf"),
    )

    assert "Sanción levantada" in interaccion.texto
    assert await sancion_vigente(GUILD, USUARIO, "ssf", local()) is None
    assert (await obtener_sancion(GUILD, USUARIO, "ssf"))["levantada_por"] == ADMIN


async def test_levantar_sancion_inexistente_avisa(cog_admin, sanciones_db):
    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(
        cog_admin, "sanciones_levantar", interaccion, usuario,
        OpcionFalsa("ssf"),
    )

    assert "no tiene una sanción vigente" in interaccion.texto


async def test_ver_lista_solo_las_vigentes_del_usuario(cog_admin, sanciones_db):
    from modules.sanciones.database import guardar_sancion, levantar_sancion

    await guardar_sancion(GUILD, USUARIO, "box", "trampa en box")
    await guardar_sancion(GUILD, USUARIO, "madrugue", "trampa en madrugue")
    await levantar_sancion(GUILD, USUARIO, "madrugue", levantada_por=ADMIN)

    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(cog_admin, "sanciones_ver", interaccion, usuario, False)

    assert "trampa en box" in interaccion.texto
    assert "trampa en madrugue" not in interaccion.texto
    assert "permanente" in interaccion.texto


async def test_ver_con_historicas_incluye_levantadas(cog_admin, sanciones_db):
    from modules.sanciones.database import guardar_sancion, levantar_sancion

    await guardar_sancion(GUILD, USUARIO, "madrugue", "trampa vieja")
    await levantar_sancion(GUILD, USUARIO, "madrugue", levantada_por=ADMIN)

    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(cog_admin, "sanciones_ver", interaccion, usuario, True)

    assert "levantada" in interaccion.texto
    assert "trampa vieja" in interaccion.texto


async def test_ver_sin_resultados_avisa(cog_admin, sanciones_db):
    usuario = MiembroFalso()
    interaccion = interaccion_admin()

    await llamar(cog_admin, "sanciones_ver", interaccion, usuario, False)

    assert interaccion.respuestas[-1].efimero
    assert "no tiene sanciones vigentes" in interaccion.texto


async def test_limpiar_desde_el_comando(cog_admin, sanciones_db):
    from modules.sanciones.database import guardar_sancion

    await guardar_sancion(
        GUILD, USUARIO, "box", "vieja",
        expira_en=local() - timedelta(days=1), creada_en=local() - timedelta(days=2),
    )

    interaccion = interaccion_admin()
    await llamar(cog_admin, "sanciones_limpiar", interaccion)

    assert "Se borraron **1** sanciones vencidas" in interaccion.texto


async def test_los_comandos_de_sanciones_son_solo_para_admins(cog_admin, sanciones_db):
    from modules.sanciones.database import obtener_sancion

    usuario = MiembroFalso()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(
        cog_admin, "sanciones_aplicar", interaccion, usuario,
        OpcionFalsa("box"), "trampa",
    )

    assert "Sin permisos" in interaccion.texto
    assert await obtener_sancion(GUILD, USUARIO, "box") is None


# ============================================================
# BLOQUEO POR MINIJUEGO
# ============================================================

async def test_madrugue_bloquea_al_sancionado(sanciones_db, monkeypatch):
    from modules.madrugue.database import inicializar_db
    from modules.madrugue.services import registrar_madrugue
    from modules.sanciones.services import aplicar_sancion
    from commands.madrugue.cog import Madrugue

    await inicializar_db()
    await aplicar_sancion(GUILD, USUARIO, "madrugue", "trampa")

    cog = construir_cog(Madrugue)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "madrugue", interaccion)

    assert interaccion.respuestas[-1].efimero
    assert "Sanción por trampa" in interaccion.texto

    # Y no quedó ningún registro guardado.
    assert await registrar_madrugue(
        GUILD, USUARIO_2, "Otro", local(hora=5, minuto=0)
    ) is not None


async def test_madrugue_deja_pasar_a_quien_no_esta_sancionado(sanciones_db, monkeypatch):
    from modules.madrugue.database import inicializar_db
    from commands.madrugue.cog import Madrugue

    await inicializar_db()
    # 06:00 cae dentro de la primera ventana de Madrugue (05:30 a 10:00).
    monkeypatch.setattr("commands.madrugue.registro.ahora", lambda: local(hora=6, minuto=0))

    cog = construir_cog(Madrugue)
    interaccion = InteraccionFalsa(GUILD, USUARIO, nombre="Tester")

    await llamar(cog, "madrugue", interaccion)

    assert "Sanción" not in interaccion.texto
    assert "¡Madrugaste" in interaccion.texto


async def test_ssf_bloquea_registro_y_supervivencia(sanciones_db):
    from modules.sanciones.services import aplicar_sancion
    from modules.ssf.database import inicializar_db
    from commands.ssf.cog import Ssf

    await inicializar_db()
    await aplicar_sancion(GUILD, USUARIO, "ssf", "trampa")

    cog = construir_cog(Ssf)

    for metodo in ("registrar", "sobrevivi"):
        interaccion = InteraccionFalsa(GUILD, USUARIO)
        await llamar(cog, metodo, interaccion)
        assert "Sanción por trampa" in interaccion.texto


async def test_lahora_ignora_el_420_de_un_sancionado(sanciones_db, monkeypatch):
    import config
    from modules.sanciones.services import aplicar_sancion
    from modules.lahora.database import inicializar_db
    from modules.lahora.services import registrar_lahora
    from commands.lahora.cog import LaHora

    await inicializar_db()
    monkeypatch.setattr(config, "LAHORA_CANALES_ID", {CANAL_420})

    await aplicar_sancion(GUILD, USUARIO, "lahora", "trampa")

    cog = construir_cog(LaHora)

    class Mensaje:
        id = 900
        content = "420"
        author = type("A", (), {"id": USUARIO, "display_name": "Tester", "bot": False})()
        channel = type("C", (), {"id": CANAL_420})()
        guild = type("G", (), {"id": GUILD})()
        created_at = local()
        reacciones = []

        async def add_reaction(self, emoji):
            self.reacciones.append(emoji)

    mensaje = Mensaje()
    await type(cog).on_message(cog, mensaje)

    # Ni reacción de confirmación ni registro: la sanción corta el atajo del
    # canal, que es donde se hace la trampa.
    assert mensaje.reacciones == []

    resultado = await registrar_lahora(GUILD, USUARIO, "Tester", local())
    assert resultado.motivo == "sancionado"
    assert not resultado.exitoso


async def test_lahora_bloquea_al_importar_el_historial(sanciones_db):
    from core.utils import ahora
    from modules.sanciones.services import aplicar_sancion
    from modules.lahora.database import inicializar_db
    from modules.lahora.services import importar_mensajes

    await inicializar_db()
    await aplicar_sancion(GUILD, USUARIO, "lahora", "trampa")

    # El historial se importa dentro de la temporada vigente: se usa una
    # ventana de hoy en vez de una fecha fija que quedaría fuera de temporada.
    momento = ahora().replace(hour=16, minute=20, second=0, microsecond=0)

    class Mensaje:
        def __init__(self, momento):
            self.author = type("A", (), {"id": USUARIO, "display_name": "Tester", "bot": False})()
            self.content = "420"
            self.created_at = momento.astimezone(TIMEZONE)
            self.edited_at = None
            self.id = 1

    async def mensajes():
        yield Mensaje(momento)

    resumen = await importar_mensajes(GUILD, mensajes())

    assert resumen.importados == 0
    assert resumen.sancionados == 1


async def test_box_bloquea_las_acciones(sanciones_db):
    from modules.sanciones.services import aplicar_sancion
    from modules.box.database import inicializar_db
    from modules.box.services import obtener_accion_activa
    from commands.box.cog import Box

    await inicializar_db()
    await aplicar_sancion(GUILD, USUARIO, "box", "trampa")

    cog = construir_cog(Box)

    for metodo in ("entrenar", "trabajar", "promoverme", "descanso"):
        interaccion = InteraccionFalsa(GUILD, USUARIO)
        await llamar(cog, metodo, interaccion, 30)
        assert "Sanción por trampa" in interaccion.texto
        assert interaccion.respuestas[-1].efimero

    assert await obtener_accion_activa(GUILD, USUARIO) is None


async def test_box_no_bloquea_las_consultas(sanciones_db):
    from modules.sanciones.services import aplicar_sancion
    from modules.box.database import inicializar_db
    from commands.box.cog import Box

    await inicializar_db()
    await aplicar_sancion(GUILD, USUARIO, "box", "trampa")

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "saldo", interaccion)

    assert "Sanción activa" in interaccion.texto
    assert "Experiencia" in interaccion.texto


async def test_una_sancion_en_otro_minijuego_no_bloquea_box(sanciones_db):
    from modules.sanciones.services import aplicar_sancion
    from modules.box.database import inicializar_db
    from modules.box.services import obtener_accion_activa
    from commands.box.cog import Box

    await inicializar_db()
    await aplicar_sancion(GUILD, USUARIO, "madrugue", "trampa")

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, "entrenar", interaccion, 30)

    assert "Sanción" not in interaccion.texto
    assert await obtener_accion_activa(GUILD, USUARIO) is not None


async def test_manualadd_no_carga_un_420_a_un_sancionado(
    sanciones_db, admin_ids, monkeypatch
):
    """El alta manual también respeta la sanción: no es una puerta trasera."""

    from commands.admin.cog import Admin
    from core.utils import ahora
    from modules.lahora.database import inicializar_db
    from modules.sanciones.services import aplicar_sancion

    await inicializar_db()
    await aplicar_sancion(GUILD, USUARIO, "lahora", "trampa")

    momento = ahora().replace(hour=16, minute=20, second=5, microsecond=0)
    monkeypatch.setattr("commands.admin.lahora.ahora", lambda: momento)

    cog = construir_cog(Admin)
    interaccion = interaccion_admin()

    await llamar(
        cog,
        "lahora_manualadd",
        interaccion,
        MiembroFalso(),
        momento.strftime("%Y-%m-%d"),
        "16:20:05",
    )

    assert "sanción vigente" in interaccion.texto
    assert interaccion.respuestas[-1].efimero
