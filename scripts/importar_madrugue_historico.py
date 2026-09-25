"""Importa el histórico de Madrugue recuperado de Discord.

Uso (desde la raíz del proyecto):

    python scripts/importar_madrugue_historico.py --guild-id 123456789

Si ``GUILD_ID`` está definido en ``.env``, el argumento puede omitirse.
La importación es idempotente: los registros ya existentes se omiten, y se
aborta si encuentra un registro con la misma fecha/usuario pero datos distintos.
No se importan mensajes de ranking, estadísticas, intentos fuera de horario ni
mensajes de conversación: solo las madrugadas que entregaron puntos.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import date
from pathlib import Path
import sys

# Permite ejecutar el archivo directamente con ``python scripts/...``.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from sqlalchemy import select  # noqa: E402

from core.database import crear_sesion, inicializar_db  # noqa: E402
from modules.madrugue.models import RegistroMadrugue  # noqa: E402


# (id de Discord, nombre mostrado, fecha, hora, puntos base, multiplicador,
#  puntos obtenidos). Los decimales son los valores mostrados por el bot.
HISTORICO = (
    (468878374400425985, "Joe Yabuki", "2026-09-05", "05:44", 100, 1.095, 109.5),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-05", "08:02", 25, 1.044, 26.1),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-06", "06:32", 100, 1.077, 107.7),
    (468878374400425985, "Joe Yabuki", "2026-09-06", "07:41", 25, 1.052, 26.3),
    (251018515023134721, "Ñoquito", "2026-09-06", "09:14", 5, 1.018, 5.1),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-07", "08:44", 25, 1.029, 25.7),
    (468878374400425985, "Joe Yabuki", "2026-09-07", "09:14", 5, 1.018, 5.1),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-08", "07:28", 25, 1.057, 26.4),
    (468878374400425985, "Joe Yabuki", "2026-09-08", "07:35", 25, 1.054, 26.4),
    (251018515023134721, "Ñoquito", "2026-09-08", "07:44", 25, 1.051, 26.3),
    (468878374400425985, "Joe Yabuki", "2026-09-09", "06:52", 100, 1.070, 107.0),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-09", "07:03", 25, 1.066, 26.6),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-10", "07:11", 25, 1.063, 26.6),
    (251018515023134721, "Ñoquito", "2026-09-10", "07:33", 25, 1.055, 26.4),
    (468878374400425985, "Joe Yabuki", "2026-09-10", "08:04", 25, 1.043, 26.1),
    (468878374400425985, "Joe Yabuki", "2026-09-11", "06:50", 100, 1.070, 107.0),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-11", "06:59", 100, 1.067, 106.7),
    (848312017701830656, "Luchito", "2026-09-11", "09:10", 5, 1.019, 5.1),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-12", "05:55", 100, 1.091, 109.1),
    (468878374400425985, "Joe Yabuki", "2026-09-12", "06:41", 100, 1.074, 107.4),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-13", "06:31", 100, 1.078, 107.8),
    (468878374400425985, "Joe Yabuki", "2026-09-13", "08:38", 25, 1.031, 25.8),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-14", "06:51", 100, 1.070, 107.0),
    (468878374400425985, "Joe Yabuki", "2026-09-14", "06:52", 100, 1.070, 107.0),
    (468878374400425985, "Joe Yabuki", "2026-09-15", "06:50", 100, 1.070, 107.0),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-15", "07:07", 25, 1.064, 26.6),
    (898791221928022036, "ay roman", "2026-09-15", "09:08", 5, 1.020, 5.1),
    (467430506762600448, "Nowthousand Leonardo +Diaz", "2026-09-16", "08:03", 25, 1.044, 26.1),
    (468878374400425985, "Joe Yabuki", "2026-09-17", "06:50", 100, 1.070, 107.0),
    (468878374400425985, "Joe Yabuki", "2026-09-18", "06:57", 100, 1.068, 106.8),
    (848312017701830656, "Luchito", "2026-09-18", "09:53", 5, 1.003, 5.0),
    (468878374400425985, "Joe Yabuki", "2026-09-19", "07:42", 25, 1.051, 26.3),
    (468878374400425985, "Joe Yabuki", "2026-09-21", "05:52", 100, 1.092, 109.2),
    (468878374400425985, "Joe Yabuki", "2026-09-22", "06:51", 100, 1.070, 107.0),
    (468878374400425985, "Joe Yabuki", "2026-09-23", "06:51", 100, 1.070, 107.0),
)


def _guild_id_argument() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guild-id", type=int, default=None, help="ID del servidor de Discord")
    args = parser.parse_args()
    value = args.guild_id or os.getenv("GUILD_ID")
    if not value:
        parser.error("indica --guild-id o configura GUILD_ID en .env")
    return int(value)


async def importar(guild_id: int) -> tuple[int, int]:
    await inicializar_db()
    importados = omitidos = 0

    async with crear_sesion() as sesion:
        for user_id, username, fecha_texto, hora, base, multiplicador, puntos in HISTORICO:
            fecha = date.fromisoformat(fecha_texto)
            existente = (await sesion.execute(
                select(RegistroMadrugue).where(
                    RegistroMadrugue.guild_id == guild_id,
                    RegistroMadrugue.user_id == user_id,
                    RegistroMadrugue.fecha == fecha,
                )
            )).scalar_one_or_none()

            if existente:
                datos = (existente.username, existente.hora, existente.puntos_base,
                         existente.multiplicador, existente.puntos_finales)
                esperados = (username, hora, base, multiplicador, puntos)
                if datos != esperados:
                    raise RuntimeError(
                        f"Conflicto en {fecha_texto} para {user_id}: "
                        f"la base ya contiene datos diferentes."
                    )
                omitidos += 1
                continue

            sesion.add(RegistroMadrugue(
                guild_id=guild_id,
                user_id=user_id,
                username=username,
                fecha=fecha,
                hora=hora,
                puntos_base=base,
                multiplicador=multiplicador,
                puntos_finales=puntos,
            ))
            importados += 1

        await sesion.commit()

    return importados, omitidos


async def main() -> None:
    guild_id = _guild_id_argument()
    importados, omitidos = await importar(guild_id)
    print(f"Importación completada: {importados} nuevos, {omitidos} ya existentes.")
    print("Los 35 registros históricos de Madrugue están disponibles para ese servidor.")


if __name__ == "__main__":
    asyncio.run(main())
