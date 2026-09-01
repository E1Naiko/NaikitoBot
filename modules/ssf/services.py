from datetime import date, datetime

from modules.ssf.database import (
    cerrar_desafio,
    crear_desafio,
    eliminar_participante,
    guardar_registro,
    obtener_desafio_activo,
    obtener_estadisticas_desafio,
    obtener_participante,
    obtener_participantes,
    obtener_registros_usuario,
    registrar_participante,
    tiene_registro,
    actualizar_participante,
    reactivar_participante,
    obtener_ultima_revision_ssf,
    guardar_ultima_revision_ssf,
    obtener_ranking_final,
    marcar_desafio_cerrado,
)

from modules.ssf.logic import (
    calcular_mejor_racha,
    calcular_racha,
    fecha_anterior,
    fecha_dentro_del_desafio,
)

from core.database import conectar_db


def iniciar_desafio(
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

    existente = obtener_desafio_activo(
        guild_id
    )

    if existente:
        return {
            "exitoso": False,
            "motivo": "ya_existe",
        }

    desafio_id = crear_desafio(
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


def registrar_usuario(
    guild_id,
    user_id,
    username,
    ahora,
):
    """
    Registra un usuario en el desafío activo.
    """

    desafio = obtener_desafio_activo(
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

    participante = obtener_participante(
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

    registrar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        username=username,
        fecha_registro=ahora.isoformat(),
    )

    return {
        "exitoso": True,
        "motivo": "registrado",
        "nombre": nombre,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
    }


def registrar_sobrevivi(
    guild_id,
    user_id,
    ahora,
):
    """
    Registra la supervivencia diaria de un participante.
    """

    desafio = obtener_desafio_activo(
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

    participante = obtener_participante(
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

    if tiene_registro(
        desafio_id,
        user_id,
        fecha.isoformat(),
    ):
        return {
            "exitoso": False,
            "motivo": "ya_registrado",
        }

    guardar_registro(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha=fecha.isoformat(),
        hora=ahora.strftime("%H:%M:%S"),
    )

    registros = obtener_registros_usuario(
        desafio_id,
        user_id,
    )

    fechas = [
        date.fromisoformat(
            registro[0]
        )
        for registro in registros
    ]

    racha = calcular_racha(
        fechas,
        fecha,
    )

    mejor_racha = calcular_mejor_racha(
        fechas
    )

    actualizar_participante(
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
        "fecha": fecha,
        "hora": ahora,
    }


def obtener_estado_usuario(
    guild_id,
    user_id,
):
    """Obtiene el estado actual de un participante."""

    desafio = obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return {
            "exitoso": False,
            "motivo": "sin_desafio",
        }

    participante = obtener_participante(
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
    }


def eliminar_faltantes(
    guild_id,
    fecha,
):
    """
    Elimina a todos los participantes activos que no
    registraron /SSF sobrevivi durante la fecha indicada.
    """

    desafio = obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return 0

    desafio_id = desafio[0]

    participantes = obtener_participantes(
        desafio_id
    )

    eliminados = 0

    for participante in participantes:

        user_id = participante[0]
        eliminado = participante[3]

        if eliminado:
            continue

        if not tiene_registro(
            desafio_id,
            user_id,
            fecha.isoformat(),
        ):
            eliminar_participante(
                desafio_id=desafio_id,
                user_id=user_id,
                fecha_eliminacion=fecha.isoformat(),
            )

            eliminados += 1

    return eliminados


def obtener_estado_desafio(
    guild_id,
):
    """Obtiene las estadísticas del desafío activo."""

    desafio = obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return None

    total, activos, eliminados = (
        obtener_estadisticas_desafio(
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


def obtener_lista_participantes(
    guild_id,
):
    """Obtiene los participantes del desafío activo."""

    desafio = obtener_desafio_activo(
        guild_id
    )

    if desafio is None:
        return None

    return obtener_participantes(
        desafio[0]
    )

def revivir_participante(
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

    desafio = obtener_desafio_activo(guild_id)

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

    participante = obtener_participante(
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

    if tiene_registro(
        desafio_id,
        user_id,
        fecha.isoformat(),
    ):
        return {
            "exitoso": False,
            "motivo": "ya_registrado",
        }

    # Registrar retroactivamente el día perdido.
    guardar_registro(
        desafio_id=desafio_id,
        user_id=user_id,
        fecha=fecha.isoformat(),
        hora="ADMIN",
    )

    # Recuperar todas las fechas después del registro.
    registros = obtener_registros_usuario(
        desafio_id,
        user_id,
    )

    fechas = [
        date.fromisoformat(
            registro[0]
        )
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
    actualizar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
        racha_actual=racha,
        mejor_racha=mejor_racha,
    )

    # Quitar estado de eliminado.
    reactivar_participante(
        desafio_id=desafio_id,
        user_id=user_id,
    )

    return {
        "exitoso": True,
        "motivo": "revivido",
        "nombre": nombre,
        "racha": racha,
        "mejor_racha": mejor_racha,
        "fecha": fecha,
    }

def procesar_eliminaciones_diarias(fecha):
    """
    Elimina automáticamente a los participantes que no
    registraron /ssf sobrevivi durante la fecha indicada.

    Procesa todos los desafíos activos.
    """

    resultados = []

    desafios = obtener_desafios_activos()

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
        # Convertir fechas almacenadas en SQLite
        # ----------------------------------------------------

        inicio = date.fromisoformat(fecha_inicio)
        fin = date.fromisoformat(fecha_fin)

        # ----------------------------------------------------
        # Solo procesar fechas dentro del desafío
        # ----------------------------------------------------

        if fecha < inicio or fecha > fin:
            continue

        # ----------------------------------------------------
        # Obtener participantes
        # ----------------------------------------------------

        participantes = obtener_participantes(
            desafio_id
        )

        eliminados = []

        for participante in participantes:

            user_id = participante[0]
            username = participante[1]
            eliminado = participante[3]

            # Ya estaba eliminado.
            if eliminado:
                continue

            # Tiene registro de supervivencia.
            if tiene_registro(
                desafio_id,
                user_id,
                fecha.isoformat(),
            ):
                continue

            # No registró: eliminar.
            eliminar_participante(
                desafio_id=desafio_id,
                user_id=user_id,
                fecha_eliminacion=fecha.isoformat(),
            )

            eliminados.append(
                {
                    "user_id": user_id,
                    "username": username,
                }
            )

        resultados.append(
            {
                "desafio_id": desafio_id,
                "guild_id": guild_id,
                "nombre": nombre,
                "fecha": fecha,
                "eliminados": eliminados,
            }
        )

    return resultados

# ============================================================
# ELIMINACIÓN AUTOMÁTICA
# ============================================================

def procesar_eliminaciones_diarias(fecha):
    """
    Procesa la eliminación automática de todos los desafíos
    SSF activos.

    Cada desafío se procesa de manera independiente.
    """

    from modules.ssf.database import conectar_db

    resultados = []

    with conectar_db() as db:

        desafios = db.execute("""
            SELECT
                id,
                guild_id,
                nombre,
                fecha_inicio,
                fecha_fin,
                canal_id,
                activo
            FROM ssf_desafios
            WHERE activo = 1
        """).fetchall()

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
            obtener_ultima_revision_ssf(
                desafio_id
            )
        )

        if ultima_revision is not None:

            ultima_revision_obj = date.fromisoformat(
                ultima_revision
            )

            if fecha <= ultima_revision_obj:
                continue

        # ----------------------------------------------------
        # OBTENER PARTICIPANTES
        # ----------------------------------------------------

        participantes = obtener_participantes(
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
            if tiene_registro(
                desafio_id,
                user_id,
                fecha.isoformat(),
            ):
                continue

            # No registró → eliminar.
            eliminar_participante(
                desafio_id=desafio_id,
                user_id=user_id,
                fecha_eliminacion=fecha.isoformat(),
            )

            eliminados.append({
                "user_id": user_id,
                "username": username,
            })

        # ----------------------------------------------------
        # GUARDAR FECHA PROCESADA
        # ----------------------------------------------------

        guardar_ultima_revision_ssf(
            desafio_id=desafio_id,
            fecha=fecha.isoformat(),
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

def cerrar_desafios_finalizados(fecha):
    """
    Cierra automáticamente los desafíos cuya fecha de fin
    ya fue procesada.

    Devuelve la información necesaria para publicar
    el resultado final.
    """

    resultados = []

    with conectar_db() as db:

        desafios = db.execute("""
            SELECT
                id,
                guild_id,
                nombre,
                fecha_inicio,
                fecha_fin,
                canal_id,
                activo
            FROM ssf_desafios
            WHERE activo = 1
        """).fetchall()

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

        fecha_fin_obj = date.fromisoformat(
            fecha_fin
        )

        # ----------------------------------------------------
        # TODAVÍA NO TERMINÓ
        # ----------------------------------------------------

        if fecha <= fecha_fin_obj:
            continue

        # ----------------------------------------------------
        # EL ÚLTIMO DÍA TIENE QUE HABER SIDO PROCESADO
        # ----------------------------------------------------

        ultima_revision = (
            obtener_ultima_revision_ssf(
                desafio_id
            )
        )

        if ultima_revision is None:
            continue

        ultima_revision_obj = date.fromisoformat(
            ultima_revision
        )

        if ultima_revision_obj < fecha_fin_obj:
            continue

        # ----------------------------------------------------
        # OBTENER RANKING FINAL
        # ----------------------------------------------------

        ranking = obtener_ranking_final(
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

        cerrado = marcar_desafio_cerrado(
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