"""Administración de SeptSinFP: revivir participantes e iniciar desafíos."""

from datetime import date

import discord
from discord import app_commands

from config import SSF_FECHA_FIN, SSF_FECHA_INICIO
from core.mensajes import responder, responder_texto
from commands.admin.base import solo_admin, solo_servidor
from core.utils import ahora
from modules.ssf.services import (
    agregar_dia,
    cerrar_desafio_activo,
    eliminar_participante_admin,
    iniciar_desafio,
    obtener_desafio_para_ranking,
    obtener_estado_desafio,
    obtener_estado_usuario,
    obtener_lista_participantes,
    quitar_dia,
    recalcular_rachas,
    revivir_participante,
)


class SsfAdminMixin:
    """Comandos administrativos de SeptSinFP bajo ``/admin ssf``."""

    # ========================================================
    # GRUPO SSF
    # ========================================================

    ssf = app_commands.Group(
        name="ssf",
        description="Comandos administrativos de SeptSinFP.",
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

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await responder_texto(interaction, "⚠️ La fecha no es válida.\n"
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

            await responder_texto(interaction, motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo revivir al participante.",
                ),
                ephemeral=True,
            )

            return

        await responder_texto(interaction, f"💚 **Participante revivido correctamente.**\n\n"
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
        fecha_inicio="Fecha de inicio en formato YYYY-MM-DD (por defecto la configurada).",
        fecha_fin="Fecha de fin en formato YYYY-MM-DD (por defecto la configurada).",
        nombre="Nombre del desafío (por defecto SeptSinFP <año>).",
    )
    async def ssf_iniciar(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        fecha_inicio: str = "",
        fecha_fin: str = "",
        nombre: str = "",
    ):
        """Inicia un nuevo desafío."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        fecha_inicio = fecha_inicio.strip() or SSF_FECHA_INICIO
        fecha_fin = fecha_fin.strip() or SSF_FECHA_FIN

        # ----------------------------------------------------
        # VALIDAR FECHAS
        # ----------------------------------------------------

        try:
            inicio_obj = date.fromisoformat(fecha_inicio)
            fin_obj = date.fromisoformat(fecha_fin)
        except ValueError:
            await responder_texto(interaction, "⚠️ Las fechas no son válidas.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-09-01`.",
                ephemeral=True,
            )
            return

        if inicio_obj > fin_obj:
            await responder_texto(interaction, "⚠️ La fecha de inicio no puede ser "
                "posterior a la fecha de fin.",
                ephemeral=True,
            )
            return

        fecha_inicio = inicio_obj.isoformat()
        fecha_fin = fin_obj.isoformat()

        nombre = nombre.strip() or f"SeptSinFP {inicio_obj.year}"

        resultado = iniciar_desafio(
            guild_id=interaction.guild.id,
            nombre=nombre,
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

            await responder_texto(interaction, mensaje,
                ephemeral=True,
            )

            return

        await responder_texto(interaction, f"🎯 **SeptSinFP iniciado correctamente.**\n\n"
            f"📋 Desafío: **{nombre}**\n"
            f"🗓️ Inicio: **{fecha_inicio}**\n"
            f"🏁 Fin: **{fecha_fin}**\n"
            f"📢 Canal: {canal.mention}\n"
            f"🆔 ID del desafío: "
            f"**{resultado['desafio_id']}**\n\n"
            f"Los participantes ya pueden utilizar "
            f"**/ssf registrar** en {canal.mention}."
        )

    # ========================================================
    # SSF - AGREGAR
    # ========================================================

    @ssf.command(
        name="agregar",
        description="Agrega manualmente un día sobrevivido a un participante.",
    )
    @app_commands.describe(
        usuario="Participante activo al que se le sumará el día.",
        fecha="Día a agregar, en formato YYYY-MM-DD.",
    )
    async def ssf_agregar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Agrega un día al registro de un participante."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await responder_texto(interaction, "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-09-01`.",
                ephemeral=True,
            )
            return

        resultado = agregar_dia(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            fecha=fecha_obj,
            hoy=ahora().date(),
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
                "eliminado": (
                    f"ℹ️ **{usuario.display_name}** "
                    "está eliminado.\n"
                    "Utiliza `/admin ssf revivir` para "
                    "devolverlo al juego."
                ),
                "futura": (
                    "⚠️ No se puede agregar un día futuro.\n"
                    f"Hoy es **{ahora().date().isoformat()}**."
                ),
                "ya_registrado": (
                    f"ℹ️ **{usuario.display_name}** "
                    f"ya tiene registrado el día **{fecha}**."
                ),
            }

            await responder_texto(interaction, motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo agregar el día.",
                ),
                ephemeral=True,
            )

            return

        await responder_texto(interaction, f"✅ **Día agregado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Día agregado: **{fecha}**\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n"
            f"🫡 Rango: **{resultado['rango']}**",
            ephemeral=True,
        )

    # ========================================================
    # SSF - QUITAR
    # ========================================================

    @ssf.command(
        name="quitar",
        description="Quita manualmente un día sobrevivido a un participante.",
    )
    @app_commands.describe(
        usuario="Participante al que se le quitará el día.",
        fecha="Día a quitar, en formato YYYY-MM-DD.",
    )
    async def ssf_quitar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Quita un día del registro de un participante."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            fecha_obj = date.fromisoformat(fecha)

        except ValueError:
            await responder_texto(interaction, "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-09-01`.",
                ephemeral=True,
            )
            return

        resultado = quitar_dia(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            fecha=fecha_obj,
        )

        if not resultado["exitoso"]:

            motivos = {
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "no_participante": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está registrado como participante "
                    "de SeptSinFP."
                ),
                "sin_registro": (
                    f"ℹ️ **{usuario.display_name}** "
                    f"no tiene registrado el día **{fecha}**."
                ),
            }

            await responder_texto(interaction, motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo quitar el día.",
                ),
                ephemeral=True,
            )

            return

        texto = (
            f"🗑️ **Día quitado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Día quitado: **{fecha}**\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n"
            f"🫡 Rango: **{resultado['rango']}**"
        )

        if resultado["eliminado"]:
            texto += (
                f"\n\n💀 **{usuario.display_name}** "
                "sigue eliminado."
            )

        await responder_texto(interaction, texto,
            ephemeral=True,
        )

    # ========================================================
    # SSF - RECALCULAR
    # ========================================================

    @ssf.command(
        name="recalcular",
        description="Recalcula las rachas de un participante desde sus registros.",
    )
    @app_commands.describe(
        usuario="Participante cuyas rachas quieres recalcular.",
    )
    async def ssf_recalcular(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Recalcula las rachas sin cambiar el estado de eliminado."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resultado = recalcular_rachas(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
        )

        if not resultado["exitoso"]:

            motivos = {
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "no_participante": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está registrado como participante "
                    "de SeptSinFP."
                ),
            }

            await responder_texto(interaction, motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudieron recalcular las rachas.",
                ),
                ephemeral=True,
            )

            return

        if resultado["eliminado"]:
            estado = "💀 Eliminado"
        else:
            estado = "🟢 Activo"

        await responder_texto(interaction, f"🔄 **Rachas recalculadas correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📊 Estado: **{estado}**\n"
            f"🔥 Racha actual: "
            f"**{resultado['racha']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n"
            f"🫡 Rango: **{resultado['rango']}**",
            ephemeral=True,
        )

    # ========================================================
    # SSF - ESTADO
    # ========================================================

    @ssf.command(
        name="estado",
        description="Muestra el estado SeptSinFP de cualquier usuario.",
    )
    @app_commands.describe(
        usuario="Usuario cuyo estado quieres consultar.",
    )
    async def ssf_estado(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Muestra el estado de un participante."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resultado = obtener_estado_usuario(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
        )

        if not resultado["exitoso"]:

            motivos = {
                "sin_desafio": (
                    "⚠️ No hay un desafío SeptSinFP activo."
                ),
                "no_participante": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está registrado como participante "
                    "de SeptSinFP."
                ),
            }

            await responder_texto(interaction, motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo obtener el estado.",
                ),
                ephemeral=True,
            )
            return

        secciones_ = [
            ("🫡 Rango", f"**{resultado['rango']}**"),
            ("🔥 Racha actual", f"**{resultado['racha_actual']} días**"),
            ("🏆 Mejor racha", f"**{resultado['mejor_racha']} días**"),
        ]

        if resultado["eliminado"]:
            secciones_.append(
                (
                    "💀 Eliminado",
                    f"El **{resultado['fecha_eliminacion']}**.",
                )
            )

        await responder(
            interaction,
            f"📊 Estado de {usuario.display_name} "
            f"en {resultado['nombre']}",
            color_area="ssf",
            ephemeral=True,
            secciones_=secciones_,
        )

    # ========================================================
    # SSF - DESAFIO
    # ========================================================

    @ssf.command(
        name="desafio",
        description="Muestra el estado global del desafío SeptSinFP activo.",
    )
    async def ssf_desafio(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el estado del desafío activo."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        estado = obtener_estado_desafio(
            interaction.guild.id,
        )

        if estado is None:
            await responder_texto(interaction, "⚠️ No hay un desafío "
                "SeptSinFP activo en este servidor.",
                ephemeral=True,
            )
            return

        canal = interaction.guild.get_channel(estado["canal_id"])

        canal_texto = (
            canal.mention
            if isinstance(canal, discord.TextChannel)
            else f"`{estado['canal_id']}`"
        )

        await responder(
            interaction,
            f"📋 {estado['nombre']}",
            color_area="ssf",
            ephemeral=True,
            secciones_=[
                ("🆔 ID", f"`{estado['id']}`"),
                ("🗓️ Período", f"`{estado['fecha_inicio']}` → `{estado['fecha_fin']}`"),
                ("📢 Canal", canal_texto),
                ("👥 Participantes", f"**{estado['total']}** en total"),
                ("🟢 Activos", f"**{estado['activos']}**"),
                ("💀 Eliminados", f"**{estado['eliminados']}**"),
            ],
        )

    # ========================================================
    # SSF - PARTICIPANTES
    # ========================================================

    @ssf.command(
        name="participantes",
        description="Lista los participantes del desafío con sus rachas.",
    )
    async def ssf_participantes(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra la lista completa de participantes."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        estado = obtener_estado_desafio(
            interaction.guild.id,
        )

        if estado is None:
            await responder_texto(interaction, "⚠️ No hay un desafío "
                "SeptSinFP activo en este servidor.",
                ephemeral=True,
            )
            return

        lista = obtener_lista_participantes(
            interaction.guild.id,
        )

        if not lista:
            await responder_texto(interaction, "ℹ️ Todavía no hay "
                "participantes registrados.",
                ephemeral=True,
            )
            return

        limite = 20
        visibles = lista[:limite]
        restantes = len(lista) - len(visibles)

        lineas = []

        for participante in visibles:
            (
                _user_id,
                username,
                _fecha_registro,
                eliminado,
                _fecha_eliminacion,
                racha_actual,
                mejor_racha,
            ) = participante

            estado_emoji = "💀" if eliminado else "🟢"

            lineas.append(
                f"{estado_emoji} **{username}** — "
                f"🔥 {racha_actual} días — "
                f"🏆 {mejor_racha} máx."
            )

        if restantes:
            lineas.append(f"… y **{restantes} más**")

        await responder(
            interaction,
            f"📋 Participantes de {estado['nombre']}",
            f"{estado['activos']} activos, "
            f"{estado['eliminados']} eliminados.",
            color_area="ssf",
            ephemeral=True,
            secciones_=[
                ("Listado", "\n".join(lineas), False),
            ],
        )

    # ========================================================
    # SSF - ELIMINAR
    # ========================================================

    @ssf.command(
        name="eliminar",
        description="Marca eliminado a un participante que no registró un día.",
    )
    @app_commands.describe(
        usuario="Participante activo que quieres eliminar.",
        fecha="Día que no registró, en formato YYYY-MM-DD.",
    )
    async def ssf_eliminar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        fecha: str,
    ):
        """Elimina manualmente a un participante faltante."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        try:
            fecha_obj = date.fromisoformat(fecha)
        except ValueError:
            await responder_texto(interaction, "⚠️ La fecha no es válida.\n"
                "Utiliza el formato **YYYY-MM-DD**.\n"
                "Ejemplo: `2026-09-01`.",
                ephemeral=True,
            )
            return

        resultado = eliminar_participante_admin(
            guild_id=interaction.guild.id,
            user_id=usuario.id,
            fecha=fecha_obj,
            hoy=ahora().date(),
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
                "futura": (
                    "⚠️ No se puede eliminar por un día futuro.\n"
                    f"Hoy es **{ahora().date().isoformat()}**."
                ),
                "no_participante": (
                    f"ℹ️ **{usuario.display_name}** "
                    "no está registrado como participante "
                    "de SeptSinFP."
                ),
                "ya_eliminado": (
                    f"ℹ️ **{usuario.display_name}** "
                    "ya está eliminado."
                ),
                "con_registro": (
                    f"ℹ️ **{usuario.display_name}** "
                    f"tiene registrado el día **{fecha}**.\n"
                    "Para eliminarlo por ese día, primero "
                    "usá `/admin ssf quitar` para sacarle "
                    "el registro."
                ),
            }

            await responder_texto(interaction, motivos.get(
                    resultado["motivo"],
                    "⚠️ No se pudo eliminar al participante.",
                ),
                ephemeral=True,
            )
            return

        await responder_texto(interaction, f"💀 **Participante eliminado correctamente.**\n\n"
            f"👤 Usuario: **{usuario.display_name}**\n"
            f"📅 Día faltado: **{fecha}**\n"
            f"🔥 Racha previa: "
            f"**{resultado['racha_actual']} días**\n"
            f"🏆 Mejor racha: "
            f"**{resultado['mejor_racha']} días**\n\n"
            f"Si fue un error, podés revivirlo con "
            f"**/admin ssf revivir**.",
            ephemeral=True,
        )

    # ========================================================
    # SSF - CERRAR
    # ========================================================

    @ssf.command(
        name="cerrar",
        description="Cierra el desafío SeptSinFP activo y muestra el resultado.",
    )
    @app_commands.describe(
        confirmar="Confirma el cierre del desafío.",
    )
    @app_commands.choices(
        confirmar=[
            app_commands.Choice(name="SI", value="SI"),
            app_commands.Choice(name="NO", value="NO"),
        ]
    )
    async def ssf_cerrar(
        self,
        interaction: discord.Interaction,
        confirmar: app_commands.Choice[str],
    ):
        """Cierra el desafío activo."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        if confirmar.value != "SI":
            await responder_texto(interaction, "🛑 Operación cancelada. "
                "No se cerró ningún desafío.",
                ephemeral=True,
            )
            return

        resultado = cerrar_desafio_activo(
            interaction.guild.id,
        )

        if not resultado["exitoso"]:
            await responder_texto(interaction, "⚠️ No hay un desafío "
                "SeptSinFP activo para cerrar.",
                ephemeral=True,
            )
            return

        sobrevivientes = len(resultado["sobrevivientes"])
        eliminados = len(resultado["eliminados"])

        await responder_texto(interaction, f"🔒 **Desafío cerrado correctamente.**\n\n"
            f"📋 Desafío: **{resultado['nombre']}**\n"
            f"🗓️ Período: `{resultado['fecha_inicio']}` → "
            f"`{resultado['fecha_fin']}`\n"
            f"👥 Total: **{resultado['total']}**\n"
            f"🏆 Sobrevivientes: **{sobrevivientes}**\n"
            f"💀 Eliminados: **{eliminados}**\n\n"
            f"Usá **/admin ssf ranking** para ver el ranking final.",
            ephemeral=True,
        )

    # ========================================================
    # SSF - RANKING
    # ========================================================

    @ssf.command(
        name="ranking",
        description="Muestra el ranking final del desafío activo o del último.",
    )
    async def ssf_ranking(
        self,
        interaction: discord.Interaction,
    ):
        """Muestra el ranking del desafío."""

        if not await solo_admin(interaction):
            return

        if not await solo_servidor(interaction):
            return

        resultado = obtener_desafio_para_ranking(
            interaction.guild.id,
        )

        if resultado is None:
            await responder_texto(interaction, "ℹ️ Todavía no hay "
                "desafíos SeptSinFP en este servidor.",
                ephemeral=True,
            )
            return

        ranking = resultado["ranking"]

        if not ranking:
            await responder_texto(interaction, "ℹ️ El desafío "
                f"**{resultado['nombre']}** no tiene participantes.",
                ephemeral=True,
            )
            return

        medallas = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        limite = 15
        visibles = ranking[:limite]
        restantes = len(ranking) - len(visibles)

        lineas = []

        for posicion, fila in enumerate(visibles, start=1):
            username, eliminado, racha_actual, mejor_racha = (
                fila[1],
                fila[2],
                fila[3],
                fila[4],
            )

            medalla = medallas.get(
                posicion,
                f"**{posicion}.**",
            )

            estado_emoji = "💀" if eliminado else "🟢"

            lineas.append(
                f"{medalla} {estado_emoji} **{username}** — "
                f"🔥 {racha_actual} días — "
                f"🏆 {mejor_racha} máx."
            )

        if restantes:
            lineas.append(f"… y **{restantes} más**")

        estado_titulo = (
            "en curso"
            if resultado["activo"]
            else "finalizado"
        )

        await responder(
            interaction,
            f"🏆 Ranking de {resultado['nombre']} ({estado_titulo})",
            color_area="ssf",
            ephemeral=True,
            secciones_=[
                ("Ranking", "\n".join(lineas), False),
            ],
        )
