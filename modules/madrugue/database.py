"""Consultas SQLite asíncronas para Madrugue.

Las funciones conservan el contrato de la capa anterior: las fechas devueltas
son objetos ``date`` y las escrituras se confirman antes de retornar.
"""

from datetime import date

from core.database import inicializar_db as _inicializar_db_base
from core.sqlite import conectar
from core.temporada import inicio_temporada


async def inicializar_db():
    """Crea el esquema de todos los módulos durante la transición."""
    await _inicializar_db_base()


def _fecha(valor):
    return valor.isoformat() if isinstance(valor, date) else valor


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


async def obtener_registro_del_dia(guild_id, user_id, fecha):
    return await _uno(
        "SELECT hora, puntos_finales FROM registros "
        "WHERE guild_id = ? AND user_id = ? AND fecha = ?",
        (guild_id, user_id, _fecha(fecha)),
    )


async def tiene_registro(guild_id, user_id, fecha):
    return await obtener_registro_del_dia(guild_id, user_id, fecha) is not None


async def guardar_registro(
    guild_id, user_id, username, fecha, hora, puntos_base, multiplicador,
    puntos_finales,
):
    await _escribir(
        "INSERT INTO registros (guild_id, user_id, username, fecha, hora, "
        "puntos_base, multiplicador, puntos_finales) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (guild_id, user_id, username, _fecha(fecha), hora, puntos_base,
         multiplicador, puntos_finales),
    )


async def obtener_total_puntos(guild_id, user_id):
    fila = await _uno(
        "SELECT COALESCE(SUM(puntos_finales), 0) FROM registros "
        "WHERE guild_id = ? AND user_id = ?", (guild_id, user_id),
    )
    return fila[0]


async def obtener_fechas_registradas(guild_id, user_id, orden="DESC"):
    if orden not in ("ASC", "DESC"):
        raise ValueError("El orden debe ser ASC o DESC.")
    filas = await _todos(
        f"SELECT fecha FROM registros WHERE guild_id = ? AND user_id = ? ORDER BY fecha {orden}",
        (guild_id, user_id),
    )
    return [date.fromisoformat(fila[0]) for fila in filas]


async def obtener_top_madrugadores(guild_id, limite=10):
    return await _todos(
        "SELECT user_id, username, SUM(puntos_finales) AS puntos FROM registros "
        "WHERE guild_id = ? GROUP BY user_id, username ORDER BY puntos DESC LIMIT ?",
        (guild_id, limite),
    )


async def obtener_estadisticas(guild_id, user_id):
    parametros = (guild_id, user_id)
    async with conectar() as conexion:
        async with conexion.execute(
            "SELECT COUNT(*), COALESCE(SUM(puntos_finales), 0), "
            "COALESCE(SUM(CASE WHEN puntos_base = 100 THEN 1 ELSE 0 END), 0), "
            "COALESCE(SUM(CASE WHEN puntos_base = 25 THEN 1 ELSE 0 END), 0), "
            "COALESCE(SUM(CASE WHEN puntos_base = 5 THEN 1 ELSE 0 END), 0) "
            "FROM registros WHERE guild_id = ? AND user_id = ?", parametros,
        ) as cursor:
            datos = await cursor.fetchone()
        async with conexion.execute(
            "SELECT hora, multiplicador, puntos_base, puntos_finales FROM registros "
            "WHERE guild_id = ? AND user_id = ? ORDER BY fecha DESC LIMIT 1", parametros,
        ) as cursor:
            ultima = await cursor.fetchone()
        async with conexion.execute(
            "SELECT AVG(CAST(SUBSTR(hora, 1, 2) AS INTEGER) * 60 + "
            "CAST(SUBSTR(hora, 4, 2) AS INTEGER)) FROM registros "
            "WHERE guild_id = ? AND user_id = ?", parametros,
        ) as cursor:
            promedio = (await cursor.fetchone())[0]
    return datos, ultima, promedio


async def obtener_estadisticas_servidor(guild_id):
    return await _uno(
        "SELECT COUNT(DISTINCT user_id), COUNT(*), COALESCE(SUM(puntos_finales), 0) "
        "FROM registros WHERE guild_id = ?", (guild_id,),
    )


async def obtener_registros_de_hoy(guild_id, fecha):
    fila = await _uno(
        "SELECT COUNT(*) FROM registros WHERE guild_id = ? AND fecha = ?",
        (guild_id, _fecha(fecha)),
    )
    return fila[0]


async def eliminar_registro_del_dia(guild_id, user_id, fecha):
    return await _escribir(
        "DELETE FROM registros WHERE guild_id = ? AND user_id = ? AND fecha = ?",
        (guild_id, user_id, _fecha(fecha)),
    )


async def eliminar_registros_usuario(guild_id, user_id):
    return await _escribir(
        "DELETE FROM registros WHERE guild_id = ? AND user_id = ?", (guild_id, user_id),
    )


async def eliminar_registros_servidor(guild_id):
    return await _escribir("DELETE FROM registros WHERE guild_id = ?", (guild_id,))


async def obtener_resumen_usuario(guild_id, user_id):
    cantidad, puntos, primera, ultima = await _uno(
        "SELECT COUNT(*), COALESCE(SUM(puntos_finales), 0), MIN(fecha), MAX(fecha) "
        "FROM registros WHERE guild_id = ? AND user_id = ?", (guild_id, user_id),
    )
    return (cantidad, puntos, date.fromisoformat(primera) if primera else None,
            date.fromisoformat(ultima) if ultima else None)


async def obtener_registro_del_dia_admin(guild_id, user_id, fecha):
    return await obtener_registro_del_dia(guild_id, user_id, fecha)


async def obtener_ultimos_registros(guild_id, user_id, limite=8):
    filas = await _todos(
        "SELECT fecha, hora, puntos_finales FROM registros "
        "WHERE guild_id = ? AND user_id = ? ORDER BY fecha DESC LIMIT ?",
        (guild_id, user_id, limite),
    )
    return [(date.fromisoformat(fecha), hora, puntos) for fecha, hora, puntos in filas]


async def importar_registros(guild_id, registros):
    """Importa filas de Madrugue de forma atómica e idempotente.

    Cada fila contiene user_id, username, fecha, hora, puntos_base,
    multiplicador y puntos_finales. Un conflicto revierte toda la operación.
    """
    nuevos = repetidos = 0
    async with conectar() as conexion:
        await conexion.execute("BEGIN IMMEDIATE")
        for user_id, username, fecha, hora, base, multiplicador, puntos in registros:
            fecha = _fecha(fecha)
            if fecha < inicio_temporada().date().isoformat():
                raise ValueError(f"{fecha} es anterior al inicio de la temporada actual")
            async with conexion.execute(
                "SELECT username, hora, puntos_base, multiplicador, puntos_finales "
                "FROM registros WHERE guild_id = ? AND user_id = ? AND fecha = ?",
                (guild_id, user_id, fecha),
            ) as cursor:
                existente = await cursor.fetchone()
            esperados = (username, hora, base, multiplicador, puntos)
            if existente is not None:
                if existente != esperados:
                    raise ValueError(
                        f"conflicto con el registro existente de {user_id} del {fecha}"
                    )
                repetidos += 1
                continue
            await conexion.execute(
                "INSERT INTO registros (guild_id, user_id, username, fecha, hora, "
                "puntos_base, multiplicador, puntos_finales) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (guild_id, user_id, username, fecha, hora, base, multiplicador, puntos),
            )
            nuevos += 1
        await conexion.commit()
    return nuevos, repetidos
