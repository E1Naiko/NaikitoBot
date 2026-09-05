from core.database import conectar_db


# ============================================================
# INICIALIZACIÓN
# ============================================================

def inicializar_db():
    """
    Crea las tablas necesarias para los desafíos SSF.

    El sistema está preparado para soportar múltiples
    desafíos a lo largo del tiempo.
    """

    with conectar_db() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS ssf_desafios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                fecha_inicio TEXT NOT NULL,
                fecha_fin TEXT NOT NULL,
                canal_id INTEGER NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS ssf_participantes (
                desafio_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                fecha_registro TEXT NOT NULL,
                eliminado INTEGER NOT NULL DEFAULT 0,
                fecha_eliminacion TEXT,
                racha_actual INTEGER NOT NULL DEFAULT 0,
                mejor_racha INTEGER NOT NULL DEFAULT 0,

                PRIMARY KEY (
                    desafio_id,
                    user_id
                ),

                FOREIGN KEY (
                    desafio_id
                )
                REFERENCES ssf_desafios(id)
                ON DELETE CASCADE
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS ssf_registros (
                desafio_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,

                PRIMARY KEY (
                    desafio_id,
                    user_id,
                    fecha
                ),

                FOREIGN KEY (
                    desafio_id
                )
                REFERENCES ssf_desafios(id)
                ON DELETE CASCADE
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS ssf_revisiones (
                desafio_id INTEGER PRIMARY KEY,
                ultima_fecha TEXT NOT NULL,

                FOREIGN KEY (
                    desafio_id
                )
                REFERENCES ssf_desafios(id)
                ON DELETE CASCADE
            )
        """)

        db.commit()


# ============================================================
# DESAFÍOS
# ============================================================

def crear_desafio(
    guild_id,
    nombre,
    fecha_inicio,
    fecha_fin,
    canal_id,
):
    """Crea un nuevo desafío."""

    with conectar_db() as db:

        cursor = db.execute("""
            INSERT INTO ssf_desafios (
                guild_id,
                nombre,
                fecha_inicio,
                fecha_fin,
                canal_id,
                activo
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            guild_id,
            nombre,
            fecha_inicio,
            fecha_fin,
            canal_id,
        ))

        db.commit()

        return cursor.lastrowid


def obtener_desafio_activo(guild_id):
    """Obtiene el desafío activo de un servidor."""

    with conectar_db() as db:

        return db.execute("""
            SELECT
                id,
                guild_id,
                nombre,
                fecha_inicio,
                fecha_fin,
                canal_id,
                activo
            FROM ssf_desafios
            WHERE guild_id = ?
            AND activo = 1
            ORDER BY id DESC
            LIMIT 1
        """, (
            guild_id,
        )).fetchone()


def obtener_desafio_por_id(desafio_id):
    """Obtiene un desafío por su ID."""

    with conectar_db() as db:

        return db.execute("""
            SELECT
                id,
                guild_id,
                nombre,
                fecha_inicio,
                fecha_fin,
                canal_id,
                activo
            FROM ssf_desafios
            WHERE id = ?
        """, (
            desafio_id,
        )).fetchone()


def cerrar_desafio(desafio_id):
    """Cierra un desafío."""

    with conectar_db() as db:

        cursor = db.execute("""
            UPDATE ssf_desafios
            SET activo = 0
            WHERE id = ?
        """, (
            desafio_id,
        ))

        db.commit()

        return cursor.rowcount


# ============================================================
# PARTICIPANTES
# ============================================================

def registrar_participante(
    desafio_id,
    user_id,
    username,
    fecha_registro,
):
    """Registra un usuario como participante."""

    with conectar_db() as db:

        db.execute("""
            INSERT INTO ssf_participantes (
                desafio_id,
                user_id,
                username,
                fecha_registro
            )
            VALUES (?, ?, ?, ?)
        """, (
            desafio_id,
            user_id,
            username,
            fecha_registro,
        ))

        db.commit()


def obtener_participante(
    desafio_id,
    user_id,
):
    """Obtiene un participante."""

    with conectar_db() as db:

        return db.execute("""
            SELECT
                desafio_id,
                user_id,
                username,
                fecha_registro,
                eliminado,
                fecha_eliminacion,
                racha_actual,
                mejor_racha
            FROM ssf_participantes
            WHERE desafio_id = ?
            AND user_id = ?
        """, (
            desafio_id,
            user_id,
        )).fetchone()


def actualizar_participante(
    desafio_id,
    user_id,
    racha_actual,
    mejor_racha,
):
    """Actualiza las rachas de un participante."""

    with conectar_db() as db:

        db.execute("""
            UPDATE ssf_participantes
            SET
                racha_actual = ?,
                mejor_racha = ?
            WHERE desafio_id = ?
            AND user_id = ?
        """, (
            racha_actual,
            mejor_racha,
            desafio_id,
            user_id,
        ))

        db.commit()


def eliminar_participante(
    desafio_id,
    user_id,
    fecha_eliminacion,
):
    """Marca a un participante como eliminado."""

    with conectar_db() as db:

        db.execute("""
            UPDATE ssf_participantes
            SET
                eliminado = 1,
                fecha_eliminacion = ?
            WHERE desafio_id = ?
            AND user_id = ?
        """, (
            fecha_eliminacion,
            desafio_id,
            user_id,
        ))

        db.commit()


def obtener_participantes(
    desafio_id,
):
    """Obtiene todos los participantes de un desafío."""

    with conectar_db() as db:

        return db.execute("""
            SELECT
                user_id,
                username,
                fecha_registro,
                eliminado,
                fecha_eliminacion,
                racha_actual,
                mejor_racha
            FROM ssf_participantes
            WHERE desafio_id = ?
            ORDER BY fecha_registro ASC
        """, (
            desafio_id,
        )).fetchall()


# ============================================================
# REGISTROS DIARIOS
# ============================================================

def guardar_registro(
    desafio_id,
    user_id,
    fecha,
    hora,
):
    """Guarda la supervivencia de un participante."""

    with conectar_db() as db:

        db.execute("""
            INSERT INTO ssf_registros (
                desafio_id,
                user_id,
                fecha,
                hora
            )
            VALUES (?, ?, ?, ?)
        """, (
            desafio_id,
            user_id,
            fecha,
            hora,
        ))

        db.commit()


def tiene_registro(
    desafio_id,
    user_id,
    fecha,
):
    """Comprueba si un participante sobrevivió ese día."""

    with conectar_db() as db:

        resultado = db.execute("""
            SELECT 1
            FROM ssf_registros
            WHERE desafio_id = ?
            AND user_id = ?
            AND fecha = ?
        """, (
            desafio_id,
            user_id,
            fecha,
        )).fetchone()

    return resultado is not None


def obtener_registros_usuario(
    desafio_id,
    user_id,
):
    """Obtiene las fechas sobrevividas por un participante."""

    with conectar_db() as db:

        return db.execute("""
            SELECT fecha
            FROM ssf_registros
            WHERE desafio_id = ?
            AND user_id = ?
            ORDER BY fecha ASC
        """, (
            desafio_id,
            user_id,
        )).fetchall()


# ============================================================
# ESTADÍSTICAS
# ============================================================

def obtener_estadisticas_desafio(
    desafio_id,
):
    """Obtiene estadísticas generales del desafío."""

    with conectar_db() as db:

        total = db.execute("""
            SELECT COUNT(*)
            FROM ssf_participantes
            WHERE desafio_id = ?
        """, (
            desafio_id,
        )).fetchone()[0]

        activos = db.execute("""
            SELECT COUNT(*)
            FROM ssf_participantes
            WHERE desafio_id = ?
            AND eliminado = 0
        """, (
            desafio_id,
        )).fetchone()[0]

        eliminados = db.execute("""
            SELECT COUNT(*)
            FROM ssf_participantes
            WHERE desafio_id = ?
            AND eliminado = 1
        """, (
            desafio_id,
        )).fetchone()[0]

    return (
        total,
        activos,
        eliminados,
    )

def reactivar_participante(
    desafio_id,
    user_id,
):
    """Reactiva a un participante eliminado."""

    with conectar_db() as db:

        db.execute("""
            UPDATE ssf_participantes
            SET
                eliminado = 0,
                fecha_eliminacion = NULL
            WHERE desafio_id = ?
            AND user_id = ?
        """, (
            desafio_id,
            user_id,
        ))

        db.commit()

def obtener_desafios_activos():
    """Obtiene todos los desafíos activos."""

    with conectar_db() as db:

        return db.execute("""
            SELECT
                id,
                guild_id,
                nombre,
                fecha_inicio,
                fecha_fin,
                canal_id,
                activo
            FROM ssf_desafios
            WHERE activo = 1
            ORDER BY id ASC
        """).fetchall()

# ============================================================
# CONTROL DE REVISIONES AUTOMÁTICAS
# ============================================================

def obtener_ultima_revision_ssf(desafio_id):
    """Obtiene la última fecha procesada automáticamente."""

    with conectar_db() as db:

        resultado = db.execute("""
            SELECT ultima_fecha
            FROM ssf_revisiones
            WHERE desafio_id = ?
        """, (
            desafio_id,
        )).fetchone()

    if resultado is None:
        return None

    return resultado[0]


def guardar_ultima_revision_ssf(
    desafio_id,
    fecha,
):
    """Guarda la última fecha procesada automáticamente."""

    with conectar_db() as db:

        db.execute("""
            INSERT INTO ssf_revisiones (
                desafio_id,
                ultima_fecha
            )
            VALUES (?, ?)
            ON CONFLICT(desafio_id)
            DO UPDATE SET
                ultima_fecha = excluded.ultima_fecha
        """, (
            desafio_id,
            fecha,
        ))

        db.commit()

def obtener_ranking_final(desafio_id):
    """Obtiene el ranking final de un desafío."""

    with conectar_db() as db:

        return db.execute("""
            SELECT
                user_id,
                username,
                eliminado,
                racha_actual,
                mejor_racha
            FROM ssf_participantes
            WHERE desafio_id = ?
            ORDER BY
                eliminado ASC,
                mejor_racha DESC,
                username COLLATE NOCASE ASC
        """, (
            desafio_id,
        )).fetchall()


def marcar_desafio_cerrado(desafio_id):
    """Marca un desafío como cerrado."""

    with conectar_db() as db:

        cursor = db.execute("""
            UPDATE ssf_desafios
            SET activo = 0
            WHERE id = ?
            AND activo = 1
        """, (
            desafio_id,
        ))

        db.commit()

        return cursor.rowcount