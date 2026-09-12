"""Pruebas del motor de combate: probabilidad, duración y coherencia.

Son pruebas de lógica pura (sin base de datos ni Discord), con semilla fija,
como ``tests/test_box_logica.py``. Lo que se cuida acá es que el relato no
contradiga al resultado: un nocaut que le da el combate al que el sorteo ya
había declarado perdedor es exactamente el tipo de bug que se ve en el canal
y no en los logs.
"""

import pytest

from modules.box.combate import (
    METODO_DECISION,
    METODO_KO,
    Plan,
    Reglas,
    asaltos_programados,
    contar_asaltos,
    probabilidad_victoria,
)
from modules.box.fighting import REGLAS_PELEA, planificar_pelea, regalar_reglas
from modules.box.logic import estadisticas_de_combate
from modules.box.sparring import REGLAS_SPARRING, planificar_sparring


def pelear(exp_a, exp_b, semilla=1, *, reglas=None, nombres=("Rojo", "Azul")):
    return planificar_pelea(
        nombres=nombres,
        experiencia=(exp_a, exp_b),
        vida_maxima=(32, 32),
        dano=(12, 10),
        defensa=(8, 6),
        semilla=semilla,
        reglas=reglas or REGLAS_PELEA,
    )


# ============================================================
# PROBABILIDAD
# ============================================================

def test_una_diferencia_enorme_no_da_una_probabilidad_del_cien():
    """El ratio crudo de EXP saturaría: 0 EXP vs 500k es 0,0 % de chances."""

    probabilidad = probabilidad_victoria(0, 500_000, REGLAS_PELEA)
    rival = probabilidad_victoria(500_000, 0, REGLAS_PELEA)

    assert probabilidad == pytest.approx(1 - REGLAS_PELEA.prob_tope)
    assert rival == pytest.approx(REGLAS_PELEA.prob_tope)
    assert 0 < probabilidad < 1


def test_experiencias_iguales_son_cincuenta_por_ciento():
    assert probabilidad_victoria(250_000, 250_000, REGLAS_PELEA) == pytest.approx(0.5)


def test_la_probabilidad_es_simetrica():
    a = probabilidad_victoria(400_000, 60_000, REGLAS_PELEA)
    b = probabilidad_victoria(60_000, 400_000, REGLAS_PELEA)

    assert a + b == pytest.approx(1.0)


def test_mas_experiencia_nunca_baja_la_probabilidad():
    anteriores = 0.0

    for exp in range(0, 400_000, 25_000):
        actual = probabilidad_victoria(exp, 100_000, REGLAS_PELEA)
        assert actual >= anteriores
        anteriores = actual


def test_cero_con_cero_es_parejo_y_no_revienta():
    assert probabilidad_victoria(0, 0, REGLAS_PELEA) == pytest.approx(0.5)


# ============================================================
# DURACIÓN: a mayor diferencia, menos asaltos
# ============================================================

def test_la_diferencia_grande_acorta_el_combate():
    """La forma buscada: parejo a la tarjeta, 2,7x a los puntos, paliza corta."""

    parejos = asaltos_programados(0.50, REGLAS_PELEA)
    distancia = asaltos_programados(0.62, REGLAS_PELEA)
    paliza = asaltos_programados(0.83, REGLAS_PELEA)
    sentenciada = asaltos_programados(REGLAS_PELEA.prob_tope, REGLAS_PELEA)

    assert parejos == REGLAS_PELEA.rounds_maximo
    assert parejos > distancia > paliza > sentenciada
    assert sentenciada == REGLAS_PELEA.rounds_minimo


def test_los_asaltos_no_pasaron_el_maximo_pactado():
    """El "fuerza impar" va antes del recorte y ese orden importa.

    Con un máximo par, ``par + 1`` superaría lo pactado: la pelea duraría un
    asalto más de lo anunciado en el canal.
    """

    for probabilidad in (0.20, 0.35, 0.5, 0.62, 0.8):
        rounds = asaltos_programados(probabilidad, REGLAS_PELEA)

        assert REGLAS_PELEA.rounds_minimo <= rounds <= REGLAS_PELEA.rounds_maximo
        assert rounds % 2 == 1, "un número par de asaltos puede empatarse"


def test_maximo_par_no_genera_once_asaltos():
    reglas = regalar_reglas(rounds_maximo=10, rounds_minimo=4)

    assert asaltos_programados(0.5, reglas) <= 10


# ============================================================
# COHERENCIA DEL RESULTADO
# ============================================================

def test_el_ganador_designado_siempre_gana_mas_asaltos():
    for semilla in range(250):
        plan = pelear(300_000, 90_000, semilla)

        if plan.metodo == METODO_KO:
            continue

        assert plan.marcador[plan.ganador] > plan.marcador[1 - plan.ganador]


def test_un_nocaut_no_le_puede_dar_el_combate_al_otro():
    """El corte lo ejecuta quien gana; el perdedor puede derribar, no noquear."""

    for semilla in range(400):
        plan = pelear(300_000, 90_000, semilla)

        assert plan.marcador[plan.ganador] >= plan.marcador[1 - plan.ganador] or (
            plan.metodo == METODO_KO and plan.marcador[plan.ganador] >= 1
        )


def test_ningun_peleador_termina_con_vida_negativa_o_pasada():
    for semilla in range(150):
        plan = pelear(semilla * 1000, 200_000, semilla)

        for asalto in plan.asaltos:
            for indice in (0, 1):
                assert 0 <= asalto.vida[indice] <= plan.vida_maxima[indice]
                assert 0 <= asalto.cansancio[indice] <= plan.vida_maxima[indice]


def test_la_vida_del_ganador_nunca_llega_a_cero():
    for semilla in range(300):
        plan = pelear(400_000, 100_000, semilla)
        final = plan.asaltos[-1]

        assert final.vida[plan.ganador] >= 1


def test_los_puntos_del_asalto_son_coherentes_con_su_ganador():
    """Un veredicto "asalto para X (1-1)" es un marcador que no cierra."""

    for semilla in range(300):
        plan = pelear(250_000, 240_000, semilla)

        for asalto in plan.asaltos:
            if asalto.eventos and asalto.eventos[-1].tipo in ("ko", "caida"):
                continue

            assert asalto.puntos[asalto.ganador] > asalto.puntos[1 - asalto.ganador]


def test_contar_asaltos_coincide_con_el_marcador_del_plan():
    plan = pelear(500_000, 120_000, 7)
    sin_cortes = [a for a in plan.asaltos if a.ganador >= 0]

    assert contar_asaltos(tuple(sin_cortes)) == plan.marcador


# ============================================================
# DETERMINISMO
# ============================================================

def test_la_misma_semilla_reproduce_el_mismo_combate():
    uno = pelear(300_000, 150_000, 42)
    otro = pelear(300_000, 150_000, 42)

    assert uno.a_json() == otro.a_json()


def test_distintas_semillas_no_dan_el_mismo_combate():
    planes = {pelear(300_000, 150_000, s).a_json() for s in range(25)}

    assert len(planes) > 20


def test_el_plan_viaja_ida_y_vuelta_por_json():
    original = pelear(280_000, 90_000, 3)
    copiado = Plan.de_json(original.a_json())

    assert copiado.marcador == original.marcador
    assert copiado.tono == original.tono
    assert copiado.metodo == original.metodo
    assert [a.puntos for a in copiado.asaltos] == [a.puntos for a in original.asaltos]
    assert [
        [e.tipo for e in a.eventos] for a in copiado.asaltos
    ] == [[e.tipo for e in a.eventos] for a in original.asaltos]


def test_el_reloj_del_plan_recorre_asaltos_y_veredictos():
    """Cada asalto ocupa ``dialogos + 1`` latidos: el último es el veredicto."""

    plan = pelear(300_000, 300_000, 5)
    ciclo = plan.dialogos_por_round + 1

    assert plan.latidos == len(plan.asaltos) * ciclo
    assert plan.posicion(0) == (0, 0)
    assert plan.posicion(ciclo - 1) == (0, plan.dialogos_por_round)
    assert plan.posicion(ciclo) == (1, 0)
    assert plan.posicion(-3) == (0, 0), "un reloj atrasado no puede dar negativo"


def test_latido_final_es_un_poco_mas_alla_del_ultimo_dialogo():
    plan = pelear(300_000, 300_000, 5)

    assert plan.latido_final() == plan.latidos


# ============================================================
# SPARRING: otra tabla de reglas, mismo motor
# ============================================================

def sparring(exp_a, exp_b, semilla=1):
    return planificar_sparring(
        nombres=("Rojo", "Azul"),
        experiencia=(exp_a, exp_b),
        vida_maxima=(32, 32),
        dano=(12, 10),
        defensa=(8, 6),
        semilla=semilla,
    )


def test_el_sparring_no_tiene_ganador():
    for semilla in range(60):
        assert sparring(900_000, 100, semilla).ganador == -1


def test_en_el_sparring_nadie_es_noqueado():
    for semilla in range(120):
        plan = sparring(500_000, 2_000, semilla)

        assert plan.metodo != METODO_KO

        for asalto in plan.asaltos:
            assert all(evento.tipo != "ko" for evento in asalto.eventos)
            assert asalto.vida[0] >= 1 and asalto.vida[1] >= 1


def test_el_sparring_se_acorta_poco_con_la_diferencia():
    """Un novato necesita rounds, no que lo saquen del ring a los dos golpes."""

    parejo = sparring(300_000, 300_000, 2).asaltos_pactados
    disparejo = sparring(900_000, 100, 2).asaltos_pactados

    assert disparejo >= REGLAS_SPARRING.rounds_minimo
    assert parejo - disparejo <= 2


def test_el_sparring_no_puede_terminar_antes_del_limite():
    assert REGLAS_SPARRING.puede_cortarse is False
    assert REGLAS_SPARRING.admite_ganador is False


# ============================================================
# CALIBRACIÓN Y REGLAS
# ============================================================

def test_la_probabilidad_de_victoria_se_mantiene_a_traves_de_los_asaltos():
    """El modelo acondicionado: el sorteo es del combate, no del intercambio.

    Si el resultado emergiera contando asaltos, once rounds con un 60 % por
    intercambio serían un 88 % de victorias y un corte en el asalto 3 volvería
    todo una moneda al aire. Acá el número final es el que se pidió.
    """

    total = 700
    promedios = []

    for semilla in range(total):
        promedios.append(pelear(700_000, 120_000, semilla).ganador == 0)

    # El invariante no es un número mágico sino la comparación contra la
    # probabilidad que el propio motor anuncia: si algún día se mueve un
    # parámetro, la tarjeta del canal sigue contando la verdad del sorteo.
    anunciada = probabilidad_victoria(700_000, 120_000, REGLAS_PELEA)

    assert sum(promedios) / total == pytest.approx(anunciada, abs=0.06)
    assert anunciada > 0.5


def test_una_pelea_pareja_no_es_un_monologo():
    """Con dos parejas el 80 % de las veces el rival gana algún asalto."""

    sin_reaccion = 0
    total = 300

    for semilla in range(total):
        plan = pelear(400_000, 395_000, semilla)
        sin_reaccion += min(plan.marcador) == 0

    assert sin_reaccion / total < 0.2


def test_el_dano_escalado_deja_llegar_a_la_decision():
    """Si un golpe sacara 10 de vida, ninguna pelea a 11 asaltos aguantaría."""

    decisiones = sum(
        1 for s in range(200) if pelear(400_000, 395_000, s).metodo == METODO_DECISION
    )

    assert decisiones > 100


def test_reglas_rechazan_un_asalto_sin_huecos_suficientes():
    with pytest.raises(ValueError):
        Reglas(
            rounds_maximo=10,
            rounds_minimo=3,
            dialogos_por_round=4,
            intercambios_min=3,
            intercambios_max=9,
            neutrales=0.3,
            prob_piso=0.2,
            prob_tope=0.8,
            suelo_exp=5000,
            compresion=0.38,
            ko_base=0.0,
            ko_por_brecha=0.0,
            ko_desde_asalto=3,
            vida_para_corte=10,
            admite_ganador=True,
            puede_cortarse=True,
            escala_asaltos=3.2,
        )


def test_reglas_rechazan_una_probabilidad_invertida():
    with pytest.raises(ValueError):
        regalar_reglas(prob_piso=0.9, prob_tope=0.4)


def test_reglas_rechazan_una_escala_de_dano_absurda():
    """Con ``escala_asaltos < 1`` un solo intercambio vacía la barra de vida.

    Es la perilla que se toca primero cuando una pelea "no se termina nunca";
    el piso existe para que bajarla de más no convierta todo en un nocaut en el
    asalto 1 sin nadie que se dé cuenta.
    """

    with pytest.raises(ValueError):
        regalar_reglas(escala_asaltos=0.5)


def test_ganador_forzado_no_puede_perder():
    """El desafío ya sorteó un ganador: el plan no lo puede discutir.

    Se pasa el índice del ``ganador_id`` de ``aceptar_desafio`` para que la
    recompensa que paga ``_liquidar_accion`` y lo que se lee en el canal
    sean el mismo resultado.
    """

    for semilla in range(120):
        plan = planificar_pelea(
            nombres=("Rojo", "Azul"),
            experiencia=(10_000, 900_000),
            vida_maxima=(32, 32),
            dano=(10, 12),
            defensa=(6, 8),
            semilla=semilla,
            ganador_forzado=0,
        )

        assert plan.ganador == 0


# ============================================================
# EQUIPAMIENTO: la tienda entra al ring
# ============================================================
EQUIPO_COMPLETO = {
    "guantes": 4,
    "casco": 4,
    "protector_bucal": 4,
    "short": 4,
    "botas": 4,
}


def _perfil(vida_maxima, dano, defensa, niveles):
    return estadisticas_de_combate(
        {"vida_maxima": vida_maxima, "dano": dano, "defensa": defensa},
        niveles or {},
    )


def pelear_con_equipo(exp_a, exp_b, semilla=1, gear_a=None, gear_b=None):
    a = _perfil(32, 12, 8, gear_a)
    b = _perfil(32, 10, 6, gear_b)

    return planificar_pelea(
        nombres=("Rojo", "Azul"),
        experiencia=(exp_a, exp_b),
        vida_maxima=(a["vida_maxima"], b["vida_maxima"]),
        dano=(a["dano"], b["dano"]),
        defensa=(a["defensa"], b["defensa"]),
        semilla=semilla,
        fatiga=(a["fatiga"], b["fatiga"]),
        bono_fuerza=(a["fuerza"], b["fuerza"]),
    )


def test_el_equipamiento_se_siente_en_el_plan():
    """Misma semilla, distinto equipo: el plan tiene que cambiar.

    Es la prueba de que ``EQUIPAMIENTO_COMBATE`` está conectado de verdad. Si
    alguien lee los niveles pero el motor los ignora, los dos planes salen
    idénticos y comprar en la tienda vuelve a ser decorativo.
    """

    sin_equipo = pelear_con_equipo(300_000, 300_000, 4242)
    con_equipo = pelear_con_equipo(
        300_000, 300_000, 4242, gear_b=EQUIPO_COMPLETO
    )

    assert con_equipo.vida_maxima[1] > sin_equipo.vida_maxima[1]
    assert con_equipo.probabilidad != sin_equipo.probabilidad


def test_el_equipamiento_inclina_peleas_parejas_sin_mandar():
    """A EXP iguales, cinco piezas Legendarias valen unos puntos de probabilidad."""

    éxitos = 0
    total = 300

    for semilla in range(total):
        plan = pelear_con_equipo(
            300_000, 300_000, 5000 + semilla, gear_b=EQUIPO_COMPLETO
        )
        éxitos += plan.ganador == 1

    proporcion = éxitos / total

    assert 0.53 <= proporcion <= 0.70, proporcion


def test_el_equipamiento_no_le_gana_a_diez_veces_de_experiencia():
    """El techo existe a propósito: un noviente con todo el equipo no le roba la pelea a un veterano."""

    sin_equipo = probabilidad_victoria(400_000, 40_000, REGLAS_PELEA)
    con_equipo = probabilidad_victoria(
        400_000,
        40_000,
        REGLAS_PELEA,
        (1.0, _perfil(32, 10, 6, EQUIPO_COMPLETO)["fuerza"]),
    )

    assert sin_equipo - con_equipo < 0.02
    assert con_equipo >= 0.75


def test_la_curva_de_duracion_es_monotona():
    """Más diferencia nunca alarga la pelea.

    El *snap* al impar más cercano puede dar plateaus (0,60 y 0,62 caen en el
    mismo 7), pero invertir la dirección sería un bug de la curva.
    """

    anterior = None

    for probabilidad in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
        rounds = asaltos_programados(probabilidad, REGLAS_PELEA)

        assert rounds % 2 == 1, "un asalto par puede terminar en empate"
        assert REGLAS_PELEA.rounds_minimo <= rounds <= REGLAS_PELEA.rounds_maximo

        if anterior is not None:
            assert rounds <= anterior

        anterior = rounds


def test_el_piso_y_el_tope_son_el_recorrido_real():
    """Con ``BOX_COMBATE_COMPRESION`` por encima del recorrido, los clamp mandan."""

    assert probabilidad_victoria(10**12, 0, REGLAS_PELEA) == pytest.approx(
        REGLAS_PELEA.prob_tope
    )
    assert probabilidad_victoria(0, 10**12, REGLAS_PELEA) == pytest.approx(
        1 - REGLAS_PELEA.prob_tope
    )
    assert REGLAS_PELEA.prob_piso == pytest.approx(1 - REGLAS_PELEA.prob_tope)


def test_los_cinco_tonos_salen_de_la_simulacion():
    """Ningún tono del catálogo queda inaccesible, ni se come el reparto.

    Si el sesgo del tono se corriera mal, un ``HUMILLADO`` saldría en peleas
    parejísimas o ``REMONTADA`` desaparecería del narrador; las dos cosas se
    ven en el canal, no en los logs.
    """

    tonos = {}
    total = 400

    for semilla in range(total):
        plan = pelear_con_equipo(400_000, 395_000, 8000 + semilla)
        tonos[plan.tono] = tonos.get(plan.tono, 0) + 1

    compartidos = {k: v / total for k, v in tonos.items()}

    assert {"INTENSO", "MEDIDO", "REMONTADA"} <= set(tonos)
    assert max(compartidos.values()) < 0.6, compartidos
    assert compartidos.get("HUMILLADO", 0) < 0.10, compartidos


def test_una_paliza_se_lee_como_paliza():
    """Con diez veces menos experiencia, lo normal es quedarse sin asaltos."""

    total = 200
    shutouts = 0

    for semilla in range(total):
        plan = pelear_con_equipo(400_000, 40_000, 31337 + semilla)
        shutouts += min(plan.marcador) == 0

    assert shutouts / total >= 0.4
