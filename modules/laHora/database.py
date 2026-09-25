"""Capa de datos del módulo laHora (SQLAlchemy asíncrono).

Todas las funciones son asíncronas y abren su propia sesión corta.
Sigue la misma convención que el módulo Madrugue para que los servicios
y comandos mantengan un contrato consistente.
"""

from sqlalchemy import Integer, case, delete, func, select

from core.database import crear_sesion, inicializar_db as _inicializar_db_base
from modules.laHora.models import RegistrolaHora


# ============================================================
# INICIALIZACIÓN
# ============================================================

async def inicializar_db():
    """Crea el esquema de laHora (y del resto de los módulos)."""

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
                RegistrolaHora.hora,
                RegistrolaHora.puntos_finales,
            ).where(
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
                RegistrolaHora.fecha == fecha,
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
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
                RegistrolaHora.fecha == fecha,
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
    """Guarda un nuevo registro de laHora."""

    async with crear_sesion() as sesion:
        sesion.add(
            RegistrolaHora(
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
                    func.sum(RegistrolaHora.puntos_finales),
                    0,
                )
            ).where(
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
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

    columna = RegistrolaHora.fecha.asc() if orden == "ASC" else RegistrolaHora.fecha.desc()

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(RegistrolaHora.fecha)
            .where(
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
            )
            .order_by(columna)
        )).all()

    return [fila[0] for fila in filas]


# ============================================================
# TOP gente que dice la hora
# ============================================================

async def obtener_top_gente_que_dice_la_hora(
    guild_id,
    limite=10,
):
    """Devuelve el TOP de un servidor."""

    puntos = func.sum(RegistrolaHora.puntos_finales).label("puntos")

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                RegistrolaHora.user_id,
                RegistrolaHora.username,
                puntos,
            )
            .where(RegistrolaHora.guild_id == guild_id)
            .group_by(
                RegistrolaHora.user_id,
                RegistrolaHora.username,
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
    Devuelve las estadísticas principales de un usuario.

    También devuelve información del último registro:
        hora
        multiplicador
        puntos_base
        puntos_finales

    NOTA: los valores hardcodeados 100, 25 y 5 de los ``case()`` son los
    valores de puntos que usaba Madrugue; acordate de cambiarlos por los
    valores de puntos que definas para laHora cuando tengas la lógica lista.
    """

    donde = (
        RegistrolaHora.guild_id == guild_id,
        RegistrolaHora.user_id == user_id,
    )

    async with crear_sesion() as sesion:

        datos = (await sesion.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(RegistrolaHora.puntos_finales),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (RegistrolaHora.puntos_base == 100, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (RegistrolaHora.puntos_base == 25, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (RegistrolaHora.puntos_base == 5, 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(*donde)
        )).one()

        ultima = (await sesion.execute(
            select(
                RegistrolaHora.hora,
                RegistrolaHora.multiplicador,
                RegistrolaHora.puntos_base,
                RegistrolaHora.puntos_finales,
            )
            .where(*donde)
            .order_by(RegistrolaHora.fecha.desc())
            .limit(1)
        )).first()

        # La hora se guarda como texto HH:MM: se promedian los minutos
        # del día para mostrar la hora promedio a la que dice la hora.
        promedio = (await sesion.execute(
            select(
                func.avg(
                    func.cast(
                        func.substr(RegistrolaHora.hora, 1, 2),
                        Integer,
                    ) * 60
                    + func.cast(
                        func.substr(RegistrolaHora.hora, 4, 2),
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

        gente_que_dice_la_hora = (await sesion.execute(
            select(
                func.count(
                    func.distinct(RegistrolaHora.user_id)
                )
            ).where(RegistrolaHora.guild_id == guild_id)
        )).scalar_one()

        registros = (await sesion.execute(
            select(func.count()).where(
                RegistrolaHora.guild_id == guild_id
            )
        )).scalar_one()

        puntos = (await sesion.execute(
            select(
                func.coalesce(
                    func.sum(RegistrolaHora.puntos_finales),
                    0,
                )
            ).where(RegistrolaHora.guild_id == guild_id)
        )).scalar_one()

    return (
        gente_que_dice_la_hora,
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
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.fecha == fecha,
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
            delete(RegistrolaHora).where(
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
                RegistrolaHora.fecha == fecha,
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
            delete(RegistrolaHora).where(
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
            )
        )
        await sesion.commit()

    return resultado.rowcount


async def eliminar_registros_servidor(
    guild_id,
):
    """Elimina todos los registros de laHora de un servidor."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(RegistrolaHora).where(
                RegistrolaHora.guild_id == guild_id
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
                    func.sum(RegistrolaHora.puntos_finales),
                    0,
                ),
                func.min(RegistrolaHora.fecha),
                func.max(RegistrolaHora.fecha),
            ).where(
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
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
                RegistrolaHora.fecha,
                RegistrolaHora.hora,
                RegistrolaHora.puntos_finales,
            )
            .where(
                RegistrolaHora.guild_id == guild_id,
                RegistrolaHora.user_id == user_id,
            )
            .order_by(RegistrolaHora.fecha.desc())
            .limit(limite)
        )).all()

    return filas