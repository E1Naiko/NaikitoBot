"""Comandos administrativos generales: info y ejecución por archivo."""

import re
import shlex
from typing import cast

import discord
from discord import app_commands

from commands.admin.base import solo_admin, solo_servidor
from config import ADMIN_USER_IDS, GUILD_ID


class _FileExecutionResponse:
    """Redirige las respuestas de comandos hacia el followup original."""

    def __init__(self, interaction: discord.Interaction):
        self._interaction = interaction

    def is_done(self) -> bool:
        return True

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
        ruta: list[str],
    ) -> app_commands.Command:
        """Obtiene un comando del grupo admin sin permitir rutas arbitrarias."""

        grupo_admin = self.bot.tree.get_command("admin")

        if not isinstance(grupo_admin, app_commands.Group):
            raise ValueError("El grupo admin no está disponible.")

        if not ruta:
            raise ValueError("Falta el nombre del comando.")

        comando: app_commands.Command | app_commands.Group | None = grupo_admin

        for nombre in ruta:
            if not isinstance(comando, app_commands.Group):
                raise ValueError("La ruta del comando no es válida.")

            comando = comando.get_command(nombre)

            if comando is None:
                raise ValueError(f"Comando admin desconocido: {' '.join(ruta)}")

        if not isinstance(comando, app_commands.Command):
            raise ValueError("La línea debe apuntar a un comando ejecutable.")

        return comando

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

        ruta = [argumentos.pop(0)]

        if ruta[0].lower() in {"ssf", "box"}:
            if not argumentos:
                raise ValueError(
                    f"Falta el subcomando de admin {ruta[0]}."
                )

            ruta.append(argumentos.pop(0))

        comando = self._resolver_comando_admin(ruta)
        nombre = comando.name
        parametros: dict[str, object] = {}

        if ruta[0].lower() == "box":
            subcomando = ruta[1].lower()

            if subcomando in {
                "info",
                "sponsors",
                "curar",
                "cancelar",
                "reset",
            }:
                if len(argumentos) != 1:
                    raise ValueError(
                        f"box {subcomando} requiere un usuario."
                    )

                parametros["usuario"] = await self._resolver_miembro(
                    interaction,
                    argumentos[0],
                )

            elif subcomando in {
                "dar_dinero",
                "dar_exp",
            }:
                if len(argumentos) != 2:
                    raise ValueError(
                        f"box {subcomando} requiere usuario y cantidad."
                    )

                parametros["usuario"] = await self._resolver_miembro(
                    interaction,
                    argumentos[0],
                )

                try:
                    parametros["cantidad"] = int(argumentos[1])
                except ValueError as error:
                    raise ValueError(
                        "La cantidad debe ser un número entero."
                    ) from error

            elif subcomando == "probabilidad":
                if len(argumentos) != 2:
                    raise ValueError(
                        "box probabilidad requiere usuario y porcentaje."
                    )

                parametros["usuario"] = await self._resolver_miembro(
                    interaction,
                    argumentos[0],
                )

                try:
                    parametros["probabilidad"] = float(argumentos[1])
                except ValueError as error:
                    raise ValueError(
                        "La probabilidad debe ser un número."
                    ) from error

            elif subcomando == "dar_sponsor":
                if len(argumentos) != 2:
                    raise ValueError(
                        "box dar_sponsor requiere usuario y tipo."
                    )

                parametros["usuario"] = await self._resolver_miembro(
                    interaction,
                    argumentos[0],
                )

                tipo = argumentos[1].lower()

                tipos_validos = {
                    "redes": "📱 Redes",
                    "radio": "📻 Radio",
                    "equipamiento": "🥊 Equipamiento",
                    "medico": "🚑 Médico",
                }

                if tipo not in tipos_validos:
                    raise ValueError(
                        "Tipo de sponsor inválido. "
                        "Usa: redes, radio, equipamiento o medico."
                    )

                parametros["tipo"] = app_commands.Choice(
                    name=tipos_validos[tipo],
                    value=tipo,
                )

            elif subcomando == "quitar_sponsor":
                if len(argumentos) != 2:
                    raise ValueError(
                        "box quitar_sponsor requiere usuario e ID del sponsor."
                    )

                parametros["usuario"] = await self._resolver_miembro(
                    interaction,
                    argumentos[0],
                )

                try:
                    parametros["sponsor_id"] = int(argumentos[1])
                except ValueError as error:
                    raise ValueError(
                        "El ID del sponsor debe ser un número entero."
                    ) from error

            else:
                raise ValueError(
                    f"Comando admin box desconocido: {subcomando}"
                )

        elif nombre in {"info", "stats", "top", "resettotal"}:
            if nombre == "resettotal":
                if len(argumentos) != 1:
                    raise ValueError("resettotal requiere SI o NO.")

                parametros["confirmar"] = app_commands.Choice(
                    name=argumentos[0].upper(),
                    value=argumentos[0].upper(),
                )
            elif argumentos:
                raise ValueError(f"{nombre} no acepta argumentos.")

        elif nombre in {"manualadd", "resetdia", "resetusuario"}:
            if not argumentos:
                raise ValueError(f"Faltan argumentos para {nombre}.")

            parametros["usuario"] = await self._resolver_miembro(
                interaction,
                argumentos.pop(0),
            )

            if nombre in {"manualadd", "resetdia"}:
                if not argumentos:
                    raise ValueError(f"Falta la fecha para {nombre}.")

                parametros["fecha"] = argumentos.pop(0)

            if nombre == "manualadd":
                if not argumentos:
                    raise ValueError("Falta la hora para manualadd.")

                parametros["hora"] = argumentos.pop(0)

            if argumentos:
                raise ValueError(f"Sobran argumentos para {nombre}.")

        elif nombre == "revivir":
            if len(argumentos) != 2:
                raise ValueError("revivir requiere miembro y fecha.")

            parametros["usuario"] = await self._resolver_miembro(
                interaction,
                argumentos[0],
            )
            parametros["fecha"] = argumentos[1]

        elif nombre == "iniciar":
            if len(argumentos) != 1 or interaction.guild is None:
                raise ValueError("iniciar requiere el ID de un canal.")

            canal_id = argumentos[0].strip("<#>")

            if not canal_id.isdigit():
                raise ValueError(f"Canal inválido: {argumentos[0]}")

            canal = interaction.guild.get_channel(int(canal_id))

            if not isinstance(canal, discord.TextChannel):
                raise ValueError(f"No se encontró el canal de texto: {argumentos[0]}")

            parametros["canal"] = canal

        else:
            raise ValueError(f"Comando no permitido: {' '.join(ruta)}")

        await comando._do_call(
            cast(
                discord.Interaction,
                _FileExecutionInteraction(interaction),
            ),
            parametros,
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
            await interaction.response.send_message(
                "⚠️ El archivo debe tener extensión `.txt`.",
                ephemeral=True,
            )
            return

        if archivo.size > 1024 * 1024:
            await interaction.response.send_message(
                "⚠️ El archivo no puede superar 1 MiB.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        contenido = (await archivo.read()).decode("utf-8-sig")
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
            except (ValueError, discord.DiscordException) as error:
                resultados.append(f"❌ Línea {numero}: {error}")
            else:
                resultados.append(f"✅ Línea {numero}: ejecutada")

        await interaction.followup.send(
            "**Ejecución finalizada**\n" + "\n".join(resultados),
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

        if interaction.guild:
            embed.add_field(
                name="📍 Servidor actual",
                value=(
                    f"{interaction.guild.name}\n"
                    f"`{interaction.guild.id}`"
                ),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )
