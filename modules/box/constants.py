"""Catálogos y textos estáticos de Box.

Nada de este módulo depende de la base de datos ni de discord.py: son datos
planos que comparten los comandos y la lógica. Los precios se leen de la
configuración (``config``) y sobre ellos se aplica el multiplicador global
de la tienda ``BOX_PRECIO_MULTIPLICADOR``.
"""

from config import (
    BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL,
    BOX_MEJORA_NIVEL_MAXIMO,
    BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL,
    BOX_MINUTOS_MAXIMO,
    BOX_MINUTOS_MINIMO,
    BOX_PRECIO_EQUIPAMIENTO_BOTAS,
    BOX_PRECIO_EQUIPAMIENTO_CASCO,
    BOX_PRECIO_EQUIPAMIENTO_GUANTES,
    BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL,
    BOX_PRECIO_EQUIPAMIENTO_SHORT,
    BOX_PRECIO_MEJORA_ENTRENAMIENTO,
    BOX_PRECIO_MEJORA_TRABAJO,
    BOX_PRECIO_MULTIPLICADOR,
    BOX_PRECIO_SUMINISTRO_CANSANCIO,
    BOX_PRECIO_SUMINISTRO_DEFENSA,
    BOX_PRECIO_SUMINISTRO_LESION,
    BOX_PRECIO_SUMINISTRO_VIDA,
    BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS,
    BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO,
)


def _precio(precio_base: int) -> int:
    """Aplica el multiplicador global de la tienda a un precio base."""

    return max(0, round(precio_base * BOX_PRECIO_MULTIPLICADOR))


CALIDADES = ["Basico", "Intermedio", "Avanzado", "Epico", "Legendario"]

NIVEL_MAXIMO_EQUIPAMIENTO = len(CALIDADES) - 1


MEJORAS = {
    "entrenamiento": {
        "nombre": "Creatina",
        "emoji": "🔥",
        "descripcion": (
            f"+{BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL} EXP por minuto "
            "de entrenamiento"
        ),
        "precio": _precio(BOX_PRECIO_MEJORA_ENTRENAMIENTO),
        "maximo": BOX_MEJORA_NIVEL_MAXIMO,
    },
    "trabajo": {
        "nombre": "Cafe",
        "emoji": "☕",
        "descripcion": (
            f"+{BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL} dinero por minuto "
            "de trabajo"
        ),
        "precio": _precio(BOX_PRECIO_MEJORA_TRABAJO),
        "maximo": BOX_MEJORA_NIVEL_MAXIMO,
    },
}


TRATAMIENTOS = {
    "fisioterapeutico": {
        "nombre": "Tratamiento Fisioterapeutico",
        "emoji": "🧑‍⚕️",
        "precio": _precio(BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO),
        "reinicia_probabilidad": False,
    },
    "cinco_estrellas": {
        "nombre": "Tratamiento 5 estrellas",
        "emoji": "🏝️",
        "precio": _precio(BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS),
        "reinicia_probabilidad": True,
    },
}


# Artículo genérico de la tienda. El tipo de suministro se elige al usarlo
# (comando /box suministro o el menú que abre su botón).
SUMINISTROS = {
    "recuperacion": {
        "nombre": "Suministros de recuperación",
        "emoji": "🎒",
        "descripcion": (
            "Restauran al máximo la estadística que elijas: "
            "vida, cansancio, defensa (reparación) o lesión."
        ),
    },
}


# Tipos de suministro disponibles, con temática de insumos de ejercicio.
TIPOS_SUMINISTRO = {
    "vida": {
        "nombre": "Bebida isotónica",
        "emoji": "🥤",
        "precio": _precio(BOX_PRECIO_SUMINISTRO_VIDA),
        "objetivo": "vida",
        "efecto": "restaura tu vida al máximo.",
    },
    "cansancio": {
        "nombre": "Bebida energética",
        "emoji": "⚡",
        "precio": _precio(BOX_PRECIO_SUMINISTRO_CANSANCIO),
        "objetivo": "cansancio",
        "efecto": "restaura tu energía (cansancio) al máximo.",
    },
    "defensa": {
        "nombre": "Servicio de reparación",
        "emoji": "🔧",
        "precio": _precio(BOX_PRECIO_SUMINISTRO_DEFENSA),
        "objetivo": "defensa",
        "efecto": "repara tu defensa hasta el máximo.",
    },
    "lesion": {
        "nombre": "Botiquín completo",
        "emoji": "🩹",
        "precio": _precio(BOX_PRECIO_SUMINISTRO_LESION),
        "objetivo": "lesion",
        "efecto": "cura tu lesión activa y deja la probabilidad en 0%.",
    },
}


EQUIPAMIENTO = {
    "casco": {
        "nombre": "Casco",
        "emoji": "🎩",
        "calidades": CALIDADES,
        "precio_base": _precio(BOX_PRECIO_EQUIPAMIENTO_CASCO),
    },
    "guantes": {
        "nombre": "Guantes",
        "emoji": "🤜",
        "calidades": CALIDADES,
        "precio_base": _precio(BOX_PRECIO_EQUIPAMIENTO_GUANTES),
    },
    "protector_bucal": {
        "nombre": "Protector Bucal",
        "emoji": "😁",
        "calidades": CALIDADES,
        "precio_base": _precio(BOX_PRECIO_EQUIPAMIENTO_PROTECTOR_BUCAL),
    },
    "short": {
        "nombre": "Short",
        "emoji": "👖",
        "calidades": CALIDADES,
        "precio_base": _precio(BOX_PRECIO_EQUIPAMIENTO_SHORT),
    },
    "botas": {
        "nombre": "Botas",
        "emoji": "👟",
        "calidades": CALIDADES,
        "precio_base": _precio(BOX_PRECIO_EQUIPAMIENTO_BOTAS),
    },
}


# Nombre en infinitivo de cada acción, para los avisos del bot.
NOMBRES_ACCIONES = {
    "TRABAJANDO": "trabajar",
    "ENTRENANDO": "entrenar",
    "SPARRING": "hacer sparring",
    "FIGHTING": "pelear",
    "PROMOVIENDO": "promocionarse",
}


# Etiqueta visible de cada tipo de sponsor.
NOMBRES_SPONSORS = {
    "redes": "📱 Redes",
    "radio": "📻 Radio",
    "equipamiento": "🥊 Equipamiento",
    "medico": "🚑 Médico",
}


# Límites de duración de las acciones, en minutos. Se leen de la
# configuración (BOX_MINUTOS_MINIMO / BOX_MINUTOS_MAXIMO) y se
# mantienen estos nombres por compatibilidad.
MINUTOS_MINIMO = BOX_MINUTOS_MINIMO
MINUTOS_MAXIMO = BOX_MINUTOS_MAXIMO


TEXTO_AYUDA = (
    "🥊 **Ayuda de Box**\n\n"
    "`/box entrenar minutos` — Entrena y gana experiencia.\n"
    "`/box trabajar minutos` — Trabaja y gana dinero.\n"
    "`/box sparring contrincante` — Desafía a sparring.\n"
    "`/box desafio contrincante` — Desafía a una pelea.\n"
    "`/box saldo` — Muestra tu experiencia y dinero.\n"
    "`/box stats` — Muestra tus estadísticas privadas.\n"
    "`/box equipo` — Muestra tu equipo y estadísticas de combate.\n"
    "`/box tienda` — Muestra todas las compras disponibles.\n"
    "`/box comprar tipo articulo` — Compra mejoras, equipamiento o tratamientos.\n"
    "`/box tratamiento tipo` — Compra un tratamiento para curar una lesión.\n"
    "`/box suministro tipo` — Usa suministros que restauran vida, cansancio,\n"
    "defensa (servicio de reparación) o la lesión.\n"
    "`/box descanso` — Reinicia la probabilidad de lesión.\n"
    "`/box topdesafios` — Muestra el ranking de desafíos.\n\n"
    "Las acciones duran el tiempo indicado y continúan aunque el bot se reinicie."
)
