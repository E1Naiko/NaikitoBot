"""Pruebas de los botones de compra de la tienda de Box."""

from datetime import timedelta

import pytest

from commands.box.compras import CATALOGOS, ejecutar_compra
from commands.box.tienda import (
    PLANTILLA_CUSTOM_ID,
    BotonCompra,
    TiendaView,
    construir_catalogo,
    custom_id_de,
    iterar_articulos,
)
from core.database import conectar_db
from core.utils import ahora
from modules.box.database import obtener_equipo, obtener_estado_box, obtener_saldo
from modules.box.services import admin_modificar_dinero, admin_modificar_probabilidad_lesion
from tests.harness import Choice, InteraccionFalsa, construir_cog

GUILD = 1
DUEÑO = 42
OTRO = 99


@pytest.fixture
def cog(base_datos_limpia):
    from commands.box.cog import Box

    return construir_cog(Box)


def dar_dinero(user_id, cantidad):
    admin_modificar_dinero(GUILD, user_id, cantidad)


def lesionar(user_id=DUEÑO):
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


def clic(boton, user_id=DUEÑO, en_servidor=True):
    import asyncio

    interaccion = InteraccionFalsa(GUILD, user_id, en_servidor=en_servidor)
    asyncio.new_event_loop().run_until_complete(boton.callback(interaccion))
    return interaccion


# ============================================================
# LA VISTA
# ============================================================

def test_la_vista_tiene_un_boton_por_articulo():
    vista = TiendaView(DUEÑO)

    assert len(vista.children) == len(list(iterar_articulos())) == 9


def test_los_botones_llevan_el_emoji_de_su_articulo():
    vista = TiendaView(DUEÑO)

    vistos = {}
    for item in vista.children:
        componente = item.to_component_dict()
        vistos[componente["custom_id"]] = componente["emoji"]["name"]

    for categoria, clave in iterar_articulos():
        cid = custom_id_de(DUEÑO, categoria, clave)
        assert vistos[cid] == CATALOGOS[categoria][clave]["emoji"], (
            f"el botón de {categoria}/{clave} no muestra su emoji"
        )


def test_los_emojis_no_se_repiten_entre_articulos():
    """Dos artículos con el mismo emoji harían ambigua la compra."""

    emojis = [
        cfg["emoji"]
        for catalogo in CATALOGOS.values()
        for cfg in catalogo.values()
    ]

    assert len(emojis) == len(set(emojis))


def test_los_botones_quedan_en_filas_validas():
    """Discord permite como máximo 5 filas de 5 componentes."""

    vista = TiendaView(DUEÑO)
    filas = [item.row for item in vista.children]

    assert max(filas) <= 4
    for fila in set(filas):
        assert filas.count(fila) <= 5


def test_custom_id_dentro_del_limite_de_discord():
    # Los IDs de Discord (snowflake) tienen hasta 19 dígitos.
    for categoria, clave in iterar_articulos():
        cid = custom_id_de(int("9" * 19), categoria, clave)
        assert len(cid) <= 100, f"{cid} supera el límite de 100 caracteres"


# ============================================================
# CUSTOM_ID: ida y vuelta
# ============================================================

@pytest.mark.parametrize(
    "categoria, clave",
    list(iterar_articulos()),
)
def test_custom_id_ida_y_vuelta(categoria, clave):
    """El custom_id debe poder reconstruir exactamente el artículo."""

    import asyncio

    cid = custom_id_de(DUEÑO, categoria, clave)
    match = PLANTILLA_CUSTOM_ID.fullmatch(cid)

    assert match is not None, f"el custom_id {cid} no matchea la plantilla"
    assert int(match["owner_id"]) == DUEÑO

    boton = asyncio.new_event_loop().run_until_complete(
        BotonCompra.from_custom_id(None, None, match)
    )
    assert boton.owner_id == DUEÑO
    assert boton.categoria == categoria
    assert boton.clave == clave


@pytest.mark.parametrize(
    "cid",
    [
        "box_comprar:42:mejora",
        "box_comprar:abc:mejora:entrenamiento",
        "otro_prefijo:42:mejora:entrenamiento",
        "box_comprar:42:mejora:entrenamiento:extra",
        "",
    ],
)
def test_custom_id_mal_formado_no_matchea(cid):
    assert PLANTILLA_CUSTOM_ID.fullmatch(cid) is None


def test_los_nueve_custom_id_matchean_con_una_sola_plantilla():
    """Una sola inscripción persistente cubre todos los artículos."""

    for categoria, clave in iterar_articulos():
        cid = custom_id_de(DUEÑO, categoria, clave)
        assert PLANTILLA_CUSTOM_ID.fullmatch(cid) is not None, cid


def test_setup_registra_el_boton_para_escucha_persistente(base_datos_limpia):
    """El registro tiene que hacerlo setup, no el que construye el bot."""

    import asyncio

    import discord
    from discord.ext import commands as dcommands

    import commands.box as extension

    bot = dcommands.Bot(command_prefix="$!", intents=discord.Intents.default())

    store = bot._connection._view_store
    assert PLANTILLA_CUSTOM_ID not in store._dynamic_items, (
        "el patrón no debería estar registrado antes de setup"
    )

    asyncio.new_event_loop().run_until_complete(extension.setup(bot))

    assert PLANTILLA_CUSTOM_ID in store._dynamic_items, (
        "setup() no registró BotonCompra: los botones de una tienda anterior "
        "al arranque dejarían de responder"
    )
    assert store._dynamic_items[PLANTILLA_CUSTOM_ID] is BotonCompra

    bot._connection._view_store.remove_dynamic_items(BotonCompra)


# ============================================================
# COMPRAR TOCANDO EL BOTÓN
# ============================================================

def test_boton_mejora_compra_para_el_dueño(cog):
    dar_dinero(DUEÑO, 5000)
    boton = BotonCompra(DUEÑO, "mejora", "entrenamiento")

    interaccion = clic(boton)

    assert "Compraste un nivel" in interaccion.texto
    assert obtener_saldo(GUILD, DUEÑO)[1] == 4000


def test_boton_equipamiento_compra_para_el_dueño(cog):
    dar_dinero(DUEÑO, 5000)
    boton = BotonCompra(DUEÑO, "equipamiento", "casco")

    interaccion = clic(boton)

    assert "Compraste una mejora de equipamiento" in interaccion.texto
    assert obtener_equipo(GUILD, DUEÑO)["casco"] == 1


def test_boton_tratamiento_compra_para_el_dueño(cog):
    dar_dinero(DUEÑO, 100000)
    lesionar()
    boton = BotonCompra(DUEÑO, "tratamiento", "fisioterapeutico")

    interaccion = clic(boton)

    assert "Compraste" in interaccion.texto
    assert obtener_estado_box(GUILD, DUEÑO)[1] is None


def test_boton_sin_dinero_informa(cog):
    boton = BotonCompra(DUEÑO, "mejora", "trabajo")

    interaccion = clic(boton)

    assert "Necesitas" in interaccion.texto
    assert interaccion.respuestas[-1].efimero


def test_boton_rechaza_a_quien_no_abrio_la_tienda(cog):
    dar_dinero(OTRO, 5000)
    boton = BotonCompra(DUEÑO, "mejora", "entrenamiento")

    interaccion = clic(boton, user_id=OTRO)

    assert "no es tuya" in interaccion.texto
    # El otro usuario no debe haber gastado nada.
    assert obtener_saldo(GUILD, OTRO)[1] == 5000


def test_boton_fuera_de_servidor_se_rechaza(cog):
    boton = BotonCompra(DUEÑO, "mejora", "entrenamiento")

    interaccion = clic(boton, en_servidor=False)

    assert "dentro de un servidor" in interaccion.texto


def test_boton_cinco_estrellas_reinicia_probabilidad(cog):
    dar_dinero(DUEÑO, 100000)
    lesionar()
    admin_modificar_probabilidad_lesion(GUILD, DUEÑO, 42.5)
    boton = BotonCompra(DUEÑO, "tratamiento", "cinco_estrellas")

    interaccion = clic(boton)

    assert "Compraste" in interaccion.texto
    assert obtener_estado_box(GUILD, DUEÑO)[0] == 0


# ============================================================
# /box tienda ahora adjunta la vista
# ============================================================

def test_tienda_adjunta_la_vista_del_usuario(cog):
    import asyncio

    interaccion = InteraccionFalsa(GUILD, DUEÑO)
    asyncio.new_event_loop().run_until_complete(
        type(cog).tienda.callback(cog, interaccion)
    )

    vista = interaccion.respuestas[-1].kwargs.get("view")
    assert isinstance(vista, TiendaView)
    assert vista.owner_id == DUEÑO
    assert len(vista.children) == 9


def test_tienda_invita_a_usar_los_botones(cog):
    import asyncio

    interaccion = InteraccionFalsa(GUILD, DUEÑO)
    asyncio.new_event_loop().run_until_complete(
        type(cog).tienda.callback(cog, interaccion)
    )

    assert "botón" in interaccion.texto


def test_catalogo_muestra_los_niveles_del_usuario(cog):
    dar_dinero(DUEÑO, 5000)
    ejecutar_compra(GUILD, DUEÑO, "mejora", "entrenamiento")

    interaccion = InteraccionFalsa(GUILD, DUEÑO)
    texto = construir_catalogo(interaccion)

    assert "Nivel **1/10**" in texto


# ============================================================
# /box comprar y /box tratamiento siguen funcionando
# ============================================================

def test_comprar_por_comando_sigue_funcionando(cog):
    import asyncio

    dar_dinero(DUEÑO, 5000)
    interaccion = InteraccionFalsa(GUILD, DUEÑO)
    asyncio.new_event_loop().run_until_complete(
        type(cog).comprar.callback(cog, interaccion, Choice("mejora"), "entrenamiento")
    )

    assert "Compraste un nivel" in interaccion.texto
