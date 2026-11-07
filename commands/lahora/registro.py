"""Registro automático de laHora: escucha los "420" del canal."""

import discord
from discord.ext import commands

import config
from core.discord_http import (
    espera_restante,
    registrar_limite,
    resumir_error,
)
from core.lahora_logs import linea_podio, linea_registro
from modules.lahora.services import es_mensaje_420, registrar_lahora
from modules.sanciones.database import sancion_vigente
from modules.sanciones.logic import texto_sancion_activa

# Reacciones con las que el bot confirma un 420 válido.
REACCION_REGISTRADO = "🌿"
REACCION_PRIMERO = "🥇"


async def _avisar_sancion(mensaje: discord.Message) -> None:
    """Avisa en el canal que el 420 no se registró por la sanción vigente.

    ``on_message`` no tiene interacción, así que se responde con un mensaje
    normal. El temporizador se lee de la base en el momento del aviso.
    """

    if espera_restante() > 0:
        return

    sancion = await sancion_vigente(
        mensaje.guild.id,
        mensaje.author.id,
        "lahora",
    )

    if sancion is None:
        return

    _, expiracion = sancion

    responder_mensaje = getattr(mensaje, "reply", None)

    if not callable(responder_mensaje):
        return

    try:
        await responder_mensaje(
            texto_sancion_activa("lahora", expiracion),
            mention_author=False,
        )
    except (discord.HTTPException, discord.RateLimited) as error:
        registrar_limite(error, contexto="420.sancion")
        print(
            f"[420] aviso de sanción omitido mensaje={mensaje.id} "
            f"({type(error).__name__}): {resumir_error(error)}",
            flush=True,
        )


class RegistroMixin:
    """Detecta los "420" del canal y los registra sin comandos."""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Registra el mensaje si es un 420 dicho a tiempo.

        Fuera de horario o repetido no se responde nada, para no llenar
        el canal de avisos: la reacción 🌿 es la confirmación.
        """

        if message.author.bot or message.guild is None:
            return

        if message.channel.id not in config.LAHORA_CANALES_ID:
            return

        if not es_mensaje_420(message.content):
            return

        resultado = await registrar_lahora(
            guild_id=message.guild.id,
            user_id=message.author.id,
            username=message.author.display_name,
            # Se usa la hora del mensaje y no la de procesamiento: un
            # 420 de las 16:20:59 no puede quedar afuera por latencia.
            momento=message.created_at,
            mensaje_id=message.id,
        )

        # En la terminal solo se cuentan las novedades del ranking: los
        # mensajes fuera de horario, repetidos o de sancionados no suman y
        # llenarían el log sin decir nada nuevo.
        if resultado.motivo == "sancionado":
            print(
                f"[420] ⛔ sanción vigente "
                f"{message.author.display_name} ({message.author.id}) "
                f"mensaje={message.id}; 420 no registrado",
                flush=True,
            )
            # El canal es de mensajes, no de comandos: se contesta una sola
            # vez por mensaje y con el temporizador del ban.
            await _avisar_sancion(message)
            return

        if not resultado.exitoso:
            return

        print(
            linea_registro(
                resultado,
                message.author.display_name,
                message.author.id,
                message.id,
            ),
            flush=True,
        )

        aviso_podio = linea_podio(
            resultado,
            message.author.display_name,
            message.author.id,
        )

        if aviso_podio:
            print(aviso_podio, flush=True)

        reacciones = [REACCION_REGISTRADO]

        if resultado.posicion == 1:
            reacciones.append(REACCION_PRIMERO)

        for reaccion in reacciones:
            # La confirmación es opcional: durante un bloqueo no se encolan
            # reacciones ni se repite el registro que ya quedó guardado.
            if espera_restante() > 0:
                break

            try:
                await message.add_reaction(reaccion)
            except (discord.HTTPException, discord.RateLimited) as error:
                registrar_limite(error, contexto="420.reaccion")
                # Sin permiso o con un límite el registro igual queda hecho.
                print(
                    f"[420] reacción omitida mensaje={message.id} "
                    f"({type(error).__name__}): {resumir_error(error)}; "
                    "registro conservado",
                    flush=True,
                )
                break
