"""Consultas académicas y progreso privado en Discord."""

import asyncio
import textwrap
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_http import espera_restante, registrar_limite
from core.mensajes import crear_embed, responder, responder_error
from core.permissions import es_admin
from modules.correlativas.services import ejecutar, sugerir_aprobacion


Semestre = Literal["1er Semestre", "2do Semestre", "Ambos"]


def _filtro(semestre):
    return {"1er Semestre": " 1", "2do Semestre": " 2"}.get(semestre, "")


def _paginas(resultado):
    paginas = []
    pagina = ""
    for linea in resultado.splitlines():
        for fragmento in textwrap.wrap(linea, 3900, replace_whitespace=False) or [""]:
            if len(pagina) + len(fragmento) + 1 > 4000:
                paginas.append(pagina)
                pagina = ""
            pagina += fragmento + "\n"
    return paginas + [pagina]


class Paginador(discord.ui.View):
    def __init__(self, paginas, usuario):
        super().__init__(timeout=180)
        self.paginas = paginas
        self.usuario = usuario
        self.indice = 0
        self._actualizar_botones(0)

    async def interaction_check(self, interaction):
        return interaction.user.id == self.usuario and espera_restante() <= 0

    def _actualizar_botones(self, indice):
        self.anterior.disabled = indice == 0
        self.siguiente.disabled = indice == len(self.paginas) - 1

    async def _mover(self, interaction, delta):
        destino = min(max(self.indice + delta, 0), len(self.paginas) - 1)
        self._actualizar_botones(destino)
        try:
            await interaction.response.edit_message(
                embed=crear_embed("Correlativas", self.paginas[destino], pie=f"Página {destino + 1}/{len(self.paginas)}"),
                view=self,
            )
        except discord.HTTPException as error:
            self._actualizar_botones(self.indice)
            if not registrar_limite(error, contexto="paginación de correlativas"):
                raise
        else:
            self.indice = destino

    @discord.ui.button(label="Anterior")
    async def anterior(self, interaction, boton):
        await self._mover(interaction, -1)

    @discord.ui.button(label="Siguiente")
    async def siguiente(self, interaction, boton):
        await self._mover(interaction, 1)


class Correlativas(commands.GroupCog, group_name="correlativas"):
    async def _ejecutar(self, interaccion, mensaje, administrador=False):
        if espera_restante() > 0:
            return
        try:
            if administrador and not es_admin(interaccion.user.id):
                await responder_error(interaccion, "Correlativas", "Comando reservado a administradores.", ephemeral=True)
                return
            usuario = interaccion.user.id
            if mensaje.startswith(("aprobar ", "unirse ", "admin ")):
                # No modificar el progreso si Discord no acepta la interacción.
                await interaccion.response.defer(ephemeral=True)
                resultado = await asyncio.to_thread(ejecutar, usuario, mensaje, administrador)
            else:
                tarea = asyncio.create_task(asyncio.to_thread(ejecutar, usuario, mensaje, administrador))
                try:
                    if not (await asyncio.wait({tarea}, timeout=1.5))[0]:
                        await interaccion.response.defer(ephemeral=True)
                    resultado = await tarea
                finally:
                    if not tarea.done():
                        tarea.cancel()
                    await asyncio.gather(tarea, return_exceptions=True)
            paginas = _paginas(resultado)
            vista = Paginador(paginas, usuario) if len(paginas) > 1 else None
            await responder(interaccion, "Correlativas", paginas[0], ephemeral=True, view=vista,
                            pie=f"Página 1/{len(paginas)}" if vista else None)
        except discord.HTTPException as error:
            if not registrar_limite(error, contexto="respuesta de correlativas"):
                raise

    @app_commands.command(description="Lista los planes de estudio disponibles.")
    async def planes(self, interaccion):
        await self._ejecutar(interaccion, "planes")

    @app_commands.command(description="Selecciona tu plan de estudio activo.")
    async def unirse(self, interaccion, plan: app_commands.Range[str, 1, 64]):
        await self._ejecutar(interaccion, f"unirse {plan}")

    @app_commands.command(description="Lista las materias de un año del plan.")
    async def materias(self, interaccion, plan: app_commands.Range[str, 1, 64], anio: app_commands.Range[int, 1, 99],
                       semestre: Semestre = "Ambos"):
        await self._ejecutar(interaccion, f"mostrar anio {plan} {anio}{_filtro(semestre)}")

    @app_commands.command(description="Registra una materia aprobada de tu plan activo.")
    async def aprobar(self, interaccion, materia: app_commands.Range[str, 1, 150]):
        await self._ejecutar(interaccion, f"aprobar materia {materia}")

    @aprobar.autocomplete("materia")
    async def autocompletar_materia(self, interaccion, actual: str) -> list[app_commands.Choice[str]]:
        if espera_restante() > 0:
            return []
        opciones = await asyncio.to_thread(sugerir_aprobacion, interaccion.user.id, actual)
        return [app_commands.Choice(name=f"{codigo} · {nombre}"[:100], value=codigo)
                for codigo, nombre in opciones]

    @app_commands.command(description="Muestra qué materias podés cursar según tus aprobaciones.")
    async def siguientes(self, interaccion, semestre: Semestre = "Ambos"):
        await self._ejecutar(interaccion, "materias quiensigue" + _filtro(semestre))

    @app_commands.command(description="Calcula el porcentaje de avance de tu plan activo.")
    async def progreso(self, interaccion):
        await self._ejecutar(interaccion, "progreso")

    @app_commands.command(description="Agrega un plan de estudio (solo administradores del bot).")
    async def agregar_plan(self, interaccion, plan: app_commands.Range[str, 1, 64]):
        await self._ejecutar(interaccion, f"admin agregar plan {plan}", administrador=True)

    @app_commands.command(description="Agrega una materia al catálogo (solo administradores del bot).")
    @app_commands.describe(previas="Códigos de materias requeridas, separados por comas.")
    async def agregar_materia(
        self, interaccion, plan: app_commands.Range[str, 1, 64], codigo: app_commands.Range[str, 1, 32],
        anio: app_commands.Range[int, 1, 99], nombre: app_commands.Range[str, 1, 150],
        previas: app_commands.Range[str, 1, 500] | None = None,
    ):
        if any(c.isspace() for c in plan + codigo) or "|" in nombre:
            await responder_error(interaccion, "Correlativas", "Plan, código o nombre inválido.", ephemeral=True)
            return
        requisitos = f" | {previas}" if previas else ""
        await self._ejecutar(interaccion, f"admin agregar materia {plan} {codigo} {anio} {nombre}{requisitos}",
                             administrador=True)


async def setup(bot):
    await bot.add_cog(Correlativas())
