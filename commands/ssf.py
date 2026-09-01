import discord
from discord import app_commands
from discord.ext import commands

from core.utils import ahora

from config import SSF_CANALES_ID

from modules.ssf.services import (
    registrar_usuario,
    registrar_sobrevivi,
    obtener_estado_usuario,
    obtener_estado_desafio,
    obtener_lista_participantes,
)


class SSF(commands.GroupCog, group_name="ssf"):
    """Comandos del desafío SeptSinFP."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========================================================
    # REGISTRAR
    # ========================================================

    @app_commands.command(
        name="registrar",
        description="Te registra como participante de SeptSinFP.",
    )
    async def registrar(
        self,
        interaction: discord.Interaction,
    ):
        """Registra al usuario en el desafío."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
                ephemeral=True,
            )
            return

        if interaction.channel_id not in SSF_CANALES_ID:
            canales = ", ".join(
                f"<#{canal_id}>"
                for canal_id in SSF_CANALES_ID
            )
        
            await interaction.response.send_message(
                "⚠️ Este comando debe utilizarse "
                f"en uno de estos canales: {canales}.",
                ephemeral=True,
            )
            return

        resultado = registrar_usuario(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            ahora=ahora(),
        )

        if not resultado["exitoso"]:

            if resultado["motivo"] == "sin_desafio":
                mensaje = (
                    "⚠️ No hay un desafío SeptSinFP activo."
                )

            elif resultado["motivo"] == "fuera_de_fecha":
                mensaje = (
                    "⚠️ El período de inscripción "
                    "no está activo."
                )

            elif resultado["motivo"] == "ya_registrado":
                mensaje = (
                    "ℹ️ Ya estás registrado en "
                    "SeptSinFP."
                )

            elif resultado["motivo"] == "eliminado":
                mensaje = (
                    "❌ Fuiste eliminado del desafío y "
                    "no puedes volver a registrarte."
                )

            else:
                mensaje = (
                    "⚠️ No se pudo completar el registro."
                )

            await interaction.response.send_message(
                mensaje,
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🎯 **¡Te registraste en SeptSinFP, "
            f"{interaction.user.mention}!**\n\n"
            f"📅 Desafío: **{resultado['nombre']}**\n"
            f"🗓️ Período: "
            f"**{resultado['fecha_inicio']}** → "
            f"**{resultado['fecha_fin']}**\n\n"
            "A partir de ahora debes utilizar "
            "**/ssf sobrevivi** todos los días."
        )

    # ========================================================
    # SOBREVIVÍ
    # ========================================================

    @app_commands.command(
        name="sobrevivi",
        description="Registra que sobreviviste el día.",
    )
    async def sobrevivi(
        self,
        interaction: discord.Interaction,
    ):
        """Registra la supervivencia diaria."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
                ephemeral=True,
            )
            return

        if interaction.channel_id not in SSF_CANALES_ID:
            canales = ", ".join(
                f"<#{canal_id}>"
                for canal_id in SSF_CANALES_ID
            )
        
            await interaction.response.send_message(
                "⚠️ Este comando debe utilizarse "
                f"en uno de estos canales: {canales}.",
                ephemeral=True,
            )
            return

        resultado = registrar_sobrevivi(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            ahora=ahora(),
        )

        if not resultado["exitoso"]:

            if resultado["motivo"] == "sin_desafio":
                mensaje = (
                    "⚠️ No hay un desafío SeptSinFP activo."
                )

            elif resultado["motivo"] == "fuera_de_fecha":
                mensaje = (
                    "⚠️ Hoy no está dentro del período "
                    "del desafío."
                )

            elif resultado["motivo"] == "no_participante":
                mensaje = (
                    "❌ No estás registrado en SeptSinFP.\n"
                    "Utiliza **/ssf registrar** primero."
                )

            elif resultado["motivo"] == "eliminado":
                mensaje = (
                    "💀 **Ya estás eliminado de SeptSinFP.**\n"
                    "Solo un administrador puede revivirte."
                )

            elif resultado["motivo"] == "ya_registrado":
                mensaje = (
                    "✅ Ya registraste tu supervivencia "
                    "de hoy."
                )

            else:
                mensaje = (
                    "⚠️ No se pudo registrar tu supervivencia."
                )

            await interaction.response.send_message(
                mensaje,
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🫡 **{interaction.user.mention} SOBREVIVIÓ.**\n\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n"
            f"🕐 Registro: "
            f"**{resultado['hora'].strftime('%H:%M:%S')}**"
        )

    # ========================================================
    # ESTADO
    # ========================================================

    @app_commands.command(
        name="estado",
        description="Muestra tu estado actual en SeptSinFP.",
    )
    async def estado(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el estado del usuario."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
                ephemeral=True,
            )
            return

        resultado = obtener_estado_usuario(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
        )

        if not resultado["exitoso"]:

            if resultado["motivo"] == "sin_desafio":
                mensaje = (
                    "⚠️ No hay un desafío SeptSinFP activo."
                )
            else:
                mensaje = (
                    "ℹ️ No estás registrado en SeptSinFP."
                )

            await interaction.response.send_message(
                mensaje,
                ephemeral=True,
            )
            return

        if resultado["eliminado"]:
            estado = "💀 **ELIMINADO**"
        else:
            estado = "🟢 **ACTIVO**"

        await interaction.response.send_message(
            f"🎯 **SeptSinFP — Tu estado**\n\n"
            f"Estado: {estado}\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha_actual']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**"
            + (
                f"\n📅 Eliminado el: "
                f"**{resultado['fecha_eliminacion']}**"
                if resultado["eliminado"]
                else ""
            ),
            ephemeral=True,
        )

    # ========================================================
    # PARTICIPANTES
    # ========================================================

    @app_commands.command(
        name="participantes",
        description="Muestra los participantes de SeptSinFP.",
    )
    async def participantes(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra los participantes."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
                ephemeral=True,
            )
            return

        resultado = obtener_lista_participantes(
            guild_id=interaction.guild.id,
        )

        if resultado is None:
            await interaction.response.send_message(
                "⚠️ No hay un desafío SeptSinFP activo.",
                ephemeral=True,
            )
            return

        if not resultado:
            await interaction.response.send_message(
                "ℹ️ Todavía no hay participantes.",
                ephemeral=True,
            )
            return

        activos = []
        eliminados = []

        for participante in resultado:

            (
                user_id,
                username,
                _fecha_registro,
                eliminado,
                _fecha_eliminacion,
                racha_actual,
                mejor_racha,
            ) = participante

            if eliminado:
                eliminados.append(
                    f"💀 **{username}**"
                )
            else:
                activos.append(
                    f"🟢 **{username}** — "
                    f"🔥 {racha_actual} días"
                )

        embed = discord.Embed(
            title="🎯 SeptSinFP",
            description="Estado de los participantes.",
        )

        if activos:
            embed.add_field(
                name=f"🟢 Activos ({len(activos)})",
                value="\n".join(activos),
                inline=False,
            )

        if eliminados:
            embed.add_field(
                name=f"💀 Eliminados ({len(eliminados)})",
                value="\n".join(eliminados),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed
        )

    # ========================================================
    # AYUDA
    # ========================================================

    @app_commands.command(
        name="ayuda",
        description="Muestra la ayuda de SeptSinFP.",
    )
    async def ayuda(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra la ayuda del desafío."""

        embed = discord.Embed(
            title="🎯 SeptSinFP",
            description=(
                "Desafío de supervivencia durante "
                "todo septiembre."
            ),
        )

        embed.add_field(
            name="📝 /ssf registrar",
            value=(
                "Te registra como participante "
                "del desafío."
            ),
            inline=False,
        )

        embed.add_field(
            name="🫡 /ssf sobrevivi",
            value=(
                "Debes utilizarlo todos los días "
                "para continuar en el desafío."
            ),
            inline=False,
        )

        embed.add_field(
            name="📊 /ssf estado",
            value=(
                "Muestra tu estado y tus rachas."
            ),
            inline=False,
        )

        embed.add_field(
            name="👥 /ssf participantes",
            value=(
                "Muestra quiénes continúan y quiénes "
                "fueron eliminados."
            ),
            inline=False,
        )

        embed.add_field(
            name="⚠️ Importante",
            value=(
                "Si no registras tu supervivencia "
                "durante un día, quedas eliminado.\n\n"
                "Un administrador puede revivirte "
                "si hubo un olvido o un problema "
                "que justifique la excepción."
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    """Carga el Cog de SeptSinFP."""

    await bot.add_cog(
        SSF(bot)
    )