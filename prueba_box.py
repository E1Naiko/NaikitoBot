import asyncio
from core.bot import NaikitoBot


async def main():
    bot = NaikitoBot()

    print("=" * 60)
    print("PRUEBA DIRECTA DE setup_hook()")
    print("=" * 60)

    print("Cogs antes:", list(bot.cogs.keys()))

    try:
        await bot.setup_hook()
        print("\nSETUP_HOOK COMPLETADO CORRECTAMENTE")
    except Exception as e:
        print("\nERROR EN setup_hook")
        print("Tipo:", type(e).__name__)
        print("Mensaje:", e)

    print("\nCogs después:", list(bot.cogs.keys()))


asyncio.run(main())