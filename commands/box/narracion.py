"""Narración en tiempo real de peleas y sparrings.

Un asalto es un mensaje del canal; cada latido del bot revela una línea más
de ese mensaje. Todo lo que se muestra se recalcula desde el plan guardado en
``box_combates``, así que no hay contadores que perderse: si el bot se
reinicia, el asalto se vuelve a renderizar y el canal sigue contando la misma
pelea.

El plan ya está resuelto cuando se acepta el desafío (ver
``modules.box.combate``), por lo que este módulo solo traduce, formatea y
habla con Discord. No decide nada.
"""

import asyncio
from dataclasses import replace
from datetime import timedelta

import discord
import discord.utils
from discord import app_commands
from discord.ext import tasks

from commands.box.base import solo_servidor

from config import (
    BOX_COMBATE_ACTIVO,
    BOX_COMBATE_CANTICOS,
    BOX_COMBATE_MAX_ASELLAR_POR_TICK,
    BOX_COMBATE_MAX_POR_TICK,
    BOX_COMBATE_TICK_SEGUNDOS,
)
from core.mensajes import crear_embed, responder, responder_error, seccion
from core.utils import ahora
from modules.box.combate import Plan
from modules.box.narracion import (
    apertura,
    cierre,
    dialogos,
    marcador_de,
    recortar,
    veredicto,
)
from modules.box.services import (
    ESTADO_CANCELADO,
    ESTADO_TERMINADO,
    actualizar_mensaje_combate,
    asaltos_publicados,
    cerrar_combate,
    latido_de,
    mensaje_de_asalto,
    obtener_canticos,
    obtener_combate_en_curso,
    obtener_combates_vivos,
    reclamar_asalto,
    registrar_mensaje_asalto,
    tiene_accion_activa,
)

# Cuánto se aguanta un canal introutable antes de dar el combate por cerrado.
GRACIA_SIN_CANAL = timedelta(minutes=5)

LIMITE_DESCRIPCION = 3800
LARGO_NOMBRE = 20
Pausa = timedelta(seconds=0.6)

TITULOS = {
    "FIGHTING": "🥊 En vivo",
    "SPARRING": "🤝 Sparring en vivo",
}


def nombre_visible(miembro) -> str:
    """Nombre del peleador, listo para meter en una línea de narración.

    Se escapa el markdown y se recorta: un apodo de 32 caracteres con
    subrayados puede romper el formato de toda la velada o estirar el
    mensaje por encima del límite de Discord.
    """

    if miembro is None:
        return "Boxeador"

    nombre = discord.utils.escape_markdown(
        str(getattr(miembro, "display_name", miembro))
    )

    if len(nombre) > LARGO_NOMBRE:
        nombre = nombre[: LARGO_NOMBRE - 1].rstrip() + "…"

    return nombre


class NarracionMixin:
    """Revela los combates en vivo, asalto por asalto."""

    def _iniciar_narracion(self):
        if BOX_COMBATE_ACTIVO:
            self.narrar_combates.start()

    @tasks.loop(seconds=BOX_COMBATE_TICK_SEGUNDOS)
    async def narrar_combates(self):
        """Un latido: revelar diálogos, cerrar asaltos y clausurar peleas."""

        vivos = await asyncio.to_thread(obtener_combates_vivos, ahora())

        if not vivos:
            return

        enviados = 0

        for combate in vivos[:BOX_COMBATE_MAX_POR_TICK]:
            try:
                enviados += await self._narrar_combate(combate)
            except discord.HTTPException as error:
                print(
                    f"[BOX] narración falló combate={combate['id']}: "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )
            except Exception as error:  # nunca tumbar el loop por un dato malo
                print(
                    f"[BOX] narración inesperada combate={combate['id']}: "
                    f"{type(error).__name__}: {error}",
                    flush=True,
                )

        if enviados:
            await asyncio.sleep(0.1)

    @narrar_combates.before_loop
    async def esperar_bot_para_narrar(self):
        await self.bot.wait_until_ready()

    # ============================================================
    # Un latido de un combate
    # ============================================================

    async def _narrar_combate(self, combate: dict) -> int:
        """Publica lo que corresponde de un combate. Devuelve los envíos."""

        canal = await self._canal_del_combate(combate)

        if canal is None:
            # Puede ser momentáneo (el bot arrancando, el guild todavía sin
            # cachar), así que se espera. Pero con un solo combate por bot un
            # canal desaparecido sería un candado eterno: pasada la ventana de
            # narración, la fila se cierra y la velada se da por terminada.
            if ahora() > combate["fin_narracion_en"] + GRACIA_SIN_CANAL:
                await asyncio.to_thread(
                    cerrar_combate,
                    combate["id"],
                    ESTADO_CANCELADO,
                    ahora(),
                    "el canal de narración no volvió a estar disponible",
                )

            return 0

        if not await asyncio.to_thread(
            tiene_accion_activa,
            combate["guild_id"],
            combate["retador_id"],
        ) or not await asyncio.to_thread(
            tiene_accion_activa,
            combate["guild_id"],
            combate["contrincante_id"],
        ):
            await asyncio.to_thread(
                cerrar_combate,
                combate["id"],
                ESTADO_CANCELADO,
                ahora(),
                "el combate se canceló antes del campanazo final",
            )
            return 0

        plan = await self._plan_con_nombres(combate)
        canticos = await self._cantos_del_servidor(combate["guild_id"])

        latido = latido_de(combate, ahora())
        terminando = latido >= plan.latidos
        asalto_actual, beat = plan.posicion(latido)
        asalto_actual = min(asalto_actual, len(plan.asaltos) - 1)

        publicados = await asyncio.to_thread(asaltos_publicados, combate["id"])

        # Asaltos que quedaron sin publicar (reinicio del bot, un canal caído):
        # se cierran con su veredicto, en orden y sin inundar el canal.
        # Cuando el combate ya terminó se incluye el último asalto, si no el
        # canal se quedaría sin el asalto de la definición.
        hasta = len(plan.asaltos) if terminando else asalto_actual
        pendientes = sorted(set(range(hasta)) - publicados)

        enviados = 0

        for indice in pendientes[:BOX_COMBATE_MAX_ASELLAR_POR_TICK]:
            await self._publicar_asalto(
                canal, combate, plan, indice, cerrado=True, canticos=canticos
            )
            await asyncio.sleep(Pausa.total_seconds())
            enviados += 1
            # El asalto recién asentado ya no está "en curso" a los efectos de
            # este latido: se refresca el set para no depender de que el
            # ``reclamar_asalto`` de abajo nos cubra las espaldas.
            publicados.add(indice)

        if terminando:
            if len(pendientes) > BOX_COMBATE_MAX_ASELLAR_POR_TICK:
                # Todavía hay asaltos que asentar: el cierre espera al
                # próximo latido, para que el resultado no llegue antes que
                # la pelea que lo explica.
                return enviados

            return enviados + await self._cerrar_combate(canal, combate, plan)

        # Asalto en curso: se manda la primera vez y de ahí se edita.
        if asalto_actual not in publicados:
            if not await asyncio.to_thread(
                reclamar_asalto, combate["id"], asalto_actual, ahora()
            ):
                return enviados

            await self._publicar_asalto(
                canal,
                combate,
                plan,
                asalto_actual,
                revelados=beat,
                canticos=canticos,
            )
            return enviados + 1

        mensaje_id = await asyncio.to_thread(
            mensaje_de_asalto, combate["id"], asalto_actual
        )
        mensaje = await self._obtener_mensaje(canal, mensaje_id)

        if mensaje is None:
            await self._publicar_asalto(
                canal,
                combate,
                plan,
                asalto_actual,
                revelados=beat,
                canticos=canticos,
            )
            return enviados + 1

        try:
            await mensaje.edit(
                embed=self._embed_asalto(
                    plan,
                    asalto_actual,
                    revelados=beat,
                    en_curso=True,
                    canticos=canticos,
                )
            )
        except discord.NotFound:
            await self._publicar_asalto(
                canal,
                combate,
                plan,
                asalto_actual,
                revelados=beat,
                canticos=canticos,
            )
            return enviados + 1

        return enviados

    # ============================================================
    # Piezas del mensaje
    # ============================================================

    async def _plan_con_nombres(self, combate: dict) -> Plan:
        """Plan guardado, con los nombres reales de los peleadores.

        La base de datos no sabe cómo se llama nadie: el plan guarda un
        rótulo genérico y acá se pisan los nombres con los del servidor. El
        resto del plan (semilla, marcador, eventos) no se toca, así el
        resultado narrado es exactamente el que se sorteó al aceptar.
        """

        plan = Plan.de_json(combate["plan"])

        guild = self.bot.get_guild(combate["guild_id"])

        nombres = []

        for user_id in (combate["retador_id"], combate["contrincante_id"]):
            miembro = guild.get_member(user_id) if guild else None

            if miembro is None and guild is not None:
                try:
                    miembro = await guild.fetch_member(user_id)
                except discord.HTTPException:
                    miembro = None

            nombres.append(nombre_visible(miembro))

        return replace(plan, nombres=tuple(nombres))

    async def _cantos_del_servidor(self, guild_id: int) -> bool:
        """Si el servidor consintió que el público nombre a alguien.

        Se lee en cada latido y no se cachea: es un SELECT de una fila y la
        decisión puede cambiar entre un asalto y el siguiente (apagar los
        cánticos a mitad de pelea tiene que funcionar ya).
        """

        decision = await asyncio.to_thread(obtener_canticos, guild_id)

        return BOX_COMBATE_CANTICOS if decision is None else decision

    def _cuerpo_del_asalto(
        self,
        plan: Plan,
        asalto_index: int,
        *,
        revelados: int,
        en_curso: bool,
        apertura_en_curso: bool = False,
        canticos: bool = BOX_COMBATE_CANTICOS,
    ) -> tuple[str, list]:
        """Texto y secciones de un asalto.

        Lo consumen el mensaje del canal y ``/box combate``: una sola fuente
        de rendering, así lo que ve quien pregunta es literalmente lo que se
        está publicando (y si algo se corta por el límite de Discord, se corta
        igual en los dos lados).
        """

        asalto = plan.asaltos[asalto_index]
        lineas = dialogos(plan, asalto_index, revelados, canticos)

        # El marcador que se muestra es el acumulado *antes* de este asalto
        # mientras sigue en curso: si ya contara el asalto en el que estamos
        # sonando, el veredicto del cierre sería redundante.
        hasta = asalto_index + 1 if not en_curso else asalto_index
        acumulado = marcador_de(plan.asaltos[:hasta])

        cuerpo = list(lineas)

        if not en_curso or revelados >= plan.dialogos_por_round:
            cuerpo.append(veredicto(plan, asalto_index))

        texto = "\n".join(cuerpo) if cuerpo else "…suena la campana…"

        if apertura_en_curso:
            texto = f"{apertura(plan, plan.nombres)}\n\n{texto}"

        secciones = [
            (
                "Asaltos",
                f"🔵 {plan.nombres[0]} {acumulado[0]} — {acumulado[1]} "
                f"{plan.nombres[1]} 🔴\n"
                f"intercambios del asalto: "
                f"{asalto.puntos[0]}-{asalto.puntos[1]}",
            ),
            ("Estado físico", self._barras(plan, asalto_index)),
            (
                "Pelea pactada",
                f"{plan.asaltos_pactados} asaltos · tono {plan.tono.lower()}",
            ),
        ]

        return recortar(texto, LIMITE_DESCRIPCION), secciones

    def _embed_asalto(
        self,
        plan: Plan,
        asalto_index: int,
        *,
        revelados: int,
        en_curso: bool,
        cerrado: bool = False,
        apertura_en_curso: bool = False,
        canticos: bool = BOX_COMBATE_CANTICOS,
    ) -> discord.Embed:
        """Embed de un asalto: líneas reveladas, barras y marcador."""

        asalto = plan.asaltos[asalto_index]
        descripcion, secciones_ = self._cuerpo_del_asalto(
            plan,
            asalto_index,
            revelados=revelados,
            en_curso=en_curso,
            apertura_en_curso=apertura_en_curso,
            canticos=canticos,
        )

        embed = crear_embed(
            f"{TITULOS.get(plan.modo, '🥊 En vivo')} · Asalto "
            f"{asalto.numero} de {plan.asaltos_pactados}",
            descripcion,
            color_area="box",
        )

        for nombre, valor in secciones_:
            seccion(embed, nombre, valor)

        if en_curso and not cerrado:
            embed.set_footer(
                text=(
                    f"asalto {asalto_index + 1}/{len(plan.asaltos)} · "
                    f"{min(revelados, plan.dialogos_por_round)}/"
                    f"{plan.dialogos_por_round} diálogos"
                )
            )

        return embed

    @staticmethod
    def _barras(plan: Plan, asalto_index: int) -> str:
        """Barras de vida y cansancio al cerrar el asalto."""

        asalto = plan.asaltos[asalto_index]
        partes = []

        for indice, color in enumerate(("🔵", "🔴")):
            maxima = max(1, plan.vida_maxima[indice])
            actual = asalto.vida[indice]
            llenado = round(10 * actual / maxima)
            partes.append(
                f"{color} {plan.nombres[indice]} "
                f"{'█' * llenado}{'░' * (10 - llenado)} {actual}"
            )

        return "\n".join(partes)

    # ============================================================
    # Publicación
    # ============================================================

    async def _publicar_asalto(
        self,
        canal,
        combate: dict,
        plan: Plan,
        asalto_index: int,
        *,
        revelados: int | None = None,
        cerrado: bool = False,
        canticos: bool = BOX_COMBATE_CANTICOS,
    ):
        """Manda el mensaje de un asalto y recuerda su id."""

        ahora_ = ahora()

        embed = self._embed_asalto(
            plan,
            asalto_index,
            revelados=plan.dialogos_por_round if cerrado else (revelados or 1),
            en_curso=not cerrado,
            cerrado=cerrado,
            apertura_en_curso=asalto_index == 0 and not cerrado,
            canticos=canticos,
        )

        mensaje = await canal.send(embed=embed)

        await asyncio.to_thread(
            registrar_mensaje_asalto,
            combate["id"],
            asalto_index,
            mensaje.id,
            ahora_,
        )
        await asyncio.to_thread(actualizar_mensaje_combate, combate["id"], mensaje.id)

        return mensaje

    async def _cerrar_combate(self, canal, combate: dict, plan: Plan) -> int:
        """Mensaje final y cierre de la fila."""

        embed = crear_embed(
            "🏁 Fin del combate",
            recortar(cierre(plan), LIMITE_DESCRIPCION),
            color_area="box",
        )
        seccion(embed, "Tarjeta", plan.resumen())
        seccion(
            embed,
            "Recompensa",
            "la experiencia y el premio se oficializan cuando termina la "
            "acción del desafío.",
        )

        await canal.send(embed=embed)

        await asyncio.to_thread(
            cerrar_combate,
            combate["id"],
            ESTADO_TERMINADO,
            ahora(),
            plan.resumen(),
        )

        return 1


    # ============================================================
    # /box combate
    # ============================================================

    @app_commands.command(
        name="combate",
        description="Muestra cómo va tu pelea o sparring en vivo.",
    )
    async def combate(self, interaction: discord.Interaction):
        """Estado del combate en curso, sin esperar al próximo latido.

        Es la misma tarjeta que publica el narrador, leída del plan: sirve
        para ver la pelea en cualquier momento y para depurar sin tener que
        dejar el bot corriendo quince minutos.
        """

        if not await solo_servidor(interaction):
            return

        fila = obtener_combate_en_curso(interaction.guild.id, interaction.user.id)

        if fila is None:
            await responder_error(
                interaction,
                "🥊 Sin combate en vivo",
                "No tenés una pelea ni un sparring en curso. Desafiá a "
                "alguien con /box desafio o /box sparring.",
            )
            return

        plan = await self._plan_con_nombres(fila)
        canticos = await self._cantos_del_servidor(fila["guild_id"])
        latido = latido_de(fila, ahora())
        terminado = latido >= plan.latidos
        asalto_index, beat = plan.posicion(latido)
        asalto_index = min(asalto_index, len(plan.asaltos) - 1)

        espera = max(0, plan.ciclo - (latido % plan.ciclo)) * fila["latido_segundos"]

        reloj = (
            f"próxima línea en {espera} s · la velada cierra "
            f"<t:{int(fila['fin_narracion_en'].timestamp())}:R>"
        )

        if terminado:
            await responder(
                interaction,
                "🏁 Combate terminado",
                cierre(plan),
                color_area="box",
                secciones_=[
                    ("Tarjeta", plan.resumen()),
                    ("Relato", reloj),
                ],
            )
            return

        descripcion, secciones_ = self._cuerpo_del_asalto(
            plan,
            asalto_index,
            revelados=beat,
            en_curso=True,
            apertura_en_curso=asalto_index == 0,
            canticos=canticos,
        )

        await responder(
            interaction,
            f"{TITULOS.get(plan.modo, '🥊 En vivo')} · Asalto "
            f"{asalto_index + 1} de {plan.asaltos_pactados}",
            descripcion,
            color_area="box",
            secciones_=[*secciones_, ("Relato", reloj)],
        )

    # ============================================================
    # Ayudas
    # ============================================================

    async def _canal_del_combate(self, combate: dict):
        """Canal donde se narra: el del desafío, o el de Box si no se guardó."""

        canal_id = combate.get("canal_id")

        if canal_id:
            canal = self.bot.get_channel(canal_id)

            if isinstance(canal, discord.abc.Messageable):
                return canal

        return self._canal_box()

    @staticmethod
    async def _obtener_mensaje(canal, mensaje_id: int):
        if mensaje_id is None:
            return None

        try:
            return await canal.fetch_message(mensaje_id)
        except discord.NotFound:
            return None
        except discord.HTTPException:
            return None


__all__ = ["NarracionMixin", "nombre_visible"]
