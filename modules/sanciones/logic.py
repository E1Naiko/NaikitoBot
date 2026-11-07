"""Reglas puras de las sanciones por trampa: sin Discord ni base de datos.

Qué se considera trampa lo decide un administrador: acá solo viven los
minijuegos válidos, el parseo del temporizador y el texto que ve el usuario
sancionado. Mantenerlo sin dependencias permite probarlo con fechas fijas.
"""

from datetime import datetime, timedelta

from config import TIMEZONE

# ============================================================
# MINIJUEGOS
# ============================================================

# Clave interna -> nombre que se muestra en Discord. La clave es la que se
# guarda en ``sanciones.minijuego`` y la que usa cada módulo para preguntar.
MINIJUEGOS = {
    "madrugue": "🌙 Madrugue",
    "lahora": "🌿 420 (laHora)",
    "ssf": "📅 SeptSinFP",
    "box": "🥊 Box",
}

TEXTO_MINIJUEGOS = ", ".join(nombre for nombre in MINIJUEGOS.values())


def nombre_minijuego(clave):
    """Nombre legible de un minijuego, o la clave cruda si es desconocida."""

    return MINIJUEGOS.get(clave, clave)


# ============================================================
# TEMPORIZADOR
# ============================================================

# Duración por defecto cuando el administrador no indica una: el ban no vence.
DURACION_POR_DEFECTO = None

# Tope para el texto libre del temporizador (evita baneos absurdos por un 0
# de más al escribir el comando).
MAXIMO_DIAS = 3650

_UNIDADES = {
    "s": ("segundo", 1 / 86400),
    "m": ("minuto", 1 / 1440),
    "h": ("hora", 1 / 24),
    "d": ("día", 1),
}

# Acepta "30m", "12h", "7d", "permanente", "perm", "nunca" o vacío.
_ALIAS_PERMANENTE = {"", "permanente", "perm", "nunca", "siempre", "infinito"}


def como_local(momento):
    """Normaliza un ``datetime`` a la zona horaria configurada."""

    if momento is None:
        return None

    if momento.tzinfo is None:
        return momento.replace(tzinfo=TIMEZONE)

    return momento.astimezone(TIMEZONE)


def ahora_local():
    """Momento actual en la zona del bot, con zona explícita."""

    return datetime.now(TIMEZONE)


def parsear_duracion(texto):
    """Convierte el texto del temporizador en ``timedelta`` o ``None``.

    ``None`` significa permanente. Un texto inválido lanza ``ValueError`` con
    el formato esperado, para que el comando responda un aviso claro en vez de
    guardar una duración a medias.
    """

    if texto is None:
        return DURACION_POR_DEFECTO

    limpio = str(texto).strip().lower().replace(" ", "")

    if limpio in _ALIAS_PERMANENTE:
        return DURACION_POR_DEFECTO

    # Se admite una sola unidad ("7d") o dos encadenadas ("2d12h").
    trozos = []
    resto = limpio
    while resto:
        cifras = ""
        while resto and resto[0].isdigit():
            cifras += resto[0]
            resto = resto[1:]
        if not cifras or not resto or resto[0] not in _UNIDADES:
            raise ValueError(_texto_formato())
        trozos.append((int(cifras), resto[0]))
        resto = resto[1:]
        if len(trozos) > 2:
            raise ValueError(_texto_formato())

    if not trozos:
        raise ValueError(_texto_formato())

    total = timedelta()
    for cantidad, unidad in trozos:
        total += timedelta(days=cantidad * _UNIDADES[unidad][1])

    if total <= timedelta():
        raise ValueError(
            "⏱️ La duración tiene que ser mayor que cero. "
            "Usá `permanente` si el ban no debe vencer."
        )

    if total > timedelta(days=MAXIMO_DIAS):
        raise ValueError(
            f"⏱️ La duración no puede superar los **{MAXIMO_DIAS} días**. "
            "Para un ban sin vencimiento usá `permanente`."
        )

    return total


def _texto_formato():
    return (
        "⏱️ Formato de duración inválido. Ejemplos: `30m`, `12h`, `7d`, "
        "`2d12h` o `permanente`."
    )


def calcular_expiracion(desde, duracion):
    """Momento de vencimiento, o ``None`` si la sanción es permanente."""

    if duracion is None:
        return None

    return como_local(desde) + duracion


def esta_vigente(expiracion, momento=None):
    """Indica si una sanción con ese vencimiento sigue bloqueando.

    ``expiracion`` en ``None`` es permanente. La comparación usa la hora con
    zona del bot para que un cambio de zona horaria del servidor no altere el
    vencimiento.
    """

    if expiracion is None:
        return True

    return como_local(expiracion) > como_local(momento or ahora_local())


# ============================================================
# ESTADO Y TEXTOS
# ============================================================

ESTADO_ACTIVA = "activa"
ESTADO_VENCIDA = "vencida"
ESTADO_LEVANTADA = "levantada"


def estado_sancion(expira_en, levantada_en=None, momento=None):
    """Estado de una fila de ``sanciones``: activa, vencida o levantada."""

    if levantada_en is not None:
        return ESTADO_LEVANTADA

    return ESTADO_ACTIVA if esta_vigente(expira_en, momento) else ESTADO_VENCIDA


def formatear_restante(expiracion, momento=None):
    """Texto del temporizador: "sin vencimiento" o "2d 3h 12m"."""

    if expiracion is None:
        return "sin vencimiento"

    restante = como_local(expiracion) - como_local(momento or ahora_local())
    segundos = int(restante.total_seconds())

    if segundos <= 0:
        return "vencida"

    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)

    partes = []
    if dias:
        partes.append(f"{dias}d")
    if horas:
        partes.append(f"{horas}h")
    if minutos and not dias:
        partes.append(f"{minutos}m")
    if segundos and not dias and not horas:
        partes.append(f"{segundos}s")

    return " ".join(partes) or "menos de 1s"


def texto_vencimiento(expiracion):
    """Fecha legible del final del ban, o "nunca" si es permanente."""

    if expiracion is None:
        return "nunca (permanente)"

    return f"<t:{int(como_local(expiracion).timestamp())}:F>"


def texto_sancion_activa(minijuego, expiracion, momento=None):
    """Aviso que recibe el usuario cuando intenta jugar estando sancionado."""

    if expiracion is None:
        detalle = "sin fecha de fin: solo un administrador puede levantarla"
    else:
        detalle = (
            f"termina {texto_vencimiento(expiracion)} "
            f"(faltan **{formatear_restante(expiracion, momento)}**)"
        )

    return (
        f"No podés participar en **{nombre_minijuego(minijuego)}**.\n"
        f"Tu sanción por trampa {detalle}."
    )
