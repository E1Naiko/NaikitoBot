"""Administración de Madrugue: ranking, registros y reseteos."""

from datetime import date, datetime
import csv
import io

import discord
from discord import app_commands
from sqlalchemy import select

from core.mensajes import responder, responder_texto
from core.database import crear_sesion
from commands.admin.base import solo_admin, solo_servidor
from config import MADRUGUE_PUNTOS_100, MADRUGUE_PUNTOS_25
from core.utils import ahora
from modules.madrugue.models import RegistroMadrugue
from modules.madrugue.services import (
    calcular_multiplicador_horario,
    calcular_racha_para_nuevo_registro,
    eliminar_registro_del_dia,
    eliminar_registros_servidor,
    eliminar_registros_usuario,
    guardar_registro,
    obtener_estadisticas_servidor,
    obtener_fechas_registradas,
    obtener_puntos_base,
    obtener_registro_del_dia,
    obtener_registro_del_dia_admin,
    obtener_resumen_usuario,
    obtener_stats_madrugue,
    obtener_top_madrugadores,
    obtener_ultimos_registros,
    texto_horario_valido,
)


class MadrugueAdminMixin:
    """Comandos administrativos de Madrugue bajo ``/admin madrugue``."""

    madrugue = app_commands.Group(
        name="madrugue",
        description="Administración de Madrugue.",
    )

    # ========================================================
    # STATS
    # ========================================================

    @madrugue.command(
        name="stats",
        description="Muestra las estadísticas de Madrugue del servidor.",
    )
    async def madrugue_stats(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra estadísticas generales."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        madrugadores, registros, puntos = (
            await obtener_estadisticas_servidor(
                interaction.guild.id
            )
        )

        embed = discord.Embed(
            title="📊 Estadísticas de Madrugue",
            description=(
                f"Estadísticas generales de "
                f"**{interaction.guild.name}**."
            ),
        )

        embed.add_field(
            name="👥 Madrugadores",
            value=f"**{madrugadores}**",
            inline=True,
        )

        embed.add_field(
            name="🌅 Registros",
            value=f"**{registros}**",
            inline=True,
        )

        embed.add_field(
            name="🏆 Puntos acumulados",
            value=f"**{puntos:.1f}**",
            inline=True,
        )

        embed.set_footer(
            text=f"Servidor: {interaction.guild.name}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # ========================================================
    # TOP
    # ========================================================

    @madrugue.command(
        name="top",
        description="Muestra el TOP de Madrugue del servidor.",
    )
    async def madrugue_top(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el ranking histórico."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resultados = await obtener_top_madrugadores(
            interaction.guild.id,
            limite=10,
        )

        if not resultados:
            await responder_texto(interaction, "🏆 Todavía no hay madrugadores registrados.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🏆 TOP Madrugadores",
            description=(
                f"Ranking histórico de **{interaction.guild.name}**."
            ),
        )

        medallas = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        lineas = []

        for posicion, (
            user_id,
            username,
            puntos,
        ) in enumerate(resultados, start=1):

            medalla = medallas.get(
                posicion,
                f"**{posicion}.**",
            )

            lineas.append(
                f"{medalla} **{username}** — "
                f"**{puntos:.1f} puntos**"
            )

        embed.add_field(
            name="Ranking",
            value="\n".join(lineas),
            inline=False,
        )

        embed.set_footer(
            text=f"Servidor: {interaction.guild.name}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # ========================================================
    # RESET DÍA
    # ========================================================

    @madrugue.command(
        name="resetdia",
        description="Elimina el registro de Madrugue de un usuario para una fecha.",
    )
    @app_commands.describe(
        usuario="Usuario cuyo registro quieres eliminar.",
        fecha="Fecha del registro en formato YYYY-MM-DD.",
    )
    async def madrugue_resetdia(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Elimina un registro diario."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await responder_texto(interaction, "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-08-31`.",
                ephemeral=True,
            )
            return

        registro = await obtener_registro_del_dia_admin(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if registro is None:
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** no tiene "
                f"un registro el **{fecha}**.",
                ephemeral=True,
            )
            return

        hora, puntos = registro

        eliminado = await eliminar_registro_del_dia(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if eliminado == 0:
            await responder_texto(interaction, "⚠️ No se pudo eliminar el registro.",
                ephemeral=True,
            )
            return

        await responder_texto(interaction, f"🗑️ Registro eliminado correctamente.\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Fecha: **{fecha}**\n"
            f"⏰ Hora registrada: **{hora}**\n"
            f"🏆 Puntos eliminados: **{puntos:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # RESET USUARIO
    # ========================================================

    @madrugue.command(
        name="resetusuario",
        description="Elimina todos los registros de Madrugue de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyos registros quieres eliminar.",
    )
    async def madrugue_resetusuario(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Elimina todos los registros de un usuario."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resumen = await obtener_resumen_usuario(
            interaction.guild.id,
            usuario.id,
        )

        cantidad_registros = resumen[0]
        puntos_totales = resumen[1]

        if cantidad_registros == 0:
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** no tiene "
                "registros en este servidor.",
                ephemeral=True,
            )
            return

        eliminado = await eliminar_registros_usuario(
            interaction.guild.id,
            usuario.id,
        )

        if eliminado == 0:
            await responder_texto(interaction, "⚠️ No se pudo eliminar ningún registro.",
                ephemeral=True,
            )
            return

        await responder_texto(interaction, f"🗑️ Registros eliminados correctamente.\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📋 Registros eliminados: **{eliminado}**\n"
            f"🏆 Puntos eliminados: **{puntos_totales:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # RESET TOTAL
    # ========================================================

    @madrugue.command(
        name="resettotal",
        description="Elimina todos los registros de Madrugue del servidor.",
    )
    @app_commands.describe(
        confirmar="Confirma el borrado total.",
    )
    @app_commands.choices(
        confirmar=[
            app_commands.Choice(name="SI", value="SI"),
            app_commands.Choice(name="NO", value="NO"),
        ]
    )
    async def madrugue_resettotal(
        self,
        interaction: discord.Interaction,
        confirmar: app_commands.Choice[str],
    ):
        """Elimina todos los registros del servidor."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        if confirmar.value != "SI":
            await responder_texto(interaction, "🛑 Operación cancelada. "
                "No se eliminó ningún registro.",
                ephemeral=True,
            )
            return

        madrugadores, registros, puntos = (
            await obtener_estadisticas_servidor(
                interaction.guild.id
            )
        )

        if registros == 0:
            await responder_texto(interaction, "ℹ️ No hay registros de Madrugue para eliminar en este servidor.",
                ephemeral=True,
            )
            return

        eliminado = await eliminar_registros_servidor(
            interaction.guild.id
        )

        await responder_texto(interaction, f"🗑️ **Borrado total completado.**\n\n"
            f"🏠 Servidor: **{interaction.guild.name}**\n"
            f"👥 Madrugadores afectados: **{madrugadores}**\n"
            f"📋 Registros eliminados: **{eliminado}**\n"
            f"🏆 Puntos eliminados: **{puntos:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # MANUAL ADD
    # ========================================================

    @app_commands.command(
        name="stats",
        description="Muestra las estadísticas de Madrugue del servidor (alias de madrugue stats).",
    )
    async def stats(
        self,
        interaction: discord.Interaction,
    ):
        """Alias directo de /admin madrugue stats."""
        await self.madrugue_stats.callback(self, interaction)

    @app_commands.command(
        name="top",
        description="Muestra el TOP de Madrugue del servidor (alias de madrugue top).",
    )
    async def top(
        self,
        interaction: discord.Interaction,
    ):
        """Alias directo de /admin madrugue top."""
        await self.madrugue_top.callback(self, interaction)

    @app_commands.command(
        name="ver",
        description="Muestra el detalle de Madrugue de un usuario (alias de madrugue ver).",
    )
    @app_commands.describe(
        usuario="Usuario cuyos registros quieres consultar.",
    )
    async def ver(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Alias directo de /admin madrugue ver."""
        await self.madrugue_ver.callback(self, interaction, usuario)

    @app_commands.command(
        name="resetdia",
        description="Elimina el registro de Madrugue de un usuario para una fecha (alias de madrugue resetdia).",
    )
    @app_commands.describe(
        usuario="Usuario cuyo registro quieres eliminar.",
        fecha="Fecha del registro en formato YYYY-MM-DD.",
    )
    async def resetdia(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Alias directo de /admin madrugue resetdia."""
        await self.madrugue_resetdia.callback(self, interaction, usuario, fecha)

    @app_commands.command(
        name="resetusuario",
        description="Elimina todos los registros de Madrugue de un usuario (alias de madrugue resetusuario).",
    )
    @app_commands.describe(
        usuario="Usuario cuyos registros quieres eliminar.",
    )
    async def resetusuario(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Alias directo de /admin madrugue resetusuario."""
        await self.madrugue_resetusuario.callback(self, interaction, usuario)

    @app_commands.command(
        name="resettotal",
        description="Elimina todos los registros de Madrugue del servidor (alias de madrugue resettotal).",
    )
    @app_commands.describe(
        confirmar="Confirma el borrado total.",
    )
    @app_commands.choices(
        confirmar=[
            app_commands.Choice(name="SI", value="SI"),
            app_commands.Choice(name="NO", value="NO"),
        ]
    )
    async def resettotal(
        self,
        interaction: discord.Interaction,
        confirmar: app_commands.Choice[str],
    ):
        """Alias directo de /admin madrugue resettotal."""
        await self.madrugue_resettotal.callback(self, interaction, confirmar)

    @app_commands.command(
        name="manualadd",
        description="Agrega manualmente la madrugada de un usuario (alias de madrugue manualadd).",
    )
    @app_commands.describe(
        usuario="Usuario al que se le agregará el registro.",
        fecha="Fecha del registro en formato YYYY-MM-DD.",
        hora="Hora de la madrugada en formato HH:MM.",
    )
    async def manualadd(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
        hora: str,
    ):
        """Alias directo de /admin madrugue manualadd."""
        await self.madrugue_manualadd.callback(
            self,
            interaction,
            usuario,
            fecha,
            hora,
        )

    @madrugue.command(
        name="manualadd",
        description="Agrega manualmente la madrugada de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario al que se le agregará el registro.",
        fecha="Fecha del registro en formato YYYY-MM-DD.",
        hora="Hora de la madrugada en formato HH:MM.",
    )
    async def madrugue_manualadd(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
        hora: str,
    ):
        """Agrega manualmente una madrugada."""

        # ----------------------------------------------------
        # VERIFICAR PERMISOS
        # ----------------------------------------------------

        if not await solo_admin(interaction):
            return

        # ----------------------------------------------------
        # VERIFICAR SERVIDOR
        # ----------------------------------------------------

        if not await solo_servidor(interaction):
            return

        # Este comando consulta la base varias veces antes de guardar. Se
        # confirma la interacción antes de esas operaciones para no perder la
        # ventana inicial de 3 segundos de Discord. Cuando ``manualadd`` se
        # ejecuta desde ``fileexecute`` la interacción proxy ya está diferida,
        # por eso no se intenta responder una segunda vez.
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # ----------------------------------------------------
        # VALIDAR FECHA
        # ----------------------------------------------------

        try:
            fecha_obj = datetime.strptime(
                fecha,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            await responder_texto(interaction, "❌ Fecha inválida.\n"
                "Usá el formato **YYYY-MM-DD**.\n\n"
                "Ejemplo: `2026-07-01`",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # RECHAZAR FECHAS FUTURAS
        # ----------------------------------------------------

        fecha_actual = ahora().date()

        if fecha_obj > fecha_actual:
            await responder_texto(interaction, "❌ No podés registrar una fecha futura.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # VALIDAR HORA
        # ----------------------------------------------------

        try:
            hora_obj = datetime.strptime(
                hora,
                "%H:%M",
            ).time()

        except ValueError:
            await responder_texto(interaction, "❌ Hora inválida.\n"
                "Usá el formato **HH:MM**.\n\n"
                "Ejemplo: `05:45`",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # COMPROBAR REGISTRO EXISTENTE
        # ----------------------------------------------------

        try:
            registro_existente = await obtener_registro_del_dia(
                interaction.guild.id,
                usuario.id,
                fecha_obj,
            )
        except Exception as e:
            await responder_texto(interaction, f"❌ Error al consultar registros existentes.\n\n"
                f"Detalle: `{str(e)}`",
                ephemeral=True,
            )
            return

        if registro_existente:
            hora_anterior, puntos = registro_existente

            await responder_texto(interaction, "⚠️ **EL USUARIO YA TIENE REGISTRO EN ESA FECHA**\n\n"
                f"👤 Usuario: **{usuario.display_name}**\n"
                f"📅 Fecha: **{fecha_obj.isoformat()}**\n"
                f"⏰ Hora registrada: **{hora_anterior}**\n"
                f"🏆 Puntos: **{puntos:.1f}**\n\n"
                "Si querés modificarlo, primero eliminá "
                "el registro del día.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # CALCULAR PUNTOS BASE
        # ----------------------------------------------------

        puntos_base = obtener_puntos_base(
            hora_obj
        )

        if puntos_base == 0:
            await responder_texto(interaction, "❌ La hora indicada está fuera "
                "del horario válido.\n\n"
                "El horario permitido es "
                f"**{texto_horario_valido()}**.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # CALCULAR RACHA
        # ----------------------------------------------------

        try:
            fechas_registradas = await obtener_fechas_registradas(
                interaction.guild.id,
                usuario.id,
            )

            racha = calcular_racha_para_nuevo_registro(
                fechas_registradas,
                fecha_obj,
            )
        except Exception as e:
            await responder_texto(interaction, f"❌ Error al calcular la racha.\n\n"
                f"Detalle: `{str(e)}`",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # CALCULAR MULTIPLICADOR
        # ----------------------------------------------------

        multiplicador = calcular_multiplicador_horario(
            hora_obj
        )

        puntos_finales = (
            puntos_base * multiplicador
        )

        # ----------------------------------------------------
        # GUARDAR REGISTRO
        # ----------------------------------------------------

        try:
            await guardar_registro(
                guild_id=interaction.guild.id,
                user_id=usuario.id,
                username=usuario.display_name,
                fecha=fecha_obj,
                hora=hora_obj.strftime("%H:%M"),
                puntos_base=puntos_base,
                multiplicador=multiplicador,
                puntos_finales=puntos_finales,
            )
        except Exception as e:
            await responder_texto(interaction, f"❌ Error al guardar el registro.\n\n"
                f"Detalle: `{str(e)}`",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # EMOJI
        # ----------------------------------------------------

        if puntos_base == MADRUGUE_PUNTOS_100:
            emoji = "🥇"
        elif puntos_base == MADRUGUE_PUNTOS_25:
            emoji = "🥈"
        else:
            emoji = "🥉"

        # ----------------------------------------------------
        # CONFIRMACIÓN
        # ----------------------------------------------------

        await responder_texto(interaction, "🔧 **REGISTRO MANUAL AGREGADO**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🆔 ID: `{usuario.id}`\n"
            f"📅 Fecha: **{fecha_obj.isoformat()}**\n"
            f"⏰ Hora registrada: "
            f"**{hora_obj.strftime('%H:%M')}**\n\n"
            f"{emoji} Puntos base: **{puntos_base}**\n"
            f"🔥 Racha: **{racha} días**\n"
            f"⭐ Multiplicador: "
            f"**×{multiplicador:.3f}**\n"
            f"🏆 Puntos obtenidos: "
            f"**{puntos_finales:.3f}**",
            ephemeral=True,
        )

    # ========================================================
    # IMPORTAR HISTÓRICO
    # ========================================================

    @madrugue.command(
        name="importar",
        description="Importa registros históricos desde un CSV.",
    )
    @app_commands.describe(
        archivo="CSV UTF-8 con user_id, username, fecha, hora y puntos históricos.",
    )
    async def madrugue_importar(
        self,
        interaction: discord.Interaction,
        archivo: discord.Attachment,
    ):
        """Importa registros de Madrugue sin recalcular sus valores históricos."""

        if not await solo_admin(interaction) or not await solo_servidor(interaction):
            return
        if not archivo.filename.lower().endswith(".csv"):
            await responder_texto(interaction, "❌ El archivo debe tener extensión `.csv`.", ephemeral=True)
            return
        if archivo.size > 1024 * 1024:
            await responder_texto(interaction, "❌ El CSV no puede superar 1 MiB.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            texto = (await archivo.read()).decode("utf-8-sig")
            lector = csv.DictReader(io.StringIO(texto))
            requeridas = {"user_id", "username", "fecha", "hora", "puntos_base", "multiplicador", "puntos_finales"}
            if not lector.fieldnames or not requeridas.issubset(lector.fieldnames):
                raise ValueError("faltan columnas obligatorias en el CSV")
            filas = []
            claves = set()
            for numero, fila in enumerate(lector, start=2):
                try:
                    registro = (
                        int(fila["user_id"]), fila["username"].strip(),
                        date.fromisoformat(fila["fecha"]), fila["hora"],
                        int(fila["puntos_base"]), float(fila["multiplicador"]),
                        float(fila["puntos_finales"]),
                    )
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"línea {numero}: datos inválidos ({error})") from error
                if not registro[1] or len(registro[3]) != 5:
                    raise ValueError(f"línea {numero}: username u hora inválidos")
                clave = (registro[0], registro[2])
                if clave in claves:
                    raise ValueError(f"línea {numero}: usuario y fecha repetidos en el archivo")
                claves.add(clave)
                filas.append(registro)
            if len(filas) > 500:
                raise ValueError("el archivo no puede contener más de 500 registros")

            nuevos = repetidos = 0
            async with crear_sesion() as sesion:
                for user_id, username, fecha, hora, base, multiplicador, puntos in filas:
                    existente = (await sesion.execute(select(RegistroMadrugue).where(
                        RegistroMadrugue.guild_id == interaction.guild.id,
                        RegistroMadrugue.user_id == user_id,
                        RegistroMadrugue.fecha == fecha,
                    ))).scalar_one_or_none()
                    if existente:
                        valores = (existente.username, existente.hora, existente.puntos_base, existente.multiplicador, existente.puntos_finales)
                        esperados = (username, hora, base, multiplicador, puntos)
                        if valores != esperados:
                            raise ValueError(f"conflicto con el registro existente de {user_id} del {fecha}")
                        repetidos += 1
                        continue
                    sesion.add(RegistroMadrugue(
                        guild_id=interaction.guild.id, user_id=user_id, username=username,
                        fecha=fecha, hora=hora, puntos_base=base,
                        multiplicador=multiplicador, puntos_finales=puntos,
                    ))
                    nuevos += 1
                await sesion.commit()
        except (UnicodeDecodeError, ValueError) as error:
            await responder_texto(interaction, f"❌ No se importó nada: {error}", ephemeral=True)
            return
        except Exception as error:
            await responder_texto(interaction, f"❌ Error al importar; no se aplicaron los cambios: {error}", ephemeral=True)
            return

        await responder_texto(interaction, f"✅ Importación completada. Nuevos: **{nuevos}** · Ya existentes: **{repetidos}**.", ephemeral=True)

    # ========================================================
    # VER
    # ========================================================

    @madrugue.command(
        name="ver",
        description="Muestra el detalle de Madrugue de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyos registros quieres consultar.",
    )
    async def madrugue_ver(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Muestra el resumen y los últimos registros de un usuario."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resumen = await obtener_resumen_usuario(
            interaction.guild.id,
            usuario.id,
        )

        if resumen is None or resumen[0] == 0:
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** no tiene "
                "registros de Madrugue en este servidor.",
                ephemeral=True,
            )
            return

        cantidad, puntos, primera, ultima = resumen

        stats = await obtener_stats_madrugue(
            interaction.guild.id,
            usuario.id,
        )

        registros = await obtener_ultimos_registros(
            interaction.guild.id,
            usuario.id,
            limite=8,
        )

        lineas = []

        for fecha, hora, puntos_registro in registros:
            lineas.append(
                f"• **{fecha}** — `{hora}` — "
                f"**{puntos_registro:.1f} pts**"
            )

        await responder(
            interaction,
            f"🌅 Madrugue — {usuario.display_name}",
            color_area="madrugue",
            ephemeral=True,
            secciones_=[
                ("📋 Registros", f"**{cantidad}** en total"),
                ("🏆 Puntos acumulados", f"**{puntos:.1f}**"),
                ("🔥 Mejor racha", f"**{stats['mejor_racha']} días**"),
                ("🗓️ Período", f"`{primera}` → `{ultima}`"),
                ("🕘 Últimos registros", "\n".join(lineas), False),
            ],
        )
