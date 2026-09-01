import sqlite3
from pathlib import Path


DB_VIEJA = Path("madrugue.db")
DB_NUEVA = Path("naikito.db")


def migrar():
    print("=" * 60)
    print("MIGRACIÓN DE MADRUGUE")
    print("=" * 60)

    if not DB_VIEJA.exists():
        print(f"❌ No existe: {DB_VIEJA}")
        return

    if not DB_NUEVA.exists():
        print(f"❌ No existe: {DB_NUEVA}")
        return

    # --------------------------------------------------------
    # CONEXIONES
    # --------------------------------------------------------

    db_vieja = sqlite3.connect(DB_VIEJA)
    db_nueva = sqlite3.connect(DB_NUEVA)

    try:
        # ----------------------------------------------------
        # LEER REGISTROS DE LA BASE VIEJA
        # ----------------------------------------------------

        registros = db_vieja.execute("""
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
            ORDER BY id ASC
        """).fetchall()

        print(
            f"\n📦 Registros encontrados en madrugue.db: "
            f"{len(registros)}"
        )

        # ----------------------------------------------------
        # CONTADORES
        # ----------------------------------------------------

        importados = 0
        duplicados = 0
        errores = 0

        # ----------------------------------------------------
        # IMPORTAR
        # ----------------------------------------------------

        for registro in registros:

            (
                guild_id,
                user_id,
                username,
                fecha,
                hora,
                puntos_base,
                multiplicador,
                puntos_finales,
            ) = registro

            # -----------------------------------------------
            # COMPROBAR SI YA EXISTE
            # -----------------------------------------------

            existente = db_nueva.execute("""
                SELECT id
                FROM registros
                WHERE guild_id = ?
                AND user_id = ?
                AND fecha = ?
            """, (
                guild_id,
                user_id,
                fecha,
            )).fetchone()

            if existente is not None:
                duplicados += 1

                print(
                    f"⏭️ Ya existe: "
                    f"{username} | "
                    f"{fecha} | "
                    f"{hora}"
                )

                continue

            # -----------------------------------------------
            # INSERTAR
            # -----------------------------------------------

            try:

                db_nueva.execute("""
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
                """, (
                    guild_id,
                    user_id,
                    username,
                    fecha,
                    hora,
                    puntos_base,
                    multiplicador,
                    puntos_finales,
                ))

                importados += 1

                print(
                    f"✅ Importado: "
                    f"{username} | "
                    f"{fecha} | "
                    f"{hora} | "
                    f"{puntos_finales:.3f} pts"
                )

            except sqlite3.Error as error:

                errores += 1

                print(
                    f"❌ Error importando "
                    f"{username} | {fecha}: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # GUARDAR
        # ----------------------------------------------------

        db_nueva.commit()

        # ----------------------------------------------------
        # RESULTADO
        # ----------------------------------------------------

        print("\n" + "=" * 60)
        print("MIGRACIÓN FINALIZADA")
        print("=" * 60)

        print(
            f"📦 Registros encontrados: {len(registros)}"
        )

        print(
            f"✅ Registros importados: {importados}"
        )

        print(
            f"⏭️ Registros ya existentes: {duplicados}"
        )

        print(
            f"❌ Errores: {errores}"
        )

        print("=" * 60)

    except sqlite3.Error as error:

        db_nueva.rollback()

        print(
            "\n❌ ERROR DURANTE LA MIGRACIÓN:"
        )

        print(error)

    finally:

        db_vieja.close()
        db_nueva.close()


if __name__ == "__main__":
    migrar()