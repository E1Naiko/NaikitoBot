"""Pruebas de los comandos de Box ejecutados de punta a punta.

Cada comando se invoca a través de su callback real con una interacción falsa,
así que estas pruebas recorren el mismo camino que Discord.
"""

from datetime import timedelta

import pytest

from core.utils import ahora
from modules.box.database import (
    comprar_mejora,
    obtener_equipo,
    obtener_nivel_mejora,
    obtener_saldo,
    obtener_estado_box,
)
from tests.harness import Choice, InteraccionFalsa, construir_cog

GUILD = 1
USUARIO = 42


@pytest.fixture
def cog(base_datos_limpia):
    from commands.box.cog import Box

    return construir_cog(Box)


def dar_dinero(cantidad):
    from modules.box.services import admin_modificar_dinero

    admin_modificar_dinero(GUILD, USUARIO, cantidad)


def lesionar(horas=3):
    from core.database import conectar_db

    hasta = (ahora() + timedelta(hours=horas)).isoformat()
    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id, lesionado_hasta)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET lesionado_hasta = excluded.lesionado_hasta
            """,
            (GUILD, USUARIO, hasta),
        )
        db.commit()


def probabilidad_lesion():
    return obtener_estado_box(GUILD, USUARIO)[0]


def llamar(cog, nombre_metodo, interaccion, *args):
    import asyncio

    metodo = getattr(type(cog), nombre_metodo).callback
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        metodo(cog, interaccion, *args)
    )


# ============================================================
# COMANDOS DE CONSULTA
# ============================================================

@pytest.mark.parametrize(
    "comando",
    ["saldo", "stats", "equipo", "topdesafios", "tienda", "ayuda"],
)
def test_comandos_de_consulta_responden(cog, comando):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, comando, interaccion)

    assert interaccion.cantidad_respuestas == 1, (
        f"/box {comando} no respondió nada: Discord mostraría "
        "'la aplicación no responde'"
    )
    assert interaccion.texto


def test_tienda_muestra_las_tres_categorias(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "tienda", interaccion)

    texto = interaccion.texto
    assert "Mejoras" in texto
    assert "Equipamiento" in texto
    assert "Tratamientos" in texto


def test_ayuda_envia_mensaje_directo(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "ayuda", interaccion)

    assert interaccion.user.mensajes_directos
    assert "Ayuda de Box" in interaccion.user.mensajes_directos[0]


def test_comandos_rechazan_mensajes_directos(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO, en_servidor=False)

    llamar(cog, "saldo", interaccion)

    assert "dentro de un servidor" in interaccion.texto


# ============================================================
# /box comprar — las tres ramas
# ============================================================

def test_comprar_mejora_descuenta_dinero(cog):
    dar_dinero(5000)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "comprar", interaccion, Choice("mejora"), "entrenamiento")

    assert "Compraste un nivel" in interaccion.texto
    assert obtener_nivel_mejora(GUILD, USUARIO, "entrenamiento") == 1
    assert obtener_saldo(GUILD, USUARIO)[1] == 4000


def test_comprar_equipamiento_responde_y_sube_nivel(cog):
    dar_dinero(5000)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "comprar", interaccion, Choice("equipamiento"), "casco")

    assert interaccion.cantidad_respuestas == 1, (
        "/box comprar tipo=equipamiento no respondió nada"
    )
    assert "Compraste una mejora de equipamiento" in interaccion.texto
    assert "Basico → Intermedio" in interaccion.texto
    assert obtener_equipo(GUILD, USUARIO)["casco"] == 1
    assert obtener_saldo(GUILD, USUARIO)[1] == 4000


def test_comprar_equipamiento_sin_dinero_informa(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "comprar", interaccion, Choice("equipamiento"), "botas")

    assert interaccion.cantidad_respuestas == 1
    assert "Necesitas" in interaccion.texto


def test_comprar_tratamiento_responde(cog):
    dar_dinero(100000)
    lesionar()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "comprar", interaccion, Choice("tratamiento"), "fisioterapeutico")

    assert interaccion.cantidad_respuestas == 1, (
        "/box comprar tipo=tratamiento no respondió nada"
    )
    assert "Compraste" in interaccion.texto
    assert obtener_estado_box(GUILD, USUARIO)[1] is None


@pytest.mark.parametrize("articulo", ["mejora", "equipamiento", "tratamiento"])
def test_comprar_con_articulo_invalido_informa(cog, articulo):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "comprar", interaccion, Choice(articulo), "inexistente")

    assert interaccion.cantidad_respuestas == 1
    assert "no válida" in interaccion.texto or "no válido" in interaccion.texto


def test_comprar_articulo_no_distingue_mayusculas(cog):
    dar_dinero(5000)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "comprar", interaccion, Choice("mejora"), "TRABAJO")

    assert "Compraste un nivel" in interaccion.texto


# ============================================================
# /box tratamiento — comando independiente
# ============================================================

def test_tratamiento_en_servidor_responde(cog):
    dar_dinero(100000)
    lesionar()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "tratamiento", interaccion, Choice("fisioterapeutico"))

    assert interaccion.cantidad_respuestas == 1, (
        "/box tratamiento no respondió nada"
    )
    assert "Compraste" in interaccion.texto


def test_tratamiento_sin_lesion_informa(cog):
    dar_dinero(100000)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "tratamiento", interaccion, Choice("fisioterapeutico"))

    assert "No estás lesionado" in interaccion.texto


def test_tratamiento_sin_dinero_informa(cog):
    lesionar()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "tratamiento", interaccion, Choice("cinco_estrellas"))

    assert "Necesitas" in interaccion.texto


def test_tratamiento_cinco_estrellas_reinicia_probabilidad(cog):
    """El 5 estrellas debe zerar la probabilidad, no solo curar."""

    from modules.box.services import admin_modificar_probabilidad_lesion

    dar_dinero(100000)
    lesionar()
    admin_modificar_probabilidad_lesion(GUILD, USUARIO, 42.5)

    interaccion = InteraccionFalsa(GUILD, USUARIO)
    llamar(cog, "tratamiento", interaccion, Choice("cinco_estrellas"))

    assert "Compraste" in interaccion.texto
    assert obtener_estado_box(GUILD, USUARIO)[1] is None
    assert probabilidad_lesion() == 0


def test_tratamiento_por_mensaje_directo_rechaza(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO, en_servidor=False)

    llamar(cog, "tratamiento", interaccion, Choice("cinco_estrellas"))

    assert interaccion.cantidad_respuestas == 1
    assert "dentro de un servidor" in interaccion.texto


# ============================================================
# ACCIONES
# ============================================================

def test_entrenar_registra_la_accion(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "entrenar", interaccion, 60, None)

    assert "Comenzaste a" in interaccion.texto
    from modules.box.database import obtener_accion_activa

    assert obtener_accion_activa(GUILD, USUARIO) is not None


def test_entrenar_mientras_lesionado_se_rechaza(cog):
    lesionar()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "entrenar", interaccion, 60, None)

    assert "lesionado hasta" in interaccion.texto


def test_promoverme_permite_estar_lesionado(cog):
    lesionar()
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "promoverme", interaccion, 60, None)

    assert "promocionarte" in interaccion.texto


def test_entrenar_con_hora_de_fin(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "entrenar", interaccion, None, "23:59")

    assert "Comenzaste a" in interaccion.texto


def test_entrenar_rechaza_minutos_y_hora_juntos(cog):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "entrenar", interaccion, 60, "18:00")

    assert "no ambas opciones" in interaccion.texto


def test_no_se_pueden_apilar_acciones(cog):
    primera = InteraccionFalsa(GUILD, USUARIO)
    llamar(cog, "entrenar", primera, 60, None)

    segunda = InteraccionFalsa(GUILD, USUARIO)
    llamar(cog, "trabajar", segunda, 60, None)

    assert "Ya estás" in segunda.texto


def test_descanso_reinicia_probabilidad(cog):
    from modules.box.services import admin_modificar_probabilidad_lesion

    admin_modificar_probabilidad_lesion(GUILD, USUARIO, 50.0)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "descanso", interaccion)

    assert "0%" in interaccion.texto
    assert probabilidad_lesion() == 0


def test_descanso_se_rechaza_con_accion_activa(cog):
    llamar(cog, "entrenar", InteraccionFalsa(GUILD, USUARIO), 60, None)
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, "descanso", interaccion)

    assert "No puedes descansar" in interaccion.texto
