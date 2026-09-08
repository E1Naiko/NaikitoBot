from datetime import datetime, timedelta
import math
import random
import sqlite3

from config import (
    BOX_CANSANCIO_INICIAL,
    BOX_DANO_INICIAL,
    BOX_DANO_MAXIMO,
    BOX_DEFENSA_INICIAL,
    BOX_DEFENSA_MAXIMO,
    BOX_DESAFIO_DURACION_HORAS,
    BOX_DESAFIO_EXP_SPARRING,
    BOX_LESION_DECAIMIENTO_POR_HORA,
    BOX_LESION_HORAS,
    BOX_LESION_PROBABILIDAD_MAXIMA,
    BOX_LESION_PROBABILIDAD_POR_HORA,
    BOX_MEDICO_CICLO_HORAS,
    BOX_MEDICO_REDUCCION,
    BOX_PROMOCION_PROBABILIDAD,
    BOX_SPONSOR_CICLO_PAGO_HORAS,
    BOX_SPONSOR_DURACION_DIAS,
    BOX_SPONSOR_EQUIPAMIENTO_BONUS,
    BOX_SPONSOR_MAXIMO,
    BOX_SPONSOR_PAGO,
    BOX_SPONSOR_PROBABILIDAD,
    BOX_VIDA_INICIAL,
)

from core.database import conectar_db
from modules.box.logic import precio_mejora


# ============================================================
# CONFIGURACIÓN DE SPONSORS
# ============================================================
#
# Los valores se leen del .env (variables BOX_SPONSOR_*) y se validan
# al arrancar en config/settings.py. Acá solo se adaptan al formato
# que usa el resto del módulo.

PROBABILIDAD_PROMOCION = BOX_PROMOCION_PROBABILIDAD

PROBABILIDAD_SPONSORS = BOX_SPONSOR_PROBABILIDAD

DURACION_SPONSOR = {
    tipo: timedelta(days=dias)
    for tipo, dias in BOX_SPONSOR_DURACION_DIAS.items()
}

PAGO_SPONSOR = BOX_SPONSOR_PAGO

MAX_SPONSORS = BOX_SPONSOR_MAXIMO


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
        db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS box_equipo (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vida INTEGER NOT NULL DEFAULT {BOX_VIDA_INICIAL},
                vida_maxima INTEGER NOT NULL DEFAULT {BOX_VIDA_INICIAL},
                dano INTEGER NOT NULL DEFAULT {BOX_DANO_INICIAL},
                dano_maximo INTEGER NOT NULL DEFAULT {BOX_DANO_MAXIMO},
                defensa INTEGER NOT NULL DEFAULT {BOX_DEFENSA_INICIAL},
                defensa_maxima INTEGER NOT NULL DEFAULT {BOX_DEFENSA_MAXIMO},
                cansancio INTEGER NOT NULL DEFAULT {BOX_CANSANCIO_INICIAL},
                cansancio_maximo INTEGER NOT NULL DEFAULT {BOX_CANSANCIO_INICIAL},
                puntos_habilidad INTEGER NOT NULL DEFAULT 0,
                casco INTEGER NOT NULL DEFAULT 0,
                guantes INTEGER NOT NULL DEFAULT 0,
                protector_bucal INTEGER NOT NULL DEFAULT 0,
                short INTEGER NOT NULL DEFAULT 0,
                botas INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
            """)

        # Migrar columnas de texto a enteros si es necesario
        columnas_equipo = {
            columna[1]
            for columna in db.execute("PRAGMA table_info(box_equipo)")
        }
        if columnas_equipo and any(col in columnas_equipo for col in ["casco", "guantes"]):
            # Verificar si son TEXT y migrar si es necesario
            tipo_casco = db.execute(
                "PRAGMA table_info(box_equipo)"
            ).fetchall()
            for columna in tipo_casco:
                if columna[1] == "casco" and columna[2] == "text":
                    # La migración ya se hizo arriba al crear la tabla con INTEGER
                    pass

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
# DECAIMIENTO DE LA PROBABILIDAD
# ============================================================

def reducir_probabilidad_lesion_inactivos(
    cantidad: float = 0.01,
) -> int:
    """
    Reduce la probabilidad de lesión de los usuarios sin acción activa.

    Cada llamada representa una hora sin entrenar ni trabajar: baja la
    probabilidad en ``cantidad`` puntos porcentuales, sin pasar de 0.
    Aplica también a usuarios lesionados (una lesión no es una acción).
    """

    with conectar_db() as db:
        cursor = db.execute(
            """
            UPDATE box_usuarios
            SET probabilidad_lesion = CASE
                WHEN probabilidad_lesion - ? < 0 THEN 0
                ELSE probabilidad_lesion - ?
            END
            WHERE probabilidad_lesion > 0
            AND NOT EXISTS (
                SELECT 1
                FROM box_acciones
                WHERE box_acciones.guild_id = box_usuarios.guild_id
                AND box_acciones.user_id = box_usuarios.user_id
            )
            """,
            (cantidad, cantidad),
        )
        db.commit()

    return cursor.rowcount


# ============================================================
# TRATAMIENTOS
# ============================================================

def comprar_tratamiento(
    guild_id: int,
    user_id: int,
    precio: int,
    ahora: datetime,
    reinicia_probabilidad: bool = False,
):
    """Compra un tratamiento, cura la lesión y opcionalmente resetea la probabilidad."""

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

        if reinicia_probabilidad:
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
# SUMINISTROS DE RECUPERACIÓN
# ============================================================

def usar_suministro(
    guild_id: int,
    user_id: int,
    objetivo: str,
    precio: int,
    ahora: datetime,
):
    """Usa un suministro y restaura al máximo la estadística indicada.

    ``objetivo`` puede ser ``vida``, ``cansancio``, ``defensa`` o ``lesion``.
    Si la estadística ya está al máximo (o no hay lesión ni probabilidad que
    curar), no descuenta dinero y devuelve el estado correspondiente.
    """

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

        saldo, probabilidad_lesion, lesionado_hasta = db.execute(
            """
            SELECT dinero, probabilidad_lesion, lesionado_hasta
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        db.execute(
            """
            INSERT INTO box_equipo (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )

        vida, vida_maxima, cansancio, cansancio_maximo, defensa, defensa_maxima = (
            db.execute(
                """
                SELECT vida, vida_maxima, cansancio, cansancio_maximo,
                       defensa, defensa_maxima
                FROM box_equipo
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()
        )

        # ----------------------------------------------------
        # COMPROBAR SI LA ESTADÍSTICA NECESITA RECUPERACIÓN
        # ----------------------------------------------------

        aplica = True

        if objetivo == "vida":
            aplica = vida < vida_maxima
        elif objetivo == "cansancio":
            aplica = cansancio < cansancio_maximo
        elif objetivo == "defensa":
            aplica = defensa < defensa_maxima
        elif objetivo == "lesion":
            lesionado_activo = (
                lesionado_hasta is not None
                and datetime.fromisoformat(lesionado_hasta) > ahora
            )
            aplica = lesionado_activo or probabilidad_lesion > 0
        else:
            db.rollback()
            return "objetivo_invalido", saldo

        if not aplica:
            db.rollback()
            if objetivo == "lesion":
                return "sin_lesion", saldo
            return "lleno", saldo

        # ----------------------------------------------------
        # COBRO Y APLICACIÓN
        # ----------------------------------------------------

        if saldo < precio:
            db.rollback()
            return "insuficiente", saldo

        db.execute(
            """
            UPDATE box_usuarios
            SET dinero = dinero - ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (precio, guild_id, user_id),
        )

        if objetivo == "vida":
            db.execute(
                """
                UPDATE box_equipo
                SET vida = vida_maxima
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            )
        elif objetivo == "cansancio":
            db.execute(
                """
                UPDATE box_equipo
                SET cansancio = cansancio_maximo
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            )
        elif objetivo == "defensa":
            db.execute(
                """
                UPDATE box_equipo
                SET defensa = defensa_maxima
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            )
        else:
            db.execute(
                """
                UPDATE box_usuarios
                SET lesionado_hasta = NULL,
                    probabilidad_lesion = 0
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
        precio = precio_mejora(precio_base, nivel)

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
    """Calcula la probabilidad de conseguir sponsor según el tiempo.

    Usa la curva configurada en ``BOX_PROMOCION_PROBABILIDAD``
    (puntos 'horas=porcentaje' interpolados linealmente); por debajo
    del primer punto vale el primero, y por encima del último, el
    último.
    """

    horas = minutos / 60

    puntos = PROBABILIDAD_PROMOCION

    if horas <= puntos[0][0]:
        return puntos[0][1]

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

    return puntos[-1][1]


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
                probabilidad *= (
                    1 - BOX_MEDICO_REDUCCION / 100
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

def _liquidar_accion(db, fila, ahora: datetime):
    """Liquida una única acción vencida y devuelve sus datos para notificar.

    PROMOVIENDO es una acción especial:
    - No da EXP.
    - No da dinero.
    - No genera lesión.
    - Tiene una probabilidad de conseguir sponsor.
    """

    (
        accion_id,
        guild_id,
        user_id,
        tipo,
        recompensa,
        dinero_recompensa,
        iniciado_en,
        finaliza_en,
    ) = fila

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

        return (
            guild_id,
            user_id,
            tipo,
            0,
            0,
            False,
            probabilidad_sponsor,
            sponsor,
        )

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
            * (1 + (bonus_exp * BOX_SPONSOR_EQUIPAMIENTO_BONUS / 100))
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

    return (
        guild_id,
        user_id,
        tipo,
        recompensa_final,
        dinero_recompensa,
        se_lesiona,
        None,
        None,
    )


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

        for fila in filas:
            completadas.append(
                _liquidar_accion(db, fila, ahora)
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


def admin_completar_acciones_vencidas(guild_id: int, ahora: datetime):
    """
    Liquida las acciones vencidas de un único servidor.

    Es la versión manual de ``completar_acciones_vencidas`` para
    mantenimiento administrativo, sin tocar las de otros servidores.
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
            WHERE guild_id = ?
            AND finaliza_en <= ?
            """,
            (guild_id, ahora.isoformat()),
        ).fetchall()

        for fila in filas:
            completadas.append(
                _liquidar_accion(db, fila, ahora)
            )

        db.commit()

    # Igual que la versión global, los sponsors se procesan
    # siempre: sus ciclos internos evitan pagos duplicados.
    procesar_pagos_sponsors(ahora)
    procesar_sponsors_medicos(ahora)

    return completadas


def admin_finalizar_accion(
    guild_id: int,
    user_id: int,
    ahora: datetime,
):
    """Liquida la acción ya vencida de un único usuario.

    Devuelve los mismos datos que ``_liquidar_accion`` o ``None``
    si el usuario no tiene una acción vencida pendiente.
    """

    with conectar_db() as db:
        fila = db.execute(
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
            WHERE guild_id = ?
            AND user_id = ?
            AND finaliza_en <= ?
            ORDER BY finaliza_en ASC
            LIMIT 1
            """,
            (guild_id, user_id, ahora.isoformat()),
        ).fetchone()

        if fila is None:
            return None

        completada = _liquidar_accion(db, fila, ahora)

        db.commit()

    procesar_pagos_sponsors(ahora)
    procesar_sponsors_medicos(ahora)

    return completada


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

        finaliza_en = ahora + timedelta(hours=BOX_DESAFIO_DURACION_HORAS)

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

def obtener_equipo(guild_id: int, user_id: int):
    """Devuelve el equipo del usuario, inicializando si es necesario."""

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_equipo (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )
        fila = db.execute(
            """
            SELECT vida, vida_maxima, dano, dano_maximo, defensa, 
                   defensa_maxima, cansancio, cansancio_maximo, 
                   puntos_habilidad, casco, guantes, protector_bucal, 
                   short, botas
            FROM box_equipo
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()
        db.commit()

    if fila:
        return {
            "vida": fila[0],
            "vida_maxima": fila[1],
            "dano": fila[2],
            "dano_maximo": fila[3],
            "defensa": fila[4],
            "defensa_maxima": fila[5],
            "cansancio": fila[6],
            "cansancio_maximo": fila[7],
            "puntos_habilidad": fila[8],
            "casco": fila[9],
            "guantes": fila[10],
            "protector_bucal": fila[11],
            "short": fila[12],
            "botas": fila[13],
        }
    return None


def actualizar_equipo(
    guild_id: int,
    user_id: int,
    vida: int | None = None,
    dano: int | None = None,
    defensa: int | None = None,
    cansancio: int | None = None,
    puntos_habilidad: int | None = None,
    casco: str | None = None,
    guantes: str | None = None,
    protector_bucal: str | None = None,
    short: str | None = None,
    botas: str | None = None,
):
    """Actualiza estadísticas o equipamiento del usuario."""

    actualizaciones = []
    valores = []

    if vida is not None:
        actualizaciones.append("vida = ?")
        valores.append(vida)
    if dano is not None:
        actualizaciones.append("dano = ?")
        valores.append(dano)
    if defensa is not None:
        actualizaciones.append("defensa = ?")
        valores.append(defensa)
    if cansancio is not None:
        actualizaciones.append("cansancio = ?")
        valores.append(cansancio)
    if puntos_habilidad is not None:
        actualizaciones.append("puntos_habilidad = ?")
        valores.append(puntos_habilidad)
    if casco is not None:
        actualizaciones.append("casco = ?")
        valores.append(casco)
    if guantes is not None:
        actualizaciones.append("guantes = ?")
        valores.append(guantes)
    if protector_bucal is not None:
        actualizaciones.append("protector_bucal = ?")
        valores.append(protector_bucal)
    if short is not None:
        actualizaciones.append("short = ?")
        valores.append(short)
    if botas is not None:
        actualizaciones.append("botas = ?")
        valores.append(botas)

    if not actualizaciones:
        return False

    valores.extend([guild_id, user_id])

    with conectar_db() as db:
        db.execute(
            f"""
            UPDATE box_equipo
            SET {", ".join(actualizaciones)}
            WHERE guild_id = ? AND user_id = ?
            """,
            valores,
        )
        db.commit()

    return True


def comprar_equipamiento_progresivo(
    guild_id: int,
    user_id: int,
    tipo_equipo: str,
    precio_base: int,
    nivel_maximo: int = 4,
):
    """Compra un nivel de equipamiento progresivamente (cada mejora cuesta el doble)."""

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

        db.execute(
            """
            INSERT INTO box_equipo (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )
        
        nivel_actual, = db.execute(
            f"""
            SELECT {tipo_equipo} FROM box_equipo
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        # Calcular precio: precio_base * 2^nivel
        precio = precio_base * (2 ** nivel_actual)

        if nivel_actual >= nivel_maximo:
            db.rollback()
            return "maximo", saldo, nivel_actual

        if saldo < precio:
            db.rollback()
            return "insuficiente", saldo, nivel_actual

        db.execute(
            """
            UPDATE box_usuarios
            SET dinero = dinero - ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (precio, guild_id, user_id),
        )
        db.execute(
            f"""
            UPDATE box_equipo
            SET {tipo_equipo} = {tipo_equipo} + 1
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        db.commit()

    return "comprado", saldo - precio, nivel_actual + 1

# ============================================================
# ADMINISTRACIÓN
# ============================================================

def admin_obtener_info_usuario(
    guild_id: int,
    user_id: int,
):
    """Devuelve toda la información administrativa del Box."""

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )

        usuario = db.execute(
            """
            SELECT experiencia,
                   dinero,
                   probabilidad_lesion,
                   lesionado_hasta
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        mejoras = db.execute(
            """
            SELECT mejora, nivel
            FROM box_mejoras
            WHERE guild_id = ? AND user_id = ?
            ORDER BY mejora
            """,
            (guild_id, user_id),
        ).fetchall()

        accion = db.execute(
            """
            SELECT tipo,
                   iniciado_en,
                   finaliza_en,
                   recompensa,
                   dinero_recompensa
            FROM box_acciones
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        sponsors = db.execute(
            """
            SELECT id,
                   tipo,
                   obtenido_en,
                   expira_en,
                   ultimo_pago,
                   ultimo_tratamiento
            FROM box_sponsors
            WHERE guild_id = ?
            AND user_id = ?
            AND expira_en > ?
            ORDER BY expira_en ASC
            """,
            (
                guild_id,
                user_id,
                datetime.now().isoformat(),
            ),
        ).fetchall()

        equipo = db.execute(
            """
            SELECT vida,
                   vida_maxima,
                   dano,
                   dano_maximo,
                   defensa,
                   defensa_maxima,
                   cansancio,
                   cansancio_maximo,
                   puntos_habilidad,
                   casco,
                   guantes,
                   protector_bucal,
                   short,
                   botas
            FROM box_equipo
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        desafios_pendientes = db.execute(
            """
            SELECT COUNT(*)
            FROM box_desafios
            WHERE guild_id = ?
            AND (retador_id = ? OR contrincante_id = ?)
            """,
            (guild_id, user_id, user_id),
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

        victorias = db.execute(
            """
            SELECT COUNT(*)
            FROM box_desafios_historial
            WHERE guild_id = ?
            AND ganador_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()[0]

        db.commit()

    return {
        "experiencia": usuario[0],
        "dinero": usuario[1],
        "probabilidad_lesion": usuario[2],
        "lesionado_hasta": usuario[3],
        "mejoras": dict(mejoras),
        "accion": accion,
        "sponsors": sponsors,
        "equipo": equipo,
        "desafios_pendientes": desafios_pendientes,
        "participaciones": participaciones,
        "victorias": victorias,
    }


def admin_modificar_dinero(
    guild_id: int,
    user_id: int,
    cantidad: int,
):
    """Modifica el dinero de un usuario."""

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )

        saldo_actual, = db.execute(
            """
            SELECT dinero
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        nuevo_saldo = saldo_actual + cantidad

        if nuevo_saldo < 0:
            db.rollback()
            return False, saldo_actual

        db.execute(
            """
            UPDATE box_usuarios
            SET dinero = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (nuevo_saldo, guild_id, user_id),
        )

        db.commit()

    return True, nuevo_saldo


def admin_modificar_experiencia(
    guild_id: int,
    user_id: int,
    cantidad: int,
):
    """Modifica la experiencia de un usuario."""

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (guild_id, user_id),
        )

        experiencia_actual, = db.execute(
            """
            SELECT experiencia
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        nueva_experiencia = experiencia_actual + cantidad

        if nueva_experiencia < 0:
            db.rollback()
            return False, experiencia_actual

        db.execute(
            """
            UPDATE box_usuarios
            SET experiencia = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (
                nueva_experiencia,
                guild_id,
                user_id,
            ),
        )

        db.commit()

    return True, nueva_experiencia


def admin_curar_usuario(
    guild_id: int,
    user_id: int,
):
    """Elimina la lesión activa de un usuario."""

    with conectar_db() as db:
        fila = db.execute(
            """
            SELECT lesionado_hasta
            FROM box_usuarios
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        if fila is None:
            return False, None

        lesionado_hasta = fila[0]

        if lesionado_hasta is None:
            return False, None

        db.execute(
            """
            UPDATE box_usuarios
            SET lesionado_hasta = NULL
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )

        db.commit()

    return True, lesionado_hasta


def admin_modificar_probabilidad_lesion(
    guild_id: int,
    user_id: int,
    probabilidad: float,
):
    """Establece manualmente la probabilidad de lesión."""

    if not 0 <= probabilidad <= BOX_LESION_PROBABILIDAD_MAXIMA:
        return False, None

    with conectar_db() as db:
        db.execute(
            """
            INSERT INTO box_usuarios (
                guild_id,
                user_id,
                probabilidad_lesion
            )
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET probabilidad_lesion = excluded.probabilidad_lesion
            """,
            (
                guild_id,
                user_id,
                probabilidad,
            ),
        )

        db.commit()

    return True, probabilidad


def admin_cancelar_accion(
    guild_id: int,
    user_id: int,
):
    """Cancela la acción activa de un usuario."""

    with conectar_db() as db:
        accion = db.execute(
            """
            SELECT tipo,
                   iniciado_en,
                   finaliza_en,
                   recompensa,
                   dinero_recompensa
            FROM box_acciones
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ).fetchone()

        if accion is None:
            return None

        db.execute(
            """
            DELETE FROM box_acciones
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )

        db.commit()

    return accion


def admin_dar_sponsor(
    guild_id: int,
    user_id: int,
    tipo: str,
    ahora: datetime,
):
    """Otorga manualmente un sponsor respetando sus límites."""

    if tipo not in DURACION_SPONSOR:
        return False, "tipo_invalido"

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
            return False, "limite"

        db.commit()

    return True, None


def admin_quitar_sponsor(
    guild_id: int,
    user_id: int,
    sponsor_id: int,
):
    """Elimina un sponsor específico."""

    with conectar_db() as db:
        sponsor = db.execute(
            """
            SELECT id, tipo
            FROM box_sponsors
            WHERE id = ?
            AND guild_id = ?
            AND user_id = ?
            """,
            (
                sponsor_id,
                guild_id,
                user_id,
            ),
        ).fetchone()

        if sponsor is None:
            return None

        db.execute(
            """
            DELETE FROM box_sponsors
            WHERE id = ?
            """,
            (sponsor_id,),
        )

        db.commit()

    return sponsor


def admin_reset_usuario(
    guild_id: int,
    user_id: int,
):
    """
    Resetea completamente el progreso Box del usuario.

    No modifica ningún dato de Madrugue ni SSF.
    """

    with conectar_db() as db:
        db.execute("BEGIN IMMEDIATE")

        tablas = (
            "box_acciones",
            "box_desafios",
            "box_mejoras",
            "box_sponsors",
            "box_desafios_historial",
            "box_equipo",
            "box_usuarios",
        )

        eliminados = {}

        for tabla in tablas:
            if tabla == "box_desafios":
                cursor = db.execute(
                    """
                    DELETE FROM box_desafios
                    WHERE guild_id = ?
                    AND (retador_id = ? OR contrincante_id = ?)
                    """,
                    (guild_id, user_id, user_id),
                )
            elif tabla == "box_desafios_historial":
                cursor = db.execute(
                    """
                    DELETE FROM box_desafios_historial
                    WHERE guild_id = ?
                    AND (retador_id = ?
                    OR contrincante_id = ?
                    OR ganador_id = ?)
                    """,
                    (
                        guild_id,
                        user_id,
                        user_id,
                        user_id,
                    ),
                )
            else:
                cursor = db.execute(
                    f"""
                    DELETE FROM {tabla}
                    WHERE guild_id = ?
                    AND user_id = ?
                    """,
                    (guild_id, user_id),
                )

            eliminados[tabla] = cursor.rowcount

        db.commit()

    return eliminados

# ============================================================
# CONSULTAS GLOBALES (SOLO ADMINISTRADORES)
# ============================================================

def admin_obtener_top_box(
    guild_id: int,
    limite: int = 10,
):
    """Devuelve el ranking del servidor por experiencia y dinero."""

    with conectar_db() as db:

        return db.execute(
            """
            SELECT
                user_id,
                experiencia,
                dinero
            FROM box_usuarios
            WHERE guild_id = ?
            ORDER BY
                experiencia DESC,
                dinero DESC
            LIMIT ?
            """,
            (guild_id, limite),
        ).fetchall()


def admin_obtener_estadisticas_box(guild_id: int):
    """Devuelve estadísticas globales de Box del servidor."""

    with conectar_db() as db:

        jugadores = db.execute(
            """
            SELECT COUNT(*)
            FROM box_usuarios
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()[0]

        experiencia, dinero = db.execute(
            """
            SELECT
                COALESCE(SUM(experiencia), 0),
                COALESCE(SUM(dinero), 0)
            FROM box_usuarios
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()

        acciones_activas = db.execute(
            """
            SELECT COUNT(*)
            FROM box_acciones
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()[0]

        sponsors_activos = db.execute(
            """
            SELECT COUNT(*)
            FROM box_sponsors
            WHERE guild_id = ?
            AND expira_en > ?
            """,
            (
                guild_id,
                datetime.now().isoformat(),
            ),
        ).fetchone()[0]

        combates = db.execute(
            """
            SELECT COUNT(*)
            FROM box_desafios_historial
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()[0]

        pendientes = db.execute(
            """
            SELECT COUNT(*)
            FROM box_desafios
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()[0]

        lesionados = db.execute(
            """
            SELECT COUNT(*)
            FROM box_usuarios
            WHERE guild_id = ?
            AND lesionado_hasta IS NOT NULL
            AND lesionado_hasta > ?
            """,
            (
                guild_id,
                datetime.now().isoformat(),
            ),
        ).fetchone()[0]

    return {
        "jugadores": jugadores,
        "experiencia": experiencia,
        "dinero": dinero,
        "acciones_activas": acciones_activas,
        "sponsors_activos": sponsors_activos,
        "combates": combates,
        "pendientes": pendientes,
        "lesionados": lesionados,
    }


def admin_obtener_historial_desafios(
    guild_id: int,
    user_id: int,
    limite: int = 10,
):
    """Devuelve los últimos combates de un usuario."""

    with conectar_db() as db:

        return db.execute(
            """
            SELECT
                creado_en,
                retador_id,
                contrincante_id,
                ganador_id
            FROM box_desafios_historial
            WHERE guild_id = ?
            AND (retador_id = ? OR contrincante_id = ?)
            ORDER BY creado_en DESC
            LIMIT ?
            """,
            (guild_id, user_id, user_id, limite),
        ).fetchall()


def admin_obtener_lesionados(
    guild_id: int,
    ahora: datetime,
):
    """Devuelve los usuarios con lesión activa o probabilidad acumulada."""

    with conectar_db() as db:

        return db.execute(
            """
            SELECT
                user_id,
                probabilidad_lesion,
                lesionado_hasta
            FROM box_usuarios
            WHERE guild_id = ?
            AND (
                probabilidad_lesion > 0
                OR (
                    lesionado_hasta IS NOT NULL
                    AND lesionado_hasta > ?
                )
            )
            ORDER BY
                lesionado_hasta DESC,
                probabilidad_lesion DESC
            """,
            (
                guild_id,
                ahora.isoformat(),
            ),
        ).fetchall()
