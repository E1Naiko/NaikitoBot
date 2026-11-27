"""Flujos de correlativas por los callbacks reales de Discord."""

import pytest

from commands.correlativas import Correlativas
from modules.correlativas.logic import listado
from tests.harness import InteraccionFalsa


def test_listado_siguientes_indica_optativas_sin_anio():
    materias = {
        'I1103': {'nombre': 'Programación III', 'anio': 2},
        'I1161': {'nombre': 'Internet de las Cosas', 'anio': None},
    }
    salida = listado(materias, lambda _codigo, _materia: True, mostrar_anio=True)
    assert 'I1103 · Programación III (2° año)' in salida
    assert 'I1161 · Internet de las Cosas (optativa, sin año fijo)' in salida


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
    assert "(1° año)" in siguientes
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
async def test_estado_cursando_suma_al_progreso_pero_no_habilita_ni_completa(base_datos_limpia):
    cog = Correlativas()
    await invocar(cog, 'unirse', 41, 'informatica-2027')
    respuesta = await invocar(cog, 'cursando', 41, 'CNE, SI208')
    assert 'Marcadas como cursando' in respuesta
    siguientes = await invocar(cog, 'siguientes', 41)
    assert 'CNE ·' not in siguientes and 'SI208 ·' not in siguientes
    assert 'SI106 ·' not in siguientes  # Cursar CNE no satisface su correlativa.
    faltantes = await invocar(cog, 'faltantes', 41)
    assert 'SI208 · Taller de lecto-comprensión y Traducción en Inglés (2° año) (cursando)' in faltantes
    avance = await invocar(cog, 'progreso', 41)
    assert '\nSolo aprobadas: **0,0%** (0 de 34)' in avance
    assert '\nContando cursadas: **2,9%** (1 de 34)' in avance
    assert 'Aprobadas:' in await invocar(cog, 'aprobar', 41, 'CNE, SI208')
    assert 'SI106 ·' in await invocar(cog, 'siguientes', 41)
    assert 'SI208 ·' not in await invocar(cog, 'faltantes', 41)


async def test_varios_planes_se_muestran_y_mantienen_aprobaciones_separadas(base_datos_limpia):
    cog = Correlativas()
    await invocar(cog, 'unirse', 41, 'informatica-2027')
    await invocar(cog, 'unirse', 41, 'apu-2027')
    progreso = await invocar(cog, 'progreso', 41)
    assert '**apu-2027**' in progreso and '**informatica-2027**' in progreso
    respuesta = await invocar(cog, 'aprobar', 41, 'CNE')
    assert '**apu-2027**' in respuesta and '**informatica-2027**' in respuesta
    faltantes = await invocar(cog, 'faltantes', 41)
    assert '**Materias pendientes — apu-2027**' in faltantes
    assert '**Materias pendientes — informatica-2027**' in faltantes
    assert 'CNE ·' not in faltantes


async def test_faltantes_lista_todo_lo_no_aprobado_del_plan(base_datos_limpia):
    cog = Correlativas()
    assert 'unirse' in await invocar(cog, 'faltantes', 41)
    await invocar(cog, 'unirse', 41, 'informatica-2027')
    await invocar(cog, 'aprobar', 41, 'CNE')
    pendientes = await invocar(cog, 'faltantes', 41)
    assert 'Materias pendientes del plan informatica-2027' in pendientes
    assert 'CNE ·' not in pendientes
    assert 'CNP ·' in pendientes
    assert '(1° año)' in pendientes


async def test_aprobar_varias_materias_separadas_por_comas(base_datos_limpia):
    cog = Correlativas()
    await invocar(cog, 'unirse', 41, 'informatica-2027')
    respuesta = await invocar(cog, 'aprobar', 41, 'CNE, CNP')
    assert 'Aprobadas:' in respuesta
    assert 'Expresión de Problemas y Algoritmos' in respuesta
    assert 'Conceptos de Procesadores e Inteligencia Artificial' in respuesta


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


async def test_filtros_de_semestre(base_datos_limpia):
    cog = Correlativas()
    args = ('informatica-2023', 1)
    primero = await invocar(cog, 'materias', 41, *args, '1er Semestre')
    segundo = await invocar(cog, 'materias', 41, *args, '2do Semestre')
    ambos = await invocar(cog, 'materias', 41, *args, 'Ambos')
    assert 'SI106 ·' in primero and 'SI107 ·' not in primero
    assert 'SI107 ·' in segundo and 'SI106 ·' not in segundo
    assert 'SI106 ·' in ambos and 'SI107 ·' in ambos and 'CNE ·' in ambos
    await invocar(cog, 'unirse', 41, 'informatica-2023')
    assert 'CNE ·' not in await invocar(cog, 'siguientes', 41, '1er Semestre')
    assert 'CNE ·' in await invocar(cog, 'siguientes', 41, 'Ambos')


async def test_progreso_apu_cuenta_un_cupo_y_excluye_ingreso(base_datos_limpia):
    cog = Correlativas()
    assert 'unirse' in await invocar(cog, 'progreso', 41)
    await invocar(cog, 'unirse', 41, 'apu-2027')
    assert '0,0%' in await invocar(cog, 'progreso', 41)
    for materia in ('CNE', 'SI306', 'SI304'):
        await invocar(cog, 'aprobar', 41, materia)
    respuesta = await invocar(cog, 'progreso', 41)
    assert 'apu-2027' in respuesta and '1 de 21' in respuesta and '4,8%' in respuesta
    assert '0,0%' not in respuesta


async def test_autocompletar_aprobar_sugiere_pendientes_habilitadas(base_datos_limpia):
    cog = Correlativas()
    interaccion = InteraccionFalsa(user_id=41)

    async def sugerencias(texto=''):
        assert cog.aprobar.get_parameter('materia').autocomplete
        callback = cog.autocompletar_materia
        return {opcion.value: opcion.name for opcion in await callback(interaccion, texto)}

    assert await sugerencias() == {}
    await invocar(cog, 'unirse', 41, 'informatica-2023')
    iniciales = await sugerencias()
    assert 'CNE' in iniciales and 'SI106' not in iniciales
    for codigo in ('CNE', 'CNC', 'CNM'):
        await invocar(cog, 'aprobar', 41, codigo)
    assert await sugerencias('si106') == {'SI106': 'SI106 · Conceptos de Algoritmos, Datos y Programas'}
    assert 'SI106' in await sugerencias('algoritmos')
    assert 'CNE' not in await sugerencias()


async def test_listado_largo_envia_una_pagina_y_edita_al_avanzar(base_datos_limpia, monkeypatch):
    import commands.correlativas as modulo

    monkeypatch.setattr(modulo, 'ejecutar', lambda *_: '\n'.join(['A' * 100] * 40 + ['última materia']))
    cog = Correlativas()
    interaccion = InteraccionFalsa(user_id=41)
    await type(cog).siguientes.callback(cog, interaccion)
    assert len(interaccion.respuestas) == 1
    respuesta = interaccion.respuestas[0].kwargs
    assert respuesta['ephemeral']
    assert 'última materia' not in respuesta['embed'].description
    vista = respuesta['view']
    assert vista.anterior.disabled and not vista.siguiente.disabled
    assert not await vista.interaction_check(InteraccionFalsa(user_id=42))
    clic = InteraccionFalsa(user_id=41)
    assert await vista.interaction_check(clic)
    await vista.siguiente.callback(clic)
    assert len(clic.respuestas) == 1
    assert 'última materia' in clic.respuestas[0].kwargs['embed'].description
    assert vista.siguiente.disabled and not vista.anterior.disabled


async def test_correlativas_respeta_pausa_tras_429(base_datos_limpia, monkeypatch):
    import commands.correlativas as modulo
    from tests.harness import error_http

    pausa = []
    intentos = []

    def registrar(error, *, contexto):
        assert error.status == 429
        pausa.append(contexto)
        return 300

    async def rechazar(**kwargs):
        intentos.append(kwargs)
        raise error_http(429, '<html>bloqueo</html>')

    monkeypatch.setattr(modulo, 'registrar_limite', registrar)
    monkeypatch.setattr(modulo, 'espera_restante', lambda: 300 if pausa else 0)
    cog = Correlativas()
    interaccion = InteraccionFalsa(user_id=41)
    monkeypatch.setattr(interaccion.response, 'send_message', rechazar)
    for _ in range(2):
        await type(cog).planes.callback(cog, interaccion)
    assert len(intentos) == 1
    assert pausa == ['respuesta de correlativas']
