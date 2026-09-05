import discord

from discord import app_commands
from discord.ext import commands

from config import (
    GENERAL_CHANNEL_IDS,
    GUILD_ID,
    MADRUGUE_CHANNEL_IDS,
    PREFIX,
    SSF_CANALES_ID,
)

from modules.madrugue.database import (
    inicializar_db as inicializar_db_madrugue,
)

from modules.ssf.database import (
    inicializar_db as inicializar_db_ssf,
)


class RestrictedCommandTree(app_commands.CommandTree):
    """Restringe cada grupo de comandos a su canal correspondiente."""

    @staticmethod
    def _command_path(data: dict) -> str:
        partes = []
        actual = data

        while isinstance(actual, dict) and actual.get("name"):
            partes.append(str(actual["name"]))
            opciones = actual.get("options", [])
            actual = next(
                (
                    opcion
                    for opcion in opciones
                    if isinstance(opcion, dict)
                    and opcion.get("type") in {1, 2}
                    and "name" in opcion
                ),
                None,
            )

        return "/" + " ".join(partes)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        data = interaction.data or {}
        command_name = data.get("name")
        channel_id = interaction.channel_id
        command_path = self._command_path(data)

        if command_name == "admin":
            permitido = True
            zona = "administración"
            canales = set()
        elif channel_id in GENERAL_CHANNEL_IDS:
            permitido = command_name in {"ping", "box"}
            zona = "general, Box y administración"
            canales = GENERAL_CHANNEL_IDS
        elif channel_id in MADRUGUE_CHANNEL_IDS:
            permitido = bool(command_name and command_name.startswith("madrugue"))
            zona = "Madrugue"
            canales = MADRUGUE_CHANNEL_IDS
        elif channel_id in SSF_CANALES_ID:
            permitido = command_name == "ssf"
            zona = "SeptSinFP"
            canales = SSF_CANALES_ID
        else:
            permitido = False
            zona = "ningún comando"
            canales = (
                GENERAL_CHANNEL_IDS
                | MADRUGUE_CHANNEL_IDS
                | SSF_CANALES_ID
            )

        if permitido:
            print(f"[COMANDO] permitido={command_path}", flush=True)
            return True

        canales_texto = ", ".join(
            f"<#{canal_id}>"
            for canal_id in sorted(canales)
        )
        mensaje = (
            f"⚠️ Este canal solo permite comandos de {zona}."
            if canales_texto
            else "⚠️ Este canal no tiene comandos configurados."
        )
        await interaction.response.send_message(mensaje, ephemeral=True)
        print(f"[COMANDO] rechazado={command_path} canal={channel_id}", flush=True)
        return False

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        command_path = self._command_path(interaction.data or {})
        print(
            f"[COMANDO] error={command_path} "
            f"tipo={type(error).__name__}: {error}",
            flush=True,
        )
        await super().on_error(interaction, error)


class NaikitoBot(commands.Bot):
    """Clase principal del bot."""

    def __init__(self):

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
            tree_cls=RestrictedCommandTree,
        )

    async def on_interaction(self, interaction: discord.Interaction):
        """Registra en consola cada comando slash recibido por el bot."""

        if interaction.type == discord.InteractionType.application_command:
            command_path = RestrictedCommandTree._command_path(
                interaction.data or {}
            )
            print(
                f"[COMANDO] recibido={command_path} "
                f"usuario={interaction.user}({interaction.user.id}) "
                f"servidor={interaction.guild_id} "
                f"canal={interaction.channel_id}",
                flush=True,
            )

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command,
    ):
        """Registra en consola los comandos slash completados."""

        command_path = RestrictedCommandTree._command_path(
            interaction.data or {}
        )
        print(
            f"[COMANDO] completado={command_path} "
            f"usuario={interaction.user.id} "
            f"canal={interaction.channel_id}",
            flush=True,
        )

    # ========================================================
    # SETUP
    # ========================================================

    async def setup_hook(self):
        """Carga módulos, sincroniza comandos e inicia tareas."""

        print("Configurando Naikito Bot...")

        # ====================================================
        # BASE DE DATOS SSF
        # ====================================================

        inicializar_db_madrugue()
        print("Base de datos Madrugue inicializada.")

        inicializar_db_ssf()
        print("Base de datos SSF inicializada.")
        
        # ====================================================
        # CARGAR COMANDOS
        # ====================================================

        await self.load_extension(
            "commands.general"
        )

        await self.load_extension(
            "commands.madrugue"
        )

        await self.load_extension(
            "commands.admin"
        )
        
        admin_cog = self.get_cog("Admin")

        print()
        print("========== ADMIN LOCAL ==========")
        
        if admin_cog:
            print("Admin encontrado:", admin_cog)
        
            print("App commands del Admin:")
        
            for comando in admin_cog.walk_app_commands():
                print(
                    f"- {comando.qualified_name} | "
                    f"tipo={type(comando).__name__}"
                )
        
        print("=================================")
        print()

        await self.load_extension(
            "commands.ssf"
        )
        print("========== DEBUG CARGA BOX ==========")
        print("Cogs antes de cargar Box:", list(self.cogs.keys()))
        print("Box existente:", self.get_cog("Box"))
        print("====================================")

        await self.load_extension(
            "commands.box"
        )

        print("Box cargado correctamente:", self.get_cog("Box"))

        # ====================================================
        # SINCRONIZAR COMANDOS
        # ====================================================

        if GUILD_ID:

            guild = discord.Object(
                id=GUILD_ID
            )

            self.tree.copy_global_to(
                guild=guild
            )

            manualadd = self.tree.get_command(
                "admin"
            )
            
            print()
            print("========== DEBUG MANUALADD ==========")
            
            if isinstance(manualadd, app_commands.Group):
                print("Admin encontrado en Tree")

                for subcomando in manualadd.commands:
                    print(
                        f"Subcomando: {subcomando.name}"
                    )

                    if (
                        subcomando.name == "manualadd"
                        and isinstance(subcomando, app_commands.Command)
                    ):
                        print("PARÁMETROS MANUALADD:")

                        for parametro in subcomando.parameters:
                            print(
                                f"- {parametro.name} | "
                                f"requerido={parametro.required} | "
                                f"tipo={parametro.type}"
                            )
            
            print("=====================================")

            print()
            comandos = await self.tree.sync(
                guild=guild
            )

            print("COMANDOS REGISTRADOS EN DISCORD:")
            print("=" * 60)

            for comando in comandos:
                print(f"- {comando.name}")

                if isinstance(comando, app_commands.Group):
                    for subcomando in comando.commands:
                        print(f"  └── {subcomando.name}")

                        if isinstance(subcomando, app_commands.Command):
                            print("      OPCIONES:")

                            for opcion in subcomando.parameters:
                                print(
                                    f"      - {opcion.name} | "
                                    f"tipo={opcion.type} | "
                                    f"requerido={opcion.required}"
                                )

            print("=" * 60)

            print(
                "Comandos sincronizados en GUILD_ID: "
                f"{GUILD_ID} ({len(comandos)} comandos)"
            )

        else:

            comandos = await self.tree.sync()

            print(
                "Comandos sincronizados globalmente: "
                f"{len(comandos)}"
            )

            print()
            print("COMANDOS REGISTRADOS:")
            print("=" * 60)

            for comando in comandos:

                print(
                    f"- {comando.name} | "
                    f"tipo={type(comando).__name__}"
                )

                if isinstance(
                    comando,
                    app_commands.Group,
                ):

                    for subcomando in comando.commands:

                        print(
                            f"    └── {subcomando.name} | "
                            f"tipo={type(subcomando).__name__}"
                        )

                        if isinstance(
                            subcomando,
                            app_commands.Group,
                        ):

                            for subsubcomando in subcomando.commands:

                                print(
                                    f"        └── "
                                    f"{subsubcomando.name} | "
                                    f"tipo={type(subsubcomando).__name__}"
                                )

            print("=" * 60)
            print()

    # ========================================================
    # READY
    # ========================================================

    async def on_ready(self):

        print(
            f"Naikito Bot conectado como {self.user}"
        )

        if self.user is not None:
            print(
                f"ID: {self.user.id}"
            )