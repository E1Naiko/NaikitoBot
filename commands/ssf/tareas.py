"""Revisión diaria automática de SeptSinFP."""

from datetime import timedelta

import discord
from discord.ext import tasks

from core.utils import ahora
from modules.ssf.services import (
    cerrar_desafios_finalizados,
    procesar_eliminaciones_diarias,
)


class TareasMixin:
    """Elimina a quienes no sobrevivieron y publica el resumen."""

    @tasks.loop(minutes=1)
    async def procesar_ssf_automatico(self):
        """
        Procesa automáticamente SSF una vez por día.

        Después de las 00:05:
        - Revisa el día anterior.
        - Elimina participantes que no sobrevivieron.
        - Publica el resumen.
        - Cierra desafíos finalizados.
        """

        ahora_actual = ahora()

        # ====================================================
        # ANTES DE LAS 00:05
        # ====================================================

        if (
            ahora_actual.hour == 0
            and ahora_actual.minute < 5
        ):
            return

        # ====================================================
        # FECHA A REVISAR
        # ====================================================

        fecha_a_revisar = (
            ahora_actual.date()
            - timedelta(days=1)
        )

        # ====================================================
        # EVITAR DUPLICADOS
        # ====================================================

        if self.ssf_ultima_revision == fecha_a_revisar:
            return

        print(
            "[SSF] Iniciando revisión automática de "
            f"{fecha_a_revisar}..."
        )

        try:

            # =================================================
            # PROCESAR ELIMINACIONES
            # =================================================

            resultados = (
                procesar_eliminaciones_diarias(
                    fecha_a_revisar
                )
            )

            # =================================================
            # PROCESAR DESAFÍOS
            # =================================================

            for resultado in resultados:

                eliminados = resultado["eliminados"]

                print(
                    "[SSF] Desafío "
                    f"{resultado['desafio_id']} "
                    f"(servidor "
                    f"{resultado['guild_id']}): "
                    f"{len(eliminados)} eliminado(s)."
                )

                # =============================================
                # SERVIDOR
                # =============================================

                guild = self.bot.get_guild(
                    resultado["guild_id"]
                )

                if guild is None:

                    print(
                        "[SSF] ⚠️ No se encontró el "
                        f"servidor {resultado['guild_id']}."
                    )

                    continue

                # =============================================
                # CANAL
                # =============================================

                canal = self._canal_desafio(
                    guild,
                    resultado["canal_id"],
                )

                if canal is None:

                    print(
                        "[SSF] ⚠️ No se encontró el "
                        f"canal {resultado['canal_id']} "
                        f"en {guild.name}."
                    )

                    continue

                # =============================================
                # EMBED
                # =============================================

                embed = discord.Embed(
                    title="🎯 SeptSinFP — Revisión diaria",
                    description=(
                        "Revisión correspondiente al "
                        f"**{fecha_a_revisar.strftime('%d/%m/%Y')}**."
                    ),
                )

                if eliminados:

                    nombres = []

                    for participante in eliminados:

                        nombres.append(
                            f"💀 **{participante['username']}**"
                        )

                    embed.add_field(
                        name=(
                            f"💀 Eliminados "
                            f"({len(eliminados)})"
                        ),
                        value="\n".join(nombres),
                        inline=False,
                    )

                    embed.add_field(
                        name="📋 Motivo",
                        value=(
                            "No registraron "
                            "**/ssf sobrevivi** durante el día."
                        ),
                        inline=False,
                    )

                else:

                    embed.add_field(
                        name="🟢 Resultado",
                        value=(
                            "No hubo eliminaciones. "
                            "Todos los participantes "
                            "registraron su supervivencia."
                        ),
                        inline=False,
                    )

                embed.set_footer(
                    text=(
                        f"Desafío: {resultado['nombre']}"
                    )
                )

                # =============================================
                # PUBLICAR
                # =============================================

                try:

                    await canal.send(
                        embed=embed
                    )

                    print(
                        "[SSF] 📢 Resumen publicado en "
                        f"#{canal.name} "
                        f"({guild.name})."
                    )

                except discord.Forbidden:

                    print(
                        "[SSF] ❌ No tengo permisos para "
                        f"escribir en #{canal.name}."
                    )

                except discord.HTTPException as error:

                    print(
                        "[SSF] ❌ Error enviando el resumen: "
                        f"{error}"
                    )

            # =================================================
            # CERRAR DESAFÍOS
            # =================================================

            try:

                cerrados = cerrar_desafios_finalizados(
                    ahora_actual.date()
                )

                if cerrados:

                    print(
                        "[SSF] 🔒 Desafíos finalizados cerrados: "
                        f"{cerrados}"
                    )

            except Exception as error:

                print(
                    "[SSF] ⚠️ Error cerrando desafíos "
                    f"finalizados: {error}"
                )

            # =================================================
            # MARCAR COMO PROCESADO
            # =================================================

            self.ssf_ultima_revision = fecha_a_revisar

            print(
                "[SSF] Revisión completada. "
                f"Fecha: {fecha_a_revisar}."
            )

        except Exception as error:

            print(
                "[SSF] ❌ Error durante la revisión "
                f"automática: {error}"
            )

    # ========================================================
    # ESPERAR CONEXIÓN
    # ========================================================

    @procesar_ssf_automatico.before_loop
    async def antes_de_procesar_ssf(self):

        await self.bot.wait_until_ready()

    @staticmethod
    def _canal_desafio(guild, canal_id):
        """Canal del desafío si acepta mensajes."""

        canal = guild.get_channel(canal_id)

        if isinstance(canal, discord.abc.Messageable):
            return canal

        return None

