"""Fachada del módulo SeptSinFP.

Los cogs importan desde acá y no directamente de ``database`` ni ``logic``,
igual que en los módulos Madrugue y Box.
"""

from modules.ssf.constants import (
    TEXTO_AYUDA,
)

from modules.ssf.database import (
    crear_desafio,
    eliminar_participante,
    eliminar_registro,
    guardar_registro,
    obtener_desafio_activo,
    obtener_estadisticas_desafio,
    obtener_participante,
    obtener_participantes,
    obtener_registros_usuario,
    obtener_ultimo_desafio,
    registrar_participante,
    tiene_registro,
    actualizar_participante,
    reactivar_participante,
    obtener_desafios_activos,
    obtener_ultima_revision_ssf,
    guardar_ultima_revision_ssf,
    obtener_ranking_final,
    marcar_desafio_cerrado,
)

from modules.ssf.logic import (
    calcular_mejor_racha,
    calcular_racha,
    calcular_rango,
    fecha_dentro_del_desafio,
)



__all__ = [
    # Constantes
    "TEXTO_AYUDA",
    # Lógica pura
    "calcular_mejor_racha",
    "calcular_racha",
    "calcular_rango",
    "fecha_dentro_del_desafio",
    # Desafíos y participantes
    "agregar_dia",
    "cerrar_desafio_activo",
    "cerrar_desafios_finalizados",
    "eliminar_faltantes",
    "eliminar_participante_admin",
    "iniciar_desafio",
    "quitar_dia",
    "recalcular_rachas",
    "obtener_desafio_para_ranking",
    "obtener_estado_desafio",
    "obtener_estado_usuario",
    "obtener_lista_participantes",
    "procesar_eliminaciones_diarias",
    "registrar_sobrevivi",
    "registrar_usuario",
    "revivir_participante",
]


async def iniciar_desafio(
    guild_id,
    nombre,
    fecha_inicio,
    fecha_fin,
    canal_id,
):
    """
    Crea un nuevo desafío.

    No permite crear otro desafío activo en el mismo servidor.
    """

    existente = await obtener_desafio_activo(
        guild_id
    )

    if existente:
        return {
            "exitoso": False,
            "motivo": "ya_existe",
        }

    desafio_id = await crear_desafio(
        guild_id=guild_id,
        nombre=nombre,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        canal_id=canal_id,
    )

    return {
        "exitoso": True,
        "desafio_id": desafio_id,
    }


async def registrar_usuario(
    guild_id,
    user_id,
    username,
    ahora,
):
    """
    Registra un usuario en el desafío activo.
    """

    desafio = await obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    (
        desafio_id,
        _guild_id,
        nombre,
        fecha_inicio,
        fecha_fin,
        canal_id,
        _activo,
    ) = desafio

    fecha = ahora.date()

    if not fecha_dentro_del_desafio(
        fecha,
        fecha_inicio,
        fecha_fin,
    ):
        return {
            "exitoso": False,
            "motivo": "fuera_de_fecha",
            "nombre": nombre,
        }

    participante = await obtener_participante(
        desafio_id,
        user_id,
    )

    if participante is not None:

        if participante[4]:
            return {
                "exitoso": False,
                "motivo": "eliminado",
            }

        return {
            "exitoso": False,
            "motivo": "ya_registrado",
        }

    await registrar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        username=username,
        fecha_registro=ahora,
    )

    # Registrarse cuenta como haber sobrevivido el día. Sin esto, quien se
    # registra el 1/9 y cumple del 2 al 6 quedaba con racha 5 en lugar de 6,
    # porque sólo /ssf sobrevivi creaba entradas en ssf_registros.
    await guardar_registro(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha=fecha,
        hora=ahora.strftime("%H:%M:%S"),
    )

    fechas = [
        registro[0]
        for registro in await obtener_registros_usuario(
            desafio_id,
            user_id,
        )
    ]

    racha = calcular_racha(
        fechas,
        fecha,
    )

    mejor_racha = calcular_mejor_racha(
        fechas
    )

    await actualizar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        racha_actual=racha,
        mejor_racha=mejor_racha,
    )

    return {
        "exitoso": True,
        "motivo": "registrado",
        "nombre": nombre,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "racha": racha,
        "mejor_racha": mejor_racha,
        "rango": calcular_rango(racha),
    }


async def registrar_sobrevivi(
    guild_id,
    user_id,
    ahora,
):
    """
    Registra la supervivencia diaria de un participante.
    """

    desafio = await obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    (
        desafio_id,
        _guild_id,
        nombre,
        fecha_inicio,
        fecha_fin,
        canal_id,
        _activo,
    ) = desafio

    fecha = ahora.date()

    if not fecha_dentro_del_desafio(
        fecha,
        fecha_inicio,
        fecha_fin,
    ):
        return {
            "exitoso": False,
            "motivo": "fuera_de_fecha",
        }

    participante = await obtener_participante(
        desafio_id,
        user_id,
    )

    if participante is None:
        return {
            "exitoso": False,
            "motivo": "no_participante",
        }

    if participante[4]:
        return {
            "exitoso": False,
            "motivo": "eliminado",
        }

    if await tiene_registro(
        desafio_id,
        user_id,
        fecha,
    ):
        return {
            "exitoso": False,
            "motivo": "ya_registrado",
        }

    await guardar_registro(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha=fecha,
        hora=ahora.strftime("%H:%M:%S"),
    )

    registros = await obtener_registros_usuario(
        desafio_id,
        user_id,
    )

    fechas = [
        registro[0]
        for registro in registros
    ]

    racha = calcular_racha(
        fechas,
        fecha,
    )

    mejor_racha = calcular_mejor_racha(
        fechas
    )

    await actualizar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        racha_actual=racha,
        mejor_racha=mejor_racha,
    )

    return {
        "exitoso": True,
        "motivo": "sobrevivio",
        "nombre": nombre,
        "racha": racha,
        "mejor_racha": mejor_racha,
        "rango": calcular_rango(racha),
        "fecha": fecha,
        "hora": ahora,
    }


async def obtener_estado_usuario(
    guild_id,
    user_id,
):
    """Obtiene el estado actual de un participante."""

    desafio = await obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    participante = await obtener_participante(
        desafio[0],
        user_id,
    )

    if participante is None:
        return {
            "exitoso": False,
            "motivo": "no_participante",
        }

    return {
        "exitoso": True,
        "nombre": desafio[2],
        "eliminado": bool(participante[4]),
        "fecha_eliminacion": participante[5],
        "racha_actual": participante[6],
        "mejor_racha": participante[7],
        "rango": calcular_rango(participante[6]),
    }


async def eliminar_faltantes(
    guild_id,
    fecha,
):
    """
    Elimina a todos los participantes activos que no
    registraron /SSF sobrevivi durante la fecha indicada.
    """

    desafio = await obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return 0

    desafio_id = desafio[0]

    participantes = await obtener_participantes(
        desafio_id
    )

    eliminados = 0

    for participante in participantes:

        user_id = participante[0]
        eliminado = participante[3]

        if eliminado:
            continue

        if not await tiene_registro(
            desafio_id,
            user_id,
            fecha,
        ):
            await eliminar_participante(
                desafio_id=desafio_id,
                user_id=user_id,
                fecha_eliminacion=fecha,
            )

            eliminados += 1

    return eliminados


async def obtener_estado_desafio(
    guild_id,
):
    """Obtiene las estadísticas del desafío activo."""

    desafio = await obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return None

    total, activos, eliminados = (
        await obtener_estadisticas_desafio(
            desafio[0]
        )
    )

    return {
        "id": desafio[0],
        "nombre": desafio[2],
        "fecha_inicio": desafio[3],
        "fecha_fin": desafio[4],
        "canal_id": desafio[5],
        "total": total,
        "activos": activos,
        "eliminados": eliminados,
    }


async def obtener_lista_participantes(
    guild_id,
):
    """Obtiene los participantes del desafío activo."""

    desafio = await obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return None

    return await obtener_participantes(
        desafio[0]
    )

async def revivir_participante(
    guild_id,
    user_id,
    fecha,
):
    """
    Revive a un participante eliminado y registra
    retroactivamente el día que había perdido.

    La operación está pensada para corregir olvidos,
    problemas de conexión u otros inconvenientes.

    La fecha indicada debe ser un día dentro del desafío.
    """

    desafio = await obtener_desafio_activo(guild_id)

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    (
        desafio_id,
        _guild_id,
        nombre,
        fecha_inicio,
        fecha_fin,
        canal_id,
        _activo,
    ) = desafio

    if not fecha_dentro_del_desafio(
        fecha,
        fecha_inicio,
        fecha_fin,
    ):
        return {
            "exitoso": False,
            "motivo": "fuera_de_fecha",
        }

    participante = await obtener_participante(
        desafio_id,
        user_id,
    )

    if participante is None:
        return {
            "exitoso": False,
            "motivo": "no_participante",
        }

    if not participante[4]:
        return {
            "exitoso": False,
            "motivo": "no_eliminado",
        }

    if await tiene_registro(
        desafio_id,
        user_id,
        fecha,
    ):
        return {
            "exitoso": False,
            "motivo": "ya_registrado",
        }

    # Registrar retroactivamente el día perdido.
    await guardar_registro(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha=fecha,
        hora="ADMIN",
    )

    # Recuperar todas las fechas después del registro.
    registros = await obtener_registros_usuario(
        desafio_id,
        user_id,
    )

    fechas = [
        registro[0]
        for registro in registros
    ]

    racha = calcular_racha(
        fechas,
        fecha,
    )

    mejor_racha = calcular_mejor_racha(
        fechas,
    )

    # El participante vuelve a estar activo.
    await actualizar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        racha_actual=racha,
        mejor_racha=mejor_racha,
    )

    # Quitar estado de eliminado.
    await reactivar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
    )

    return {
        "exitoso": True,
        "motivo": "revivido",
        "nombre": nombre,
        "racha": racha,
        "mejor_racha": mejor_racha,
        "rango": calcular_rango(racha),
        "fecha": fecha,
    }

# ============================================================
# REPARACIÓN MANUAL (SOLO ADMINISTRADORES)
# ============================================================

async def _actualizar_rachas_desde_registros(
    desafio_id,
    user_id,
):
    """
    Recalcula ambas rachas desde los registros guardados.

    Los registros son la fuente de verdad y las rachas
    almacenadas un caché: la racha actual es la racha
    consecutiva que termina en el último día registrado.

    No toca el estado de eliminado del participante.
    """

    registros = await obtener_registros_usuario(
        desafio_id,
        user_id,
    )

    fechas = [
        registro[0]
        for registro in registros
    ]

    if not fechas:
        racha = 0
    else:
        racha = calcular_racha(
            fechas,
            max(fechas),
        )

    mejor_racha = calcular_mejor_racha(
        fechas
    )

    await actualizar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        racha_actual=racha,
        mejor_racha=mejor_racha,
    )

    return (
        racha,
        mejor_racha,
    )


async def agregar_dia(
    guild_id,
    user_id,
    fecha,
    hoy,
):
    """
    Agrega manualmente un día sobrevivido a un participante activo.

    Sirve para corregir olvidos o errores sin revivir a nadie:
    el participante debe estar activo (para eliminados existe
    ``revivir_participante``). No acepta fechas futuras.
    """

    desafio = await obtener_desafio_activo(guild_id)

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    (
        desafio_id,
        _guild_id,
        nombre,
        fecha_inicio,
        fecha_fin,
        _canal_id,
        _activo,
    ) = desafio

    if not fecha_dentro_del_desafio(
        fecha,
        fecha_inicio,
        fecha_fin,
    ):
        return {
            "exitoso": False,
            "motivo": "fuera_de_fecha",
        }

    participante = await obtener_participante(
        desafio_id,
        user_id,
    )

    if participante is None:
        return {
            "exitoso": False,
            "motivo": "no_participante",
        }

    if participante[4]:
        return {
            "exitoso": False,
            "motivo": "eliminado",
        }

    if fecha > hoy:
        return {
            "exitoso": False,
            "motivo": "futura",
        }

    if await tiene_registro(
        desafio_id,
        user_id,
        fecha,
    ):
        return {
            "exitoso": False,
            "motivo": "ya_registrado",
        }

    await guardar_registro(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha=fecha,
        hora="ADMIN",
    )

    racha, mejor_racha = (
        await _actualizar_rachas_desde_registros(
            desafio_id,
            user_id,
        )
    )

    return {
        "exitoso": True,
        "motivo": "agregado",
        "nombre": nombre,
        "racha": racha,
        "mejor_racha": mejor_racha,
        "rango": calcular_rango(racha),
        "fecha": fecha,
    }


async def quitar_dia(
    guild_id,
    user_id,
    fecha,
):
    """
    Quita manualmente un día sobrevivido a un participante.

    Acepta participantes eliminados: quitar un día no cambia
    el estado de eliminado, solo recalcula las rachas desde
    los registros restantes.

    No valida que la fecha esté dentro del desafío ni que no
    sea futura: si existe un registro erróneo, hay que poder
    borrarlo sea cual sea su fecha.
    """

    desafio = await obtener_desafio_activo(guild_id)

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    desafio_id = desafio[0]
    nombre = desafio[2]

    participante = await obtener_participante(
        desafio_id,
        user_id,
    )

    if participante is None:
        return {
            "exitoso": False,
            "motivo": "no_participante",
        }

    if not await tiene_registro(
        desafio_id,
        user_id,
        fecha,
    ):
        return {
            "exitoso": False,
            "motivo": "sin_registro",
        }

    await eliminar_registro(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha=fecha,
    )

    racha, mejor_racha = (
        await _actualizar_rachas_desde_registros(
            desafio_id,
            user_id,
        )
    )

    return {
        "exitoso": True,
        "motivo": "quitado",
        "nombre": nombre,
        "racha": racha,
        "mejor_racha": mejor_racha,
        "rango": calcular_rango(racha),
        "fecha": fecha,
        "eliminado": bool(participante[4]),
    }


async def recalcular_rachas(
    guild_id,
    user_id,
):
    """
    Recalcula las rachas de un participante desde sus registros.

    No cambia el estado de eliminado: sirve para reparar la
    racha mostrada cuando quedó en un valor incorrecto (por
    ejemplo, participantes eliminados por el código anterior
    a la corrección, que pisaba la racha con 0).
    """

    desafio = await obtener_desafio_activo(guild_id)

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    desafio_id = desafio[0]
    nombre = desafio[2]

    participante = await obtener_participante(
        desafio_id,
        user_id,
    )

    if participante is None:
        return {
            "exitoso": False,
            "motivo": "no_participante",
        }

    racha, mejor_racha = (
        await _actualizar_rachas_desde_registros(
            desafio_id,
            user_id,
        )
    )

    return {
        "exitoso": True,
        "motivo": "recalculado",
        "nombre": nombre,
        "racha": racha,
        "mejor_racha": mejor_racha,
        "rango": calcular_rango(racha),
        "eliminado": bool(participante[4]),
    }

# ============================================================
# ELIMINACIÓN AUTOMÁTICA
# ============================================================

async def procesar_eliminaciones_diarias(fecha):
    """
    Procesa la eliminación automática de todos los desafíos
    SSF activos.

    Cada desafío se procesa de manera independiente.
    """

    resultados = []

    desafios = await obtener_desafios_activos()

    for desafio in desafios:

        (
            desafio_id,
            guild_id,
            nombre,
            fecha_inicio,
            fecha_fin,
            canal_id,
            activo,
        ) = desafio

        # ----------------------------------------------------
        # COMPROBAR QUE LA FECHA PERTENECE AL DESAFÍO
        # ----------------------------------------------------

        if not fecha_dentro_del_desafio(
            fecha,
            fecha_inicio,
            fecha_fin,
        ):
            continue

        # ----------------------------------------------------
        # EVITAR PROCESAR DOS VECES LA MISMA FECHA
        # ----------------------------------------------------

        ultima_revision = (
            await obtener_ultima_revision_ssf(
                desafio_id
            )
        )

        if ultima_revision is not None:

            if fecha <= ultima_revision:
                continue

        # ----------------------------------------------------
        # OBTENER PARTICIPANTES
        # ----------------------------------------------------

        participantes = await obtener_participantes(
            desafio_id
        )

        eliminados = []

        for participante in participantes:

            (
                user_id,
                username,
                _fecha_registro,
                eliminado,
                _fecha_eliminacion,
                _racha_actual,
                _mejor_racha,
            ) = participante

            # Ya eliminado → no tocar.
            if eliminado:
                continue

            # Tiene supervivencia → continúa.
            if await tiene_registro(
                desafio_id,
                user_id,
                fecha,
            ):
                continue

            # No registró → eliminar.
            await eliminar_participante(
                desafio_id=desafio_id,
                user_id=user_id,
                fecha_eliminacion=fecha,
            )

            eliminados.append({
                "user_id": user_id,
                "username": username,
            })

        # ----------------------------------------------------
        # GUARDAR FECHA PROCESADA
        # ----------------------------------------------------

        await guardar_ultima_revision_ssf(
            desafio_id=desafio_id,
            fecha=fecha,
        )

        resultados.append({
            "desafio_id": desafio_id,
            "guild_id": guild_id,
            "nombre": nombre,
            "canal_id": canal_id,
            "fecha": fecha,
            "eliminados": eliminados,
        })

    return resultados

# ============================================================
# CIERRE AUTOMÁTICO
# ============================================================

async def cerrar_desafios_finalizados(fecha):
    """
    Cierra automáticamente los desafíos cuya fecha de fin
    ya fue procesada.

    Devuelve la información necesaria para publicar
    el resultado final.
    """

    resultados = []

    desafios = await obtener_desafios_activos()

    for desafio in desafios:

        (
            desafio_id,
            guild_id,
            nombre,
            fecha_inicio,
            fecha_fin,
            canal_id,
            activo,
        ) = desafio

        # ----------------------------------------------------
        # TODAVÍA NO TERMINÓ
        # ----------------------------------------------------

        if fecha <= fecha_fin:
            continue

        # ----------------------------------------------------
        # EL ÚLTIMO DÍA TIENE QUE HABER SIDO PROCESADO
        # ----------------------------------------------------

        ultima_revision = (
            await obtener_ultima_revision_ssf(
                desafio_id
            )
        )

        if ultima_revision is None:
            continue

        if ultima_revision < fecha_fin:
            continue

        # ----------------------------------------------------
        # OBTENER RANKING FINAL
        # ----------------------------------------------------

        ranking = await obtener_ranking_final(
            desafio_id
        )

        total = len(ranking)

        sobrevivientes = [
            participante
            for participante in ranking
            if not participante[2]
        ]

        eliminados = [
            participante
            for participante in ranking
            if participante[2]
        ]

        # ----------------------------------------------------
        # CERRAR DESAFÍO
        # ----------------------------------------------------

        cerrado = await marcar_desafio_cerrado(
            desafio_id
        )

        if cerrado == 0:
            continue

        # ----------------------------------------------------
        # GUARDAR RESULTADO
        # ----------------------------------------------------

        resultados.append({
            "desafio_id": desafio_id,
            "guild_id": guild_id,
            "nombre": nombre,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "canal_id": canal_id,
            "total": total,
            "sobrevivientes": sobrevivientes,
            "eliminados": eliminados,
            "ranking": ranking,
        })

    return resultados

# ============================================================
# ADMINISTRACIÓN MANUAL (SOLO ADMINISTRADORES)
# ============================================================

async def eliminar_participante_admin(
    guild_id,
    user_id,
    fecha,
    hoy,
):
    """Elimina manualmente a un participante que faltó un día.

    Es la reparación simétrica de ``revivir_participante``: replica lo que
    habría hecho el proceso automático diario si se hubiera ejecutado.
    """

    desafio = await obtener_desafio_activo(guild_id)

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    (
        desafio_id,
        _guild_id,
        nombre,
        fecha_inicio,
        fecha_fin,
        canal_id,
        _activo,
    ) = desafio

    if not fecha_dentro_del_desafio(
        fecha,
        fecha_inicio,
        fecha_fin,
    ):
        return {
            "exitoso": False,
            "motivo": "fuera_de_fecha",
        }

    if fecha > hoy:
        return {
            "exitoso": False,
            "motivo": "futura",
        }

    participante = await obtener_participante(
        desafio_id,
        user_id,
    )

    if participante is None:
        return {
            "exitoso": False,
            "motivo": "no_participante",
        }

    if participante[4]:
        return {
            "exitoso": False,
            "motivo": "ya_eliminado",
        }

    if await tiene_registro(
        desafio_id,
        user_id,
        fecha,
    ):
        return {
            "exitoso": False,
            "motivo": "con_registro",
        }

    await eliminar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha_eliminacion=fecha,
    )

    return {
        "exitoso": True,
        "nombre": nombre,
        "fecha": fecha,
        "racha_actual": participante[6],
        "mejor_racha": participante[7],
    }


async def cerrar_desafio_activo(guild_id):
    """Cierra el desafío activo y devuelve su resultado final."""

    desafio = await obtener_desafio_activo(guild_id)

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    (
        desafio_id,
        _guild_id,
        nombre,
        fecha_inicio,
        fecha_fin,
        canal_id,
        _activo,
    ) = desafio

    ranking = await obtener_ranking_final(desafio_id)

    await marcar_desafio_cerrado(desafio_id)

    sobrevivientes = [
        fila
        for fila in ranking
        if not fila[2]
    ]

    eliminados = [
        fila
        for fila in ranking
        if fila[2]
    ]

    return {
        "exitoso": True,
        "desafio_id": desafio_id,
        "nombre": nombre,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "canal_id": canal_id,
        "total": len(ranking),
        "sobrevivientes": sobrevivientes,
        "eliminados": eliminados,
        "ranking": ranking,
    }


async def obtener_desafio_para_ranking(guild_id):
    """Devuelve el desafío a rankear: el activo o el más reciente."""

    desafio = await obtener_desafio_activo(guild_id)

    activo = True

    if desafio is None:
        desafio = await obtener_ultimo_desafio(guild_id)
        activo = False

    if desafio is None:
        return None

    (
        desafio_id,
        _guild_id,
        nombre,
        fecha_inicio,
        fecha_fin,
        canal_id,
        _activo_db,
    ) = desafio

    return {
        "desafio_id": desafio_id,
        "nombre": nombre,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "canal_id": canal_id,
        "activo": activo,
        "ranking": await obtener_ranking_final(desafio_id),
    }
