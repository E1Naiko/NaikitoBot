"""Líneas de terminal del canal 420 cuando el ranking cambia.

El registro en vivo ya imprime una línea por cada 420 válido, pero con el ID
numérico del usuario y sin contexto: no se ve quién fue ni qué pasó con los
puntos. Acá se arma el texto que se imprime en la terminal cuando **suma
puntos**: el 420 aceptado, el podio de la ventana y el cierre de una ventana.

Lo que no suma no se imprime: un mensaje fuera de horario o repetido no cambia
nada del juego y solo ensucia el log (el registro queda igual en la base).
"""

from datetime import datetime, timedelta

from config import LAHORA_DURACION_MINUTOS, LAHORA_HORAS, TIMEZONE

# Cuántos puestos del podio se muestran al cerrar la ventana.
PUESTOS_RESUMEN = 3


def _hora(momento):
    return momento.astimezone(TIMEZONE).strftime("%H:%M:%S")


def _fecha(momento):
    """Día y mes de un ``date`` o ``datetime`` en la zona del bot."""

    if isinstance(momento, datetime):
        momento = momento.astimezone(TIMEZONE)

    return momento.strftime("%d/%m")


def nombre_usuario(username, user_id):
    """Apodo legible; si viene vacío se muestra el ID."""

    limpio = (username or "").strip()

    return limpio or f"usuario {user_id}"


def linea_registro(resultado, username, user_id, mensaje_id=None, manual=False):
    """Una línea por 420 que sumó puntos.

    Se arma con el resultado del servicio, así que incluye la posición y los
    puntos definitivos de la ventana (``agregar_manual`` los recalcula antes
    de devolver, y esta función se llama después).
    """

    origen = f" mensaje={mensaje_id}" if mensaje_id is not None else ""

    if manual:
        origen += " manual=true"

    return (
        f"[420] ✅ {nombre_usuario(username, user_id)} ({user_id}) "
        f"{_fecha(resultado.momento)} {_hora(resultado.momento)} "
        f"ventana={resultado.ventana} "
        f"segundos={resultado.segundos} "
        f"posicion={resultado.posicion} "
        f"puntos={resultado.puntos_finales:g}{origen}"
    )


def linea_podio(resultado, username, user_id):
    """Aviso cuando el 420 entra en el podio de la ventana.

    Solo se imprime en el primero, segundo o tercer puesto: la llegada
    número diez no cambia nada del ranking visible, ya quedó en la línea de
    registro.
    """

    if resultado.posicion > PUESTOS_RESUMEN:
        return None

    medallas = {1: "🥇", 2: "🥈", 3: "🥉"}
    medalla = medallas[resultado.posicion]

    return (
        f"[420] {medalla} podio {nombre_usuario(username, user_id)} ({user_id}) "
        f"ventana={resultado.ventana} posicion={resultado.posicion} "
        f"puntos={resultado.puntos_finales:g}"
    )


def linea_resumen_ventana(fecha, ventana, filas):
    """Resumen de una ventana cerrada, para dejar el resultado en la terminal.

    ``filas`` son ``(user_id, username, segundos, puntos)`` en orden de
    llegada. Devuelve ``None`` si no hubo nadie: una ventana vacía no tiene
    nada que contar.
    """

    if not filas:
        return None

    podio = " | ".join(
        f"{posicion}. {nombre_usuario(username, user_id)} {puntos:g} pts"
        for posicion, (user_id, username, _segundos, puntos) in enumerate(
            filas[:PUESTOS_RESUMEN], 1
        )
    )

    return (
        f"[420] 📊 cierre {_fecha(fecha)} ventana={ventana} "
        f"participantes={len(filas)} → {podio}"
    )


def momentos_de_cierre(fecha, ventana):
    """Momento exacto en que cierra la ventana (hora local con zona)."""

    return datetime.combine(fecha, ventana, tzinfo=TIMEZONE) + timedelta(
        minutes=LAHORA_DURACION_MINUTOS
    )


def ventana_recien_cerrada(momento, tolerancia_segundos=90):
    """Ventana que terminó hace poco, o ``None``.

    La tarea que imprime el resumen corre cada minuto: la tolerancia un poco
    mayor evita perder la ventana si un latido se atrasa. El llamador
    deduplica para no imprimir dos veces la misma.
    """

    local = momento.astimezone(TIMEZONE) if momento.tzinfo else momento.replace(
        tzinfo=TIMEZONE
    )

    for ventana in LAHORA_HORAS:
        cierre = momentos_de_cierre(local.date(), ventana)
        transcurrido = (local - cierre).total_seconds()

        if 0 <= transcurrido <= tolerancia_segundos:
            return local.date(), ventana

    return None
