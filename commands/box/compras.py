"""Ejecución de compras de Box, independiente de Discord.

La usan tanto los comandos ``/box comprar`` y ``/box tratamiento`` como los
botones de la tienda, así que no puede depender de ``interaction``: recibe
identificadores y devuelve el resultado ya formateado.
"""

from dataclasses import dataclass

from core.utils import ahora
from modules.box.services import (
    EQUIPAMIENTO,
    MEJORAS,
    NIVEL_MAXIMO_EQUIPAMIENTO,
    SUMINISTROS,
    TIPOS_SUMINISTRO,
    TRATAMIENTOS,
    calidad_equipamiento,
    comprar_equipamiento_progresivo,
    comprar_mejora,
    comprar_tratamiento,
    es_nivel_maximo,
    obtener_equipo,
    precio_equipamiento,
    precio_mejora,
    usar_suministro,
)

CATALOGOS = {
    "mejora": MEJORAS,
    "equipamiento": EQUIPAMIENTO,
    "tratamiento": TRATAMIENTOS,
    "suministro": SUMINISTROS,
}

NOMBRES_CATEGORIA = {
    "mejora": "Mejora",
    "equipamiento": "Equipamiento",
    "tratamiento": "Tratamiento",
    "suministro": "Suministro",
}


@dataclass(frozen=True)
class Resultado:
    """Resultado de un intento de compra."""

    exitoso: bool
    estado: str
    texto: str


def opciones_validas(categoria: str) -> str:
    catalogo = CATALOGOS.get(categoria, {})
    return ", ".join(f"`{clave}`" for clave in catalogo)


def _comprar_mejora(guild_id: int, user_id: int, clave: str) -> Resultado:
    configuracion = MEJORAS[clave]
    estado, saldo, nivel = comprar_mejora(
        guild_id=guild_id,
        user_id=user_id,
        mejora=clave,
        precio_base=configuracion["precio"],
        nivel_maximo=configuracion["maximo"],
    )

    if estado == "insuficiente":
        return Resultado(
            False,
            estado,
            f"⚠️ Necesitas el siguiente precio "
            f"(**{precio_mejora(configuracion['precio'], nivel)}**) "
            f"y tienes **{saldo}**.",
        )

    if estado == "maximo":
        return Resultado(
            False,
            estado,
            f"⚠️ Ya alcanzaste el nivel máximo (**{nivel}**).",
        )

    return Resultado(
        True,
        estado,
        f"✅ Compraste un nivel de **{configuracion['nombre']}**. "
        f"Nivel actual: **{nivel}**. Saldo restante: **{saldo}**.",
    )


def _comprar_equipamiento(guild_id: int, user_id: int, clave: str) -> Resultado:
    configuracion = EQUIPAMIENTO[clave]
    estado, saldo, nivel = comprar_equipamiento_progresivo(
        guild_id=guild_id,
        user_id=user_id,
        tipo_equipo=clave,
        precio_base=configuracion["precio_base"],
        nivel_maximo=NIVEL_MAXIMO_EQUIPAMIENTO,
    )

    if estado == "insuficiente":
        return Resultado(
            False,
            estado,
            f"⚠️ Necesitas **{precio_equipamiento(configuracion['precio_base'], nivel)}** "
            f"y tienes **{saldo}**.",
        )

    if estado == "maximo":
        return Resultado(
            False,
            estado,
            f"⚠️ Ya alcanzaste la calidad máxima "
            f"(**{calidad_equipamiento(clave, nivel)}**).",
        )

    # En "comprado", nivel es el nivel ya incrementado.
    return Resultado(
        True,
        estado,
        f"✅ ¡Compraste una mejora de equipamiento!\n"
        f"{configuracion['emoji']} **{configuracion['nombre']}**: "
        f"{configuracion['calidades'][nivel - 1]} → "
        f"{configuracion['calidades'][nivel]}\n"
        f"💰 Saldo restante: **{saldo}$**",
    )


def _comprar_tratamiento(guild_id: int, user_id: int, clave: str) -> Resultado:
    configuracion = TRATAMIENTOS[clave]
    estado, saldo = comprar_tratamiento(
        guild_id=guild_id,
        user_id=user_id,
        precio=configuracion["precio"],
        ahora=ahora(),
        reinicia_probabilidad=configuracion["reinicia_probabilidad"],
    )

    if estado == "insuficiente":
        return Resultado(
            False,
            estado,
            f"⚠️ Necesitas **{configuracion['precio']}** y tienes **{saldo}**.",
        )

    if estado == "no_lesionado":
        return Resultado(False, estado, "⚠️ No estás lesionado.")

    return Resultado(
        True,
        estado,
        f"✅ Compraste **{configuracion['nombre']}**. "
        f"Saldo restante: **{saldo}**.",
    )


def _comprar_suministro(
    guild_id: int,
    user_id: int,
    clave: str,
) -> Resultado:
    """La entrada genérica necesita elegir el tipo: orienta al usuario."""

    configuracion = SUMINISTROS[clave]

    tipos = "\n".join(
        f"{tipo['emoji']} `{nombre_clave}` — **{tipo['nombre']}** "
        f"({tipo['precio']}$)"
        for nombre_clave, tipo in TIPOS_SUMINISTRO.items()
    )

    return Resultado(
        False,
        "elegir_tipo",
        f"🎒 **{configuracion['nombre']}**: elegí el suministro con "
        f"**/box suministro <tipo>**.\n\n{tipos}",
    )


def texto_tipos_suministro() -> str:
    """Lista los tipos de suministro disponibles para los comandos."""

    return ", ".join(
        f"`{clave}`"
        for clave in TIPOS_SUMINISTRO
    )


def usar_suministro_resultado(
    guild_id: int,
    user_id: int,
    tipo: str,
) -> Resultado:
    """Usa un suministro tipificado y devuelve el mensaje formateado."""

    configuracion = TIPOS_SUMINISTRO.get(tipo)

    if configuracion is None:
        return Resultado(
            False,
            "tipo_invalido",
            f"⚠️ Suministro no válido. Opciones: {texto_tipos_suministro()}",
        )

    estado, saldo = usar_suministro(
        guild_id=guild_id,
        user_id=user_id,
        objetivo=configuracion["objetivo"],
        precio=configuracion["precio"],
        ahora=ahora(),
    )

    if estado == "insuficiente":
        return Resultado(
            False,
            estado,
            f"⚠️ Necesitas **{configuracion['precio']}$** y "
            f"tienes **{saldo}$**.",
        )

    if estado == "lleno":
        return Resultado(
            False,
            estado,
            "ℹ️ Ya tienes la estadística al máximo. "
            "No se descontó dinero.",
        )

    if estado == "sin_lesion":
        return Resultado(
            False,
            estado,
            "ℹ️ No tienes ninguna lesión activa ni "
            "probabilidad acumulada. No se descontó dinero.",
        )

    if estado != "comprado":
        return Resultado(
            False,
            estado,
            "⚠️ No se pudo usar el suministro.",
        )

    # Detalle del estado tras la recuperación.
    objetivo = configuracion["objetivo"]

    if objetivo == "lesion":
        detalle = "🩹 Lesión curada y probabilidad en **0%**."
    else:
        equipo = obtener_equipo(guild_id, user_id)
        if objetivo == "vida":
            detalle = f"❤️ Vida: **{equipo['vida']}/{equipo['vida_maxima']}**."
        elif objetivo == "cansancio":
            detalle = f"😴 Cansancio: **{equipo['cansancio']}/{equipo['cansancio_maximo']}**."
        else:
            detalle = f"🛡️ Defensa: **{equipo['defensa']}/{equipo['defensa_maxima']}**."

    return Resultado(
        True,
        estado,
        f"✅ Usaste {configuracion['emoji']} **{configuracion['nombre']}**: "
        f"{configuracion['efecto']} {detalle}\n"
        f"💰 Saldo restante: **{saldo}$**.",
    )


MANEJADORES = {
    "mejora": _comprar_mejora,
    "equipamiento": _comprar_equipamiento,
    "tratamiento": _comprar_tratamiento,
    "suministro": _comprar_suministro,
}


def ejecutar_compra(
    guild_id: int,
    user_id: int,
    categoria: str,
    clave: str,
) -> Resultado:
    """Compra un artículo y devuelve el resultado con su mensaje listo.

    Nunca lanza por datos inválidos: devuelve un ``Resultado`` no exitoso.
    """

    manejador = MANEJADORES.get(categoria)
    if manejador is None:
        return Resultado(
            False,
            "categoria_invalida",
            f"⚠️ Categoría no válida. Opciones: "
            f"{', '.join(f'`{c}`' for c in MANEJADORES)}",
        )

    clave = clave.lower()
    if clave not in CATALOGOS[categoria]:
        nombre = NOMBRES_CATEGORIA[categoria]
        genero_masculino = categoria in {"equipamiento", "suministro"}
        return Resultado(
            False,
            "articulo_invalido",
            f"⚠️ {nombre} no válid{'o' if genero_masculino else 'a'}. "
            f"Opciones: {opciones_validas(categoria)}",
        )

    return manejador(guild_id, user_id, clave)


def siguiente_nivel_disponible(categoria: str, clave: str, nivel: int) -> bool:
    """Indica si el artículo todavía puede comprarse desde la tienda."""

    if categoria == "mejora":
        return nivel < MEJORAS[clave]["maximo"]

    if categoria == "equipamiento":
        return not es_nivel_maximo(clave, nivel)

    return True
