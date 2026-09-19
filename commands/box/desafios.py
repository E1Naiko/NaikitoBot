"""Desafíos entre usuarios: sparring y pelea, con su vista de botones."""

from datetime import datetime, timedelta

import discord
from discord import app_commands

from commands.box.base import (
    canal_de_la_interaccion,
    resolver_canal,
    solo_servidor,
)
from config import (
    BOX_CHANNEL_IDS,
    BOX_COMBATE_ACTIVO,
    BOX_COMBATE_TICK_SEGUNDOS,
    BOX_DESAFIO_DURACION_HORAS,
    BOX_DESAFIO_VENTANA_HORAS,
    BOX_DESAFIO_EXP_PELEA,
    BOX_DESAFIO_EXP_SPARRING,
    BOX_DESAFIO_PREMIO_VS_BOT,
    BOX_DESAFIO_RECOMPENSA_POR_MEJORA,
    BOX_EXPERIENCIA_POR_MINUTO,
)
from core.mensajes import (
    crear_embed,
    responder,
    responder_error,
    responder_ok,
    seccion,
)
from core.permissions import es_admin
from core.utils import ahora
from modules.box.logic import texto_horas
from modules.box.services import (
    aceptar_desafio,
    cancelar_desafio,
    combate_en_curso,
    crear_desafio,
    desafio_registrado,
    desafios_pendientes,
    obtener_accion_activa,
    obtener_estado_box,
    preparar_bot_para_desafio,
    registrar_mensaje_desafio,
)

VENTANA_DESAFIO = timedelta(hours=BOX_DESAFIO_VENTANA_HORAS)
DURACION_DESAFIO = timedelta(hours=BOX_DESAFIO_DURACION_HORAS)

MENSAJES_DESAFIO_NO_DISPONIBLE = {
    "expirado": "⌛ El desafío ya expiró.",
    "ocupado": "⚠️ Uno de los dos usuarios ya tiene una acción activa.",
    "lesionado": "🚑 Uno de los dos usuarios está lesionado.",
    "combate_en_curso": "🥊 Hay una pelea narrándose en el canal.",
}

# Estados en los que la solicitud sigue pendiente en la base: la tarjeta del
# canal conserva su botón para volver a intentar más tarde. En los demás
# ("expirado", "invalido") la fila ya no está y la tarjeta se retira.
ESTADOS_TRANSITORIOS = ("ocupado", "lesionado", "combate_en_curso")

# Etiqueta legible de cada modalidad, para no mostrar "FIGHTING" en el canal.
MODALIDADES = {
    "SPARRING": "sparring",
    "FIGHTING": "pelea",
}


def modalidad(tipo: str) -> str:
    """Nombre legible de la modalidad de una solicitud."""

    return MODALIDADES.get(tipo, tipo.lower())


def _mencion(guild, user_id: int) -> str:
    """Mención legible de un peleador, sin explotar si no está en el guild."""

    miembro = guild.get_member(user_id) if guild is not None else None

    return miembro.mention if miembro is not None else f"Usuario {user_id}"


class ChallengeView(discord.ui.View):
    """Permite que solo el contrincante acepte un desafío.

    La tarjeta que lleva este botón se publica en el canal (no como respuesta
    efímera de la interacción), porque quien tiene que apretarlo es el
    desafiado y no el que ejecutó ``/box desafio`` o ``/box sparring``.
    """

    def __init__(
        self,
        box,
        desafio_id: int,
        retador_id: int,
        contrincante_id: int,
        tipo: str,
    ):
        super().__init__(timeout=int(BOX_DESAFIO_VENTANA_HORAS * 3600))
        self.box = box
        self.desafio_id = desafio_id
        self.retador_id = retador_id
        self.contrincante_id = contrincante_id
        self.tipo = tipo
        self.message = None

    @discord.ui.button(
        label="Aceptar desafío",
        style=discord.ButtonStyle.success,
    )
    async def aceptar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if (
            not es_admin(interaction.user.id)
            and interaction.channel_id not in BOX_CHANNEL_IDS
        ):
            await responder_error(
                interaction,
                "⚠️ Canal incorrecto",
                "Este desafío solo puede aceptarse en el canal de Box.",
            )
            return

        if interaction.user.id != self.contrincante_id:
            await responder_error(
                interaction,
                "⚠️ No autorizado",
                "Solo el contrincante puede aceptar este desafío.",
            )
            return

        # Igual que en el comando: la aceptación resuelve el plan completo
        # sobre la base y no puede gastar la ventana de 3 segundos.
        await interaction.response.defer(ephemeral=True)

        try:
            resultado = await self.box._aceptar_desafio(
                interaction,
                self.desafio_id,
                self.contrincante_id,
                self.tipo,
            )
        except Exception as error:
            print(
                f"[BOX] aceptar desafío falló: {type(error).__name__}: {error}",
                flush=True,
            )
            await responder_error(
                interaction,
                "⚠️ Error al aceptar el desafío",
                "Algo se rompió al procesar la aceptación. El desafío sigue "
                "pendiente; podés volver a intentarlo.",
            )
            return

        if resultado["estado"] == "aceptado":
            button.disabled = True
            embed = crear_embed(
                "🥊 ¡Desafío aceptado!",
                f"{_mencion(interaction.guild, self.retador_id)} vs "
                f"{_mencion(interaction.guild, self.contrincante_id)}: ambos "
                "competirán durante "
                f"{texto_horas(BOX_DESAFIO_DURACION_HORAS)}.",
                color_area="box",
            )
            seccion(embed, "Modalidad", f"**{modalidad(self.tipo)}**")
            # El helper vive en el cog (``DesafiosMixin``), no en la view:
            # ``self`` acá es la view y la llamada directa revienta con
            # ``AttributeError`` nada más aceptarse el desafío.
            self.box._agregar_relato(embed, resultado)
            await interaction.message.edit(
                embed=embed,
                view=self,
            )
            # La tarjeta del canal ya cuenta lo que pasó, pero el que apretó
            # el botón difirió una interacción efímera: si no llega una
            # respuesta propia se queda con la burbuja de "pensando" colgada.
            await responder_ok(
                interaction,
                "🥊 ¡Aceptaste el desafío!",
                f"Son {texto_horas(BOX_DESAFIO_DURACION_HORAS)} de "
                f"**{modalidad(self.tipo)}** contra "
                f"{_mencion(interaction.guild, self.retador_id)}.",
            )
            self.stop()
            return

        estado = resultado["estado"]
        detalle = MENSAJES_DESAFIO_NO_DISPONIBLE.get(
            estado,
            "El desafío ya no está disponible.",
        )

        if estado == "combate_en_curso":
            en_curso = resultado["combate"]
            detalle += (
                "\n\n**En el ring:** "
                f"{_mencion(interaction.guild, en_curso['retador_id'])} vs "
                f"{_mencion(interaction.guild, en_curso['contrincante_id'])} · "
                f"pelea #{en_curso['id']}."
                "\nTerminá de mirar esa y volvé a aceptar: el desafío sigue "
                "pendiente. `/box combate` muestra cómo va."
            )

        if estado in ESTADOS_TRANSITORIOS:
            # La solicitud sigue pendiente en la base, así que la tarjeta se
            # queda intacta y con su botón: antes se la reemplazaba por el
            # error y el "volvé a aceptar" no tenía con qué. El motivo viaja
            # en privado, al único que le interesa.
            await responder_error(
                interaction,
                "⚠️ Todavía no se puede aceptar",
                detalle,
            )
            return

        # Expirado o inexistente: la fila ya no está y la tarjeta es un botón
        # que no lleva a nada. Se retira del canal y se avisa al que apretó.
        if interaction.message is not None:
            await interaction.message.edit(
                embed=crear_embed(
                    "⚠️ Desafío no disponible",
                    detalle,
                    color_area="error",
                ),
                view=None,
            )

        await responder_error(
            interaction,
            "⚠️ Desafío no disponible",
            detalle,
        )
        self.stop()

    async def on_timeout(self):
        if self.message is None:
            return

        # La view vive en memoria hasta una hora después de publicada la
        # tarjeta. Si la solicitud ya se canceló (``/box cancelar``) o se
        # aceptó por otro camino, el canal está mostrando otra cosa y el
        # timeout no tiene que pisarla con un "expirado" mentiroso.
        if not await desafio_registrado(self.desafio_id):
            return

        embed = crear_embed(
            "⌛ Desafío expirado",
            f"El desafío de {modalidad(self.tipo)} expiró.",
            color_area="aviso",
        )
        await self.message.edit(
            embed=embed,
            view=None,
        )


class DesafiosMixin:
    """Crear y aceptar desafíos de sparring y de pelea."""

    @staticmethod
    def _agregar_relato(embed, resultado):
        """Avisá que la pelea se narra en el canal, si es que se narra.

        El relato se arma con el plan ya sorteado, así que lo único que puede
        faltar es que esté desactivado por configuración o que el canal no se
        haya resuelto al aceptar (combates viejos, previa a esta versión).
        """

        if not BOX_COMBATE_ACTIVO or resultado.get("combate_id") is None:
            return

        seccion(
            embed,
            "Relato en vivo",
            "Se publica acá mesmo: un mensaje por asalto y una línea nueva "
            f"cada {BOX_COMBATE_TICK_SEGUNDOS} segundos.",
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

        return await aceptar_desafio(
            desafio_id=desafio_id,
            guild_id=interaction.guild.id,
            contrincante_id=contrincante_id,
            ahora=ahora(),
            recompensa=(
                int(BOX_DESAFIO_DURACION_HORAS * 60)
                * BOX_EXPERIENCIA_POR_MINUTO
            ),
            tipo=tipo,
            multiplicador_experiencia=(
                BOX_DESAFIO_EXP_PELEA
                if tipo == "FIGHTING"
                else BOX_DESAFIO_EXP_SPARRING
            ),
            recompensa_por_mejora=BOX_DESAFIO_RECOMPENSA_POR_MEJORA,
            canal_id=interaction.channel_id,
            contrincante_es_bot=self._contrincante_es_bot(
                interaction, contrincante_id
            ),
        )

    def _contrincante_es_bot(
        self,
        interaction: discord.Interaction,
        contrincante_id: int,
    ) -> bool:
        """Indica si el desafío es contra el bot (pelear contra la casa).

        Es lo que decide si el premio se reduce a la fracción de
        ``BOX_DESAFIO_PREMIO_VS_BOT``. Se mira el miembro del guild y, por si
        la caché todavía no lo tiene, se compara contra el propio bot.
        """

        miembro = (
            interaction.guild.get_member(contrincante_id)
            if interaction.guild is not None
            else None
        )

        if getattr(miembro, "bot", False):
            return True

        return self.bot.user is not None and contrincante_id == self.bot.user.id

    async def _crear_desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
        tipo: str,
    ):
        """Desafía a un usuario (o al bot) a una pelea o sparring.

        La respuesta inicial solo se acepta durante 3 segundos y este
        camino toca la base varias veces (acción activa, lesión, candado;
        contra el bot, la resolución completa del plan). Se defiere al
        toque para que, si la base se demora, el comando tarde —y no
        reviente con 10062 "Unknown interaction".
        """
        await interaction.response.defer(ephemeral=True)

        try:
            await self._procesar_desafio(interaction, contrincante, tipo)
        except Exception as error:
            print(
                f"[BOX] crear desafío falló: {type(error).__name__}: {error}",
                flush=True,
            )
            await responder_error(
                interaction,
                "⚠️ Error al crear el desafío",
                "Algo se rompió al procesar el desafío. Volvé a intentarlo.",
            )

    async def _procesar_desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
        tipo: str,
    ):
        if not await solo_servidor(interaction):
            return

        if contrincante.id == interaction.user.id:
            await responder_error(
                interaction,
                "⚠️ Desafío inválido",
                "No puedes desafiarte a ti mismo.",
            )
            return

        if await obtener_accion_activa(interaction.guild.id, interaction.user.id):
            await responder_error(
                interaction,
                "⚠️ Acción activa",
                "Ya tienes una acción activa.",
            )
            return

        _, lesionado_hasta = await obtener_estado_box(
            interaction.guild.id,
            interaction.user.id,
        )
        if lesionado_hasta and lesionado_hasta > ahora():
            await responder_error(
                interaction,
                "🚑 Lesión activa",
                "No puedes desafiar a otro usuario mientras estás lesionado.",
            )
            return

        # Un solo combate a la vez: se avisa acá, antes de mandar el botón,
        # para no dejar a nadie con un desafío que no se puede aceptar. El
        # control duro está en ``aceptar_desafio``, dentro de la transacción.
        en_curso = await combate_en_curso(interaction.guild.id)

        if en_curso is not None:
            await responder_error(
                interaction,
                "🥊 Pelea en curso",
                f"{_mencion(interaction.guild, en_curso['retador_id'])} vs "
                f"{_mencion(interaction.guild, en_curso['contrincante_id'])} "
                "están en el ring ahora mismo. Cuando termine esa velada se "
                "puede aceptar la tuya; el desafío queda pendiente.",
            )
            return

        # ------------------------------------------------------------
        # CASO ESPECIAL: desafiar al bot -> auto-acepta con stats random
        # ------------------------------------------------------------
        es_bot = getattr(contrincante, "bot", False)
        if not es_bot and self.bot.user is not None:
            es_bot = contrincante.id == self.bot.user.id

        if es_bot:
            inicio = ahora()

            # Randomiza stats del bot entre los extremos del servidor
            # (min por stat = jugador más bajo, max = jugador más alto)
            info_bot = await preparar_bot_para_desafio(
                interaction.guild.id,
                contrincante.id,
            )

            # Asegurar que no quede un desafío pendiente duplicado previo
            # (preparar_bot ya limpia, pero reforzamos para el par exacto)
            try:
                from sqlalchemy import delete

                from core.database import crear_sesion
                from modules.box.models import BoxDesafio

                async with crear_sesion() as _sesion:
                    await _sesion.execute(
                        delete(BoxDesafio).where(
                            BoxDesafio.guild_id == interaction.guild.id,
                            BoxDesafio.retador_id == interaction.user.id,
                            BoxDesafio.contrincante_id == contrincante.id,
                        )
                    )
                    await _sesion.commit()
            except Exception:
                pass

            desafio_id = await crear_desafio(
                guild_id=interaction.guild.id,
                retador_id=interaction.user.id,
                contrincante_id=contrincante.id,
                ahora=inicio,
                expira_en=inicio + VENTANA_DESAFIO,
                tipo=tipo,
                canal_id=interaction.channel_id,
            )
            if desafio_id is None:
                await responder_error(
                    interaction,
                    "⚠️ Desafío pendiente",
                    "Ya existe un desafío pendiente con ese usuario.",
                )
                return

            resultado = await self._aceptar_desafio(
                interaction,
                desafio_id,
                contrincante.id,
                tipo,
            )

            if resultado["estado"] == "aceptado":
                vals = info_bot["valores"]
                rangos = info_bot["rangos_equipo"]
                embed = crear_embed(
                    "🤖 ¡El bot aceptó tu desafío!",
                    f"Has desafiado al bot y **aceptó al instante**.\n"
                    f"Ambos competirán durante {texto_horas(BOX_DESAFIO_DURACION_HORAS)}.",
                    color_area="box",
                )
                seccion(embed, "Modalidad", f"**{modalidad(tipo)}**")
                if tipo == "FIGHTING":
                    seccion(
                        embed,
                        "Premio contra el bot",
                        "Si ganás, cobrás solo el "
                        f"**{BOX_DESAFIO_PREMIO_VS_BOT:.0%}** del premio de "
                        "una pelea contra otro jugador. La experiencia se "
                        "cobra igual.",
                    )
                self._agregar_relato(embed, resultado)
                seccion(
                    embed,
                    "Stats del bot (randomizados)",
                    (
                        f"❤️ Vida: **{vals['vida']}/{vals['vida_maxima']}** "
                        f"(rango server {rangos['vida'][0]}-{rangos['vida'][1]})\n"
                        f"💥 Daño: **{vals['dano']}/{vals['dano_maximo']}** "
                        f"(rango {rangos['dano'][0]}-{rangos['dano'][1]})\n"
                        f"🛡️ Defensa: **{vals['defensa']}/{vals['defensa_maxima']}** "
                        f"(rango {rangos['defensa'][0]}-{rangos['defensa'][1]})\n"
                        f"⚡ Cansancio: **{vals['cansancio']}/{vals['cansancio_maximo']}** "
                        f"(rango {rangos['cansancio'][0]}-{rangos['cansancio'][1]})\n"
                        f"⭐ Exp: **{info_bot['experiencia']}** "
                        f"(rango {info_bot['rango_experiencia'][0]}-{info_bot['rango_experiencia'][1]})\n"
                        f"🎒 Equipamiento: casco **{vals['casco']}**, guantes **{vals['guantes']}**, "
                        f"bucal **{vals['protector_bucal']}**, short **{vals['short']}**, botas **{vals['botas']}**"
                    ),
                )
                if resultado.get("ganador_id") is not None:
                    ganador_mencion = (
                        contrincante.mention
                        if resultado["ganador_id"] == contrincante.id
                        else interaction.user.mention
                    )
                    seccion(
                        embed,
                        "Pelea — ganador sorteado",
                        f"{ganador_mencion} se lleva **${resultado['premio_dinero']:,}**",
                    )
                # Privada a propósito: contra el bot no hay desafiado que
                # esperar y la tarjeta trae el ganador ya sorteado, que el
                # canal no tiene por qué conocer antes del relato.
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Si el bot no pudo aceptar (ej. error inesperado), mapear a mensaje humano
            mensaje = MENSAJES_DESAFIO_NO_DISPONIBLE.get(
                resultado["estado"],
                "El desafío al bot no pudo completarse.",
            )
            await responder_error(
                interaction,
                "⚠️ Desafío no disponible",
                mensaje,
            )
            return

        inicio = ahora()

        # La tarjeta la tiene que ver el desafiado, que es quien puede
        # aceptarla, así que se publica en el canal. Por
        # ``interaction.followup`` no sirve: el comando difiere la interacción
        # como efímera (para que la base no gaste la ventana de tres segundos)
        # y por ahí la respuesta le llega solo al que desafió.
        canal = await canal_de_la_interaccion(self.bot, interaction)

        if canal is None:
            await responder_error(
                interaction,
                "⚠️ No se pudo publicar el desafío",
                "No encuentro el canal donde publicar la tarjeta con el "
                "botón. Probá de nuevo desde el canal de Box.",
            )
            return

        desafio_id = await crear_desafio(
            guild_id=interaction.guild.id,
            retador_id=interaction.user.id,
            contrincante_id=contrincante.id,
            ahora=inicio,
            expira_en=inicio + VENTANA_DESAFIO,
            tipo=tipo,
            canal_id=interaction.channel_id,
        )
        if desafio_id is None:
            await responder_error(
                interaction,
                "⚠️ Desafío pendiente",
                "Ya existe un desafío pendiente con ese usuario.",
            )
            return

        view = ChallengeView(
            self,
            desafio_id,
            interaction.user.id,
            contrincante.id,
            tipo,
        )
        embed = crear_embed(
            "🥊 ¡Nuevo desafío!",
            f"{contrincante.mention}, {interaction.user.mention} "
            "te desafía.",
            color_area="box",
        )
        seccion(embed, "Modalidad", f"**{modalidad(tipo)}**")
        seccion(
            embed,
            "Tiempo",
            f"{contrincante.mention} tiene "
            f"**{texto_horas(BOX_DESAFIO_VENTANA_HORAS)}** para aceptar.",
        )
        seccion(
            embed,
            "Para aceptar",
            "Tocá **Aceptar desafío** acá abajo. Si nadie lo toca, la "
            "solicitud expira sola y el que la mandó puede retirarla con "
            "`/box cancelar`.",
        )
        # Publicar puede fallar (sin permiso de envío en el canal, por
        # ejemplo): se retira la fila, porque una solicitud cuya tarjeta nadie
        # vio no se puede aceptar y bloquearía el par hasta que expire.
        try:
            mensaje = await canal.send(
                # La mención va en el contenido y no solo en el embed: dentro
                # de un embed no notifica a nadie, y una solicitud que el
                # desafiado no ve es una solicitud que expira sola.
                content=(
                    f"🥊 {contrincante.mention}, tenés una solicitud de "
                    f"**{modalidad(tipo)}** esperando."
                ),
                embed=embed,
                view=view,
            )
        except discord.HTTPException as error:
            print(
                f"[BOX] no se publicó la tarjeta del desafío {desafio_id}: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )
            await cancelar_desafio(
                desafio_id,
                interaction.guild.id,
                interaction.user.id,
                ahora(),
            )
            await responder_error(
                interaction,
                "⚠️ No se pudo publicar el desafío",
                "No pude mandar la tarjeta al canal: revisá que el bot tenga "
                "permiso de enviar mensajes ahí. La solicitud no quedó "
                "registrada.",
            )
            return

        view.message = mensaje

        # La tarjeta queda anotada en la fila para que ``/box cancelar`` la
        # pueda retirar del canal, incluso después de un reinicio del bot.
        try:
            await registrar_mensaje_desafio(desafio_id, mensaje.id)
        except Exception as error:
            print(
                f"[BOX] no se anotó la tarjeta del desafío {desafio_id}: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

        await responder(
            interaction,
            "🥊 Solicitud enviada",
            f"{contrincante.mention} tiene "
            f"**{texto_horas(BOX_DESAFIO_VENTANA_HORAS)}** para aceptar la "
            f"**{modalidad(tipo)}**.",
            color_area="box",
            secciones_=[
                (
                    "Dónde",
                    "La tarjeta con el botón quedó publicada en este canal: "
                    "ahí la ve el desafiado.",
                ),
                ("Cancelar", "`/box cancelar` la retira si te arrepentís."),
            ],
            ephemeral=True,
        )

    # ============================================================
    # /box cancelar
    # ============================================================

    @app_commands.command(
        name="cancelar",
        description="Cancela una solicitud de sparring o de pelea pendiente.",
    )
    @app_commands.describe(
        contrincante=(
            "Con quién tenés la solicitud. Hace falta si tenés más de una."
        ),
    )
    async def cancelar(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member | None = None,
    ):
        """Retira una solicitud pendiente: la que mandaste o la que te mandaron.

        Para la base es el mismo borrado en los dos roles (lo único que cambia
        es el aviso: "cancelada" si la propusiste, "rechazada" si te la
        propusieron). Además retira la tarjeta del canal, para que nadie
        apriete un botón que ya no lleva a ninguna parte.
        """

        if not await solo_servidor(interaction):
            return

        # Lee y borra en la base y después toca el canal: se difiere igual que
        # en la creación, para no gastar la ventana de tres segundos.
        await interaction.response.defer(ephemeral=True)

        try:
            await self._cancelar_solicitud(interaction, contrincante)
        except Exception as error:
            print(
                "[BOX] cancelar desafío falló: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )
            await responder_error(
                interaction,
                "⚠️ Error al cancelar",
                "Algo se rompió al cancelar la solicitud. Volvé a intentarlo.",
            )

    async def _cancelar_solicitud(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member | None,
    ):
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        momento = ahora()

        pendientes = await desafios_pendientes(guild_id, user_id, momento)

        if contrincante is not None:
            pendientes = [
                pendiente
                for pendiente in pendientes
                if contrincante.id
                in (pendiente["retador_id"], pendiente["contrincante_id"])
            ]

            if not pendientes:
                await responder_error(
                    interaction,
                    "⚠️ Solicitud inexistente",
                    f"No tenés ninguna solicitud pendiente con "
                    f"{contrincante.mention}.",
                )
                return

        if not pendientes:
            await responder_error(
                interaction,
                "🗑️ Sin solicitudes pendientes",
                "No tenés ningún desafío ni sparring esperando. Se crean con "
                "`/box desafio` o `/box sparring`.",
            )
            return

        if len(pendientes) > 1:
            await responder(
                interaction,
                "⚠️ Tenés varias solicitudes",
                "Decime cuál cancelar pasando el parámetro `contrincante`.",
                color_area="aviso",
                secciones_=[
                    (
                        "Pendientes",
                        "\n".join(
                            self._linea_pendiente(
                                interaction.guild,
                                user_id,
                                pendiente,
                            )
                            for pendiente in pendientes
                        ),
                    ),
                ],
                ephemeral=True,
            )
            return

        cancelado = await cancelar_desafio(
            pendientes[0]["id"],
            guild_id,
            user_id,
            momento,
        )

        if cancelado is None:
            # Carrera con el botón: entre la lectura y el borrado la solicitud
            # se aceptó (o expiró y otra creación la limpió).
            await responder_error(
                interaction,
                "⚠️ Ya no se puede cancelar",
                "La solicitud se aceptó o expiró mientras tanto: ya no queda "
                "nada pendiente con esa persona.",
            )
            return

        await self._retirar_tarjeta(interaction.guild, cancelado)

        propuso = cancelado["retador_id"] == user_id
        otro = _mencion(
            interaction.guild,
            (
                cancelado["contrincante_id"]
                if propuso
                else cancelado["retador_id"]
            ),
        )
        nombre = modalidad(cancelado["tipo"])

        await responder(
            interaction,
            "🛑 Solicitud cancelada" if propuso else "🛑 Solicitud rechazada",
            (
                f"Retiraste la solicitud de **{nombre}** que le mandaste a "
                f"{otro}."
                if propuso
                else f"Rechazaste la solicitud de **{nombre}** de {otro}."
            ),
            color_area="box",
            secciones_=[
                (
                    "Tarjeta",
                    "El mensaje del canal quedó sin botón: nadie puede "
                    "aceptarla.",
                ),
            ],
            ephemeral=True,
        )

    @staticmethod
    def _linea_pendiente(guild, user_id: int, pendiente: dict) -> str:
        """Una solicitud pendiente resumida en una línea."""

        la_propuso = pendiente["retador_id"] == user_id
        otro_id = (
            pendiente["contrincante_id"]
            if la_propuso
            else pendiente["retador_id"]
        )

        return (
            f"· {modalidad(pendiente['tipo'])} "
            f"{'enviada' if la_propuso else 'recibida'} · "
            f"{_mencion(guild, otro_id)} · expira "
            f"<t:{int(pendiente['expira_en'].timestamp())}:R>"
        )

    async def _retirar_tarjeta(self, guild, desafio: dict) -> None:
        """Cambia la tarjeta publicada por un aviso de solicitud cancelada.

        Si el mensaje ya no está (lo borraron a mano, cambió el canal, el bot
        perdió la caché) no se hace nada: la fila ya salió de la base, así que
        el botón —si alguien llega a apretarlo— responde "desafío no
        disponible" y retira la tarjeta él solo.
        """

        canal_id = desafio.get("canal_id")
        mensaje_id = desafio.get("mensaje_id")

        if not canal_id or not mensaje_id:
            return

        canal = await resolver_canal(self.bot, canal_id)

        if canal is None:
            return

        try:
            mensaje = await canal.fetch_message(mensaje_id)
            await mensaje.edit(
                embed=crear_embed(
                    "🛑 Solicitud cancelada",
                    f"La {modalidad(desafio['tipo'])} entre "
                    f"{_mencion(guild, desafio['retador_id'])} y "
                    f"{_mencion(guild, desafio['contrincante_id'])} quedó sin "
                    "efecto: ya no se puede aceptar.",
                    color_area="aviso",
                ),
                view=None,
            )
        except discord.HTTPException as error:
            print(
                f"[BOX] no se pudo retirar la tarjeta del desafío "
                f"{desafio['id']}: {type(error).__name__}: {error}",
                flush=True,
            )

    @app_commands.command(
        name="sparring",
        description=(
            "Desafía a otro usuario a un sparring de "
            f"{texto_horas(BOX_DESAFIO_DURACION_HORAS)}."
        ),
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
        description=(
            "Desafía a otro usuario a una pelea de "
            f"{texto_horas(BOX_DESAFIO_DURACION_HORAS)}."
        ),
    )
    @app_commands.describe(contrincante="Usuario al que quieres desafiar.")
    async def desafio(
        self,
        interaction: discord.Interaction,
        contrincante: discord.Member,
    ):
        await self._crear_desafio(interaction, contrincante, "FIGHTING")
