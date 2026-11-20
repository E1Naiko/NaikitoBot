"""Flujos de correlativas por los callbacks reales de Discord."""

import pytest

from commands.correlativas import Correlativas
from tests.harness import InteraccionFalsa


async def invocar(cog, comando, usuario, *args):
    interaccion = InteraccionFalsa(user_id=usuario)
    await getattr(type(cog), comando).callback(cog, interaccion, *args)
    respuesta = interaccion.respuestas[-1]
    assert respuesta.kwargs["ephemeral"]
    return respuesta.kwargs["embed"].description


@pytest.mark.asyncio
async def test_progreso_independiente(base_datos_limpia):
    cog = Correlativas()
    assert "computacion-2024" in await invocar(cog, "planes", 41)
    for usuario in (41, 42):
        await invocar(cog, "unirse", usuario, "computacion-2024")
    assert "F1301" in await invocar(cog, "materias", 41, "computacion-2024", 1)
    assert "Aprobada" in await invocar(cog, "aprobar", 41, "D1001")
    assert "Ya estaba" in await invocar(cog, "aprobar", 41, "D1001")
    siguientes = await invocar(Correlativas(), "siguientes", 41)
    assert "F1301" in siguientes and "D1001" not in siguientes
    assert "F1301" not in await invocar(cog, "siguientes", 42)


@pytest.mark.asyncio
async def test_altas_administrativas(base_datos_limpia, monkeypatch):
    monkeypatch.setattr("commands.correlativas.es_admin", lambda usuario: usuario == 1)
    cog = Correlativas()
    assert "reservado" in await invocar(cog, "agregar_plan", 42, "sistemas")
    assert "agregado" in await invocar(cog, "agregar_plan", 1, "sistemas")
    assert "agregada" in await invocar(cog, "agregar_materia", 1, "sistemas", "M1", 1, "Matemática I")
    datos = ("sistemas", "M2", 2, "Matemática II")
    assert "previa" in await invocar(cog, "agregar_materia", 1, *datos, "NO")
    assert "agregada" in await invocar(cog, "agregar_materia", 1, *datos, "M1")
    await invocar(cog, "unirse", 42, "sistemas")
    assert "M2" not in await invocar(cog, "siguientes", 42)
    await invocar(cog, "aprobar", 42, "M1")
    assert "M2" in await invocar(cog, "siguientes", 42)


@pytest.mark.asyncio
async def test_plan_informatica_2027(base_datos_limpia):
    cog = Correlativas()
    assert 'informatica-2027' in await invocar(cog, 'planes', 41)
    await invocar(cog, 'unirse', 41, 'informatica-2027')
    assert 'SI106' not in await invocar(cog, 'siguientes', 41)
    await invocar(cog, 'aprobar', 41, 'CNE')
    assert 'SI106' in await invocar(cog, 'siguientes', 41)

    for codigo in ('CNP', 'CNM', 'SI106', 'SI108', 'SI101', 'SI107', 'SI109',
                   'SI102', 'SI211', 'SI203', 'SI207', 'SI212', 'SI202', 'SI206', 'SI204'):
        await invocar(cog, 'aprobar', 41, codigo)
    assert '0I503' not in await invocar(cog, 'siguientes', 41)
    await invocar(cog, 'aprobar', 41, 'SI208')
    await invocar(cog, 'aprobar', 41, 'SI308')
    assert '0I503' not in await invocar(cog, 'siguientes', 41)
    await invocar(cog, 'aprobar', 41, 'SI302')
    assert '0I503' in await invocar(cog, 'siguientes', 41)
