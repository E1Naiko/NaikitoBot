"""Pruebas del decaimiento horario de la probabilidad de lesión en Box.

Regla: cada hora, los usuarios con ``probabilidad_lesion > 0`` y sin ninguna
acción activa en ``box_acciones`` reducen su probabilidad en 0.01 puntos
porcentuales, sin pasar de 0. Aplica también a usuarios lesionados.
"""

from datetime import timedelta

import pytest

from tests.harness import conectar_db
from core.utils import ahora
from modules.box.services import (
    admin_modificar_dinero,
    admin_modificar_probabilidad_lesion,
    iniciar_accion,
    reducir_probabilidad_lesion_inactivos,
)

GUILD = 1
USUARIO = 42
USUARIO_2 = 43
USUARIO_3 = 44


async def probabilidad(user_id=USUARIO):
    from modules.box.services import obtener_estado_box

    return (await obtener_estado_box(GUILD, user_id))[0]


def lesionar(user_id=USUARIO):
    """Deja al usuario con una lesión activa de 3 horas."""

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


async def con_probabilidad(user_id, valor):
    """Crea al usuario y le fija una probabilidad de lesión."""

    await admin_modificar_probabilidad_lesion(GUILD, user_id, valor)
    assert await probabilidad(user_id) == pytest.approx(valor)


async def test_reduce_la_probabilidad_de_un_usuario_inactivo(base_datos_limpia):
    await con_probabilidad(USUARIO, 25.0)

    reducidos = await reducir_probabilidad_lesion_inactivos()

    assert reducidos == 1
    assert await probabilidad(USUARIO) == pytest.approx(24.99)


async def test_varias_horas_acumulan_la_reduccion(base_datos_limpia):
    await con_probabilidad(USUARIO, 25.0)

    for _ in range(3):
        await reducir_probabilidad_lesion_inactivos()

    assert await probabilidad(USUARIO) == pytest.approx(24.97)


async def test_no_baja_de_cero(base_datos_limpia):
    await con_probabilidad(USUARIO, 0.005)

    await reducir_probabilidad_lesion_inactivos()

    assert await probabilidad(USUARIO) == 0.0


async def test_usuario_con_accion_activa_no_se_toca(base_datos_limpia):
    await con_probabilidad(USUARIO, 25.0)
    await admin_modificar_dinero(GUILD, USUARIO, 100)

    ahora_actual = ahora()
    await iniciar_accion(
        GUILD,
        USUARIO,
        "ENTRENANDO",
        ahora_actual,
        ahora_actual + timedelta(hours=1),
        1000,
    )

    reducidos = await reducir_probabilidad_lesion_inactivos()

    assert reducidos == 0
    assert await probabilidad(USUARIO) == pytest.approx(25.0)


async def test_probabilidad_cero_no_cuenta(base_datos_limpia):
    await admin_modificar_dinero(GUILD, USUARIO, 100)

    reducidos = await reducir_probabilidad_lesion_inactivos()

    assert reducidos == 0


async def test_aplica_tambien_a_lesionados_inactivos(base_datos_limpia):
    await con_probabilidad(USUARIO, 25.0)
    lesionar(USUARIO)

    reducidos = await reducir_probabilidad_lesion_inactivos()

    assert reducidos == 1
    assert await probabilidad(USUARIO) == pytest.approx(24.99)


async def test_solo_reduce_a_quienes_no_tienen_accion(base_datos_limpia):
    await con_probabilidad(USUARIO, 10.0)
    await con_probabilidad(USUARIO_2, 20.0)

    ahora_actual = ahora()
    await admin_modificar_dinero(GUILD, USUARIO_2, 100)
    await iniciar_accion(
        GUILD,
        USUARIO_2,
        "TRABAJANDO",
        ahora_actual,
        ahora_actual + timedelta(hours=1),
        500,
    )

    reducidos = await reducir_probabilidad_lesion_inactivos()

    assert reducidos == 1
    assert await probabilidad(USUARIO) == pytest.approx(9.99)
    assert await probabilidad(USUARIO_2) == pytest.approx(20.0)


async def test_la_reduccion_aplica_a_todos_los_servidores(base_datos_limpia):
    """El tic horario es global: reduce en todos los gremios del bot."""

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id, probabilidad_lesion)
            VALUES (?, ?, ?)
            """,
            (GUILD, USUARIO, 5.0),
        )
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id, probabilidad_lesion)
            VALUES (?, ?, ?)
            """,
            (GUILD + 1, USUARIO_3, 7.0),
        )
        db.commit()

    reducidos = await reducir_probabilidad_lesion_inactivos()

    assert reducidos == 2
    assert await probabilidad(USUARIO) == pytest.approx(4.99)

    from modules.box.services import obtener_estado_box

    assert (await obtener_estado_box(GUILD + 1, USUARIO_3))[0] == pytest.approx(6.99)


async def test_cantidad_personalizada(base_datos_limpia):
    await con_probabilidad(USUARIO, 25.0)

    reducidos = await reducir_probabilidad_lesion_inactivos(cantidad=0.5)

    assert reducidos == 1
    assert await probabilidad(USUARIO) == pytest.approx(24.5)
