from datetime import datetime, timedelta
import math
import random
import sqlite3

from core.database import conectar_db


def inicializar_db():
    """Crea las tablas de progreso y acciones activas de Box."""

    with conectar_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS box_usuarios (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                experiencia INTEGER NOT NULL DEFAULT 0,
                dinero INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        columnas_usuario = {
            columna[1]
            for columna in db.execute("PRAGMA table_info(box_usuarios)")
        }
        if "probabilidad_lesion" not in columnas_usuario:
            db.execute(
                "ALTER TABLE box_usuarios ADD COLUMN probabilidad_lesion REAL NOT NULL DEFAULT 0"
            )
        if "lesionado_hasta" not in columnas_usuario:
            db.execute(
                "ALTER TABLE box_usuarios ADD COLUMN lesionado_hasta TEXT"
            )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS box_acciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                iniciado_en TEXT NOT NULL,
                finaliza_en TEXT NOT NULL,
                recompensa INTEGER NOT NULL,
                UNIQUE (guild_id, user_id)
            )
            """
        )
        columnas = {
            columna[1]
            for columna in db.execute("PRAGMA table_info(box_acciones)")
        }
        if "dinero_recompensa" not in columnas:
            db.execute(
                """
                ALTER TABLE box_acciones
                ADD COLUMN dinero_recompensa INTEGER NOT NULL DEFAULT 0
                """
            )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS box_desafios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                retador_id INTEGER NOT NULL,
                contrincante_id INTEGER NOT NULL,
                expira_en TEXT NOT NULL,
                UNIQUE (guild_id, retador_id, contrincante_id)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS box_mejoras (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                mejora TEXT NOT NULL,
                nivel INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, mejora)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS box_desafios_historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                retador_id INTEGER NOT NULL,
                contrincante_id INTEGER NOT NULL,
                ganador_id INTEGER NOT NULL,
                creado_en TEXT NOT NULL
            )
            """
        )
        db.commit()


def iniciar_accion(
    guild_id: int,
    user_id: int,
    tipo: str,
    iniciado_en: datetime,
    finaliza_en: datetime,
    recompensa: int,
    dinero_recompensa: int = 0,
):
    """Registra una acción si el usuario no tiene otra activa."""

    if tipo == "TRABAJANDO":
        dinero_recompensa = recompensa

    with conectar_db() as db:
        try:
            db.execute(
                """
                INSERT INTO box_acciones (
                    guild_id, user_id, tipo, iniciado_en,
                    finaliza_en, recompensa, dinero_recompensa
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    tipo,
                    iniciado_en.isoformat(),
                    finaliza_en.isoformat(),
                    recompensa,
                    dinero_recompensa,
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return False

    return True


def obtener_accion_activa(guild_id: int, user_id: int):
    """Devuelve la acción activa del usuario, si existe."""

    with conectar_db() as db:
        return db.execute(
            """
            SELECT tipo, finaliza_en, recompensa
            FROM box_acciones
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()


def obtener_estado_box(guild_id: int, user_id: int):
    """Devuelve probabilidad de lesión y fecha de recuperación."""

    with conectar_db() as db:
        fila = db.execute(
            """
            SELECT probabilidad_lesion, lesionado_hasta
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

    return fila or (0.0, None)


def descansar(guild_id: int, user_id: int):
    """Reinicia la probabilidad de lesión sin curar al usuario."""

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET probabilidad_lesion = 0
            """,
            (guild_id, user_id),
        )
        db.commit()


def comprar_tratamiento(
    guild_id: int,
    user_id: int,
    tratamiento: str,
    precio: int,
    ahora: datetime,
):
    """Compra un tratamiento y actualiza el estado de lesión."""

    with conectar_db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )
        saldo, lesionado_hasta = db.execute(
            "SELECT dinero, lesionado_hasta FROM box_usuarios WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        if saldo < precio:
            db.rollback()
            return "insuficiente", saldo
        if (
            lesionado_hasta is None
            or datetime.fromisoformat(lesionado_hasta) <= ahora
        ):
            db.rollback()
            return "no_lesionado", saldo

        db.execute(
            """
            UPDATE box_usuarios
            SET dinero = dinero - ?, lesionado_hasta = NULL
            WHERE guild_id = ? AND user_id = ?
            """,
            (precio, guild_id, user_id),
        )
        if tratamiento == "tratamiento_5_estrellas":
            db.execute(
                """
                UPDATE box_usuarios
                SET probabilidad_lesion = 0
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            )
        db.commit()

    return "comprado", saldo - precio


def obtener_saldo(guild_id: int, user_id: int):
    """Devuelve experiencia y dinero del usuario."""

    with conectar_db() as db:
        fila = db.execute(
            """
            SELECT experiencia, dinero
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

    return fila or (0, 0)


def obtener_estadisticas_box(guild_id: int, user_id: int):
    """Devuelve el resumen privado de progreso y desafíos del usuario."""

    experiencia, dinero = obtener_saldo(guild_id, user_id)
    probabilidad_lesion, lesionado_hasta = obtener_estado_box(
        guild_id,
        user_id,
    )
    niveles = {}
    with conectar_db() as db:
        for mejora, nivel in db.execute(
            """
            SELECT mejora, nivel
            FROM box_mejoras
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchall():
            niveles[mejora] = nivel

        ganadas = db.execute(
            """
            SELECT COUNT(*)
            FROM box_desafios_historial
            WHERE guild_id = ? AND ganador_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()[0]
        participaciones = db.execute(
            """
            SELECT COUNT(*)
            FROM box_desafios_historial
            WHERE guild_id = ? AND (retador_id = ? OR contrincante_id = ?)
            """,
            (guild_id, user_id, user_id),
        ).fetchone()[0]

    perdidas = participaciones - ganadas
    return {
        "experiencia": experiencia,
        "dinero": dinero,
        "nivel_entrenamiento": niveles.get("entrenamiento", 0),
        "nivel_trabajo": niveles.get("trabajo", 0),
        "ganadas": ganadas,
        "perdidas": perdidas,
        "ratio": ganadas / perdidas if perdidas else float("inf"),
        "probabilidad_lesion": probabilidad_lesion,
        "lesionado_hasta": lesionado_hasta,
    }


def obtener_nivel_mejora(guild_id: int, user_id: int, mejora: str):
    """Devuelve el nivel actual de una mejora."""

    with conectar_db() as db:
        fila = db.execute(
            """
            SELECT nivel
            FROM box_mejoras
            WHERE guild_id = ? AND user_id = ? AND mejora = ?
            """,
            (guild_id, user_id, mejora),
        ).fetchone()

    return fila[0] if fila else 0


def comprar_mejora(
    guild_id: int,
    user_id: int,
    mejora: str,
    precio_base: int,
    nivel_maximo: int,
):
    """Compra un nivel de mejora descontando el dinero de forma atómica."""

    with conectar_db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )
        saldo, = db.execute(
            "SELECT dinero FROM box_usuarios WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        fila = db.execute(
            """
            SELECT nivel
            FROM box_mejoras
            WHERE guild_id = ? AND user_id = ? AND mejora = ?
            """,
            (guild_id, user_id, mejora),
        ).fetchone()
        nivel = fila[0] if fila else 0
        precio = math.ceil(precio_base * 1.25 ** nivel)

        if nivel >= nivel_maximo:
            db.rollback()
            return "maximo", saldo, nivel
        if saldo < precio:
            db.rollback()
            return "insuficiente", saldo, nivel

        db.execute(
            """
            UPDATE box_usuarios
            SET dinero = dinero - ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (precio, guild_id, user_id),
        )
        db.execute(
            """
            INSERT INTO box_mejoras (guild_id, user_id, mejora, nivel)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(guild_id, user_id, mejora)
            DO UPDATE SET nivel = nivel + 1
            """,
            (guild_id, user_id, mejora),
        )
        db.commit()

    return "comprada", saldo - precio, nivel + 1


def completar_acciones_vencidas(ahora: datetime):
    """Liquida acciones vencidas y devuelve sus datos para notificar."""

    completadas = []

    with conectar_db() as db:
        filas = db.execute(
            """
            SELECT id, guild_id, user_id, tipo, recompensa, dinero_recompensa
            FROM box_acciones
            WHERE finaliza_en <= ?
            """,
            (ahora.isoformat(),),
        ).fetchall()

        for (
            accion_id,
            guild_id,
            user_id,
            tipo,
            recompensa,
            dinero_recompensa,
        ) in filas:
            accion = db.execute(
                "SELECT iniciado_en, finaliza_en FROM box_acciones WHERE id = ?",
                (accion_id,),
            ).fetchone()
            duracion_horas = (
                datetime.fromisoformat(accion[1])
                - datetime.fromisoformat(accion[0])
            ).total_seconds() / 3600
            db.execute(
                "DELETE FROM box_acciones WHERE id = ?",
                (accion_id,),
            )
            db.execute(
                """
                INSERT INTO box_usuarios (guild_id, user_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id, user_id) DO NOTHING
                """,
                (guild_id, user_id),
            )

            probabilidad_anterior, lesionado_hasta = db.execute(
                """
                SELECT probabilidad_lesion, lesionado_hasta
                FROM box_usuarios
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()
            probabilidad = min(
                100.0,
                probabilidad_anterior + duracion_horas,
            )
            se_lesiona = random.random() < (probabilidad / 100)
            if se_lesiona:
                lesionado_hasta = (
                    ahora + timedelta(hours=3)
                ).isoformat()
            db.execute(
                """
                UPDATE box_usuarios
                SET probabilidad_lesion = ?, lesionado_hasta = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (probabilidad, lesionado_hasta, guild_id, user_id),
            )

            db.execute(
                """
                UPDATE box_usuarios
                SET experiencia = experiencia + ?,
                    dinero = dinero + ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (
                    recompensa if tipo != "TRABAJANDO" else 0,
                    dinero_recompensa,
                    guild_id,
                    user_id,
                ),
            )
            completadas.append(
                (
                    guild_id,
                    user_id,
                    tipo,
                    recompensa,
                    dinero_recompensa,
                    se_lesiona,
                )
            )

        db.commit()

    return completadas


def crear_desafio(
    guild_id: int,
    retador_id: int,
    contrincante_id: int,
    ahora: datetime,
    expira_en: datetime,
):
    """Crea un desafío pendiente."""

    with conectar_db() as db:
        try:
            db.execute(
                """
                DELETE FROM box_desafios
                WHERE expira_en <= ?
                """,
                (ahora.isoformat(),),
            )
            db.execute(
                """
                INSERT INTO box_desafios (
                    guild_id, retador_id, contrincante_id, expira_en
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    guild_id,
                    retador_id,
                    contrincante_id,
                    expira_en.isoformat(),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return None

        return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def aceptar_desafio(
    desafio_id: int,
    guild_id: int,
    contrincante_id: int,
    ahora: datetime,
    recompensa: int,
    tipo: str = "SPARRING",
    multiplicador_experiencia: int = 5,
    recompensa_por_mejora: int = 0,
):
    """Acepta un desafío y crea las dos acciones enfrentadas."""

    with conectar_db() as db:
        db.execute("BEGIN IMMEDIATE")
        desafio = db.execute(
            """
            SELECT retador_id, expira_en
            FROM box_desafios
            WHERE id = ? AND guild_id = ? AND contrincante_id = ?
            """,
            (desafio_id, guild_id, contrincante_id),
        ).fetchone()

        if desafio is None:
            return {"estado": "invalido"}

        retador_id, expira_en = desafio
        if datetime.fromisoformat(expira_en) <= ahora:
            db.execute("DELETE FROM box_desafios WHERE id = ?", (desafio_id,))
            db.commit()
            return {"estado": "expirado"}

        usuarios = db.execute(
            """
            SELECT user_id
            FROM box_acciones
            WHERE guild_id = ? AND user_id IN (?, ?)
            """,
            (guild_id, retador_id, contrincante_id),
        ).fetchall()
        if usuarios:
            db.execute("DELETE FROM box_desafios WHERE id = ?", (desafio_id,))
            db.commit()
            return {"estado": "ocupado"}

        lesionados = db.execute(
            """
            SELECT user_id
            FROM box_usuarios
            WHERE guild_id = ?
            AND user_id IN (?, ?)
            AND lesionado_hasta IS NOT NULL
            AND lesionado_hasta > ?
            """,
            (
                guild_id,
                retador_id,
                contrincante_id,
                ahora.isoformat(),
            ),
        ).fetchall()
        if lesionados:
            db.execute("DELETE FROM box_desafios WHERE id = ?", (desafio_id,))
            db.commit()
            return {"estado": "lesionado"}

        experiencias = {}
        niveles_entrenamiento = {}
        for user_id in (retador_id, contrincante_id):
            fila = db.execute(
                """
                SELECT COALESCE(experiencia, 0)
                FROM box_usuarios
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()
            experiencias[user_id] = fila[0] if fila else 0
            mejora = db.execute(
                """
                SELECT nivel
                FROM box_mejoras
                WHERE guild_id = ? AND user_id = ? AND mejora = 'entrenamiento'
                """,
                (guild_id, user_id),
            ).fetchone()
            niveles_entrenamiento[user_id] = mejora[0] if mejora else 0

        ganador_id = None
        premio_dinero = 0
        if tipo == "FIGHTING":
            ganador_id = random.SystemRandom().choices(
                [retador_id, contrincante_id],
                weights=[
                    max(experiencias[retador_id], 1),
                    max(experiencias[contrincante_id], 1),
                ],
                k=1,
            )[0]
            premio_dinero = experiencias[retador_id] + experiencias[contrincante_id]

            db.execute(
                """
                INSERT INTO box_desafios_historial (
                    guild_id, retador_id, contrincante_id,
                    ganador_id, creado_en
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    retador_id,
                    contrincante_id,
                    ganador_id,
                    ahora.isoformat(),
                ),
            )

        finaliza_en = ahora + timedelta(hours=1)
        for user_id in (retador_id, contrincante_id):
            db.execute(
                """
                INSERT INTO box_acciones (
                    guild_id, user_id, tipo, iniciado_en,
                    finaliza_en, recompensa, dinero_recompensa
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    tipo,
                    ahora.isoformat(),
                    finaliza_en.isoformat(),
                    (
                        recompensa
                        + niveles_entrenamiento[user_id] * recompensa_por_mejora
                        * multiplicador_experiencia
                    ),
                    premio_dinero if user_id == ganador_id else 0,
                ),
            )

        db.execute("DELETE FROM box_desafios WHERE id = ?", (desafio_id,))
        db.commit()
        return {
            "estado": "aceptado",
            "ganador_id": ganador_id,
            "premio_dinero": premio_dinero,
        }


def obtener_top_desafios(guild_id: int, limite: int = 10):
    """Devuelve el ranking de FIGHTING ordenado por ratio."""

    resultados = {}
    with conectar_db() as db:
        filas = db.execute(
            """
            SELECT retador_id, contrincante_id, ganador_id
            FROM box_desafios_historial
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchall()

    for retador_id, contrincante_id, ganador_id in filas:
        for user_id in (retador_id, contrincante_id):
            estadisticas = resultados.setdefault(
                user_id,
                {"ganadas": 0, "perdidas": 0},
            )
            if user_id == ganador_id:
                estadisticas["ganadas"] += 1
            else:
                estadisticas["perdidas"] += 1

    ranking = []
    for user_id, estadisticas in resultados.items():
        perdidas = estadisticas["perdidas"]
        ranking.append(
            (
                user_id,
                estadisticas["ganadas"],
                perdidas,
                estadisticas["ganadas"] / perdidas
                if perdidas
                else float("inf"),
            )
        )

    return sorted(
        ranking,
        key=lambda fila: (fila[3], fila[1]),
        reverse=True,
    )[:limite]
