import os

from dotenv import load_dotenv

from core.bot import NaikitoBot


load_dotenv()


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