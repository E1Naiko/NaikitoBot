import sqlite3

DATABASE = "naikito.db"

GUILD_ID = 966498278831173672

REGISTROS = [
    ("2026-08-27", 468878374400425985, "Joe Yabuki", "06:51", 100, 1.070300000),
    ("2026-08-27", 251018515023134721, "Ñoquito", "07:16", 25, 1.0611333333333333),
    ("2026-08-27", 898791221928022036, "Mole Moli", "08:30", 25, 1.034000000),

    ("2026-08-28", 468878374400425985, "Joe Yabuki", "06:51", 100, 1.070300000),
    ("2026-08-28", 290238540246417408, "oʞᴉɐN", "09:00", 5, 1.023000000),

    ("2026-08-29", 468878374400425985, "Joe Yabuki", "06:04", 100, 1.0875333333333332),
    ("2026-08-29", 251018515023134721, "Ñoquito", "08:00", 25, 1.045000000),

    ("2026-08-30", 468878374400425985, "Joe Yabuki", "07:01", 25, 1.0666333333333333),
    ("2026-08-30", 467430506762600448, "Nowthousand Leonardo +Diaz", "08:05", 25, 1.0431666666666666),

    ("2026-08-31", 468878374400425985, "Joe Yabuki", "06:31", 100, 1.0776333333333334),
    ("2026-08-31", 290238540246417408, "oʞᴉɐN", "08:18", 25, 1.038400000),
    ("2026-08-31", 251018515023134721, "Ñoquito", "08:32", 25, 1.0332666666666666),
]


def main():
    db = sqlite3.connect(DATABASE)

    print("=" * 60)
    print("MIGRACIÓN DESDE CHAT LOG")
    print("=" * 60)
    print()

    importados = 0
    existentes = 0

    for fecha, user_id, username, hora, puntos_base, multiplicador in REGISTROS:

        existente = db.execute(
            """
            SELECT id
            FROM registros
            WHERE guild_id = ?
              AND user_id = ?
              AND fecha = ?
            """,
            (GUILD_ID, user_id, fecha),
        ).fetchone()

        if existente:
            print(f"⏭️ YA EXISTE: {username} | {fecha}")
            existentes += 1
            continue

        puntos_finales = puntos_base * multiplicador

        db.execute(
            """
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
            """,
            (
                GUILD_ID,
                user_id,
                username,
                fecha,
                hora,
                puntos_base,
                multiplicador,
                puntos_finales,
            ),
        )

        print(
            f"✅ Importado: {username} | "
            f"{fecha} | {hora} | "
            f"{puntos_finales:.3f} pts"
        )

        importados += 1

    db.commit()

    print()
    print("=" * 60)
    print("MIGRACIÓN FINALIZADA")
    print("=" * 60)
    print(f"📦 Registros procesados: {len(REGISTROS)}")
    print(f"✅ Registros importados: {importados}")
    print(f"⏭️ Registros ya existentes: {existentes}")
    print("=" * 60)

    db.close()


if __name__ == "__main__":
    main()