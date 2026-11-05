"""Configuración SQLite y conexiones directas."""

import os
import subprocess
import sys

import pytest


def ejecutar_con_configuracion(codigo, **variables):
    entorno = os.environ.copy()
    entorno.update(variables)
    return subprocess.run(
        [sys.executable, "-c", codigo],
        env=entorno, text=True, capture_output=True, check=False,
    )


def test_rechaza_url_antigua_sin_exponer_credenciales():
    resultado = ejecutar_con_configuracion(
        "import config", DATABASE_URL="postgresql://usuario:secreto@servidor/base"
    )
    assert resultado.returncode != 0
    assert "DATABASE_URL ya no está soportada" in resultado.stderr
    assert "secreto" not in resultado.stderr


@pytest.mark.parametrize("ruta", ["", "  ", ":memory:"])
def test_rechaza_ruta_no_persistente(ruta):
    resultado = ejecutar_con_configuracion(
        "import config", DATABASE_URL="", DATABASE=ruta,
    )
    assert resultado.returncode != 0
    assert "archivo SQLite persistente" in resultado.stderr


async def test_conexion_directa_comparte_archivo_y_revierte_sin_commit(base_datos_limpia):
    from core.sqlite import conectar
    from modules.madrugue.database import tiene_registro

    async with conectar() as conexion:
        await conexion.execute(
            "INSERT INTO registros (guild_id,user_id,username,fecha,hora,"
            "puntos_base,multiplicador,puntos_finales) VALUES (?,?,?,?,?,?,?,?)",
            (1, 2, "Usuario", "2026-01-01", "06:00", 100, 1.0, 100),
        )
        await conexion.commit()
    from datetime import date
    assert await tiene_registro(1, 2, date(2026, 1, 1))

    async with conectar() as conexion:
        await conexion.execute("DELETE FROM registros")
        # Salir sin commit deja intacta la fila.
    assert await tiene_registro(1, 2, date(2026, 1, 1))


def test_ruta_con_signos_es_un_nombre_de_archivo(tmp_path):
    ruta = tmp_path / "base?progreso%.db"
    resultado = ejecutar_con_configuracion(
        "import asyncio; from core.database import inicializar_db; "
        "asyncio.run(inicializar_db())",
        DATABASE_URL="", DATABASE=str(ruta),
    )
    assert resultado.returncode == 0, resultado.stderr
    assert ruta.is_file()


async def test_importacion_madrugue_atomica_e_idempotente(base_datos_limpia):
    from modules.madrugue.database import importar_registros, obtener_total_puntos

    existentes = [(1, "Usuario", "2026-01-01", "06:00", 100, 1.0, 100)]
    assert await importar_registros(5, existentes) == (1, 0)
    assert await importar_registros(5, existentes) == (0, 1)

    nuevas_y_conflicto = [
        (2, "Otro", "2026-01-02", "06:00", 100, 1.0, 100),
        (1, "Usuario", "2026-01-01", "07:00", 25, 1.0, 25),
    ]
    with pytest.raises(ValueError, match="conflicto"):
        await importar_registros(5, nuevas_y_conflicto)
    assert await obtener_total_puntos(5, 1) == 100
    assert await obtener_total_puntos(5, 2) == 0


def test_combinar_sqlite_respalda_y_fusiona(tmp_path):
    import sqlite3

    origen = tmp_path / "origen.db"
    destino = tmp_path / "destino.db"
    codigo = (
        "import asyncio; from core.database import inicializar_db; "
        "asyncio.run(inicializar_db())"
    )
    for ruta in (origen, destino):
        resultado = ejecutar_con_configuracion(codigo, DATABASE_URL="", DATABASE=str(ruta))
        assert resultado.returncode == 0, resultado.stderr
    from core.temporada import inicio_temporada
    with sqlite3.connect(origen) as db:
        db.execute(
            "INSERT INTO registros (guild_id,user_id,username,fecha,hora,puntos_base,"
            "multiplicador,puntos_finales) VALUES (1,2,'Usuario',?,"
            "'06:00',100,1.0,100)", (inicio_temporada().date().isoformat(),)
        )

    entorno = os.environ.copy()
    entorno.update(DATABASE_URL="", DATABASE=str(destino))
    for aplicar in (False, True):
        comando = [sys.executable, "-m", "scripts.combinar_db", str(origen)]
        if aplicar:
            comando.append("--aplicar")
        resultado = subprocess.run(comando, env=entorno, text=True, capture_output=True)
        assert resultado.returncode == 0, resultado.stderr
        with sqlite3.connect(destino) as db:
            cantidad = db.execute("SELECT COUNT(*) FROM registros").fetchone()[0]
        assert cantidad == int(aplicar)
    copias = list(tmp_path.glob("destino.antes-de-combinar-*.db"))
    assert len(copias) == 1
    with sqlite3.connect(copias[0]) as db:
        assert db.execute("SELECT COUNT(*) FROM registros").fetchone()[0] == 0
