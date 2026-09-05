from datetime import date

from core.database import conectar_db


# ============================================================
# INICIALIZACIÓN
# ============================================================

def inicializar_db():
    """
    Verifica que la tabla registros tenga la estructura actual.

    La migración de la base existente se realizó mediante
    migrar.py, por lo que aquí solamente comprobamos que
    guild_id exista.
    """

    with conectar_db() as db:
        columnas = db.execute("""
            PRAGMA table_info(registros)
        """).fetchall()

        if not columnas:
            db.execute("""
                CREATE TABLE registros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    hora TEXT NOT NULL,
                    puntos_base INTEGER NOT NULL,
                    multiplicador REAL NOT NULL,
                    puntos_finales REAL NOT NULL,
                    UNIQUE(guild_id, user_id, fecha)
                )
            """)
            db.commit()
            return

        nombres = {
            columna[1]
            for columna in columnas
        }

        if "guild_id" not in nombres:
            raise RuntimeError(
                "La base de datos no tiene guild_id. "
                "Ejecutá migrar.py antes de iniciar el bot."
            )


# ============================================================
# REGISTROS
# ============================================================

def obtener_registro_del_dia(
    guild_id,
    user_id,
    fecha,
):
    """Obtiene el registro de un usuario para una fecha."""

    with conectar_db() as db:
        return db.execute("""
            SELECT
                hora,
                puntos_finales
            FROM registros
            WHERE guild_id = ?
            AND user_id = ?
            AND fecha = ?
        """, (
            guild_id,
            user_id,
            fecha.isoformat(),
        )).fetchone()


def tiene_registro(
    guild_id,
    user_id,
    fecha,
):
    """Indica si el usuario tiene un registro para una fecha."""

    with conectar_db() as db:
        resultado = db.execute("""
            SELECT 1
            FROM registros
            WHERE guild_id = ?
            AND user_id = ?
            AND fecha = ?
        """, (
            guild_id,
            user_id,
            fecha.isoformat(),
        )).fetchone()

    return resultado is not None


def guardar_registro(
    guild_id,
    user_id,
    username,
    fecha,
    hora,
    puntos_base,
    multiplicador,
    puntos_finales,
):
    """Guarda una nueva madrugada."""

    with conectar_db() as db:
        db.execute("""
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
            fecha.isoformat(),
            hora,
            puntos_base,
            multiplicador,
            puntos_finales,
        ))
        db.commit()


# ============================================================
# PUNTOS
# ============================================================

def obtener_total_puntos(
    guild_id,
    user_id,
):
    """Devuelve el total de puntos de un usuario en un servidor."""

    with conectar_db() as db:
        return db.execute("""
            SELECT COALESCE(
                SUM(puntos_finales),
                0
            )
            FROM registros
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id,
        )).fetchone()[0]


# ============================================================
# FECHAS
# ============================================================

def obtener_fechas_registradas(
    guild_id,
    user_id,
    orden="DESC",
):
    """Devuelve las fechas registradas de un usuario como objetos date."""

    if orden not in ("ASC", "DESC"):
        raise ValueError(
            "El orden debe ser ASC o DESC."
        )

    with conectar_db() as db:
        filas = db.execute(f"""
            SELECT fecha
            FROM registros
            WHERE guild_id = ?
            AND user_id = ?
            ORDER BY fecha {orden}
        """, (
            guild_id,
            user_id,
        )).fetchall()

    return [
        date.fromisoformat(fila[0])
        for fila in filas
    ]


# ============================================================
# TOP MADRUGADORES
# ============================================================

def obtener_top_madrugadores(
    guild_id,
    limite=10,
):
    """Devuelve el TOP de un servidor."""

    with conectar_db() as db:
        return db.execute("""
            SELECT
                user_id,
                username,
                SUM(puntos_finales) AS puntos
            FROM registros
            WHERE guild_id = ?
            GROUP BY user_id
            ORDER BY puntos DESC
            LIMIT ?
        """, (
            guild_id,
            limite,
        )).fetchall()


# ============================================================
# ESTADÍSTICAS
# ============================================================

def obtener_estadisticas(
    guild_id,
    user_id,
):
    """
    Devuelve las estadísticas principales.

    También devuelve información de la última madrugada:
        hora
        multiplicador
        puntos_base
        puntos_finales
    """

    with conectar_db() as db:

        datos = db.execute("""
            SELECT
                COUNT(*),
                COALESCE(
                    SUM(puntos_finales),
                    0
                ),

                COALESCE(
                    SUM(
                        CASE
                            WHEN puntos_base = 100
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ),

                COALESCE(
                    SUM(
                        CASE
                            WHEN puntos_base = 25
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ),

                COALESCE(
                    SUM(
                        CASE
                            WHEN puntos_base = 5
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                )

            FROM registros

            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id,
        )).fetchone()

        ultima = db.execute("""
            SELECT
                hora,
                multiplicador,
                puntos_base,
                puntos_finales

            FROM registros

            WHERE guild_id = ?
            AND user_id = ?

            ORDER BY fecha DESC
            LIMIT 1
        """, (
            guild_id,
            user_id,
        )).fetchone()

        promedio = db.execute("""
            SELECT AVG(
                CAST(
                    substr(hora, 1, 2)
                    AS INTEGER
                ) * 60 +

                CAST(
                    substr(hora, 4, 2)
                    AS INTEGER
                )
            )

            FROM registros

            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id,
        )).fetchone()[0]

    return datos, ultima, promedio


# ============================================================
# ADMINISTRACIÓN
# ============================================================

def obtener_estadisticas_servidor(
    guild_id,
):
    """Devuelve estadísticas generales de un servidor."""

    with conectar_db() as db:

        madrugadores = db.execute("""
            SELECT COUNT(DISTINCT user_id)
            FROM registros
            WHERE guild_id = ?
        """, (
            guild_id,
        )).fetchone()[0]

        registros = db.execute("""
            SELECT COUNT(*)
            FROM registros
            WHERE guild_id = ?
        """, (
            guild_id,
        )).fetchone()[0]

        puntos = db.execute("""
            SELECT COALESCE(
                SUM(puntos_finales),
                0
            )
            FROM registros
            WHERE guild_id = ?
        """, (
            guild_id,
        )).fetchone()[0]

    return (
        madrugadores,
        registros,
        puntos,
    )


def obtener_registros_de_hoy(
    guild_id,
    fecha,
):
    """Devuelve la cantidad de registros de un día."""

    with conectar_db() as db:
        return db.execute("""
            SELECT COUNT(*)
            FROM registros
            WHERE guild_id = ?
            AND fecha = ?
        """, (
            guild_id,
            fecha.isoformat(),
        )).fetchone()[0]


def eliminar_registro_del_dia(
    guild_id,
    user_id,
    fecha,
):
    """Elimina el registro de un usuario para una fecha."""

    with conectar_db() as db:

        cursor = db.execute("""
            DELETE FROM registros
            WHERE guild_id = ?
            AND user_id = ?
            AND fecha = ?
        """, (
            guild_id,
            user_id,
            fecha.isoformat(),
        ))

        db.commit()

        return cursor.rowcount


def eliminar_registros_usuario(
    guild_id,
    user_id,
):
    """Elimina todos los registros de un usuario."""

    with conectar_db() as db:

        cursor = db.execute("""
            DELETE FROM registros
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id,
        ))

        db.commit()

        return cursor.rowcount

def eliminar_registros_servidor(
    guild_id,
):
    """Elimina todos los registros de Madrugue de un servidor."""

    with conectar_db() as db:

        cursor = db.execute("""
            DELETE FROM registros
            WHERE guild_id = ?
        """, (
            guild_id,
        ))

        db.commit()

        return cursor.rowcount


def obtener_resumen_usuario(
    guild_id,
    user_id,
):
    """Obtiene un resumen de los registros de un usuario."""

    with conectar_db() as db:

        resultado = db.execute("""
            SELECT
                COUNT(*),
                COALESCE(
                    SUM(puntos_finales),
                    0
                ),
                MIN(fecha),
                MAX(fecha)
            FROM registros
            WHERE guild_id = ?
            AND user_id = ?
        """, (
            guild_id,
            user_id,
        )).fetchone()

    return resultado


def obtener_registro_del_dia_admin(
    guild_id,
    user_id,
    fecha,
):
    """Obtiene el registro del usuario para una fecha."""

    with conectar_db() as db:

        return db.execute("""
            SELECT
                hora,
                puntos_finales
            FROM registros
            WHERE guild_id = ?
            AND user_id = ?
            AND fecha = ?
        """, (
            guild_id,
            user_id,
            fecha.isoformat(),
        )).fetchone()
