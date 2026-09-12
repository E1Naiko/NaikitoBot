"""Administración del sistema Box: economía, equipo y sponsors."""

import discord
from discord import app_commands

from core.mensajes import responder, responder_texto
from commands.admin.base import solo_admin, solo_servidor
from core.utils import ahora
from modules.box.services import (
    ESTADO_CANCELADO,
    NOMBRES_ACCIONES,
    NOMBRES_SPONSORS,
    admin_cancelar_accion,
    cerrar_combate,
    combate_en_curso,
    fijar_canticos,
    obtener_canticos,
    admin_completar_acciones_vencidas,
    admin_curar_usuario,
    admin_dar_sponsor,
    admin_finalizar_accion,
    admin_modificar_dinero,
    admin_modificar_experiencia,
    admin_modificar_probabilidad_lesion,
    admin_obtener_estadisticas_box,
    admin_obtener_historial_desafios,
    admin_obtener_info_usuario,
    admin_obtener_lesionados,
    admin_obtener_top_box,
    admin_quitar_sponsor,
    admin_reset_usuario,
    obtener_accion_activa,
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
            await responder_texto(interaction, "⚠️ La cantidad no puede ser 0.",
                ephemeral=True,
            )
            return

        exitoso, saldo = admin_modificar_dinero(
            interaction.guild.id,
            usuario.id,
            cantidad,
        )

        if not exitoso:
            await responder_texto(interaction, f"❌ No se pudo modificar el dinero.\n\n"
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

        await responder_texto(interaction, f"💰 **Dinero {accion} correctamente.**\n\n"
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
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** no tiene "
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
            await responder_texto(interaction, "⚠️ La cantidad no puede ser 0.",
                ephemeral=True,
            )
            return

        exitoso, experiencia = admin_modificar_experiencia(
            interaction.guild.id,
            usuario.id,
            cantidad,
        )

        if not exitoso:
            await responder_texto(interaction, f"❌ No se pudo modificar la experiencia.\n\n"
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

        await responder_texto(interaction, f"⭐ **Experiencia {accion} correctamente.**\n\n"
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
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** "
                "no tiene una lesión activa.",
                ephemeral=True,
            )
            return

        await responder_texto(interaction, f"🚑 **Usuario curado correctamente.**\n\n"
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
            await responder_texto(interaction, "❌ La probabilidad debe estar entre **0% y 100%**.",
                ephemeral=True,
            )
            return

        await responder_texto(interaction, f"⚠️ **Probabilidad de lesión modificada.**\n\n"
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
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** "
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

        await responder_texto(interaction, f"🛑 **Acción cancelada correctamente.**\n\n"
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
                    await responder_texto(interaction, f"❌ No se pudo otorgar el sponsor "
                        f"**{nombre_sponsor}**.\n\n"
                        f"Se alcanzó el límite de **{limite} sponsors "
                        "activos de este tipo**.",
                        ephemeral=True,
                    )
                else:
                    await responder_texto(interaction, f"❌ No se pudo otorgar el sponsor "
                        f"**{nombre_sponsor}**.",
                        ephemeral=True,
                    )
            else:
                await responder_texto(interaction, "❌ El tipo de sponsor indicado no es válido.",
                    ephemeral=True,
                )

            return

        await responder_texto(interaction, f"🤝 **Sponsor otorgado correctamente.**\n\n"
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
            await responder_texto(interaction, f"❌ No se encontró el sponsor con ID "
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

        await responder_texto(interaction, f"🗑️ **Sponsor eliminado correctamente.**\n\n"
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

        await responder_texto(interaction, f"♻️ **Progreso Box reseteado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🗑️ Registros eliminados: **{total}**\n\n"
            f"🥊 El progreso de Box fue eliminado por completo.\n"
            f"📋 **Madrugue y SSF no fueron modificados.**",
            ephemeral=True,
        )

    # ========================================================
    # AYUDAS INTERNAS
    # ========================================================

    def _nombre_miembro(
        self,
        interaction: discord.Interaction,
        user_id: int,
    ) -> str:
        """Devuelve el nombre visible de un miembro o su mención cruda."""

        if interaction.guild is not None:
            miembro = interaction.guild.get_member(user_id)

            if miembro is not None:
                return miembro.display_name

        return f"<@{user_id}>"

    def _texto_sponsor(self, tipo: str) -> str:
        """Nombre visible de un tipo de sponsor."""

        return NOMBRES_SPONSORS.get(
            tipo,
            tipo.capitalize(),
        )

    # ========================================================
    # TOP
    # ========================================================

    @box.command(
        name="top",
        description="Muestra el ranking Box del servidor por EXP y dinero.",
    )
    async def box_top(
        self,
        interaction: discord.Interaction,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        filas = admin_obtener_top_box(
            interaction.guild.id,
            limite=10,
        )

        if not filas:
            await responder_texto(interaction, "ℹ️ Todavía no hay "
                "usuarios con progreso Box en este servidor.",
                ephemeral=True,
            )
            return

        medallas = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        lineas = []

        for posicion, (user_id, experiencia, dinero) in enumerate(
            filas,
            start=1,
        ):
            medalla = medallas.get(
                posicion,
                f"**{posicion}.**",
            )

            nombre = self._nombre_miembro(
                interaction,
                user_id,
            )

            lineas.append(
                f"{medalla} **{nombre}** — "
                f"⭐ {experiencia} EXP — 💰 {dinero}$"
            )

        await responder(
            interaction,
            "🥊 TOP Box del servidor",
            f"Ranking de **{interaction.guild.name}**.",
            color_area="box",
            ephemeral=True,
            secciones_=[
                ("Ranking", "\n".join(lineas), False),
            ],
        )

    # ========================================================
    # STATS
    # ========================================================

    @box.command(
        name="stats",
        description="Muestra estadísticas globales de Box del servidor.",
    )
    async def box_stats(
        self,
        interaction: discord.Interaction,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        datos = admin_obtener_estadisticas_box(
            interaction.guild.id,
        )

        await responder(
            interaction,
            "📊 Estadísticas de Box",
            f"Totales de **{interaction.guild.name}**.",
            color_area="box",
            ephemeral=True,
            secciones_=[
                ("👥 Jugadores", f"**{datos['jugadores']}**"),
                ("⭐ EXP total", f"**{datos['experiencia']}**"),
                ("💰 Dinero total", f"**{datos['dinero']}$**"),
                ("⏱️ Acciones activas", f"**{datos['acciones_activas']}**"),
                ("🤝 Sponsors activos", f"**{datos['sponsors_activos']}**"),
                ("🏆 Combates resueltos", f"**{datos['combates']}**"),
                ("📨 Desafíos pendientes", f"**{datos['pendientes']}**"),
                ("🚑 Lesionados", f"**{datos['lesionados']}**"),
            ],
        )

    # ========================================================
    # HISTORIAL
    # ========================================================

    @box.command(
        name="historial",
        description="Muestra los últimos combates de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyo historial quieres consultar.",
    )
    async def box_historial(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        filas = admin_obtener_historial_desafios(
            interaction.guild.id,
            usuario.id,
            limite=10,
        )

        if not filas:
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** "
                "todavía no participó en ningún combate.",
                ephemeral=True,
            )
            return

        lineas = []

        for creado_en, retador_id, contrincante_id, ganador_id in filas:
            rival_id = (
                retador_id
                if retador_id != usuario.id
                else contrincante_id
            )

            rival = self._nombre_miembro(
                interaction,
                rival_id,
            )

            gano = ganador_id == usuario.id
            resultado = "✅ Victoria" if gano else "❌ Derrota"

            fecha_corta = creado_en[:10]

            lineas.append(
                f"• `{fecha_corta}` vs **{rival}** — {resultado}"
            )

        await responder(
            interaction,
            f"🏆 Historial de {usuario.display_name}",
            color_area="box",
            ephemeral=True,
            secciones_=[
                ("Combates", "\n".join(lineas), False),
            ],
        )

    # ========================================================
    # LESIONADOS
    # ========================================================

    @box.command(
        name="lesionados",
        description="Lista usuarios con lesión activa o probabilidad acumulada.",
    )
    async def box_lesionados(
        self,
        interaction: discord.Interaction,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        ahora_actual = ahora()

        filas = admin_obtener_lesionados(
            interaction.guild.id,
            ahora_actual,
        )

        if not filas:
            await responder_texto(interaction, "✅ No hay usuarios "
                "lesionados ni con probabilidad acumulada.",
                ephemeral=True,
            )
            return

        limite = 20
        visibles = filas[:limite]
        restantes = len(filas) - len(visibles)

        lineas = []

        for user_id, probabilidad, lesionado_hasta in visibles:
            nombre = self._nombre_miembro(
                interaction,
                user_id,
            )

            if lesionado_hasta and lesionado_hasta > ahora_actual.isoformat():
                estado = f"🚑 hasta `{lesionado_hasta}`"
            else:
                estado = "🟢 sin lesión activa"

            lineas.append(
                f"• **{nombre}** — 🎲 {probabilidad:.1f}% — {estado}"
            )

        if restantes:
            lineas.append(f"… y **{restantes} más**")

        await responder(
            interaction,
            "🚑 Lesionados y probabilidades",
            color_area="box",
            ephemeral=True,
            secciones_=[
                ("Listado", "\n".join(lineas), False),
            ],
        )

    # ========================================================
    # FINALIZAR
    # ========================================================

    @box.command(
        name="finalizar",
        description="Liquida la acción ya vencida de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuya acción quieres liquidar.",
    )
    async def box_finalizar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        ahora_actual = ahora()

        accion = obtener_accion_activa(
            interaction.guild.id,
            usuario.id,
        )

        if accion is None:
            await responder_texto(interaction, f"ℹ️ **{usuario.display_name}** "
                "no tiene ninguna acción activa.",
                ephemeral=True,
            )
            return

        tipo, finaliza_en, _recompensa = accion

        if finaliza_en > ahora_actual.isoformat():
            nombre_accion = NOMBRES_ACCIONES.get(
                tipo,
                tipo.lower(),
            )

            await responder_texto(interaction, f"ℹ️ La acción de "
                f"**{usuario.display_name}** todavía no vence.\n\n"
                f"🥊 Acción: **{nombre_accion}**\n"
                f"⏰ Termina: `{finaliza_en}`\n\n"
                "Cuando venza la liquida el bot automáticamente. "
                "Si querés cancelarla sin recompensa, usá "
                "**/admin box cancelar**.",
                ephemeral=True,
            )
            return

        completada = admin_finalizar_accion(
            interaction.guild.id,
            usuario.id,
            ahora_actual,
        )

        if completada is None:
            await responder_texto(interaction, "⚠️ No se pudo liquidar "
                "la acción. Probablemente el bot ya la procesó.",
                ephemeral=True,
            )
            return

        (
            _guild_id,
            _user_id,
            tipo,
            recompensa,
            dinero_recompensa,
            se_lesiona,
            _probabilidad_sponsor,
            sponsor,
        ) = completada

        nombre_accion = NOMBRES_ACCIONES.get(
            tipo,
            tipo.lower(),
        )

        texto = (
            f"✅ **Acción liquidada correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"🥊 Acción: **{nombre_accion}**"
        )

        if tipo == "PROMOVIENDO":
            if sponsor:
                texto += (
                    f"\n🤝 Sponsor conseguido: "
                    f"**{self._texto_sponsor(sponsor)}**"
                )
            else:
                texto += "\n😞 No consiguió sponsor."
        else:
            recompensa_texto = f"{recompensa} EXP"

            if dinero_recompensa:
                recompensa_texto += f" + {dinero_recompensa}$"

            texto += f"\n🎁 Recompensa entregada: **{recompensa_texto}**"

        if se_lesiona:
            texto += "\n🚑 Se lastimó y quedó lesionado 3 horas."

        await responder_texto(interaction, texto,
            ephemeral=True,
        )

    # ========================================================
    # PROCESAR
    # ========================================================

    @box.command(
        name="procesar",
        description="Liquida todas las acciones vencidas del servidor.",
    )
    async def box_procesar(
        self,
        interaction: discord.Interaction,
    ):
        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        completadas = admin_completar_acciones_vencidas(
            interaction.guild.id,
            ahora(),
        )

        cantidad = len(completadas)

        if cantidad == 0:
            await responder_texto(interaction, "✅ No había acciones "
                "vencidas pendientes de liquidar en este servidor.",
                ephemeral=True,
            )
            return

        nombres_acciones = []
        lesiones = 0
        sponsors_conseguidos = 0

        for (
            _guild_id,
            _user_id,
            tipo,
            _recompensa,
            _dinero,
            se_lesiona,
            _probabilidad,
            sponsor,
        ) in completadas:
            nombre = NOMBRES_ACCIONES.get(
                tipo,
                tipo.lower(),
            )

            nombres_acciones.append(nombre)

            if se_lesiona:
                lesiones += 1

            if tipo == "PROMOVIENDO" and sponsor:
                sponsors_conseguidos += 1

        conteo = {}

        for nombre in nombres_acciones:
            conteo[nombre] = conteo.get(nombre, 0) + 1

        resumen = ", ".join(
            f"{nombre} ×{cantidad_acciones}"
            for nombre, cantidad_acciones in conteo.items()
        )

        texto = (
            f"✅ **Acciones procesadas: {cantidad}**\n\n"
            f"📋 Detalle: {resumen}\n"
            f"🚑 Lesiones nuevas: **{lesiones}**\n"
            f"🤝 Sponsors conseguidos: **{sponsors_conseguidos}**"
        )

        await responder_texto(interaction, texto,
            ephemeral=True,
        )

    @box.command(
        name="canticos",
        description="Activa o desactiva los cánticos del público que nombran miembros.",
    )
    @app_commands.describe(
        estado="Qué hacer con los cánticos de este servidor.",
    )
    @app_commands.choices(
        estado=[
            app_commands.Choice(
                name="🔊 Activar (consentido por el servidor)",
                value="activar",
            ),
            app_commands.Choice(
                name="🔇 Desactivar",
                value="desactivar",
            ),
            app_commands.Choice(
                name="❓ Consultar",
                value="consultar",
            ),
        ]
    )
    async def box_canticos(
        self,
        interaction: discord.Interaction,
        estado: app_commands.Choice[str],
    ):
        """El interruptor del cántico, por servidor.

        El cántico saca el apodo de una persona real al aire. En un servidor
        privado donde todos se conocen está bien; en uno grande es una
        humillación pública sin permiso. Por eso no se decide con una variable
        de entorno global sino con una declaración explícita de este servidor, y
        el default es apagado.
        """

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        guild_id = interaction.guild.id
        actual = obtener_canticos(guild_id)

        if estado.value == "consultar":
            await responder_texto(
                interaction,
                "🔊 Cánticos activados (este servidor decidió)."
                if actual
                else (
                    "🔇 Cánticos desactivados (este servidor decidió)."
                    if actual is not None
                    else "🔇 Nadie decidió todavía: rige la configuración "
                    "general, que viene apagada."
                ),
                ephemeral=True,
            )
            return

        activado = estado.value == "activar"
        fijar_canticos(guild_id, activado, interaction.user.id, ahora())

        await responder_texto(
            interaction,
            (
                "🔊 Cánticos activados. Aviso en el canal: a partir de la "
                "próxima pelea el público va a corear apodos reales."
                if activado
                else "🔇 Cánticos desactivados. Desde el próximo asalto el "
                "público no nombra a nadie."
            ),
            ephemeral=True,
        )

    @box.command(
        name="cerrar_combate",
        description="Cierra la pelea narrada que está ocupando el canal.",
    )
    async def box_cerrar_combate(self, interaction: discord.Interaction):
        """Desocupa el candado de "un combate a la vez".

        Hace falta para operar: si un canal se borró o el bot se cayó a mitad
        de una velada, la fila ``VIVO`` bloquearía todos los desafíos
        siguientes. Se cierra sin tocar las acciones ni las recompensas; lo
        único que se suelta es el candado del relato.
        """

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        en_curso = combate_en_curso(interaction.guild.id)

        if en_curso is None:
            await responder_texto(
                interaction,
                "🔇 No hay ninguna pelea narrándose en este servidor.",
                ephemeral=True,
            )
            return

        cerrar_combate(
            en_curso["id"],
            ESTADO_CANCELADO,
            ahora(),
            f"cerrado a mano por {interaction.user.display_name}",
        )

        await responder_texto(
            interaction,
            f"✅ Cerrada la pelea #{en_curso['id']}. El canal quedó libre "
            "para el próximo desafío; las acciones y recompensas de los "
            "peleadores no se tocaron.",
            ephemeral=True,
        )
