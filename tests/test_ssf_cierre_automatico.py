"""Regresiones del cierre automático de desafíos SeptSinFP."""

from datetime import date

import pytest

from modules.ssf.database import obtener_desafio_activo
from modules.ssf.services import (
    cerrar_desafios_finalizados,
    iniciar_desafio,
    procesar_eliminaciones_diarias,
)

GUILD = 1
CANAL = 99
INICIO = date(2026, 9, 1)
FIN = date(2026, 9, 30)


@pytest.fixture
async def desafio_finalizado(base_datos_limpia):
    resultado = await iniciar_desafio(
        GUILD,
        "SeptiembreSinFAP",
        INICIO,
        FIN,
        CANAL,
    )
    assert resultado["exitoso"]

    # El cierre exige que el último día ya haya pasado por la revisión diaria.
    await procesar_eliminaciones_diarias(FIN)
    return resultado["desafio_id"]


async def test_cierra_un_desafio_cuyo_ultimo_dia_ya_fue_procesado(
    desafio_finalizado,
):
    cerrados = await cerrar_desafios_finalizados(date(2026, 10, 1))

    assert [resultado["desafio_id"] for resultado in cerrados] == [
        desafio_finalizado,
    ]
    assert await obtener_desafio_activo(GUILD) is None


async def test_no_cierra_hasta_que_se_procese_el_ultimo_dia(base_datos_limpia):
    resultado = await iniciar_desafio(
        GUILD,
        "SeptiembreSinFAP",
        INICIO,
        FIN,
        CANAL,
    )
    assert resultado["exitoso"]

    # Solo se revisó el penúltimo día: el desafío debe seguir activo.
    await procesar_eliminaciones_diarias(date(2026, 9, 29))
    cerrados = await cerrar_desafios_finalizados(date(2026, 10, 1))

    assert cerrados == []
    assert await obtener_desafio_activo(GUILD) is not None
