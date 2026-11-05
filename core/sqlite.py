"""Conexiones SQLite al mismo archivo persistente del bot.

Cada operación abre su propia conexión. Las escrituras deben confirmar la
transacción explícitamente; al cerrar sin confirmar, SQLite la revierte.
"""

import asyncio
from contextlib import asynccontextmanager, contextmanager
import sqlite3

import aiosqlite

from config import DATABASE
from core import temporada


class _ConexionAsync:
    """Impide confirmar una operación que atravesó el corte anual."""

    def __init__(self, conexion, inicio):
        self._conexion = conexion
        self._inicio = inicio

    def __getattr__(self, nombre):
        return getattr(self._conexion, nombre)

    async def commit(self):
        if temporada.inicio_temporada() != self._inicio:
            await self._conexion.rollback()
            raise RuntimeError("La temporada cambió durante la operación; volvé a intentarla.")
        await self._conexion.commit()


class _ConexionSync:
    def __init__(self, conexion, inicio):
        self._conexion = conexion
        self._inicio = inicio

    def __getattr__(self, nombre):
        return getattr(self._conexion, nombre)

    def commit(self):
        if temporada.inicio_temporada() != self._inicio:
            self._conexion.rollback()
            raise RuntimeError("La temporada cambió durante la operación; volvé a intentarla.")
        self._conexion.commit()


@asynccontextmanager
async def conectar():
    """Conexión asíncrona; comprueba el corte sin bloquear el event loop."""
    while True:
        inicio = temporada.inicio_temporada()
        await asyncio.to_thread(temporada.verificar_temporada)
        if inicio == temporada.inicio_temporada():
            break
    async with aiosqlite.connect(DATABASE, timeout=30) as conexion:
        yield _ConexionAsync(conexion, inicio)


@contextmanager
def conectar_sync():
    """Conexión bloqueante para operaciones ejecutadas fuera del event loop."""
    while True:
        inicio = temporada.inicio_temporada()
        temporada.verificar_temporada()
        if inicio == temporada.inicio_temporada():
            break
    conexion = sqlite3.connect(DATABASE, timeout=30)
    try:
        yield _ConexionSync(conexion, inicio)
    finally:
        conexion.close()
