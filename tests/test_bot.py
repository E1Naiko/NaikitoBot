"""Cableado del bot: todas las extensiones cargan juntas sin chocar."""

import asyncio

import discord
from discord.ext import commands


async def test_todas_las_extensiones_cargan_juntas(base_datos_limpia):
    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    # Los cogs de SSF y Box arrancan sus tareas periódicas al cargarse;
    # se las cancela al final para no dejar tareas pendientes.
    try:
        await bot.load_extension("commands.general")
        await bot.load_extension("commands.madrugue")
        await bot.load_extension("commands.lahora")
        await bot.load_extension("commands.admin")
        await bot.load_extension("commands.ssf")
        await bot.load_extension("commands.box")

        nombres = {
            comando.qualified_name for comando in bot.tree.walk_commands()
        }

        assert "ping" in nombres
        assert "madrugue" in nombres
        assert "madrugue_stats" in nombres
        assert "420_top" in nombres
        assert "420_stats" in nombres
        assert "admin ssf revivir" in nombres
        assert "admin box info" in nombres
        assert "ssf registrar" in nombres
        assert "box saldo" in nombres
    finally:
        ssf = bot.get_cog("Ssf")
        box = bot.get_cog("Box")

        if ssf is not None:
            ssf.procesar_ssf_automatico.cancel()

        if box is not None:
            box.comprobar_acciones.cancel()
            box.reducir_probabilidad_lesion.cancel()
            box.narrar_combates.cancel()

        await asyncio.sleep(0)
