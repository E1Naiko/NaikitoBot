import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from core.bot import NaikitoBot


def main():
    token = os.getenv("DISCORD_TOKEN")

    if not token:
        raise RuntimeError(
            "No se encontró DISCORD_TOKEN en las variables de entorno."
        )

    bot = NaikitoBot()
    bot.run(token)


if __name__ == "__main__":
    main()