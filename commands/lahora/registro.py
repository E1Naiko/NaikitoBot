"""Registro automático de laHora: escucha los "420" del canal."""

import discord
from discord.ext import commands

import config
from modules.lahora.services import es_mensaje_420, registrar_lahora

# Reacciones con las que el bot confirma un 420 válido.
REACCION_REGISTRADO = "🌿"
REACCION_PRIMERO = "🥇"


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

        print(
            f"[420] {resultado.motivo} usuario={message.author.id} "
            f"hora={resultado.momento.strftime('%H:%M:%S')} "
            f"ventana={resultado.ventana} posicion={resultado.posicion} "
            f"puntos={resultado.puntos_finales}",
            flush=True,
        )

        if not resultado.exitoso:
            return

        reacciones = [REACCION_REGISTRADO]

        if resultado.posicion == 1:
            reacciones.append(REACCION_PRIMERO)

        for reaccion in reacciones:
            try:
                await message.add_reaction(reaccion)
            except discord.HTTPException as error:
                # Sin permiso de reacciones el registro igual queda hecho.
                print(
                    f"[420] no se pudo reaccionar ({type(error).__name__}): "
                    f"{error}",
                    flush=True,
                )
                break
