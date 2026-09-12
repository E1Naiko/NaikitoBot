"""Motor de combate de Box: planifica peleas y sparrings.

Módulo **puro**: no ve la base de datos ni Discord, así que se puede probar
con una semilla fija (igual que ``modules.box.logic``).

La idea central es que el combate se resuelve **entero al aceptar el
desafío** y el resultado queda guardado como un plan serializable
(:meth:`Plan.a_json`). El narrador del cog solamente revela ese plan contra
el reloj, lo que da tres cosas gratis:

* reproducible: la misma ``semilla`` reproduce el mismo combate,
* a prueba de reinicios: lo que ya se leyó en el canal no cambia,
* sin trabajo por latido: no hace falta simular nada cada 15 segundos.

El desenlace se decide **antes** de narrar (modelo acondicionado): se sortea
un ganador con la probabilidad exacta que da la diferencia de experiencia y
después los asaltos se reparten de forma coherente con ese sorteo. Si el
resultado emergiera de contar puntos intercambio a intercambio, la
cantidad de asaltos deformaría la probabilidad (a 10 asaltos un 60 % por
intercambio es un 88 % de victorias) y acortar la pelea por diferencia de
nivel la volvería una moneda al aire.
"""

from dataclasses import dataclass
import json
import math
import random

# Métodos con los que puede terminar un combate.
METODO_DECISION = "DECISION"
METODO_KO = "KO"
METODO_ENTRENAMIENTO = "ENTRENAMIENTO"

TONOS = ("MEDIDO", "ESTRATEGICO", "INTENSO", "REMONTADA", "HUMILLADO")

# Tipos de intercambio que produce el motor. Cada modo los traduce a sus
# pools en ``modules.box.narracion``.
TIPOS_EVENTO = (
    "ataque",
    "defensa",
    "contra",
    "error",
    "presion",
    "lesion",
    "caida",
    "ko",
    "neutro",
    "stats",
    "ritmo",
    "movimiento",
)


@dataclass(frozen=True)
class Reglas:
    """Balance de un modo de combate.

    Los valores se leen de la configuración (``BOX_COMBATE_*``) y cada modo
    arma su propia instancia en ``fighting.py`` o ``sparring.py``.
    """

    rounds_maximo: int
    rounds_minimo: int
    dialogos_por_round: int
    intercambios_min: int
    intercambios_max: int
    neutrales: float
    prob_piso: float
    prob_tope: float
    suelo_exp: int
    compresion: float
    ko_base: float
    ko_por_brecha: float
    ko_desde_asalto: int
    vida_para_corte: int
    admite_ganador: bool
    puede_cortarse: bool
    # Divisor de la escala de daño: cuanto más grande, más golpe hace falta
    # para vaciar la barra de vida. Es LA perilla del balance (ver
    # ``BOX_COMBATE_ESCALA_DANO``): con 1.0 cualquier pelea es un nocaut en el
    # asalto 1 y con 8.0 nadie se cae nunca.
    escala_asaltos: float = 3.2

    def __post_init__(self):
        if not 1 <= self.rounds_minimo <= self.rounds_maximo <= 36:
            raise ValueError(
                "los asaltos deben cumplir 1 <= rounds_minimo <= "
                f"rounds_maximo <= 36, pero se recibió {self.rounds_minimo}"
                f"..{self.rounds_maximo}."
            )

        if not 1 <= self.intercambios_min <= self.intercambios_max:
            raise ValueError(
                "los intercambios deben cumplir intercambios_min <= "
                f"intercambios_max, pero se recibió {self.intercambios_min}"
                f"..{self.intercambios_max}."
            )

        if self.intercambios_max > self.dialogos_por_round:
            raise ValueError(
                "un asalto no puede tener más intercambios que huecos de "
                f"narración: {self.intercambios_max} > "
                f"{self.dialogos_por_round}."
            )

        if not 0 < self.prob_piso <= self.prob_tope < 1:
            raise ValueError(
                "la probabilidad debe cumplir 0 < prob_piso <= prob_tope "
                f"< 1, pero se recibió {self.prob_piso}..{self.prob_tope}."
            )

        if not 0 <= self.neutrales < 0.9:
            raise ValueError(
                "la banda de neutrales debe estar entre 0 y 0.9, pero se "
                f"recibió {self.neutrales}."
            )

        if self.escala_asaltos < 1:
            raise ValueError(
                "escala_asaltos debe ser mayor o igual que 1 para que un "
                f"asalto no vacíe la vida de un golpe, pero se recibió "
                f"{self.escala_asaltos}."
            )


@dataclass(frozen=True)
class Evento:
    """Una acción dentro de un asalto.

    ``gana`` es ``0`` para el retador, ``1`` para el contrincante y ``-1``
    cuando el intercambio no favorece a ninguno (relleno táctico).
    """

    tipo: str
    gana: int

    def a_dict(self) -> dict:
        return {"tipo": self.tipo, "gana": self.gana}

    @staticmethod
    def de_dict(datos: dict) -> "Evento":
        return Evento(tipo=datos["tipo"], gana=int(datos["gana"]))


@dataclass(frozen=True)
class Asalto:
    """Un asalto narrable, con su marcador de intercambio y la vida final."""

    numero: int
    puntos: tuple[int, int]
    ganador: int
    eventos: tuple[Evento, ...]
    vida: tuple[int, int]
    cansancio: tuple[int, int]

    def a_dict(self) -> dict:
        return {
            "numero": self.numero,
            "puntos": list(self.puntos),
            "ganador": self.ganador,
            "eventos": [evento.a_dict() for evento in self.eventos],
            "vida": list(self.vida),
            "cansancio": list(self.cansancio),
        }

    @staticmethod
    def de_dict(datos: dict) -> "Asalto":
        return Asalto(
            numero=int(datos["numero"]),
            puntos=(int(datos["puntos"][0]), int(datos["puntos"][1])),
            ganador=int(datos["ganador"]),
            eventos=tuple(
                Evento.de_dict(evento) for evento in datos["eventos"]
            ),
            vida=(int(datos["vida"][0]), int(datos["vida"][1])),
            cansancio=(
                int(datos["cansancio"][0]),
                int(datos["cansancio"][1]),
            ),
        )


@dataclass(frozen=True)
class Plan:
    """Combate completo y resuelto, listo para que el narrador lo revele."""

    modo: str
    semilla: int
    probabilidad: float
    tono: str
    asaltos_pactados: int
    asaltos: tuple[Asalto, ...]
    ganador: int
    metodo: str
    marcador: tuple[int, int]
    vida: tuple[int, int]
    vida_maxima: tuple[int, int]
    nombres: tuple[str, str]
    dialogos_por_round: int

    # ------------------------------------------------------------
    # Reloj del narrador
    # ------------------------------------------------------------
    @property
    def ciclo(self) -> int:
        """Latidos de un asalto: sus diálogos más el veredicto."""

        return self.dialogos_por_round + 1

    @property
    def latidos(self) -> int:
        """Latidos totales del combate; después de eso ya no hay nada."""

        return len(self.asaltos) * self.ciclo

    def posicion(self, latido: int) -> tuple[int, int]:
        """Traduce un latido global a ``(índice de asalto, diálogo)``.

        El último latido de cada asalto (``dialogo == dialogos_por_round``)
        es el veredicto del corner, no un diálogo más.
        """

        return divmod(max(0, latido), self.ciclo)

    def latido_final(self) -> int:
        """Latido en el que el combate ya terminó de narrarse."""

        return self.latidos

    # ------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------
    @property
    def brecha(self) -> int:
        return abs(self.marcador[0] - self.marcador[1])

    @property
    def destacado(self) -> int:
        """Quién rindió mejor, aunque el modo no declare ganador."""

        return 0 if self.marcador[0] >= self.marcador[1] else 1

    def resumen(self) -> str:
        """Una línea con el resultado, para el aviso de acción finalizada."""

        a, b = self.marcador

        if self.ganador < 0:
            return (
                f"sparring terminado {a}-{b} a favor de "
                f"{self.nombres[self.destacado]}"
            )

        return (
            f"{self.nombres[self.ganador]} gana {max(a, b)}-{min(a, b)} "
            f"por {self.metodo.lower()}"
        )

    # ------------------------------------------------------------
    # Serialización: esto es lo que vive en box_combates.plan
    # ------------------------------------------------------------
    def a_json(self) -> str:
        return json.dumps(
            {
                "modo": self.modo,
                "semilla": self.semilla,
                "probabilidad": round(self.probabilidad, 4),
                "tono": self.tono,
                "asaltos_pactados": self.asaltos_pactados,
                "ganador": self.ganador,
                "metodo": self.metodo,
                "marcador": list(self.marcador),
                "vida": list(self.vida),
                "vida_maxima": list(self.vida_maxima),
                "nombres": list(self.nombres),
                "dialogos_por_round": self.dialogos_por_round,
                "asaltos": [asalto.a_dict() for asalto in self.asaltos],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def de_json(texto: str) -> "Plan":
        datos = json.loads(texto)

        return Plan(
            modo=datos["modo"],
            semilla=int(datos["semilla"]),
            probabilidad=float(datos["probabilidad"]),
            tono=datos["tono"],
            asaltos_pactados=int(datos["asaltos_pactados"]),
            asaltos=tuple(
                Asalto.de_dict(asalto) for asalto in datos["asaltos"]
            ),
            ganador=int(datos["ganador"]),
            metodo=datos["metodo"],
            marcador=(int(datos["marcador"][0]), int(datos["marcador"][1])),
            vida=(int(datos["vida"][0]), int(datos["vida"][1])),
            vida_maxima=(
                int(datos["vida_maxima"][0]),
                int(datos["vida_maxima"][1]),
            ),
            nombres=tuple(datos["nombres"]),
            dialogos_por_round=int(datos["dialogos_por_round"]),
        )


# ============================================================
# PROBABILIDAD Y DURACIÓN
# ============================================================

def probabilidad_victoria(
    exp_a: int,
    exp_b: int,
    reglas: Reglas,
    bono_fuerza: tuple[float, float] = (1.0, 1.0),
) -> float:
    """Probabilidad de que ``a`` gane, con la experiencia comprimida.

    La experiencia no tiene tope (``BOX_EXPERIENCIA_POR_MINUTO`` por minuto
    de acción, y un desafío de 24 h reparte miles), así que el ratio crudo
    ``exp_a / (exp_a + exp_b)`` saturaría a 0 % o 100 % en cuanto uno de los
    dos lleva un mes boxeando. Se compara ``log1p`` de la experiencia y el
    resultado se acota entre ``prob_piso`` y ``prob_tope``: el más débil
    siempre gana algún intercambio, que es lo que hace creíble una remontada.

    ``bono_fuerza`` es el multiplicador que aporta el equipamiento de cada
    uno (ver ``logic.estadisticas_de_combate``). Entra *antes* del ``log1p`` a
    propósito: como la experiencia se compara en escala logarítmica, el equipo
    pesa bastante entre rivales parejos y casi nada cuando la diferencia de
    experiencia es de un orden de magnitud. Sin ese orden, un par de guantes
    Legendarios le ganarían a diez años de entrenamiento.
    """

    d = math.log1p(max(exp_a, 0) * bono_fuerza[0] + reglas.suelo_exp) - (
        math.log1p(max(exp_b, 0) * bono_fuerza[1] + reglas.suelo_exp)
    )

    probabilidad = 0.5 + reglas.compresion * math.tanh(d)

    return min(reglas.prob_tope, max(reglas.prob_piso, probabilidad))


def _dominacion(
    probabilidad: float,
    reglas: Reglas,
    recorrido: float = 1.0,
) -> float:
    """Cuánto del recorrido posible se usó: 0 es parejo, 1 es paliza.

    La fórmula de ``probabilidad_victoria`` nunca se mueve más de
    ``compresion`` del 50 %, así que esa —y no el tope— es la escala honesta.
    ``recorrido`` permite ajustar contra qué se mide: para la duración se usa
    el recorrido completo, y para el reparto de asaltos un 0.8, porque la
    tarjeta tiene que empezar a sentirse paliza antes de que la pelea se
    acorte al mínimo.
    """

    return min(
        1.0,
        abs(probabilidad - 0.5) / max(reglas.compresion * recorrido, 0.0001),
    )


def asaltos_programados(probabilidad: float, reglas: Reglas) -> int:
    """Cuántos asaltos se pegan: a mayor diferencia de nivel, menos asaltos.

    Se deriva del mismo ``probabilidad`` que gobernó el sorteo, nunca de la
    experiencia cruda, para que las dos reglas no se contradigan.

    Se normaliza contra ``compresion``, no contra el tope: la fórmula nunca se
    mueve más de ``compresion`` del 50 %, así que ese es el recorrido real. Con
    los valores por defecto la curva queda 0,50 → 9 asaltos, 0,60 → 7, 0,75 →
    5, 0,88 o más → 3. Los impares se eligen *snappeando* al impar más cercano,
    no sumando uno: sumar siempre estira la pelea y con un máximo par la deja
    por encima de lo pactado en el canal.
    """

    objetivo = reglas.rounds_maximo - (
        reglas.rounds_maximo - reglas.rounds_minimo
    ) * _dominacion(probabilidad, reglas)

    rounds = round((objetivo - 1) / 2) * 2 + 1
    rounds = min(reglas.rounds_maximo, max(reglas.rounds_minimo, rounds))

    if es_impar(rounds):
        return rounds

    # Un rango encerrado entre dos pares no deja impar: se baja al de abajo,
    # que es el que acorta la pelea, antes que pasarse del máximo pactado.
    abajo = rounds - 1

    return abajo if abajo >= reglas.rounds_minimo else rounds


def es_impar(valor: int) -> bool:
    """Indica si la cantidad de asaltos no puede terminar en empate."""

    return valor % 2 == 1


# ============================================================
# PLANIFICACIÓN
# ============================================================

def planificar(
    *,
    modo: str,
    nombres: tuple[str, str],
    experiencia: tuple[int, int],
    vida_maxima: tuple[int, int],
    dano: tuple[int, int],
    defensa: tuple[int, int],
    reglas: Reglas,
    semilla: int,
    ganador_forzado: int | None = None,
    fatiga: tuple[float, float] = (1.0, 1.0),
    bono_fuerza: tuple[float, float] = (1.0, 1.0),
) -> Plan:
    """Resuelve el combate completo y devuelve el plan para narrarlo.

    ``ganador_forzado`` es el índice del elegido por el desafío (pelea): el
    plan se arma acondicionado a ese resultado, que es el que después cobra
    la recompensa. Si es ``None``, se sortea acá con la probabilidad de la
    experiencia. En el sparring no hay ganador forzado ni real.
    """

    rng = random.Random(semilla)

    probabilidad = probabilidad_victoria(
        experiencia[0],
        experiencia[1],
        reglas,
        bono_fuerza,
    )
    pactados = asaltos_programados(probabilidad, reglas)

    if not reglas.admite_ganador:
        ganador = -1
    elif ganador_forzado in (0, 1):
        ganador = ganador_forzado
    else:
        ganador = 0 if rng.random() < probabilidad else 1

    asaltos, vida, cansancio, metodo = _simular_asaltos(
        rng=rng,
        reglas=reglas,
        pactados=pactados,
        probabilidad=probabilidad,
        ganador=ganador,
        vida_maxima=vida_maxima,
        dano=dano,
        defensa=defensa,
        fatiga=fatiga,
    )

    marcador = contar_asaltos(asaltos)
    tono = _tono(probabilidad, ganador, asaltos, marcador, pactados)

    return Plan(
        modo=modo,
        semilla=semilla,
        probabilidad=probabilidad,
        tono=tono,
        asaltos_pactados=pactados,
        asaltos=asaltos,
        ganador=ganador,
        metodo=metodo,
        marcador=marcador,
        vida=vida,
        vida_maxima=vida_maxima,
        nombres=nombres,
        dialogos_por_round=reglas.dialogos_por_round,
    )


def _simular_asaltos(
    *,
    rng: random.Random,
    reglas: Reglas,
    pactados: int,
    ganador: int,
    probabilidad: float,
    vida_maxima: tuple[int, int],
    dano: tuple[int, int],
    defensa: tuple[int, int],
    fatiga: tuple[float, float] = (1.0, 1.0),
):
    """Genera los asaltos con su reparto de puntos y su daño acumulado.

    El que va abajo puede derribar al líder, pero no noquearlo: la vida del
    ganador declarado tiene un piso de un punto. Sin ese piso, un golpe de
    suerte en el asalto 2 le daría el combate al que el sorteo ya había
    declarado perdedor, y la narración contradeciría la recompensa que paga
    ``_liquidar_accion``. El corte, en cambio, siempre lo ejecuta el que
    gana: el nocaut es la *forma* en que termina, no la decisión.
    """

    vida = [float(vida_maxima[0]), float(vida_maxima[1])]
    cansancio = [0, 0]
    asaltos: list[Asalto] = []
    metodo = METODO_DECISION if reglas.admite_ganador else METODO_ENTRENAMIENTO

    dueños = _repartir_asaltos(rng, pactados, ganador, reglas, probabilidad)

    for numero in range(1, pactados + 1):
        dueno = dueños[numero - 1]

        eventos, puntos = _intercambios_del_asalto(rng, reglas, numero, dueno)

        # El daño se calibra contra la longitud del combate: una pelea pactada a
        # tres asaltos golpea más fuerte por intercambio que una a once, así
        # "más diferencia = más corto" se siente en el ring y no solo en el
        # tablero.
        escala = max(vida_maxima[0], vida_maxima[1]) / max(
            1.0, pactados * reglas.escala_asaltos
        )
        recibidos = [0.0, 0.0]
        for evento in eventos:
            if evento.gana < 0:
                continue
            recibidos[1 - evento.gana] += _golpe(
                rng, dano, defensa, cansancio, evento.gana, escala
            )

        caido_previo = -1
        for indice in (0, 1):
            piso = _piso_de_vida(reglas, ganador, indice, numero)
            anterior = vida[indice]
            vida[indice] = max(piso, vida[indice] - recibidos[indice])
            if anterior > 0 and vida[indice] <= 0:
                caido_previo = indice
            # La fatiga la marca el calzado: el que menos se cansa llega entero
            # al último tercio y ahí es donde se destruye el otro.
            cansancio[indice] = min(
                vida_maxima[indice],
                cansancio[indice] + round(rng.randint(2, 5) * fatiga[indice]),
            )

        # El líder fue al piso pero aguantó el conteo: se narra la caída, no
        # el nocaut, y el asalto sigue perteneciendo al que lo ganó.
        if caido_previo < 0 and vida[ganador if ganador in (0, 1) else 0] <= 1:
            sobreviviente = ganador if ganador in (0, 1) else 0
            if rng.random() < 0.25:
                eventos = eventos + (Evento("caida", 1 - sobreviviente),)

        noqueado = -1
        for indice in (0, 1):
            if vida[indice] <= 0 and indice != ganador:
                noqueado = indice

        if noqueado >= 0:
            asaltos.append(
                Asalto(
                    numero=numero,
                    puntos=puntos,
                    ganador=1 - noqueado,
                    eventos=eventos + (Evento("ko", 1 - noqueado),),
                    vida=(int(vida[0]), int(vida[1])),
                    cansancio=(cansancio[0], cansancio[1]),
                )
            )
            if reglas.admite_ganador:
                metodo = METODO_KO
            break

        asaltos.append(
            Asalto(
                numero=numero,
                puntos=puntos,
                ganador=dueno,
                eventos=eventos,
                vida=(int(vida[0]), int(vida[1])),
                cansancio=(cansancio[0], cansancio[1]),
            )
        )

        if not _puede_cortarse(rng, reglas, numero, asaltos, vida, ganador):
            continue

        asaltos[-1] = Asalto(
            numero=asaltos[-1].numero,
            puntos=asaltos[-1].puntos,
            ganador=ganador,
            eventos=asaltos[-1].eventos
            + (Evento("caida", ganador), Evento("ko", ganador)),
            vida=asaltos[-1].vida,
            cansancio=asaltos[-1].cansancio,
        )
        metodo = METODO_KO
        break

    return (
        tuple(asaltos),
        (int(vida[0]), int(vida[1])),
        (cansancio[0], cansancio[1]),
        metodo,
    )


def _piso_de_vida(
    reglas: Reglas,
    ganador: int,
    indice: int,
    numero: int,
) -> float:
    """Hasta dónde puede bajar la vida de un peleador dentro del asalto.

    El perdedor declarado puede llegar a cero: ahí existe el nocaut. El
    ganador se queda con un punto de reserva, porque su victoria ya está
    decidida y un golpe de suerte no puede cambiar el resultado que cobra la
    acción. En el sparring ninguno baja de uno: ahí nadie noquea a nadie.
    """

    if not reglas.admite_ganador or ganador not in (0, 1):
        return 1.0

    if indice == ganador or numero < reglas.ko_desde_asalto:
        return 1.0

    return 0.0


def _puede_cortarse(
    rng: random.Random,
    reglas: Reglas,
    numero: int,
    asaltos: list[Asalto],
    vida: list[float],
    ganador: int,
) -> bool:
    """ Decide si el corner para la pelea antes del límite.

    Solo cuando la diferencia de asaltos ya duele y el que va abajo está
    golpeado: es el mismo disparador que justifica narrar un ``KO``, así la
    frase no contradice lo que pasó en el ring.
    """

    if not (reglas.puede_cortarse and reglas.admite_ganador):
        return False

    if numero < reglas.ko_desde_asalto:
        return False

    marcador = contar_asaltos(tuple(asaltos))

    if abs(marcador[0] - marcador[1]) < 2:
        return False

    if ganador not in (0, 1) or marcador[ganador] <= marcador[1 - ganador]:
        return False

    if vida[1 - ganador] > reglas.vida_para_corte:
        return False

    return rng.random() < reglas.ko_base + reglas.ko_por_brecha * abs(
        marcador[0] - marcador[1]
    )


def _repartir_asaltos(
    rng: random.Random,
    pactados: int,
    ganador: int,
    reglas: Reglas,
    probabilidad: float,
) -> tuple[int, ...]:
    """Dueño de cada asalto, en orden de aparición.

    Cada asalto se sortea con una probabilidad escalada desde la del
    combate, y después se le asegura la mayoría al ganador declarado. Escalar
    en vez de repartir "la mayoría que salga" es lo que hace que dos parejas
    terminen 6-5 y no 11-0: si no, la diferencia de asaltos sería
    independiente del nivel real y el tono ``HUMILLADO`` saldría en peleas
    parejísimas.
    """

    if ganador not in (0, 1):
        # Sparring: nadie gana, pero cada asalto tiene dueño para que el
        # corner tenga de dónde sacar el comentario.
        return tuple(0 if rng.random() < 0.5 else 1 for _ in range(pactados))

    por_asalto = 0.55 + 0.34 * _dominacion(probabilidad, reglas, 0.8)

    perdedor = 1 - ganador
    dueños = [ganador if rng.random() < por_asalto else perdedor for _ in range(pactados)]

    minimo = pactados // 2 + 1
    while dueños.count(ganador) < minimo:
        # Se le da al ganador el último asalto que todavía era del rival: así
        # el cierre es del que gana, que es como se lee una pelea de boxeo.
        for indice in range(pactados - 1, -1, -1):
            if dueños[indice] == perdedor:
                dueños[indice] = ganador
                break
        else:
            break

    return tuple(dueños)


def _intercambios_del_asalto(
    rng: random.Random,
    reglas: Reglas,
    numero: int,
    dueno: int,
) -> tuple[tuple[Evento, ...], tuple[int, int]]:
    """Intercambios de un asalto: quién conecta, quién falla, quién nada.

    La cantidad es aleatoria dentro de ``intercambios_min..intercambios_max``
    para que los asaltos no se lean todos iguales. Los neutrales no suman
    punto: son el comentario táctico del que habla el relator cuando nadie
    anotó.
    """

    techo = min(reglas.intercambios_max, reglas.dialogos_por_round)
    total = rng.randint(reglas.intercambios_min, max(reglas.intercambios_min, techo))

    neutrales = int(round(total * reglas.neutrales))
    neutrales = max(0, min(total - 1, neutrales))
    puntuables = max(1, total - neutrales)
    neutrales = total - puntuables

    # El dueño del asalto tiene que terminar con más puntos que el rival: si
    # no, el veredicto diría "asalto para X (1-1)" y el marcador no cierra.
    puntos_otro = rng.randint(0, (puntuables - 1) // 2)
    puntos_ganador = puntuables - puntos_otro

    puntos = [0, 0]
    eventos: list[Evento] = []

    for indice, cantidad in ((dueno, puntos_ganador), (1 - dueno, puntos_otro)):
        for _ in range(cantidad):
            if indice in (0, 1):
                puntos[indice] += 1
            eventos.append(_evento_de_ataque(rng, indice, numero))

    for _ in range(neutrales):
        eventos.append(Evento(_tipo_neutro(rng), -1))

    rng.shuffle(eventos)

    return tuple(eventos), (puntos[0], puntos[1])


def _evento_de_ataque(rng: random.Random, atacante: int, numero: int) -> Evento:
    """Sortea el tipo de intercambio que gana ``atacante``.

    El ``lesion`` aparece cuando ya hay castigo acumulado; no reemplaza a la
    lesión formal de ``box_usuarios``, que se sigue sorteando al liquidar la
    acción: acá solo narra el dolor del asalto, para que el texto no
    contradiga a la base de datos.
    """

    sorteo = rng.random()

    if sorteo < 0.12:
        return Evento("defensa", atacante)

    if sorteo < 0.20:
        return Evento("contra", atacante)

    if sorteo < 0.28:
        return Evento("error", 1 - atacante)

    if sorteo < 0.38:
        return Evento("presion", atacante)

    if sorteo < 0.44 and numero >= 3:
        return Evento("lesion", atacante)

    return Evento("ataque", atacante)


def _tipo_neutro(rng: random.Random) -> str:
    """Tipo de un intercambio sin dueño: comentario táctico del relator."""

    return rng.choice(("neutro", "stats", "ritmo", "movimiento"))


def _golpe(
    rng: random.Random,
    dano: tuple[int, int],
    defensa: tuple[int, int],
    cansancio: list[int],
    atacante: int,
    escala: float,
) -> float:
    """Daño de un intercambio, en puntos de vida del rival.

    El poder relativo sale del ``box_equipo`` real (daño propio contra
    defensa ajena), que existía pero no participaba de nada. El cansancio
    suma, no resta: a medida que la pelea se alarga los golpes entran más
    limpios porque el que recibe ya no mueve la cabeza, y así una pelea a
    once asaltos se destruye de a poco en vez de resolverse en dos.
    """

    poder = (dano[atacante] + 6) / (defensa[1 - atacante] + 6)
    ruido = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5))
    desgaste = 1.0 + 0.1 * min(4, cansancio[1 - atacante] // 12)

    return round(max(0.4, escala * poder * ruido * desgaste), 2)


def contar_asaltos(asaltos: tuple[Asalto, ...]) -> tuple[int, int]:
    """Asaltos ganados por cada peleador."""

    contador = [0, 0]

    for asalto in asaltos:
        if asalto.ganador in (0, 1):
            contador[asalto.ganador] += 1

    return (contador[0], contador[1])


def _llego_perdiendo(ganador: int, asaltos: tuple[Asalto, ...]) -> bool:
    """Si el que terminó ganando llegó a perder por dos asaltos o más.

    El "por dos" importa: con un coin near-even el ganador casi siempre estuvo
    abajo por un asalto en algún momento, y sin el umbral ``REMONTADA`` se
    comía el 65 % de las peleas parejas. Dos asaltos de diferencia todavía es
    remontada, pero es una de verdad.
    """

    contador = [0, 0]

    for asalto in asaltos[:-1]:
        if asalto.ganador in (0, 1):
            contador[asalto.ganador] += 1

        if contador[1 - ganador] - contador[ganador] >= 2:
            return True

    return False


def _tono(
    probabilidad: float,
    ganador: int,
    asaltos: tuple[Asalto, ...],
    marcador: tuple[int, int],
    pactados: int,
) -> str:
    """Tono narrativo del combate, deducido de lo que pasó.

    Se decide una sola vez y el narrador lo usa como sesgo, no como única
    fuente de frases: si el tono se sorteara al azar, un 10-0 se narraría
    con "remontada" y se notaría el truco.
    """

    if not asaltos:
        return "MEDIDO"

    diferencia = abs(marcador[0] - marcador[1])

    if ganador in (0, 1) and min(marcador) == 0:
        # Lo dejó sin asaltos: eso es una paliza, no una pelea dura.
        return "HUMILLADO"

    if ganador in (0, 1) and _llego_perdiendo(ganador, asaltos):
        # El ganador estuvo abajo en el marcador en algún momento. Se mira el
        # recorrido y no solo la mitad inicial: una remontada del último round
        # también lo es, y con el criterio de "quién ganó los primeros" salía
        # en menos del 1 % de las peleas.
        return "REMONTADA"

    if diferencia <= 1:
        return "INTENSO"

    if abs(probabilidad - 0.5) >= 0.2:
        return "ESTRATEGICO"

    return "MEDIDO"
