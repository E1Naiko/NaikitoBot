import os
import re
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


__all__ = [
    "PREFIX",
    "TIMEZONE",
    "DATABASE",
    "MADRUGUE_INICIO_100",
    "MADRUGUE_INICIO_25",
    "MADRUGUE_INICIO_5",
    "MADRUGUE_FIN",
    "MADRUGUE_PUNTOS_100",
    "MADRUGUE_PUNTOS_25",
    "MADRUGUE_PUNTOS_5",
    "MADRUGUE_BONUS_MAXIMO",
    "MADRUGUE_BONUS_MINIMO",
    "ADMIN_USER_IDS",
    "GUILD_ID",
    "GENERAL_CHANNEL_IDS",
    "MADRUGUE_CHANNEL_IDS",
    "BOX_CHANNEL_IDS",
    "SSF_CANALES_ID",
    "SSF_FECHA_INICIO",
    "SSF_FECHA_FIN",
    "BOX_EXPERIENCIA_POR_MINUTO",
    "BOX_DINERO_POR_MINUTO",
    "BOX_MINUTOS_MINIMO",
    "BOX_MINUTOS_MAXIMO",
    "BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL",
    "BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL",
    "BOX_PRECIO_MULTIPLICADOR",
    "BOX_PRECIO_MEJORA_CRECIMIENTO",
    "BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO",
    "BOX_MEJORA_NIVEL_MAXIMO",
    "BOX_PRECIO_MEJORA_ENTRENAMIENTO",
    "BOX_PRECIO_MEJORA_TRABAJO",
    "BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO",
    "BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS",
    "BOX_PRECIO_SUMINISTRO_VIDA",
    "BOX_PRECIO_SUMINISTRO_CANSANCIO",
    "BOX_PRECIO_SUMINISTRO_DEFENSA",
    "BOX_PRECIO_SUMINISTRO_LESION",
    "BOX_PRECIO_EQUIPAMIENTO_CASCO",
    "BOX_PRECIO_EQUIPAMIENTO_GUANTES",
    "BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL",
    "BOX_PRECIO_EQUIPAMIENTO_SHORT",
    "BOX_PRECIO_EQUIPAMIENTO_BOTAS",
    "BOX_LESION_HORAS",
    "BOX_LESION_PROBABILIDAD_POR_HORA",
    "BOX_LESION_PROBABILIDAD_MAXIMA",
    "BOX_LESION_DECAIMIENTO_POR_HORA",
    "BOX_DESAFIO_VENTANA_HORAS",
    "BOX_DESAFIO_DURACION_HORAS",
    "BOX_DESAFIO_EXP_SPARRING",
    "BOX_DESAFIO_EXP_PELEA",
    "BOX_DESAFIO_RECOMPENSA_POR_MEJORA",
    "BOX_PROMOCION_PROBABILIDAD",
    "BOX_SPONSOR_PROBABILIDAD",
    "BOX_SPONSOR_DURACION_DIAS",
    "BOX_SPONSOR_PAGO",
    "BOX_SPONSOR_MAXIMO",
    "BOX_SPONSOR_CICLO_PAGO_HORAS",
    "BOX_MEDICO_CICLO_HORAS",
    "BOX_SPONSOR_EQUIPAMIENTO_BONUS",
    "BOX_MEDICO_REDUCCION",
    "BOX_VIDA_INICIAL",
    "BOX_CANSANCIO_INICIAL",
    "BOX_DANO_INICIAL",
    "BOX_DANO_MAXIMO",
    "BOX_DEFENSA_INICIAL",
    "BOX_DEFENSA_MAXIMO",
]


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# LECTURA Y VALIDACIÓN DE VARIABLES
# ============================================================

def _leer_hora(nombre, defecto):
    """Lee una variable ``HH:MM`` y falla con un error claro si no valida.

    El formato es estricto: dos dígitos para la hora, dos para los
    minutos (``05:30`` sí, ``5:30`` no).
    """

    valor = os.getenv(nombre, defecto).strip()

    hora = None

    if re.fullmatch("[0-9]{2}:[0-9]{2}", valor):
        try:
            hora = datetime.strptime(
                valor,
                "%H:%M",
            ).time()

        except ValueError:
            hora = None

    if hora is None:
        raise RuntimeError(
            f"Configuración inválida: {nombre} debe ser una hora en "
            f"formato HH:MM (por ejemplo 05:30), pero se recibió "
            f"'{valor}'."
        )

    return hora


def _leer_entero(nombre, defecto):
    """Lee una variable entera y falla con un error claro si no valida."""

    valor = os.getenv(nombre, str(defecto)).strip()

    try:
        return int(valor)

    except ValueError:
        raise RuntimeError(
            f"Configuración inválida: {nombre} debe ser un número "
            f"entero (por ejemplo {defecto}), pero se recibió "
            f"'{valor}'."
        ) from None


def _leer_decimal(nombre, defecto):
    """Lee una variable decimal y falla con un error claro si no valida."""

    valor = os.getenv(nombre, str(defecto)).strip()

    try:
        return float(valor)

    except ValueError:
        raise RuntimeError(
            f"Configuración inválida: {nombre} debe ser un número "
            f"decimal (por ejemplo {defecto}), pero se recibió "
            f"'{valor}'."
        ) from None


def _leer_mapa(nombre, defecto, tipo_valor):
    """Lee un mapa ``clave=valor,clave=valor`` y valida cada ítem.

    Se usa para las configuraciones de Box que son diccionarios
    (probabilidades, duraciones y pagos de sponsors). Devuelve un
    ``dict`` con las claves en el orden escrito.
    """

    valor = os.getenv(nombre, defecto).strip()

    if not valor:
        return {}

    mapa = {}

    for item in valor.split(","):

        if "=" not in item:
            raise RuntimeError(
                f"Configuración inválida: {nombre} debe ser una lista "
                f"de ítems 'clave=valor' separados por comas (por "
                f"ejemplo {defecto}), pero se recibió '{valor}'."
            )

        clave, _, crudo = item.partition("=")
        clave = clave.strip()
        crudo = crudo.strip()

        try:
            mapa[clave] = tipo_valor(crudo)

        except ValueError:
            raise RuntimeError(
                f"Configuración inválida: el ítem '{clave}' de "
                f"{nombre} debe ser un número {tipo_valor.__name__} "
                f"(por ejemplo {defecto}), pero se recibió '{crudo}'."
            ) from None

    return mapa


def _leer_curva(nombre, defecto):
    """Lee una curva ``horas=valor,...`` ordenada por horas.

    Se usa para la probabilidad de conseguir sponsor según el tiempo
    promocionándose: cada ítem es un punto de la curva.
    """

    puntos = sorted(
        (float(horas), valor)
        for horas, valor in _leer_mapa(
            nombre,
            defecto,
            float,
        ).items()
    )

    _comprobar(
        len(puntos) >= 2,
        f"{nombre} debe definir al menos dos puntos de la curva "
        f"'horas=valor' separados por comas (por ejemplo {defecto}), "
        f"pero se recibió '{os.getenv(nombre, defecto).strip()}'.",
    )

    for horas, probabilidad in puntos:

        _comprobar(
            horas > 0,
            f"{nombre} debe usar horas mayores que cero para cada "
            f"punto, pero definió {horas}.",
        )

        _comprobar(
            0 <= probabilidad <= 100,
            f"{nombre} debe usar probabilidades entre 0 y 100, pero "
            f"definió {probabilidad} a las {horas} horas.",
        )

    return tuple(puntos)


def _comprobar(valida, detalle):
    """Aborta el arranque con un error claro si no se cumple algo."""

    if not valida:
        raise RuntimeError(
            f"Configuración inválida: {detalle}"
        )


def _hhmm(hora: time) -> str:
    return hora.strftime("%H:%M")


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

PREFIX = "$!"

TIMEZONE = ZoneInfo(
    os.getenv(
        "TIMEZONE",
        "America/Argentina/Buenos_Aires",
    )
)


# ============================================================
# BASE DE DATOS
# ============================================================

DATABASE = os.getenv("DATABASE", "naikito.db")


# ============================================================
# CONFIGURACIÓN DE MADRUGUE
# ============================================================

# Ventanas de puntos, fin de la madrugada y bonus horario. Todo se
# configura desde el .env con variables MADRUGUE_* (formato HH:MM para
# las horas) y se valida al arrancar: un valor inválido impide que el
# bot arranque con un error que nombra la variable culpable.

MADRUGUE_INICIO_100 = _leer_hora(
    "MADRUGUE_INICIO_100",
    "05:30",
)

MADRUGUE_INICIO_25 = _leer_hora(
    "MADRUGUE_INICIO_25",
    "07:00",
)

MADRUGUE_INICIO_5 = _leer_hora(
    "MADRUGUE_INICIO_5",
    "09:00",
)

MADRUGUE_FIN = _leer_hora(
    "MADRUGUE_FIN",
    "10:00",
)

MADRUGUE_PUNTOS_100 = _leer_entero(
    "MADRUGUE_PUNTOS_100",
    100,
)

MADRUGUE_PUNTOS_25 = _leer_entero(
    "MADRUGUE_PUNTOS_25",
    25,
)

MADRUGUE_PUNTOS_5 = _leer_entero(
    "MADRUGUE_PUNTOS_5",
    5,
)

MADRUGUE_BONUS_MAXIMO = _leer_decimal(
    "MADRUGUE_BONUS_MAXIMO",
    0.100,
)

MADRUGUE_BONUS_MINIMO = _leer_decimal(
    "MADRUGUE_BONUS_MINIMO",
    0.001,
)

# Validaciones cruzadas: las ventanas tienen que abrir y cerrar en
# orden, los puntos ser positivos y el bonus no invertirse.

_comprobar(
    MADRUGUE_INICIO_100
    < MADRUGUE_INICIO_25
    < MADRUGUE_INICIO_5
    < MADRUGUE_FIN,
    "los horarios de Madrugue deben ir en orden y sin repetirse: "
    "MADRUGUE_INICIO_100 < MADRUGUE_INICIO_25 < MADRUGUE_INICIO_5 "
    f"< MADRUGUE_FIN, pero se recibió {_hhmm(MADRUGUE_INICIO_100)} < "
    f"{_hhmm(MADRUGUE_INICIO_25)} < {_hhmm(MADRUGUE_INICIO_5)} < "
    f"{_hhmm(MADRUGUE_FIN)}.",
)

for _nombre, _puntos in (
    ("MADRUGUE_PUNTOS_100", MADRUGUE_PUNTOS_100),
    ("MADRUGUE_PUNTOS_25", MADRUGUE_PUNTOS_25),
    ("MADRUGUE_PUNTOS_5", MADRUGUE_PUNTOS_5),
):
    _comprobar(
        _puntos >= 1,
        f"{_nombre} debe ser un número entero mayor o igual que 1, "
        f"pero se recibió {_puntos}.",
    )

_comprobar(
    0
    <= MADRUGUE_BONUS_MINIMO
    <= MADRUGUE_BONUS_MAXIMO,
    "el bonus de Madrugue debe cumplir 0 <= MADRUGUE_BONUS_MINIMO "
    "<= MADRUGUE_BONUS_MAXIMO, pero se recibió mínimo "
    f"{MADRUGUE_BONUS_MINIMO} y máximo {MADRUGUE_BONUS_MAXIMO}.",
)


# ============================================================
# USUARIOS CON ACCESO ADMINISTRATIVO
# ============================================================

ADMIN_USER_IDS = {
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_USER_IDS", "").split(",")
    if user_id.strip()
}


# ============================================================
# SERVIDORES DE DISCORD
# ============================================================

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

GENERAL_CHANNEL_IDS = {
    int(canal_id.strip())
    for canal_id in os.getenv(
        "GENERAL_CHANNEL_ID",
        os.getenv("BOX_CHANNEL_ID", ""),
    ).split(",")
    if canal_id.strip()
}

MADRUGUE_CHANNEL_IDS = {
    int(canal_id.strip())
    for canal_id in os.getenv("MADRUGUE_CHANNEL_ID", "").split(",")
    if canal_id.strip()
}

BOX_CHANNEL_IDS = {
    int(canal_id.strip())
    for canal_id in os.getenv("BOX_CHANNEL_ID", "").split(",")
    if canal_id.strip()
}

# ============================================================
# CONFIGURACIÓN DE SEPTIEMBRESINFAP
# ============================================================

SSF_CANALES_ID = {
    int(canal_id.strip())
    for canal_id in os.getenv("SSF_CANALES_ID", "").split(",")
    if canal_id.strip()
}

SSF_FECHA_INICIO = os.getenv(
    "SSF_FECHA_INICIO",
    "2026-09-01",
)

SSF_FECHA_FIN = os.getenv(
    "SSF_FECHA_FIN",
    "2026-09-30",
)

# ============================================================
# CONFIGURACIÓN DE BOX
# ============================================================
#
# Todo el balance de Box se configura desde el .env con variables
# BOX_* y se valida al arrancar: un valor inválido impide que el bot
# arranque con un error que nombra la variable culpable.

# ------------------------------------------------------------
# ACCIONES
# ------------------------------------------------------------

# Ganancia base por minuto de entrenar (EXP) y de trabajar (dinero).

BOX_EXPERIENCIA_POR_MINUTO = _leer_entero(
    "BOX_EXPERIENCIA_POR_MINUTO",
    10,
)

BOX_DINERO_POR_MINUTO = _leer_entero(
    "BOX_DINERO_POR_MINUTO",
    100,
)

# Límites de duración de entrenar, trabajar y promocionarse, en
# minutos (los comparte modules/box/constants.py).

BOX_MINUTOS_MINIMO = _leer_entero(
    "BOX_MINUTOS_MINIMO",
    1,
)

BOX_MINUTOS_MAXIMO = _leer_entero(
    "BOX_MINUTOS_MAXIMO",
    1440,
)

# Ganancia fija de cada nivel de mejora (Creatina y Cafe).

BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL = _leer_entero(
    "BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL",
    5,
)

BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL = _leer_entero(
    "BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL",
    50,
)

_comprobar(
    0 < BOX_MINUTOS_MINIMO <= BOX_MINUTOS_MAXIMO,
    "la duración de las acciones debe cumplir 0 < BOX_MINUTOS_MINIMO "
    f"<= BOX_MINUTOS_MAXIMO, pero se recibió mínimo "
    f"{BOX_MINUTOS_MINIMO} y máximo {BOX_MINUTOS_MAXIMO}.",
)

for _nombre, _valor in (
    ("BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL", BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL),
    ("BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL", BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL),
):
    _comprobar(
        _valor >= 0,
        f"{_nombre} debe ser mayor o igual que 0, pero se recibió "
        f"{_valor}.",
    )

# ------------------------------------------------------------
# TIENDA: PRECIOS Y MULTIPLICADOR
# ------------------------------------------------------------

# Multiplicador global de la tienda: se aplica sobre el precio de
# todos los artículos (mejoras, tratamientos, suministros y
# equipamiento) y también sobre los precios que crecen por nivel.

BOX_PRECIO_MULTIPLICADOR = _leer_decimal(
    "BOX_PRECIO_MULTIPLICADOR",
    1.0,
)

# Crecimiento del precio por nivel: las mejoras suben un
# BOX_PRECIO_MEJORA_CRECIMIENTO compuesto por nivel (1.25 = +25 %) y
# cada pieza de equipamiento se multiplica por
# BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO (2.0 = se duplica).

BOX_PRECIO_MEJORA_CRECIMIENTO = _leer_decimal(
    "BOX_PRECIO_MEJORA_CRECIMIENTO",
    1.25,
)

BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO = _leer_decimal(
    "BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO",
    2.0,
)

# Nivel máximo de las mejoras (Creatina y Cafe).

BOX_MEJORA_NIVEL_MAXIMO = _leer_entero(
    "BOX_MEJORA_NIVEL_MAXIMO",
    10,
)

# Precios base de la tienda.

BOX_PRECIO_MEJORA_ENTRENAMIENTO = _leer_entero(
    "BOX_PRECIO_MEJORA_ENTRENAMIENTO",
    1000,
)

BOX_PRECIO_MEJORA_TRABAJO = _leer_entero(
    "BOX_PRECIO_MEJORA_TRABAJO",
    1000,
)

BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO = _leer_entero(
    "BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO",
    10000,
)

BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS = _leer_entero(
    "BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS",
    50000,
)

BOX_PRECIO_SUMINISTRO_VIDA = _leer_entero(
    "BOX_PRECIO_SUMINISTRO_VIDA",
    1500,
)

BOX_PRECIO_SUMINISTRO_CANSANCIO = _leer_entero(
    "BOX_PRECIO_SUMINISTRO_CANSANCIO",
    1500,
)

BOX_PRECIO_SUMINISTRO_DEFENSA = _leer_entero(
    "BOX_PRECIO_SUMINISTRO_DEFENSA",
    3000,
)

BOX_PRECIO_SUMINISTRO_LESION = _leer_entero(
    "BOX_PRECIO_SUMINISTRO_LESION",
    60000,
)

BOX_PRECIO_EQUIPAMIENTO_CASCO = _leer_entero(
    "BOX_PRECIO_EQUIPAMIENTO_CASCO",
    1000,
)

BOX_PRECIO_EQUIPAMIENTO_GUANTES = _leer_entero(
    "BOX_PRECIO_EQUIPAMIENTO_GUANTES",
    1000,
)

BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL = _leer_entero(
    "BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL",
    600,
)

BOX_PRECIO_EQUIPAMIENTO_SHORT = _leer_entero(
    "BOX_PRECIO_EQUIPAMIENTO_SHORT",
    600,
)

BOX_PRECIO_EQUIPAMIENTO_BOTAS = _leer_entero(
    "BOX_PRECIO_EQUIPAMIENTO_BOTAS",
    800,
)

_comprobar(
    BOX_PRECIO_MULTIPLICADOR > 0,
    "BOX_PRECIO_MULTIPLICADOR debe ser mayor que 0, pero se recibió "
    f"{BOX_PRECIO_MULTIPLICADOR}.",
)

for _nombre, _crecimiento in (
    ("BOX_PRECIO_MEJORA_CRECIMIENTO", BOX_PRECIO_MEJORA_CRECIMIENTO),
    ("BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO", BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO),
):
    _comprobar(
        _crecimiento >= 1,
        f"{_nombre} debe ser mayor o igual que 1 (sin rebajas por "
        f"nivel), pero se recibió {_crecimiento}.",
    )

_comprobar(
    BOX_MEJORA_NIVEL_MAXIMO >= 1,
    "BOX_MEJORA_NIVEL_MAXIMO debe ser mayor o igual que 1, pero se "
    f"recibió {BOX_MEJORA_NIVEL_MAXIMO}.",
)

for _nombre, _precio in (
    ("BOX_PRECIO_MEJORA_ENTRENAMIENTO", BOX_PRECIO_MEJORA_ENTRENAMIENTO),
    ("BOX_PRECIO_MEJORA_TRABAJO", BOX_PRECIO_MEJORA_TRABAJO),
    ("BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO", BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO),
    ("BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS", BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS),
    ("BOX_PRECIO_SUMINISTRO_VIDA", BOX_PRECIO_SUMINISTRO_VIDA),
    ("BOX_PRECIO_SUMINISTRO_CANSANCIO", BOX_PRECIO_SUMINISTRO_CANSANCIO),
    ("BOX_PRECIO_SUMINISTRO_DEFENSA", BOX_PRECIO_SUMINISTRO_DEFENSA),
    ("BOX_PRECIO_SUMINISTRO_LESION", BOX_PRECIO_SUMINISTRO_LESION),
    ("BOX_PRECIO_EQUIPAMIENTO_CASCO", BOX_PRECIO_EQUIPAMIENTO_CASCO),
    ("BOX_PRECIO_EQUIPAMIENTO_GUANTES", BOX_PRECIO_EQUIPAMIENTO_GUANTES),
    ("BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL", BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL),
    ("BOX_PRECIO_EQUIPAMIENTO_SHORT", BOX_PRECIO_EQUIPAMIENTO_SHORT),
    ("BOX_PRECIO_EQUIPAMIENTO_BOTAS", BOX_PRECIO_EQUIPAMIENTO_BOTAS),
):
    _comprobar(
        _precio >= 0,
        f"{_nombre} debe ser mayor o igual que 0, pero se recibió "
        f"{_precio}.",
    )

# ------------------------------------------------------------
# LESIONES
# ------------------------------------------------------------

# Duración de la lesión, en horas (admite decimales, por ejemplo 1.5).

BOX_LESION_HORAS = _leer_decimal(
    "BOX_LESION_HORAS",
    3.0,
)

# Cuánto sube la probabilidad de lesionarse por cada hora de acción,
# el techo de esa probabilidad y cuánto baja por cada hora de
# descanso (sin acción activa). Todo en puntos porcentuales.

BOX_LESION_PROBABILIDAD_POR_HORA = _leer_decimal(
    "BOX_LESION_PROBABILIDAD_POR_HORA",
    1.0,
)

BOX_LESION_PROBABILIDAD_MAXIMA = _leer_decimal(
    "BOX_LESION_PROBABILIDAD_MAXIMA",
    100.0,
)

BOX_LESION_DECAIMIENTO_POR_HORA = _leer_decimal(
    "BOX_LESION_DECAIMIENTO_POR_HORA",
    0.01,
)

_comprobar(
    BOX_LESION_HORAS > 0,
    "BOX_LESION_HORAS debe ser mayor que 0, pero se recibió "
    f"{BOX_LESION_HORAS}.",
)

_comprobar(
    0 < BOX_LESION_PROBABILIDAD_POR_HORA
    <= BOX_LESION_PROBABILIDAD_MAXIMA <= 100,
    "la probabilidad de lesión debe cumplir 0 < "
    "BOX_LESION_PROBABILIDAD_POR_HORA <= BOX_LESION_PROBABILIDAD_MAXIMA "
    "<= 100, pero se recibió por hora "
    f"{BOX_LESION_PROBABILIDAD_POR_HORA} y máxima "
    f"{BOX_LESION_PROBABILIDAD_MAXIMA}.",
)

_comprobar(
    BOX_LESION_DECAIMIENTO_POR_HORA >= 0,
    "BOX_LESION_DECAIMIENTO_POR_HORA debe ser mayor o igual que 0, "
    f"pero se recibió {BOX_LESION_DECAIMIENTO_POR_HORA}.",
)

# ------------------------------------------------------------
# DESAFÍOS
# ------------------------------------------------------------

# Duración del sparring y la pelea, en horas (admite decimales).

BOX_DESAFIO_VENTANA_HORAS = _leer_decimal(
    "BOX_DESAFIO_VENTANA_HORAS",
    1.0,
)

BOX_DESAFIO_DURACION_HORAS = _leer_decimal(
    "BOX_DESAFIO_DURACION_HORAS",
    1.0,
)

# Multiplicador de experiencia del perdedor y recompensa fija de
# puntos de habilidad por mejora usada.

BOX_DESAFIO_EXP_SPARRING = _leer_entero(
    "BOX_DESAFIO_EXP_SPARRING",
    5,
)

BOX_DESAFIO_EXP_PELEA = _leer_entero(
    "BOX_DESAFIO_EXP_PELEA",
    10,
)

BOX_DESAFIO_RECOMPENSA_POR_MEJORA = _leer_entero(
    "BOX_DESAFIO_RECOMPENSA_POR_MEJORA",
    5,
)

_comprobar(
    BOX_DESAFIO_VENTANA_HORAS > 0,
    "BOX_DESAFIO_VENTANA_HORAS debe ser mayor que 0, pero se recibió "
    f"{BOX_DESAFIO_VENTANA_HORAS}.",
)

_comprobar(
    BOX_DESAFIO_DURACION_HORAS > 0,
    "BOX_DESAFIO_DURACION_HORAS debe ser mayor que 0, pero se recibió "
    f"{BOX_DESAFIO_DURACION_HORAS}.",
)

for _nombre, _valor in (
    ("BOX_DESAFIO_EXP_SPARRING", BOX_DESAFIO_EXP_SPARRING),
    ("BOX_DESAFIO_EXP_PELEA", BOX_DESAFIO_EXP_PELEA),
    ("BOX_DESAFIO_RECOMPENSA_POR_MEJORA", BOX_DESAFIO_RECOMPENSA_POR_MEJORA),
):
    _comprobar(
        _valor >= 0,
        f"{_nombre} debe ser mayor o igual que 0, pero se recibió "
        f"{_valor}.",
    )

# ------------------------------------------------------------
# SPONSORS
# ------------------------------------------------------------

# Curva de probabilidad de conseguir sponsor según las horas
# promocionándose, en puntos de la forma 'horas=porcentaje'. La
# probabilidad se interpola linealmente entre puntos.

BOX_PROMOCION_PROBABILIDAD = _leer_curva(
    "BOX_PROMOCION_PROBABILIDAD",
    "1=5,2=10,4=20,8=40,12=60,16=80,24=100",
)

# Tipos de sponsor: probabilidad de cada uno en el sorteo (en %),
# duración en días, pago por ciclo en dinero y cantidad máxima
# simultánea. Los mapas usan el formato 'clave=valor' separado por
# comas; los tipos son redes, radio, equipamiento y medico.

_TIPOS_SPONSOR = {"redes", "radio", "equipamiento", "medico"}

BOX_SPONSOR_PROBABILIDAD = _leer_mapa(
    "BOX_SPONSOR_PROBABILIDAD",
    "redes=50,radio=30,equipamiento=15,medico=5",
    float,
)

BOX_SPONSOR_DURACION_DIAS = _leer_mapa(
    "BOX_SPONSOR_DURACION_DIAS",
    "redes=7,radio=7,equipamiento=14,medico=30",
    float,
)

BOX_SPONSOR_PAGO = _leer_mapa(
    "BOX_SPONSOR_PAGO",
    "redes=500,radio=1000",
    int,
)

BOX_SPONSOR_MAXIMO = _leer_mapa(
    "BOX_SPONSOR_MAXIMO",
    "redes=10,radio=10",
    int,
)

# Ciclo de pagos de Redes y Radio, y ciclo de tratamientos del
# sponsor Médico, ambos en horas.

BOX_SPONSOR_CICLO_PAGO_HORAS = _leer_decimal(
    "BOX_SPONSOR_CICLO_PAGO_HORAS",
    24.0,
)

BOX_MEDICO_CICLO_HORAS = _leer_decimal(
    "BOX_MEDICO_CICLO_HORAS",
    24.0,
)

# Bonus de EXP por sponsor de Equipamiento activo, en % por sponsor.

BOX_SPONSOR_EQUIPAMIENTO_BONUS = _leer_decimal(
    "BOX_SPONSOR_EQUIPAMIENTO_BONUS",
    10.0,
)

# Reducción de la probabilidad de lesión de cada tratamiento del
# sponsor Médico, en %.

BOX_MEDICO_REDUCCION = _leer_decimal(
    "BOX_MEDICO_REDUCCION",
    50.0,
)

for _nombre, _mapa, _tipos in (
    ("BOX_SPONSOR_PROBABILIDAD", BOX_SPONSOR_PROBABILIDAD, _TIPOS_SPONSOR),
    ("BOX_SPONSOR_DURACION_DIAS", BOX_SPONSOR_DURACION_DIAS, _TIPOS_SPONSOR),
):
    _comprobar(
        set(_mapa) == _tipos,
        f"{_nombre} debe definir exactamente los cuatro tipos de "
        f"sponsor ({', '.join(sorted(_tipos))}), pero se recibió "
        f"{', '.join(sorted(_mapa)) or 'un mapa vacío'}.",
    )

for _nombre, _mapa in (
    ("BOX_SPONSOR_PAGO", BOX_SPONSOR_PAGO),
    ("BOX_SPONSOR_MAXIMO", BOX_SPONSOR_MAXIMO),
):
    _comprobar(
        set(_mapa) <= _TIPOS_SPONSOR,
        f"{_nombre} solo puede usar los tipos de sponsor "
        f"({', '.join(sorted(_TIPOS_SPONSOR))}), pero se recibió "
        f"{', '.join(sorted(_mapa)) or 'un mapa vacío'}.",
    )

_comprobar(
    0 <= sum(BOX_SPONSOR_PROBABILIDAD.values()),
    "BOX_SPONSOR_PROBABILIDAD no puede tener valores negativos, pero "
    "se recibió "
    f"{', '.join(f'{clave}={valor}' for clave, valor in sorted(BOX_SPONSOR_PROBABILIDAD.items()))}.",
)

_comprobar(
    sum(BOX_SPONSOR_PROBABILIDAD.values()) > 0,
    "BOX_SPONSOR_PROBABILIDAD debe sumar más de 0 para que el sorteo "
    "pueda elegir un sponsor, pero la suma es "
    f"{sum(BOX_SPONSOR_PROBABILIDAD.values())}.",
)

for _nombre, _valor in BOX_SPONSOR_PROBABILIDAD.items():
    _comprobar(
        0 <= _valor <= 100,
        f"el tipo '{_nombre}' de BOX_SPONSOR_PROBABILIDAD debe "
        f"estar entre 0 y 100, pero se recibió {_valor}.",
    )

for _tipo, _dias in BOX_SPONSOR_DURACION_DIAS.items():
    _comprobar(
        _dias > 0,
        f"la duración de '{_tipo}' en BOX_SPONSOR_DURACION_DIAS debe "
        f"ser mayor que 0 días, pero se recibió {_dias}.",
    )

for _nombre, _mapa in (
    ("BOX_SPONSOR_PAGO", BOX_SPONSOR_PAGO),
    ("BOX_SPONSOR_MAXIMO", BOX_SPONSOR_MAXIMO),
):
    for _tipo, _valor in _mapa.items():
        _comprobar(
            _valor >= 0,
            f"el tipo '{_tipo}' de {_nombre} debe ser mayor o igual "
            f"que 0, pero se recibió {_valor}.",
        )

_comprobar(
    BOX_SPONSOR_CICLO_PAGO_HORAS > 0,
    "BOX_SPONSOR_CICLO_PAGO_HORAS debe ser mayor que 0, pero se "
    f"recibió {BOX_SPONSOR_CICLO_PAGO_HORAS}.",
)

_comprobar(
    BOX_MEDICO_CICLO_HORAS > 0,
    "BOX_MEDICO_CICLO_HORAS debe ser mayor que 0, pero se recibió "
    f"{BOX_MEDICO_CICLO_HORAS}.",
)

_comprobar(
    BOX_SPONSOR_EQUIPAMIENTO_BONUS >= 0,
    "BOX_SPONSOR_EQUIPAMIENTO_BONUS debe ser mayor o igual que 0, "
    f"pero se recibió {BOX_SPONSOR_EQUIPAMIENTO_BONUS}.",
)

_comprobar(
    0 <= BOX_MEDICO_REDUCCION <= 100,
    "BOX_MEDICO_REDUCCION debe estar entre 0 y 100, pero se recibió "
    f"{BOX_MEDICO_REDUCCION}.",
)

# ------------------------------------------------------------
# ESTADÍSTICAS INICIALES DE COMBATE
# ------------------------------------------------------------

# Valores con los que arranca el equipo de un boxeador nuevo: la
# vida y el cansancio arrancan al máximo de su valor, y el daño y la
# defensa arrancan en su valor inicial hasta subir el máximo.

BOX_VIDA_INICIAL = _leer_entero(
    "BOX_VIDA_INICIAL",
    32,
)

BOX_CANSANCIO_INICIAL = _leer_entero(
    "BOX_CANSANCIO_INICIAL",
    25,
)

BOX_DANO_INICIAL = _leer_entero(
    "BOX_DANO_INICIAL",
    1,
)

BOX_DANO_MAXIMO = _leer_entero(
    "BOX_DANO_MAXIMO",
    25,
)

BOX_DEFENSA_INICIAL = _leer_entero(
    "BOX_DEFENSA_INICIAL",
    1,
)

BOX_DEFENSA_MAXIMO = _leer_entero(
    "BOX_DEFENSA_MAXIMO",
    22,
)

for _nombre, _inicial, _maximo in (
    ("BOX_DANO_INICIAL", BOX_DANO_INICIAL, BOX_DANO_MAXIMO),
    ("BOX_DEFENSA_INICIAL", BOX_DEFENSA_INICIAL, BOX_DEFENSA_MAXIMO),
):
    _comprobar(
        0 < _inicial <= _maximo,
        f"el daño y la defensa deben cumplir 0 < inicial <= máximo: "
        f"{_nombre} es {_inicial} y su máximo es {_maximo}.",
    )

_comprobar(
    BOX_VIDA_INICIAL > 0,
    "BOX_VIDA_INICIAL debe ser mayor que 0, pero se recibió "
    f"{BOX_VIDA_INICIAL}.",
)

_comprobar(
    BOX_CANSANCIO_INICIAL > 0,
    "BOX_CANSANCIO_INICIAL debe ser mayor que 0, pero se recibió "
    f"{BOX_CANSANCIO_INICIAL}.",
)