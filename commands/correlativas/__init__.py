"""Consultas académicas y progreso privado en Discord."""

import asyncio
import textwrap
from typing import Literal

from discord import app_commands
from discord.ext import commands

from core.mensajes import responder, responder_error
from core.permissions import es_admin
from modules.correlativas.services import ejecutar, sugerir_aprobacion


Semestre = Literal["1er Semestre", "2do Semestre", "Ambos"]


def _filtro(semestre):
    return {"1er Semestre": " 1", "2do Semestre": " 2"}.get(semestre, "")


class Correlativas(commands.GroupCog, group_name="correlativas"):
    async def _ejecutar(self, interaccion, mensaje, administrador=False):
        if administrador and not es_admin(interaccion.user.id):
            await responder_error(interaccion, "Correlativas", "Comando reservado a administradores.", ephemeral=True)
            return
        await interaccion.response.defer(ephemeral=True)
        resultado = await asyncio.to_thread(ejecutar, interaccion.user.id, mensaje, administrador)
        pagina = ""
        for linea in resultado.splitlines():
            for fragmento in textwrap.wrap(linea, 3900, replace_whitespace=False):
                if len(pagina) + len(fragmento) + 1 > 4000:
                    await responder(interaccion, "Correlativas", pagina, ephemeral=True)
                    pagina = ""
                pagina += fragmento + "\n"
        if pagina:
            await responder(interaccion, "Correlativas", pagina, ephemeral=True)

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
