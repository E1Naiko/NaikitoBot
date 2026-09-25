"""Administración del canal 420: importar historial, altas y bajas manuales."""

import asyncio
from datetime import date, datetime, time

import discord
from discord import app_commands

import config
from commands.admin.base import solo_admin, solo_servidor
from core.mensajes import crear_embed, responder, responder_texto
from core.utils import ahora
from modules.lahora.logic import texto_ventanas
from modules.lahora.services import (
    agregar_manual,
    borrar_dia,
    borrar_servidor,
    borrar_usuario,
    importar_mensajes,
    obtener_estadisticas_servidor,
    obtener_registros_usuario,
)

# Una importación recorre todo el historial del canal y puede tardar
# minutos: se permite una sola a la vez.
_importando = asyncio.Lock()

# Cada cuántos mensajes revisados se actualiza el mensaje de progreso.
PROGRESO_CADA = 1000

OPCIONES_VENTANA = [
    app_commands.Choice(name=hora.strftime("%H:%M"), value=hora.strftime("%H:%M"))
    for hora in config.LAHORA_HORAS
]


def _parsear_fecha(texto: str) -> date | None:
    try:
        return datetime.strptime(texto.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parsear_hora(texto: str) -> time | None:
    for formato in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(texto.strip(), formato).time()
        except ValueError:
            continue

    return None


def _texto_resumen(resumen, errores, terminado: bool) -> str:
    lineas = [
        f"📨 Mensajes revisados: **{resumen.revisados}**",
        f"🌿 420 detectados: **{resumen.detectados}**",
        f"✅ Importados: **{resumen.importados}**",
    ]

    if terminado:
        lineas += [
            f"🔁 Ya registrados o repetidos: **{resumen.repetidos}**",
            f"⏰ Fuera de horario: **{resumen.fuera_de_horario}**",
            f"✏️ Editados después de la ventana: **{resumen.editados}**",
        ]

        if resumen.primero and resumen.ultimo:
            lineas.append(
                f"📅 Rango importado: **{resumen.primero:%d/%m/%Y}** a "
                f"**{resumen.ultimo:%d/%m/%Y}**"
            )

    if errores:
        lineas.append("")
        lineas += [f"⚠️ {error}" for error in errores]

    return "\n".join(lineas)[:4000]


class LaHoraAdminMixin:
    """Comandos administrativos del canal 420 bajo ``/admin 420``."""

    lahora = app_commands.Group(
        name="420",
        description="Administración del canal 420.",
    )

    # ========================================================
    # IMPORTAR HISTORIAL
    # ========================================================

    @lahora.command(
        name="importar",
        description="Importa los 420 que ya están en el historial del canal.",
    )
    @app_commands.describe(
        canal="Canal a recorrer (por defecto, los de LAHORA_CANALES_ID).",
        desde="Solo mensajes desde esta fecha (YYYY-MM-DD). Por defecto, todo.",
    )
    async def lahora_importar(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel | None = None,
        desde: str | None = None,
    ):
        """Recorre el historial y registra los 420 con las reglas de siempre."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        desde_dt = None

        if desde:
            fecha_desde = _parsear_fecha(desde)

            if fecha_desde is None:
                await responder_texto(
                    interaction,
                    "❌ Fecha inválida. Usá el formato **YYYY-MM-DD**.\n\n"
                    "Ejemplo: `2026-08-01`",
                    ephemeral=True,
                )
                return

            desde_dt = datetime.combine(
                fecha_desde,
                time(0, 0),
                tzinfo=config.TIMEZONE,
            )

        if canal is not None:
            canales = [canal]
        else:
            canales = []

            for canal_id in sorted(config.LAHORA_CANALES_ID):
                encontrado = interaction.guild.get_channel(canal_id)

                if encontrado is None:
                    try:
                        encontrado = await self.bot.fetch_channel(canal_id)
                    except discord.HTTPException:
                        encontrado = None

                if encontrado is not None:
                    canales.append(encontrado)

        if not canales:
            await responder_texto(
                interaction,
                "⚠️ No hay canal 420 para recorrer. Configurá "
                "`LAHORA_CANALES_ID` o indicá el `canal`.",
                ephemeral=True,
            )
            return

        if _importando.locked():
            await responder_texto(
                interaction,
                "⏳ Ya hay una importación en curso. Esperá a que termine.",
                ephemeral=True,
            )
            return

        async with _importando:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)

            errores: list[str] = []
            nombres = ", ".join(f"<#{c.id}>" for c in canales)

            async def historial():
                for actual in canales:
                    try:
                        async for mensaje in actual.history(
                            limit=None,
                            after=desde_dt,
                            oldest_first=True,
                        ):
                            yield mensaje
                    except discord.Forbidden:
                        errores.append(
                            f"<#{actual.id}>: el bot no tiene permiso para "
                            "leer el historial."
                        )
                    except discord.HTTPException as error:
                        errores.append(
                            f"<#{actual.id}>: Discord cortó la lectura "
                            f"({error}). Lo leído hasta ahí quedó importado."
                        )

            async def progreso(resumen):
                # Si la edición falla (por ejemplo, el token de la
                # interacción venció a los 15 minutos) se sigue igual.
                try:
                    await interaction.edit_original_response(
                        embed=crear_embed(
                            "⏳ Importando 420…",
                            f"Recorriendo {nombres}.\n\n"
                            + _texto_resumen(resumen, errores, False),
                            color_area="lahora",
                        )
                    )
                except discord.HTTPException:
                    pass

            print(f"[420] importación iniciada canales={nombres}", flush=True)

            resumen = await importar_mensajes(
                interaction.guild.id,
                historial(),
                al_progresar=progreso,
                cada=PROGRESO_CADA,
            )

            print(
                f"[420] importación terminada revisados={resumen.revisados} "
                f"importados={resumen.importados} repetidos={resumen.repetidos}",
                flush=True,
            )

            embed = crear_embed(
                "✅ Importación terminada" if not errores else "⚠️ Importación con avisos",
                f"Canales: {nombres}\n\n" + _texto_resumen(resumen, errores, True),
                color_area="lahora" if not errores else "aviso",
            )

            # Una importación larga puede superar los 15 minutos del token:
            # si ya no se puede responder, el resumen llega por MD.
            try:
                await interaction.edit_original_response(embed=embed)
            except discord.HTTPException:
                try:
                    await interaction.user.send(embed=embed)
                except discord.HTTPException:
                    pass

    # ========================================================
    # ALTA MANUAL
    # ========================================================

    @lahora.command(
        name="manualadd",
        description="Registra a mano un 420 de un usuario.",
    )
    @app_commands.describe(
        usuario="Usuario al que se le agregará el 420.",
        fecha="Fecha en formato YYYY-MM-DD.",
        hora="Hora del 420 en formato HH:MM:SS (o HH:MM, segundo 0).",
    )
    async def lahora_manualadd(
        self,
        interaction: discord.Interaction,
        usuario: discord.User,
        fecha: str,
        hora: str,
    ):
        """Agrega un 420 con las mismas reglas que el registro automático."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        fecha_obj = _parsear_fecha(fecha)

        if fecha_obj is None:
            await responder_texto(
                interaction,
                "❌ Fecha inválida. Usá el formato **YYYY-MM-DD**.\n\n"
                "Ejemplo: `2026-09-25`",
                ephemeral=True,
            )
            return

        hora_obj = _parsear_hora(hora)

        if hora_obj is None:
            await responder_texto(
                interaction,
                "❌ Hora inválida. Usá el formato **HH:MM:SS** o **HH:MM**.\n\n"
                "Ejemplo: `16:20:15`",
                ephemeral=True,
            )
            return

        momento = datetime.combine(fecha_obj, hora_obj, tzinfo=config.TIMEZONE)

        if momento > ahora():
            await responder_texto(
                interaction,
                "❌ No podés registrar un 420 en el futuro.",
                ephemeral=True,
            )
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        resultado = await agregar_manual(
            interaction.guild.id,
            usuario.id,
            usuario.display_name,
            momento,
        )

        if resultado.motivo == "fuera_de_horario":
            await responder(
                interaction,
                "❌ Fuera de horario",
                f"Las **{hora_obj:%H:%M:%S}** no caen en ninguna ventana.",
                color_area="error",
                ephemeral=True,
                secciones_=[("⏰ Horarios válidos", texto_ventanas())],
            )
            return

        if resultado.motivo == "ya_registrado":
            await responder_texto(
                interaction,
                f"ℹ️ **{usuario.display_name}** ya tiene un 420 el "
                f"**{fecha_obj:%d/%m/%Y}** en la ventana de las "
                f"**{resultado.ventana}**. Si querés cambiarlo, borralo con "
                "`/admin 420 resetdia` y volvé a agregarlo.",
                ephemeral=True,
            )
            return

        await responder(
            interaction,
            "✅ 420 registrado",
            f"Se agregó el 420 de **{usuario.display_name}**.",
            color_area="lahora",
            ephemeral=True,
            secciones_=[
                ("📅 Fecha", f"**{fecha_obj:%d/%m/%Y}**", True),
                ("🕓 Ventana", f"**{resultado.ventana}**", True),
                ("⏱️ Segundo", f"**{resultado.segundos}**", True),
                ("🏅 Posición", f"**{resultado.posicion}**", True),
                ("🏆 Puntos", f"**{resultado.puntos_finales:.1f}**", True),
            ],
        )

    # ========================================================
    # BORRAR UN DÍA / UNA VENTANA
    # ========================================================

    @lahora.command(
        name="resetdia",
        description="Borra los 420 de un usuario en una fecha (o solo una ventana).",
    )
    @app_commands.describe(
        usuario="Usuario cuyos 420 querés borrar.",
        fecha="Fecha en formato YYYY-MM-DD.",
        ventana="Solo esta ventana (por defecto, todas las del día).",
    )
    @app_commands.choices(ventana=OPCIONES_VENTANA)
    async def lahora_resetdia(
        self,
        interaction: discord.Interaction,
        usuario: discord.User,
        fecha: str,
        ventana: app_commands.Choice[str] | None = None,
    ):
        """Borra registros y reordena las ventanas afectadas."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        fecha_obj = _parsear_fecha(fecha)

        if fecha_obj is None:
            await responder_texto(
                interaction,
                "❌ Fecha inválida. Usá el formato **YYYY-MM-DD**.",
                ephemeral=True,
            )
            return

        valor_ventana = ventana.value if ventana is not None else None
        borrados = await borrar_dia(
            interaction.guild.id,
            usuario.id,
            fecha_obj,
            valor_ventana,
        )

        donde = (
            f"en la ventana de las **{valor_ventana}**"
            if valor_ventana
            else "ese día"
        )

        if borrados == 0:
            await responder_texto(
                interaction,
                f"ℹ️ **{usuario.display_name}** no tiene 420 el "
                f"**{fecha_obj:%d/%m/%Y}** {donde}.",
                ephemeral=True,
            )
            return

        await responder_texto(
            interaction,
            f"🗑️ Se borraron **{borrados}** 420 de **{usuario.display_name}** "
            f"el **{fecha_obj:%d/%m/%Y}** {donde}. Las posiciones de esa "
            "ventana se recalcularon.",
            ephemeral=True,
        )

    # ========================================================
    # VER USUARIO
    # ========================================================

    @lahora.command(
        name="ver",
        description="Muestra los últimos 420 registrados de un usuario.",
    )
    @app_commands.describe(usuario="Usuario a consultar.")
    async def lahora_ver(
        self,
        interaction: discord.Interaction,
        usuario: discord.User,
    ):
        """Lista los últimos 20 registros del usuario."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        registros = await obtener_registros_usuario(
            interaction.guild.id,
            usuario.id,
            limite=20,
        )

        if not registros:
            await responder_texto(
                interaction,
                f"ℹ️ **{usuario.display_name}** no tiene 420 registrados.",
                ephemeral=True,
            )
            return

        lineas = [
            f"`{fecha:%d/%m/%Y}` **{ventana}** · {segundos} s · "
            f"#{posicion} · **{puntos:.1f} pts**"
            + ("" if mensaje_id else " · ✍️ manual")
            for fecha, ventana, segundos, posicion, puntos, mensaje_id in registros
        ]

        await responder(
            interaction,
            f"🌿 420 de {usuario.display_name}",
            "\n".join(lineas),
            color_area="lahora",
            ephemeral=True,
            pie="Últimos 20 registros",
        )

    # ========================================================
    # BORRAR USUARIO
    # ========================================================

    @lahora.command(
        name="resetusuario",
        description="Borra todos los 420 de un usuario.",
    )
    @app_commands.describe(usuario="Usuario cuyos 420 querés borrar.")
    async def lahora_resetusuario(
        self,
        interaction: discord.Interaction,
        usuario: discord.User,
    ):
        """Borra todos los registros del usuario."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        borrados = await borrar_usuario(interaction.guild.id, usuario.id)

        if borrados == 0:
            await responder_texto(
                interaction,
                f"ℹ️ **{usuario.display_name}** no tiene 420 registrados.",
                ephemeral=True,
            )
            return

        await responder_texto(
            interaction,
            f"🗑️ Se borraron **{borrados}** 420 de **{usuario.display_name}**. "
            "Las posiciones de sus ventanas se recalcularon.",
            ephemeral=True,
        )

    # ========================================================
    # BORRAR TODO
    # ========================================================

    @lahora.command(
        name="resettotal",
        description="Borra todos los 420 del servidor.",
    )
    @app_commands.describe(confirmar="Confirma el borrado total.")
    @app_commands.choices(
        confirmar=[
            app_commands.Choice(name="SI", value="SI"),
            app_commands.Choice(name="NO", value="NO"),
        ]
    )
    async def lahora_resettotal(
        self,
        interaction: discord.Interaction,
        confirmar: app_commands.Choice[str],
    ):
        """Borra todos los registros del servidor si se confirma."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        if confirmar.value != "SI":
            await responder_texto(
                interaction,
                "🛑 Operación cancelada. No se borró ningún 420.",
                ephemeral=True,
            )
            return

        usuarios, registros, puntos = await obtener_estadisticas_servidor(
            interaction.guild.id,
        )
        borrados = await borrar_servidor(interaction.guild.id)

        await responder_texto(
            interaction,
            f"🗑️ Se borraron **{borrados}** 420 de **{usuarios}** usuarios "
            f"(**{float(puntos):.1f}** puntos). Podés volver a cargarlos con "
            "`/admin 420 importar`.",
            ephemeral=True,
        )

    # ========================================================
    # STATS
    # ========================================================

    @lahora.command(
        name="stats",
        description="Muestra las estadísticas del canal 420 del servidor.",
    )
    async def lahora_stats(
        self,
        interaction: discord.Interaction,
    ):
        """Totales del servidor."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        usuarios, registros, puntos = await obtener_estadisticas_servidor(
            interaction.guild.id,
        )

        await responder(
            interaction,
            "📊 Estadísticas del canal 420",
            color_area="lahora",
            ephemeral=True,
            secciones_=[
                ("👥 Usuarios", f"**{usuarios}**", True),
                ("🌿 420 registrados", f"**{registros}**", True),
                ("🏆 Puntos repartidos", f"**{float(puntos):.1f}**", True),
            ],
        )
