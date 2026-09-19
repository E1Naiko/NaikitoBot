"""Presentación: las respuestas principales usan embeds con secciones."""

import asyncio

import discord

from tests.harness import InteraccionFalsa, construir_cog


def ejecutar(coro):
    """Ejecuta un coroutine en un loop descartable (estas pruebas no tocan la base)."""

    loop = asyncio.new_event_loop()

    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return await metodo(cog, interaccion, *args)


def embed_ultimo(interaccion):
    ultimo = interaccion.respuestas[-1]
    assert ultimo.kwargs.get("embed") is not None, (
        "la respuesta debería ser un embed"
    )
    return ultimo.kwargs["embed"]


def nombres_secciones(embed):
    return [campo.name for campo in embed.fields]


def test_responder_general_crea_embed_con_seccion():
    interaccion = InteraccionFalsa(1, 42)
    from core.mensajes import responder

    ejecutar(
        responder(
            interaccion,
            "Título",
            "Descripción.",
            secciones_=[("Sección A", "valor")],
        )
    )

    embed = embed_ultimo(interaccion)
    assert embed.title == "Título"
    assert embed.description == "Descripción."
    assert nombres_secciones(embed) == ["Sección A"]


def test_responder_sin_vista_no_pasa_view_none():
    """Sin vista hay que enviar el centinela MISSING, nunca ``None``.

    ``send_message(view=None)`` revienta en discord.py con
    ``AttributeError: 'NoneType' object has no attribute 'is_finished'``
    (el doble del harness también lo valida).
    """
    interaccion = InteraccionFalsa(1, 42)
    from core.mensajes import responder

    ejecutar(responder(interaccion, "Título", "Descripción."))

    assert interaccion.respuestas[-1].kwargs.get("view", "ausente") is not None


def test_responder_texto_sin_vista_no_pasa_view_none():
    """Cubre el fallo real: ``/admin box cancelar`` → ``responder_texto``."""
    interaccion = InteraccionFalsa(1, 42)
    from core.mensajes import responder_texto

    ejecutar(responder_texto(interaccion, "🛑 **Acción cancelada correctamente.**"))

    assert interaccion.respuestas[-1].kwargs.get("view", "ausente") is not None


def test_responder_con_vista_la_reenvia():
    class Vista(discord.ui.View):
        pass

    interaccion = InteraccionFalsa(1, 42)
    vista = Vista()
    from core.mensajes import responder

    ejecutar(responder(interaccion, "Título", "Descripción.", view=vista))

    assert interaccion.respuestas[-1].kwargs.get("view") is vista


async def test_box_saldo_usa_embed_con_secciones(base_datos_limpia):
    from commands.box.cog import Box

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(1, 42)

    await llamar(cog, "saldo", interaccion)

    embed = embed_ultimo(interaccion)
    assert "Saldo" in embed.title
    secciones = nombres_secciones(embed)
    assert any("Experiencia" in nombre for nombre in secciones)
    assert any("Dinero" in nombre for nombre in secciones)


async def test_box_stats_usa_embed_con_secciones(base_datos_limpia):
    from commands.box.cog import Box

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(1, 42)

    await llamar(cog, "stats", interaccion)

    embed = embed_ultimo(interaccion)
    assert "Stats" in embed.title
    secciones = nombres_secciones(embed)
    assert any("Economía" in nombre for nombre in secciones)
    assert any("Desafíos" in nombre for nombre in secciones)
    assert any("Acción actual" in nombre for nombre in secciones)


async def test_madrugue_stats_usa_embed_con_secciones(base_datos_limpia):
    from commands.madrugue.cog import Madrugue
    from modules.madrugue.database import inicializar_db

    await inicializar_db()

    cog = construir_cog(Madrugue)
    interaccion = InteraccionFalsa(1, 42)

    await llamar(cog, "stats", interaccion)

    embed = embed_ultimo(interaccion)
    assert "Estadísticas" in embed.title
    secciones = nombres_secciones(embed)
    assert any("Puntos acumulados" in nombre for nombre in secciones)
    assert any("Mejor racha" in nombre for nombre in secciones)


async def test_ayuda_box_se_envia_como_embed(base_datos_limpia):
    from commands.box.cog import Box

    cog = construir_cog(Box)
    interaccion = InteraccionFalsa(1, 42)

    await llamar(cog, "ayuda", interaccion)

    assert interaccion.user.mensajes_directos
    assert "Ayuda de Box" in interaccion.user.mensajes_directos[0]
