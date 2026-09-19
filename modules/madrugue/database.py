"""Capa de datos del módulo Madrugue (SQLAlchemy asíncrono).

Todas las funciones son asíncronas y abren su propia sesión corta.
Devuelven tuplas con la misma forma que tenía la capa SQLite original,
para que los servicios y comandos no cambien de contrato.
"""

from sqlalchemy import Integer, case, delete, func, select

from core.database import crear_sesion, inicializar_db as _inicializar_db_base
from modules.madrugue.models import RegistroMadrugue


# ============================================================
# INICIALIZACIÓN
# ============================================================

async def inicializar_db():
    """Crea el esquema de Madrugue (y del resto de los módulos)."""

    await _inicializar_db_base()


# ============================================================
# REGISTROS
# ============================================================

async def obtener_registro_del_dia(
    guild_id,
    user_id,
    fecha,
):
    """Obtiene el registro de un usuario para una fecha."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                RegistroMadrugue.hora,
                RegistroMadrugue.puntos_finales,
            ).where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
                RegistroMadrugue.fecha == fecha,
            )
        )).first()

    return fila


async def tiene_registro(
    guild_id,
    user_id,
    fecha,
):
    """Indica si el usuario tiene un registro para una fecha."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(1).where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
                RegistroMadrugue.fecha == fecha,
            )
        )).first()

    return fila is not None


async def guardar_registro(
    guild_id,
    user_id,
    username,
    fecha,
    hora,
    puntos_base,
    multiplicador,
    puntos_finales,
):
    """Guarda una nueva madrugada."""

    async with crear_sesion() as sesion:
        sesion.add(
            RegistroMadrugue(
                guild_id=guild_id,
                user_id=user_id,
                username=username,
                fecha=fecha,
                hora=hora,
                puntos_base=puntos_base,
                multiplicador=multiplicador,
                puntos_finales=puntos_finales,
            )
        )
        await sesion.commit()


# ============================================================
# PUNTOS
# ============================================================

async def obtener_total_puntos(
    guild_id,
    user_id,
):
    """Devuelve el total de puntos de un usuario en un servidor."""

    async with crear_sesion() as sesion:
        total = (await sesion.execute(
            select(
                func.coalesce(
                    func.sum(RegistroMadrugue.puntos_finales),
                    0,
                )
            ).where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
            )
        )).scalar_one()

    return total


# ============================================================
# FECHAS
# ============================================================

async def obtener_fechas_registradas(
    guild_id,
    user_id,
    orden="DESC",
):
    """Devuelve las fechas registradas de un usuario como objetos date."""

    if orden not in ("ASC", "DESC"):
        raise ValueError(
            "El orden debe ser ASC o DESC."
        )

    columna = RegistroMadrugue.fecha.asc() if orden == "ASC" else RegistroMadrugue.fecha.desc()

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(RegistroMadrugue.fecha)
            .where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
            )
            .order_by(columna)
        )).all()

    return [fila[0] for fila in filas]


# ============================================================
# TOP MADRUGADORES
# ============================================================

async def obtener_top_madrugadores(
    guild_id,
    limite=10,
):
    """Devuelve el TOP de un servidor."""

    puntos = func.sum(RegistroMadrugue.puntos_finales).label("puntos")

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                RegistroMadrugue.user_id,
                RegistroMadrugue.username,
                puntos,
            )
            .where(RegistroMadrugue.guild_id == guild_id)
            .group_by(
                RegistroMadrugue.user_id,
                RegistroMadrugue.username,
            )
            .order_by(puntos.desc())
            .limit(limite)
        )).all()

    return filas


# ============================================================
# ESTADÍSTICAS
# ============================================================

async def obtener_estadisticas(
    guild_id,
    user_id,
):
    """
    Devuelve las estadísticas principales.

    También devuelve información de la última madrugada:
        hora
        multiplicador
        puntos_base
        puntos_finales
    """

    donde = (
        RegistroMadrugue.guild_id == guild_id,
        RegistroMadrugue.user_id == user_id,
    )

    async with crear_sesion() as sesion:

        datos = (await sesion.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(RegistroMadrugue.puntos_finales),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (RegistroMadrugue.puntos_base == 100, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (RegistroMadrugue.puntos_base == 25, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (RegistroMadrugue.puntos_base == 5, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(*donde)
        )).one()

        ultima = (await sesion.execute(
            select(
                RegistroMadrugue.hora,
                RegistroMadrugue.multiplicador,
                RegistroMadrugue.puntos_base,
                RegistroMadrugue.puntos_finales,
            )
            .where(*donde)
            .order_by(RegistroMadrugue.fecha.desc())
            .limit(1)
        )).first()

        # La hora se guarda como texto HH:MM: se promedian los minutos
        # del día, igual que en la versión SQLite.
        promedio = (await sesion.execute(
            select(
                func.avg(
                    func.cast(
                        func.substr(RegistroMadrugue.hora, 1, 2),
                        Integer,
                    ) * 60
                    + func.cast(
                        func.substr(RegistroMadrugue.hora, 4, 2),
                        Integer,
                    )
                )
            ).where(*donde)
        )).scalar_one()

    return datos, ultima, promedio


# ============================================================
# ADMINISTRACIÓN
# ============================================================

async def obtener_estadisticas_servidor(
    guild_id,
):
    """Devuelve estadísticas generales de un servidor."""

    async with crear_sesion() as sesion:

        madrugadores = (await sesion.execute(
            select(
                func.count(
                    func.distinct(RegistroMadrugue.user_id)
                )
            ).where(RegistroMadrugue.guild_id == guild_id)
        )).scalar_one()

        registros = (await sesion.execute(
            select(func.count()).where(
                RegistroMadrugue.guild_id == guild_id
            )
        )).scalar_one()

        puntos = (await sesion.execute(
            select(
                func.coalesce(
                    func.sum(RegistroMadrugue.puntos_finales),
                    0,
                )
            ).where(RegistroMadrugue.guild_id == guild_id)
        )).scalar_one()

    return (
        madrugadores,
        registros,
        puntos,
    )


async def obtener_registros_de_hoy(
    guild_id,
    fecha,
):
    """Devuelve la cantidad de registros de un día."""

    async with crear_sesion() as sesion:
        cantidad = (await sesion.execute(
            select(func.count()).where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.fecha == fecha,
            )
        )).scalar_one()

    return cantidad


async def eliminar_registro_del_dia(
    guild_id,
    user_id,
    fecha,
):
    """Elimina el registro de un usuario para una fecha."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(RegistroMadrugue).where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
                RegistroMadrugue.fecha == fecha,
            )
        )
        await sesion.commit()

    return resultado.rowcount


async def eliminar_registros_usuario(
    guild_id,
    user_id,
):
    """Elimina todos los registros de un usuario."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(RegistroMadrugue).where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
            )
        )
        await sesion.commit()

    return resultado.rowcount


async def eliminar_registros_servidor(
    guild_id,
):
    """Elimina todos los registros de Madrugue de un servidor."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(RegistroMadrugue).where(
                RegistroMadrugue.guild_id == guild_id
            )
        )
        await sesion.commit()

    return resultado.rowcount


async def obtener_resumen_usuario(
    guild_id,
    user_id,
):
    """Obtiene un resumen de los registros de un usuario."""

    async with crear_sesion() as sesion:
        resultado = (await sesion.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(RegistroMadrugue.puntos_finales),
                    0,
                ),
                func.min(RegistroMadrugue.fecha),
                func.max(RegistroMadrugue.fecha),
            ).where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
            )
        )).one()

    return resultado


async def obtener_registro_del_dia_admin(
    guild_id,
    user_id,
    fecha,
):
    """Obtiene el registro del usuario para una fecha."""

    return await obtener_registro_del_dia(
        guild_id,
        user_id,
        fecha,
    )


async def obtener_ultimos_registros(
    guild_id,
    user_id,
    limite=8,
):
    """Obtiene los últimos registros de un usuario, del más reciente al más viejo."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                RegistroMadrugue.fecha,
                RegistroMadrugue.hora,
                RegistroMadrugue.puntos_finales,
            )
            .where(
                RegistroMadrugue.guild_id == guild_id,
                RegistroMadrugue.user_id == user_id,
            )
            .order_by(RegistroMadrugue.fecha.desc())
            .limit(limite)
        )).all()

    return filas
