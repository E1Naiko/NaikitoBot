"""Capa de datos del módulo Box (SQLAlchemy asíncrono).

Todas las funciones son asíncronas y abren su propia sesión corta.
Las fechas se manejan como objetos ``datetime`` nativos (con zona
horaria) en lugar de texto ISO. Las funciones que necesitan varias
escrituras relacionadas usan una única sesión sin commit intermedio:
si algo falla o se devuelve temprano, los cambios se descartan solos,
igual que los viejos ``BEGIN IMMEDIATE`` + ``rollback`` de SQLite.
"""

from collections import defaultdict
from datetime import datetime, timedelta
import math
import random

from sqlalchemy import case, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from config import (
    BOX_CANSANCIO_INICIAL,
    BOX_DESCANSO_REDUCCION_POR_HORA,
    BOX_COMBATE_ACTIVO,
    BOX_COMBATE_TICK_SEGUNDOS,
    BOX_COMBATE_UNICO_GLOBAL,
    BOX_DANO_INICIAL,
    BOX_DANO_MAXIMO,
    BOX_DEFENSA_INICIAL,
    BOX_DEFENSA_MAXIMO,
    BOX_DESAFIO_DURACION_HORAS,
    BOX_DESAFIO_PREMIO_VS_BOT,
    BOX_LESION_DECAIMIENTO_POR_HORA,
    BOX_LESION_HORAS,
    BOX_LESION_PROBABILIDAD_MAXIMA,
    BOX_LESION_PROBABILIDAD_POR_HORA,
    BOX_MEDICO_CICLO_HORAS,
    BOX_MEDICO_REDUCCION,
    BOX_PROMOCION_PROBABILIDAD,
    BOX_SPONSOR_CICLO_PAGO_HORAS,
    BOX_SPONSOR_DURACION_DIAS,
    BOX_SPONSOR_EQUIPAMIENTO_BONUS,
    BOX_SPONSOR_MAXIMO,
    BOX_SPONSOR_PAGO,
    BOX_SPONSOR_PROBABILIDAD,
    BOX_VIDA_INICIAL,
)

from core.database import crear_sesion, inicializar_db as _inicializar_db_base
from core.utils import ahora as _ahora
from modules.box.fighting import planificar_pelea
from modules.box.logic import precio_mejora, estadisticas_de_combate
from modules.box.models import (
    BoxAccion,
    BoxCombate,
    BoxCombateAsalto,
    BoxConfigGuild,
    BoxDesafio,
    BoxDesafioHistorial,
    BoxEquipo,
    BoxMejora,
    BoxSponsor,
    BoxUsuario,
)
from modules.box.sparring import planificar_sparring


# ============================================================
# CONFIGURACIÓN DE SPONSORS
# ============================================================
#
# Los valores se leen del .env (variables BOX_SPONSOR_*) y se validan
# al arrancar en config/settings.py. Acá solo se adaptan al formato
# que usa el resto del módulo.

PROBABILIDAD_PROMOCION = BOX_PROMOCION_PROBABILIDAD

PROBABILIDAD_SPONSORS = BOX_SPONSOR_PROBABILIDAD

DURACION_SPONSOR = {
    tipo: timedelta(days=dias)
    for tipo, dias in BOX_SPONSOR_DURACION_DIAS.items()
}

PAGO_SPONSOR = BOX_SPONSOR_PAGO

MAX_SPONSORS = BOX_SPONSOR_MAXIMO


async def inicializar_db():
    """Crea el esquema de Box (y del resto de los módulos)."""

    await _inicializar_db_base()


# ============================================================
# HELPERS DE SESIÓN
# ============================================================

async def _asegurar_usuario(sesion, guild_id: int, user_id: int):
    """Crea la fila de ``box_usuarios`` si todavía no existe."""

    if await sesion.get(BoxUsuario, (guild_id, user_id)) is None:
        sesion.add(BoxUsuario(guild_id=guild_id, user_id=user_id))
        await sesion.flush()


async def _asegurar_equipo(sesion, guild_id: int, user_id: int):
    """Crea la fila de ``box_equipo`` si todavía no existe."""

    if await sesion.get(BoxEquipo, (guild_id, user_id)) is None:
        sesion.add(BoxEquipo(guild_id=guild_id, user_id=user_id))
        await sesion.flush()


# ============================================================
# ACCIONES
# ============================================================

async def iniciar_accion(
    guild_id: int,
    user_id: int,
    tipo: str,
    iniciado_en: datetime,
    finaliza_en: datetime,
    recompensa: int,
    dinero_recompensa: int = 0,
):
    """Registra una acción si el usuario no tiene otra activa."""

    if tipo == "TRABAJANDO":
        dinero_recompensa = recompensa

    async with crear_sesion() as sesion:
        try:
            sesion.add(
                BoxAccion(
                    guild_id=guild_id,
                    user_id=user_id,
                    tipo=tipo,
                    iniciado_en=iniciado_en,
                    finaliza_en=finaliza_en,
                    recompensa=recompensa,
                    dinero_recompensa=dinero_recompensa,
                )
            )
            await sesion.commit()
        except IntegrityError:
            await sesion.rollback()
            return False

    return True


async def obtener_accion_activa(guild_id: int, user_id: int):
    """Devuelve la acción activa del usuario, si existe."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                BoxAccion.tipo,
                BoxAccion.finaliza_en,
                BoxAccion.recompensa,
            ).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == user_id,
            )
        )).first()

    return fila


# ============================================================
# ESTADO DEL USUARIO
# ============================================================

async def obtener_estado_box(guild_id: int, user_id: int):
    """Devuelve probabilidad de lesión y fecha de recuperación."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                BoxUsuario.probabilidad_lesion,
                BoxUsuario.lesionado_hasta,
            ).where(
                BoxUsuario.guild_id == guild_id,
                BoxUsuario.user_id == user_id,
            )
        )).first()

    return fila or (0.0, None)


# ============================================================
# DECAIMIENTO DE LA PROBABILIDAD
# ============================================================

async def reducir_probabilidad_lesion_inactivos(
    cantidad: float = BOX_LESION_DECAIMIENTO_POR_HORA,
) -> int:
    """
    Reduce la probabilidad de lesión de los usuarios sin acción activa.

    Cada llamada representa una hora sin ninguna acción activa: baja la
    probabilidad en ``cantidad`` puntos porcentuales, sin pasar de 0.
    Aplica también a usuarios lesionados (una lesión no es una acción).
    """

    nueva_probabilidad = case(
        (BoxUsuario.probabilidad_lesion - cantidad < 0, 0),
        else_=BoxUsuario.probabilidad_lesion - cantidad,
    )

    tiene_accion = exists(
        select(1).where(
            BoxAccion.guild_id == BoxUsuario.guild_id,
            BoxAccion.user_id == BoxUsuario.user_id,
        )
    )

    async with crear_sesion() as sesion:
        resultado = await sesion.execute(
            update(BoxUsuario)
            .where(
                BoxUsuario.probabilidad_lesion > 0,
                ~tiene_accion,
            )
            .values(probabilidad_lesion=nueva_probabilidad)
            .execution_options(synchronize_session=False)
        )
        await sesion.commit()

    return resultado.rowcount


# ============================================================
# TRATAMIENTOS
# ============================================================

async def comprar_tratamiento(
    guild_id: int,
    user_id: int,
    precio: int,
    ahora: datetime,
    reinicia_probabilidad: bool = False,
):
    """Compra un tratamiento, cura la lesión y opcionalmente resetea la probabilidad."""

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, user_id)

        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))

        saldo = usuario.dinero
        lesionado_hasta = usuario.lesionado_hasta

        if saldo < precio:
            return "insuficiente", saldo

        if lesionado_hasta is None or lesionado_hasta <= ahora:
            return "no_lesionado", saldo

        usuario.dinero = usuario.dinero - precio
        usuario.lesionado_hasta = None

        if reinicia_probabilidad:
            usuario.probabilidad_lesion = 0.0

        await sesion.commit()

    return "comprado", saldo - precio


# ============================================================
# SUMINISTROS DE RECUPERACIÓN
# ============================================================

async def usar_suministro(
    guild_id: int,
    user_id: int,
    objetivo: str,
    precio: int,
    ahora: datetime,
):
    """Usa un suministro y restaura al máximo la estadística indicada.

    ``objetivo`` puede ser ``vida``, ``cansancio``, ``defensa`` o ``lesion``.
    Si la estadística ya está al máximo (o no hay lesión ni probabilidad que
    curar), no descuenta dinero y devuelve el estado correspondiente.
    """

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, user_id)
        await _asegurar_equipo(sesion, guild_id, user_id)

        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))
        equipo = await sesion.get(BoxEquipo, (guild_id, user_id))

        saldo = usuario.dinero

        # ----------------------------------------------------
        # COMPROBAR SI LA ESTADÍSTICA NECESITA RECUPERACIÓN
        # ----------------------------------------------------

        aplica = True

        if objetivo == "vida":
            aplica = equipo.vida < equipo.vida_maxima
        elif objetivo == "cansancio":
            aplica = equipo.cansancio < equipo.cansancio_maximo
        elif objetivo == "defensa":
            aplica = equipo.defensa < equipo.defensa_maxima
        elif objetivo == "lesion":
            lesionado_activo = (
                usuario.lesionado_hasta is not None
                and usuario.lesionado_hasta > ahora
            )
            aplica = lesionado_activo or usuario.probabilidad_lesion > 0
        else:
            return "objetivo_invalido", saldo

        if not aplica:
            if objetivo == "lesion":
                return "sin_lesion", saldo
            return "lleno", saldo

        # ----------------------------------------------------
        # COBRO Y APLICACIÓN
        # ----------------------------------------------------

        if saldo < precio:
            return "insuficiente", saldo

        usuario.dinero = usuario.dinero - precio

        if objetivo == "vida":
            equipo.vida = equipo.vida_maxima
        elif objetivo == "cansancio":
            equipo.cansancio = equipo.cansancio_maximo
        elif objetivo == "defensa":
            equipo.defensa = equipo.defensa_maxima
        else:
            usuario.lesionado_hasta = None
            usuario.probabilidad_lesion = 0.0

        await sesion.commit()

    return "comprado", saldo - precio


# ============================================================
# SALDO / ESTADÍSTICAS
# ============================================================

async def obtener_saldo(guild_id: int, user_id: int):
    """Devuelve experiencia y dinero del usuario."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                BoxUsuario.experiencia,
                BoxUsuario.dinero,
            ).where(
                BoxUsuario.guild_id == guild_id,
                BoxUsuario.user_id == user_id,
            )
        )).first()

    return fila or (0, 0)


async def obtener_estadisticas_box(guild_id: int, user_id: int):
    """Devuelve el resumen privado de progreso y desafíos del usuario."""

    experiencia, dinero = await obtener_saldo(guild_id, user_id)

    probabilidad_lesion, lesionado_hasta = await obtener_estado_box(
        guild_id,
        user_id,
    )

    niveles = {}

    async with crear_sesion() as sesion:
        filas_mejoras = (await sesion.execute(
            select(
                BoxMejora.mejora,
                BoxMejora.nivel,
            ).where(
                BoxMejora.guild_id == guild_id,
                BoxMejora.user_id == user_id,
            )
        )).all()

        for mejora, nivel in filas_mejoras:
            niveles[mejora] = nivel

        ganadas = (await sesion.execute(
            select(func.count()).where(
                BoxDesafioHistorial.guild_id == guild_id,
                BoxDesafioHistorial.ganador_id == user_id,
            )
        )).scalar_one()

        participaciones = (await sesion.execute(
            select(func.count()).where(
                BoxDesafioHistorial.guild_id == guild_id,
                or_(
                    BoxDesafioHistorial.retador_id == user_id,
                    BoxDesafioHistorial.contrincante_id == user_id,
                ),
            )
        )).scalar_one()

        sponsors = (await sesion.execute(
            select(
                BoxSponsor.tipo,
                func.count(),
            )
            .where(
                BoxSponsor.guild_id == guild_id,
                BoxSponsor.user_id == user_id,
                BoxSponsor.expira_en > _ahora(),
            )
            .group_by(BoxSponsor.tipo)
        )).all()

    sponsors_activos = {
        tipo: cantidad
        for tipo, cantidad in sponsors
    }

    perdidas = participaciones - ganadas

    return {
        "experiencia": experiencia,
        "dinero": dinero,
        "nivel_entrenamiento": niveles.get("entrenamiento", 0),
        "nivel_trabajo": niveles.get("trabajo", 0),
        "ganadas": ganadas,
        "perdidas": perdidas,
        "ratio": ganadas / perdidas if perdidas else float("inf"),
        "probabilidad_lesion": probabilidad_lesion,
        "lesionado_hasta": lesionado_hasta,
        "sponsors": sponsors_activos,
    }


# ============================================================
# MEJORAS
# ============================================================

async def obtener_nivel_mejora(guild_id: int, user_id: int, mejora: str):
    """Devuelve el nivel actual de una mejora."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(BoxMejora.nivel).where(
                BoxMejora.guild_id == guild_id,
                BoxMejora.user_id == user_id,
                BoxMejora.mejora == mejora,
            )
        )).first()

    return fila[0] if fila else 0


async def comprar_mejora(
    guild_id: int,
    user_id: int,
    mejora: str,
    precio_base: int,
    nivel_maximo: int,
):
    """Compra un nivel de mejora descontando el dinero de forma atómica."""

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, user_id)

        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))
        saldo = usuario.dinero

        fila_mejora = await sesion.get(
            BoxMejora,
            (guild_id, user_id, mejora),
        )

        nivel = fila_mejora.nivel if fila_mejora else 0
        precio = precio_mejora(precio_base, nivel)

        if nivel >= nivel_maximo:
            return "maximo", saldo, nivel

        if saldo < precio:
            return "insuficiente", saldo, nivel

        usuario.dinero = usuario.dinero - precio

        if fila_mejora is None:
            sesion.add(
                BoxMejora(
                    guild_id=guild_id,
                    user_id=user_id,
                    mejora=mejora,
                    nivel=1,
                )
            )
        else:
            fila_mejora.nivel = fila_mejora.nivel + 1

        await sesion.commit()

    return "comprada", saldo - precio, nivel + 1


# ============================================================
# SPONSORS
# ============================================================

def _probabilidad_promocion(minutos: float) -> float:
    """Calcula la probabilidad de conseguir sponsor según el tiempo.

    Usa la curva configurada en ``BOX_PROMOCION_PROBABILIDAD``
    (puntos 'horas=porcentaje' interpolados linealmente); por debajo
    del primer punto vale el primero, y por encima del último, el
    último.
    """

    horas = minutos / 60

    puntos = PROBABILIDAD_PROMOCION

    if horas <= puntos[0][0]:
        return puntos[0][1]

    if horas >= puntos[-1][0]:
        return puntos[-1][1]

    for (hora_a, prob_a), (hora_b, prob_b) in zip(
        puntos,
        puntos[1:],
    ):
        if hora_a <= horas <= hora_b:
            proporcion = (horas - hora_a) / (hora_b - hora_a)
            return prob_a + (
                (prob_b - prob_a) * proporcion
            )

    return puntos[-1][1]


def _sortear_sponsor():
    """Sortear el tipo de sponsor según sus probabilidades."""

    return random.SystemRandom().choices(
        list(PROBABILIDAD_SPONSORS.keys()),
        weights=list(PROBABILIDAD_SPONSORS.values()),
        k=1,
    )[0]


async def _contar_sponsors_activos(
    sesion,
    guild_id: int,
    user_id: int,
    tipo: str,
    ahora: datetime,
):
    return (await sesion.execute(
        select(func.count()).where(
            BoxSponsor.guild_id == guild_id,
            BoxSponsor.user_id == user_id,
            BoxSponsor.tipo == tipo,
            BoxSponsor.expira_en > ahora,
        )
    )).scalar_one()


async def _crear_sponsor(
    sesion,
    guild_id: int,
    user_id: int,
    tipo: str,
    ahora: datetime,
):
    """Crea un sponsor individual dentro de la sesión abierta."""

    limite = MAX_SPONSORS.get(tipo)

    if limite is not None:
        cantidad = await _contar_sponsors_activos(
            sesion,
            guild_id,
            user_id,
            tipo,
            ahora,
        )

        if cantidad >= limite:
            return False

    expira_en = ahora + DURACION_SPONSOR[tipo]

    sesion.add(
        BoxSponsor(
            guild_id=guild_id,
            user_id=user_id,
            tipo=tipo,
            obtenido_en=ahora,
            expira_en=expira_en,
            ultimo_pago=(
                ahora
                if tipo in PAGO_SPONSOR
                else None
            ),
            ultimo_tratamiento=(
                ahora
                if tipo == "medico"
                else None
            ),
        )
    )
    await sesion.flush()

    return True


async def obtener_sponsors_activos(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """Devuelve los sponsors actualmente activos."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                BoxSponsor.id,
                BoxSponsor.tipo,
                BoxSponsor.obtenido_en,
                BoxSponsor.expira_en,
                BoxSponsor.ultimo_pago,
                BoxSponsor.ultimo_tratamiento,
            )
            .where(
                BoxSponsor.guild_id == guild_id,
                BoxSponsor.user_id == user_id,
                BoxSponsor.expira_en > ahora,
            )
            .order_by(BoxSponsor.expira_en.asc())
        )).all()

    return filas


async def obtener_bonus_experiencia_sponsor(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """Devuelve el bonus porcentual de EXP de Equipamiento."""

    async with crear_sesion() as sesion:
        cantidad = await _contar_sponsors_activos(
            sesion,
            guild_id,
            user_id,
            "equipamiento",
            ahora,
        )

    return cantidad * 10


async def obtener_sponsor_para_promocion(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """
    Devuelve un sponsor aleatorio si el usuario consigue uno
    por promocionarse.
    """

    tipo = _sortear_sponsor()

    async with crear_sesion() as sesion:
        creado = await _crear_sponsor(
            sesion,
            guild_id,
            user_id,
            tipo,
            ahora,
        )

        if not creado:
            return None

        await sesion.commit()

    return tipo


async def procesar_pagos_sponsors(ahora: datetime):
    """
    Procesa los pagos diarios de Redes y Radio.

    Cada sponsor tiene su propio ciclo de 24 horas.
    """

    pagos = []

    async with crear_sesion() as sesion:
        sponsors = (await sesion.execute(
            select(
                BoxSponsor.id,
                BoxSponsor.guild_id,
                BoxSponsor.user_id,
                BoxSponsor.tipo,
                BoxSponsor.ultimo_pago,
                BoxSponsor.expira_en,
            ).where(
                BoxSponsor.tipo.in_(["redes", "radio"]),
                BoxSponsor.expira_en > ahora,
            )
        )).all()

        for (
            sponsor_id,
            guild_id,
            user_id,
            tipo,
            ultimo_pago,
            expira_en,
        ) in sponsors:

            if ultimo_pago is None:
                ultimo_pago_dt = ahora
            else:
                ultimo_pago_dt = ultimo_pago

            horas_transcurridas = (
                ahora - ultimo_pago_dt
            ).total_seconds() / 3600

            ciclo_horas = BOX_SPONSOR_CICLO_PAGO_HORAS

            pagos_pendientes = int(horas_transcurridas // ciclo_horas)

            if pagos_pendientes <= 0:
                continue

            pago = PAGO_SPONSOR[tipo] * pagos_pendientes

            await _asegurar_usuario(sesion, guild_id, user_id)

            usuario = await sesion.get(
                BoxUsuario,
                (guild_id, user_id),
            )
            usuario.dinero = usuario.dinero + pago

            nuevo_ultimo_pago = (
                ultimo_pago_dt
                + timedelta(hours=ciclo_horas * pagos_pendientes)
            )

            # No permitir que el siguiente pago quede programado
            # después de la fecha de vencimiento.
            if nuevo_ultimo_pago > expira_en:
                nuevo_ultimo_pago = expira_en

            sponsor = await sesion.get(BoxSponsor, sponsor_id)
            sponsor.ultimo_pago = nuevo_ultimo_pago

            pagos.append(
                (
                    guild_id,
                    user_id,
                    tipo,
                    pago,
                )
            )

        await sesion.commit()

    return pagos


async def procesar_sponsors_medicos(ahora: datetime):
    """
    Aplica una reducción del 50% a la probabilidad de lesión
    una vez cada 24 horas por sponsor médico.
    """

    procesados = []

    async with crear_sesion() as sesion:
        sponsors = (await sesion.execute(
            select(
                BoxSponsor.id,
                BoxSponsor.guild_id,
                BoxSponsor.user_id,
                BoxSponsor.ultimo_tratamiento,
                BoxSponsor.expira_en,
            ).where(
                BoxSponsor.tipo == "medico",
                BoxSponsor.expira_en > ahora,
            )
        )).all()

        for (
            sponsor_id,
            guild_id,
            user_id,
            ultimo_tratamiento,
            expira_en,
        ) in sponsors:

            if ultimo_tratamiento is None:
                ultimo_tratamiento_dt = (
                    ahora - timedelta(hours=BOX_MEDICO_CICLO_HORAS)
                )
            else:
                ultimo_tratamiento_dt = ultimo_tratamiento

            horas_transcurridas = (
                ahora - ultimo_tratamiento_dt
            ).total_seconds() / 3600

            tratamientos_pendientes = int(
                horas_transcurridas // BOX_MEDICO_CICLO_HORAS
            )

            if tratamientos_pendientes <= 0:
                continue

            usuario = await sesion.get(
                BoxUsuario,
                (guild_id, user_id),
            )

            if usuario is None:
                probabilidad = 0.0
            else:
                probabilidad = float(usuario.probabilidad_lesion)

            for _ in range(tratamientos_pendientes):
                probabilidad *= (
                    1 - BOX_MEDICO_REDUCCION / 100
                )

            await _asegurar_usuario(sesion, guild_id, user_id)

            usuario = await sesion.get(
                BoxUsuario,
                (guild_id, user_id),
            )
            usuario.probabilidad_lesion = probabilidad

            nuevo_ultimo_tratamiento = (
                ultimo_tratamiento_dt
                + timedelta(
                    hours=BOX_MEDICO_CICLO_HORAS * tratamientos_pendientes
                )
            )

            if nuevo_ultimo_tratamiento > expira_en:
                nuevo_ultimo_tratamiento = expira_en

            sponsor = await sesion.get(BoxSponsor, sponsor_id)
            sponsor.ultimo_tratamiento = nuevo_ultimo_tratamiento

            procesados.append(
                (
                    guild_id,
                    user_id,
                    probabilidad,
                )
            )

        await sesion.commit()

    return procesados


# ============================================================
# COMPLETAR ACCIONES
# ============================================================

async def _liquidar_accion(sesion, fila, ahora: datetime):
    """Liquida una única acción vencida y devuelve sus datos para notificar.

    Las acciones especiales no usan la liquidación normal:

    - ``PROMOVIENDO`` busca un sponsor sin recompensas ni riesgo de lesión.
    - ``DESCANSANDO`` reduce la probabilidad de lesión sin curar al usuario.
    """

    (
        accion_id,
        guild_id,
        user_id,
        tipo,
        recompensa,
        dinero_recompensa,
        iniciado_en,
        finaliza_en,
    ) = fila

    duracion_horas = (
        finaliza_en - iniciado_en
    ).total_seconds() / 3600

    await sesion.execute(
        delete(BoxAccion).where(BoxAccion.id == accion_id)
    )

    await _asegurar_usuario(sesion, guild_id, user_id)

    # =================================================
    # DESCANSO
    # =================================================

    if tipo == "DESCANSANDO":
        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))
        probabilidad_anterior = usuario.probabilidad_lesion
        reduccion_programada = (
            duracion_horas * BOX_DESCANSO_REDUCCION_POR_HORA
        )
        probabilidad_nueva = max(
            0.0,
            probabilidad_anterior - reduccion_programada,
        )
        reduccion_efectiva = probabilidad_anterior - probabilidad_nueva

        usuario.probabilidad_lesion = probabilidad_nueva

        # Descansar no cura una lesión, no da recompensas y tampoco puede
        # provocar una lesión nueva. El cuarto campo comunica cuánto se redujo
        # realmente para que los avisos automáticos y administrativos puedan
        # mostrarlo sin cambiar el contrato de la tupla de liquidación.
        return (
            guild_id,
            user_id,
            tipo,
            reduccion_efectiva,
            0,
            False,
            None,
            None,
        )

    # =================================================
    # PROMOCIÓN
    # =================================================

    if tipo == "PROMOVIENDO":
        minutos = duracion_horas * 60
        probabilidad_sponsor = _probabilidad_promocion(
            minutos
        )

        consiguio_sponsor = (
            random.random()
            < probabilidad_sponsor / 100
        )

        sponsor = None

        if consiguio_sponsor:
            sponsor = _sortear_sponsor()

            creado = await _crear_sponsor(
                sesion,
                guild_id,
                user_id,
                sponsor,
                ahora,
            )

            if not creado:
                sponsor = None

        return (
            guild_id,
            user_id,
            tipo,
            0,
            0,
            False,
            probabilidad_sponsor,
            sponsor,
        )

    # =================================================
    # ACCIONES NORMALES
    # =================================================

    usuario = await sesion.get(BoxUsuario, (guild_id, user_id))

    probabilidad_anterior = usuario.probabilidad_lesion
    lesionado_hasta = usuario.lesionado_hasta

    probabilidad = min(
        BOX_LESION_PROBABILIDAD_MAXIMA,
        probabilidad_anterior
        + duracion_horas * BOX_LESION_PROBABILIDAD_POR_HORA,
    )

    se_lesiona = random.random() < (
        probabilidad / 100
    )

    if se_lesiona:
        lesionado_hasta = ahora + timedelta(hours=BOX_LESION_HORAS)

    usuario.probabilidad_lesion = probabilidad
    usuario.lesionado_hasta = lesionado_hasta

    # Bonus de Equipamiento.
    bonus_exp = await _contar_sponsors_activos(
        sesion,
        guild_id,
        user_id,
        "equipamiento",
        ahora,
    )

    recompensa_final = recompensa

    if bonus_exp:
        recompensa_final = math.floor(
            recompensa
            * (1 + (bonus_exp * BOX_SPONSOR_EQUIPAMIENTO_BONUS / 100))
        )

    if tipo != "TRABAJANDO":
        usuario.experiencia = usuario.experiencia + recompensa_final

    usuario.dinero = usuario.dinero + dinero_recompensa

    return (
        guild_id,
        user_id,
        tipo,
        recompensa_final,
        dinero_recompensa,
        se_lesiona,
        None,
        None,
    )


_COLUMNAS_ACCION_VENCIDA = (
    BoxAccion.id,
    BoxAccion.guild_id,
    BoxAccion.user_id,
    BoxAccion.tipo,
    BoxAccion.recompensa,
    BoxAccion.dinero_recompensa,
    BoxAccion.iniciado_en,
    BoxAccion.finaliza_en,
)


async def completar_acciones_vencidas(ahora: datetime):
    """Liquida acciones vencidas y devuelve sus datos para notificar.

    La liquidación contempla las reglas especiales de promoción y descanso;
    las acciones normales entregan recompensas y sortean una posible lesión.
    """

    completadas = []

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(*_COLUMNAS_ACCION_VENCIDA).where(
                BoxAccion.finaliza_en <= ahora
            )
        )).all()

        for fila in filas:
            completadas.append(
                await _liquidar_accion(sesion, fila, ahora)
            )

        await sesion.commit()

    # Los sponsors se procesan cada vez que el sistema
    # comprueba acciones vencidas.
    #
    # Esto permite que los pagos y tratamientos sigan
    # funcionando aunque el bot haya estado reiniciado.
    await procesar_pagos_sponsors(ahora)
    await procesar_sponsors_medicos(ahora)

    return completadas


async def admin_completar_acciones_vencidas(guild_id: int, ahora: datetime):
    """
    Liquida las acciones vencidas de un único servidor.

    Es la versión manual de ``completar_acciones_vencidas`` para
    mantenimiento administrativo, sin tocar las de otros servidores.
    """

    completadas = []

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(*_COLUMNAS_ACCION_VENCIDA).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.finaliza_en <= ahora,
            )
        )).all()

        for fila in filas:
            completadas.append(
                await _liquidar_accion(sesion, fila, ahora)
            )

        await sesion.commit()

    # Igual que la versión global, los sponsors se procesan
    # siempre: sus ciclos internos evitan pagos duplicados.
    await procesar_pagos_sponsors(ahora)
    await procesar_sponsors_medicos(ahora)

    return completadas


async def admin_finalizar_accion(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """Liquida la acción ya vencida de un único usuario.

    Devuelve los mismos datos que ``_liquidar_accion`` o ``None``
    si el usuario no tiene una acción vencida pendiente.
    """

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(*_COLUMNAS_ACCION_VENCIDA)
            .where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == user_id,
                BoxAccion.finaliza_en <= ahora,
            )
            .order_by(BoxAccion.finaliza_en.asc())
            .limit(1)
        )).first()

        if fila is None:
            return None

        completada = await _liquidar_accion(sesion, fila, ahora)

        await sesion.commit()

    await procesar_pagos_sponsors(ahora)
    await procesar_sponsors_medicos(ahora)

    return completada


# ============================================================
# DESAFÍOS
# ============================================================

async def crear_desafio(
    guild_id: int,
    retador_id: int,
    contrincante_id: int,
    ahora: datetime,
    expira_en: datetime,
    *,
    tipo: str = "SPARRING",
    canal_id: int | None = None,
):
    """Crea un desafío pendiente.

    ``tipo`` (``SPARRING`` o ``FIGHTING``) y ``canal_id`` se guardan para que
    la solicitud se pueda describir y retirar sin depender de la view del
    botón, que se pierde con cada reinicio del bot.
    """

    async with crear_sesion() as sesion:
        await sesion.execute(
            delete(BoxDesafio).where(BoxDesafio.expira_en <= ahora)
        )

        desafio = BoxDesafio(
            guild_id=guild_id,
            retador_id=retador_id,
            contrincante_id=contrincante_id,
            expira_en=expira_en,
            tipo=tipo,
            canal_id=canal_id,
        )
        sesion.add(desafio)

        try:
            await sesion.flush()
        except IntegrityError:
            await sesion.rollback()
            return None

        desafio_id = desafio.id
        await sesion.commit()

    return desafio_id


async def registrar_mensaje_desafio(desafio_id: int, mensaje_id: int):
    """Guarda el id de la tarjeta publicada, para poder retirarla después."""

    async with crear_sesion() as sesion:
        await sesion.execute(
            update(BoxDesafio)
            .where(BoxDesafio.id == desafio_id)
            .values(mensaje_id=mensaje_id)
            .execution_options(synchronize_session=False)
        )
        await sesion.commit()


def _fila_desafio(fila) -> dict:
    """Diccionario de una fila de ``box_desafios``."""

    return {
        "id": fila[0],
        "retador_id": fila[1],
        "contrincante_id": fila[2],
        "tipo": fila[3],
        "expira_en": fila[4],
        "canal_id": fila[5],
        "mensaje_id": fila[6],
    }


_COLUMNAS_DESAFIO = (
    BoxDesafio.id,
    BoxDesafio.retador_id,
    BoxDesafio.contrincante_id,
    BoxDesafio.tipo,
    BoxDesafio.expira_en,
    BoxDesafio.canal_id,
    BoxDesafio.mensaje_id,
)


async def desafios_pendientes(guild_id: int, user_id: int, ahora: datetime):
    """Solicitudes vigentes en las que participa el usuario, en cualquier rol.

    Sirve a ``/box cancelar``: el que propuso puede retirar su solicitud y el
    desafiado puede rechazarla, que en la base es el mismo borrado.
    """

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(*_COLUMNAS_DESAFIO)
            .where(
                BoxDesafio.guild_id == guild_id,
                or_(
                    BoxDesafio.retador_id == user_id,
                    BoxDesafio.contrincante_id == user_id,
                ),
                BoxDesafio.expira_en > ahora,
            )
            .order_by(BoxDesafio.id.asc())
        )).all()

    return [_fila_desafio(fila) for fila in filas]


async def desafio_registrado(desafio_id: int) -> bool:
    """Si la solicitud sigue escrita en la base, vigente o no.

    Lo mira la view del botón antes de anunciar "expirado" en su timeout: la
    view vive en memoria hasta una hora después de publicada la tarjeta, así
    que si la solicitud ya se canceló o ya se aceptó, la tarjeta del canal
    está contando otra cosa y no hay que pisarla.
    """

    async with crear_sesion() as sesion:
        cantidad = (await sesion.execute(
            select(func.count()).where(BoxDesafio.id == desafio_id)
        )).scalar_one()

    return bool(cantidad)


async def cancelar_desafio(
    desafio_id: int,
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """Borra una solicitud pendiente y devuelve lo que se borró, o ``None``.

    Solo puede cancelarla quien participa (el que propuso o el desafiado) y
    solo mientras siga vigente. Todo ocurre en una única transacción para no
    pisarse con una aceptación simultánea: si el botón gana la carrera, la
    fila ya no está y acá devuelve ``None``.
    """

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(*_COLUMNAS_DESAFIO)
            .where(
                BoxDesafio.id == desafio_id,
                BoxDesafio.guild_id == guild_id,
                or_(
                    BoxDesafio.retador_id == user_id,
                    BoxDesafio.contrincante_id == user_id,
                ),
                BoxDesafio.expira_en > ahora,
            )
            .with_for_update()
        )).first()

        if fila is None:
            return None

        await sesion.execute(
            delete(BoxDesafio).where(BoxDesafio.id == desafio_id)
        )
        await sesion.commit()

    return _fila_desafio(fila)


async def aceptar_desafio(
    desafio_id: int,
    guild_id: int,
    contrincante_id: int,
    ahora: datetime,
    recompensa: int,
    tipo: str = "SPARRING",
    multiplicador_experiencia: int = 5,
    recompensa_por_mejora: int = 0,
    canal_id: int | None = None,
    contrincante_es_bot: bool = False,
):
    """Acepta un desafío y crea las dos acciones enfrentadas.

    Además resuelve y registra el combate en vivo (``box_combates``) para que
    el narrador lo vaya revelando asalto por asalto en ``canal_id``.

    ``contrincante_es_bot`` marca la pelea contra la casa: el premio del
    ganador se reduce a ``BOX_DESAFIO_PREMIO_VS_BOT`` (un cuarto por
    defecto) de lo que pagaría la misma pelea contra otro jugador.
    """

    async with crear_sesion() as sesion:
        desafio = (await sesion.execute(
            select(
                BoxDesafio.retador_id,
                BoxDesafio.expira_en,
            ).where(
                BoxDesafio.id == desafio_id,
                BoxDesafio.guild_id == guild_id,
                BoxDesafio.contrincante_id == contrincante_id,
            )
            .with_for_update()
        )).first()

        if desafio is None:
            return {"estado": "invalido"}

        retador_id, expira_en = desafio

        if expira_en <= ahora:
            await sesion.execute(
                delete(BoxDesafio).where(BoxDesafio.id == desafio_id)
            )
            await sesion.commit()
            return {"estado": "expirado"}

        # Un solo combate a la vez. Se comprueba acá, dentro de la misma
        # transacción que crea la fila, porque es el punto donde dos
        # aceptaciones simultáneas podrían pasar las dos por el candado
        # "amable" del comando. El desafío NO se borra: queda pendiente y se
        # puede aceptar cuando termine la pelea que estorbaba.
        en_curso = await _hay_combate_vivo(
            sesion,
            None if BOX_COMBATE_UNICO_GLOBAL else guild_id,
        )

        if en_curso is not None:
            return {
                "estado": "combate_en_curso",
                "combate": {
                    "id": en_curso[0],
                    "guild_id": en_curso[1],
                    "retador_id": en_curso[2],
                    "contrincante_id": en_curso[3],
                    "modo": en_curso[4],
                },
            }

        usuarios = (await sesion.execute(
            select(BoxAccion.user_id).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id.in_(
                    [retador_id, contrincante_id]
                ),
            )
        )).all()

        if usuarios:
            await sesion.execute(
                delete(BoxDesafio).where(BoxDesafio.id == desafio_id)
            )
            await sesion.commit()
            return {"estado": "ocupado"}

        lesionados = (await sesion.execute(
            select(BoxUsuario.user_id).where(
                BoxUsuario.guild_id == guild_id,
                BoxUsuario.user_id.in_(
                    [retador_id, contrincante_id]
                ),
                BoxUsuario.lesionado_hasta.is_not(None),
                BoxUsuario.lesionado_hasta > ahora,
            )
        )).all()

        if lesionados:
            await sesion.execute(
                delete(BoxDesafio).where(BoxDesafio.id == desafio_id)
            )
            await sesion.commit()
            return {"estado": "lesionado"}

        experiencias = {}
        niveles_entrenamiento = {}

        for user_id in (
            retador_id,
            contrincante_id,
        ):
            fila = (await sesion.execute(
                select(
                    func.coalesce(BoxUsuario.experiencia, 0)
                ).where(
                    BoxUsuario.guild_id == guild_id,
                    BoxUsuario.user_id == user_id,
                )
            )).first()

            experiencias[user_id] = (
                fila[0] if fila else 0
            )

            mejora = (await sesion.execute(
                select(BoxMejora.nivel).where(
                    BoxMejora.guild_id == guild_id,
                    BoxMejora.user_id == user_id,
                    BoxMejora.mejora == "entrenamiento",
                )
            )).first()

            niveles_entrenamiento[user_id] = (
                mejora[0] if mejora else 0
            )

        ganador_id = None
        premio_dinero = 0

        if tipo == "FIGHTING":
            ganador_id = random.SystemRandom().choices(
                [
                    retador_id,
                    contrincante_id,
                ],
                weights=[
                    max(
                        experiencias[retador_id],
                        1,
                    ),
                    max(
                        experiencias[contrincante_id],
                        1,
                    ),
                ],
                k=1,
            )[0]

            premio_dinero = (
                experiencias[retador_id]
                + experiencias[contrincante_id]
            )

            # Pelear contra el bot es el camino sin riesgo de la casa: el
            # que lo elige y gana cobra solo una fracción del premio real
            # (un cuarto por defecto). Se escala el premio de la pelea
            # entera, así el aviso de aceptación, la liquidación y el
            # embed muestran siempre la misma cifra.
            if contrincante_es_bot and premio_dinero > 0:
                premio_dinero = max(
                    1,
                    math.floor(premio_dinero * BOX_DESAFIO_PREMIO_VS_BOT),
                )

            sesion.add(
                BoxDesafioHistorial(
                    guild_id=guild_id,
                    retador_id=retador_id,
                    contrincante_id=contrincante_id,
                    ganador_id=ganador_id,
                    creado_en=ahora,
                )
            )
            await sesion.flush()

        finaliza_en = ahora + timedelta(hours=BOX_DESAFIO_DURACION_HORAS)

        for user_id in (
            retador_id,
            contrincante_id,
        ):
            if tipo == "SPARRING":
                # El sparring recompensa a cada participante según el nivel
                # de su rival, no según su propia experiencia ni la duración
                # configurada del desafío. Se usa división entera para que
                # la EXP guardada siga siendo un número entero.
                otro_id = (
                    contrincante_id
                    if user_id == retador_id
                    else retador_id
                )
                recompensa_usuario = experiencias[otro_id] // 10
            else:
                recompensa_usuario = (
                    recompensa
                    + niveles_entrenamiento[user_id]
                    * recompensa_por_mejora
                    * multiplicador_experiencia
                )

            sesion.add(
                BoxAccion(
                    guild_id=guild_id,
                    user_id=user_id,
                    tipo=tipo,
                    iniciado_en=ahora,
                    finaliza_en=finaliza_en,
                    recompensa=recompensa_usuario,
                    dinero_recompensa=(
                        premio_dinero
                        if user_id == ganador_id
                        else 0
                    ),
                )
            )

        await sesion.execute(
            delete(BoxDesafio).where(BoxDesafio.id == desafio_id)
        )

        combate_id = await _crear_combate(
            sesion,
            guild_id,
            modo=tipo,
            retador_id=retador_id,
            contrincante_id=contrincante_id,
            experiencias=experiencias,
            ganador_id=ganador_id,
            ahora=ahora,
            canal_id=canal_id,
        )

        await sesion.commit()

        return {
            "estado": "aceptado",
            "ganador_id": ganador_id,
            "premio_dinero": premio_dinero,
            "combate_id": combate_id,
        }


# ============================================================
# RANKING DE DESAFÍOS
# ============================================================

async def obtener_top_desafios(
    guild_id: int,
    limite: int = 10,
):
    """Devuelve el ranking de FIGHTING ordenado por ratio."""

    resultados = {}

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                BoxDesafioHistorial.retador_id,
                BoxDesafioHistorial.contrincante_id,
                BoxDesafioHistorial.ganador_id,
            ).where(BoxDesafioHistorial.guild_id == guild_id)
        )).all()

    for (
        retador_id,
        contrincante_id,
        ganador_id,
    ) in filas:

        for user_id in (
            retador_id,
            contrincante_id,
        ):
            estadisticas = resultados.setdefault(
                user_id,
                {
                    "ganadas": 0,
                    "perdidas": 0,
                },
            )

            if user_id == ganador_id:
                estadisticas["ganadas"] += 1
            else:
                estadisticas["perdidas"] += 1

    ranking = []

    for user_id, estadisticas in resultados.items():
        perdidas = estadisticas["perdidas"]

        ranking.append(
            (
                user_id,
                estadisticas["ganadas"],
                perdidas,
                (
                    estadisticas["ganadas"]
                    / perdidas
                    if perdidas
                    else float("inf")
                ),
            )
        )

    return sorted(
        ranking,
        key=lambda fila: (
            fila[3],
            fila[1],
        ),
        reverse=True,
    )[:limite]


# ============================================================
# BOT COMO CONTRINCANTE
# ============================================================

async def preparar_bot_para_desafio(
    guild_id: int,
    bot_id: int,
) -> dict:
    """Randomiza los stats del bot entre los extremos del servidor.

    Para cada stat de ``box_equipo`` se busca el mínimo y máximo
    entre todos los jugadores del servidor (excluyendo al propio
    bot) y se elige un valor aleatorio inclusivo entre ellos. Si
    el servidor no tiene jugadores, se usan los valores iniciales
    de ``config``. También randomiza experiencia y niveles de
    mejora entre los mismos extremos.

    Además limpia cualquier acción/lesión/desafío pendiente del bot
    para que siempre pueda aceptar.

    Devuelve un diccionario con los valores generados y los rangos
    usados, útil para mostrar en el embed de aceptación.
    """

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, bot_id)
        await _asegurar_equipo(sesion, guild_id, bot_id)

        # Bot siempre disponible: limpiar acción, lesión y desafíos viejos
        await sesion.execute(
            delete(BoxAccion).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == bot_id,
            )
        )

        bot_usuario = await sesion.get(
            BoxUsuario,
            (guild_id, bot_id),
        )
        bot_usuario.lesionado_hasta = None
        bot_usuario.probabilidad_lesion = 0.0

        await sesion.execute(
            delete(BoxDesafio).where(
                BoxDesafio.guild_id == guild_id,
                or_(
                    BoxDesafio.retador_id == bot_id,
                    BoxDesafio.contrincante_id == bot_id,
                ),
            )
        )

        # ---------- RANGOS DE EQUIPO ----------
        columnas_equipo = [
            "vida",
            "vida_maxima",
            "dano",
            "dano_maximo",
            "defensa",
            "defensa_maxima",
            "cansancio",
            "cansancio_maximo",
            "puntos_habilidad",
            "casco",
            "guantes",
            "protector_bucal",
            "short",
            "botas",
        ]

        filas = (await sesion.execute(
            select(
                *(getattr(BoxEquipo, col) for col in columnas_equipo)
            ).where(
                BoxEquipo.guild_id == guild_id,
                BoxEquipo.user_id != bot_id,
            )
        )).all()

        rangos_equipo: dict[str, tuple[int, int]] = {}
        valores: dict[str, int] = {}

        if not filas:
            # Sin jugadores: usar valores iniciales (determinístico)
            valores = {
                "vida": BOX_VIDA_INICIAL,
                "vida_maxima": BOX_VIDA_INICIAL,
                "dano": BOX_DANO_INICIAL,
                "dano_maximo": BOX_DANO_MAXIMO,
                "defensa": BOX_DEFENSA_INICIAL,
                "defensa_maxima": BOX_DEFENSA_MAXIMO,
                "cansancio": BOX_CANSANCIO_INICIAL,
                "cansancio_maximo": BOX_CANSANCIO_INICIAL,
                "puntos_habilidad": 0,
                "casco": 0,
                "guantes": 0,
                "protector_bucal": 0,
                "short": 0,
                "botas": 0,
            }
            for col in columnas_equipo:
                rangos_equipo[col] = (valores[col], valores[col])
        else:
            # Calcular min/max por columna entre todos los jugadores
            for idx, col in enumerate(columnas_equipo):
                col_vals = [fila[idx] for fila in filas]
                mn = min(col_vals)
                mx = max(col_vals)
                if mn > mx:
                    mn, mx = mx, mn
                rangos_equipo[col] = (mn, mx)
                valores[col] = random.randint(mn, mx)

            # Consistencia: vida/cansancio/defensa/dano no pueden superar su máximo
            if valores["vida"] > valores["vida_maxima"]:
                valores["vida"] = valores["vida_maxima"]
            if valores["cansancio"] > valores["cansancio_maximo"]:
                valores["cansancio"] = valores["cansancio_maximo"]
            if valores["defensa"] > valores["defensa_maxima"]:
                valores["defensa"] = valores["defensa_maxima"]
            if valores["dano"] > valores["dano_maximo"]:
                valores["dano"] = valores["dano_maximo"]

        bot_equipo = await sesion.get(BoxEquipo, (guild_id, bot_id))

        for col in columnas_equipo:
            setattr(bot_equipo, col, valores[col])

        # ---------- RANGO DE EXPERIENCIA ----------
        exps = (await sesion.execute(
            select(
                func.coalesce(BoxUsuario.experiencia, 0)
            ).where(
                BoxUsuario.guild_id == guild_id,
                BoxUsuario.user_id != bot_id,
            )
        )).all()

        if exps:
            vals_exp = [fila[0] for fila in exps]
            min_exp = min(vals_exp)
            max_exp = max(vals_exp)
            bot_exp = random.randint(min_exp, max_exp)
            rango_exp = (min_exp, max_exp)
        else:
            bot_exp = 0
            rango_exp = (0, 0)

        bot_usuario.experiencia = bot_exp

        # ---------- RANGO DE MEJORAS ----------
        filas_mejoras = (await sesion.execute(
            select(
                BoxMejora.mejora,
                BoxMejora.nivel,
            ).where(
                BoxMejora.guild_id == guild_id,
                BoxMejora.user_id != bot_id,
            )
        )).all()

        grupos: dict[str, list[int]] = defaultdict(list)
        for mejora, nivel in filas_mejoras:
            grupos[mejora].append(nivel)

        rangos_mejoras: dict[str, tuple[int, int]] = {}
        niveles_bot: dict[str, int] = {}

        for mejora_tipo in ("entrenamiento", "trabajo"):
            niveles = grupos.get(mejora_tipo, [])
            if niveles:
                mn = min(niveles)
                mx = max(niveles)
                rangos_mejoras[mejora_tipo] = (mn, mx)
                niveles_bot[mejora_tipo] = random.randint(mn, mx)
            else:
                rangos_mejoras[mejora_tipo] = (0, 0)
                niveles_bot[mejora_tipo] = 0

            await sesion.execute(
                delete(BoxMejora).where(
                    BoxMejora.guild_id == guild_id,
                    BoxMejora.user_id == bot_id,
                    BoxMejora.mejora == mejora_tipo,
                )
            )
            if niveles_bot[mejora_tipo] > 0:
                sesion.add(
                    BoxMejora(
                        guild_id=guild_id,
                        user_id=bot_id,
                        mejora=mejora_tipo,
                        nivel=niveles_bot[mejora_tipo],
                    )
                )

        await sesion.commit()

        return {
            "valores": valores,
            "rangos_equipo": rangos_equipo,
            "experiencia": bot_exp,
            "rango_experiencia": rango_exp,
            "niveles_mejora": niveles_bot,
            "rangos_mejora": rangos_mejoras,
        }


async def obtener_equipo(guild_id: int, user_id: int):
    """Devuelve el equipo del usuario, inicializando si es necesario."""

    async with crear_sesion() as sesion:
        await _asegurar_equipo(sesion, guild_id, user_id)

        equipo = await sesion.get(BoxEquipo, (guild_id, user_id))

        await sesion.commit()

        if equipo is None:
            return None

        return {
            "vida": equipo.vida,
            "vida_maxima": equipo.vida_maxima,
            "dano": equipo.dano,
            "dano_maximo": equipo.dano_maximo,
            "defensa": equipo.defensa,
            "defensa_maxima": equipo.defensa_maxima,
            "cansancio": equipo.cansancio,
            "cansancio_maximo": equipo.cansancio_maximo,
            "puntos_habilidad": equipo.puntos_habilidad,
            "casco": equipo.casco,
            "guantes": equipo.guantes,
            "protector_bucal": equipo.protector_bucal,
            "short": equipo.short,
            "botas": equipo.botas,
        }


async def actualizar_equipo(
    guild_id: int,
    user_id: int,
    vida: int | None = None,
    dano: int | None = None,
    defensa: int | None = None,
    cansancio: int | None = None,
    puntos_habilidad: int | None = None,
    casco: str | None = None,
    guantes: str | None = None,
    protector_bucal: str | None = None,
    short: str | None = None,
    botas: str | None = None,
):
    """Actualiza estadísticas o equipamiento del usuario."""

    valores = {}

    for nombre, valor in (
        ("vida", vida),
        ("dano", dano),
        ("defensa", defensa),
        ("cansancio", cansancio),
        ("puntos_habilidad", puntos_habilidad),
        ("casco", casco),
        ("guantes", guantes),
        ("protector_bucal", protector_bucal),
        ("short", short),
        ("botas", botas),
    ):
        if valor is not None:
            valores[nombre] = valor

    if not valores:
        return False

    async with crear_sesion() as sesion:
        await sesion.execute(
            update(BoxEquipo)
            .where(
                BoxEquipo.guild_id == guild_id,
                BoxEquipo.user_id == user_id,
            )
            .values(**valores)
            .execution_options(synchronize_session=False)
        )
        await sesion.commit()

    return True


async def comprar_equipamiento_progresivo(
    guild_id: int,
    user_id: int,
    tipo_equipo: str,
    precio_base: int,
    nivel_maximo: int = 4,
):
    """Compra un nivel de equipamiento progresivamente (cada mejora cuesta el doble)."""

    if not hasattr(BoxEquipo, tipo_equipo):
        return "objetivo_invalido", 0, 0

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, user_id)
        await _asegurar_equipo(sesion, guild_id, user_id)

        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))
        equipo = await sesion.get(BoxEquipo, (guild_id, user_id))

        saldo = usuario.dinero
        nivel_actual = getattr(equipo, tipo_equipo)

        # Calcular precio: precio_base * 2^nivel
        precio = precio_base * (2 ** nivel_actual)

        if nivel_actual >= nivel_maximo:
            return "maximo", saldo, nivel_actual

        if saldo < precio:
            return "insuficiente", saldo, nivel_actual

        usuario.dinero = usuario.dinero - precio
        setattr(equipo, tipo_equipo, nivel_actual + 1)

        await sesion.commit()

    return "comprado", saldo - precio, nivel_actual + 1


# ============================================================
# ADMINISTRACIÓN
# ============================================================

async def admin_obtener_info_usuario(
    guild_id: int,
    user_id: int,
):
    """Devuelve toda la información administrativa del Box."""

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, user_id)
        await sesion.commit()

    async with crear_sesion() as sesion:
        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))

        filas_mejoras = (await sesion.execute(
            select(
                BoxMejora.mejora,
                BoxMejora.nivel,
            )
            .where(
                BoxMejora.guild_id == guild_id,
                BoxMejora.user_id == user_id,
            )
            .order_by(BoxMejora.mejora)
        )).all()

        accion = (await sesion.execute(
            select(
                BoxAccion.tipo,
                BoxAccion.iniciado_en,
                BoxAccion.finaliza_en,
                BoxAccion.recompensa,
                BoxAccion.dinero_recompensa,
            ).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == user_id,
            )
        )).first()

        sponsors = (await sesion.execute(
            select(
                BoxSponsor.id,
                BoxSponsor.tipo,
                BoxSponsor.obtenido_en,
                BoxSponsor.expira_en,
                BoxSponsor.ultimo_pago,
                BoxSponsor.ultimo_tratamiento,
            )
            .where(
                BoxSponsor.guild_id == guild_id,
                BoxSponsor.user_id == user_id,
                BoxSponsor.expira_en > _ahora(),
            )
            .order_by(BoxSponsor.expira_en.asc())
        )).all()

        fila_equipo = (await sesion.execute(
            select(
                BoxEquipo.vida,
                BoxEquipo.vida_maxima,
                BoxEquipo.dano,
                BoxEquipo.dano_maximo,
                BoxEquipo.defensa,
                BoxEquipo.defensa_maxima,
                BoxEquipo.cansancio,
                BoxEquipo.cansancio_maximo,
                BoxEquipo.puntos_habilidad,
                BoxEquipo.casco,
                BoxEquipo.guantes,
                BoxEquipo.protector_bucal,
                BoxEquipo.short,
                BoxEquipo.botas,
            ).where(
                BoxEquipo.guild_id == guild_id,
                BoxEquipo.user_id == user_id,
            )
        )).first()

        desafios_pendientes = (await sesion.execute(
            select(func.count()).where(
                BoxDesafio.guild_id == guild_id,
                or_(
                    BoxDesafio.retador_id == user_id,
                    BoxDesafio.contrincante_id == user_id,
                ),
            )
        )).scalar_one()

        participaciones = (await sesion.execute(
            select(func.count()).where(
                BoxDesafioHistorial.guild_id == guild_id,
                or_(
                    BoxDesafioHistorial.retador_id == user_id,
                    BoxDesafioHistorial.contrincante_id == user_id,
                ),
            )
        )).scalar_one()

        victorias = (await sesion.execute(
            select(func.count()).where(
                BoxDesafioHistorial.guild_id == guild_id,
                BoxDesafioHistorial.ganador_id == user_id,
            )
        )).scalar_one()

    return {
        "experiencia": usuario.experiencia,
        "dinero": usuario.dinero,
        "probabilidad_lesion": usuario.probabilidad_lesion,
        "lesionado_hasta": usuario.lesionado_hasta,
        "mejoras": dict(filas_mejoras),
        "accion": accion,
        "sponsors": sponsors,
        "equipo": fila_equipo,
        "desafios_pendientes": desafios_pendientes,
        "participaciones": participaciones,
        "victorias": victorias,
    }


async def admin_modificar_dinero(
    guild_id: int,
    user_id: int,
    cantidad: int,
):
    """Modifica el dinero de un usuario."""

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, user_id)

        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))
        saldo_actual = usuario.dinero

        nuevo_saldo = saldo_actual + cantidad

        if nuevo_saldo < 0:
            return False, saldo_actual

        usuario.dinero = nuevo_saldo
        await sesion.commit()

    return True, nuevo_saldo


async def admin_modificar_experiencia(
    guild_id: int,
    user_id: int,
    cantidad: int,
):
    """Modifica la experiencia de un usuario."""

    async with crear_sesion() as sesion:
        await _asegurar_usuario(sesion, guild_id, user_id)

        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))
        experiencia_actual = usuario.experiencia

        nueva_experiencia = experiencia_actual + cantidad

        if nueva_experiencia < 0:
            return False, experiencia_actual

        usuario.experiencia = nueva_experiencia
        await sesion.commit()

    return True, nueva_experiencia


async def admin_curar_usuario(
    guild_id: int,
    user_id: int,
):
    """Elimina la lesión activa de un usuario."""

    async with crear_sesion() as sesion:
        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))

        if usuario is None:
            return False, None

        lesionado_hasta = usuario.lesionado_hasta

        if lesionado_hasta is None:
            return False, None

        usuario.lesionado_hasta = None
        await sesion.commit()

    return True, lesionado_hasta


async def admin_modificar_probabilidad_lesion(
    guild_id: int,
    user_id: int,
    probabilidad: float,
):
    """Establece manualmente la probabilidad de lesión."""

    if not 0 <= probabilidad <= BOX_LESION_PROBABILIDAD_MAXIMA:
        return False, None

    async with crear_sesion() as sesion:
        usuario = await sesion.get(BoxUsuario, (guild_id, user_id))

        if usuario is None:
            sesion.add(
                BoxUsuario(
                    guild_id=guild_id,
                    user_id=user_id,
                    probabilidad_lesion=probabilidad,
                )
            )
        else:
            usuario.probabilidad_lesion = probabilidad

        await sesion.commit()

    return True, probabilidad


async def admin_cancelar_accion(
    guild_id: int,
    user_id: int,
):
    """Cancela la acción activa de un usuario."""

    async with crear_sesion() as sesion:
        accion = (await sesion.execute(
            select(
                BoxAccion.tipo,
                BoxAccion.iniciado_en,
                BoxAccion.finaliza_en,
                BoxAccion.recompensa,
                BoxAccion.dinero_recompensa,
            ).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == user_id,
            )
        )).first()

        if accion is None:
            return None

        await sesion.execute(
            delete(BoxAccion).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == user_id,
            )
        )

        await sesion.commit()

    return accion


async def admin_dar_sponsor(
    guild_id: int,
    user_id: int,
    tipo: str,
    ahora: datetime,
):
    """Otorga manualmente un sponsor respetando sus límites."""

    if tipo not in DURACION_SPONSOR:
        return False, "tipo_invalido"

    async with crear_sesion() as sesion:
        creado = await _crear_sponsor(
            sesion,
            guild_id,
            user_id,
            tipo,
            ahora,
        )

        if not creado:
            return False, "limite"

        await sesion.commit()

    return True, None


async def admin_quitar_sponsor(
    guild_id: int,
    user_id: int,
    sponsor_id: int,
):
    """Elimina un sponsor específico."""

    async with crear_sesion() as sesion:
        sponsor = (await sesion.execute(
            select(
                BoxSponsor.id,
                BoxSponsor.tipo,
            ).where(
                BoxSponsor.id == sponsor_id,
                BoxSponsor.guild_id == guild_id,
                BoxSponsor.user_id == user_id,
            )
        )).first()

        if sponsor is None:
            return None

        await sesion.execute(
            delete(BoxSponsor).where(BoxSponsor.id == sponsor_id)
        )

        await sesion.commit()

    return sponsor


async def admin_reset_usuario(
    guild_id: int,
    user_id: int,
):
    """
    Resetea completamente el progreso Box del usuario.

    No modifica ningún dato de Madrugue ni SSF.
    """

    async with crear_sesion() as sesion:
        eliminados = {}

        resultado = await sesion.execute(
            delete(BoxAccion).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == user_id,
            )
        )
        eliminados["box_acciones"] = resultado.rowcount

        resultado = await sesion.execute(
            delete(BoxDesafio).where(
                BoxDesafio.guild_id == guild_id,
                or_(
                    BoxDesafio.retador_id == user_id,
                    BoxDesafio.contrincante_id == user_id,
                ),
            )
        )
        eliminados["box_desafios"] = resultado.rowcount

        resultado = await sesion.execute(
            delete(BoxMejora).where(
                BoxMejora.guild_id == guild_id,
                BoxMejora.user_id == user_id,
            )
        )
        eliminados["box_mejoras"] = resultado.rowcount

        resultado = await sesion.execute(
            delete(BoxSponsor).where(
                BoxSponsor.guild_id == guild_id,
                BoxSponsor.user_id == user_id,
            )
        )
        eliminados["box_sponsors"] = resultado.rowcount

        resultado = await sesion.execute(
            delete(BoxDesafioHistorial).where(
                BoxDesafioHistorial.guild_id == guild_id,
                or_(
                    BoxDesafioHistorial.retador_id == user_id,
                    BoxDesafioHistorial.contrincante_id == user_id,
                    BoxDesafioHistorial.ganador_id == user_id,
                ),
            )
        )
        eliminados["box_desafios_historial"] = resultado.rowcount

        resultado = await sesion.execute(
            delete(BoxEquipo).where(
                BoxEquipo.guild_id == guild_id,
                BoxEquipo.user_id == user_id,
            )
        )
        eliminados["box_equipo"] = resultado.rowcount

        resultado = await sesion.execute(
            delete(BoxUsuario).where(
                BoxUsuario.guild_id == guild_id,
                BoxUsuario.user_id == user_id,
            )
        )
        eliminados["box_usuarios"] = resultado.rowcount

        await sesion.commit()

    return eliminados


# ============================================================
# CONSULTAS GLOBALES (SOLO ADMINISTRADORES)
# ============================================================

async def admin_obtener_top_box(
    guild_id: int,
    limite: int = 10,
):
    """Devuelve el ranking del servidor por experiencia y dinero."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                BoxUsuario.user_id,
                BoxUsuario.experiencia,
                BoxUsuario.dinero,
            )
            .where(BoxUsuario.guild_id == guild_id)
            .order_by(
                BoxUsuario.experiencia.desc(),
                BoxUsuario.dinero.desc(),
            )
            .limit(limite)
        )).all()

    return filas


async def admin_obtener_estadisticas_box(guild_id: int):
    """Devuelve estadísticas globales de Box del servidor."""

    ahora = _ahora()

    async with crear_sesion() as sesion:

        jugadores = (await sesion.execute(
            select(func.count()).where(
                BoxUsuario.guild_id == guild_id
            )
        )).scalar_one()

        experiencia, dinero = (await sesion.execute(
            select(
                func.coalesce(func.sum(BoxUsuario.experiencia), 0),
                func.coalesce(func.sum(BoxUsuario.dinero), 0),
            ).where(BoxUsuario.guild_id == guild_id)
        )).one()

        acciones_activas = (await sesion.execute(
            select(func.count()).where(
                BoxAccion.guild_id == guild_id
            )
        )).scalar_one()

        sponsors_activos = (await sesion.execute(
            select(func.count()).where(
                BoxSponsor.guild_id == guild_id,
                BoxSponsor.expira_en > ahora,
            )
        )).scalar_one()

        combates = (await sesion.execute(
            select(func.count()).where(
                BoxDesafioHistorial.guild_id == guild_id
            )
        )).scalar_one()

        pendientes = (await sesion.execute(
            select(func.count()).where(
                BoxDesafio.guild_id == guild_id
            )
        )).scalar_one()

        lesionados = (await sesion.execute(
            select(func.count()).where(
                BoxUsuario.guild_id == guild_id,
                BoxUsuario.lesionado_hasta.is_not(None),
                BoxUsuario.lesionado_hasta > ahora,
            )
        )).scalar_one()

    return {
        "jugadores": jugadores,
        "experiencia": experiencia,
        "dinero": dinero,
        "acciones_activas": acciones_activas,
        "sponsors_activos": sponsors_activos,
        "combates": combates,
        "pendientes": pendientes,
        "lesionados": lesionados,
    }


async def admin_obtener_historial_desafios(
    guild_id: int,
    user_id: int,
    limite: int = 10,
):
    """Devuelve los últimos combates de un usuario."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                BoxDesafioHistorial.creado_en,
                BoxDesafioHistorial.retador_id,
                BoxDesafioHistorial.contrincante_id,
                BoxDesafioHistorial.ganador_id,
            )
            .where(
                BoxDesafioHistorial.guild_id == guild_id,
                or_(
                    BoxDesafioHistorial.retador_id == user_id,
                    BoxDesafioHistorial.contrincante_id == user_id,
                ),
            )
            .order_by(BoxDesafioHistorial.creado_en.desc())
            .limit(limite)
        )).all()

    return filas


async def admin_obtener_lesionados(
    guild_id: int,
    ahora: datetime,
):
    """Devuelve los usuarios con lesión activa o probabilidad acumulada."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                BoxUsuario.user_id,
                BoxUsuario.probabilidad_lesion,
                BoxUsuario.lesionado_hasta,
            )
            .where(
                BoxUsuario.guild_id == guild_id,
                or_(
                    BoxUsuario.probabilidad_lesion > 0,
                    (
                        BoxUsuario.lesionado_hasta.is_not(None)
                        & (BoxUsuario.lesionado_hasta > ahora)
                    ),
                ),
            )
            .order_by(
                BoxUsuario.lesionado_hasta.desc(),
                BoxUsuario.probabilidad_lesion.desc(),
            )
        )).all()

    return filas


# ============================================================
# COMBATES EN VIVO
# ============================================================
#
# Un combate es el relato de un desafío aceptado: se resuelve acá, al aceptar,
# y el narrador del cog lo va revelando asalto por asalto. Se guarda el plan
# serializado (no el texto de cada línea) para que el resultado sea
# reproducible y un reinicio del bot no escriba una versión alternativa de la
# pelea en el canal.

ESTADO_VIVO = "VIVO"
ESTADO_TERMINADO = "TERMINADO"
ESTADO_CANCELADO = "CANCELADO"


async def _fila_estadisticas_combate(sesion, guild_id: int, user_id: int) -> dict:
    """Vida, daño, defensa y equipamiento de un peleador, listos para simular.

    ``box_equipo`` guardaba los niveles de casco, guantes, bucal, short y botas
    como una etiqueta de la tienda: ningún desafío los leía y comprar no servía
    de nada arriba del ring. Acá se convierten en los números que entiende el
    motor (ver ``logic.estadisticas_de_combate``), con el techo que pone
    ``BOX_COMBATE_EQUIPO_POR_NIVEL``.

    El ``cansancio`` actual no entra a propósito: hoy ninguna acción lo baja,
    así que siempre está en su máximo y usarlo sería decorativo. Cuando pelear
    desgaste la fila, ahí vale la pena.
    """

    fila = (await sesion.execute(
        select(
            BoxEquipo.vida_maxima,
            BoxEquipo.dano,
            BoxEquipo.defensa,
            BoxEquipo.casco,
            BoxEquipo.guantes,
            BoxEquipo.protector_bucal,
            BoxEquipo.short,
            BoxEquipo.botas,
        ).where(
            BoxEquipo.guild_id == guild_id,
            BoxEquipo.user_id == user_id,
        )
    )).first()

    base = {
        "vida_maxima": BOX_VIDA_INICIAL,
        "dano": BOX_DANO_INICIAL,
        "defensa": BOX_DEFENSA_INICIAL,
    }
    niveles = {}

    if fila is not None:
        base = {
            "vida_maxima": fila[0] or BOX_VIDA_INICIAL,
            "dano": fila[1] or BOX_DANO_INICIAL,
            "defensa": fila[2] or BOX_DEFENSA_INICIAL,
        }
        niveles = dict(
            zip(
                ("casco", "guantes", "protector_bucal", "short", "botas"),
                fila[3:8],
            )
        )

    return estadisticas_de_combate(base, niveles)


async def _crear_combate(
    sesion,
    guild_id: int,
    *,
    modo: str,
    retador_id: int,
    contrincante_id: int,
    experiencias: dict,
    ganador_id: int | None,
    ahora: datetime,
    canal_id: int | None = None,
):
    """Resuelve el combate y lo registra, dentro de la transacción abierta.

    ``ganador_id`` es el que ya sorteó el desafío: la narración se arma
    acondicionada a ese resultado, así el relato y la recompensa que paga
    ``_liquidar_accion`` nunca se contradicen. En el sparring no hay ganador
    y tampoco hay premio.
    """

    if not BOX_COMBATE_ACTIVO:
        return None

    equipos = {
        user_id: await _fila_estadisticas_combate(sesion, guild_id, user_id)
        for user_id in (retador_id, contrincante_id)
    }

    semilla = random.SystemRandom().randrange(1 << 30)

    forzado = None

    if ganador_id == retador_id:
        forzado = 0
    elif ganador_id == contrincante_id:
        forzado = 1

    comunes = dict(
        nombres=("Retador", "Contrincante"),
        experiencia=(
            experiencias.get(retador_id, 0),
            experiencias.get(contrincante_id, 0),
        ),
        vida_maxima=(
            equipos[retador_id]["vida_maxima"],
            equipos[contrincante_id]["vida_maxima"],
        ),
        dano=(equipos[retador_id]["dano"], equipos[contrincante_id]["dano"]),
        defensa=(
            equipos[retador_id]["defensa"],
            equipos[contrincante_id]["defensa"],
        ),
        semilla=semilla,
        fatiga=(
            equipos[retador_id]["fatiga"],
            equipos[contrincante_id]["fatiga"],
        ),
        bono_fuerza=(
            equipos[retador_id]["fuerza"],
            equipos[contrincante_id]["fuerza"],
        ),
    )

    if modo == "FIGHTING":
        plan = planificar_pelea(ganador_forzado=forzado, **comunes)
    else:
        plan = planificar_sparring(**comunes)

    latidos = max(1, plan.latidos)

    combate = BoxCombate(
        guild_id=guild_id,
        canal_id=canal_id,
        modo=modo,
        retador_id=retador_id,
        contrincante_id=contrincante_id,
        semilla=semilla,
        plan=plan.a_json(),
        iniciado_en=ahora,
        latido_segundos=BOX_COMBATE_TICK_SEGUNDOS,
        latidos_totales=latidos,
        fin_narracion_en=(
            ahora + timedelta(seconds=latidos * BOX_COMBATE_TICK_SEGUNDOS)
        ),
        estado=ESTADO_VIVO,
    )
    sesion.add(combate)
    await sesion.flush()

    return combate.id


async def _hay_combate_vivo(sesion, guild_id: int | None):
    """Fila del combate en curso, leída dentro de una transacción abierta."""

    condiciones = [BoxCombate.estado == ESTADO_VIVO]

    if guild_id is not None:
        condiciones.append(BoxCombate.guild_id == guild_id)

    return (await sesion.execute(
        select(
            BoxCombate.id,
            BoxCombate.guild_id,
            BoxCombate.retador_id,
            BoxCombate.contrincante_id,
            BoxCombate.modo,
        )
        .where(*condiciones)
        .order_by(BoxCombate.id.desc())
        .limit(1)
    )).first()


async def combate_en_curso(guild_id: int | None = None):
    """El único combate que puede haber a la vez, o ``None``.

    El candado existe porque el canal de Box es uno: dos peleas narrándose
    juntas se pisan mensaje a mensaje y el reloj de cada una deja de tener
    sentido. ``BOX_COMBATE_UNICO_GLOBAL`` define el alcance: con 1 es una pelea
    por bot (la suposición real: servidores privados de poca gente), con 0 una
    por servidor.
    """

    async with crear_sesion() as sesion:
        fila = await _hay_combate_vivo(
            sesion,
            None if BOX_COMBATE_UNICO_GLOBAL else guild_id,
        )

    if fila is None:
        return None

    return {
        "id": fila[0],
        "guild_id": fila[1],
        "retador_id": fila[2],
        "contrincante_id": fila[3],
        "modo": fila[4],
    }


async def obtener_canticos(guild_id: int):
    """Si el servidor consintió los cánticos que nombran miembros reales.

    ``None`` significa "nadie decidió todavía", y el narrador cae al valor de
    ``BOX_COMBATE_CANTICOS``. Se pidió una decisión por servidor -y no un
    global- porque el cántico tira el apodo de una persona al aire: en un grupo
    chico, acordado entre todos, está bien; usado a escondidas en un canal de
    cuatrocientos, no.
    """

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(BoxConfigGuild.canticos).where(
                BoxConfigGuild.guild_id == guild_id
            )
        )).first()

    if fila is None or fila[0] is None:
        return None

    return bool(fila[0])


async def fijar_canticos(
    guild_id: int,
    activado: bool,
    moderador_id: int,
    ahora: datetime,
) -> None:
    """Guarda la decisión del servidor sobre los cánticos."""

    async with crear_sesion() as sesion:
        config = await sesion.get(BoxConfigGuild, guild_id)

        if config is None:
            sesion.add(
                BoxConfigGuild(
                    guild_id=guild_id,
                    canticos=int(bool(activado)),
                    actualizado_en=ahora,
                    actualizado_por=moderador_id,
                )
            )
        else:
            config.canticos = int(bool(activado))
            config.actualizado_en = ahora
            config.actualizado_por = moderador_id

        await sesion.commit()


async def obtener_combates_vivos(ahora: datetime, guild_id: int | None = None):
    """Combates en vivo, listos para el latido del narrador.

    Se devuelven también los que ya vencieron: hay que cerrarlos y asentar el
    resultado, si no quedarían marcados como vivos para siempre.
    """

    condiciones = [BoxCombate.estado == ESTADO_VIVO]

    if guild_id is not None:
        condiciones.append(BoxCombate.guild_id == guild_id)

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                BoxCombate.id,
                BoxCombate.guild_id,
                BoxCombate.canal_id,
                BoxCombate.modo,
                BoxCombate.retador_id,
                BoxCombate.contrincante_id,
                BoxCombate.plan,
                BoxCombate.iniciado_en,
                BoxCombate.latido_segundos,
                BoxCombate.latidos_totales,
                BoxCombate.fin_narracion_en,
                BoxCombate.estado,
                BoxCombate.mensaje_id,
            )
            .where(*condiciones)
            .order_by(BoxCombate.iniciado_en)
        )).all()

    combatientes = []

    for fila in filas:
        combatientes.append(
            {
                "id": fila[0],
                "guild_id": fila[1],
                "canal_id": fila[2],
                "modo": fila[3],
                "retador_id": fila[4],
                "contrincante_id": fila[5],
                "plan": fila[6],
                "iniciado_en": fila[7],
                "latido_segundos": fila[8],
                "latidos_totales": fila[9],
                "fin_narracion_en": fila[10],
                "estado": fila[11],
                "mensaje_id": fila[12],
            }
        )

    return combatientes


def latido_de(combate: dict, ahora: datetime) -> int:
    """Cuántos latidos pasaron desde que empezó el combate."""

    segundos = (ahora - combate["iniciado_en"]).total_seconds()

    # Un reloj atrasado (arranque antes de sincronizar el horario, por
    # ejemplo) no puede dar un latido negativo: el combate recién empieza.
    return max(0, int(segundos // max(1, combate["latido_segundos"])))


async def asaltos_publicados(combate_id: int) -> set:
    """Asaltos que ya tienen su mensaje en el canal."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(BoxCombateAsalto.asalto).where(
                BoxCombateAsalto.combate_id == combate_id
            )
        )).all()

    return {fila[0] for fila in filas}


async def mensaje_de_asalto(combate_id: int, asalto: int):
    """Mensaje del asalto, si ya fue publicado."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(BoxCombateAsalto.mensaje_id).where(
                BoxCombateAsalto.combate_id == combate_id,
                BoxCombateAsalto.asalto == asalto,
            )
        )).first()

    return fila[0] if fila else None


async def reclamar_asalto(combate_id: int, asalto: int, ahora: datetime) -> bool:
    """Marca el asalto como propio; ``False`` si ya lo estaba publicando otro.

    Es el seguro contra dobles envíos: el tick, un retry de Discord o el
    catch-up después de un reinicio pueden pedir el mismo asalto, y solo uno
    de los tres gana la carrera.
    """

    async with crear_sesion() as sesion:
        sesion.add(
            BoxCombateAsalto(
                combate_id=combate_id,
                asalto=asalto,
                publicado_en=ahora,
            )
        )

        try:
            await sesion.commit()
        except IntegrityError:
            await sesion.rollback()
            return False

    return True


async def registrar_mensaje_asalto(
    combate_id: int,
    asalto: int,
    mensaje_id: int,
    ahora: datetime,
):
    """Guarda el mensaje de un asalto (o lo reemplaza si fue borrado)."""

    async with crear_sesion() as sesion:
        fila = await sesion.get(
            BoxCombateAsalto,
            (combate_id, asalto),
        )

        if fila is None:
            sesion.add(
                BoxCombateAsalto(
                    combate_id=combate_id,
                    asalto=asalto,
                    mensaje_id=mensaje_id,
                    publicado_en=ahora,
                )
            )
        else:
            fila.mensaje_id = mensaje_id
            fila.publicado_en = ahora

        await sesion.commit()


async def actualizar_mensaje_combate(combate_id: int, mensaje_id: int):
    """Recuerda el último mensaje del combate, para poder editarlo."""

    async with crear_sesion() as sesion:
        await sesion.execute(
            update(BoxCombate)
            .where(BoxCombate.id == combate_id)
            .values(mensaje_id=mensaje_id)
            .execution_options(synchronize_session=False)
        )
        await sesion.commit()


async def cerrar_combate(
    combate_id: int,
    estado: str,
    ahora: datetime,
    resumen: str | None = None,
):
    """Cierra un combate: ya no se narra más."""

    async with crear_sesion() as sesion:
        combate = await sesion.get(BoxCombate, combate_id)

        if combate is not None:
            combate.estado = estado
            combate.terminado_en = ahora

            if resumen is not None:
                combate.resumen = resumen

            await sesion.commit()


async def tiene_accion_activa(guild_id: int, user_id: int) -> bool:
    """Indica si el usuario sigue con la acción del desafío en curso.

    El narrador lo consulta en cada latido: si un administrador finalizó o
    canceló la acción, el combate hay que cerrarlo, si no quedaría narrando
    para siempre una pelea que ya no existe.
    """

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(1).where(
                BoxAccion.guild_id == guild_id,
                BoxAccion.user_id == user_id,
            )
        )).first()

    return fila is not None


async def obtener_combate_en_curso(guild_id: int, user_id: int):
    """Combate vivo en el que participa el usuario, para /box combate."""

    async with crear_sesion() as sesion:
        fila = (await sesion.execute(
            select(
                BoxCombate.id,
                BoxCombate.plan,
                BoxCombate.iniciado_en,
                BoxCombate.latido_segundos,
                BoxCombate.latidos_totales,
                BoxCombate.modo,
                BoxCombate.retador_id,
                BoxCombate.contrincante_id,
                BoxCombate.fin_narracion_en,
            )
            .where(
                BoxCombate.guild_id == guild_id,
                BoxCombate.estado == ESTADO_VIVO,
                or_(
                    BoxCombate.retador_id == user_id,
                    BoxCombate.contrincante_id == user_id,
                ),
            )
            .order_by(BoxCombate.iniciado_en.desc())
            .limit(1)
        )).first()

    if fila is None:
        return None

    return {
        "id": fila[0],
        "plan": fila[1],
        "iniciado_en": fila[2],
        "latido_segundos": fila[3],
        "latidos_totales": fila[4],
        "modo": fila[5],
        # El guild_id no está en la consulta porque es el filtro; se completa
        # acá para que el diccionario tenga la misma forma que devuelve
        # ``obtener_combates_vivos`` y el narrador pueda consumirlo igual.
        "guild_id": guild_id,
        "retador_id": fila[6],
        "contrincante_id": fila[7],
        "fin_narracion_en": fila[8],
    }


async def ultimos_combates(guild_id: int, limite: int = 5):
    """Últimos combates narrados del servidor, para el historial."""

    async with crear_sesion() as sesion:
        filas = (await sesion.execute(
            select(
                BoxCombate.id,
                BoxCombate.modo,
                BoxCombate.retador_id,
                BoxCombate.contrincante_id,
                BoxCombate.estado,
                BoxCombate.resumen,
                BoxCombate.fin_narracion_en,
            )
            .where(BoxCombate.guild_id == guild_id)
            .order_by(BoxCombate.id.desc())
            .limit(limite)
        )).all()

    return [
        {
            "id": fila[0],
            "modo": fila[1],
            "retador_id": fila[2],
            "contrincante_id": fila[3],
            "estado": fila[4],
            "resumen": fila[5],
            "fin_narracion_en": fila[6],
        }
        for fila in filas
    ]
