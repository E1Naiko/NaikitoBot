"""Persistencia asíncrona de SeptSinFP con SQLite directo."""

from datetime import date, datetime

from config import TIMEZONE
from core.database import inicializar_db as _inicializar_db_base
from core.sqlite import conectar


async def inicializar_db():
    await _inicializar_db_base()


def _iso(valor):
    if isinstance(valor, datetime) and valor.tzinfo is None:
        valor = valor.replace(tzinfo=TIMEZONE)
    return valor.isoformat() if isinstance(valor, (date, datetime)) else valor


def _desafio(fila):
    if fila is None:
        return None
    return (*fila[:3], date.fromisoformat(fila[3]), date.fromisoformat(fila[4]), *fila[5:])


def _participante(fila, con_desafio=False):
    if fila is None:
        return None
    datos = list(fila)
    offset = 1 if con_desafio else 0
    datos[2 + offset] = datetime.fromisoformat(datos[2 + offset])
    if datos[4 + offset] is not None:
        datos[4 + offset] = date.fromisoformat(datos[4 + offset])
    return tuple(datos)


async def _uno(sql, parametros=()):
    async with conectar() as conexion:
        async with conexion.execute(sql, parametros) as cursor:
            return await cursor.fetchone()


async def _todos(sql, parametros=()):
    async with conectar() as conexion:
        async with conexion.execute(sql, parametros) as cursor:
            return await cursor.fetchall()


async def _escribir(sql, parametros=()):
    async with conectar() as conexion:
        async with conexion.execute(sql, parametros) as cursor:
            resultado = (cursor.rowcount, cursor.lastrowid)
        await conexion.commit()
        return resultado


async def crear_desafio(guild_id, nombre, fecha_inicio, fecha_fin, canal_id):
    _, identificador = await _escribir(
        "INSERT INTO ssf_desafios (guild_id,nombre,fecha_inicio,fecha_fin,canal_id,activo) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (guild_id, nombre, _iso(fecha_inicio), _iso(fecha_fin), canal_id),
    )
    return identificador


_COLUMNAS_DESAFIO = "id, guild_id, nombre, fecha_inicio, fecha_fin, canal_id, activo"


async def obtener_desafio_activo(guild_id):
    return _desafio(await _uno(
        f"SELECT {_COLUMNAS_DESAFIO} FROM ssf_desafios WHERE guild_id = ? AND activo = 1 "
        "ORDER BY id DESC LIMIT 1", (guild_id,),
    ))


async def obtener_ultimo_desafio(guild_id):
    return _desafio(await _uno(
        f"SELECT {_COLUMNAS_DESAFIO} FROM ssf_desafios WHERE guild_id = ? ORDER BY id DESC LIMIT 1",
        (guild_id,),
    ))


async def obtener_desafio_por_id(desafio_id):
    return _desafio(await _uno(
        f"SELECT {_COLUMNAS_DESAFIO} FROM ssf_desafios WHERE id = ?", (desafio_id,),
    ))


async def cerrar_desafio(desafio_id):
    return (await _escribir("UPDATE ssf_desafios SET activo = 0 WHERE id = ?", (desafio_id,)))[0]


async def registrar_participante(desafio_id, user_id, username, fecha_registro):
    await _escribir(
        "INSERT INTO ssf_participantes (desafio_id,user_id,username,fecha_registro) VALUES (?,?,?,?)",
        (desafio_id, user_id, username, _iso(fecha_registro)),
    )


async def obtener_participante(desafio_id, user_id):
    return _participante(await _uno(
        "SELECT desafio_id,user_id,username,fecha_registro,eliminado,fecha_eliminacion,"
        "racha_actual,mejor_racha FROM ssf_participantes WHERE desafio_id = ? AND user_id = ?",
        (desafio_id, user_id),
    ), con_desafio=True)


async def actualizar_participante(desafio_id, user_id, racha_actual, mejor_racha):
    await _escribir(
        "UPDATE ssf_participantes SET racha_actual = ?, mejor_racha = ? WHERE desafio_id = ? AND user_id = ?",
        (racha_actual, mejor_racha, desafio_id, user_id),
    )


async def eliminar_participante(desafio_id, user_id, fecha_eliminacion):
    await _escribir(
        "UPDATE ssf_participantes SET eliminado = 1, fecha_eliminacion = ? WHERE desafio_id = ? AND user_id = ?",
        (_iso(fecha_eliminacion), desafio_id, user_id),
    )


async def obtener_participantes(desafio_id):
    filas = await _todos(
        "SELECT user_id,username,fecha_registro,eliminado,fecha_eliminacion,racha_actual,mejor_racha "
        "FROM ssf_participantes WHERE desafio_id = ? ORDER BY fecha_registro", (desafio_id,),
    )
    return [_participante(fila) for fila in filas]


async def guardar_registro(desafio_id, user_id, fecha, hora):
    await _escribir(
        "INSERT INTO ssf_registros (desafio_id,user_id,fecha,hora) VALUES (?,?,?,?)",
        (desafio_id, user_id, _iso(fecha), hora),
    )


async def tiene_registro(desafio_id, user_id, fecha):
    return await _uno(
        "SELECT 1 FROM ssf_registros WHERE desafio_id = ? AND user_id = ? AND fecha = ?",
        (desafio_id, user_id, _iso(fecha)),
    ) is not None


async def obtener_registros_usuario(desafio_id, user_id):
    filas = await _todos(
        "SELECT fecha FROM ssf_registros WHERE desafio_id = ? AND user_id = ? ORDER BY fecha",
        (desafio_id, user_id),
    )
    return [(date.fromisoformat(fila[0]),) for fila in filas]


async def eliminar_registro(desafio_id, user_id, fecha):
    return (await _escribir(
        "DELETE FROM ssf_registros WHERE desafio_id = ? AND user_id = ? AND fecha = ?",
        (desafio_id, user_id, _iso(fecha)),
    ))[0]


async def obtener_estadisticas_desafio(desafio_id):
    return await _uno(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN eliminado = 0 THEN 1 ELSE 0 END), 0), "
        "COALESCE(SUM(CASE WHEN eliminado = 1 THEN 1 ELSE 0 END), 0) "
        "FROM ssf_participantes WHERE desafio_id = ?", (desafio_id,),
    )


async def reactivar_participante(desafio_id, user_id):
    await _escribir(
        "UPDATE ssf_participantes SET eliminado = 0, fecha_eliminacion = NULL WHERE desafio_id = ? AND user_id = ?",
        (desafio_id, user_id),
    )


async def obtener_desafios_activos():
    filas = await _todos(f"SELECT {_COLUMNAS_DESAFIO} FROM ssf_desafios WHERE activo = 1 ORDER BY id")
    return [_desafio(fila) for fila in filas]


async def obtener_ultima_revision_ssf(desafio_id):
    fila = await _uno("SELECT ultima_fecha FROM ssf_revisiones WHERE desafio_id = ?", (desafio_id,))
    return date.fromisoformat(fila[0]) if fila else None


async def guardar_ultima_revision_ssf(desafio_id, fecha):
    await _escribir(
        "INSERT INTO ssf_revisiones (desafio_id, ultima_fecha) VALUES (?, ?) "
        "ON CONFLICT(desafio_id) DO UPDATE SET ultima_fecha = excluded.ultima_fecha",
        (desafio_id, _iso(fecha)),
    )


async def obtener_ranking_final(desafio_id):
    return await _todos(
        "SELECT user_id,username,eliminado,racha_actual,mejor_racha FROM ssf_participantes "
        "WHERE desafio_id = ? ORDER BY eliminado, mejor_racha DESC, lower(username)", (desafio_id,),
    )


async def marcar_desafio_cerrado(desafio_id):
    return (await _escribir(
        "UPDATE ssf_desafios SET activo = 0 WHERE id = ? AND activo = 1", (desafio_id,),
    ))[0]
