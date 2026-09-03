from datetime import date, datetime
import re
import shlex
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

from core.utils import ahora

from modules.madrugue.database import (
    guardar_registro,
    eliminar_registros_usuario,
    eliminar_registros_servidor,
    eliminar_registro_del_dia,
    obtener_estadisticas_servidor,
    obtener_registro_del_dia_admin,
    obtener_registro_del_dia,
    obtener_fechas_registradas,
    obtener_resumen_usuario,
    obtener_top_madrugadores,
)

from config import (
    ADMIN_USER_IDS,
    GUILD_ID,
)

from modules.madrugue.logic import (
    calcular_multiplicador_horario,
    calcular_racha_para_nuevo_registro,
    obtener_puntos_base,
)

from modules.ssf.services import (
    revivir_participante,
    iniciar_desafio,
)

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


# ============================================================
# COG ADMIN
# ============================================================

class Admin(commands.GroupCog, group_name="admin"):
    """Comandos administrativos del bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⛔ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
    # GRUPO SSF
    # ========================================================

    ssf = app_commands.Group(
        name="ssf",
        description="Comandos administrativos de SeptSinFP.",
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
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
    # SSF - REVIVIR
    # ========================================================

    @ssf.command(
        name="revivir",
        description="Revive a un participante eliminado de SeptSinFP.",
    )
    @app_commands.describe(
        usuario="Usuario eliminado que quieres revivir.",
        fecha="Día que olvidó registrar, en formato YYYY-MM-DD.",
    )
    async def ssf_revivir(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Revive un participante."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await interaction.response.send_message(
                "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-09-01`.",
                ephemeral=True,
            )
            return

        resultado = revivir_participante(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            fecha=fecha_obj,
        )

        if not resultado["exitoso"]:

            motivos = {
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "fuera_de_fecha": (
                    "⚠️ La fecha indicada está fuera "
                    "del período del desafío."
                ),
                "no_participante": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está registrado como participante "
                    "de SeptSinFP."
                ),
                "no_eliminado": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está eliminado.\n"
                    "No es necesario revivirlo."
                ),
                "ya_registrado": (
                    f"ℹ️ **{usuario.display_name}** "
                    f"ya tiene registrado el día **{fecha}**."
                ),
            }

            await interaction.response.send_message(
                motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo revivir al participante.",
                ),
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            f"💚 **Participante revivido correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Día recuperado: **{fecha}**\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n\n"
            f"🫡 **{usuario.display_name}** puede "
            "volver a utilizar `/ssf sobrevivi` normalmente."
        )

    # ========================================================
    # SSF - INICIAR
    # ========================================================

    @ssf.command(
        name="iniciar",
        description="Inicia un nuevo desafío SeptSinFP.",
    )
    @app_commands.describe(
        canal="Canal donde se utilizarán los comandos de SeptSinFP.",
    )
    async def ssf_iniciar(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
    ):
        """Inicia un nuevo desafío."""

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        fecha_inicio = "2026-09-01"
        fecha_fin = "2026-09-30"

        resultado = iniciar_desafio(
            guild_id=interaction.guild.id,
            nombre="SeptSinFP 2026",
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            canal_id=canal.id,
        )

        if not resultado["exitoso"]:

            if resultado["motivo"] == "ya_existe":
                mensaje = (
                    "⚠️ Ya existe un desafío SeptSinFP "
                    "activo en este servidor."
                )
            else:
                mensaje = (
                    "⚠️ No se pudo iniciar el desafío."
                )

            await interaction.response.send_message(
                mensaje,
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            f"🎯 **SeptSinFP iniciado correctamente.**\n\n"
            f"📋 Desafío: **SeptSinFP 2026**\n"
            f"🗓️ Inicio: **{fecha_inicio}**\n"
            f"🏁 Fin: **{fecha_fin}**\n"
            f"📢 Canal: {canal.mention}\n"
            f"🆔 ID del desafío: "
            f"**{resultado['desafio_id']}**\n\n"
            f"Los participantes ya pueden utilizar "
            f"**/ssf registrar** en {canal.mention}."
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

        if interaction.user.id not in ADMIN_USER_IDS:
            await interaction.response.send_message(
                "⛔ No tienes permisos para utilizar este comando.",
                ephemeral=True,
            )
            return

        # ----------------------------------------------------
        # VERIFICAR SERVIDOR
        # ----------------------------------------------------

        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse "
                "dentro de un servidor.",
                ephemeral=True,
            )
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


# ============================================================
# SETUP
# ============================================================

async def setup(bot: commands.Bot):
    """Carga el Cog administrativo."""

    await bot.add_cog(
        Admin(bot)
    )
