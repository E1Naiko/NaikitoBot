"""Combina (fusiona) un backup SQLite con la base de datos actual.

A diferencia de ``migrar_sqlite_a_postgres.py`` —que exige un destino vacío o
lo pisa entero con ``--limpiar``—, este script **fusiona** los datos de un
backup dentro de la base que ya está en uso, sin perder nada de lo que hay
hoy y recuperando lo que estaba en el backup.

Caso de uso: el deploy tiene la base actual (``naikito.db``) y una copia de
seguridad vieja (``naikito-BK2492026.db``, del día 24). Queremos que los dos
mundos convivan: recuperar los registros que hoy faltan y que los rankings de
puntos reflejen la suma de todo.

CÓMO FUSIONA
------------
Cada tabla se fusiona por su **identidad lógica** (la clave natural o la
restricción UNIQUE), no por el ``id`` autoincremental —que puede chocar entre
las dos bases—. Hay dos categorías:

* Tablas de **eventos** (madrugue ``registros``, ``lahora_registros``,
  ``ssf_registros``, historial de desafíos, combates, sponsors): son un
  registro histórico. Se hace la **unión**: se insertan los eventos del backup
  que hoy no están y se dejan intactos los que ya existen. Como los puntos se
  guardan por evento, los totales de los rankings pasan a ser automáticamente
  la SUMA de todo (backup + actual). No se duplica ni se pierde nada.

* Tablas de **estado** (progreso de boxeo: dinero/experiencia/equipo, rachas
  de SSF, config del server): representan una foto del momento, no eventos que
  se sumen. Ahí:
    - Si una fila existe SOLO en el backup (se perdió), se **restaura**.
    - Si existe en las dos, se aplica la política ``--estado``:
        * ``actual`` (por defecto): se conserva el valor de la base actual.
        * ``backup``: se pisa con el valor del backup.
        * ``mayor``:  para columnas numéricas se toma el valor más alto de las
                      dos (útil si la base actual perdió progreso); el resto se
                      deja como está en la actual.

Las tablas con ``id`` autoincremental que son padres de otras (``ssf_desafios``
→ participantes/registros/revisiones, ``box_combates`` → asaltos) se reindexan:
al insertar filas nuevas se les asigna un id libre y las hijas se re-apuntan al
id correcto, así las foreign keys nunca quedan rotas.

SEGURIDAD
---------
* El backup de origen se abre en modo SOLO LECTURA: nunca se modifica.
* Por defecto el script SIMULA (dry-run) y solo informa qué haría. Hay que
  pasar ``--aplicar`` para escribir de verdad.
* Antes de escribir, si el destino es un archivo SQLite, se hace una copia
  ``<archivo>.antes-de-combinar-<timestamp>.db`` por las dudas.

USO (desde la raíz del proyecto)
--------------------------------
    # 1) Ver qué haría (no toca nada). Usa DATABASE_URL/DATABASE del .env:
    python -m scripts.combinar_db naikito-BK2492026.db

    # 2) Aplicar de verdad (política de estado por defecto: 'actual'):
    python -m scripts.combinar_db naikito-BK2492026.db --aplicar

    # Variantes de conflicto en tablas de estado:
    python -m scripts.combinar_db naikito-BK2492026.db --aplicar --estado mayor

Podés forzar el destino con la variable de entorno, por ejemplo:
    DATABASE=naikito.db python -m scripts.combinar_db naikito-BK2492026.db --aplicar
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

# Permite ejecutar el archivo como módulo desde la raíz del proyecto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import (  # noqa: E402
    Date,
    DateTime,
    Float,
    Integer,
    delete,
    func,
    insert,
    select,
    update,
)

from config import DATABASE, DATABASE_URL, TIMEZONE  # noqa: E402
from core.database import Base, engine, registrar_modelos  # noqa: E402


# ---------------------------------------------------------------------------
# Identidad lógica de cada tabla.
#
#   tabla -> (claves_de_identidad, {columna_fk: tabla_padre}, categoria)
#
# categoria:
#   "log"    -> tabla de eventos: unión pura (insertar lo que falte).
#   "estado" -> foto del momento: aplica la política --estado en conflictos.
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Lectura del backup (SQLite, solo lectura).
# ---------------------------------------------------------------------------
def leer_origen(ruta: Path) -> dict[str, list[dict]]:
    """Lee todas las tablas del backup SQLite como listas de dicts."""

    conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    conexion.row_factory = sqlite3.Row
    datos: dict[str, list[dict]] = {}
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


# ---------------------------------------------------------------------------
# Conversión / normalización de valores.
# ---------------------------------------------------------------------------
def es_columna_temporal(columna) -> bool:
    return isinstance(columna.type, (DateTime, Date))


def interpretar_fecha(valor, columna):
    """Convierte un valor de fecha (texto ISO del SQLite) al tipo de la columna."""

    if valor is None or not isinstance(valor, str):
        return valor

    es_fecha = isinstance(columna.type, Date)
    try:
        bruto = valor.replace("Z", "+00:00")
        if es_fecha:
            return date.fromisoformat(bruto[:10])
        momento = datetime.fromisoformat(bruto)
    except ValueError:
        momento = datetime.strptime(valor[:19], "%Y-%m-%d %H:%M:%S")

    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TIMEZONE)
    return momento


def normalizar_clave(valor):
    """Vuelve un valor comparable de forma estable entre backup y destino."""

    if isinstance(valor, datetime):
        return ("dt", valor.isoformat())
    if isinstance(valor, date):
        return ("d", valor.isoformat())
    return valor


def valor_convertido(columna, fila: dict, clave: str, filas: list[dict]):
    """El valor de una columna para una fila del backup, ya convertido.

    Si el backup no tenía la columna, cae al default del modelo (igual que el
    script de migración).
    """

    if clave in fila:
        if es_columna_temporal(columna):
            return interpretar_fecha(fila.get(clave), columna)
        return fila.get(clave)

    default = columna.default
    if default is not None:
        return default.arg() if callable(default.arg) else default.arg
    if not columna.nullable:
        raise RuntimeError(
            f"La columna '{clave}' de '{columna.table.name}' no existe en el "
            "backup, es NOT NULL y no tiene default: no se puede fusionar."
        )
    return None


def columna_id_autoincremental(tabla):
    """Devuelve la columna PK autoincremental única, o None si no hay."""

    pks = list(tabla.primary_key.columns)
    if len(pks) != 1:
        return None
    col = pks[0]
    if isinstance(col.type, Integer) and col.autoincrement in (True, "auto"):
        return col
    return None


# ---------------------------------------------------------------------------
# Fusión.
# ---------------------------------------------------------------------------
async def combinar(ruta: Path, aplicar: bool, estado: str) -> None:
    if not ruta.exists():
        raise SystemExit(f"No existe el backup de origen: {ruta}")

    print(f"Backup (origen): {ruta}")
    print(f"Destino:         {DATABASE_URL}")
    print(f"Modo:            {'APLICAR (escribe)' if aplicar else 'SIMULACIÓN (dry-run)'}")
    print(f"Conflictos estado: {estado}\n")

    origen = leer_origen(ruta)
    registrar_modelos()
    tablas = Base.metadata.sorted_tables  # orden que respeta las foreign keys

    if aplicar:
        respaldar_destino_sqlite()

    # old_id (del backup) -> id en destino, por tabla padre.
    remap: dict[str, dict[int, int]] = {}
    resumen: list[tuple[str, int, int, int]] = []  # tabla, insertadas, saltadas, actualizadas

    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

        for tabla in tablas:
            nombre = tabla.name
            filas = origen.get(nombre, [])
            claves, fks, categoria = IDENTIDAD.get(nombre, (None, {}, "log"))

            if nombre not in IDENTIDAD:
                print(f"• {nombre}: sin regla de identidad definida, se omite")
                resumen.append((nombre, 0, len(filas), 0))
                continue

            id_col = columna_id_autoincremental(tabla)
            if id_col is not None:
                remap.setdefault(nombre, {})

            if not filas:
                print(f"• {nombre}: el backup no tiene filas")
                resumen.append((nombre, 0, 0, 0))
                continue

            columnas = {c.key: c for c in tabla.columns}

            # Índice de lo que ya existe en el destino, por clave de identidad.
            cols_sel = [tabla.c[k] for k in claves]
            if id_col is not None:
                cols_sel.append(id_col)
            existentes = (await conexion.execute(select(*cols_sel))).all()

            indice: dict[tuple, int | None] = {}
            for fila in existentes:
                datos = fila._mapping
                clave_val = tuple(normalizar_clave(datos[k]) for k in claves)
                indice[clave_val] = datos[id_col.key] if id_col is not None else None

            # Próximo id libre para inserciones (tablas con id autoincremental).
            proximo_id = None
            if id_col is not None:
                maximo = (
                    await conexion.execute(select(func.max(id_col)))
                ).scalar_one()
                proximo_id = (maximo or 0) + 1

            nuevas: list[dict] = []
            actualizaciones: list[tuple[tuple, dict]] = []
            saltadas = 0

            for fila in filas:
                # Valores convertidos de todas las columnas del modelo.
                valores = {
                    clave: valor_convertido(col, fila, clave, filas)
                    for clave, col in columnas.items()
                }

                # Re-mapear foreign keys al id que quedó en el destino.
                fk_roto = False
                for fk_col, tabla_padre in fks.items():
                    viejo = valores.get(fk_col)
                    if viejo is None:
                        continue
                    nuevo = remap.get(tabla_padre, {}).get(viejo)
                    if nuevo is None:
                        # El padre no se pudo mapear (no estaba ni se insertó):
                        # se descarta la fila hija para no romper la FK.
                        fk_roto = True
                        break
                    valores[fk_col] = nuevo
                if fk_roto:
                    saltadas += 1
                    continue

                clave_val = tuple(normalizar_clave(valores[k]) for k in claves)

                if clave_val in indice:
                    # Ya existe: mapear id y resolver conflicto si es estado.
                    if id_col is not None:
                        remap[nombre][fila.get(id_col.key)] = indice[clave_val]
                    if categoria == "estado" and estado != "actual":
                        cambio = calcular_actualizacion(
                            tabla, columnas, claves, valores, estado
                        )
                        if cambio:
                            actualizaciones.append((clave_val, cambio))
                    else:
                        saltadas += 1
                    continue

                # Fila nueva: asignar id libre si corresponde y recordar remap.
                if id_col is not None:
                    viejo_id = fila.get(id_col.key)
                    valores[id_col.key] = proximo_id
                    remap[nombre][viejo_id] = proximo_id
                    indice[clave_val] = proximo_id
                    proximo_id += 1
                else:
                    indice[clave_val] = None

                nuevas.append(valores)

            # Escribir (solo si --aplicar).
            actualizadas = 0
            if aplicar:
                if nuevas:
                    for i in range(0, len(nuevas), 500):
                        await conexion.execute(insert(tabla), nuevas[i : i + 500])
                for clave_val, cambio in actualizaciones:
                    cond = _condicion_por_clave(tabla, claves, clave_val)
                    await conexion.execute(
                        update(tabla).where(cond).values(**cambio)
                    )
                    actualizadas += 1
            else:
                actualizadas = len(actualizaciones)

            detalle = f"+{len(nuevas)} nuevas, {saltadas} ya estaban"
            if categoria == "estado" and estado != "actual":
                detalle += f", {actualizadas} actualizadas ({estado})"
            print(f"• {nombre}: {detalle}")
            resumen.append((nombre, len(nuevas), saltadas, actualizadas))

        await ajustar_secuencias_postgres(conexion, tablas)

        if not aplicar:
            # En dry-run deshacemos cualquier cambio implícito.
            raise _Rollback()


async def combinar_seguro(ruta: Path, aplicar: bool, estado: str) -> None:
    try:
        await combinar(ruta, aplicar, estado)
    except _Rollback:
        pass

    total_nuevas = 0  # el resumen ya se imprimió por tabla
    print()
    if aplicar:
        print("Fusión aplicada. ✅  Revisá el bot y los rankings.")
    else:
        print(
            "Simulación completa. No se escribió nada.\n"
            "Si el detalle de arriba es correcto, repetí con --aplicar."
        )
    _ = total_nuevas


class _Rollback(Exception):
    """Se lanza para revertir la transacción en modo simulación."""


def _condicion_por_clave(tabla, claves, clave_val):
    from sqlalchemy import and_

    condiciones = []
    for k, valor_norm in zip(claves, clave_val):
        # valor_norm puede venir normalizado (tuplas para fechas): reconstruir.
        condiciones.append(tabla.c[k] == _desnormalizar(valor_norm))
    return and_(*condiciones)


def _desnormalizar(valor_norm):
    if isinstance(valor_norm, tuple) and len(valor_norm) == 2:
        etiqueta, iso = valor_norm
        if etiqueta == "dt":
            return datetime.fromisoformat(iso)
        if etiqueta == "d":
            return date.fromisoformat(iso)
    return valor_norm


def calcular_actualizacion(tabla, columnas, claves, valores_backup, estado):
    """Devuelve el dict de columnas a actualizar en una fila de estado.

    * estado == 'backup': pisa todas las columnas no-clave con el backup.
    * estado == 'mayor':  para columnas numéricas toma el valor del backup solo
                          si es mayor (lo resuelve la BD comparando); acá
                          devolvemos las columnas candidatas y la comparación
                          se hace con GREATEST/CASE en la BD.
    """

    cambios: dict = {}
    protegidas = set(claves) | {c.name for c in tabla.primary_key.columns}

    for clave, col in columnas.items():
        if clave in protegidas:
            continue
        valor = valores_backup.get(clave)
        if estado == "backup":
            cambios[clave] = valor
        elif estado == "mayor":
            if isinstance(col.type, (Integer, Float)) and valor is not None:
                # Tomar el mayor entre el valor actual y el del backup. En
                # SQLite el escalar es ``max(a, b)``; en PostgreSQL es
                # ``GREATEST(a, b)`` (``max`` allí es solo agregado).
                if engine.dialect.name == "postgresql":
                    cambios[clave] = func.greatest(tabla.c[clave], valor)
                else:
                    cambios[clave] = func.max(tabla.c[clave], valor)
    return cambios


async def ajustar_secuencias_postgres(conexion, tablas) -> None:
    """En PostgreSQL, deja las secuencias de los PK después del mayor id."""

    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    for tabla in tablas:
        clave = columna_id_autoincremental(tabla)
        if clave is None:
            continue
        await conexion.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{tabla.name}', "
                f"'{clave.name}'), COALESCE(MAX({clave.name}), 1)) "
                f"FROM {tabla.name}"
            )
        )


def respaldar_destino_sqlite() -> None:
    """Copia el archivo SQLite de destino antes de escribir."""

    if not DATABASE_URL.startswith("sqlite"):
        print("Destino no-SQLite: se asume que tenés tu propio respaldo.\n")
        return

    destino = Path(DATABASE)
    if not destino.exists():
        print("El destino SQLite todavía no existe: se creará limpio.\n")
        return

    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    copia = destino.with_name(f"{destino.stem}.antes-de-combinar-{sello}.db")
    shutil.copy2(destino, copia)
    print(f"Respaldo del destino: {copia}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fusiona un backup SQLite con la base actual (definida por "
            "DATABASE_URL/DATABASE). Por defecto solo simula."
        )
    )
    parser.add_argument(
        "origen",
        nargs="?",
        default="naikito-BK2492026.db",
        help="ruta al backup SQLite (default: naikito-BK2492026.db)",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="escribe los cambios (sin esta bandera solo simula)",
    )
    parser.add_argument(
        "--estado",
        choices=("actual", "backup", "mayor"),
        default="actual",
        help=(
            "qué hacer cuando una fila de ESTADO existe en las dos bases: "
            "'actual' conserva la base actual (default), 'backup' la pisa con "
            "el backup, 'mayor' toma el valor numérico más alto."
        ),
    )
    args = parser.parse_args()

    asyncio.run(combinar_seguro(Path(args.origen), args.aplicar, args.estado))


if __name__ == "__main__":
    main()
