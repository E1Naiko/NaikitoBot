import asyncio
from datetime import datetime

import discord

from discord import app_commands
from discord.ext import commands

from config import (
    BOX_CHANNEL_IDS,
    BOX_COMBATE_ACTIVO,
    GENERAL_CHANNEL_IDS,
    GUILD_ID,
    LAHORA_CANALES_ID,
    MADRUGUE_CHANNEL_IDS,
    PREFIX,
    SSF_CANALES_ID,
)

from core.discord_http import espera_restante
from core.lahora_sync import sincronizar_lahora
from core.mensajes import responder
from core.permissions import es_admin
from core.temporada import inicio_temporada, verificar_temporada
from core.version import version_bot
from modules.madrugue.database import (
    inicializar_db as inicializar_db_madrugue,
)

from modules.sanciones.database import (
    inicializar_db as inicializar_db_sanciones,
)

from modules.ssf.database import (
    inicializar_db as inicializar_db_ssf,
)

# Área, extensión, cog, comando raíz y canales habilitados (None para admin).
_SISTEMAS = (
    ("General", "commands.general", "General", "ping", GENERAL_CHANNEL_IDS),
    ("Madrugue", "commands.madrugue", "Madrugue", "madrugue", MADRUGUE_CHANNEL_IDS),
    ("420", "commands.lahora", "LaHora", "420_stats", LAHORA_CANALES_ID),
    ("Administración", "commands.admin", "Admin", "admin", None),
    ("SeptSinFP", "commands.ssf", "Ssf", "ssf", SSF_CANALES_ID),
    ("Box", "commands.box", "Box", "box", BOX_CHANNEL_IDS),
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

        if es_admin(interaction.user.id):
            # Los administradores no tienen la restricción de canal.
            permitido = True
            zona = "administración"
            canales = set()
        elif command_name == "admin":
            # El chequeo de administrador se hace de nuevo en cada comando
            # /admin (solo_admin); acá solo se evita bloquearlos por canal.
            permitido = True
            zona = "administración"
            canales = set()
        elif command_name == "box":
            permitido = channel_id in BOX_CHANNEL_IDS
            zona = "Box"
            canales = BOX_CHANNEL_IDS
        elif channel_id in GENERAL_CHANNEL_IDS:
            permitido = command_name == "ping"
            zona = "generales"
            canales = GENERAL_CHANNEL_IDS
        elif channel_id in MADRUGUE_CHANNEL_IDS:
            permitido = bool(command_name and command_name.startswith("madrugue"))
            zona = "Madrugue"
            canales = MADRUGUE_CHANNEL_IDS
        elif channel_id in LAHORA_CANALES_ID:
            permitido = bool(command_name and command_name.startswith("420"))
            zona = "420"
            canales = LAHORA_CANALES_ID
        elif channel_id in SSF_CANALES_ID:
            permitido = command_name == "ssf"
            zona = "SeptSinFP"
            canales = SSF_CANALES_ID
        else:
            permitido = False
            zona = "ningún comando"
            canales = (
                BOX_CHANNEL_IDS
                | GENERAL_CHANNEL_IDS
                | MADRUGUE_CHANNEL_IDS
                | LAHORA_CANALES_ID
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
            f"Este canal solo permite comandos de **{zona}**."
            if canales_texto
            else "Este canal no tiene comandos configurados."
        )
        await responder(
            interaction,
            "⚠️ Canal no habilitado",
            mensaje,
            color_area="aviso",
            ephemeral=True,
        )
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
        # Permite distinguir fallos anteriores al setup de errores que podrían
        # dejar tareas o cambios de estado ya iniciados.
        self.setup_iniciado = False
        self._base_inicializada = False
        self._sincronizacion_comandos = None
        self._tarea_temporada = None

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
        """Carga módulos y sincroniza comandos sin volcar el árbol completo."""

        self.setup_iniciado = True
        try:
            await inicializar_db_madrugue()
            await inicializar_db_sanciones()
            await inicializar_db_ssf()
        except Exception as error:
            print(f"[INICIO] Error al inicializar SQLite: {type(error).__name__}", flush=True)
            raise
        self._base_inicializada = True

        for nombre, extension, _cog, _comando, _canales in _SISTEMAS:
            try:
                await self.load_extension(extension)
            except Exception as error:
                print(f"[INICIO] Error al cargar {nombre}: {type(error).__name__}", flush=True)
                raise

        try:
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                # Reemplaza firmas antiguas sin borrar el árbol local.
                self.tree.clear_commands(guild=guild)
                self.tree.copy_global_to(guild=guild)
                comandos = await self.tree.sync(guild=guild)
                alcance = f"servidor {GUILD_ID}"
            else:
                comandos = await self.tree.sync()
                alcance = "global"
        except Exception as error:
            print(
                f"[INICIO] Error al sincronizar comandos: {type(error).__name__}",
                flush=True,
            )
            raise
        self._sincronizacion_comandos = (alcance, len(comandos))
        self._tarea_temporada = asyncio.create_task(self._vigilar_temporada())

    async def _vigilar_temporada(self):
        """Aplica el corte incluso si el bot permanece encendido sin actividad."""
        while True:
            actual = datetime.now(inicio_temporada().tzinfo)
            inicio = inicio_temporada(actual)
            siguiente = datetime(inicio.year + 1, 10, 3, tzinfo=inicio.tzinfo)
            demora = siguiente.timestamp() - actual.timestamp()
            await asyncio.sleep(max(0, demora))
            while True:
                try:
                    await asyncio.to_thread(verificar_temporada)
                    break
                except Exception as error:
                    print(f"[TEMPORADA] Error al reiniciar: {error}; reintento en 60 s.", flush=True)
                    await asyncio.sleep(60)

    async def close(self):
        if self._tarea_temporada is not None:
            self._tarea_temporada.cancel()
            await asyncio.gather(self._tarea_temporada, return_exceptions=True)
            self._tarea_temporada = None
        await super().close()

    def _estado_sistema(self, extension, nombre_cog, comando, canales):
        """Describe lo comprobado localmente, sin afirmar que pasó pruebas."""
        if extension not in self.extensions or self.get_cog(nombre_cog) is None:
            return "no cargado"
        if self.tree.get_command(comando) is None:
            return "sin comando principal"
        if canales is not None and not canales:
            return "cargado; sin canales configurados"
        return "cargado"

    @staticmethod
    def _estado_tarea(cog, nombre, *, habilitada=True):
        """Estado actual del loop; no implica que haya completado su trabajo."""
        tarea = getattr(cog, nombre, None) if cog is not None else None
        if tarea is None:
            return "no disponible"
        if tarea.is_running() and not tarea.is_being_cancelled():
            return "activa"
        return "detenida" if habilitada else "desactivada por configuración"

    def _imprimir_resumen_inicio(self):
        """Muestra versión, carga local y servidores, sin enumerar comandos."""
        print(f"\n=== {version_bot()} ===", flush=True)
        print(f"Conectado como: {self.user or 'desconocido'}", flush=True)
        print(
            f"Base de datos: {'inicializada' if self._base_inicializada else 'no inicializada'}",
            flush=True,
        )
        print("Funciones (estado de carga local):", flush=True)
        for nombre, extension, cog, comando, canales in _SISTEMAS:
            estado = self._estado_sistema(extension, cog, comando, canales)
            print(f"  {nombre}: {estado}", flush=True)

        box = self.get_cog("Box")
        ssf = self.get_cog("Ssf")
        lahora = self.get_cog("LaHora")
        print(
            "Tareas: "
            f"Box acciones={self._estado_tarea(box, 'comprobar_acciones')}, "
            f"lesiones={self._estado_tarea(box, 'reducir_probabilidad_lesion')}, "
            f"narración={self._estado_tarea(box, 'narrar_combates', habilitada=BOX_COMBATE_ACTIVO)}; "
            f"SSF revisión={self._estado_tarea(ssf, 'procesar_ssf_automatico')}; "
            f"420 ventanas={self._estado_tarea(lahora, 'resumir_ventanas')}",
            flush=True,
        )

        if self._sincronizacion_comandos is None:
            print("Comandos en Discord: sincronización no confirmada", flush=True)
        else:
            alcance, cantidad = self._sincronizacion_comandos
            print(f"Comandos en Discord: sincronizados ({alcance}, {cantidad} de primer nivel)", flush=True)

        servidores = sorted(self.guilds, key=lambda guild: (guild.name.casefold(), guild.id))
        print(f"Servidores conectados: {len(servidores)}", flush=True)
        for guild in servidores:
            print(f"  - {guild.name} (ID: {guild.id})", flush=True)

    async def on_ready(self):
        self._imprimir_resumen_inicio()

        # Al reconectar se recuperan los 420 pendientes en una tarea aparte.
        asyncio.create_task(self._sincronizar_lahora_al_conectar())

    async def _sincronizar_lahora_al_conectar(self) -> None:
        """Recupera los \"420\" perdidos mientras el bot estaba offline."""

        if espera_restante() > 0:
            print(
                "[420] sincronización omitida: pausa HTTP vigente; "
                "se puede recuperar con /admin 420 sincronizar al terminar",
                flush=True,
            )
            return

        try:
            resultados = await sincronizar_lahora(self)
        except Exception as error:
            print(
                "[420] sincronización automática falló "
                f"({type(error).__name__}): {error}",
                flush=True,
            )
            return

        if not resultados:
            return

        for resultado in resultados:
            if resultado.error:
                print(
                    f"[420] sincronización canal={resultado.canal_id} "
                    f"guild={resultado.guild_id} error={resultado.error}",
                    flush=True,
                )
                continue

            resumen = resultado.resumen

            if resumen is not None and (resumen.importados or resumen.revisados):
                print(
                    f"[420] sincronización canal={resultado.canal_id} "
                    f"guild={resultado.guild_id} "
                    f"revisados={resumen.revisados} "
                    f"importados={resumen.importados}",
                    flush=True,
                )
