import discord
from discord.ext import commands

from config import PREFIX


class NaikitoBot(commands.Bot):
    """Clase principal del bot."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        """Carga los módulos del bot antes de conectarse."""

        print("Configurando Naikito Bot...")

        await self.load_extension(
            "commands.general"
        )

        await self.tree.sync()

        print("Comandos de aplicación sincronizados.")

    async def on_ready(self):
        """Se ejecuta cuando el bot está conectado."""

        print(
            f"Naikito Bot conectado como {self.user}"
        )
        print(
            f"ID: {self.user.id}"
        )