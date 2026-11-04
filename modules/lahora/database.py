"""Persistencia asíncrona de 420 mediante consultas SQLite directas."""

from datetime import date, datetime
import sqlite3

from config import TIMEZONE
from core.database import inicializar_db as _inicializar_db_base
from core.sqlite import conectar


async def inicializar_db():
    await _inicializar_db_base()


def _fecha(valor):
    return valor.isoformat() if isinstance(valor, date) else valor


def _momento(valor):
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=TIMEZONE)
        return valor.isoformat()
    return valor


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
            cantidad = cursor.rowcount
        await conexion.commit()
        return cantidad


async def obtener_registro(guild_id, user_id, fecha, ventana):
    fila = await _uno(
        "SELECT momento, puntos_finales FROM lahora_registros "
        "WHERE guild_id = ? AND user_id = ? AND fecha = ? AND ventana = ?",
        (guild_id, user_id, _fecha(fecha), ventana),
    )
    return (datetime.fromisoformat(fila[0]), fila[1]) if fila else None


async def contar_registros_ventana(guild_id, fecha, ventana):
    return (await _uno(
        "SELECT COUNT(*) FROM lahora_registros WHERE guild_id = ? AND fecha = ? AND ventana = ?",
        (guild_id, _fecha(fecha), ventana),
    ))[0]


async def guardar_registro(**datos):
    columnas = ("guild_id", "user_id", "username", "fecha", "ventana", "momento",
                "segundos", "posicion", "puntos_base", "multiplicador",
                "bonus_posicion", "puntos_finales", "mensaje_id")
    datos = {**datos}
    datos.setdefault("bonus_posicion", 0)
    datos.setdefault("mensaje_id", None)
    datos["fecha"] = _fecha(datos["fecha"])
    datos["momento"] = _momento(datos["momento"])
    try:
        await _escribir(
            f"INSERT INTO lahora_registros ({', '.join(columnas)}) "
            f"VALUES ({', '.join('?' for _ in columnas)})",
            tuple(datos[columna] for columna in columnas),
        )
    except sqlite3.IntegrityError:
        return False
    return True


async def obtener_resumen_usuario(guild_id, user_id):
    return await _uno(
        "SELECT COALESCE(SUM(puntos_finales), 0), COUNT(*), "
        "COALESCE(SUM(CASE WHEN posicion = 1 THEN 1 ELSE 0 END), 0), MIN(segundos) "
        "FROM lahora_registros WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )


async def obtener_fechas_registradas(guild_id, user_id):
    filas = await _todos(
        "SELECT DISTINCT fecha FROM lahora_registros WHERE guild_id = ? AND user_id = ? ORDER BY fecha",
        (guild_id, user_id),
    )
    return [date.fromisoformat(fila[0]) for fila in filas]


async def obtener_top(guild_id, limite=10):
    return await _todos(
        "SELECT a.user_id, r.username, a.puntos, a.cantidad FROM "
        "(SELECT user_id, SUM(puntos_finales) AS puntos, COUNT(*) AS cantidad, "
        "MAX(id) AS ultimo_id FROM lahora_registros WHERE guild_id = ? GROUP BY user_id) a "
        "JOIN lahora_registros r ON r.id = a.ultimo_id "
        "ORDER BY a.puntos DESC, a.user_id LIMIT ?", (guild_id, limite),
    )


async def obtener_registros_del_dia(guild_id, fecha):
    return await _todos(
        "SELECT ventana, posicion, username, segundos, puntos_finales FROM lahora_registros "
        "WHERE guild_id = ? AND fecha = ? ORDER BY ventana, posicion", (guild_id, _fecha(fecha)),
    )


async def eliminar_registros_usuario(guild_id, user_id):
    return await _escribir(
        "DELETE FROM lahora_registros WHERE guild_id = ? AND user_id = ?", (guild_id, user_id),
    )


async def obtener_registros_usuario(guild_id, user_id, limite=20):
    filas = await _todos(
        "SELECT fecha, ventana, segundos, posicion, puntos_finales, mensaje_id "
        "FROM lahora_registros WHERE guild_id = ? AND user_id = ? "
        "ORDER BY fecha DESC, ventana DESC LIMIT ?", (guild_id, user_id, limite),
    )
    return [(date.fromisoformat(f[0]), *f[1:]) for f in filas]


async def obtener_detalle_registro(guild_id, user_id, fecha, ventana):
    return await _uno(
        "SELECT segundos, posicion, puntos_finales FROM lahora_registros "
        "WHERE guild_id = ? AND user_id = ? AND fecha = ? AND ventana = ?",
        (guild_id, user_id, _fecha(fecha), ventana),
    )


async def obtener_ventanas_usuario(guild_id, user_id, fecha=None):
    sql = "SELECT DISTINCT fecha, ventana FROM lahora_registros WHERE guild_id = ? AND user_id = ?"
    parametros = (guild_id, user_id)
    if fecha is not None:
        sql += " AND fecha = ?"
        parametros += (_fecha(fecha),)
    filas = await _todos(sql, parametros)
    return [(date.fromisoformat(f[0]), f[1]) for f in filas]


async def eliminar_registros(guild_id, user_id, fecha, ventana=None):
    sql = "DELETE FROM lahora_registros WHERE guild_id = ? AND user_id = ? AND fecha = ?"
    parametros = (guild_id, user_id, _fecha(fecha))
    if ventana is not None:
        sql += " AND ventana = ?"
        parametros += (ventana,)
    return await _escribir(sql, parametros)


async def eliminar_registros_servidor(guild_id):
    return await _escribir("DELETE FROM lahora_registros WHERE guild_id = ?", (guild_id,))


async def obtener_estadisticas_servidor(guild_id):
    return await _uno(
        "SELECT COUNT(DISTINCT user_id), COUNT(*), COALESCE(SUM(puntos_finales), 0) "
        "FROM lahora_registros WHERE guild_id = ?", (guild_id,),
    )


async def obtener_ultimo_chequeo(canal_id):
    fila = await _uno("SELECT ultimo_chequeo FROM lahora_sincronizacion WHERE canal_id = ?", (canal_id,))
    return datetime.fromisoformat(fila[0]) if fila else None


async def guardar_ultimo_chequeo(guild_id, canal_id, momento):
    await _escribir(
        "INSERT INTO lahora_sincronizacion (canal_id, guild_id, ultimo_chequeo) VALUES (?, ?, ?) "
        "ON CONFLICT(canal_id) DO UPDATE SET guild_id = excluded.guild_id, "
        "ultimo_chequeo = excluded.ultimo_chequeo", (canal_id, guild_id, _momento(momento)),
    )


async def recalcular_ventana(guild_id, fecha, ventana, calcular_puntos):
    """Reordena y recalcula una ventana dentro de una única transacción."""
    async with conectar() as conexion:
        await conexion.execute("BEGIN IMMEDIATE")
        async with conexion.execute(
            "SELECT id, momento, segundos FROM lahora_registros "
            "WHERE guild_id = ? AND fecha = ? AND ventana = ?",
            (guild_id, _fecha(fecha), ventana),
        ) as cursor:
            registros = await cursor.fetchall()
        registros.sort(key=lambda r: (datetime.fromisoformat(r[1]), r[0]))
        for posicion, (registro_id, _instante, segundos) in enumerate(registros, 1):
            base, multiplicador, bonus, finales = calcular_puntos(segundos, posicion)
            await conexion.execute(
                "UPDATE lahora_registros SET posicion = ?, puntos_base = ?, "
                "multiplicador = ?, bonus_posicion = ?, puntos_finales = ? WHERE id = ?",
                (posicion, base, multiplicador, bonus, finales, registro_id),
            )
        await conexion.commit()
    return len(registros)
