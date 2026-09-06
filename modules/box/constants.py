"""Catálogos y textos estáticos de Box.

Nada de este módulo depende de la base de datos ni de discord.py: son datos
planos que comparten los comandos y la lógica.
"""

CALIDADES = ["Basico", "Intermedio", "Avanzado", "Epico", "Legendario"]

NIVEL_MAXIMO_EQUIPAMIENTO = len(CALIDADES) - 1


MEJORAS = {
    "entrenamiento": {
        "nombre": "Creatina",
        "emoji": "🔥",
        "descripcion": "+5 EXP por minuto de entrenamiento",
        "precio": 1000,
        "maximo": 10,
    },
    "trabajo": {
        "nombre": "Cafe",
        "emoji": "☕",
        "descripcion": "+5 dinero por minuto de trabajo",
        "precio": 1000,
        "maximo": 10,
    },
}


TRATAMIENTOS = {
    "fisioterapeutico": {
        "nombre": "Tratamiento Fisioterapeutico",
        "emoji": "🧑‍⚕️",
        "precio": 10000,
        "reinicia_probabilidad": False,
    },
    "cinco_estrellas": {
        "nombre": "Tratamiento 5 estrellas",
        "emoji": "🏝️",
        "precio": 50000,
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
        "precio": 1500,
        "objetivo": "vida",
        "efecto": "restaura tu vida al máximo.",
    },
    "cansancio": {
        "nombre": "Bebida energética",
        "emoji": "⚡",
        "precio": 1500,
        "objetivo": "cansancio",
        "efecto": "restaura tu energía (cansancio) al máximo.",
    },
    "defensa": {
        "nombre": "Servicio de reparación",
        "emoji": "🔧",
        "precio": 3000,
        "objetivo": "defensa",
        "efecto": "repara tu defensa hasta el máximo.",
    },
    "lesion": {
        "nombre": "Botiquín completo",
        "emoji": "🩹",
        "precio": 60000,
        "objetivo": "lesion",
        "efecto": "cura tu lesión activa y deja la probabilidad en 0%.",
    },
}


EQUIPAMIENTO = {
    "casco": {
        "nombre": "Casco",
        "emoji": "🎩",
        "calidades": CALIDADES,
        "precio_base": 1000,
    },
    "guantes": {
        "nombre": "Guantes",
        "emoji": "🤜",
        "calidades": CALIDADES,
        "precio_base": 1000,
    },
    "protector_bucal": {
        "nombre": "Protector Bucal",
        "emoji": "😁",
        "calidades": CALIDADES,
        "precio_base": 600,
    },
    "short": {
        "nombre": "Short",
        "emoji": "👖",
        "calidades": CALIDADES,
        "precio_base": 600,
    },
    "botas": {
        "nombre": "Botas",
        "emoji": "👟",
        "calidades": CALIDADES,
        "precio_base": 800,
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


# Límites de duración de las acciones, en minutos.
MINUTOS_MINIMO = 1
MINUTOS_MAXIMO = 1440


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
