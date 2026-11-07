"""Persistencia asíncrona de las sanciones por trampa en SQLite."""

from datetime import datetime

from core.database import inicializar_db as _inicializar_db_base
from core.sqlite import conectar

from modules.sanciones.logic import (
    ESTADO_ACTIVA,
    ESTADO_LEVANTADA,
    ESTADO_VENCIDA,
    como_local,
    ahora_local,
    esta_vigente,
    estado_sancion,
)

_COLUMNAS = (
    "id, guild_id, user_id, minijuego, motivo, creada_en, expira_en, "
    "levantada_en, levantada_por, creada_por"
)


async def inicializar_db():
    """Crea el esquema completo, incluida la tabla ``sanciones``."""

    await _inicializar_db_base()


def _iso(valor):
    normalizado = como_local(valor)
    return normalizado.isoformat() if normalizado is not None else None


def _momento(valor):
    """Texto ISO de la base -> ``datetime`` con zona (o el valor original)."""

    if isinstance(valor, str):
        return como_local(datetime.fromisoformat(valor))

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


def _sancion(fila):
    """Fila cruda -> diccionario con fechas y estado ya resueltos."""

    if fila is None:
        return None

    datos = dict(zip(
        (
            "id",
            "guild_id",
            "user_id",
            "minijuego",
            "motivo",
            "creada_en",
            "expira_en",
            "levantada_en",
            "levantada_por",
            "creada_por",
        ),
        fila,
    ))

    for columna in ("creada_en", "expira_en", "levantada_en"):
        datos[columna] = _momento(datos[columna])

    datos["estado"] = estado_sancion(
        datos["expira_en"],
        datos["levantada_en"],
    )
    datos["vigente"] = datos["estado"] == ESTADO_ACTIVA

    return datos


def _vigente(fila, momento=None):
    """Fila ``(minijuego, expira_en)`` vigente en ``momento``, o ``None``."""

    if fila is None:
        return None

    minijuego, expira_en = fila
    expira_en = _momento(expira_en)

    return (minijuego, expira_en) if esta_vigente(expira_en, momento) else None


async def obtener_sancion(guild_id, user_id, minijuego):
    """La sanción de ese usuario en ese minijuego, vigente o no."""

    return _sancion(await _uno(
        f"SELECT {_COLUMNAS} FROM sanciones "
        "WHERE guild_id = ? AND user_id = ? AND minijuego = ?",
        (guild_id, user_id, minijuego),
    ))


async def sancion_vigente(guild_id, user_id, minijuego, momento=None):
    """Devuelve el vencimiento si el usuario está sancionado ahora.

    El resultado distingue los dos casos que importan al jugador:
    ``(minijuego, None)`` es un ban permanente y ``(minijuego, datetime)``
    vence en esa fecha. ``None`` significa que puede participar.
    """

    fila = await _uno(
        "SELECT minijuego, expira_en FROM sanciones "
        "WHERE guild_id = ? AND user_id = ? AND minijuego = ? "
        "AND levantada_en IS NULL",
        (guild_id, user_id, minijuego),
    )

    return _vigente(fila, momento)


async def sanciones_vigentes(guild_id, user_id, momento=None):
    """Todas las sanciones vigentes del usuario en el servidor."""

    filas = await _todos(
        "SELECT minijuego, expira_en FROM sanciones "
        "WHERE guild_id = ? AND user_id = ? AND levantada_en IS NULL",
        (guild_id, user_id),
    )

    vigentes = (_vigente(fila, momento) for fila in filas)

    return sorted(
        (sancion for sancion in vigentes if sancion is not None),
        key=lambda sancion: sancion[0],
    )


async def usuarios_vigentes(guild_id, minijuego, momento=None):
    """IDs sancionados en un minijuego, útil para avisos masivos."""

    filas = await _todos(
        "SELECT user_id, expira_en FROM sanciones "
        "WHERE guild_id = ? AND minijuego = ? AND levantada_en IS NULL",
        (guild_id, minijuego),
    )

    return [
        user_id
        for user_id, expira_en in filas
        if esta_vigente(_momento(expira_en), momento)
    ]


async def listar_sanciones(guild_id, minijuego=None, incluir_historicas=False, momento=None):
    """Sanciones del servidor, opcionalmente filtradas por minijuego."""

    sql = f"SELECT {_COLUMNAS} FROM sanciones WHERE guild_id = ?"
    parametros = [guild_id]

    if minijuego is not None:
        sql += " AND minijuego = ?"
        parametros.append(minijuego)

    sql += " ORDER BY user_id, minijuego"

    sanciones = [
        _sancion(fila)
        for fila in await _todos(sql, tuple(parametros))
    ]

    if incluir_historicas:
        return sanciones

    return [
        sancion
        for sancion in sanciones
        if estado_sancion(
            sancion["expira_en"],
            sancion["levantada_en"],
            momento,
        ) == ESTADO_ACTIVA
    ]


async def guardar_sancion(
    guild_id,
    user_id,
    minijuego,
    motivo,
    expira_en=None,
    creada_en=None,
    creada_por=None,
):
    """Crea o reemplaza la sanción de ese usuario en ese minijuego.

    Una sanción nueva pisa a la anterior (aunque estuviera vencida o
    levantada): el temporizador que vale es el último que decidió un admin.
    """

    ahora = como_local(creada_en) if creada_en is not None else ahora_local()

    async with conectar() as conexion:
        await conexion.execute(
            "INSERT INTO sanciones (guild_id, user_id, minijuego, motivo, "
            "creada_en, expira_en, levantada_en, levantada_por, creada_por) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?) "
            "ON CONFLICT(guild_id, user_id, minijuego) DO UPDATE SET "
            "motivo = excluded.motivo, creada_en = excluded.creada_en, "
            "expira_en = excluded.expira_en, levantada_en = NULL, "
            "levantada_por = NULL, creada_por = excluded.creada_por",
            (
                guild_id,
                user_id,
                minijuego,
                motivo,
                ahora.isoformat(),
                _iso(expira_en),
                creada_por,
            ),
        )
        await conexion.commit()

    return await obtener_sancion(guild_id, user_id, minijuego)


async def levantar_sancion(guild_id, user_id, minijuego, levantada_por=None, momento=None):
    """Marca la sanción como levantada a mano. Devuelve ``False`` si no había."""

    cantidad = await _escribir(
        "UPDATE sanciones SET levantada_en = ?, levantada_por = ? "
        "WHERE guild_id = ? AND user_id = ? AND minijuego = ? "
        "AND levantada_en IS NULL",
        (
            _iso(momento or ahora_local()),
            levantada_por,
            guild_id,
            user_id,
            minijuego,
        ),
    )

    return cantidad > 0


async def eliminar_sancion(guild_id, user_id, minijuego):
    """Borra la fila (para pruebas y limpieza manual)."""

    return await _escribir(
        "DELETE FROM sanciones WHERE guild_id = ? AND user_id = ? AND minijuego = ?",
        (guild_id, user_id, minijuego),
    ) > 0


async def limpiar_vencidas(guild_id=None, momento=None):
    """Borra las sanciones que ya vencieron y nadie levantó.

    No hace falta para bloquear (las consultas ya miran el vencimiento); es
    mantenimiento para que la tabla no crezca con bans de años atrás.
    """

    sql = "DELETE FROM sanciones WHERE levantada_en IS NULL AND expira_en IS NOT NULL AND expira_en <= ?"
    parametros = [_iso(momento or ahora_local())]

    if guild_id is not None:
        sql += " AND guild_id = ?"
        parametros.append(guild_id)

    return await _escribir(sql, tuple(parametros))



__all__ = [
    "ESTADO_ACTIVA",
    "ESTADO_LEVANTADA",
    "ESTADO_VENCIDA",
    "eliminar_sancion",
    "guardar_sancion",
    "inicializar_db",
    "levantar_sancion",
    "limpiar_vencidas",
    "listar_sanciones",
    "obtener_sancion",
    "sancion_vigente",
    "sanciones_vigentes",
    "usuarios_vigentes",
]
