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

# NARRACION DE FIGHTING

NARRACION_FIGHTING_HUMILLADO = (
    "¡SE ACTIVÓ EL MODO BESTIA!\n"
    "{atacante} dejó de boxear y empezó a cazar.\n"
    "¡Ahora sí, {defensor} tiene un problema enorme!\n"
    "{atacante} está encima, encima y encima.\n"
    "¡No le da un segundo de descanso!\n"
    "Esto ya parece una persecución dentro del ring.\n"
    "{defensor} está contra las cuerdas y {atacante} se viene encima.\n"
    "¡Qué presión! ¡Qué brutalidad de {atacante}!\n"
    "{atacante} camina hacia adelante como si el ring fuera suyo.\n"
    "¡Hay algo aterrador en la manera en que {atacante} está acortando la distancia!\n"
    "{defensor} está sintiendo la presión de cada segundo.\n"
    "¡No le está dando espacio para respirar!\n"
    "{atacante} está buscando terminar esto rápido.\n"
    "¡Esa mirada de {atacante} no promete nada bueno!\n"
    "{defensor} retrocede y {atacante} huele sangre.\n"
    "¡Se viene una tormenta sobre {defensor}!\n"
    "{atacante} está atacando con una violencia tremenda.\n"
    "¡Cada golpe parece tener intención de terminar la pelea!\n"
    "No quiere ganar por puntos. {atacante} quiere apagar las luces.\n"
    "¡La presión de {atacante} es absolutamente asfixiante!\n"
    "¡No alcanza con tener el apellido, hay que demostrarlo arriba del ring!\n"
    "{atacante} está construyendo su propia historia golpe a golpe.\n"
    "Hay presión, hay talento y hay mucho orgullo en este ring.\n"
    "{defensor} tiene que demostrar de qué está hecho.\n"
    "{defensor} está peleando como si tuviera algo mucho más grande en juego.\n"
    "¡SALÍ DE AHÍ, {defensor}!\n"
    "Claro asalto para {atacante}.\n"
    "Ahí está {atacante}, haciendo su negocio.\n"
    "{atacante} lo está haciendo quedar muy mal a {defensor}.\n"
    "Lo tiene totalmente desconcertado a {defensor}.\n"
    "{defensor} está sobreviviendo como puede.\n"
    "Lo está paseando por todo el ring {atacante}.\n"
    "Está dando una verdadera exhibición {atacante}.\n"
    "{defensor} no encuentra la manera de meterse en la pelea.\n"
    "Está boxeando con una mano atada {atacante}.\n"
    "¡Todavía no terminó!\n"
    "¡Vamos, {defensor}! ¡Una más!\n"
    "¡No te rindas!\n"
    "¡Seguí avanzando!\n"
)

NARRACION_FIGHTING_INTENSO = (
    "Los dos saben que después de esta noche ninguno va a ser el mismo.\n"
    "¡Acá no se pelea solamente por ganar, se pelea por dejar un legado!\n"
    "{atacante} no quiere ser la sombra de nadie.\n"
    "{defensor} está recibiendo castigo, pero todavía tiene fuego en los ojos.\n"
    "{defensor} no está peleando solamente contra {atacante} está peleando contra sus propias dudas.\n"
    "¡Acá se está poniendo a prueba el legado!\n"
    "{atacante} quiere demostrar que pertenece a este nivel.\n"
    "{defensor} se mete peligrosamente en la zona de fuego sin meter golpes.\n"
    "Me parece que la estrategia de {atacante} es demolerlo psicológicamente, y después terminarlo boxísticamente.\n"
    "¡Se están dando con todo!\n"
    "Acá no hay tiempo para respirar.\n"
    "Cada golpe puede cambiar la historia de esta pelea.\n"
    "¡Qué intercambio estamos viendo!\n"
    "Se plantaron los dos y ninguno quiere retroceder.\n"
    "¡Esto es una guerra en el centro del ring!\n"
    "{atacante} y {defensor} están dejando todo arriba del cuadrilátero.\n"
)

NARRACION_FIGHTING_MEDIDO = (
    "¡El público está de pie! ¡Esto parece una película!\n"
    "¡Dos guerreros, un ring y una sola oportunidad!\n"
    "¡Que alguien ponga la música porque esto se está poniendo cinematográfico!\n"
    "¡No hay estrategia que valga cuando el corazón empieza a hablar!\n"
    "¡Este es el momento que después se cuenta durante años!\n"
    "¡Todo lo entrenado, todo el sacrificio, todo termina acá!\n"
    "¡Uno de los dos va a salir de este ring convertido en leyenda!\n"
    "¡Todos tienen un plan hasta que empiezan a recibir golpes!\n"
    "¡El miedo también pelea!\n"
    "¡Acá no hay lugar para pestañear!\n"
    "¡Que alguien avise que esto es una pelea de boxeo y no una masacre!\n"
    "¡{defensor} acaba de conocer el verdadero significado de presión!\n"
    "Buena de derecha de {atacante}, contra {defensor}.\n"
    "Milimétrico el esquive de {defensor} ante el ataque de {atacante}.\n"
    "Tira {atacante}, pero no le queda otra que esquivar la respuesta de {defensor}.\n"
    "{defensor} tira ganchos bajos, {atacante} que aprovecha y descarga.\n"
    "Los dos se estudian, ninguno quiere regalar nada.\n"
    "{atacante} toca y sale rápidamente.\n"
    "{defensor} espera el momento justo para contraatacar.\n"
    "Buena lectura de pelea por parte de {atacante}.\n"
    "Poca acción, pero mucha inteligencia arriba del ring.\n"
    "{defensor} no entra en la trampa y mantiene la distancia.\n"
)

NARRACION_FIGHTING_REMONTADA = (
    "¡Bien {defensor}, bien, cerebral! Toca abajo, toca arriba, se va, vuelve.\n"
    "¡Está reaccionando {defensor}!\n"
    "Parecía perdido y ahora está nuevamente en pelea.\n"
    "{defensor} encontró la llave de la pelea.\n"
    "¡Qué manera de recuperarse {defensor}!\n"
    "Ahora es {atacante} el que tiene que cuidarse.\n"
    "Se dio vuelta completamente este asalto.\n"
    "{defensor} recuperó la confianza y se nota.\n"
    "¡Está creciendo {defensor} minuto a minuto!\n"
    "¡No importa cuántas veces caiga, {defensor} sigue levantándose!\n"
    "Esto ya no es solamente boxeo, es cuestión de corazón.\n"
    "{defensor} está peleando como si no existiera mañana.\n"
    "¡Hay que aguantar, respirar y seguir avanzando!\n"
    "{atacante} pega fuerte, pero {defensor} no quiere saber nada con rendirse.\n"
    "¡Todavía está de pie! ¡Todavía está en esta pelea!\n"
    "El cuerpo pide parar, pero la cabeza dice que hay que seguir.\n"
    "¡Este combate necesita corazón y {defensor} lo está demostrando!\n"
    "Podés derribarlo, pero todavía tenés que conseguir que no vuelva a levantarse.\n"
    "{defensor} está buscando dentro suyo lo que le queda para seguir peleando.\n"
    "¡La pelea se gana golpe a golpe, segundo a segundo!\n"
)

NARRACION_FIGHTING_ESTRATEGICO = (
    "{atacante} le está midiendo la confianza, le baja las manos, lo sobra.\n"
    "{atacante} está leyendo cada movimiento de {defensor}.\n"
    "Está jugando con los tiempos {atacante}.\n"
    "No se desespera {atacante}, sabe exactamente lo que quiere hacer.\n"
    "{defensor} quiere entrar, pero {atacante} ya sabe por dónde viene.\n"
    "Le está ganando la pelea desde la cabeza {atacante}.\n"
    "Mucho trabajo de piernas de {atacante}.\n"
    "{atacante} lo invita a entrar y prepara la respuesta.\n"
    "Está esperando el error {atacante}.\n"
)

NARRACION_FIGHTING_COMIENZO = (
    "¡Suena la campana y comienza el combate!\n"
    "¡Ya están en el centro del ring!\n"
    "Primeros segundos de estudio entre {atacante} y {defensor}.\n"
    "Los dos salen con cautela, nadie quiere regalar el primer golpe.\n"
    "{atacante} toma la iniciativa.\n"
    "{defensor} espera y observa qué propone su rival.\n"
    "¡Comenzó la acción!\n"
    "Primeros movimientos, primeras mediciones.\n"
    "Se miran, se estudian, empieza la partida de ajedrez.\n"
)

NARRACION_FIGHTING_FINAL = (
    "¡Se termina el combate!\n"
    "¡Suena la campana final!\n"
    "¡Se acabó! Los dos dejan todo en el centro del ring.\n"
    "¡No hay más tiempo!\n"
    "Final del combate, ahora todo queda en manos de los jueces.\n"
    "¡Qué pelea acabamos de presenciar!\n"
    "Los dos levantan los brazos esperando el veredicto.\n"
    "¡Últimos segundos y se terminó!\n"
    "Ya no hay nada más que hacer, terminó la pelea.\n"
)

NARRACION_FIGHTING_ENTEROUNDS = (
    "¡Campana! Comienza un nuevo asalto.\n"
    "Termina el descanso y vuelven a la acción.\n"
    "¡Vamos con otro asalto!\n"
    "Nuevo round, nueva historia.\n"
    "Los dos vuelven al centro del ring.\n"
    "Se reanuda la pelea.\n"
    "¡Arranca otro asalto y todavía está todo abierto!\n"
    "Después de un minuto de descanso, volvemos a la acción.\n"
    "¡Campana y a trabajar!\n"
)

NARRACION_FIGHTING_STATS = (
    "Los números favorecen a {atacante} hasta este momento.\n"
    "{atacante} está conectando con mayor claridad.\n"
    "{defensor} está absorbiendo demasiado castigo.\n"
    "Más actividad de {atacante} en este tramo de la pelea.\n"
    "{defensor} está teniendo dificultades para encontrar la distancia.\n"
    "El ritmo de {atacante} está empezando a marcar diferencias.\n"
    "Muy pareja la pelea hasta este momento.\n"
    "Ninguno consigue sacar una ventaja clara.\n"
    "La diferencia está en la precisión, no en la cantidad de golpes.\n"
    "{atacante} está aprovechando mejor sus oportunidades.\n"
)

NARRACION_FIGHTING_CANTICO = (
    "El Público: ¡{atacante}, compadre, la concha de tu madre!\n"
    "El Público: ¡{defensor}, compadre, la concha de tu madre!\n"
    "El Público: ¡OLE, OLE, OLE, OLE!\n"
    "El Público: ¡{atacante}, MUEEEERTOOOO!\n"
    "El Público: ¡{defensor}, MUEEEERTOOOO!\n"
    "El Público: ¡VAMOS {defensor}!\n"
    "El Público: Y YA LO VEEE, Y YA LO VEEEE, EL QUE NO SALTA, ES UN INGLEEES\n"
)

NARRACION_FIGHTING_CAIDA = (
    "¡SE FUE AL PISO {defensor}!\n"
    "¡CUENTA EL ÁRBITRO!\n"
    "¡{defensor} ESTÁ EN LA LONA!\n"
    "¡QUÉ GOLPE ACABA DE RECIBIR {defensor}!\n"
    "¡ESTUVO A NADA DE TERMINARSE LA PELEA!\n"
)

NARRACION_FIGHTING_KO = (
    "¡SE TERMINÓ! ¡SE TERMINÓ! ¡SE TERMINÓ! {defensor} NOCÁUT!\n"
    "¡NO HAY MÁS! ¡{defensor} NO PUEDE CONTINUAR!\n"
    "¡NOCÁUT! ¡NOCÁUT A FAVOR DE {atacante}!\n"
    "¡LO DURMIÓ! ¡QUÉ MANERA DE TERMINAR LA PELEA!\n"
    "¡EL ÁRBITRO DICE QUE {defensor} NO VA MÁS!\n"
    "¡{atacante} ACABA DE APAGARLE LAS LUCES A {defensor}!\n"
)

NARRACION_FIGHTING_LESION = (
    "{defensor} acusa el golpe... algo no está bien.\n"
    "{atacante} encontró una zona que parece estar molestando a {defensor}.\n"
    "{defensor} se toca la zona golpeada, claramente siente el impacto.\n"
    "¡Ojo con {defensor}! Parece que ese golpe dejó secuelas.\n"
    "{defensor} empieza a mostrar signos de dolor.\n"
    "Hay una molestia evidente en {defensor}.\n"
    "{atacante} está castigando una zona que ya parece comprometida.\n"
    "¡Ese golpe hizo daño! {defensor} quedó sentido.\n"
    "{defensor} intenta disimularlo, pero se nota que algo le duele.\n"
    "La lesión puede empezar a cambiar el desarrollo de esta pelea.\n"
    "{defensor} está peleando con una dificultad más encima.\n"
    "¡Qué problema para {defensor}! Esa lesión puede ser determinante.\n"
    "{atacante} se dio cuenta de la lesión y va directamente sobre ella.\n"
    "Cada golpe sobre esa zona parece dolerle el doble a {defensor}.\n"
    "{defensor} tiene que sobreponerse al dolor si quiere seguir en combate.\n"
)

NARRACION_FIGHTING_LESION_GRAVE = (
    "¡ALGO LE PASÓ A {defensor}! Se nota claramente el dolor.\n"
    "{defensor} está teniendo problemas para continuar con normalidad.\n"
    "¡La lesión es seria! {defensor} está protegiendo esa zona.\n"
    "{defensor} prácticamente está peleando con medio cuerpo comprometido.\n"
    "Esto puede ser un antes y un después para {defensor}.\n"
    "{atacante} detectó la debilidad y no piensa dejarla pasar.\n"
    "¡Qué momento para {defensor}! Ahora tiene que sacar todo lo que tiene adentro.\n"
)

# NARRACION DE SPARRING

NARRACION_SPARRING_COMIENZO = (
    "¡Vamos, empezó el sparring!\n"
    "¡{atacante}, empezá a medirlo! ¡{defensor}, no regales la distancia!\n"
    "¡Tranquilos los dos! ¡Primeros segundos, estudien al rival!\n"
    "¡{atacante}, marcá el ritmo! ¡{defensor}, leé los movimientos!\n"
)

NARRACION_SPARRING_ATAQUE = (
    "¡{atacante}, entrá con el jab!\n"
    "¡Bien, {atacante}! ¡Ahora combiná!\n"
    "¡{atacante}, dos golpes y salí!\n"
    "¡Trabajá el cuerpo, {atacante}!\n"
    "¡No tires de a uno, {atacante}! ¡Combiná!\n"
    "¡{atacante}, meté presión pero no te desesperes!\n"
    "¡Ahí! ¡Esa es la distancia que queríamos!\n"
)

NARRACION_SPARRING_DEFENSA = (
    "¡{defensor}, manos arriba!\n"
    "¡{defensor}, no te quedes en línea!\n"
    "¡Mové la cabeza, {defensor}!\n"
    "¡{defensor}, cerrá los codos!\n"
    "¡No retrocedas derecho, {defensor}! ¡Salí por un costado!\n"
    "¡{defensor}, esperá la contra!\n"
    "¡Bien esa defensa! ¡Ahora respondé!\n"
)

NARRACION_SPARRING_CONTRA = (
    "¡{atacante}, cuidado con la contra!\n"
    "¡{defensor}, ahí está la oportunidad!\n"
    "¡{defensor}, dejalo entrar y respondé!\n"
    "¡{atacante}, no te quedes después de tirar!\n"
    "¡Muy bien la lectura de {defensor}!\n"
    "¡{atacante}, cambiá el ángulo antes de volver a entrar!\n"
)

NARRACION_SPARRING_MOVIMIENTO = (
    "¡{atacante}, cortale el ring!\n"
    "¡{defensor}, usá las piernas!\n"
    "¡{atacante}, no lo persigas!\n"
    "¡{defensor}, no corras! ¡Movete con inteligencia!\n"
    "¡{atacante}, cerrá la salida!\n"
    "¡{defensor}, salí por tu izquierda!\n"
    "¡Los dos, mantengan el movimiento!\n"
)

NARRACION_SPARRING_ERROR = (
    "¡No, {atacante}! ¡Estás entrando demasiado derecho!\n"
    "¡{defensor}, no bajes las manos!\n"
    "¡{atacante}, no te quedes mirando después de golpear!\n"
    "¡{defensor}, no retrocedas con los pies cruzados!\n"
    "¡{atacante}, estás tirando demasiado desde lejos!\n"
    "¡{defensor}, estás regalando el centro del ring!\n"
)

NARRACION_SPARRING_PRESION = (
    "¡{atacante}, presionalo!\n"
    "¡{atacante}, no le des espacio para respirar!\n"
    "¡{defensor}, salí de las cuerdas!\n"
    "¡{atacante}, cortale la salida!\n"
    "¡{defensor}, no aceptes la pelea donde él quiere!\n"
    "¡{atacante}, mantenelo trabajando!\n"
)

NARRACION_SPARRING_RITMO = (
    "¡{atacante}, cambiá el ritmo!\n"
    "¡{defensor}, no te adaptes a su ritmo!\n"
    "¡{atacante}, acelerá ahora!\n"
    "¡{defensor}, hacelo fallar y recuperá la distancia!\n"
    "¡No sean predecibles!\n"
    "¡Cambien velocidades, cambien ángulos!\n"
)

NARRACION_SPARRING_REACCION = (
    "¡Eso, {atacante}! ¡Exactamente eso!\n"
    "¡Muy bien, {defensor}! ¡Excelente defensa!\n"
    "¡Bien la combinación de {atacante}!\n"
    "¡Perfecta la respuesta de {defensor}!\n"
    "¡Eso es lo que quiero ver!\n"
    "¡Muy buena lectura de los dos!\n"
    "¡Ahí apareció el contraataque de {defensor}!\n"
    "¡{atacante}, no gastes energía de más!\n"
    "¡{defensor}, respiración! ¡No te aceleres!\n"
    "¡{atacante}, usá el jab para controlar el ritmo!\n"
    "¡{defensor}, seguí moviendo las piernas!\n"
    "¡Los dos, respiren y mantengan la técnica!\n"
)


NARRACION_SPARRING_LESION = (
    "¡{atacante}, cuidado con esa zona! ¡Controlá los golpes!\n"
    "¡{defensor}, no fuerces esa lesión!\n"
    "¡{atacante}, bajá la potencia si está sentido!\n"
    "¡{defensor}, protegé esa zona y avisá si empeora!\n"
    "¡Tranquilos! ¡Esto es sparring, prioricen la técnica!\n"
)

NARRACION_SPARRING_ENTRE_ROUNDS = (
    "¡Escuchen los dos! Buen round, pero hay cosas para corregir.\n"
    "¡{atacante}, estás entrando demasiado derecho! ¡{defensor}, estás retrocediendo demasiado!\n"
    "¡{atacante}, quiero más trabajo al cuerpo! ¡{defensor}, buscá más la contra!\n"
    "Muy bien los dos. Ahora quiero que trabajen más el movimiento.\n"
    "¡{atacante}, no persigas la cabeza! ¡{defensor}, no regales el centro!\n"
    "Buen trabajo. Ahora quiero más técnica y menos fuerza.\n"
)

NARRACION_SPARRING_FINAL = (
    "¡Tiempo! ¡Se terminó el sparring!\n"
    "¡Muy buen trabajo los dos!\n"
    "¡Bajen las manos y recuperen el aire!\n"
    "¡Eso es lo que quería ver!\n"
    "¡Buen trabajo, {atacante}! ¡Buena defensa, {defensor}!\n"
)
