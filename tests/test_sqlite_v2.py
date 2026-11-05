"""Regresiones de transacciones y compatibilidad en la capa SQLite 2.0."""

import asyncio
from datetime import datetime, timedelta
import os
import sqlite3
import subprocess
import sys

from config import TIMEZONE


async def test_accion_se_liquida_una_sola_vez_en_concurrencia(base_datos_limpia):
    from modules.box.database import iniciar_accion, completar_acciones_vencidas, obtener_saldo

    inicio = datetime(2026, 1, 1, 10, tzinfo=TIMEZONE)
    assert await iniciar_accion(1, 2, "TRABAJANDO", inicio, inicio + timedelta(hours=1), 50)
    resultados = await asyncio.gather(*(
        completar_acciones_vencidas(inicio + timedelta(hours=2)) for _ in range(4)
    ))
    assert sum(len(resultado) for resultado in resultados) == 1
    assert (await obtener_saldo(1, 2))[1] == 50


async def test_sponsors_respetan_ciclos_configurados(base_datos_limpia, monkeypatch):
    import modules.box.database as box

    monkeypatch.setattr(box, "BOX_SPONSOR_CICLO_PAGO_HORAS", 2)
    monkeypatch.setattr(box, "BOX_MEDICO_CICLO_HORAS", 3)
    inicio = datetime(2026, 1, 1, 10, tzinfo=TIMEZONE)
    await box.admin_modificar_probabilidad_lesion(1, 2, 40)
    assert (await box.admin_dar_sponsor(1, 2, "redes", inicio))[0]
    assert (await box.admin_dar_sponsor(1, 2, "medico", inicio))[0]

    pagos = await box.procesar_pagos_sponsors(inicio + timedelta(hours=5))
    tratamientos = await box.procesar_sponsors_medicos(inicio + timedelta(hours=5))
    assert pagos[0][3] == box.PAGO_SPONSOR["redes"] * 2
    assert tratamientos[0][2] == 40 * (1 - box.BOX_MEDICO_REDUCCION / 100)
    assert await box.procesar_pagos_sponsors(inicio + timedelta(hours=5)) == []
    assert await box.procesar_sponsors_medicos(inicio + timedelta(hours=5)) == []


async def test_estadisticas_de_box_devuelve_fecha_con_zona(base_datos_limpia):
    from modules.box.database import obtener_estadisticas_box

    momento = datetime(2026, 9, 1, 12, tzinfo=TIMEZONE)
    with sqlite3.connect(base_datos_limpia) as db:
        db.execute("INSERT INTO box_usuarios (guild_id,user_id,lesionado_hasta) VALUES (1,2,?)", (momento.isoformat(),))
    estadisticas = await obtener_estadisticas_box(1, 2)
    assert estadisticas["lesionado_hasta"] == momento


def test_combinar_remapea_padres_y_es_idempotente(tmp_path):
    origen, destino = tmp_path / "origen.db", tmp_path / "destino.db"
    entorno = os.environ.copy()
    entorno["DATABASE_URL"] = ""
    for ruta in (origen, destino):
        entorno["DATABASE"] = str(ruta)
        resultado = subprocess.run(
            [sys.executable, "-c", "import asyncio; from core.database import inicializar_db; asyncio.run(inicializar_db())"],
            env=entorno, capture_output=True, text=True,
        )
        assert resultado.returncode == 0, resultado.stderr
    from core.temporada import inicio_temporada
    inicio = inicio_temporada()
    fecha = inicio.date().isoformat()
    siguiente = (inicio.date() + timedelta(days=1)).isoformat()
    fin = (inicio.date() + timedelta(days=29)).isoformat()
    with sqlite3.connect(origen) as db:
        db.execute("INSERT INTO ssf_desafios VALUES (1,1,'origen',?,?,4,1)", (fecha, fin))
        db.execute("INSERT INTO ssf_participantes (desafio_id,user_id,username,fecha_registro) VALUES (1,2,'Usuario',?)", (inicio.isoformat(),))
        db.execute("INSERT INTO ssf_registros VALUES (1,2,?,'08:00')", (siguiente,))
        db.execute("INSERT INTO ssf_revisiones VALUES (1,?)", (siguiente,))
    with sqlite3.connect(destino) as db:
        db.execute("INSERT INTO ssf_desafios VALUES (1,1,'existente',?,?,4,0)", (fecha, fin))
    entorno["DATABASE"] = str(destino)
    for _ in range(2):
        resultado = subprocess.run(
            [sys.executable, "-m", "scripts.combinar_db", str(origen), "--aplicar"],
            env=entorno, capture_output=True, text=True,
        )
        assert resultado.returncode == 0, resultado.stderr
    with sqlite3.connect(destino) as db:
        nuevo_id = db.execute("SELECT id FROM ssf_desafios WHERE nombre='origen'").fetchone()[0]
        assert nuevo_id != 1
        for tabla in ("ssf_participantes", "ssf_registros", "ssf_revisiones"):
            assert db.execute(f"SELECT desafio_id FROM {tabla}").fetchall() == [(nuevo_id,)]
        assert db.execute("SELECT COUNT(*) FROM ssf_desafios").fetchone()[0] == 2
