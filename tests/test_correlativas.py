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


@pytest.mark.asyncio
async def test_plan_apu_2027(base_datos_limpia):
    cog = Correlativas()
    assert 'apu-2027' in await invocar(cog, 'planes', 41)
    await invocar(cog, 'unirse', 41, 'apu-2027')
    tercero = await invocar(cog, 'materias', 41, 'apu-2027', 3)
    assert tercero.count('elegir una asignatura del grupo') == 4
    assert 'SO303 · Bases de Datos 1' in tercero
    assert 'SO410 · Sistemas y Organizaciones' in tercero
    assert '07301' not in await invocar(cog, 'siguientes', 41)
    for codigo in ('SI212', 'SI203', 'SI204', 'SI206', 'SI208'):
        await invocar(cog, 'aprobar', 41, codigo)
    assert '07301' not in await invocar(cog, 'siguientes', 41)
    await invocar(cog, 'aprobar', 41, 'SI302')
    siguientes = await invocar(cog, 'siguientes', 41)
    assert '07301' in siguientes
    assert 'SO303 · Bases de Datos 1 (elegir una asignatura del grupo)' in siguientes


@pytest.mark.parametrize('plan, codigo', [
    ('informatica-2023', 'SI308'), ('sistemas-2023', 'SI308'),
    ('apu-2023', 'SI308'), ('atic-2023', 'PPS'),
])
async def test_ingles_para_tercero_en_planes_2023(base_datos_limpia, plan, codigo):
    cog = Correlativas()
    assert plan in await invocar(cog, 'planes', 41)
    await invocar(cog, 'unirse', 41, plan)
    previas = ('SI210', 'SI203', 'SI204', 'SI206', 'SI302') if codigo == 'PPS' else ('SI102',)
    for previa in previas:
        await invocar(cog, 'aprobar', 41, previa)
    assert codigo not in await invocar(cog, 'siguientes', 41)
    await invocar(cog, 'aprobar', 41, 'SI208')
    assert codigo in await invocar(cog, 'siguientes', 41)


async def test_pps_y_codigo_repetido_en_ciencia_de_datos(base_datos_limpia):
    cog = Correlativas()
    await invocar(cog, 'unirse', 41, 'ciencia-de-datos-2024')
    assert 'I101-BD' in await invocar(cog, 'materias', 41, 'ciencia-de-datos-2024', 2)
    for codigo in ('I101', 'X102', 'E103', 'I104', 'X105', 'E106', 'I201',
                   'I202', 'E203', 'X204', 'E206', 'X207'):
        await invocar(cog, 'aprobar', 41, codigo)
    pendientes = await invocar(cog, 'siguientes', 41)
    assert 'O408' not in pendientes and 'O407' not in pendientes
    assert 'I101-BD' in pendientes
    await invocar(cog, 'aprobar', 41, 'I101-BD')
    assert 'O408' in await invocar(cog, 'siguientes', 41)


async def test_aprobar_muestra_solo_materias_recien_habilitadas(base_datos_limpia):
    cog = Correlativas()
    await invocar(cog, 'unirse', 41, 'informatica-2023')
    for codigo in ('CNE', 'CNC'):
        respuesta = await invocar(cog, 'aprobar', 41, codigo)
        assert 'No se habilitaron materias nuevas' in respuesta
    respuesta = await invocar(cog, 'aprobar', 41, 'CNM')
    assert 'Materias recién habilitadas' in respuesta
    for codigo in ('SI106', 'SI104', 'SI101'):
        assert codigo in respuesta
    assert 'SI208' not in respuesta  # Ya estaba habilitada antes.
    assert 'SI107' not in respuesta  # Sigue requiriendo SI106.
    assert 'SI208' in await invocar(cog, 'siguientes', 41)
    repetida = await invocar(cog, 'aprobar', 41, 'CNM')
    assert 'Ya estaba aprobada' in repetida and 'SI106' not in repetida
