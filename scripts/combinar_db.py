"""Fusiona un backup SQLite con la base actual sin modificar el origen.

Por defecto simula en memoria. Usá ``--aplicar`` para escribir; antes se crea
un respaldo consistente de la base destino. Ejecutar con el bot detenido.

    python -m scripts.combinar_db backup.db
    python -m scripts.combinar_db backup.db --aplicar --estado actual

Los eventos se unen por identidad lógica; los estados existentes se conservan
(``actual``), se reemplazan (``backup``) o toman el mayor valor numérico
(``mayor``). Los IDs de padres se remapean antes de importar sus hijos.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATABASE  # noqa: E402
from core.database import esquema_sql  # noqa: E402

IDENTIDAD: dict[str, tuple[list[str], dict[str, str], str]] = {
    "box_usuarios": (["guild_id", "user_id"], {}, "estado"),
    "box_mejoras": (["guild_id", "user_id", "mejora"], {}, "estado"),
    "box_equipo": (["guild_id", "user_id"], {}, "estado"),
    "box_config_guild": (["guild_id"], {}, "estado"),
    "box_acciones": (["guild_id", "user_id"], {}, "estado"),
    "box_desafios": (
        ["guild_id", "retador_id", "contrincante_id"],
        {},
        "estado",
    ),
    "box_desafios_historial": (
        ["guild_id", "retador_id", "contrincante_id", "ganador_id", "creado_en"],
        {},
        "log",
    ),
    "box_combates": (
        ["guild_id", "retador_id", "contrincante_id", "iniciado_en"],
        {},
        "log",
    ),
    "box_combates_asaltos": (
        ["combate_id", "asalto"],
        {"combate_id": "box_combates"},
        "log",
    ),
    "box_sponsors": (
        ["guild_id", "user_id", "tipo", "obtenido_en"],
        {},
        "log",
    ),
    "registros": (["guild_id", "user_id", "fecha"], {}, "log"),
    "lahora_registros": (
        ["guild_id", "user_id", "fecha", "ventana"],
        {},
        "log",
    ),
    "ssf_desafios": (
        ["guild_id", "nombre", "fecha_inicio", "fecha_fin"],
        {},
        "estado",
    ),
    "ssf_participantes": (
        ["desafio_id", "user_id"],
        {"desafio_id": "ssf_desafios"},
        "estado",
    ),
    "ssf_registros": (
        ["desafio_id", "user_id", "fecha"],
        {"desafio_id": "ssf_desafios"},
        "log",
    ),
    "ssf_revisiones": (
        ["desafio_id"],
        {"desafio_id": "ssf_desafios"},
        "estado",
    ),
}

def _q(nombre):
    """Identificador escapado; los valores se pasan siempre como parámetros."""
    return '"' + nombre.replace('"', '""') + '"'


def _abrir_lectura(ruta):
    return sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)


def leer_origen(ruta):
    datos = {}
    with closing(_abrir_lectura(ruta)) as conexion:
        conexion.row_factory = sqlite3.Row
        tablas = conexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (tabla,) in tablas:
            if tabla in IDENTIDAD:
                datos[tabla] = [dict(fila) for fila in conexion.execute(f"SELECT * FROM {_q(tabla)}")]
    return datos


def respaldar_destino_sqlite():
    destino = Path(DATABASE)
    if not destino.exists():
        print("El destino SQLite todavía no existe: se creará limpio.\n")
        return
    sello = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    copia = destino.with_name(f"{destino.stem}.antes-de-combinar-{sello}.db")
    with closing(_abrir_lectura(destino)) as origen, closing(sqlite3.connect(copia)) as backup:
        origen.backup(backup)
    print(f"Respaldo del destino: {copia}\n")


def _valor_default(db, columna, fila, tabla):
    nombre, tipo, no_nulo, default, pk = columna
    if nombre in fila:
        return fila[nombre]
    if default is not None:
        return db.execute(f"SELECT {default}").fetchone()[0]
    if (tabla, nombre) == ("lahora_registros", "bonus_posicion"):
        return 0
    if no_nulo and not (pk and nombre == "id" and tipo.upper() == "INTEGER"):
        raise RuntimeError(f"El backup no contiene la columna obligatoria {tabla}.{nombre}.")
    return None


def combinar(ruta: Path, aplicar: bool, estado: str):
    if not ruta.is_file():
        raise SystemExit(f"No existe el backup de origen: {ruta}")
    destino = Path(DATABASE)
    if ruta.resolve() == destino.resolve():
        raise SystemExit("El origen y el destino deben ser archivos distintos.")
    print(f"Backup (origen): {ruta}\nDestino:         {destino}")
    print(f"Modo:            {'APLICAR' if aplicar else 'SIMULACIÓN'}\nConflictos estado: {estado}\n")
    origen = leer_origen(ruta)
    if aplicar:
        respaldar_destino_sqlite()
        conexion = sqlite3.connect(destino, timeout=30)
    else:
        conexion = sqlite3.connect(":memory:")
        if destino.exists():
            with closing(_abrir_lectura(destino)) as actual:
                actual.backup(conexion)

    try:
        conexion.executescript("BEGIN IMMEDIATE;\n" + esquema_sql())
        # Los padres deben procesarse antes que sus hijos.
        orden = list(IDENTIDAD)
        orden.remove("box_combates_asaltos")
        orden.insert(orden.index("box_combates") + 1, "box_combates_asaltos")
        remap = {}
        for nombre in orden:
            filas = origen.get(nombre, [])
            claves, fks, categoria = IDENTIDAD[nombre]
            info = conexion.execute(f"PRAGMA table_info({_q(nombre)})").fetchall()
            columnas = [(r[1], r[2], r[3], r[4], r[5]) for r in info]
            pk = [col[0] for col in columnas if col[4]]
            id_col = "id" if pk == ["id"] else None
            nombres = [col[0] for col in columnas]
            nuevas = saltadas = actualizadas = 0
            remap[nombre] = {}

            for fila in filas:
                valores = {col[0]: _valor_default(conexion, col, fila, nombre) for col in columnas}
                fk_roto = False
                for fk, padre in fks.items():
                    viejo = valores[fk]
                    if viejo is not None:
                        nuevo = remap.get(padre, {}).get(viejo)
                        if nuevo is None:
                            fk_roto = True
                            break
                        valores[fk] = nuevo
                if fk_roto:
                    saltadas += 1
                    continue
                condicion = " AND ".join(f"{_q(clave)} IS ?" for clave in claves)
                args = tuple(valores[k] for k in claves)
                existente = conexion.execute(
                    f"SELECT * FROM {_q(nombre)} WHERE {condicion} LIMIT 1", args
                ).fetchone()
                if existente is not None:
                    actual = dict(zip(nombres, existente))
                    if id_col:
                        remap[nombre][fila.get(id_col)] = actual[id_col]
                    cambios = {}
                    if categoria == "estado" and estado != "actual":
                        for col, tipo, _, _, _ in columnas:
                            if col in claves or col in pk:
                                continue
                            valor = valores[col]
                            if estado == "backup":
                                cambios[col] = valor
                            elif any(t in tipo.upper() for t in ("INT", "FLOAT", "REAL", "NUMERIC")) and valor is not None:
                                actual_valor = actual[col]
                                cambios[col] = max(actual_valor, valor) if actual_valor is not None else None
                    if cambios:
                        setters = ", ".join(f"{_q(k)} = ?" for k in cambios)
                        conexion.execute(f"UPDATE {_q(nombre)} SET {setters} WHERE {condicion}",
                                         (*cambios.values(), *args))
                        actualizadas += 1
                    else:
                        saltadas += 1
                    continue
                if id_col:
                    # Dejar que SQLite elija un ID libre, aunque el backup lo reutilice.
                    valores.pop(id_col)
                columnas_insert = list(valores)
                cursor = conexion.execute(
                    f"INSERT INTO {_q(nombre)} ({', '.join(map(_q, columnas_insert))}) "
                    f"VALUES ({', '.join('?' for _ in columnas_insert)})",
                    tuple(valores[c] for c in columnas_insert),
                )
                if id_col:
                    remap[nombre][fila.get(id_col)] = cursor.lastrowid
                nuevas += 1
            print(f"• {nombre}: +{nuevas} nuevas, {saltadas} ya estaban, {actualizadas} actualizadas")
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
    print("\nFusión aplicada. ✅" if aplicar else "\nSimulación completa. No se escribió nada.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origen", nargs="?", default="naikito-BK2492026.db")
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--estado", choices=("actual", "backup", "mayor"), default="actual")
    args = parser.parse_args()
    combinar(Path(args.origen), args.aplicar, args.estado)


if __name__ == "__main__":
    main()
