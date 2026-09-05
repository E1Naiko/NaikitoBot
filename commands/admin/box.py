"""Administración del sistema Box: economía, equipo y sponsors."""

import discord
from discord import app_commands

from commands.admin.base import solo_admin, solo_servidor
from core.utils import ahora
from modules.box.services import (
    admin_obtener_info_usuario,
    admin_modificar_dinero,
    admin_modificar_experiencia,
    admin_curar_usuario,
    admin_modificar_probabilidad_lesion,
    admin_cancelar_accion,
    admin_dar_sponsor,
    admin_quitar_sponsor,
    admin_reset_usuario,
)


class BoxAdminMixin:
    """Comandos administrativos de Box bajo ``/admin box``."""

    box = app_commands.Group(
        name="box",
        description="Administración del sistema Box.",
    )

    @box.command(
        name="info",
        description="Muestra toda la información Box de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario del servidor.",
    )
    async def box_info(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        info = admin_obtener_info_usuario(
            interaction.guild.id,
            usuario.id,
        )

        embed = discord.Embed(
            title=f"🥊 Información Box — {usuario.display_name}",
            color=discord.Color.dark_red(),
        )

        embed.add_field(
            name="💰 Economía",
            value=(
                f"EXP: **{info['experiencia']}**\n"
                f"Dinero: **{info['dinero']}$**"
            ),
            inline=True,
        )

        lesionado_hasta = info["lesionado_hasta"]

        if lesionado_hasta:
            estado_lesion = f"🚑 Hasta `{lesionado_hasta}`"
        else:
            estado_lesion = "✅ No lesionado"

        embed.add_field(
            name="🚑 Lesión",
            value=(
                f"Probabilidad: **{info['probabilidad_lesion']:.1f}%**\n"
                f"Estado: {estado_lesion}"
            ),
            inline=True,
        )

        accion = info["accion"]

        if accion:
            tipo, iniciado_en, finaliza_en, recompensa, dinero = accion

            recompensa_texto = f"{recompensa} EXP"

            if dinero:
                recompensa_texto += f" + {dinero}$"

            accion_texto = (
                f"**{tipo}**\n"
                f"Inicio: `{iniciado_en}`\n"
                f"Finaliza: `{finaliza_en}`\n"
                f"Recompensa: **{recompensa_texto}**"
            )
        else:
            accion_texto = "✅ Sin acción activa."

        embed.add_field(
            name="⏱️ Acción",
            value=accion_texto,
            inline=False,
        )

        mejoras = info["mejoras"]

        if mejoras:
            mejoras_texto = "\n".join(
                f"• `{mejora}`: nivel **{nivel}**"
                for mejora, nivel in mejoras.items()
            )
        else:
            mejoras_texto = "Sin mejoras."

        embed.add_field(
            name="📈 Mejoras",
            value=mejoras_texto,
            inline=True,
        )

        equipo = info["equipo"]

        if equipo:
            (
                vida,
                vida_maxima,
                dano,
                dano_maximo,
                defensa,
                defensa_maxima,
                cansancio,
                cansancio_maximo,
                puntos_habilidad,
                casco,
                guantes,
                protector_bucal,
                short,
                botas,
            ) = equipo

            equipo_texto = (
                f"❤️ Vida: **{vida}/{vida_maxima}**\n"
                f"⚔️ Daño: **{dano}/{dano_maximo}**\n"
                f"🛡️ Defensa: **{defensa}/{defensa_maxima}**\n"
                f"😮‍💨 Cansancio: **{cansancio}/{cansancio_maximo}**\n"
                f"⭐ Puntos habilidad: **{puntos_habilidad}**\n\n"
                f"🥊 Casco: **{casco}**\n"
                f"🥊 Guantes: **{guantes}**\n"
                f"🦷 Protector: **{protector_bucal}**\n"
                f"🩳 Short: **{short}**\n"
                f"🥾 Botas: **{botas}**"
            )
        else:
            equipo_texto = "Sin equipo registrado."

        embed.add_field(
            name="🥊 Equipo",
            value=equipo_texto,
            inline=True,
        )

        embed.add_field(
            name="🏆 Combates",
            value=(
                f"Pendientes: **{info['desafios_pendientes']}**\n"
                f"Participaciones: **{info['participaciones']}**\n"
                f"Victorias: **{info['victorias']}**"
            ),
            inline=False,
        )

        sponsors = info["sponsors"]

        nombres_sponsors = {
            "redes": "📱 Redes",
            "radio": "📻 Radio",
            "equipamiento": "🥊 Equipamiento",
            "medico": "🚑 Médico",
        }

        if sponsors:
            sponsors_texto = "\n".join(
                f"• ID `{sponsor[0]}` — "
                f"**{nombres_sponsors.get(sponsor[1], sponsor[1])}** "
                f"(expira `{sponsor[3]}`)"
                for sponsor in sponsors
            )
        else:
            sponsors_texto = "Sin sponsors activos."

        embed.add_field(
            name="🤝 Sponsors",
            value=sponsors_texto,
            inline=False,
        )

        embed.set_thumbnail(url=usuario.display_avatar.url)

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @box.command(
        name="dar_dinero",
        description="Suma o resta dinero Box a un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario al que se modificará el dinero.",
        cantidad="Cantidad de dinero a sumar o restar.",
    )
    async def box_dar_dinero(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        cantidad: int,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        if cantidad == 0:
            await interaction.response.send_message(
                "⚠️ La cantidad no puede ser 0.",
                ephemeral=True,
            )
            return

        exitoso, saldo = admin_modificar_dinero(
            interaction.guild.id,
            usuario.id,
            cantidad,
        )

        if not exitoso:
            await interaction.response.send_message(
                f"❌ No se pudo modificar el dinero.\n\n"
                f"💰 Saldo actual: **{saldo}$**\n"
                f"📉 La operación dejaría el saldo por debajo de **0$**.",
                ephemeral=True,
            )
            return

        if cantidad > 0:
            accion = "agregado"
            cantidad_texto = f"+{cantidad}"
        else:
            accion = "retirado"
            cantidad_texto = str(cantidad)

        await interaction.response.send_message(
            f"💰 **Dinero {accion} correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"💵 Modificación: **{cantidad_texto}$**\n"
            f"💰 Nuevo saldo: **{saldo}$**",
            ephemeral=True,
        )
    @box.command(
        name="sponsors",
        description="Muestra los sponsors activos de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyos sponsors quieres consultar.",
    )
    async def box_sponsors(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        info = admin_obtener_info_usuario(
            interaction.guild.id,
            usuario.id,
        )

        sponsors = info["sponsors"]

        nombres_sponsors = {
            "redes": "📱 Redes",
            "radio": "📻 Radio",
            "equipamiento": "🥊 Equipamiento",
            "medico": "🚑 Médico",
        }

        if not sponsors:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** no tiene "
                "sponsors activos.",
                ephemeral=True,
            )
            return

        lineas = []

        for sponsor in sponsors:
            (
                sponsor_id,
                tipo,
                obtenido_en,
                expira_en,
                ultimo_pago,
                ultimo_tratamiento,
            ) = sponsor

            nombre = nombres_sponsors.get(
                tipo,
                tipo.capitalize(),
            )

            linea = (
                f"**{nombre}**\n"
                f"🆔 ID: `{sponsor_id}`\n"
                f"📅 Obtenido: `{obtenido_en}`\n"
                f"⏳ Expira: `{expira_en}`"
            )

            if tipo in {"redes", "radio"}:
                linea += (
                    f"\n💰 Último pago: "
                    f"`{ultimo_pago or 'Nunca'}`"
                )

            if tipo == "medico":
                linea += (
                    f"\n🚑 Último tratamiento: "
                    f"`{ultimo_tratamiento or 'Nunca'}`"
                )

            lineas.append(linea)

        embed = discord.Embed(
            title=f"🤝 Sponsors — {usuario.display_name}",
            description="\n\n".join(lineas),
            color=discord.Color.gold(),
        )

        embed.set_thumbnail(
            url=usuario.display_avatar.url
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @box.command(
        name="dar_exp",
        description="Suma o resta experiencia Box a un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario al que se modificará la experiencia.",
        cantidad="Cantidad de EXP a sumar o restar.",
    )
    async def box_dar_exp(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        cantidad: int,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        if cantidad == 0:
            await interaction.response.send_message(
                "⚠️ La cantidad no puede ser 0.",
                ephemeral=True,
            )
            return

        exitoso, experiencia = admin_modificar_experiencia(
            interaction.guild.id,
            usuario.id,
            cantidad,
        )

        if not exitoso:
            await interaction.response.send_message(
                f"❌ No se pudo modificar la experiencia.\n\n"
                f"⭐ EXP actual: **{experiencia}**\n"
                f"📉 La operación dejaría la experiencia por debajo de **0**.",
                ephemeral=True,
            )
            return

        if cantidad > 0:
            accion = "agregada"
            cantidad_texto = f"+{cantidad}"
        else:
            accion = "retirada"
            cantidad_texto = str(cantidad)

        await interaction.response.send_message(
            f"⭐ **Experiencia {accion} correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"⭐ Modificación: **{cantidad_texto} EXP**\n"
            f"🏆 Nueva experiencia: **{experiencia} EXP**",
            ephemeral=True,
        )

    @box.command(
        name="curar",
        description="Cura la lesión activa de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario al que quieres curar.",
    )
    async def box_curar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        curado, lesionado_hasta = admin_curar_usuario(
            interaction.guild.id,
            usuario.id,
        )

        if not curado:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** "
                "no tiene una lesión activa.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🚑 **Usuario curado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🩹 La lesión que terminaba en "
            f"`{lesionado_hasta}` fue eliminada.\n\n"
            f"⚠️ La probabilidad de lesión acumulada "
            f"no fue modificada.",
            ephemeral=True,
        )

    @box.command(
        name="probabilidad",
        description="Establece la probabilidad de lesión de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario al que se modificará la probabilidad.",
        probabilidad="Probabilidad de lesión entre 0 y 100.",
    )
    async def box_probabilidad(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        probabilidad: float,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        exitoso, nuevo_valor = admin_modificar_probabilidad_lesion(
            interaction.guild.id,
            usuario.id,
            probabilidad,
        )

        if not exitoso:
            await interaction.response.send_message(
                "❌ La probabilidad debe estar entre **0% y 100%**.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"⚠️ **Probabilidad de lesión modificada.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🎲 Nueva probabilidad: **{nuevo_valor:.1f}%**",
            ephemeral=True,
        )

    @box.command(
        name="cancelar",
        description="Cancela la acción Box activa de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuya acción quieres cancelar.",
    )
    async def box_cancelar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        accion = admin_cancelar_accion(
            interaction.guild.id,
            usuario.id,
        )

        if accion is None:
            await interaction.response.send_message(
                f"ℹ️ **{usuario.display_name}** "
                "no tiene ninguna acción activa.",
                ephemeral=True,
            )
            return

        (
            tipo,
            iniciado_en,
            finaliza_en,
            recompensa,
            dinero_recompensa,
        ) = accion

        recompensa_texto = f"{recompensa} EXP"

        if dinero_recompensa:
            recompensa_texto += f" + {dinero_recompensa}$"

        await interaction.response.send_message(
            f"🛑 **Acción cancelada correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🥊 Acción: **{tipo}**\n"
            f"🕐 Iniciada: `{iniciado_en}`\n"
            f"⏰ Terminaba: `{finaliza_en}`\n"
            f"🎁 Recompensa que no se entregará: "
            f"**{recompensa_texto}**",
            ephemeral=True,
        )

    @box.command(
        name="dar_sponsor",
        description="Otorga manualmente un sponsor a un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario que recibirá el sponsor.",
        tipo="Tipo de sponsor que se otorgará.",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(
                name="📱 Redes",
                value="redes",
            ),
            app_commands.Choice(
                name="📻 Radio",
                value="radio",
            ),
            app_commands.Choice(
                name="🥊 Equipamiento",
                value="equipamiento",
            ),
            app_commands.Choice(
                name="🚑 Médico",
                value="medico",
            ),
        ]
    )
    async def box_dar_sponsor(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        tipo: app_commands.Choice[str],
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        ahora_actual = ahora()

        creado, motivo = admin_dar_sponsor(
            interaction.guild.id,
            usuario.id,
            tipo.value,
            ahora_actual,
        )

        nombres_sponsors = {
            "redes": "📱 Redes",
            "radio": "📻 Radio",
            "equipamiento": "🥊 Equipamiento",
            "medico": "🚑 Médico",
        }

        nombre_sponsor = nombres_sponsors.get(
            tipo.value,
            tipo.value.capitalize(),
        )

        if not creado:
            if motivo == "limite":
                if tipo.value in {"redes", "radio"}:
                    limite = 10
                    await interaction.response.send_message(
                        f"❌ No se pudo otorgar el sponsor "
                        f"**{nombre_sponsor}**.\n\n"
                        f"Se alcanzó el límite de **{limite} sponsors "
                        "activos de este tipo**.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ No se pudo otorgar el sponsor "
                        f"**{nombre_sponsor}**.",
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    "❌ El tipo de sponsor indicado no es válido.",
                    ephemeral=True,
                )

            return

        await interaction.response.send_message(
            f"🤝 **Sponsor otorgado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🏷️ Sponsor: **{nombre_sponsor}**",
            ephemeral=True,
        )

    @box.command(
        name="quitar_sponsor",
        description="Elimina un sponsor específico de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyo sponsor quieres eliminar.",
        sponsor_id="ID del sponsor que quieres eliminar.",
    )
    async def box_quitar_sponsor(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        sponsor_id: int,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        sponsor = admin_quitar_sponsor(
            interaction.guild.id,
            usuario.id,
            sponsor_id,
        )

        if sponsor is None:
            await interaction.response.send_message(
                f"❌ No se encontró el sponsor con ID "
                f"`{sponsor_id}` para **{usuario.display_name}**.",
                ephemeral=True,
            )
            return

        _, tipo = sponsor

        nombres_sponsors = {
            "redes": "📱 Redes",
            "radio": "📻 Radio",
            "equipamiento": "🥊 Equipamiento",
            "medico": "🚑 Médico",
        }

        nombre_sponsor = nombres_sponsors.get(
            tipo,
            tipo.capitalize(),
        )

        await interaction.response.send_message(
            f"🗑️ **Sponsor eliminado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🆔 ID: `{sponsor_id}`\n"
            f"🏷️ Sponsor: **{nombre_sponsor}**",
            ephemeral=True,
        )

    @box.command(
        name="reset",
        description="Resetea completamente el progreso Box de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyo progreso Box quieres resetear.",
    )
    async def box_reset(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        eliminados = admin_reset_usuario(
            interaction.guild.id,
            usuario.id,
        )

        total = sum(eliminados.values())

        await interaction.response.send_message(
            f"♻️ **Progreso Box reseteado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🗑️ Registros eliminados: **{total}**\n\n"
            f"🥊 El progreso de Box fue eliminado por completo.\n"
            f"📋 **Madrugue y SSF no fueron modificados.**",
            ephemeral=True,
        )
