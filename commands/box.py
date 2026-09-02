from datetime import datetime, timedelta
import math

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core.utils import ahora
from modules.box.database import inicializar_db
from modules.box.services import (
    aceptar_desafio,
    completar_acciones_vencidas,
    crear_desafio,
    iniciar_accion,
    comprar_mejora,
    obtener_nivel_mejora,
    obtener_estadisticas_box,
    obtener_saldo,
    obtener_top_desafios,
    obtener_accion_activa,
    obtener_estado_box,
    descansar,
    comprar_tratamiento,
)
from config import (
    BOX_CHANNEL_IDS,
    BOX_DINERO_POR_MINUTO,
    BOX_EXPERIENCIA_POR_MINUTO,
)

MEJORAS = {
    "entrenamiento": {
        "nombre": "Creatina",
        "descripcion": "+5 EXP por minuto de entrenamiento",
        "precio": 1000,
        "maximo": 10,
    },
    "trabajo": {
        "nombre": "Cafe",
        "descripcion": "+50 dinero por minuto de trabajo",
        "precio": 1000,
        "maximo": 10,
    },
}

TRATAMIENTOS = {
    "fisioterapeutico": {
        "nombre": "Tratamiento Fisioterapeutico",
        "precio": 10000,
        "reinicia_probabilidad": False,
    },
    "cinco_estrellas": {
        "nombre": "Tratamiento 5 estrellas",
        "precio": 50000,
        "reinicia_probabilidad": True,
    },
}


def precio_mejora(mejora: dict, nivel: int) -> int:
    """Calcula el precio del siguiente nivel con aumento compuesto del 25 %."""

    return math.ceil(mejora["precio"] * 1.25 ** nivel)


class ChallengeView(discord.ui.View):
    """Permite que solo el contrincante acepte un desafío."""

    def __init__(
        self,
        box: "Box",
        desafio_id: int,
        contrincante_id: int,
        tipo: str,
    ):
        super().__init__(timeout=3600)
        self.box = box
        self.desafio_id = desafio_id
        self.contrincante_id = contrincante_id
        self.tipo = tipo
        self.message = None

    @discord.ui.button(label="Aceptar desafío", style=discord.ButtonStyle.success)
    async def aceptar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.contrincante_id:
            await interaction.response.send_message(
                "⚠️ Solo el contrincante puede aceptar este desafío.",
                ephemeral=True,
            )
            return

        resultado = await self.box._aceptar_desafio(
            interaction,
            self.desafio_id,
            self.contrincante_id,
            self.tipo,
        )
        if resultado["estado"] == "aceptado":
            button.disabled = True
            nombre = self.tipo.lower()
            await interaction.response.edit_message(
                content=f"🥊 ¡Desafío de {nombre} aceptado! Ambos competirán durante 1 hora.",
                view=self,
            )
            self.stop()
            return

        mensajes = {
            "expirado": "⌛ El desafío ya expiró.",
            "ocupado": "⚠️ Uno de los dos usuarios ya tiene una acción activa.",
            "lesionado": "🚑 Uno de los dos usuarios está lesionado.",
        }
        await interaction.response.edit_message(
            content=mensajes.get(
                resultado["estado"],
                "⚠️ El desafío ya no está disponible.",
            ),
            view=None,
        )
        self.stop()

    async def on_timeout(self):
        if self.message is not None:
            await self.message.edit(
                content="⌛ El desafío de sparring expiró.",
                view=None,
            )


class Box(commands.GroupCog, group_name="box"):
    """Acciones temporizadas de progreso y economía."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.comprobar_acciones.start()

    def cog_unload(self):
        self.comprobar_acciones.cancel()

    @tasks.loop(seconds=15)
    async def comprobar_acciones(self):
        """Liquida acciones vencidas y avisa en el canal disponible."""

        for (
            guild_id,
            user_id,
            tipo,
            recompensa,
            dinero_recompensa,
            se_lesiona,
        ) in completar_acciones_vencidas(ahora()):
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            usuario = guild.get_member(user_id)
            if usuario is None:
                try:
                    usuario = await guild.fetch_member(user_id)
                except discord.HTTPException:
                    continue

            canal = next(
                (
                    self.bot.get_channel(canal_id)
                    for canal_id in BOX_CHANNEL_IDS
                    if isinstance(
                        self.bot.get_channel(canal_id),
                        discord.abc.Messageable,
                    )
                ),
                None,
            )
            if isinstance(canal, discord.abc.Messageable):
                if tipo == "TRABAJANDO":
                    recompensa_texto = f"**{dinero_recompensa} $**"
                else:
                    recompensa_texto = f"**{recompensa} EXP**"
                    if dinero_recompensa:
                        recompensa_texto += (
                            f" y recibió **{dinero_recompensa} $**"
                        )
                nombres_acciones = {
                    "TRABAJANDO": "trabajar",
                    "ENTRENANDO": "entrenar",
                    "SPARRING": "hacer sparring",
                    "FIGHTING": "pelear",
                }
                nombre_accion = nombres_acciones.get(
                    tipo,
                    tipo.lower(),
                )
                await canal.send(
                    f"✅ {usuario.mention} terminó de **{nombre_accion}** "
                    f"y recibió {recompensa_texto}."
                )
                if se_lesiona:
                    await canal.send(
                        f"🚑 {usuario.mention} se lesionó y estará lesionado durante 24 horas."
                    )

    @comprobar_acciones.before_loop
    async def esperar_bot(self):
        await self.bot.wait_until_ready()

    async def _comenzar_accion(
        self,
        interaction: discord.Interaction,
        minutos: int | None,
        tipo: str,
        recompensa_por_minuto: int,
        hasta: str | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        _, lesionado_hasta = obtener_estado_box(
            interaction.guild.id,
            interaction.user.id,
        )
        if lesionado_hasta and datetime.fromisoformat(lesionado_hasta) > ahora():
            await interaction.response.send_message(
                f"🚑 Estás lesionado hasta <t:{int(datetime.fromisoformat(lesionado_hasta).timestamp())}:R>.",
                ephemeral=True,
            )
            return

        iniciado_en = ahora()
        if minutos is not None and hasta is not None:
            await interaction.response.send_message(
                "⚠️ Indica minutos o una hora de finalización, no ambas opciones.",
                ephemeral=True,
            )
            return

        if hasta is not None:
            try:
                hora_fin = datetime.strptime(hasta.strip(), "%H:%M").time()
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ La hora debe tener el formato HH:MM, por ejemplo 18:30.",
                    ephemeral=True,
                )
                return

            finaliza_en = datetime.combine(
                iniciado_en.date(),
                hora_fin,
                tzinfo=iniciado_en.tzinfo,
            )
            if finaliza_en <= iniciado_en:
                finaliza_en += timedelta(days=1)
            minutos = math.ceil(
                (finaliza_en - iniciado_en).total_seconds() / 60
            )
        elif minutos is not None:
            finaliza_en = iniciado_en + timedelta(minutes=minutos)
        else:
            await interaction.response.send_message(
                "⚠️ Debes indicar minutos o una hora de finalización.",
                ephemeral=True,
            )
            return

        if not 1 <= minutos <= 1440:
            await interaction.response.send_message(
                "⚠️ La duración debe estar entre 1 y 1440 minutos.",
                ephemeral=True,
            )
            return

        accion = obtener_accion_activa(
            interaction.guild.id,
            interaction.user.id,
        )
        if accion is not None:
            tipo_actual, finaliza_en, _ = accion
            timestamp = int(datetime.fromisoformat(finaliza_en).timestamp())
            await interaction.response.send_message(
                f"⚠️ Ya estás **{tipo_actual.lower()}**. "
                f"Tu acción termina <t:{timestamp}:R>.",
                ephemeral=True,
            )
            return

        recompensa = minutos * recompensa_por_minuto

        if not iniciar_accion(
            interaction.guild.id,
            interaction.user.id,
            tipo,
            iniciado_en,
            finaliza_en,
            recompensa,
        ):
            await interaction.response.send_message(
                "⚠️ Ya tienes otra acción activa.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Comenzaste a **{tipo.lower()}** durante **{minutos} minutos**.\n"
            f"⏰ Finaliza <t:{int(finaliza_en.timestamp())}:R>.\n"
            f"🎁 Recompensa: **{recompensa} "
            f"{'EXP' if tipo == 'ENTRENANDO' else '$'}**.",
        )

    @app_commands.command(
        name="entrenar",
        description="Entrena durante un tiempo para obtener experiencia.",
    )
    @app_commands.describe(
        minutos="Cantidad de minutos de entrenamiento.",
        hasta="Hora de finalización en formato HH:MM.",
    )
    async def entrenar(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        nivel = obtener_nivel_mejora(
            interaction.guild.id,
            interaction.user.id,
            "entrenamiento",
        ) if interaction.guild else 0
        await self._comenzar_accion(
            interaction,
            minutos,
            "ENTRENANDO",
            BOX_EXPERIENCIA_POR_MINUTO + nivel * 5,
            hasta,
        )

    @app_commands.command(
        name="trabajar",
        description="Trabaja durante un tiempo para obtener dinero.",
    )
    @app_commands.describe(
        minutos="Cantidad de minutos de trabajo.",
        hasta="Hora de finalización en formato HH:MM.",
    )
    async def trabajar(
        self,
        interaction: discord.Interaction,
        minutos: int | None = None,
        hasta: str | None = None,
    ):
        nivel = obtener_nivel_mejora(
            interaction.guild.id,
            interaction.user.id,
            "trabajo",
        ) if interaction.guild else 0
        await self._comenzar_accion(
            interaction,
            minutos,
            "TRABAJANDO",
            BOX_DINERO_POR_MINUTO + nivel * 50,
            hasta,
        )

    @app_commands.command(
        name="ayuda",
        description="Envía por mensaje directo la ayuda de Box.",
    )
    async def ayuda(self, interaction: discord.Interaction):
        ayuda = (
            "🥊 **Ayuda de Box**\n\n"
            "`/box entrenar minutos` — Entrena y gana experiencia.\n"
            "`/box trabajar minutos` — Trabaja y gana dinero.\n"
            "`/box sparring contrincante` — Desafía a sparring.\n"
            "`/box desafio contrincante` — Desafía a una pelea.\n"
            "`/box saldo` — Muestra tu experiencia y dinero.\n"
            "`/box stats` — Muestra tus estadísticas privadas.\n"
            "`/box tienda` — Muestra mejoras y tratamientos.\n"
            "`/box comprar mejora` — Compra una mejora.\n"
            "`/box tratamiento tipo` — Cura una lesión.\n"
            "`/box descanso` — Reinicia la probabilidad de lesión.\n"
            "`/box topdesafios` — Muestra el ranking de desafíos.\n\n"
            "Las acciones duran el tiempo indicado y continúan aunque el bot se reinicie."
        )

        try:
            await interaction.user.send(ayuda)
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ No pude enviarte un mensaje directo. "
                "Activa los mensajes directos de este servidor e inténtalo otra vez.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "✅ Te envié la ayuda de Box por mensaje directo.",
            ephemeral=True,
        )

    @app_commands.command(
        name="saldo",
        description="Muestra tu experiencia y dinero de Box.",
    )
    async def saldo(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        experiencia, dinero = obtener_saldo(
            interaction.guild.id,
            interaction.user.id,
        )
        await interaction.response.send_message(
            f"📊 **Saldo de {interaction.user.display_name}**\n"
            f"⭐ Experiencia: **{experiencia}**\n"
            f"💰 Dinero: **{dinero}**"
        )

    @app_commands.command(
        name="descanso",
        description="Reinicia tu probabilidad de lesión a cero.",
    )
    async def descanso(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return
        if obtener_accion_activa(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message(
                "⚠️ No puedes descansar mientras realizas una acción.",
                ephemeral=True,
            )
            return

        _, lesionado_hasta = obtener_estado_box(
            interaction.guild.id,
            interaction.user.id,
        )
        if lesionado_hasta and datetime.fromisoformat(lesionado_hasta) > ahora():
            await interaction.response.send_message(
                "🚑 No puedes descansar mientras estás lesionado.",
                ephemeral=True,
            )
            return

        descansar(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            "🛌 Tu probabilidad de lesión volvió a **0%**.",
            ephemeral=True,
        )
    @app_commands.command(
        name="stats",
        description="Muestra tus estadísticas privadas de Box.",
    )
    async def stats(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        estadisticas = obtener_estadisticas_box(
            interaction.guild.id,
            interaction.user.id,
        )
        ratio = estadisticas["ratio"]
        ratio_texto = "∞" if ratio == float("inf") else f"{ratio:.2f}"
        accion = obtener_accion_activa(
            interaction.guild.id,
            interaction.user.id,
        )
        accion_texto = "Ninguna"
        if accion is not None:
            accion_texto = (
                f"{accion[0].lower()} hasta "
                f"<t:{int(datetime.fromisoformat(accion[1]).timestamp())}:R>"
            )

        await interaction.response.send_message(
            f"📊 **Stats de {interaction.user.display_name}**\n"
            f"⭐ Experiencia: **{estadisticas['experiencia']}**\n"
            f"💰 Dinero: **{estadisticas['dinero']}**\n"
            f"🥊 Desafíos: **{estadisticas['ganadas']}/"
            f"{estadisticas['perdidas']}** ratio: **{ratio_texto}**\n"
            f"📈 Creatina: nivel **{estadisticas['nivel_entrenamiento']}**\n"
            f"☕ Cafe: nivel **{estadisticas['nivel_trabajo']}**\n"
            f"🩹 Probabilidad de lesión: **{estadisticas['probabilidad_lesion']:.2f}%**\n"
            f"⏳ Acción actual: **{accion_texto}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="topdesafios",
        description="Muestra el ranking histórico de desafíos.",
    )
    async def topdesafios(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        ranking = obtener_top_desafios(interaction.guild.id)
        if not ranking:
            await interaction.response.send_message(
                "🏆 Todavía no hay desafíos finalizados."
            )
            return

        lineas = ["🏆 **TOP DE DESAFÍOS**"]
        for posicion, (user_id, ganadas, perdidas, ratio) in enumerate(
            ranking,
            start=1,
        ):
            usuario = interaction.guild.get_member(user_id)
            nombre = usuario.display_name if usuario else f"Usuario {user_id}"
            ratio_texto = "∞" if ratio == float("inf") else f"{ratio:.2f}"
            lineas.append(
                f"{posicion}) **{nombre}** {ganadas}/{perdidas} "
                f"ratio: **{ratio_texto}**"
            )

        await interaction.response.send_message("\n".join(lineas))

    @app_commands.command(
        name="tienda",
        description="Muestra las mejoras disponibles en la tienda.",
    )
    async def tienda(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        lineas = ["🛒 **Tienda de Box**"]
        for clave, mejora in MEJORAS.items():
            nivel = obtener_nivel_mejora(
                interaction.guild.id,
                interaction.user.id,
                clave,
            )
            lineas.append(
                f"**{clave}** — {mejora['descripcion']} | "
                f"Nivel **{nivel}/{mejora['maximo']}** | "
                f"Siguiente nivel: **{precio_mejora(mejora, nivel)}**"
            )
        lineas.append("\n**Tratamientos**")
        for tratamiento in TRATAMIENTOS.values():
            lineas.append(
                f"**{tratamiento['nombre']}** — "
                f"Precio fijo: **{tratamiento['precio']}**"
            )
        await interaction.response.send_message("\n".join(lineas))

    @app_commands.command(
        name="comprar",
        description="Compra un nivel de mejora con tu dinero.",
    )
    @app_commands.describe(mejora="Mejora que quieres comprar.")
    @app_commands.choices(
        mejora=[
            app_commands.Choice(name="Creatina", value="entrenamiento"),
            app_commands.Choice(name="Cafe", value="trabajo"),
        ]
    )
    async def comprar(
        self,
        interaction: discord.Interaction,
        mejora: app_commands.Choice[str],
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        configuracion = MEJORAS[mejora.value]
        estado, saldo, nivel = comprar_mejora(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            mejora=mejora.value,
            precio_base=configuracion["precio"],
            nivel_maximo=configuracion["maximo"],
        )
        if estado == "insuficiente":
            await interaction.response.send_message(
                f"⚠️ Necesitas el siguiente precio (**{precio_mejora(configuracion, nivel)}**) "
                f"y tienes **{saldo}**.",
                ephemeral=True,
            )
            return
        if estado == "maximo":
            await interaction.response.send_message(
                f"⚠️ Ya alcanzaste el nivel máximo (**{nivel}**).",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ Compraste un nivel de **{configuracion['nombre']}**. "
            f"Nivel actual: **{nivel}**. Saldo restante: **{saldo}**."
        )

    @app_commands.command(
        name="tratamiento",
        description="Compra un tratamiento para quitar una lesión.",
    )
    @app_commands.describe(tipo="Tratamiento que quieres comprar.")
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="Tratamiento Fisioterapeutico", value="fisioterapeutico"),
            app_commands.Choice(name="Tratamiento 5 estrellas", value="cinco_estrellas"),
        ]
    )
    async def tratamiento(
        self,
        interaction: discord.Interaction,
        tipo: app_commands.Choice[str],
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        configuracion = TRATAMIENTOS[tipo.value]
        estado, saldo = comprar_tratamiento(
            interaction.guild.id,
            interaction.user.id,
            f"tratamiento_{tipo.value}",
            configuracion["precio"],
            ahora(),
        )
        if estado == "insuficiente":
            await interaction.response.send_message(
                f"⚠️ Necesitas **{configuracion['precio']}** y tienes **{saldo}**.",
                ephemeral=True,
            )
            return
        if estado == "no_lesionado":
            await interaction.response.send_message(
                "⚠️ No estás lesionado.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"✅ Compraste **{configuracion['nombre']}** y ya no estás lesionado.",
            ephemeral=True,
        )

    async def _aceptar_desafio(
        self,
        interaction: discord.Interaction,
        desafio_id: int,
        contrincante_id: int,
        tipo: str,
    ):
        if interaction.guild is None:
            return {"estado": "invalido"}

        base = 60 * BOX_EXPERIENCIA_POR_MINUTO
        resultado = aceptar_desafio(
            desafio_id=desafio_id,
            guild_id=interaction.guild.id,
            contrincante_id=contrincante_id,
            ahora=ahora(),
            recompensa=60 * BOX_EXPERIENCIA_POR_MINUTO,
            tipo=tipo,
            multiplicador_experiencia=10 if tipo == "FIGHTING" else 5,
            recompensa_por_mejora=5,
        )
        return resultado

    async def _crear_desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
        tipo: str,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ Este comando solo puede utilizarse dentro de un servidor.",
                ephemeral=True,
            )
            return

        if contrincante.id == interaction.user.id:
            await interaction.response.send_message(
                "⚠️ No puedes desafiarte a ti mismo.",
                ephemeral=True,
            )
            return

        if obtener_accion_activa(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message(
                "⚠️ Ya tienes una acción activa.",
                ephemeral=True,
            )
            return

        _, lesionado_hasta = obtener_estado_box(
            interaction.guild.id,
            interaction.user.id,
        )
        if lesionado_hasta and datetime.fromisoformat(lesionado_hasta) > ahora():
            await interaction.response.send_message(
                "🚑 No puedes desafiar a otro usuario mientras estás lesionado.",
                ephemeral=True,
            )
            return

        ahora_actual = ahora()
        desafio_id = crear_desafio(
            guild_id=interaction.guild.id,
            retador_id=interaction.user.id,
            contrincante_id=contrincante.id,
            ahora=ahora_actual,
            expira_en=ahora_actual + timedelta(hours=1),
        )
        if desafio_id is None:
            await interaction.response.send_message(
                "⚠️ Ya existe un desafío pendiente con ese usuario.",
                ephemeral=True,
            )
            return

        nombre = tipo.lower()
        view = ChallengeView(self, desafio_id, contrincante.id, tipo)
        await interaction.response.send_message(
            f"🥊 {contrincante.mention}, {interaction.user.mention} te desafía "
            f"a un {nombre}. Tienes 1 hora para aceptar.\n"
            f"Al aceptar, ambos estarán en modo **{tipo}** durante 1 hora.",
            view=view,
        )
        view.message = await interaction.original_response()

    @app_commands.command(
        name="sparring",
        description="Desafía a otro usuario a un sparring de una hora.",
    )
    @app_commands.describe(contrincante="Usuario al que quieres desafiar.")
    async def sparring(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
    ):
        await self._crear_desafio(interaction, contrincante, "SPARRING")

    @app_commands.command(
        name="desafio",
        description="Desafía a otro usuario a una pelea de una hora.",
    )
    @app_commands.describe(contrincante="Usuario al que quieres desafiar.")
    async def desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
    ):
        await self._crear_desafio(interaction, contrincante, "FIGHTING")


async def setup(bot: commands.Bot):
    inicializar_db()
    await bot.add_cog(Box(bot))
