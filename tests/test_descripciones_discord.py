"""Comprueba las descripciones que realmente se envían al sincronizar slash commands."""

import discord
import pytest
from discord.ext import commands, tasks


EXTENSIONES = (
    "commands.general", "commands.madrugue", "commands.lahora",
    "commands.admin", "commands.ssf", "commands.box",
)


def errores_descripcion(comando, ruta=()):
    """Valida comandos, subcomandos, opciones y traducciones de sus descripciones."""
    ruta = (*ruta, comando.get("name", "?"))
    errores = []
    if "description" in comando:
        descripcion = comando["description"]
        if not isinstance(descripcion, str) or not 1 <= len(descripcion) <= 100:
            errores.append(f"{' '.join(ruta)}: descripción {descripcion!r}")
    for idioma, descripcion in (comando.get("description_localizations") or {}).items():
        if not isinstance(descripcion, str) or not 1 <= len(descripcion) <= 100:
            errores.append(f"{' '.join(ruta)} ({idioma}): descripción {descripcion!r}")
    for opcion in comando.get("options", []):
        # Todos los subcomandos y parámetros deben tener descripción.
        if "description" not in opcion:
            errores.append(f"{' '.join((*ruta, opcion.get('name', '?')))}: sin descripción")
        errores.extend(errores_descripcion(opcion, ruta))
    return errores


@pytest.mark.parametrize("en_servidor", [False, True])
async def test_arbol_completo_respeta_limites_de_discord(
    base_datos_limpia, monkeypatch, en_servidor
):
    # No se ejecutan tareas periódicas ni se contacta a Discord: se inspecciona
    # el payload real construido por discord.py para ambos alcances de sync.
    monkeypatch.setattr(tasks.Loop, "start", lambda *_args, **_kwargs: None)
    bot = commands.Bot(command_prefix="$!", intents=discord.Intents.default())
    for extension in EXTENSIONES:
        await bot.load_extension(extension)

    guild = discord.Object(id=123456789) if en_servidor else None
    if guild is not None:
        bot.tree.copy_global_to(guild=guild)
    comandos = bot.tree.get_commands(guild=guild)
    assert comandos
    payload = [comando.to_dict(bot.tree) for comando in comandos]
    # Los comandos de contexto no llevan descripción; los slash sí.
    errores = [
        f"{comando['name']}: sin descripción"
        for comando in payload
        if comando.get("type") == 1 and "description" not in comando
    ]
    errores.extend(error for comando in payload for error in errores_descripcion(comando))
    assert not errores, "Descripciones rechazadas por Discord:\n" + "\n".join(errores)


def test_validador_detecta_descripciones_invalidas_anidadas_y_traducciones():
    datos = {
        "name": "admin", "description": "Administración",
        "options": [
            {"name": "420", "description": "420", "options": [
                {"name": "sincronizar", "description": "x" * 101,
                 "description_localizations": {"en-US": ""},
                 "options": [{"name": "canal"}]},
            ]},
        ],
    }
    errores = errores_descripcion(datos)
    assert any("admin 420 sincronizar:" in error for error in errores)
    assert any("en-US" in error for error in errores)
    assert any("admin 420 sincronizar canal: sin descripción" in error for error in errores)
