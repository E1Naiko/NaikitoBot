"""Pruebas de los suministros de recuperación de Box.

Cubren la lógica de ``usar_suministro`` (vida, cansancio, defensa como
servicio de reparación y lesión), el comando ``/box suministro`` y el menú
que abre el botón de la tienda.
"""

from datetime import timedelta

import pytest

from tests.harness import conectar_db
from core.utils import ahora
from modules.box.constants import SUMINISTROS, TIPOS_SUMINISTRO
from modules.box.database import actualizar_equipo, obtener_equipo
from modules.box.services import (
    admin_modificar_dinero,
    admin_modificar_probabilidad_lesion,
    obtener_estado_box,
    obtener_saldo,
    usar_suministro,
)
from tests.harness import Choice, InteraccionFalsa, construir_cog

GUILD = 1
USUARIO = 42

PRECIOS = {
    tipo["objetivo"]: tipo["precio"]
    for tipo in TIPOS_SUMINISTRO.values()
}


async def dar_dinero(cantidad):
    await admin_modificar_dinero(GUILD, USUARIO, cantidad)


async def usar(objetivo, precio=None):
    return await usar_suministro(
        GUILD,
        USUARIO,
        objetivo,
        precio or PRECIOS.get(objetivo, 1),
        ahora(),
    )


def lesionar(user_id=USUARIO):
    hasta = (ahora() + timedelta(hours=3)).isoformat()
    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id, lesionado_hasta)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET lesionado_hasta = excluded.lesionado_hasta
            """,
            (GUILD, user_id, hasta),
        )
        db.commit()


# ============================================================
# CATÁLOGO
# ============================================================

def test_existe_el_articulo_generico_en_la_tienda():
    assert SUMINISTROS["recuperacion"]["emoji"] == "🎒"


def test_los_cuatro_tipos_cubren_las_estadisticas_pedidas():
    objetivos = {
        tipo["objetivo"]
        for tipo in TIPOS_SUMINISTRO.values()
    }

    assert objetivos == {"vida", "cansancio", "defensa", "lesion"}


def test_los_emojis_de_suministros_no_se_repiten():
    emojis = [
        tipo["emoji"]
        for tipo in TIPOS_SUMINISTRO.values()
    ]

    assert len(emojis) == len(set(emojis))


# ============================================================
# VIDA
# ============================================================

async def test_vida_restaura_al_maximo(base_datos_limpia):
    await dar_dinero(5000)
    await obtener_equipo(GUILD, USUARIO)  # crea la fila de equipo
    await actualizar_equipo(GUILD, USUARIO, vida=10)

    estado, saldo = await usar("vida")

    assert estado == "comprado"
    assert saldo == 5000 - PRECIOS["vida"]
    assert (await obtener_equipo(GUILD, USUARIO))["vida"] == (
        (await obtener_equipo(GUILD, USUARIO))["vida_maxima"]
    )


async def test_vida_llena_no_cobra(base_datos_limpia):
    await dar_dinero(5000)

    estado, saldo = await usar("vida")

    assert estado == "lleno"
    assert saldo == 5000
    assert (await obtener_saldo(GUILD, USUARIO))[1] == 5000


# ============================================================
# CANSANCIO
# ============================================================

async def test_cansancio_restaura_al_maximo(base_datos_limpia):
    await dar_dinero(5000)
    await obtener_equipo(GUILD, USUARIO)  # crea la fila de equipo
    await actualizar_equipo(GUILD, USUARIO, cansancio=5)

    estado, saldo = await usar("cansancio")

    assert estado == "comprado"
    equipo = await obtener_equipo(GUILD, USUARIO)
    assert equipo["cansancio"] == equipo["cansancio_maximo"]


async def test_cansancio_lleno_no_cobra(base_datos_limpia):
    await dar_dinero(5000)

    estado, _ = await usar("cansancio")

    assert estado == "lleno"


# ============================================================
# DEFENSA (SERVICIO DE REPARACIÓN)
# ============================================================

async def test_defensa_repara_hasta_el_maximo(base_datos_limpia):
    await dar_dinero(5000)
    # La defensa arranca en 1 con máximo 22.
    await actualizar_equipo(GUILD, USUARIO, defensa=3)

    estado, _ = await usar("defensa")

    assert estado == "comprado"
    equipo = await obtener_equipo(GUILD, USUARIO)
    assert equipo["defensa"] == equipo["defensa_maxima"]


async def test_defensa_ya_reparada_no_cobra(base_datos_limpia):
    await dar_dinero(5000)
    await obtener_equipo(GUILD, USUARIO)  # crea la fila de equipo
    await actualizar_equipo(GUILD, USUARIO, defensa=22)

    estado, saldo = await usar("defensa")

    assert estado == "lleno"
    assert saldo == 5000


# ============================================================
# LESIÓN (BOTIQUÍN)
# ============================================================

async def test_lesion_cura_y_reinicia_probabilidad(base_datos_limpia):
    await dar_dinero(70000)
    lesionar()
    await admin_modificar_probabilidad_lesion(GUILD, USUARIO, 40.0)

    estado, _ = await usar("lesion")

    assert estado == "comprado"

    probabilidad, lesionado_hasta = await obtener_estado_box(GUILD, USUARIO)
    assert probabilidad == 0.0
    assert lesionado_hasta is None


async def test_lesion_sin_lesion_ni_probabilidad_no_cobra(base_datos_limpia):
    await dar_dinero(70000)

    estado, saldo = await usar("lesion")

    assert estado == "sin_lesion"
    assert saldo == 70000


async def test_lesion_con_probabilidad_sin_lesion_cura_probabilidad(
    base_datos_limpia,
):
    """Si no hay lesión activa pero sí probabilidad, el botiquín la reinicia."""

    await dar_dinero(70000)
    await admin_modificar_probabilidad_lesion(GUILD, USUARIO, 12.0)

    estado, _ = await usar("lesion")

    assert estado == "comprado"
    assert (await obtener_estado_box(GUILD, USUARIO))[0] == 0.0


async def test_lesion_sin_dinero_informa(base_datos_limpia):
    lesionar()

    estado, saldo = await usar("lesion")

    assert estado == "insuficiente"
    assert saldo == 0


# ============================================================
# GENÉRICO
# ============================================================

async def test_objetivo_invalido(base_datos_limpia):
    await dar_dinero(5000)

    estado, saldo = await usar("ataque", precio=1500)

    assert estado == "objetivo_invalido"
    assert saldo == 5000


# ============================================================
# /box suministro (comando)
# ============================================================

async def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return await metodo(cog, interaccion, *args)


@pytest.fixture
def cog(base_datos_limpia):
    from commands.box.cog import Box

    return construir_cog(Box)


@pytest.fixture(autouse=True)
def canal_box(monkeypatch):
    """Los botones de la tienda viven en el canal de Box."""

    import commands.box.tienda as tienda

    monkeypatch.setattr(tienda, "BOX_CHANNEL_IDS", {GUILD})


async def test_comando_suministro_vida_restaura(cog):
    await dar_dinero(5000)
    await obtener_equipo(GUILD, USUARIO)
    await actualizar_equipo(GUILD, USUARIO, vida=4)

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "suministro", interaccion, Choice("vida"))

    assert "Bebida isotónica" in interaccion.texto
    assert "restaura tu vida al máximo" in interaccion.texto
    assert "❤️ Vida: **" in interaccion.texto
    assert "no se descontó" not in interaccion.texto


async def test_comando_suministro_vida_llena_avisa(cog):
    await dar_dinero(5000)
    await obtener_equipo(GUILD, USUARIO)

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "suministro", interaccion, Choice("vida"))

    assert "Ya tienes la estadística al máximo" in interaccion.texto


async def test_comando_suministro_defensa_repara(cog):
    await dar_dinero(5000)
    await obtener_equipo(GUILD, USUARIO)

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "suministro", interaccion, Choice("defensa"))

    assert "Servicio de reparación" in interaccion.texto
    assert "🛡️ Defensa: **22/22**" in interaccion.texto


async def test_comando_suministro_tipo_invalido(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "suministro", interaccion, Choice("no_existe"))

    assert "Suministro no válido" in interaccion.texto


# ============================================================
# MENÚ DE LA TIENDA
# ============================================================

async def test_boton_suministro_abre_el_menu_efimero():
    from commands.box.tienda import TiendaView

    vista = TiendaView(USUARIO)

    # El botón de suministros está presente en la tienda.
    boton_suministro = next(
        item
        for item in vista.children
        if item.to_component_dict()["custom_id"].endswith(":suministro:recuperacion")
    )

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await boton_suministro.callback(interaccion)

    from commands.box.tienda import VistaSuministro

    assert isinstance(interaccion.respuestas[-1].kwargs.get("view"), VistaSuministro)
    assert interaccion.respuestas[-1].efimero


async def test_selector_de_suministro_aplica_y_actualiza_la_tienda(cog):
    from commands.box.tienda import VistaSuministro

    await dar_dinero(5000)
    await obtener_equipo(GUILD, USUARIO)
    await actualizar_equipo(GUILD, USUARIO, vida=7)

    apertura = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "tienda", apertura)
    mensaje_tienda = apertura.respuestas[-1]

    vista = VistaSuministro(USUARIO, tienda_message=mensaje_tienda)
    selector = vista.children[0]

    # Simula la elección del usuario en Discord.
    selector._values = ["vida"]

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await selector.callback(interaccion)

    assert selector.disabled
    assert interaccion.cantidad_respuestas >= 2
    assert "Bebida isotónica" in interaccion.texto
    assert mensaje_tienda.ediciones == 1
    assert "Dinero disponible: **3500$**" in mensaje_tienda.texto


async def test_selector_rechaza_a_un_usuario_que_no_es_el_dueño():
    from commands.box.tienda import VistaSuministro

    vista = VistaSuministro(USUARIO)
    selector = vista.children[0]
    selector._values = ["vida"]

    interaccion = InteraccionFalsa(GUILD, 999)
    await selector.callback(interaccion)

    assert "no es tuya" in interaccion.texto


async def test_comprar_suministro_orienta_a_usar_el_comando(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)
    await llamar(cog, "comprar", interaccion, Choice("suministro"), "recuperacion")

    assert "🎒 Elige el suministro" in interaccion.texto
    assert "/box suministro" in interaccion.texto
