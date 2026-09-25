"""Comandos administrativos generales: info y ejecución por archivo."""

import re
import shlex
from typing import cast

import discord
from discord import app_commands

from core.mensajes import responder_texto
from commands.admin.base import solo_admin, solo_servidor
from core.utils import ahora
from config import (
    ADMIN_USER_IDS,
    BOX_CHANNEL_IDS,
    BOX_DINERO_POR_MINUTO,
    BOX_EXPERIENCIA_POR_MINUTO,
    GENERAL_CHANNEL_IDS,
    GUILD_ID,
    LAHORA_CANALES_ID,
    MADRUGUE_CHANNEL_IDS,
    SSF_CANALES_ID,
    SSF_FECHA_FIN,
    SSF_FECHA_INICIO,
    TIMEZONE,
)


LIMITE_MENSAJE_DISCORD = 2000
ENCABEZADO_RESULTADOS = "**Ejecución finalizada**"
ENCABEZADO_CONTINUACION = "**Ejecución finalizada (continuación)**"


def _fragmentar_resultados(resultados: list[str]) -> list[str]:
    """Agrupa el informe del archivo en mensajes válidos para Discord."""

    if not resultados:
        return [f"{ENCABEZADO_RESULTADOS}\nNo había comandos para ejecutar."]

    # Una sola línea también puede ser enorme (el archivo admite hasta 1 MiB),
    # así que se recorta antes de agrupar. Se reserva lugar para el encabezado
    # más largo y el salto de línea.
    limite_linea = (
        LIMITE_MENSAJE_DISCORD
        - len(ENCABEZADO_CONTINUACION)
        - 2
    )
    lineas = [
        linea
        if len(linea) <= limite_linea
        else f"{linea[: limite_linea - 1]}…"
        for linea in resultados
    ]

    mensajes: list[str] = []
    actual = ENCABEZADO_RESULTADOS

    for linea in lineas:
        candidato = f"{actual}\n{linea}"

        if len(candidato) <= LIMITE_MENSAJE_DISCORD:
            actual = candidato
            continue

        mensajes.append(actual)
        actual = f"{ENCABEZADO_CONTINUACION}\n{linea}"

    mensajes.append(actual)
    return mensajes


def _texto_faltan_argumentos(nombre_comando: str) -> str:
    """Aviso cuando una línea de un TXT no completa los argumentos obligatorios."""

    mensajes = {
        "revivir": "revivir requiere miembro y fecha.",
        "agregar": "agregar requiere miembro y fecha.",
        "quitar": "quitar requiere miembro y fecha.",
        "eliminar": "eliminar requiere miembro y fecha.",
        "recalcular": "recalcular requiere un miembro.",
        "estado": "estado requiere un miembro.",
        "ver": "ver requiere un miembro.",
        "resetdia": "resetdia requiere usuario y fecha.",
        "manualadd": "manualadd requiere usuario, fecha y hora.",
        "resetusuario": "resetusuario requiere un usuario.",
        "resettotal": "resettotal requiere SI o NO.",
        "cerrar": "cerrar requiere SI o NO.",
        "iniciar": "iniciar requiere el ID de un canal.",
        "dar_dinero": "dar_dinero requiere usuario y cantidad.",
        "dar_exp": "dar_exp requiere usuario y cantidad.",
        "probabilidad": "probabilidad requiere usuario y porcentaje.",
        "dar_sponsor": "dar_sponsor requiere usuario y tipo.",
        "quitar_sponsor": "quitar_sponsor requiere usuario e ID del sponsor.",
    }

    return mensajes.get(
        nombre_comando,
        f"Faltan argumentos para {nombre_comando}.",
    )


class _FileExecutionResponse:
    """Redirige las respuestas de comandos hacia el followup original."""

    def __init__(self, interaction: discord.Interaction):
        self._interaction = interaction

    def is_done(self) -> bool:
        return True

    async def defer(self, **kwargs):
        """No vuelve a diferir: ``fileexecute`` ya confirmó la interacción."""

        return None

    async def send_message(self, *args, **kwargs):
        return await self._interaction.followup.send(*args, **kwargs)


class _FileExecutionInteraction:
    """Proxy de interacción para ejecutar varios comandos en una respuesta."""

    def __init__(self, interaction: discord.Interaction):
        self._interaction = interaction
        self.response = _FileExecutionResponse(interaction)

    def __getattr__(self, name):
        return getattr(self._interaction, name)


class SistemaMixin:
    """Información del bot y ejecución de comandos desde un TXT."""

    async def _resolver_miembro(
        self,
        interaction: discord.Interaction,
        valor: str,
    ) -> discord.Member:
        """Resuelve un miembro desde una mención, un ID o un nombre."""

        if interaction.guild is None:
            raise ValueError("El comando requiere un servidor.")

        valor = valor.strip()
        coincidencia = re.fullmatch(r"<@!?([0-9]+)>|([0-9]+)", valor)

        if coincidencia is not None:
            miembro_id = int(coincidencia.group(1) or coincidencia.group(2))
            miembro = interaction.guild.get_member(miembro_id)

            if miembro is None:
                try:
                    miembro = await interaction.guild.fetch_member(miembro_id)
                except discord.HTTPException as error:
                    raise ValueError(f"No se encontró el miembro: {valor}") from error

            return miembro

        nombre = re.fullmatch(r"<@?([^>]+)>|@(.+)", valor)
        nombre = (nombre.group(1) or nombre.group(2)) if nombre else valor
        nombre = nombre.strip()

        miembros = list(interaction.guild.members)

        if not any(
            any(
                candidato is not None
                and candidato.casefold() == nombre.casefold()
                for candidato in {
                    miembro.name,
                    miembro.display_name,
                    miembro.global_name,
                }
            )
            for miembro in miembros
        ):
            try:
                miembros.extend(
                    await interaction.guild.query_members(
                        query=nombre,
                        limit=100,
                    )
                )
            except discord.DiscordException:
                pass

        for miembro in miembros:
            nombres = {
                miembro.name,
                miembro.display_name,
                miembro.global_name,
            }
            if any(
                candidato is not None
                and candidato.casefold() == nombre.casefold()
                for candidato in nombres
            ):
                return miembro

        raise ValueError(f"No se encontró el miembro: {valor}")

    def _resolver_comando_admin(
        self,
        grupo: str | None,
        nombre_comando: str,
    ) -> app_commands.Command:
        """Obtiene un comando registrado bajo ``/admin`` sin rutas arbitrarias."""

        grupo_admin = self.bot.tree.get_command("admin")

        if not isinstance(grupo_admin, app_commands.Group):
            raise ValueError("El grupo admin no está disponible.")

        grupo_concreto: app_commands.Group | app_commands.Command = grupo_admin

        if grupo is not None:
            subgrupo = grupo_admin.get_command(grupo)

            if not isinstance(subgrupo, app_commands.Group):
                raise ValueError(
                    f"Comando admin desconocido: {grupo} {nombre_comando}"
                )

            grupo_concreto = subgrupo

        comando = grupo_concreto.get_command(nombre_comando)

        if not isinstance(comando, app_commands.Command):
            ruta = f"{grupo} {nombre_comando}".strip()
            raise ValueError(f"Comando admin desconocido: {ruta}")

        return comando

    async def _resolver_canal(
        self,
        interaction: discord.Interaction,
        valor: str,
    ) -> discord.TextChannel:
        """Resuelve un canal de texto desde un ID o una mención ``#``."""

        if interaction.guild is None:
            raise ValueError("El comando requiere un servidor.")

        canal_id = valor.strip("<#>")

        if not canal_id.isdigit():
            raise ValueError(f"Canal inválido: {valor}")

        canal = interaction.guild.get_channel(int(canal_id))

        if not isinstance(canal, discord.TextChannel):
            raise ValueError(f"No se encontró el canal de texto: {valor}")

        return canal

    async def _convertir_argumento(
        self,
        interaction: discord.Interaction,
        parametro,
        valor: str,
    ) -> object:
        """Convierte un argumento de texto al tipo del parámetro del comando."""

        if parametro.choices:
            for opcion in parametro.choices:
                if (
                    str(opcion.value).casefold() == valor.casefold()
                    or str(opcion.name).casefold() == valor.casefold()
                ):
                    return app_commands.Choice(
                        name=opcion.name,
                        value=opcion.value,
                    )

            raise ValueError(
                f"Valor inválido para {parametro.name}: {valor}"
            )

        tipo = parametro.type

        if tipo is discord.AppCommandOptionType.user:
            return await self._resolver_miembro(interaction, valor)

        if tipo is discord.AppCommandOptionType.channel:
            return await self._resolver_canal(interaction, valor)

        if tipo is discord.AppCommandOptionType.integer:
            try:
                return int(valor)
            except ValueError as error:
                raise ValueError(
                    f"{parametro.name} debe ser un número entero."
                ) from error

        if tipo is discord.AppCommandOptionType.number:
            try:
                return float(valor)
            except ValueError as error:
                raise ValueError(
                    f"{parametro.name} debe ser un número."
                ) from error

        return valor

    async def _ejecutar_linea_archivo(
        self,
        interaction: discord.Interaction,
        linea: str,
    ) -> None:
        """Parsea y ejecuta una única línea de comandos admin."""

        try:
            argumentos = shlex.split(linea, comments=True, posix=True)
        except ValueError as error:
            raise ValueError(f"Sintaxis inválida: {error}") from error

        if not argumentos:
            return

        if argumentos[0].startswith("/"):
            argumentos[0] = argumentos[0][1:]

        if argumentos[0].lower() == "admin":
            argumentos.pop(0)

        if not argumentos:
            raise ValueError("Falta el nombre del comando admin.")

        primero = argumentos.pop(0).lower()

        # Por compatibilidad, los comandos de Madrugue pueden escribirse
        # sin el subgrupo: ``stats`` equivale a ``madrugue stats``.
        if primero in {"madrugue", "ssf", "box", "420"}:
            grupo = primero

            if not argumentos:
                raise ValueError(
                    f"Falta el subcomando de admin {grupo}."
                )

            nombre_comando = argumentos.pop(0).lower()

        elif primero in {
            "stats",
            "top",
            "ver",
            "resetdia",
            "resetusuario",
            "resettotal",
            "manualadd",
        }:
            grupo = "madrugue"
            nombre_comando = primero

        elif primero in {"info", "fileexecute", "test"}:
            grupo = None
            nombre_comando = primero

        else:
            raise ValueError(f"Comando admin desconocido: {primero}")

        comando = self._resolver_comando_admin(
            grupo,
            nombre_comando,
        )

        if nombre_comando == "fileexecute":
            raise ValueError("fileexecute no puede ejecutarse desde un archivo.")

        if grupo == "420" and nombre_comando == "importar":
            raise ValueError(
                "420 importar no puede ejecutarse desde un archivo: "
                "usá /admin 420 importar directamente."
            )

        parametros = comando.parameters
        requeridos = [
            parametro
            for parametro in parametros
            if parametro.required
        ]

        if len(argumentos) > len(parametros):
            raise ValueError(
                f"Sobran argumentos para {nombre_comando}."
            )

        if len(argumentos) < len(requeridos):
            raise ValueError(
                _texto_faltan_argumentos(nombre_comando)
            )

        kwargs: dict[str, object] = {}

        for posicion, parametro in enumerate(parametros):
            if posicion >= len(argumentos):
                break

            kwargs[parametro.name] = await self._convertir_argumento(
                interaction,
                parametro,
                argumentos[posicion],
            )

        await comando._do_call(
            cast(
                discord.Interaction,
                _FileExecutionInteraction(interaction),
            ),
            kwargs,
        )

    @app_commands.command(
        name="fileexecute",
        description="Ejecuta comandos admin desde un archivo TXT, línea por línea.",
    )
    @app_commands.describe(
        archivo="Archivo TXT con un comando admin por línea.",
    )
    async def fileexecute(
        self,
        interaction: discord.Interaction,
        archivo: discord.Attachment,
    ):
        """Ejecuta únicamente comandos del grupo admin desde un TXT."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        if not archivo.filename.lower().endswith(".txt"):
            await responder_texto(interaction, "⚠️ El archivo debe tener extensión `.txt`.",
                ephemeral=True,
            )
            return

        if archivo.size > 1024 * 1024:
            await responder_texto(interaction, "⚠️ El archivo no puede superar 1 MiB.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            datos = await archivo.read()
        except discord.HTTPException as error:
            await responder_texto(
                interaction,
                "❌ No pude descargar el archivo adjunto. "
                "Volvé a subirlo e intentá nuevamente.\n\n"
                f"Detalle: `{error}`",
                color_area="error",
                ephemeral=True,
            )
            return

        try:
            contenido = datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            await responder_texto(
                interaction,
                "❌ No pude leer el archivo. Guardalo como texto UTF-8 "
                "y volvé a intentarlo.",
                color_area="error",
                ephemeral=True,
            )
            return

        lineas = [linea.strip() for linea in contenido.splitlines()]
        lineas = [linea for linea in lineas if linea and not linea.startswith("#")]

        if len(lineas) > 50:
            await interaction.followup.send(
                "⚠️ El archivo no puede contener más de 50 comandos.",
                ephemeral=True,
            )
            return

        resultados = []

        for numero, linea in enumerate(lineas, start=1):
            try:
                await self._ejecutar_linea_archivo(interaction, linea)
            except Exception as error:
                # Cada línea es independiente: un error inesperado de un
                # comando no debe abortar las líneas restantes ni dejar el
                # defer sin una respuesta final.
                causa = getattr(error, "original", error)
                detalle = str(causa) or type(causa).__name__
                resultados.append(f"❌ Línea {numero}: {detalle}")
                print(
                    "[ADMIN FILEEXECUTE] "
                    f"línea={numero} error={type(causa).__name__}: {detalle}",
                    flush=True,
                )
            else:
                resultados.append(f"✅ Línea {numero}: ejecutada")

        for mensaje in _fragmentar_resultados(resultados):
            await interaction.followup.send(
                mensaje,
                ephemeral=True,
            )

    # ========================================================
    # INFO
    # ========================================================

    @app_commands.command(
        name="info",
        description="Muestra información de configuración del bot.",
    )
    async def info(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra información administrativa."""

        if not await solo_admin(interaction):
            return

        def canales_texto(ids: set[int]) -> str:
            if not ids:
                return "No configurado"

            return ", ".join(
                f"`{canal_id}`"
                for canal_id in sorted(ids)
            )

        embed = discord.Embed(
            title="⚙️ Información de Naikito Bot",
            description="Configuración administrativa.",
        )

        embed.add_field(
            name="👤 Administradores",
            value=str(len(ADMIN_USER_IDS)),
            inline=True,
        )

        embed.add_field(
            name="🏠 Servidor configurado",
            value=(
                str(GUILD_ID)
                if GUILD_ID
                else "No configurado"
            ),
            inline=True,
        )

        embed.add_field(
            name="🗓️ SSF",
            value=(
                f"Inicio: `{SSF_FECHA_INICIO}`\n"
                f"Fin: `{SSF_FECHA_FIN}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="🥊 Box",
            value=(
                f"EXP/min: **{BOX_EXPERIENCIA_POR_MINUTO}**\n"
                f"Dinero/min: **{BOX_DINERO_POR_MINUTO}$**"
            ),
            inline=True,
        )

        embed.add_field(
            name="📡 Canales generales",
            value=canales_texto(GENERAL_CHANNEL_IDS),
            inline=False,
        )

        embed.add_field(
            name="🌅 Canales de Madrugue",
            value=canales_texto(MADRUGUE_CHANNEL_IDS),
            inline=True,
        )

        embed.add_field(
            name="🌿 Canales 420",
            value=canales_texto(LAHORA_CANALES_ID),
            inline=True,
        )

        embed.add_field(
            name="🥊 Canales de Box",
            value=canales_texto(BOX_CHANNEL_IDS),
            inline=True,
        )

        embed.add_field(
            name="🫡 Canales de SeptSinFP",
            value=canales_texto(SSF_CANALES_ID),
            inline=False,
        )

        if interaction.guild:
            embed.add_field(
                name="📍 Servidor actual",
                value=(
                    f"{interaction.guild.name}\n"
                    f"`{interaction.guild.id}`"
                ),
                inline=False,
            )

        embed.set_footer(
            text=(
                f"🕐 {TIMEZONE} — "
                f"{ahora().strftime('%Y-%m-%d %H:%M')}"
            )
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )
