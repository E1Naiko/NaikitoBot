"""Pruebas del catálogo de narración y de su selección determinista.

Acá se cuida lo que ``py_compile`` no ve: que las 260 líneas de los catálogos
formateen, que ningún texto tenga una llave mal cerrada (un ``{atacante`` sin
su ``}`` revienta la narración de una pelea real cuando el azar elige esa
línea, no cuando se prueba) y que los nombres se asignen al peleador
correcto.
"""

import random
from collections import Counter

import pytest

from modules.box import constants
from modules.box.combate import Evento
from modules.box.narracion import (
    EVENTOS,
    MOMENTOS,
    NEUTROS,
    POOLS,
    ROLES,
    SUSTITUCIONES,
    Rol,
    apertura,
    cierre,
    dialogos,
    elegir_clave,
    formar,
    linea_de,
    pool,
    problemas_del_catalogo,
    recortar,
    veredicto,
)
from modules.box.fighting import planificar_pelea


def pelear(semilla=1, exp=(300_000, 150_000)):
    return planificar_pelea(
        nombres=("Rojo", "Azul"),
        experiencia=exp,
        vida_maxima=(32, 32),
        dano=(12, 10),
        defensa=(8, 6),
        semilla=semilla,
    )


def todas_las_lineas():
    for modo, pools in POOLS.items():
        for clave, entrada in pools.items():
            for indice, linea in enumerate(entrada.lineas):
                yield modo, clave, indice, linea


# ============================================================
# SALUD DEL CATÁLOGO
# ============================================================

def test_el_catalogo_no_tiene_problemas():
    assert problemas_del_catalogo() == []


def test_todos_los_textos_del_catalogo_formatean():
    """El test que habría agarrado el ``{atacante;`` de ``NARRACION_FIGHTING_INTENSO``."""

    for nombre, valor in vars(constants).items():
        if not nombre.startswith("NARRACION_"):
            continue

        for linea in valor.split("\n"):
            linea = linea.strip()

            if not linea:
                continue

            salida = linea.replace("{atacante}", "A").replace("{defensor}", "B")

            assert "{" not in salida and "}" not in salida, f"{nombre}: {linea}"


def test_los_placeholders_son_conocidos():
    import re

    for _, _, _, linea in todas_las_lineas():
        for clave in re.findall(r"\{([^{}]*)\}", linea):
            assert clave in SUSTITUCIONES, f"placeholder desconocido: {clave}"


def test_cada_pool_declara_su_papel_y_su_momento():
    for modo, pools in POOLS.items():
        for clave, entrada in pools.items():
            assert (modo, clave) in ROLES
            assert clave in MOMENTOS
            assert entrada.lineas, f"{modo}.{clave} está vacío"


def test_el_registro_cubre_todos_los_catalogos_de_constants():
    """Ningún ``NARRACION_*`` se queda afuera del motor por un typo."""

    declarados = set()

    for nombre in dir(constants):
        if not nombre.startswith("NARRACION_"):
            continue

        _, modo, clave = nombre.split("_", 2)
        declarados.add((modo, clave))

    en_registro = {
        (modo, clave) for modo, pools in POOLS.items() for clave in pools
    }

    assert declarados == en_registro


def test_ningun_pool_queda_inaccesible():
    """Un pool que ningún evento elige es texto escrito y nunca leído.

    Los de marca (comienzo, final, entre asaltos) los usa el propio render y
    el cántico depende de un interruptor de configuración.
    """

    from modules.box.narracion import CANAL_EXTRA, MARCAS

    for modo, pools in POOLS.items():
        alcanzables = set(NEUTROS[modo]) | set(MARCAS[modo].values()) | set(CANAL_EXTRA.get(modo, ()))

        for candidatas in EVENTOS[modo].values():
            alcanzables.update(candidatas)

        for clave, entrada in pools.items():
            assert clave in alcanzables, f"{modo}.{clave} no lo elige nada"


def test_todos_los_eventos_del_motor_tienen_pool():
    from modules.box.combate import TIPOS_EVENTO

    for modo in POOLS:
        for tipo in TIPOS_EVENTO:
            assert tipo in EVENTOS[modo], f"{modo}: falta {tipo}"


# ============================================================
# SELECCIÓN DETERMINISTA Y ANTI-REPETICIÓN
# ============================================================

def test_los_dialogos_de_un_asalto_no_se_repiten():
    for semilla in range(25):
        plan = pelear(semilla)

        for indice in range(len(plan.asaltos)):
            lineas = dialogos(plan, indice, plan.dialogos_por_round)
            assert len(lineas) == len(set(lineas)), f"semilla {semilla}: líneas repetidas"


def test_renderizar_dos_veces_dá_lo_mismo():
    plan = pelear(9)

    for revelados in range(1, plan.dialogos_por_round + 1):
        assert dialogos(plan, 0, revelados) == dialogos(plan, 0, revelados)


def test_re_renderizado_no_cambia_lo_ya_mostrado():
    """El catch-up no reescribe la historia: las líneas viejas siguen ahí."""

    plan = pelear(13)
    primero = dialogos(plan, 0, 3)
    despues = dialogos(plan, 0, 7)

    assert despues[:3] == primero


def test_se_rellena_el_asalto_aun_cuando_hay_pocos_eventos():
    plan = pelear(4)
    asalto = plan.asaltos[0]

    assert len(asalto.eventos) <= plan.dialogos_por_round
    assert len(dialogos(plan, 0, plan.dialogos_por_round)) == plan.dialogos_por_round


def test_un_pool_agotado_baja_al_neutro_en_vez_de_repetir():
    modo = "SPARRING"
    entrada = pool(modo, "CONTRA")  # 6 líneas: se agota en un asalto de 8

    usadas = set()
    claves = []

    for _ in range(len(entrada.lineas) + 2):
        clave, linea = linea_de(modo, "CONTRA", 3, 1, usadas)
        claves.append(clave)
        usadas.add(linea)

    assert claves[: len(entrada.lineas)] == ["CONTRA"] * len(entrada.lineas)
    assert all(clave != "CONTRA" for clave in claves[len(entrada.lineas):]), (
        "debería haber bajado al pool neutro"
    )


def test_la_misma_semilla_elige_el_mismo_mazo():
    def correr():
        usadas = set()
        salida = []

        for _ in range(6):
            clave, linea = linea_de("FIGHTING", "HUMILLADO", 77, 2, usadas)
            usadas.add(linea)
            salida.append(linea)

        return salida

    assert correr() == correr()


def test_dos_pools_distintos_no_pueden_devolver_la_misma_linea():
    """El refugio compartido era un agujero: dos eventos, la misma frase."""

    plan = pelear(2)

    for indice in range(len(plan.asaltos)):
        assert len(dialogos(plan, indice, plan.dialogos_por_round)) == len(
            set(dialogos(plan, indice, plan.dialogos_por_round))
        )


def _claves_elegidas(modo, tipo, tono, muestras=400, semilla=0, canticos=None):
    rng = random.Random(semilla)

    if canticos is None:
        claves = [elegir_clave(modo, tipo, tono, rng) for _ in range(muestras)]
    else:
        claves = [
            elegir_clave(modo, tipo, tono, rng, canticos) for _ in range(muestras)
        ]

    return Counter(claves)


def test_el_tono_sesga_pero_no_es_la_unica_fuente():
    """El tono tiene que aparecer, pero no puede ser el único texto del ring.

    Si mandara, un 10-0 con tono "remontada" narraría una remontada que nadie
    vio: el tono inclina la balanza, el resto del catálogo la sostiene.
    """

    elegido = _claves_elegidas("FIGHTING", "ataque", "HUMILLADO")

    assert elegido["HUMILLADO"] > 0
    assert sum(c for clave, c in elegido.items() if clave != "HUMILLADO") > 0
    assert elegido["HUMILLADO"] < sum(elegido.values())


def test_un_evento_desconocido_cae_al_relleno_del_modo():
    elegidas = _claves_elegidas("SPARRING", "tipo_inventado", "RITMO", muestras=40)

    assert set(elegidas) <= set(NEUTROS["SPARRING"])
    assert elegidas


# ============================================================
# ROLES: DE QUIÉN HABLA CADA FRASE
# ============================================================

@pytest.mark.parametrize("linea", ["{atacante} domina", "Bien {defensor}"])
def test_formar_sustituye_los_dos_nombres(linea):
    texto = formar(linea, Rol.ATACANTE_GANA, ("Rojo", "Azul"), 0)

    assert "{atacante}" not in texto and "{defensor}" not in texto


def test_el_atacante_gana_es_el_que_anota():
    texto = formar(
        "{atacante} conecta y {defensor} aguanta",
        Rol.ATACANTE_GANA,
        ("Rojo", "Azul"),
        1,
    )

    assert texto == "Azul conecta y Rojo aguanta"


def test_un_pool_de_atacante_que_falla_invierte_los_nombres():
    """``NARRACION_SPARRING_ERROR`` le habla al que la pega mal.

    Sin esta inversión, cuando gana el contrincante se le narran al otro sus
    propias virtudes: el error más difícil de ver en un combate.
    """

    bueno = formar("{atacante} falló, {defensor} responde", Rol.ATACANTE_GANA, ("A", "B"), 1)
    malo = formar("{atacante} falló, {defensor} responde", Rol.ATACANTE_FALLA, ("A", "B"), 1)

    assert bueno == "B falló, A responde"
    assert malo == "A falló, B responde"


def test_los_pools_de_tono_le_hablan_al_que_domina():
    from modules.box.narracion import protagonista_de

    plan = pelear(2)
    asalto = plan.asaltos[0]
    entrada = pool("FIGHTING", "HUMILLADO")
    evento = Evento("ataque", 1 - plan.ganador)

    assert protagonista_de(plan, asalto, evento, entrada) == plan.ganador


def test_los_pools_de_evento_le_hablan_al_del_intercambio():
    from modules.box.narracion import protagonista_de

    plan = pelear(2)
    asalto = plan.asaltos[0]
    entrada = pool("FIGHTING", "KO")
    evento = Evento("ko", 1 - plan.ganador)

    assert protagonista_de(plan, asalto, evento, entrada) == 1 - plan.ganador


def test_los_nombres_con_llaves_no_rompen_nada():
    """Un apodo tipo ``{x}`` no puede romper la narración de una pelea."""

    texto = formar("{atacante} ataca", Rol.ATACANTE_GANA, ("{roto}", "B"), 0)

    assert "{roto}" in texto


# ============================================================
# LÍMITES DE DISCORD
# ============================================================

def test_recortar_conserva_lo_mas_reciente():
    texto = "\n".join(f"línea {i}" for i in range(400))
    salida = recortar(texto, 200)

    assert len(salida) <= 200
    assert salida.rstrip().endswith("línea 399")


def test_recortar_no_devuelve_un_mensaje_vacio():
    assert recortar("x" * 5000, 200) != "…"


def test_un_asalto_completo_cabe_en_el_limite_de_mensaje():
    for semilla in range(40):
        plan = pelear(semilla)
        cuerpo = "\n".join(dialogos(plan, 0, plan.dialogos_por_round))

        assert len(cuerpo) < 2000


def test_apertura_anuncia_los_asaltos_pactados():
    plan = pelear(3)
    texto = apertura(plan, ("<@1>", "<@2>"))

    assert str(plan.asaltos_pactados) in texto
    assert "asaltos" in texto


def test_el_veredicto_muestra_marcador_y_barras():
    plan = pelear(5)
    texto = veredicto(plan, 0)

    assert "Asalto 1" in texto
    assert str(plan.asaltos[0].puntos[0]) in texto


def test_el_cierre_declara_al_ganador():
    plan = pelear(11)

    assert plan.nombres[plan.ganador] in cierre(plan)


def test_la_narracion_no_promete_lo_que_el_plan_no_cumple():
    """Nada de lines de 'NOCAUT' si el plan dice que fue a la decisión."""

    for semilla in range(60):
        plan = pelear(semilla)
        todo = "\n".join(
            "\n".join(dialogos(plan, i, plan.dialogos_por_round))
            for i in range(len(plan.asaltos))
        )

        if plan.metodo != "KO":
            assert "¡NOCÁUT" not in todo


def test_nombres_de_apodo_no_estiran_el_mensaje():
    """Un apodo de 32 caracteres entra 8 veces por asalto: hay que recortar."""

    from commands.box.narracion import LARGO_NOMBRE, nombre_visible

    class Miembro:
        display_name = "u" * 32

    assert len(nombre_visible(Miembro())) <= LARGO_NOMBRE
    assert nombre_visible(None) == "Boxeador"


# ============================================================
# EL CÁNTICO Y EL CONSENTIMIENTO DEL SERVIDOR
# ============================================================


def test_sin_consentimiento_el_cantico_no_se_pisa():
    """El único texto del catálogo que nombra a una persona real está gateado.

    No es estética: ``CANTICO`` corea el apodo de un miembro del servidor. Con
    el interruptor apagado no puede elegirse ni una vez, por muchas semillas
    que se prueben.
    """

    for muestras in (200, 2000, 5000):
        elegido = _claves_elegidas(
            "FIGHTING", "ataque", "INTENSO", muestras=muestras, canticos=False
        )

        assert "CANTICO" not in elegido


def test_con_consentimiento_el_cantico_existe():
    """Al revés: si el servidor lo autoriza, el pool no es texto muerto.

    Un ``if`` mal puesto (o un pool con el nombre mal escrito) dejaría el
    catálogo de 260 líneas con un pool inalcanzable, y eso solo se ve acá.
    """

    elegido = _claves_elegidas(
        "FIGHTING", "ataque", "INTENSO", muestras=4000, canticos=True
    )

    assert elegido["CANTICO"] > 0
    # Pero no manda: el cántico es un adorno cada tanto, no la narración.
    assert elegido["CANTICO"] < sum(elegido.values()) * 0.4


def test_el_sparring_no_canta():
    """El pool del cántico solo existe en FIGHTING: el sparring no lo pide."""

    elegido = _claves_elegidas(
        "SPARRING", "ataque", "MEDIDO", muestras=2000, canticos=True
    )

    assert "CANTICO" not in elegido
