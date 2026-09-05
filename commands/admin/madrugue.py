"""Administración de Madrugue: ranking, registros y reseteos."""

from datetime import date, datetime

import discord
from discord import app_commands

from commands.admin.base import solo_admin, solo_servidor
from core.utils import ahora
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
    obtener_top_madrugadores,
)


class MadrugueAdminMixin:
    """Comandos administrativos de Madrugue bajo ``/admin``."""

    # ========================================================
    # STATS
    # ========================================================

    @app_commands.command(
        name="stats",
        description="Muestra las estadísticas de Madrugue del servidor.",
    )
    async def stats(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra estadísticas generales."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        madrugadores, registros, puntos = (
            obtener_estadisticas_servidor(
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

    @app_commands.command(
        name="top",
        description="Muestra el TOP de Madrugue del servidor.",
    )
    async def top(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el ranking histórico."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resultados = obtener_top_madrugadores(
            interaction.guild.id,
            limite=10,
        )

        if not resultados:
            await interaction.response.send_message(
                "🏆 Todavía no hay madrugadores registrados.",
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

    @app_commands.command(
        name="resetdia",
        description="Elimina el registro de Madrugue de un usuario para una fecha.",
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
        """Elimina un registro diario."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await interaction.response.send_message(
                "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-08-31`.",
                ephemeral=True,
            )
            return

        registro = obtener_registro_del_dia_admin(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if registro is None:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** no tiene "
                f"un registro el **{fecha}**.",
                ephemeral=True,
            )
            return

        hora, puntos = registro

        eliminado = eliminar_registro_del_dia(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if eliminado == 0:
            await interaction.response.send_message(
                "⚠️ No se pudo eliminar el registro.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🗑️ Registro eliminado correctamente.\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Fecha: **{fecha}**\n"
            f"⏰ Hora registrada: **{hora}**\n"
            f"🏆 Puntos eliminados: **{puntos:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # RESET USUARIO
    # ========================================================

    @app_commands.command(
        name="resetusuario",
        description="Elimina todos los registros de Madrugue de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyos registros quieres eliminar.",
    )
    async def resetusuario(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Elimina todos los registros de un usuario."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resumen = obtener_resumen_usuario(
            interaction.guild.id,
            usuario.id,
        )

        cantidad_registros = resumen[0]
        puntos_totales = resumen[1]

        if cantidad_registros == 0:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** no tiene "
                "registros en este servidor.",
                ephemeral=True,
            )
            return

        eliminado = eliminar_registros_usuario(
            interaction.guild.id,
            usuario.id,
        )

        if eliminado == 0:
            await interaction.response.send_message(
                "⚠️ No se pudo eliminar ningún registro.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🗑️ Registros eliminados correctamente.\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📋 Registros eliminados: **{eliminado}**\n"
            f"🏆 Puntos eliminados: **{puntos_totales:.1f}**",
            ephemeral=True,
        )

    # ========================================================
    # RESET TOTAL
    # ========================================================

    @app_commands.command(
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
    async def resettotal(
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
            await interaction.response.send_message(
                "🛑 Operación cancelada. "
                "No se eliminó ningún registro.",
                ephemeral=True,
            )
            return

        madrugadores, registros, puntos = (
            obtener_estadisticas_servidor(
                interaction.guild.id
            )
        )

        if registros == 0:
            await interaction.response.send_message(
                "ℹ️ No hay registros de Madrugue para eliminar en este servidor.",
                ephemeral=True,
            )
            return

        eliminado = eliminar_registros_servidor(
            interaction.guild.id
        )

        await interaction.response.send_message(
            f"🗑️ **Borrado total completado.**\n\n"
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
        name="manualadd",
        description="Agrega manualmente la madrugada de un usuario.",
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

        # ----------------------------------------------------
        # VALIDAR FECHA
        # ----------------------------------------------------

        try:
            fecha_obj = datetime.strptime(
                fecha,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            await interaction.response.send_message(
                "❌ Fecha inválida.\n"
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
            await interaction.response.send_message(
                "❌ No podés registrar una fecha futura.",
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
            await interaction.response.send_message(
                "❌ Hora inválida.\n"
                "Usá el formato **HH:MM**.\n\n"
                "Ejemplo: `05:45`",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # COMPROBAR REGISTRO EXISTENTE
        # ----------------------------------------------------

        registro_existente = obtener_registro_del_dia(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
        )

        if registro_existente:
            hora_anterior, puntos = registro_existente

            await interaction.response.send_message(
                "⚠️ **EL USUARIO YA TIENE REGISTRO EN ESA FECHA**\n\n"
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
            await interaction.response.send_message(
                "❌ La hora indicada está fuera "
                "del horario válido.\n\n"
                "El horario permitido es "
                "**05:30 a 10:00**.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # CALCULAR RACHA
        # ----------------------------------------------------

        fechas_registradas = obtener_fechas_registradas(
            interaction.guild.id,
            usuario.id,
        )

        racha = calcular_racha_para_nuevo_registro(
            fechas_registradas,
            fecha_obj,
        )

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

        guardar_registro(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            username=usuario.display_name,
            fecha=fecha_obj,
            hora=hora_obj.strftime("%H:%M"),
            puntos_base=puntos_base,
            multiplicador=multiplicador,
            puntos_finales=puntos_finales,
        )

        # ----------------------------------------------------
        # EMOJI
        # ----------------------------------------------------

        if puntos_base == 100:
            emoji = "🥇"
        elif puntos_base == 25:
            emoji = "🥈"
        else:
            emoji = "🥉"

        # ----------------------------------------------------
        # CONFIRMACIÓN
        # ----------------------------------------------------

        await interaction.response.send_message(
            "🔧 **REGISTRO MANUAL AGREGADO**\n\n"
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
