"""Capa de datos del módulo laHora (SQLAlchemy asíncrono).

Todas las funciones son asíncronas y abren su propia sesión corta,
con la misma convención que el módulo Madrugue.
"""

from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError

from core.database import crear_sesion, inicializar_db as _inicializar_db_base
from modules.lahora.models import RegistroLaHora


# ============================================================
# INICIALIZACIÓN
# ============================================================

async def inicializar_db():
    """Crea el esquema de laHora (y del resto de los módulos)."""

    await _inicializar_db_base()


# ============================================================
# REGISTROS
# ============================================================

async def obtener_registro(
    guild_id,
    user_id,
    fecha,
    ventana,
):
    """Devuelve ``(momento, puntos_finales)`` si ya dijo 420 en esa ventana."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                RegistroLaHora.momento,
                RegistroLaHora.puntos_finales,
            ).where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.user_id == user_id,
                RegistroLaHora.fecha == fecha,
                RegistroLaHora.ventana == ventana,
            )
        )).first()

    return fila


async def contar_registros_ventana(
    guild_id,
    fecha,
    ventana,
):
    """Cantidad de 420 ya registrados en una ventana del servidor."""

    async with crear_sesion() as sesion:
        cantidad = (await sesion.execute(
            select(func.count()).where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.fecha == fecha,
                RegistroLaHora.ventana == ventana,
            )
        )).scalar_one()

    return cantidad


async def guardar_registro(**datos):
    """Guarda un 420.

    Devuelve ``False`` si ya existía (restricción única), por ejemplo si
    llegaron dos mensajes del mismo usuario casi al mismo tiempo.
    """

    async with crear_sesion() as sesion:
        sesion.add(RegistroLaHora(**datos))

        try:
            await sesion.commit()
        except IntegrityError:
            await sesion.rollback()
            return False

    return True


# ============================================================
# CONSULTAS
# ============================================================

async def obtener_resumen_usuario(
    guild_id,
    user_id,
):
    """Devuelve ``(total_puntos, cantidad, veces_primero, mejor_segundos)``."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                func.coalesce(func.sum(RegistroLaHora.puntos_finales), 0),
                func.count(),
                func.coalesce(
                    func.sum(
                        case((RegistroLaHora.posicion == 1, 1), else_=0)
                    ),
                    0,
                ),
                func.min(RegistroLaHora.segundos),
            ).where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.user_id == user_id,
            )
        )).one()

    return tuple(fila)


async def obtener_fechas_registradas(
    guild_id,
    user_id,
):
    """Fechas distintas en las que el usuario dijo 420 al menos una vez."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(RegistroLaHora.fecha)
            .where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.user_id == user_id,
            )
            .distinct()
            .order_by(RegistroLaHora.fecha)
        )).all()

    return [fila[0] for fila in filas]


async def obtener_top(
    guild_id,
    limite=10,
):
    """TOP por puntos: ``(user_id, username, puntos, cantidad)``.

    Se agrupa solo por ``user_id`` para que un cambio de apodo no parta
    a la misma persona en dos filas; se muestra el último nombre usado.
    """

    puntos = func.sum(RegistroLaHora.puntos_finales).label("puntos")
    ultimo_id = func.max(RegistroLaHora.id).label("ultimo_id")

    async with crear_sesion() as sesion:
        agregados = (
            select(
                RegistroLaHora.user_id,
                puntos,
                func.count().label("cantidad"),
                ultimo_id,
            )
            .where(RegistroLaHora.guild_id == guild_id)
            .group_by(RegistroLaHora.user_id)
            .subquery()
        )

        filas = (await sesion.execute(
            select(
                agregados.c.user_id,
                RegistroLaHora.username,
                agregados.c.puntos,
                agregados.c.cantidad,
            )
            .join(RegistroLaHora, RegistroLaHora.id == agregados.c.ultimo_id)
            .order_by(agregados.c.puntos.desc(), agregados.c.user_id)
            .limit(limite)
        )).all()

    return filas


async def obtener_registros_del_dia(
    guild_id,
    fecha,
):
    """Registros de un día: ``(ventana, posicion, username, segundos, puntos)``."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                RegistroLaHora.ventana,
                RegistroLaHora.posicion,
                RegistroLaHora.username,
                RegistroLaHora.segundos,
                RegistroLaHora.puntos_finales,
            )
            .where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.fecha == fecha,
            )
            .order_by(RegistroLaHora.ventana, RegistroLaHora.posicion)
        )).all()

    return filas


# ============================================================
# ADMINISTRACIÓN
# ============================================================

async def eliminar_registros_usuario(
    guild_id,
    user_id,
):
    """Elimina todos los 420 de un usuario. Devuelve cuántos borró."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(RegistroLaHora).where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.user_id == user_id,
            )
        )
        await sesion.commit()

    return resultado.rowcount


async def obtener_registros_usuario(
    guild_id,
    user_id,
    limite=20,
):
    """Últimos 420 de un usuario:
    ``(fecha, ventana, segundos, posicion, puntos_finales, mensaje_id)``."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                RegistroLaHora.fecha,
                RegistroLaHora.ventana,
                RegistroLaHora.segundos,
                RegistroLaHora.posicion,
                RegistroLaHora.puntos_finales,
                RegistroLaHora.mensaje_id,
            )
            .where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.user_id == user_id,
            )
            .order_by(RegistroLaHora.fecha.desc(), RegistroLaHora.ventana.desc())
            .limit(limite)
        )).all()

    return filas


async def obtener_detalle_registro(
    guild_id,
    user_id,
    fecha,
    ventana,
):
    """``(segundos, posicion, puntos_finales)`` de un registro o ``None``."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                RegistroLaHora.segundos,
                RegistroLaHora.posicion,
                RegistroLaHora.puntos_finales,
            ).where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.user_id == user_id,
                RegistroLaHora.fecha == fecha,
                RegistroLaHora.ventana == ventana,
            )
        )).first()

    return fila


async def obtener_ventanas_usuario(
    guild_id,
    user_id,
    fecha=None,
):
    """Pares ``(fecha, ventana)`` en los que el usuario tiene registro."""

    condiciones = [
        RegistroLaHora.guild_id == guild_id,
        RegistroLaHora.user_id == user_id,
    ]

    if fecha is not None:
        condiciones.append(RegistroLaHora.fecha == fecha)

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(RegistroLaHora.fecha, RegistroLaHora.ventana)
            .where(*condiciones)
            .distinct()
        )).all()

    return [(fila[0], fila[1]) for fila in filas]


async def eliminar_registros(
    guild_id,
    user_id,
    fecha,
    ventana=None,
):
    """Borra los 420 de un usuario en una fecha (o solo en una ventana)."""

    condiciones = [
        RegistroLaHora.guild_id == guild_id,
        RegistroLaHora.user_id == user_id,
        RegistroLaHora.fecha == fecha,
    ]

    if ventana is not None:
        condiciones.append(RegistroLaHora.ventana == ventana)

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(RegistroLaHora).where(*condiciones)
        )
        await sesion.commit()

    return resultado.rowcount


async def eliminar_registros_servidor(
    guild_id,
):
    """Borra todos los 420 del servidor. Devuelve cuántos borró."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(RegistroLaHora).where(
                RegistroLaHora.guild_id == guild_id,
            )
        )
        await sesion.commit()

    return resultado.rowcount


async def obtener_estadisticas_servidor(
    guild_id,
):
    """``(usuarios, registros, puntos)`` del servidor."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                func.count(func.distinct(RegistroLaHora.user_id)),
                func.count(),
                func.coalesce(func.sum(RegistroLaHora.puntos_finales), 0),
            ).where(RegistroLaHora.guild_id == guild_id)
        )).one()

    return tuple(fila)


async def recalcular_ventana(
    guild_id,
    fecha,
    ventana,
    calcular_puntos,
):
    """Reordena una ventana por hora del mensaje y recalcula los puntos.

    Las posiciones (y el bonus del primero) dependen del orden de llegada.
    Al importar mensajes viejos, agregar a mano o borrar un registro, el
    orden puede cambiar: esto lo deja consistente. ``calcular_puntos``
    recibe ``(segundos, posicion)`` y devuelve
    ``(puntos_base, multiplicador, bonus, puntos_finales)``.
    """

    async with crear_sesion() as sesion:
        registros = (await sesion.execute(
            select(RegistroLaHora).where(
                RegistroLaHora.guild_id == guild_id,
                RegistroLaHora.fecha == fecha,
                RegistroLaHora.ventana == ventana,
            )
        )).scalars().all()

        # Se ordena en Python: en SQLite la hora se guarda como texto ISO.
        registros = sorted(registros, key=lambda r: (r.momento, r.id))

        for posicion, registro in enumerate(registros, start=1):
            base, multiplicador, bonus, finales = calcular_puntos(
                registro.segundos,
                posicion,
            )
            registro.posicion = posicion
            registro.puntos_base = base
            registro.multiplicador = multiplicador
            registro.bonus_posicion = bonus
            registro.puntos_finales = finales

        await sesion.commit()

    return len(registros)
