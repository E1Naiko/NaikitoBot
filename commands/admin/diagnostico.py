"""Diagnóstico operativo seguro para los comandos y subsistemas del bot."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from time import perf_counter

import discord
from discord import app_commands
from sqlalchemy import text

from commands.admin.base import solo_admin, solo_servidor
from config import (
    BOX_CHANNEL_IDS,
    BOX_COMBATE_ACTIVO,
    GENERAL_CHANNEL_IDS,
    GUILD_ID,
    LAHORA_CANALES_ID,
    MADRUGUE_CHANNEL_IDS,
    SSF_CANALES_ID,
)
from core.database import crear_sesion
from core.mensajes import responder
from modules.box.services import obtener_estado_box, obtener_saldo
from modules.madrugue.services import obtener_stats_madrugue
from modules.ssf.services import obtener_estado_desafio

ESTADO_OK = "ok"
ESTADO_AVISO = "aviso"
ESTADO_ERROR = "error"

ICONOS_ESTADO = {
    ESTADO_OK: "✅",
    ESTADO_AVISO: "⚠️",
    ESTADO_ERROR: "❌",
}

# Permisos que el bot necesita en cada canal configurado. En el canal 420
# además confirma cada registro con una reacción y necesita leer el
# contenido de los mensajes.
PERMISOS_CANAL = ("view_channel", "send_messages", "embed_links")
PERMISOS_POR_AREA = {
    "420": PERMISOS_CANAL + ("read_message_history", "add_reactions"),
}

# Manifiesto de comandos hoja que debe exponer esta versión. Además de detectar
# callbacks rotos, permite avisar si una extensión no cargó o si una
# sincronización dejó afuera un comando completo.
COMANDOS_ESPERADOS = frozenset(
    {
        "ping",
        "madrugue",
        "madrugue_stats",
        "madrugue_top",
        "madrugue_ayuda",
        "420_stats",
        "420_top",
        "420_hoy",
        "420_ayuda",
        "admin test",
        "admin info",
        "admin fileexecute",
        "admin stats",
        "admin top",
        "admin ver",
        "admin resetdia",
        "admin resetusuario",
        "admin resettotal",
        "admin manualadd",
        "admin madrugue stats",
        "admin madrugue top",
        "admin madrugue ver",
        "admin madrugue resetdia",
        "admin madrugue resetusuario",
        "admin madrugue resettotal",
        "admin madrugue manualadd",
        "admin 420 importar",
        "admin 420 manualadd",
        "admin 420 resetdia",
        "admin 420 ver",
        "admin 420 resetusuario",
        "admin 420 resettotal",
        "admin 420 stats",
        "admin ssf revivir",
        "admin ssf iniciar",
        "admin ssf agregar",
        "admin ssf quitar",
        "admin ssf recalcular",
        "admin ssf estado",
        "admin ssf desafio",
        "admin ssf participantes",
        "admin ssf eliminar",
        "admin ssf cerrar",
        "admin ssf ranking",
        "admin box info",
        "admin box dar_dinero",
        "admin box sponsors",
        "admin box dar_exp",
        "admin box curar",
        "admin box probabilidad",
        "admin box cancelar",
        "admin box dar_sponsor",
        "admin box quitar_sponsor",
        "admin box reset",
        "admin box top",
        "admin box stats",
        "admin box historial",
        "admin box lesionados",
        "admin box finalizar",
        "admin box procesar",
        "admin box canticos",
        "admin box cerrar_combate",
        "ssf ayuda",
        "ssf estado",
        "ssf participantes",
        "ssf registrar",
        "ssf sobrevivi",
        "box tienda",
        "box comprar",
        "box tratamiento",
        "box suministro",
        "box combate",
        "box ayuda",
        "box saldo",
        "box stats",
        "box equipo",
        "box topdesafios",
        "box cancelar",
        "box sparring",
        "box desafio",
        "box entrenar",
        "box trabajar",
        "box promoverme",
        "box descanso",
    }
)


@dataclass(frozen=True)
class Comprobacion:
    """Resultado presentable de una parte del diagnóstico."""

    nombre: str
    estado: str
    detalle: str

    @property
    def titulo(self) -> str:
        return f"{ICONOS_ESTADO[self.estado]} {self.nombre}"


class DiagnosticoMixin:
    """Comando administrativo de diagnóstico no destructivo."""

    def _diagnosticar_arbol(self) -> Comprobacion:
        comandos = list(self.bot.tree.walk_commands())
        hojas = {
            comando.qualified_name
            for comando in comandos
            if isinstance(comando, app_commands.Command)
        }
        callbacks_invalidos = sorted(
            comando.qualified_name
            for comando in comandos
            if isinstance(comando, app_commands.Command)
            and not callable(getattr(comando, "callback", None))
        )
        faltantes = sorted(COMANDOS_ESPERADOS - hojas)
        adicionales = sorted(hojas - COMANDOS_ESPERADOS)

        problemas = []
        if faltantes:
            problemas.append("Faltan: " + ", ".join(f"`/{ruta}`" for ruta in faltantes))
        if callbacks_invalidos:
            problemas.append(
                "Sin callback: "
                + ", ".join(f"`/{ruta}`" for ruta in callbacks_invalidos)
            )

        if problemas:
            return Comprobacion(
                "Árbol de comandos",
                ESTADO_ERROR,
                f"Se encontraron **{len(hojas)}** comandos hoja. "
                + "\n".join(problemas),
            )

        if adicionales:
            return Comprobacion(
                "Árbol de comandos",
                ESTADO_AVISO,
                f"Los **{len(COMANDOS_ESPERADOS)}** comandos esperados están cargados, "
                "pero el manifiesto no incluye: "
                + ", ".join(f"`/{ruta}`" for ruta in adicionales),
            )

        return Comprobacion(
            "Árbol de comandos",
            ESTADO_OK,
            f"Los **{len(hojas)}** comandos esperados están cargados y tienen callback.",
        )

    def _diagnosticar_discord(self, interaction: discord.Interaction) -> Comprobacion:
        problemas = []
        avisos = []

        if self.bot.user is None:
            problemas.append("el cliente no tiene usuario autenticado")

        latencia = self.bot.latency
        latencia_disponible = math.isfinite(latencia) and latencia >= 0
        latencia_ms = round(latencia * 1000) if latencia_disponible else None
        if not latencia_disponible:
            avisos.append("latencia del gateway no disponible")

        if not self.bot.intents.members:
            avisos.append("intent de miembros desactivado")
        if not self.bot.intents.message_content:
            avisos.append("intent de contenido desactivado")

        guild_id = getattr(
            interaction,
            "guild_id",
            getattr(interaction.guild, "id", None),
        )
        if GUILD_ID and guild_id != GUILD_ID:
            avisos.append(
                f"servidor actual `{guild_id}` distinto de GUILD_ID `{GUILD_ID}`"
            )

        if problemas:
            return Comprobacion(
                "Discord",
                ESTADO_ERROR,
                "; ".join(problemas + avisos),
            )

        detalle = (
            f"Gateway conectado · latencia **{latencia_ms} ms**."
            if latencia_ms is not None
            else "Gateway conectado · latencia no disponible."
        )
        if avisos:
            detalle += " Avisos: " + "; ".join(avisos) + "."
            return Comprobacion("Discord", ESTADO_AVISO, detalle)

        return Comprobacion("Discord", ESTADO_OK, detalle)

    async def _diagnosticar_base(self) -> Comprobacion:
        async with crear_sesion() as sesion:
            valor = (await sesion.execute(text("SELECT 1"))).scalar_one()

        if valor != 1:
            raise RuntimeError(f"SELECT 1 devolvió {valor!r}")

        return Comprobacion(
            "Base de datos",
            ESTADO_OK,
            "Conexión y consulta básica correctas.",
        )

    async def _diagnosticar_box(self, guild_id: int, user_id: int) -> Comprobacion:
        experiencia, dinero = await obtener_saldo(guild_id, user_id)
        probabilidad, _lesionado_hasta = await obtener_estado_box(guild_id, user_id)
        return Comprobacion(
            "Box",
            ESTADO_OK,
            "Consultas de solo lectura correctas · "
            f"EXP **{experiencia}**, dinero **{dinero}$**, lesión **{probabilidad:.2f}%**.",
        )

    async def _diagnosticar_madrugue(
        self,
        guild_id: int,
        user_id: int,
    ) -> Comprobacion:
        estadisticas = await obtener_stats_madrugue(guild_id, user_id)
        return Comprobacion(
            "Madrugue",
            ESTADO_OK,
            "Consultas de solo lectura correctas · "
            f"puntos **{estadisticas['total_puntos']:.1f}**, "
            f"mejor racha **{estadisticas['mejor_racha']}**.",
        )

    async def _diagnosticar_ssf(self, guild_id: int) -> Comprobacion:
        estado = await obtener_estado_desafio(guild_id)
        detalle = (
            "Consulta correcta · desafío activo disponible."
            if estado is not None
            else "Consulta correcta · no hay desafío activo."
        )
        return Comprobacion("SeptSinFP", ESTADO_OK, detalle)

    async def _diagnosticar_canales(
        self,
        interaction: discord.Interaction,
    ) -> Comprobacion:
        por_area = {
            "general": GENERAL_CHANNEL_IDS,
            "Madrugue": MADRUGUE_CHANNEL_IDS,
            "420": LAHORA_CANALES_ID,
            "Box": BOX_CHANNEL_IDS,
            "SeptSinFP": SSF_CANALES_ID,
        }
        sin_configurar = [area for area, ids in por_area.items() if not ids]
        errores = []
        verificados = 0

        for area, ids in por_area.items():
            for canal_id in sorted(ids):
                canal = self.bot.get_channel(canal_id)
                if canal is None and interaction.guild is not None:
                    canal = interaction.guild.get_channel(canal_id)

                if canal is None:
                    try:
                        canal = await self.bot.fetch_channel(canal_id)
                    except Exception as error:
                        errores.append(
                            f"{area} `<#{canal_id}>`: {type(error).__name__}"
                        )
                        continue

                if not callable(getattr(canal, "send", None)):
                    errores.append(f"{area} `<#{canal_id}>`: no permite mensajes")
                    continue

                verificados += 1

                permissions_for = getattr(canal, "permissions_for", None)
                guild = getattr(canal, "guild", None)
                miembro_bot = getattr(guild, "me", None)
                if miembro_bot is None and self.bot.user is not None and guild is not None:
                    get_member = getattr(guild, "get_member", None)
                    if callable(get_member):
                        miembro_bot = get_member(self.bot.user.id)

                if not callable(permissions_for) or miembro_bot is None:
                    errores.append(
                        f"{area} `<#{canal_id}>`: no se pudieron inspeccionar permisos"
                    )
                    continue

                permisos = permissions_for(miembro_bot)
                faltan = [
                    nombre
                    for nombre in PERMISOS_POR_AREA.get(area, PERMISOS_CANAL)
                    if not getattr(permisos, nombre, False)
                ]
                if faltan:
                    errores.append(
                        f"{area} `<#{canal_id}>`: faltan " + ", ".join(faltan)
                    )

        if errores:
            return Comprobacion(
                "Canales y permisos",
                ESTADO_ERROR,
                "; ".join(errores),
            )

        detalle = f"**{verificados}** canales configurados y accesibles."
        if sin_configurar:
            detalle += " Sin configurar: " + ", ".join(sin_configurar) + "."
            return Comprobacion("Canales y permisos", ESTADO_AVISO, detalle)

        return Comprobacion("Canales y permisos", ESTADO_OK, detalle)

    def _diagnosticar_tareas(self) -> Comprobacion:
        esperadas = {
            "Box": (
                "comprobar_acciones",
                "reducir_probabilidad_lesion",
            ),
            "Ssf": ("procesar_ssf_automatico",),
        }
        detenidas = []
        activas = 0

        for cog_nombre, tareas in esperadas.items():
            cog = self.bot.get_cog(cog_nombre)
            if cog is None:
                detenidas.append(f"cog `{cog_nombre}` no cargado")
                continue

            for tarea_nombre in tareas:
                tarea = getattr(cog, tarea_nombre, None)
                if tarea is None or not tarea.is_running():
                    detenidas.append(f"`{cog_nombre}.{tarea_nombre}`")
                else:
                    activas += 1

        box = self.bot.get_cog("Box")
        if BOX_COMBATE_ACTIVO:
            narrador = getattr(box, "narrar_combates", None) if box else None
            if narrador is None or not narrador.is_running():
                detenidas.append("`Box.narrar_combates`")
            else:
                activas += 1

        if detenidas:
            return Comprobacion(
                "Tareas automáticas",
                ESTADO_ERROR,
                "Detenidas o ausentes: " + ", ".join(detenidas) + ".",
            )

        detalle = f"**{activas}** tareas periódicas activas."
        if not BOX_COMBATE_ACTIVO:
            detalle += " Narración desactivada por configuración."
        return Comprobacion("Tareas automáticas", ESTADO_OK, detalle)

    @staticmethod
    def _error_aislado(nombre: str, error: Exception) -> Comprobacion:
        detalle = str(error).strip() or type(error).__name__
        if len(detalle) > 500:
            detalle = detalle[:499] + "…"
        return Comprobacion(
            nombre,
            ESTADO_ERROR,
            f"{type(error).__name__}: {detalle}",
        )

    def _proteger_sincrono(self, nombre: str, operacion) -> Comprobacion:
        """Aísla una prueba local para que una caída no oculte las demás."""

        try:
            return operacion()
        except Exception as error:
            return self._error_aislado(nombre, error)

    async def _proteger(self, nombre: str, operacion) -> Comprobacion:
        """Aísla y limita una prueba asíncrona potencialmente externa."""

        try:
            return await asyncio.wait_for(operacion, timeout=10)
        except Exception as error:
            return self._error_aislado(nombre, error)

    @app_commands.command(
        name="test",
        description="Diagnostica comandos y subsistemas sin modificar datos.",
    )
    async def test(self, interaction: discord.Interaction):
        """Ejecuta comprobaciones operativas seguras y devuelve un resumen."""

        if not await solo_admin(interaction):
            return
        if not await solo_servidor(interaction):
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        inicio = perf_counter()
        guild_id = interaction.guild.id
        user_id = interaction.user.id

        resultados = [
            self._proteger_sincrono(
                "Árbol de comandos",
                self._diagnosticar_arbol,
            ),
            self._proteger_sincrono(
                "Discord",
                lambda: self._diagnosticar_discord(interaction),
            ),
            self._proteger_sincrono(
                "Tareas automáticas",
                self._diagnosticar_tareas,
            ),
        ]
        resultados.extend(
            await asyncio.gather(
                self._proteger("Base de datos", self._diagnosticar_base()),
                self._proteger("Box", self._diagnosticar_box(guild_id, user_id)),
                self._proteger(
                    "Madrugue",
                    self._diagnosticar_madrugue(guild_id, user_id),
                ),
                self._proteger("SeptSinFP", self._diagnosticar_ssf(guild_id)),
                self._proteger("Canales y permisos", self._diagnosticar_canales(interaction)),
            )
        )

        orden = {
            "Discord": 0,
            "Árbol de comandos": 1,
            "Base de datos": 2,
            "Box": 3,
            "Madrugue": 4,
            "SeptSinFP": 5,
            "Canales y permisos": 6,
            "Tareas automáticas": 7,
        }
        resultados.sort(key=lambda resultado: orden.get(resultado.nombre, 99))

        errores = sum(resultado.estado == ESTADO_ERROR for resultado in resultados)
        avisos = sum(resultado.estado == ESTADO_AVISO for resultado in resultados)
        estado_general = (
            "❌ Se detectaron fallos"
            if errores
            else "⚠️ Operativo con avisos"
            if avisos
            else "✅ Todo operativo"
        )
        color_area = "error" if errores else "aviso" if avisos else "ok"
        duracion = perf_counter() - inicio

        await responder(
            interaction,
            "🧪 Test administrativo",
            f"**{estado_general}** · {errores} errores · {avisos} avisos.\n"
            "Diagnóstico de solo lectura: no ejecutó compras, acciones ni reseteos.",
            color_area=color_area,
            ephemeral=True,
            pie=f"Completado en {duracion:.2f} s",
            secciones_=[
                (resultado.titulo, resultado.detalle[:1024], False)
                for resultado in resultados
            ],
        )
