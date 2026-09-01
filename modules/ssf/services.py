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
)

from modules.ssf.logic import (
    calcular_mejor_racha,
    calcular_racha,
    fecha_anterior,
    fecha_dentro_del_desafio,
)


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