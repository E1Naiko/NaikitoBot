"""Catálogo de diálogos y selección determinista para el narrador de Box.

Módulo **puro**: lee los catálogos de :mod:`modules.box.constants` y traduce
los eventos de :mod:`modules.box.combate` a líneas listas para el canal. No
sabe nada de Discord ni de sqlite.

Tres reglas de diseño:

* **Determinismo.** La línea de un diálogo es una función de
  ``(semilla, asalto, pool, uso)``. El asalto se re-renderiza entero en cada
  latido, así que el catch-up después de un reinicio es gratis y lo que ya
  se leyó en el canal no cambia nunca.
* **Roles.** Cada pool declara cómo usa ``{atacante}`` y ``{defensor}``:
  hay pools donde el atacante conecta (:data:`Rol.ATACANTE_GANA`) y pools
  donde el atacante la pega mal (:data:`Rol.ATACANTE_FALLA`, como
  ``NARRACION_SPARRING_ERROR``). Sin esa etiqueta, cuando gana el
  contrincante se narra todo al revés.
* **Bolsa por asalto.** Dentro de un asalto cada línea se usa una sola vez;
  si el pool se agota se baja al pool neutro, en vez de repetir la misma
  frase a los treinta segundos.
"""

from dataclasses import dataclass
from enum import Enum
import random

from config import BOX_COMBATE_CANTICOS

from modules.box import constants
from modules.box.combate import METODO_KO, Asalto, Plan

# ============================================================
# PAPELES DE CADA CATALOGO
# ============================================================


class Rol(Enum):
    """Cómo el pool reparte los nombres."""

    ATACANTE_GANA = "vence"
    ATACANTE_FALLA = "falla"
    NEUTRO = "neutro"


class Momento(Enum):
    """Familia del pool: marca del combate, evento duro, tono u observación."""

    MARCA = "marca"
    EVENTO = "evento"
    TONO = "tono"
    OBSERVACION = "observacion"


# Los únicos placeholders que el narrador sabe rellenar. Cualquier otra llave
# en un catálogo es un error de tipeo, no un dato.
SUSTITUCIONES = ("atacante", "defensor", "asaltos", "round", "marcador")

# El papel de cada pool, indexado por modo: en la pelea ``LESION`` es el
# castigo del atacante y en el sparring es el DT pidiendo control, aunque
# compartan clave.
ROLES = {
    ("FIGHTING", "HUMILLADO"): Rol.ATACANTE_GANA,
    ("FIGHTING", "INTENSO"): Rol.ATACANTE_GANA,
    ("FIGHTING", "REMONTADA"): Rol.ATACANTE_GANA,
    ("FIGHTING", "ESTRATEGICO"): Rol.ATACANTE_GANA,
    ("FIGHTING", "MEDIDO"): Rol.NEUTRO,
    ("FIGHTING", "COMIENZO"): Rol.NEUTRO,
    ("FIGHTING", "FINAL"): Rol.NEUTRO,
    ("FIGHTING", "ENTEROUNDS"): Rol.NEUTRO,
    ("FIGHTING", "STATS"): Rol.ATACANTE_GANA,
    ("FIGHTING", "CANTICO"): Rol.NEUTRO,
    ("FIGHTING", "CAIDA"): Rol.ATACANTE_GANA,
    ("FIGHTING", "KO"): Rol.ATACANTE_GANA,
    ("FIGHTING", "LESION"): Rol.ATACANTE_GANA,
    ("FIGHTING", "LESION_GRAVE"): Rol.ATACANTE_GANA,
    ("SPARRING", "COMIENZO"): Rol.NEUTRO,
    ("SPARRING", "FINAL"): Rol.NEUTRO,
    ("SPARRING", "ENTRE_ROUNDS"): Rol.NEUTRO,
    ("SPARRING", "ATAQUE"): Rol.ATACANTE_GANA,
    ("SPARRING", "REACCION"): Rol.NEUTRO,
    ("SPARRING", "PRESION"): Rol.ATACANTE_GANA,
    ("SPARRING", "DEFENSA"): Rol.ATACANTE_FALLA,
    ("SPARRING", "CONTRA"): Rol.ATACANTE_FALLA,
    ("SPARRING", "ERROR"): Rol.ATACANTE_FALLA,
    ("SPARRING", "MOVIMIENTO"): Rol.NEUTRO,
    ("SPARRING", "RITMO"): Rol.NEUTRO,
    ("SPARRING", "LESION"): Rol.NEUTRO,
}

MOMENTOS = {
    "HUMILLADO": Momento.TONO,
    "INTENSO": Momento.TONO,
    "MEDIDO": Momento.TONO,
    "REMONTADA": Momento.TONO,
    "ESTRATEGICO": Momento.TONO,
    "ATAQUE": Momento.TONO,
    "DEFENSA": Momento.TONO,
    "CONTRA": Momento.TONO,
    "ERROR": Momento.TONO,
    "PRESION": Momento.TONO,
    "COMIENZO": Momento.MARCA,
    "FINAL": Momento.MARCA,
    "ENTEROUNDS": Momento.MARCA,
    "ENTRE_ROUNDS": Momento.MARCA,
    "CAIDA": Momento.EVENTO,
    "KO": Momento.EVENTO,
    "LESION": Momento.EVENTO,
    "LESION_GRAVE": Momento.EVENTO,
    "STATS": Momento.OBSERVACION,
    "CANTICO": Momento.OBSERVACION,
    "MOVIMIENTO": Momento.OBSERVACION,
    "RITMO": Momento.OBSERVACION,
    "REACCION": Momento.OBSERVACION,
}

# Qué pools puede usar cada tipo de evento, en orden de preferencia. En el
# sparring no hay caídas ni nocaut: esos eventos se narran como golpe
# sentido, que es lo que diría el corner.
EVENTOS = {
    "FIGHTING": {
        "ataque": ("HUMILLADO", "INTENSO", "MEDIDO", "ESTRATEGICO", "REMONTADA"),
        "presion": ("HUMILLADO", "ESTRATEGICO", "INTENSO", "MEDIDO"),
        "defensa": ("ESTRATEGICO", "MEDIDO", "INTENSO"),
        "contra": ("ESTRATEGICO", "INTENSO", "MEDIDO"),
        "error": ("MEDIDO", "INTENSO", "HUMILLADO", "REMONTADA"),
        "lesion": ("LESION_GRAVE", "LESION"),
        "caida": ("CAIDA",),
        "ko": ("KO", "CAIDA"),
        "neutro": ("STATS", "MEDIDO"),
        "stats": ("STATS", "MEDIDO"),
        "ritmo": ("MEDIDO", "STATS"),
        "movimiento": ("MEDIDO", "ESTRATEGICO"),
    },
    "SPARRING": {
        "ataque": ("ATAQUE", "REACCION", "PRESION"),
        "presion": ("PRESION", "ATAQUE"),
        "defensa": ("DEFENSA", "REACCION"),
        "contra": ("CONTRA", "DEFENSA"),
        "error": ("ERROR", "CONTRA"),
        "lesion": ("LESION",),
        "caida": ("LESION",),
        "ko": ("LESION",),
        "neutro": ("RITMO", "MOVIMIENTO", "REACCION"),
        "stats": ("REACCION", "RITMO"),
        "ritmo": ("RITMO",),
        "movimiento": ("MOVIMIENTO",),
    },
}

# Pools que no estan en la tabla de eventos: solo se activan con un
# interruptor de configuracion, y el validador no los debe marcar como
# huérfanos.
CANAL_EXTRA = {"FIGHTING": ("CANTICO",), "SPARRING": ()}

# Marcas fijas del asalto, por modo. Van en una tabla porque los catálogos no
# se llaman igual en los dos modos (``ENTEROUNDS`` contra ``ENTRE_ROUNDS``) y
# una de las dos ortografías está mal escrita a propósito en el otro lado.
MARCAS = {
    "FIGHTING": {
        "comienzo": "COMIENZO",
        "reinicio": "ENTEROUNDS",
        "cierre": "FINAL",
    },
    "SPARRING": {
        "comienzo": "COMIENZO",
        "reinicio": "ENTRE_ROUNDS",
        "cierre": "FINAL",
    },
}

# Refugio cuando un pool se agota dentro del asalto.
NEUTROS = {
    "FIGHTING": ("MEDIDO", "STATS", "INTENSO"),
    "SPARRING": ("REACCION", "RITMO", "MOVIMIENTO"),
}


@dataclass(frozen=True)
class Pool:
    """Un catálogo de frases, con su semántica para el narrador."""

    modo: str
    clave: str
    rol: Rol
    momento: Momento
    lineas: tuple[str, ...]

    @property
    def peso(self) -> int:
        """Cuánto pesa al elegir: los pools chicos se eligen poco.

        Sin esto, un pool de cinco líneas dentro de un asalto de ocho
        diálogos se repite sí o sí.
        """

        return min(len(self.lineas), 24)


def _lineas(valor) -> tuple[str, ...]:
    """Acepta el catálogo como string con saltos de línea o como tupla."""

    if isinstance(valor, str):
        return tuple(l.strip() for l in valor.split("\n") if l.strip())

    return tuple(str(l).strip() for l in valor if str(l).strip())


def _cargar_pools() -> dict[str, dict[str, Pool]]:
    """Arma el registro a partir de las constantes, sin duplicar textos."""

    cargados: dict[str, dict[str, Pool]] = {"FIGHTING": {}, "SPARRING": {}}

    for nombre, valor in vars(constants).items():
        if not nombre.startswith("NARRACION_"):
            continue

        _, modo, clave = nombre.split("_", 2)

        if modo not in cargados:
            continue

        cargados[modo][clave] = Pool(
            modo=modo,
            clave=clave,
            rol=ROLES.get((modo, clave), Rol.NEUTRO),
            momento=MOMENTOS.get(clave, Momento.TONO),
            lineas=_lineas(valor),
        )

    return cargados


POOLS = _cargar_pools()


def pool(modo: str, clave: str) -> Pool:
    """Devuelve un pool del catálogo; ``KeyError`` si no existe."""

    return POOLS[modo][clave]


# ============================================================
# SELECCION DETERMINISTA
# ============================================================

def _mazo(semilla: int, asalto: int, clave: str, lineas: tuple[str, ...]) -> list[str]:
    """Orden determinista de las frases de un pool dentro de un asalto."""

    rng = random.Random(f"{semilla}:{asalto}:{clave}")
    mazo = list(lineas)
    rng.shuffle(mazo)

    return mazo


def elegir_clave(
    modo: str,
    tipo: str,
    tono: str,
    rng: random.Random,
    canticos: bool = BOX_COMBATE_CANTICOS,
) -> str:
    """Elige el pool de un evento, favoreciendo el tono del combate.

    El tono pesa un 60 % pero no manda: si mandara, un 10-0 se narraría con
    frases de remontada solo porque el tono salió así.

    ``canticos`` lo trae el narrador desde la decisión del servidor
    (``database.obtener_canticos``), no de la configuración global: el público
    nombra a un miembro real y eso se consiente por servidor.
    """

    candidatas = EVENTOS[modo].get(tipo) or NEUTROS[modo]

    if modo == "FIGHTING" and canticos and rng.random() < 0.12:
        return "CANTICO"

    if tono in candidatas and len(candidatas) > 1 and rng.random() < 0.6:
        return tono

    pesos = [pool(modo, clave).peso for clave in candidatas]

    return rng.choices(list(candidatas), weights=pesos, k=1)[0]


def linea_de(
    modo: str,
    clave: str,
    semilla: int,
    asalto: int,
    usadas,
) -> tuple[str, str]:
    """Devuelve ``(clave_efectiva, línea)`` sin repetir lo ya mostrado.

    Se pide una línea al pool indicado; si ya no le queda ninguna libre se
    baja al primer neutro con frases frescas, antes que repetir la misma
    frase a los treinta segundos. El conjunto ``usadas`` es del asalto, no del
    pool: si no, dos eventos que caen en pools distintos pueden terminar
    pidiendo la misma línea del refugio.
    """

    usadas = set(usadas or ())

    for nombre in (clave, *NEUTROS[modo]):
        entrada = pool(modo, nombre)
        mazo = _mazo(semilla, asalto, nombre, entrada.lineas)

        for linea in mazo:
            if linea not in usadas:
                return nombre, linea

    # Se acabó el repertorio del asalto: se repite, pero rotando una posición
    # para que no salga la misma línea dos veces seguidas.
    entrada = pool(modo, clave)
    mazo = _mazo(semilla, asalto, clave, entrada.lineas)

    return clave, mazo[len(usadas) % len(mazo)]


def formar(
    linea: str,
    rol: Rol,
    nombres: tuple[str, str],
    protagonista: int,
    **extras,
) -> str:
    """Rellena los nombres según el papel del pool.

    Con :attr:`Rol.ATACANTE_FALLA` el ``{atacante}`` es el que **falló** —los
    textos de ``ERROR``, ``DEFENSA`` y ``CONTRA`` están escritos desde ese
    punto de vista—, así que se le pasa el que pierde el intercambio.

    Se reemplaza con :meth:`str.replace` y no con ``format``: un apodo con
    una llave no puede romper la narración de una pelea en curso.
    """

    rival = 1 - protagonista

    if rol is Rol.ATACANTE_FALLA:
        atacante, defensor = nombres[rival], nombres[protagonista]
    else:
        atacante, defensor = nombres[protagonista], nombres[rival]

    texto = linea.replace("{atacante}", atacante).replace("{defensor}", defensor)

    for clave, valor in extras.items():
        texto = texto.replace("{" + clave + "}", str(valor))

    return texto


# ============================================================
# RENDER DE UN ASALTO
# ============================================================

def lider_de(plan: Plan, asalto: Asalto) -> int:
    """Índice del que va arriba, que es el referente de los pools de tono."""

    if plan.ganador in (0, 1):
        return plan.ganador

    if asalto.ganador in (0, 1):
        return asalto.ganador

    return plan.destacado


def protagonista_de(plan: Plan, asalto: Asalto, evento, entrada: Pool) -> int:
    """De quién habla la línea que se va a formatear.

    Los pools de evento (caída, nocaut, lesión) y los de "el atacante la
    pega mal" le hablan al dueño del intercambio. Los de tono y de
    observación le hablan al que domina el combate: son frases tipo "claro
    asalto para X" y, si se le atribuyen al que está siendo paseado, el texto
    contradice al marcador.
    """

    del_intercambio = (
        evento is not None
        and evento.gana in (0, 1)
        and (
            entrada.momento is Momento.EVENTO
            or entrada.rol is Rol.ATACANTE_FALLA
        )
    )

    if del_intercambio:
        return evento.gana

    return lider_de(plan, asalto)


def dialogos(
    plan: Plan,
    asalto_index: int,
    revelados: int,
    canticos: bool = BOX_COMBATE_CANTICOS,
) -> list[str]:
    """Texto de las líneas ya reveladas de un asalto.

    Es lo que el narrador llama en cada latido: se re-renderiza el asalto
    completo desde el plan, así que no hay nada que "appendear".
    """

    if asalto_index >= len(plan.asaltos):
        return []

    asalto = plan.asaltos[asalto_index]
    total = min(max(0, revelados), plan.dialogos_por_round)
    eventos = asalto.eventos

    rng = random.Random(f"{plan.semilla}:beats:{asalto_index}")
    lineas: list[str] = []

    # Líneas ya mostradas en este asalto. Se reconstruye de a una porque el
    # render es determinista: el estado del asalto es su propio índice.
    usadas: set[str] = set()

    for indice in range(total):
        evento = eventos[indice] if indice < len(eventos) else None
        tipo = evento.tipo if evento is not None else _tipo_de_relleno(rng)

        marcas = MARCAS[plan.modo]

        if indice == 0:
            clave = marcas["comienzo"] if asalto.numero == 1 else marcas["reinicio"]
        else:
            clave = elegir_clave(plan.modo, tipo, plan.tono, rng, canticos)

        clave, linea = linea_de(
            plan.modo,
            clave,
            plan.semilla,
            asalto.numero,
            usadas,
        )
        usadas.add(linea)
        entrada = pool(plan.modo, clave)

        lineas.append(
            formar(
                linea,
                entrada.rol,
                plan.nombres,
                protagonista_de(plan, asalto, evento, entrada),
                asaltos=plan.asaltos_pactados,
                round=asalto.numero,
                marcador=f"{asalto.puntos[0]}-{asalto.puntos[1]}",
            )
        )

    return lineas


def _tipo_de_relleno(rng: random.Random) -> str:
    """Tipo de un hueco del asalto sin evento: comentario táctico."""

    return rng.choice(("neutro", "ritmo", "movimiento", "stats"))


def _marcador(asaltos) -> tuple[int, int]:
    """Asaltos ganados por cada peleador hasta el momento."""

    contador = [0, 0]

    for asalto in asaltos:
        if asalto.ganador in (0, 1):
            contador[asalto.ganador] += 1

    return (contador[0], contador[1])


def marcador_de(asaltos) -> tuple[int, int]:
    """Versión pública de :func:`_marcador`, para los avisos del cog."""

    return _marcador(asaltos)


def veredicto(plan: Plan, asalto_index: int) -> str:
    """Línea de cierre de un asalto, con el marcador acumulado.

    Si el asalto terminó en una interrupción se anuncia el corte, no la
    planilla: el nocaut es la noticia, y el marcador queda abajo.
    """

    asalto = plan.asaltos[asalto_index]
    marcador = _marcador(plan.asaltos[: asalto_index + 1])
    corto = bool(asalto.eventos) and asalto.eventos[-1].tipo in ("ko", "caida")

    if plan.ganador < 0 or asalto.ganador < 0:
        # En el sparring el corner no anota: corrige. Cada asalto tiene un
        # dueño para poder comentarlos, pero nadie gana la sesión.
        tuvo = plan.nombres[asalto.ganador] if asalto.ganador in (0, 1) else "ninguno"

        return (
            f"⏱️ Asalto {asalto.numero}: nada para anotar, el corner corrige"
            f" (el mejor tramo fue de {tuvo}). {barras(asalto)}"
        )

    nombre = plan.nombres[asalto.ganador]

    if corto and asalto.eventos[-1].tipo == "ko":
        return (
            f"💥 ¡Se acabó en el asalto {asalto.numero}! **{nombre}** lo "
            f"liquidó y el marcador dice {marcador[0]}-{marcador[1]}. "
            f"{barras(asalto)}"
        )

    return (
        f"🔔 Asalto {asalto.numero} para **{nombre}** "
        f"({asalto.puntos[0]}-{asalto.puntos[1]} | combate "
        f"{marcador[0]}-{marcador[1]}). {barras(asalto)}"
    )


def apertura(plan: Plan, titulos: tuple[str, str]) -> str:
    """Cabecera del primer mensaje: qué se pelea, a cuántos asaltos y por qué.

    Anunciar la cantidad de asaltos es lo que hace que una pelea cortada en
    el asalto 3 se lea como una velada diseñada y no como un bug: en el boxeo
    real las peleas de undercard se pactan a cuatro asaltos.
    """

    motivo = (
        "por la diferencia de experiencia"
        if abs(plan.probabilidad - 0.5) >= 0.15
        else "los dos vienen parejos"
    )
    favorito = max(plan.probabilidad, 1 - plan.probabilidad)
    etiqueta = "Pelea" if plan.modo == "FIGHTING" else "Sparring"

    return (
        f"🥊 **{etiqueta} pactada a {plan.asaltos_pactados} asaltos** "
        f"{motivo}.\n"
        f"{titulos[0]} vs {titulos[1]} · favorito al {favorito:.0%} · "
        f"arranca 0-0."
    )


def cierre(plan: Plan) -> str:
    """Línea final del combate, con el resultado y el método."""

    a, b = plan.marcador

    if plan.ganador < 0:
        return f"🏁 Fin del sparring: **{a}-{b}**. Los dos bajan las manos."

    if plan.metodo == METODO_KO:
        # Con una interrupción el marcador no decide nada: se muestra tal
        # cual estaba, no "el ganador quedó 3-1" cuando iba 2-1 abajo.
        return (
            f"🏁 ¡{plan.nombres[plan.ganador]} lo termina antes del límite "
            f"en el asalto {len(plan.asaltos)} (marcador {a}-{b})."
        )

    return (
        f"🏁 Gana **{plan.nombres[plan.ganador]}** {max(a, b)}-{min(a, b)} "
        f"por {plan.metodo.lower()} sobre {plan.asaltos_pactados} asaltos."
    )


def barras(asalto: Asalto) -> str:
    """Estado físico del asalto, para el embed."""

    return (
        f"🩸 {asalto.vida[0]} · 😮‍💨 {asalto.cansancio[0]} | "
        f"🩸 {asalto.vida[1]} · 😮‍💨 {asalto.cansancio[1]}"
    )


def recortar(texto: str, limite: int = 2000) -> str:
    """Recorta al límite de Discord, conservando las líneas más recientes.

    Si un asalto se estira (nombres larguísimos o catálogos crecidos) se
    sueltan líneas desde arriba: lo último es lo que se está leyendo en vivo.
    """

    if len(texto) <= limite:
        return texto

    lineas = texto.split("\n")

    while len(lineas) > 1 and len("\n".join(lineas)) + 1 > limite:
        lineas.pop(0)

    salida = "\n".join(lineas)

    if len(salida) > limite - 1:
        salida = salida[-(limite - 1):]

    return "…" + salida


# ============================================================
# VALIDACION DEL CATALOGO
# ============================================================

def _claves_sueltas(linea: str) -> list[str]:
    """Nombres entre llaves, marcando una llave mal cerrada como error."""

    claves: list[str] = []
    actual = None

    for caracter in linea:
        if caracter == "{":
            if actual is not None:
                claves.append(actual + "?sin cerrar")
            actual = ""
        elif caracter == "}":
            claves.append("«suelta»" if actual is None else actual)
            actual = None
        elif actual is not None:
            actual += caracter

    if actual is not None:
        claves.append(actual + "?sin cerrar")

    return claves


def problemas_del_catalogo() -> list[str]:
    """Errores de los catálogos, para el test de ``tests/``.

    Revisa lo que ``py_compile`` no ve: que cada línea tenga sus claves de
    rol y momento declaradas, que no queden placeholders sueltos y que
    ningún evento apunte a un pool inexistente. Un solo texto con
    ``{atacante`` sin cerrar revienta la narración de una pelea real cuando
    el azar elige esa línea.
    """

    errores: list[str] = []

    for modo, pools in POOLS.items():
        for clave, entrada in pools.items():
            if (modo, clave) not in ROLES:
                errores.append(f"{modo}.{clave}: falta el rol en ROLES")

            if clave not in MOMENTOS:
                errores.append(f"{modo}.{clave}: falta el momento en MOMENTOS")

            if not entrada.lineas:
                errores.append(f"{modo}.{clave}: catálogo vacío")
                continue

            for indice, linea in enumerate(entrada.lineas):
                for llave in _claves_sueltas(linea):
                    if llave not in SUSTITUCIONES:
                        errores.append(
                            f"{modo}.{clave}[{indice}]: placeholder "
                            f"inválido '{llave}'"
                        )

                if len(linea) > 1900:
                    errores.append(
                        f"{modo}.{clave}[{indice}]: {len(linea)} caracteres"
                    )

        for tipo, candidatas in EVENTOS[modo].items():
            for clave in candidatas:
                if clave not in pools:
                    errores.append(
                        f"{modo}: el evento '{tipo}' apunta al pool "
                        f"inexistente {clave}"
                    )

        for clave in NEUTROS[modo]:
            if clave not in pools:
                errores.append(f"{modo}: neutro inexistente {clave}")

        for clave in pools:
            if clave in CANAL_EXTRA.get(modo, ()):
                continue

            if all(clave not in valores for valores in EVENTOS[modo].values()):
                if clave not in NEUTROS[modo] and MOMENTOS[clave] is not Momento.MARCA:
                    errores.append(f"{modo}.{clave}: ningún evento lo usa")

    return errores
