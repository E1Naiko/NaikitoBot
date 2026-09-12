"""Pruebas de los comandos administrativos nuevos de Box.

Cubren ``/admin box top``, ``stats``, ``historial``, ``lesionados``,
``finalizar`` y ``procesar``, ejecutando los callbacks reales.
"""

import asyncio
from datetime import timedelta

import pytest

from core.utils import ahora
from tests.harness import (
    GuildFalso,
    InteraccionFalsa,
    UsuarioFalso,
    construir_cog,
)

GUILD = 1
ADMIN = 1
USUARIO = 42
USUARIO_2 = 43


@pytest.fixture
def admin_ids(monkeypatch):
    monkeypatch.setattr(
        "core.permissions.ADMIN_USER_IDS",
        {ADMIN},
    )


@pytest.fixture
def cog(base_datos_limpia, admin_ids):
    from commands.admin.cog import Admin

    return construir_cog(Admin)


def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        metodo(cog, interaccion, *args)
    )


def interaccion_admin(miembros=None):
    guild = GuildFalso(
        GUILD,
        miembros=miembros or {},
    )

    interaccion = InteraccionFalsa(
        GUILD,
        ADMIN,
        nombre="Admin",
    )
    interaccion.guild = guild
    return interaccion


def miembro(user_id, nombre):
    return UsuarioFalso(user_id, nombre)


def crear_usuario(user_id=USUARIO, exp=0, dinero=0):
    from modules.box.services import (
        admin_modificar_dinero,
        admin_modificar_experiencia,
    )

    admin_modificar_experiencia(GUILD, user_id, exp)
    admin_modificar_dinero(GUILD, user_id, dinero)


def insertar_combate(retador=USUARIO, contrincante=USUARIO_2, ganador=USUARIO):
    from core.database import conectar_db

    with conectar_db() as db:
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
                GUILD,
                retador,
                contrincante,
                ganador,
                "2026-09-01T12:00:00",
            ),
        )
        db.commit()


def iniciar_accion_expirada(user_id=USUARIO, hace_horas=2, recompensa=1000):
    from modules.box.services import iniciar_accion

    ahora_actual = ahora()

    return iniciar_accion(
        GUILD,
        user_id,
        "ENTRENANDO",
        ahora_actual - timedelta(hours=hace_horas),
        ahora_actual - timedelta(hours=hace_horas - 1),
        recompensa,
    )


# ========================================================
# TOP
# ========================================================

def test_top_ordena_por_experiencia(cog):
    crear_usuario(USUARIO_2, exp=3000, dinero=100)
    crear_usuario(USUARIO, exp=5000, dinero=900)

    interaccion = interaccion_admin(
        miembros={
            USUARIO: miembro(USUARIO, "Pepe"),
            USUARIO_2: miembro(USUARIO_2, "Rival"),
        }
    )

    llamar(cog, "box_top", interaccion)

    texto = interaccion.texto
    assert "TOP Box" in texto
    assert "**Pepe**" in texto
    assert "⭐ 5000 EXP" in texto
    assert "**Rival**" in texto
    assert texto.index("Pepe") < texto.index("Rival")


def test_top_sin_jugadores_informa(cog):
    interaccion = interaccion_admin()

    llamar(cog, "box_top", interaccion)

    assert "Todavía no hay usuarios" in interaccion.texto


# ========================================================
# STATS
# ========================================================

def test_stats_muestra_totales_del_servidor(cog):
    crear_usuario(USUARIO, exp=5000, dinero=900)
    crear_usuario(USUARIO_2, exp=3000, dinero=100)
    insertar_combate()

    interaccion = interaccion_admin()
    llamar(cog, "box_stats", interaccion)

    texto = interaccion.texto
    assert "Estadísticas de Box" in texto
    assert "**2**" in texto  # jugadores
    assert "**8000**" in texto  # EXP total
    assert "**1000$**" in texto  # dinero total
    assert "**1**" in texto  # combates resueltos
    assert "Combates resueltos" in texto


# ========================================================
# HISTORIAL
# ========================================================

def test_historial_muestra_victoria_y_derrota(cog):
    crear_usuario(USUARIO)
    crear_usuario(USUARIO_2)
    insertar_combate(ganador=USUARIO)

    interaccion = interaccion_admin(
        miembros={
            USUARIO: miembro(USUARIO, "Pepe"),
            USUARIO_2: miembro(USUARIO_2, "Rival"),
        }
    )

    llamar(
        cog,
        "box_historial",
        interaccion,
        miembro(USUARIO, "Pepe"),
    )

    texto = interaccion.texto
    assert "Historial de Pepe" in texto
    assert "vs **Rival**" in texto
    assert "✅ Victoria" in texto

    interaccion_2 = interaccion_admin(
        miembros={
            USUARIO: miembro(USUARIO, "Pepe"),
            USUARIO_2: miembro(USUARIO_2, "Rival"),
        }
    )

    llamar(
        cog,
        "box_historial",
        interaccion_2,
        miembro(USUARIO_2, "Rival"),
    )

    assert "❌ Derrota" in interaccion_2.texto


def test_historial_sin_combates_informa(cog):
    interaccion = interaccion_admin()

    llamar(
        cog,
        "box_historial",
        interaccion,
        miembro(USUARIO, "Pepe"),
    )

    assert "todavía no participó" in interaccion.texto


# ========================================================
# LESIONADOS
# ========================================================

def test_lesionados_lista_probabilidad_y_lesiones(cog):
    from modules.box.services import admin_modificar_probabilidad_lesion

    crear_usuario(USUARIO)
    crear_usuario(USUARIO_2)

    admin_modificar_probabilidad_lesion(GUILD, USUARIO, 25.0)

    from core.database import conectar_db

    hasta = (ahora() + timedelta(hours=3)).isoformat()

    with conectar_db() as db:
        db.execute(
            """
            UPDATE box_usuarios
            SET lesionado_hasta = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (hasta, GUILD, USUARIO_2),
        )
        db.commit()

    interaccion = interaccion_admin(
        miembros={
            USUARIO: miembro(USUARIO, "Pepe"),
            USUARIO_2: miembro(USUARIO_2, "Rival"),
        }
    )

    llamar(cog, "box_lesionados", interaccion)

    texto = interaccion.texto
    assert "**Pepe**" in texto
    assert "25.0%" in texto
    assert "**Rival**" in texto
    assert "🚑" in texto


def test_lesionados_vacio_informa(cog):
    interaccion = interaccion_admin()

    llamar(cog, "box_lesionados", interaccion)

    assert "No hay usuarios" in interaccion.texto


# ========================================================
# FINALIZAR
# ========================================================

def test_finalizar_liquida_accion_vencida(cog):
    crear_usuario(USUARIO)
    iniciar_accion_expirada(USUARIO, hace_horas=2, recompensa=1000)

    from modules.box.services import obtener_saldo

    assert obtener_saldo(GUILD, USUARIO) == (0, 0)

    interaccion = interaccion_admin()

    llamar(
        cog,
        "box_finalizar",
        interaccion,
        miembro(USUARIO, "Pepe"),
    )

    assert "Acción liquidada correctamente" in interaccion.texto
    assert "entrenar" in interaccion.texto
    assert "**1000 EXP**" in interaccion.texto

    saldo = obtener_saldo(GUILD, USUARIO)
    assert saldo[0] == 1000

    from modules.box.services import obtener_accion_activa

    assert obtener_accion_activa(GUILD, USUARIO) is None


def test_finalizar_accion_no_vencida_informa(cog):
    crear_usuario(USUARIO)

    from modules.box.services import iniciar_accion

    ahora_actual = ahora()
    iniciar_accion(
        GUILD,
        USUARIO,
        "ENTRENANDO",
        ahora_actual,
        ahora_actual + timedelta(hours=1),
        1000,
    )

    interaccion = interaccion_admin()

    llamar(
        cog,
        "box_finalizar",
        interaccion,
        miembro(USUARIO, "Pepe"),
    )

    assert "todavía no vence" in interaccion.texto
    assert "box cancelar" in interaccion.texto


def test_finalizar_sin_accion_informa(cog):
    interaccion = interaccion_admin()

    llamar(
        cog,
        "box_finalizar",
        interaccion,
        miembro(USUARIO, "Pepe"),
    )

    assert "no tiene ninguna acción activa" in interaccion.texto


# ========================================================
# PROCESAR
# ========================================================

def test_procesar_liquida_las_acciones_vencidas(cog):
    crear_usuario(USUARIO)
    crear_usuario(USUARIO_2)
    iniciar_accion_expirada(USUARIO, hace_horas=2, recompensa=1000)
    iniciar_accion_expirada(USUARIO_2, hace_horas=3, recompensa=2000)

    interaccion = interaccion_admin()

    llamar(cog, "box_procesar", interaccion)

    assert "**Acciones procesadas: 2**" in interaccion.texto
    assert "entrenar" in interaccion.texto

    from modules.box.services import obtener_saldo

    assert obtener_saldo(GUILD, USUARIO)[0] == 1000
    assert obtener_saldo(GUILD, USUARIO_2)[0] == 2000


def test_procesar_sin_vencidas_informa(cog):
    interaccion = interaccion_admin()

    llamar(cog, "box_procesar", interaccion)

    assert "No había acciones vencidas" in interaccion.texto


# ============================================================
# /admin box canticos
# ============================================================


def test_admin_box_canticos_consultar_sin_decision(cog):
    from tests.harness import Choice

    interaccion = interaccion_admin()

    llamar(cog, "box_canticos", interaccion, Choice("consultar"))

    assert "Nadie decidió" in interaccion.texto


def test_admin_box_canticos_activar_y_desactivar(cog):
    from modules.box.database import obtener_canticos
    from tests.harness import Choice

    interaccion = interaccion_admin()

    llamar(cog, "box_canticos", interaccion, Choice("activar"))

    assert obtener_canticos(GUILD) is True
    assert "activados" in interaccion.texto

    llamar(cog, "box_canticos", interaccion, Choice("desactivar"))

    assert obtener_canticos(GUILD) is False

    llamar(cog, "box_canticos", interaccion, Choice("consultar"))

    assert "desactivados" in interaccion.texto
    # La respuesta es privada: el aviso de que "se activaron los cánticos" no
    # tiene por qué llenar el canal.
    assert interaccion.respuestas[-1].efimero is True


# ============================================================
# /admin box cerrar_combate
# ============================================================


def _combate_vivo_de_broma(guild_id=GUILD):
    from core.database import conectar_db

    with conectar_db() as db:
        fila = db.execute(
            """
            INSERT INTO box_combates (
                guild_id,
                canal_id,
                modo,
                retador_id,
                contrincante_id,
                semilla,
                plan,
                iniciado_en,
                latido_segundos,
                latidos_totales,
                fin_narracion_en,
                estado
            ) VALUES (?, ?, 'FIGHTING', ?, ?, 1, '{}', ?, 15, 9, ?, 'VIVO')
            """,
            (
                guild_id,
                77,
                USUARIO,
                USUARIO_2,
                ahora().isoformat(),
                ahora().isoformat(),
            ),
        )
        db.commit()

        return fila.lastrowid


def test_admin_box_cerrar_combate_suelta_el_candado(cog):
    from modules.box.database import combate_en_curso, obtener_combates_vivos

    combate_id = _combate_vivo_de_broma()

    assert combate_en_curso(GUILD) is not None
    assert len(obtener_combates_vivos(ahora())) == 1

    interaccion = interaccion_admin()

    llamar(cog, "box_cerrar_combate", interaccion)

    assert "Cerrada la pelea" in interaccion.texto
    assert combate_en_curso(GUILD) is None
    assert obtener_combates_vivos(ahora()) == []

    with __import__("core.database", fromlist=["conectar_db"]).conectar_db() as db:
        estado, resumen = db.execute(
            "SELECT estado, resumen FROM box_combates WHERE id = ?",
            (combate_id,),
        ).fetchone()

    assert estado == "CANCELADO"
    assert "cerrado a mano" in resumen


def test_admin_box_cerrar_combate_sin_pelea_avisa(cog):
    interaccion = interaccion_admin()

    llamar(cog, "box_cerrar_combate", interaccion)

    assert "No hay ninguna pelea" in interaccion.texto
