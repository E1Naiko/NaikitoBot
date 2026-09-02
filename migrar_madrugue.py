import sqlite3
import shutil
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

ORIGEN = Path("madrugue.db")
DESTINO = Path("naikito.db")
BACKUP = Path("naikito_backup_antes_madrugue.db")


# ============================================================
# COMPROBACIONES
# ============================================================

if not ORIGEN.exists():
    raise FileNotFoundError(
        f"No se encontró la base de origen: {ORIGEN}"
    )

if not DESTINO.exists():
    raise FileNotFoundError(
        f"No se encontró la base de destino: {DESTINO}"
    )


# ============================================================
# BACKUP
# ============================================================

print("=" * 60)
print("MIGRACIÓN DE MADRUGUE")
print("=" * 60)

print("\n📦 Creando backup de naikito.db...")

shutil.copy2(DESTINO, BACKUP)

print(f"✅ Backup creado: {BACKUP}")


# ============================================================
# LEER BASE DE MADRUGUE
# ============================================================

print("\n📖 Leyendo madrugue.db...")

db_origen = sqlite3.connect(ORIGEN)

registros = db_origen.execute("""
    SELECT
        guild_id,
        user_id,
        username,
        fecha,
        hora,
        puntos_base,
        multiplicador,
        puntos_finales
    FROM registros
    ORDER BY fecha, hora
""").fetchall()

db_origen.close()

print(f"📊 Registros encontrados: {len(registros)}")


# ============================================================
# INSERTAR EN NAIKITOBOT
# ============================================================

print("\n💾 Insertando registros en naikito.db...")

db_destino = sqlite3.connect(DESTINO)

# Verificar que exista la tabla
tabla = db_destino.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name = 'registros'
""").fetchone()

if tabla is None:
    db_destino.close()

    raise RuntimeError(
        "La tabla 'registros' no existe en naikito.db.\n"
        "Iniciá el bot una vez para que se cree."
    )


insertados = 0
omitidos = 0

for registro in registros:

    try:

        cursor = db_destino.execute("""
            INSERT INTO registros (
                guild_id,
                user_id,
                username,
                fecha,
                hora,
                puntos_base,
                multiplicador,
                puntos_finales
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, registro)

        if cursor.rowcount > 0:
            insertados += 1

    except sqlite3.IntegrityError:

        # Ya existe un registro para ese
        # servidor / usuario / fecha.
        omitidos += 1


db_destino.commit()


# ============================================================
# VERIFICACIÓN
# ============================================================

total = db_destino.execute("""
    SELECT COUNT(*)
    FROM registros
""").fetchone()[0]


db_destino.close()


# ============================================================
# RESULTADO
# ============================================================

print("\n" + "=" * 60)
print("RESULTADO")
print("=" * 60)

print(f"📥 Registros encontrados: {len(registros)}")
print(f"✅ Registros insertados:  {insertados}")
print(f"⏭️ Registros omitidos:    {omitidos}")
print(f"📊 Total en naikito.db:   {total}")

print("\n✅ Migración terminada.")
print(f"🛡️ Backup disponible en: {BACKUP}")