from datetime import datetime, timedelta
import math
import random
import sqlite3

from core.database import conectar_db


# ============================================================
# CONFIGURACIÓN DE SPONSORS
# ============================================================

PROBABILIDAD_PROMOCION = {
    1: 5.0,
    2: 10.0,
    4: 20.0,
    8: 40.0,
    12: 60.0,
    16: 80.0,
    24: 100.0,
}

PROBABILIDAD_SPONSORS = {
    "redes": 50,
    "radio": 30,
    "equipamiento": 15,
    "medico": 5,
}

DURACION_SPONSOR = {
    "redes": timedelta(days=7),
    "radio": timedelta(days=7),
    "equipamiento": timedelta(days=14),
    "medico": timedelta(days=30),
}

PAGO_SPONSOR = {
    "redes": 500,
    "radio": 1000,
}

MAX_SPONSORS = {
    "redes": 10,
    "radio": 10,
}


def inicializar_db():
    """Crea las tablas de progreso, acciones y sponsors de Box."""

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
                """
                ALTER TABLE box_usuarios
                ADD COLUMN probabilidad_lesion REAL NOT NULL DEFAULT 0
                """
            )

        if "lesionado_hasta" not in columnas_usuario:
            db.execute(
                """
                ALTER TABLE box_usuarios
                ADD COLUMN lesionado_hasta TEXT
                """
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

        # ====================================================
        # SPONSORS
        # ====================================================

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS box_sponsors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                obtenido_en TEXT NOT NULL,
                expira_en TEXT NOT NULL,
                ultimo_pago TEXT,
                ultimo_tratamiento TEXT
            )
            """
        )

        db.commit()


# ============================================================
# ACCIONES
# ============================================================

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


# ============================================================
# ESTADO DEL USUARIO
# ============================================================

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
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET probabilidad_lesion = 0
            """,
            (guild_id, user_id),
        )
        db.commit()


# ============================================================
# TRATAMIENTOS
# ============================================================

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
            """
            SELECT dinero, lesionado_hasta
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
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
            SET dinero = dinero - ?,
                lesionado_hasta = NULL
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


# ============================================================
# SALDO / ESTADÍSTICAS
# ============================================================

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
            WHERE guild_id = ?
            AND (retador_id = ? OR contrincante_id = ?)
            """,
            (guild_id, user_id, user_id),
        ).fetchone()[0]

        sponsors = db.execute(
            """
            SELECT tipo, COUNT(*)
            FROM box_sponsors
            WHERE guild_id = ?
            AND user_id = ?
            AND expira_en > ?
            GROUP BY tipo
            """,
            (
                guild_id,
                user_id,
                datetime.now().isoformat(),
            ),
        ).fetchall()

    sponsors_activos = {
        tipo: cantidad
        for tipo, cantidad in sponsors
    }

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
        "sponsors": sponsors_activos,
    }


# ============================================================
# MEJORAS
# ============================================================

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
            """
            SELECT dinero
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
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
            INSERT INTO box_mejoras (
                guild_id, user_id, mejora, nivel
            )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(guild_id, user_id, mejora)
            DO UPDATE SET nivel = nivel + 1
            """,
            (guild_id, user_id, mejora),
        )

        db.commit()

    return "comprada", saldo - precio, nivel + 1


# ============================================================
# SPONSORS
# ============================================================

def _probabilidad_promocion(minutos: float) -> float:
    """Calcula la probabilidad de conseguir sponsor según el tiempo."""

    horas = minutos / 60

    if horas <= 1:
        return 5.0

    puntos = sorted(PROBABILIDAD_PROMOCION.items())

    if horas >= puntos[-1][0]:
        return puntos[-1][1]

    for (hora_a, prob_a), (hora_b, prob_b) in zip(
        puntos,
        puntos[1:],
    ):
        if hora_a <= horas <= hora_b:
            proporcion = (horas - hora_a) / (hora_b - hora_a)
            return prob_a + (
                (prob_b - prob_a) * proporcion
            )

    return 5.0


def _sortear_sponsor():
    """Sortear el tipo de sponsor según sus probabilidades."""

    return random.SystemRandom().choices(
        list(PROBABILIDAD_SPONSORS.keys()),
        weights=list(PROBABILIDAD_SPONSORS.values()),
        k=1,
    )[0]


def _contar_sponsors_activos(
    db,
    guild_id: int,
    user_id: int,
    tipo: str,
    ahora: datetime,
):
    return db.execute(
        """
        SELECT COUNT(*)
        FROM box_sponsors
        WHERE guild_id = ?
        AND user_id = ?
        AND tipo = ?
        AND expira_en > ?
        """,
        (
            guild_id,
            user_id,
            tipo,
            ahora.isoformat(),
        ),
    ).fetchone()[0]


def _crear_sponsor(
    db,
    guild_id: int,
    user_id: int,
    tipo: str,
    ahora: datetime,
):
    """Crea un sponsor individual."""

    limite = MAX_SPONSORS.get(tipo)

    if limite is not None:
        cantidad = _contar_sponsors_activos(
            db,
            guild_id,
            user_id,
            tipo,
            ahora,
        )

        if cantidad >= limite:
            return False

    expira_en = ahora + DURACION_SPONSOR[tipo]

    db.execute(
        """
        INSERT INTO box_sponsors (
            guild_id,
            user_id,
            tipo,
            obtenido_en,
            expira_en,
            ultimo_pago,
            ultimo_tratamiento
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            user_id,
            tipo,
            ahora.isoformat(),
            expira_en.isoformat(),
            ahora.isoformat()
            if tipo in PAGO_SPONSOR
            else None,
            ahora.isoformat()
            if tipo == "medico"
            else None,
        ),
    )

    return True


def obtener_sponsors_activos(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """Devuelve los sponsors actualmente activos."""

    with conectar_db() as db:
        return db.execute(
            """
            SELECT id, tipo, obtenido_en, expira_en,
                   ultimo_pago, ultimo_tratamiento
            FROM box_sponsors
            WHERE guild_id = ?
            AND user_id = ?
            AND expira_en > ?
            ORDER BY expira_en ASC
            """,
            (
                guild_id,
                user_id,
                ahora.isoformat(),
            ),
        ).fetchall()


def obtener_bonus_experiencia_sponsor(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """Devuelve el bonus porcentual de EXP de Equipamiento."""

    with conectar_db() as db:
        cantidad = _contar_sponsors_activos(
            db,
            guild_id,
            user_id,
            "equipamiento",
            ahora,
        )

    return cantidad * 10


def obtener_sponsor_para_promocion(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """
    Devuelve un sponsor aleatorio si el usuario consigue uno
    por promocionarse.
    """

    tipo = _sortear_sponsor()

    with conectar_db() as db:
        db.execute("BEGIN IMMEDIATE")

        creado = _crear_sponsor(
            db,
            guild_id,
            user_id,
            tipo,
            ahora,
        )

        if not creado:
            db.rollback()
            return None

        db.commit()

    return tipo


def procesar_pagos_sponsors(ahora: datetime):
    """
    Procesa los pagos diarios de Redes y Radio.

    Cada sponsor tiene su propio ciclo de 24 horas.
    """

    pagos = []

    with conectar_db() as db:
        db.execute("BEGIN IMMEDIATE")

        sponsors = db.execute(
            """
            SELECT id, guild_id, user_id, tipo,
                   ultimo_pago, expira_en
            FROM box_sponsors
            WHERE tipo IN ('redes', 'radio')
            AND expira_en > ?
            """,
            (ahora.isoformat(),),
        ).fetchall()

        for (
            sponsor_id,
            guild_id,
            user_id,
            tipo,
            ultimo_pago,
            expira_en,
        ) in sponsors:

            if ultimo_pago is None:
                ultimo_pago_dt = ahora
            else:
                ultimo_pago_dt = datetime.fromisoformat(
                    ultimo_pago
                )

            horas_transcurridas = (
                ahora - ultimo_pago_dt
            ).total_seconds() / 3600

            pagos_pendientes = int(horas_transcurridas // 24)

            if pagos_pendientes <= 0:
                continue

            pago = PAGO_SPONSOR[tipo] * pagos_pendientes

            db.execute(
                """
                INSERT INTO box_usuarios (
                    guild_id,
                    user_id
                )
                VALUES (?, ?)
                ON CONFLICT(guild_id, user_id) DO NOTHING
                """,
                (guild_id, user_id),
            )

            db.execute(
                """
                UPDATE box_usuarios
                SET dinero = dinero + ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (
                    pago,
                    guild_id,
                    user_id,
                ),
            )

            nuevo_ultimo_pago = (
                ultimo_pago_dt
                + timedelta(days=pagos_pendientes)
            )

            # No permitir que el siguiente pago quede programado
            # después de la fecha de vencimiento.
            expira_dt = datetime.fromisoformat(expira_en)

            if nuevo_ultimo_pago > expira_dt:
                nuevo_ultimo_pago = expira_dt

            db.execute(
                """
                UPDATE box_sponsors
                SET ultimo_pago = ?
                WHERE id = ?
                """,
                (
                    nuevo_ultimo_pago.isoformat(),
                    sponsor_id,
                ),
            )

            pagos.append(
                (
                    guild_id,
                    user_id,
                    tipo,
                    pago,
                )
            )

        db.commit()

    return pagos


def procesar_sponsors_medicos(ahora: datetime):
    """
    Aplica una reducción del 50% a la probabilidad de lesión
    una vez cada 24 horas por sponsor médico.
    """

    procesados = []

    with conectar_db() as db:
        db.execute("BEGIN IMMEDIATE")

        sponsors = db.execute(
            """
            SELECT id, guild_id, user_id,
                   ultimo_tratamiento, expira_en
            FROM box_sponsors
            WHERE tipo = 'medico'
            AND expira_en > ?
            """,
            (ahora.isoformat(),),
        ).fetchall()

        for (
            sponsor_id,
            guild_id,
            user_id,
            ultimo_tratamiento,
            expira_en,
        ) in sponsors:

            if ultimo_tratamiento is None:
                ultimo_tratamiento_dt = (
                    ahora - timedelta(days=1)
                )
            else:
                ultimo_tratamiento_dt = datetime.fromisoformat(
                    ultimo_tratamiento
                )

            horas_transcurridas = (
                ahora - ultimo_tratamiento_dt
            ).total_seconds() / 3600

            tratamientos_pendientes = int(
                horas_transcurridas // 24
            )

            if tratamientos_pendientes <= 0:
                continue

            fila = db.execute(
                """
                SELECT probabilidad_lesion
                FROM box_usuarios
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()

            if fila is None:
                probabilidad = 0.0
            else:
                probabilidad = float(fila[0])

            for _ in range(tratamientos_pendientes):
                probabilidad *= 0.5

            db.execute(
                """
                INSERT INTO box_usuarios (
                    guild_id,
                    user_id
                )
                VALUES (?, ?)
                ON CONFLICT(guild_id, user_id) DO NOTHING
                """,
                (guild_id, user_id),
            )

            db.execute(
                """
                UPDATE box_usuarios
                SET probabilidad_lesion = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (
                    probabilidad,
                    guild_id,
                    user_id,
                ),
            )

            nuevo_ultimo_tratamiento = (
                ultimo_tratamiento_dt
                + timedelta(days=tratamientos_pendientes)
            )

            expira_dt = datetime.fromisoformat(expira_en)

            if nuevo_ultimo_tratamiento > expira_dt:
                nuevo_ultimo_tratamiento = expira_dt

            db.execute(
                """
                UPDATE box_sponsors
                SET ultimo_tratamiento = ?
                WHERE id = ?
                """,
                (
                    nuevo_ultimo_tratamiento.isoformat(),
                    sponsor_id,
                ),
            )

            procesados.append(
                (
                    guild_id,
                    user_id,
                    probabilidad,
                )
            )

        db.commit()

    return procesados


# ============================================================
# COMPLETAR ACCIONES
# ============================================================

def completar_acciones_vencidas(ahora: datetime):
    """
    Liquida acciones vencidas y devuelve sus datos para notificar.

    PROMOVIENDO es una acción especial:
    - No da EXP.
    - No da dinero.
    - No genera lesión.
    - Tiene una probabilidad de conseguir sponsor.
    """

    completadas = []

    with conectar_db() as db:
        filas = db.execute(
            """
            SELECT
                id,
                guild_id,
                user_id,
                tipo,
                recompensa,
                dinero_recompensa,
                iniciado_en,
                finaliza_en
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
            iniciado_en,
            finaliza_en,
        ) in filas:

            duracion_horas = (
                datetime.fromisoformat(finaliza_en)
                - datetime.fromisoformat(iniciado_en)
            ).total_seconds() / 3600

            db.execute(
                "DELETE FROM box_acciones WHERE id = ?",
                (accion_id,),
            )

            db.execute(
                """
                INSERT INTO box_usuarios (
                    guild_id,
                    user_id
                )
                VALUES (?, ?)
                ON CONFLICT(guild_id, user_id) DO NOTHING
                """,
                (guild_id, user_id),
            )

            # =================================================
            # PROMOCIÓN
            # =================================================

            if tipo == "PROMOVIENDO":
                minutos = duracion_horas * 60
                probabilidad_sponsor = _probabilidad_promocion(
                    minutos
                )

                consiguio_sponsor = (
                    random.random()
                    < probabilidad_sponsor / 100
                )

                sponsor = None

                if consiguio_sponsor:
                    sponsor = _sortear_sponsor()

                    creado = _crear_sponsor(
                        db,
                        guild_id,
                        user_id,
                        sponsor,
                        ahora,
                    )

                    if not creado:
                        sponsor = None

                completadas.append(
                    (
                        guild_id,
                        user_id,
                        tipo,
                        0,
                        0,
                        False,
                        probabilidad_sponsor,
                        sponsor,
                    )
                )

                continue

            # =================================================
            # ACCIONES NORMALES
            # =================================================

            probabilidad_anterior, lesionado_hasta = db.execute(
                """
                SELECT
                    probabilidad_lesion,
                    lesionado_hasta
                FROM box_usuarios
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()

            probabilidad = min(
                100.0,
                probabilidad_anterior + duracion_horas,
            )

            se_lesiona = random.random() < (
                probabilidad / 100
            )

            if se_lesiona:
                lesionado_hasta = (
                    ahora + timedelta(hours=3)
                ).isoformat()

            db.execute(
                """
                UPDATE box_usuarios
                SET
                    probabilidad_lesion = ?,
                    lesionado_hasta = ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (
                    probabilidad,
                    lesionado_hasta,
                    guild_id,
                    user_id,
                ),
            )

            # Bonus de Equipamiento.
            bonus_exp = _contar_sponsors_activos(
                db,
                guild_id,
                user_id,
                "equipamiento",
                ahora,
            )

            recompensa_final = recompensa

            if bonus_exp:
                recompensa_final = math.floor(
                    recompensa
                    * (1 + (bonus_exp * 0.10))
                )

            db.execute(
                """
                UPDATE box_usuarios
                SET
                    experiencia = experiencia + ?,
                    dinero = dinero + ?
                WHERE guild_id = ? AND user_id = ?
                """,
                (
                    recompensa_final
                    if tipo != "TRABAJANDO"
                    else 0,
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
                    recompensa_final,
                    dinero_recompensa,
                    se_lesiona,
                    None,
                    None,
                )
            )

        db.commit()

    # Los sponsors se procesan cada vez que el sistema
    # comprueba acciones vencidas.
    #
    # Esto permite que los pagos y tratamientos sigan
    # funcionando aunque el bot haya estado reiniciado.
    procesar_pagos_sponsors(ahora)
    procesar_sponsors_medicos(ahora)

    return completadas


# ============================================================
# DESAFÍOS
# ============================================================

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
                    guild_id,
                    retador_id,
                    contrincante_id,
                    expira_en
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

        return db.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]


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
            WHERE id = ?
            AND guild_id = ?
            AND contrincante_id = ?
            """,
            (
                desafio_id,
                guild_id,
                contrincante_id,
            ),
        ).fetchone()

        if desafio is None:
            return {"estado": "invalido"}

        retador_id, expira_en = desafio

        if datetime.fromisoformat(expira_en) <= ahora:
            db.execute(
                "DELETE FROM box_desafios WHERE id = ?",
                (desafio_id,),
            )
            db.commit()
            return {"estado": "expirado"}

        usuarios = db.execute(
            """
            SELECT user_id
            FROM box_acciones
            WHERE guild_id = ?
            AND user_id IN (?, ?)
            """,
            (
                guild_id,
                retador_id,
                contrincante_id,
            ),
        ).fetchall()

        if usuarios:
            db.execute(
                "DELETE FROM box_desafios WHERE id = ?",
                (desafio_id,),
            )
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
            db.execute(
                "DELETE FROM box_desafios WHERE id = ?",
                (desafio_id,),
            )
            db.commit()
            return {"estado": "lesionado"}

        experiencias = {}
        niveles_entrenamiento = {}

        for user_id in (
            retador_id,
            contrincante_id,
        ):
            fila = db.execute(
                """
                SELECT COALESCE(experiencia, 0)
                FROM box_usuarios
                WHERE guild_id = ? AND user_id = ?
                """,
                (
                    guild_id,
                    user_id,
                ),
            ).fetchone()

            experiencias[user_id] = (
                fila[0] if fila else 0
            )

            mejora = db.execute(
                """
                SELECT nivel
                FROM box_mejoras
                WHERE guild_id = ?
                AND user_id = ?
                AND mejora = 'entrenamiento'
                """,
                (
                    guild_id,
                    user_id,
                ),
            ).fetchone()

            niveles_entrenamiento[user_id] = (
                mejora[0] if mejora else 0
            )

        ganador_id = None
        premio_dinero = 0

        if tipo == "FIGHTING":
            ganador_id = random.SystemRandom().choices(
                [
                    retador_id,
                    contrincante_id,
                ],
                weights=[
                    max(
                        experiencias[retador_id],
                        1,
                    ),
                    max(
                        experiencias[contrincante_id],
                        1,
                    ),
                ],
                k=1,
            )[0]

            premio_dinero = (
                experiencias[retador_id]
                + experiencias[contrincante_id]
            )

            db.execute(
                """
                INSERT INTO box_desafios_historial (
                    guild_id,
                    retador_id,
                    contrincante_id,
                    ganador_id,
                    creado_en
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

        for user_id in (
            retador_id,
            contrincante_id,
        ):
            recompensa_usuario = (
                recompensa
                + niveles_entrenamiento[user_id]
                * recompensa_por_mejora
                * multiplicador_experiencia
            )

            # Bonus temporal de Equipamiento.
            recompensa_usuario = (
                recompensa
                + niveles_entrenamiento[user_id]
                * recompensa_por_mejora
                * multiplicador_experiencia
            )

            db.execute(
                """
                INSERT INTO box_acciones (
                    guild_id,
                    user_id,
                    tipo,
                    iniciado_en,
                    finaliza_en,
                    recompensa,
                    dinero_recompensa
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    user_id,
                    tipo,
                    ahora.isoformat(),
                    finaliza_en.isoformat(),
                    recompensa_usuario,
                    premio_dinero
                    if user_id == ganador_id
                    else 0,
                ),
            )

        db.execute(
            "DELETE FROM box_desafios WHERE id = ?",
            (desafio_id,),
        )

        db.commit()

        return {
            "estado": "aceptado",
            "ganador_id": ganador_id,
            "premio_dinero": premio_dinero,
        }


# ============================================================
# RANKING DE DESAFÍOS
# ============================================================

def obtener_top_desafios(
    guild_id: int,
    limite: int = 10,
):
    """Devuelve el ranking de FIGHTING ordenado por ratio."""

    resultados = {}

    with conectar_db() as db:
        filas = db.execute(
            """
            SELECT
                retador_id,
                contrincante_id,
                ganador_id
            FROM box_desafios_historial
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchall()

    for (
        retador_id,
        contrincante_id,
        ganador_id,
    ) in filas:

        for user_id in (
            retador_id,
            contrincante_id,
        ):
            estadisticas = resultados.setdefault(
                user_id,
                {
                    "ganadas": 0,
                    "perdidas": 0,
                },
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
                (
                    estadisticas["ganadas"]
                    / perdidas
                    if perdidas
                    else float("inf")
                ),
            )
        )

    return sorted(
        ranking,
        key=lambda fila: (
            fila[3],
            fila[1],
        ),
        reverse=True,
    )[:limite]