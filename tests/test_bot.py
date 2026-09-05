"""Cableado del bot: todas las extensiones cargan juntas sin chocar."""

import asyncio

import discord
from discord.ext import commands


def test_todas_las_extensiones_cargan_juntas(base_datos_limpia):
    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    # Los cogs de SSF y Box arrancan sus tareas periódicas al cargarse;
    # se usa un loop propio para cancelarlas y cerrarlo sin dejar tareas
    # pendientes.
    loop = asyncio.new_event_loop()

    try:
        async def cargar():
            await bot.load_extension("commands.general")
            await bot.load_extension("commands.madrugue")
            await bot.load_extension("commands.admin")
            await bot.load_extension("commands.ssf")
            await bot.load_extension("commands.box")

        loop.run_until_complete(cargar())

        nombres = {
            comando.qualified_name for comando in bot.tree.walk_commands()
        }

        assert "ping" in nombres
        assert "madrugue" in nombres
        assert "madrugue_stats" in nombres
        assert "admin ssf revivir" in nombres
        assert "admin box info" in nombres
        assert "ssf registrar" in nombres
        assert "box saldo" in nombres
    finally:
        bot.get_cog("Ssf").procesar_ssf_automatico.cancel()
        bot.get_cog("Box").comprobar_acciones.cancel()
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()
