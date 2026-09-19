"""Capa de datos del módulo SeptSinFP (SQLAlchemy asíncrono).

Todas las funciones son asíncronas y devuelven tuplas con la misma
forma que tenía la capa SQLite original. Las fechas se entregan como
objetos ``date``/``datetime`` nativos en lugar de texto ISO.
"""

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from core.database import crear_sesion, inicializar_db as _inicializar_db_base
from modules.ssf.models import (
    SsfDesafio,
    SsfParticipante,
    SsfRegistro,
    SsfRevision,
)


# ============================================================
# INICIALIZACIÓN
# ============================================================

async def inicializar_db():
    """Crea el esquema SSF (y del resto de los módulos)."""

    await _inicializar_db_base()


# ============================================================
# DESAFÍOS
# ============================================================

async def crear_desafio(
    guild_id,
    nombre,
    fecha_inicio,
    fecha_fin,
    canal_id,
):
    """Crea un nuevo desafío y devuelve su id."""

    async with crear_sesion() as sesion:
        desafio = SsfDesafio(
            guild_id=guild_id,
            nombre=nombre,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            canal_id=canal_id,
            activo=1,
        )
        sesion.add(desafio)
        await sesion.flush()
        desafio_id = desafio.id
        await sesion.commit()

    return desafio_id


_COLUMNAS_DESAFIO = (
    SsfDesafio.id,
    SsfDesafio.guild_id,
    SsfDesafio.nombre,
    SsfDesafio.fecha_inicio,
    SsfDesafio.fecha_fin,
    SsfDesafio.canal_id,
    SsfDesafio.activo,
)


async def obtener_desafio_activo(guild_id):
    """Obtiene el desafío activo de un servidor."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(*_COLUMNAS_DESAFIO)
            .where(
                SsfDesafio.guild_id == guild_id,
                SsfDesafio.activo == 1,
            )
            .order_by(SsfDesafio.id.desc())
            .limit(1)
        )).first()

    return fila


async def obtener_ultimo_desafio(guild_id):
    """Obtiene el desafío más reciente de un servidor, activo o no."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(*_COLUMNAS_DESAFIO)
            .where(SsfDesafio.guild_id == guild_id)
            .order_by(SsfDesafio.id.desc())
            .limit(1)
        )).first()

    return fila


async def obtener_desafio_por_id(desafio_id):
    """Obtiene un desafío por su ID."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(*_COLUMNAS_DESAFIO).where(SsfDesafio.id == desafio_id)
        )).first()

    return fila


async def cerrar_desafio(desafio_id):
    """Cierra un desafío. Devuelve la cantidad de filas afectadas."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            update(SsfDesafio)
            .where(SsfDesafio.id == desafio_id)
            .values(activo=0)
        )
        await sesion.commit()

    return resultado.rowcount


# ============================================================
# PARTICIPANTES
# ============================================================

async def registrar_participante(
    desafio_id,
    user_id,
    username,
    fecha_registro,
):
    """Registra un usuario como participante."""

    async with crear_sesion() as sesion:
        sesion.add(
            SsfParticipante(
                desafio_id=desafio_id,
                user_id=user_id,
                username=username,
                fecha_registro=fecha_registro,
            )
        )
        await sesion.commit()


async def obtener_participante(
    desafio_id,
    user_id,
):
    """Obtiene un participante."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                SsfParticipante.desafio_id,
                SsfParticipante.user_id,
                SsfParticipante.username,
                SsfParticipante.fecha_registro,
                SsfParticipante.eliminado,
                SsfParticipante.fecha_eliminacion,
                SsfParticipante.racha_actual,
                SsfParticipante.mejor_racha,
            ).where(
                SsfParticipante.desafio_id == desafio_id,
                SsfParticipante.user_id == user_id,
            )
        )).first()

    return fila


async def actualizar_participante(
    desafio_id,
    user_id,
    racha_actual,
    mejor_racha,
):
    """Actualiza las rachas de un participante."""

    async with crear_sesion() as sesion:
        await sesion.execute(
            update(SsfParticipante)
            .where(
                SsfParticipante.desafio_id == desafio_id,
                SsfParticipante.user_id == user_id,
            )
            .values(
                racha_actual=racha_actual,
                mejor_racha=mejor_racha,
            )
        )
        await sesion.commit()


async def eliminar_participante(
    desafio_id,
    user_id,
    fecha_eliminacion,
):
    """Marca a un participante como eliminado."""

    async with crear_sesion() as sesion:
        await sesion.execute(
            update(SsfParticipante)
            .where(
                SsfParticipante.desafio_id == desafio_id,
                SsfParticipante.user_id == user_id,
            )
            .values(
                eliminado=1,
                fecha_eliminacion=fecha_eliminacion,
            )
        )
        await sesion.commit()


async def obtener_participantes(
    desafio_id,
):
    """Obtiene todos los participantes de un desafío."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                SsfParticipante.user_id,
                SsfParticipante.username,
                SsfParticipante.fecha_registro,
                SsfParticipante.eliminado,
                SsfParticipante.fecha_eliminacion,
                SsfParticipante.racha_actual,
                SsfParticipante.mejor_racha,
            )
            .where(SsfParticipante.desafio_id == desafio_id)
            .order_by(SsfParticipante.fecha_registro.asc())
        )).all()

    return filas


# ============================================================
# REGISTROS DIARIOS
# ============================================================

async def guardar_registro(
    desafio_id,
    user_id,
    fecha,
    hora,
):
    """Guarda la supervivencia de un participante."""

    async with crear_sesion() as sesion:
        sesion.add(
            SsfRegistro(
                desafio_id=desafio_id,
                user_id=user_id,
                fecha=fecha,
                hora=hora,
            )
        )
        await sesion.commit()


async def tiene_registro(
    desafio_id,
    user_id,
    fecha,
):
    """Comprueba si un participante sobrevivió ese día."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(1).where(
                SsfRegistro.desafio_id == desafio_id,
                SsfRegistro.user_id == user_id,
                SsfRegistro.fecha == fecha,
            )
        )).first()

    return fila is not None


async def obtener_registros_usuario(
    desafio_id,
    user_id,
):
    """Obtiene las fechas sobrevividas por un participante."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(SsfRegistro.fecha)
            .where(
                SsfRegistro.desafio_id == desafio_id,
                SsfRegistro.user_id == user_id,
            )
            .order_by(SsfRegistro.fecha.asc())
        )).all()

    return filas


async def eliminar_registro(
    desafio_id,
    user_id,
    fecha,
):
    """
    Elimina la supervivencia de un día.

    Solo lo usan las herramientas administrativas de reparación manual.
    Ningún flujo normal del juego borra registros.
    """

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            delete(SsfRegistro).where(
                SsfRegistro.desafio_id == desafio_id,
                SsfRegistro.user_id == user_id,
                SsfRegistro.fecha == fecha,
            )
        )
        await sesion.commit()

    return resultado.rowcount


# ============================================================
# ESTADÍSTICAS
# ============================================================

async def obtener_estadisticas_desafio(
    desafio_id,
):
    """Obtiene estadísticas generales del desafío."""

    async with crear_sesion() as sesion:

        total = (await sesion.execute(
            select(func.count()).where(
                SsfParticipante.desafio_id == desafio_id
            )
        )).scalar_one()

        activos = (await sesion.execute(
            select(func.count()).where(
                SsfParticipante.desafio_id == desafio_id,
                SsfParticipante.eliminado == 0,
            )
        )).scalar_one()

        eliminados = (await sesion.execute(
            select(func.count()).where(
                SsfParticipante.desafio_id == desafio_id,
                SsfParticipante.eliminado == 1,
            )
        )).scalar_one()

    return (
        total,
        activos,
        eliminados,
    )


async def reactivar_participante(
    desafio_id,
    user_id,
):
    """Reactiva a un participante eliminado."""

    async with crear_sesion() as sesion:
        await sesion.execute(
            update(SsfParticipante)
            .where(
                SsfParticipante.desafio_id == desafio_id,
                SsfParticipante.user_id == user_id,
            )
            .values(
                eliminado=0,
                fecha_eliminacion=None,
            )
        )
        await sesion.commit()


async def obtener_desafios_activos():
    """Obtiene todos los desafíos activos."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(*_COLUMNAS_DESAFIO)
            .where(SsfDesafio.activo == 1)
            .order_by(SsfDesafio.id.asc())
        )).all()

    return filas


# ============================================================
# CONTROL DE REVISIONES AUTOMÁTICAS
# ============================================================

async def obtener_ultima_revision_ssf(desafio_id):
    """Obtiene la última fecha procesada automáticamente."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(SsfRevision.ultima_fecha).where(
                SsfRevision.desafio_id == desafio_id
            )
        )).first()

    if fila is None:
        return None

    return fila[0]


async def guardar_ultima_revision_ssf(
    desafio_id,
    fecha,
):
    """Guarda la última fecha procesada automáticamente."""

    async with crear_sesion() as sesion:
        revision = await sesion.get(SsfRevision, desafio_id)

        if revision is None:
            sesion.add(
                SsfRevision(
                    desafio_id=desafio_id,
                    ultima_fecha=fecha,
                )
            )
        else:
            revision.ultima_fecha = fecha

        await sesion.commit()


async def obtener_ranking_final(desafio_id):
    """Obtiene el ranking final de un desafío."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                SsfParticipante.user_id,
                SsfParticipante.username,
                SsfParticipante.eliminado,
                SsfParticipante.racha_actual,
                SsfParticipante.mejor_racha,
            )
            .where(SsfParticipante.desafio_id == desafio_id)
            .order_by(
                SsfParticipante.eliminado.asc(),
                SsfParticipante.mejor_racha.desc(),
                # COLLATE NOCASE de SQLite equivale a ordenar por minúsculas.
                func.lower(SsfParticipante.username).asc(),
            )
        )).all()

    return filas


async def marcar_desafio_cerrado(desafio_id):
    """Marca un desafío como cerrado."""

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            update(SsfDesafio)
            .where(
                SsfDesafio.id == desafio_id,
                SsfDesafio.activo == 1,
            )
            .values(activo=0)
        )
        await sesion.commit()

    return resultado.rowcount
