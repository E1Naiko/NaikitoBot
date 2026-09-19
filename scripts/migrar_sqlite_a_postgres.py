"""Migra los datos del viejo ``naikito.db`` (SQLite) a la base nueva.

El bot pasó de SQLite crudo a SQLAlchemy asíncrono: en producción se usa
PostgreSQL (``postgresql+asyncpg://...`` en ``DATABASE_URL``) y en
desarrollo sigue funcionando SQLite. Este script copia **los datos** de una
instalación existente al destino que indique ``DATABASE_URL``, creando el
esquema con los modelos ORM si no existe.

Uso (desde la raíz del proyecto)::

    # 1. Ver qué haría, sin tocar el destino:
    python -m scripts.migrar_sqlite_a_postgres naikito.db --solo-ver

    # 2. Migrar de verdad (el destino tiene que estar vacío):
    DATABASE_URL="postgresql+asyncpg://usuario:clave@host:5432/naikito" \
        python -m scripts.migrar_sqlite_a_postgres naikito.db

    # Si el destino ya tiene datos y querés pisarlo:
    python -m scripts.migrar_sqlite_a_postgres naikito.db --limpiar

Notas:
- El archivo de origen se abre en modo lectura: nunca se modifica.
- Las tablas se copian en orden de dependencias (foreign keys).
- Las fechas guardadas como texto ISO se convierten a ``datetime``/``date``
  nativos; las que vienen sin zona horaria se interpretan en la ``TIMEZONE``
  del bot.
- En PostgreSQL se reajustan las secuencias de las claves autoincrementales
  para que los próximos INSERT no choquen con los ids migrados.
"""

import argparse
import asyncio
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

# El script corre como módulo desde la raíz del proyecto; aseguramos el
# path por si alguien lo ejecuta directo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import Date, DateTime, delete, func, insert, select

from config import DATABASE_URL, TIMEZONE
from core.database import Base, crear_sesion, engine, registrar_modelos


def leer_origen(ruta: Path) -> dict[str, list[dict]]:
    """Lee todas las tablas del SQLite viejo como listas de dicts."""

    conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    conexion.row_factory = sqlite3.Row

    datos = {}
    try:
        tablas = [
            fila[0]
            for fila in conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        for tabla in tablas:
            filas = conexion.execute(f"SELECT * FROM {tabla}").fetchall()
            datos[tabla] = [dict(fila) for fila in filas]
    finally:
        conexion.close()

    return datos


def interpretar_fecha(valor, columna):
    """Convierte un valor de fecha del SQLite viejo al tipo de la columna."""

    if valor is None or not isinstance(valor, str):
        return valor

    es_fecha = isinstance(columna.type, Date)

    try:
        bruto = valor.replace("Z", "+00:00")
        if es_fecha:
            return date.fromisoformat(bruto[:10])

        momento = datetime.fromisoformat(bruto)
    except ValueError:
        # Formatos históricos menos frecuentes ("2026-09-19 03:00:00").
        momento = datetime.strptime(valor[:19], "%Y-%m-%d %H:%M:%S")

    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TIMEZONE)

    return momento


def es_columna_temporal(columna) -> bool:
    return isinstance(columna.type, (DateTime, Date))


def valor_para_columna(columna, filas: list[dict], clave: str):
    """El valor de una columna del modelo para cada fila vieja.

    Si la tabla de origen no tenía la columna (instalación vieja a la que
    nunca le corrió el ALTER), se usa el default del modelo.
    """

    if clave in filas[0]:
        if es_columna_temporal(columna):
            return [interpretar_fecha(fila.get(clave), columna) for fila in filas]

        return [fila.get(clave) for fila in filas]

    default = columna.default
    if default is not None:
        fijo = default.arg() if callable(default.arg) else default.arg
        print(f"    ⚠️ columna '{clave}' ausente en origen: default {fijo!r}")
        return [fijo for _ in filas]

    if not columna.nullable:
        raise RuntimeError(
            f"La columna '{clave}' de '{columna.table.name}' no existe en el "
            "origen, es NOT NULL y no tiene default: no se puede migrar."
        )

    print(f"    ⚠️ columna '{clave}' ausente en origen: NULL")
    return [None for _ in filas]


async def migrar(ruta: Path, solo_ver: bool, limpiar: bool) -> None:
    if not ruta.exists():
        raise SystemExit(f"No existe el archivo de origen: {ruta}")

    print(f"Origen:  {ruta}")
    print(f"Destino: {DATABASE_URL}")

    origen = leer_origen(ruta)
    print(f"Tablas en origen: {len(origen)}\n")

    registrar_modelos()
    tablas = Base.metadata.sorted_tables

    if solo_ver:
        total = 0
        for tabla in tablas:
            filas = origen.get(tabla.name, [])
            extra = "(no existe en origen)" if tabla.name not in origen else ""
            print(f"• {tabla.name}: {len(filas)} filas a copiar {extra}".rstrip())
            total += len(filas)
        print(f"\nSimulación: se copiarían {total} filas.")
        return

    resumen = []

    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

        for tabla in tablas:
            nombre = tabla.name
            filas = origen.get(nombre, [])

            if not filas:
                print(f"• {nombre}: sin filas en origen")
                resumen.append((nombre, 0))
                continue

            existentes = (
                await conexion.execute(select(func.count()).select_from(tabla))
            ).scalar_one()

            if solo_ver:
                print(f"• {nombre}: {len(filas)} filas a copiar")
                resumen.append((nombre, len(filas)))
                continue

            if existentes and not limpiar:
                raise SystemExit(
                    f"La tabla destino '{nombre}' ya tiene {existentes} filas. "
                    "Usá --limpiar para vaciarla antes de migrar."
                )

            if existentes and limpiar:
                await conexion.execute(delete(tabla))

            columnas = {c.key: c for c in tabla.columns}
            ignoradas = set(filas[0]) - set(columnas)
            if ignoradas:
                print(
                    f"• {nombre}: columnas del origen sin destino "
                    f"({', '.join(sorted(ignoradas))}): se ignoran"
                )

            valores = {
                clave: valor_para_columna(columna, filas, clave)
                for clave, columna in columnas.items()
            }

            lotes = [
                [
                    {clave: columna[i] for clave, columna in valores.items()}
                    for i in range(inicio, min(inicio + 500, len(filas)))
                ]
                for inicio in range(0, len(filas), 500)
            ]
            for lote in lotes:
                await conexion.execute(insert(tabla), lote)

            print(f"• {nombre}: {len(filas)} filas copiadas")
            resumen.append((nombre, len(filas)))

        await ajustar_secuencias_postgres(conexion, tablas)

    print()
    total = sum(filas for _, filas in resumen)
    print(f"Migración completada: {total} filas.")

    async with crear_sesion() as sesion:
        for tabla in tablas:
            cuenta = (
                await sesion.execute(select(func.count()).select_from(tabla))
            ).scalar_one()
            esperado = dict(resumen).get(tabla.name, 0)
            if cuenta != esperado:
                raise SystemExit(
                    f"Verificación fallida en '{tabla.name}': "
                    f"{cuenta} != {esperado}"
                )
    print("Verificación: las cuentas coinciden tabla por tabla. ✅")


async def ajustar_secuencias_postgres(conexion, tablas) -> None:
    """En PostgreSQL, deja las secuencias de los PK autoincrementales
    apuntando después del mayor id migrado."""

    if engine.dialect.name != "postgresql":
        return

    from sqlalchemy import text

    for tabla in tablas:
        clave = next(
            (
                columna
                for columna in tabla.columns
                if columna.primary_key and columna.autoincrement is True
            ),
            None,
        )
        if clave is None:
            continue

        await conexion.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{tabla.name}', "
                f"'{clave.name}'), COALESCE(MAX({clave.name}), 1)) "
                f"FROM {tabla.name}"
            )
        )
        print(f"• secuencia de {tabla.name}.{clave.name} reajustada")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Migra los datos del SQLite viejo (naikito.db) a la base nueva "
            "definida por DATABASE_URL."
        )
    )
    parser.add_argument(
        "origen",
        nargs="?",
        default="naikito.db",
        help="ruta al SQLite viejo (default: naikito.db)",
    )
    parser.add_argument(
        "--solo-ver",
        action="store_true",
        help="muestra qué se copiaría sin escribir nada",
    )
    parser.add_argument(
        "--limpiar",
        action="store_true",
        help="vacía las tablas destino antes de copiar (pisa datos)",
    )
    argumentos = parser.parse_args()

    asyncio.run(
        migrar(Path(argumentos.origen), argumentos.solo_ver, argumentos.limpiar)
    )


if __name__ == "__main__":
    main()
