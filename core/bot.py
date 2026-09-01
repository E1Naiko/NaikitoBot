import discord
from discord.ext import commands

from config import GUILD_TEST, PREFIX


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
        """Carga los módulos y sincroniza los comandos."""

        print("Configurando Naikito Bot...")

        await self.load_extension(
            "commands.general"
        )

        await self.load_extension(
            "commands.madrugue"
        )

        await self.load_extension(
            "commands.admin"
        )
        await self.load_extension(
            "commands.ssf"
        )

        if GUILD_TEST:
            guild = discord.Object(id=GUILD_TEST)

            self.tree.copy_global_to(
                guild=guild
            )

            comandos = await self.tree.sync(
                guild=guild
            )

            print(
                f"Comandos sincronizados en servidor de prueba: "
                f"{len(comandos)}"
            )

        else:
            comandos = await self.tree.sync()

            print(
                f"Comandos globales sincronizados: "
                f"{len(comandos)}"
            )

    async def on_ready(self):
        """Se ejecuta cuando el bot está conectado."""

        print(
            f"Naikito Bot conectado como {self.user}"
        )
        print(
            f"ID: {self.user.id}"
        )