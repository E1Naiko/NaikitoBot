"""Corte anual de los datos del bot a las 00:00 del 3 de octubre local."""

from datetime import datetime
import sqlite3

from config import DATABASE, TIMEZONE


def inicio_temporada(momento=None):
    """Último 3 de octubre, a medianoche en la zona configurada."""
    momento = momento or datetime.now(TIMEZONE)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TIMEZONE)
    else:
        momento = momento.astimezone(TIMEZONE)
    inicio = datetime(momento.year, 10, 3, tzinfo=TIMEZONE)
    if momento < inicio:
        inicio = datetime(momento.year - 1, 10, 3, tzinfo=TIMEZONE)
    return inicio


def verificar_temporada():
    """Aplica el corte en una transacción SQLite, una sola vez por temporada.

    Se verifica antes de abrir cada conexión de aplicación, inclusive después
    de una caída o si el bot siguió encendido durante el cambio de año. El
    bloqueo de escritura serializa la transición entre procesos/conexiones.
    Si el esquema todavía no existe, su inicialización la aplicará después.
    """
    fecha = inicio_temporada().date().isoformat()
    conexion = sqlite3.connect(DATABASE, timeout=30)
    try:
        existe = conexion.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'temporada'"
        ).fetchone()
        if not existe:
            return
        fila = conexion.execute("SELECT inicio FROM temporada WHERE id = 1").fetchone()
        if fila and fila[0] == fecha:
            return
        conexion.execute("BEGIN IMMEDIATE")
        # El bloqueo puede haber esperado hasta después de medianoche.
        fecha = inicio_temporada().date().isoformat()
        fila = conexion.execute("SELECT inicio FROM temporada WHERE id = 1").fetchone()
        if fila and fila[0] == fecha:
            conexion.rollback()
            return
        if fila and fila[0] > fecha:
            raise RuntimeError("La temporada guardada es futura: revisá el reloj y la zona horaria.")

        # Madrugue y 420 guardan fechas: se conserva lo que ya pertenece a la
        # temporada actual, incluso en la primera instalación de esta regla.
        conexion.execute("DELETE FROM registros WHERE fecha < ?", (fecha,))
        conexion.execute("DELETE FROM lahora_registros WHERE fecha < ?", (fecha,))
        # Una competencia anterior no puede arrastrar participantes ni rachas.
        for tabla in ("ssf_registros", "ssf_revisiones", "ssf_participantes"):
            conexion.execute(
                f"DELETE FROM {tabla} WHERE desafio_id IN "
                "(SELECT id FROM ssf_desafios WHERE fecha_inicio < ?)", (fecha,)
            )
        conexion.execute("DELETE FROM ssf_desafios WHERE fecha_inicio < ?", (fecha,))
        # Un desafío posterior también puede tener inscripciones anticipadas.
        conexion.execute(
            "DELETE FROM ssf_registros WHERE fecha < ? OR (desafio_id, user_id) IN "
            "(SELECT desafio_id, user_id FROM ssf_participantes WHERE fecha_registro < ?)",
            (fecha, fecha),
        )
        conexion.execute("DELETE FROM ssf_participantes WHERE fecha_registro < ?", (fecha,))
        conexion.execute("DELETE FROM ssf_revisiones WHERE ultima_fecha < ?", (fecha,))
        # El estado de Box no tiene fecha de origen: se reinicia completo.
        # La configuración de cada servidor se conserva.
        for tabla in (
            "box_combates_asaltos", "box_combates", "box_desafios_historial",
            "box_desafios", "box_acciones", "box_sponsors", "box_mejoras",
            "box_equipo", "box_usuarios",
        ):
            conexion.execute(f"DELETE FROM {tabla}")
        conexion.execute(
            "INSERT INTO temporada (id, inicio) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET inicio = excluded.inicio", (fecha,)
        )
        conexion.commit()
        print(f"[TEMPORADA] Reinicio aplicado desde {fecha}; configuración conservada.", flush=True)
    finally:
        conexion.close()
