"""Regresiones del corte anual, migración y recuperación de historial."""

import asyncio
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

from config import TIMEZONE
from core.temporada import inicio_temporada, verificar_temporada


def test_corte_anual_en_hora_local():
    antes = datetime(2026, 10, 3, 2, 59, 59, tzinfo=timezone.utc)
    despues = antes + timedelta(seconds=1)
    assert inicio_temporada(antes) == datetime(2025, 10, 3, tzinfo=TIMEZONE)
    assert inicio_temporada(despues) == datetime(2026, 10, 3, tzinfo=TIMEZONE)
    assert inicio_temporada(datetime(2027, 1, 1, tzinfo=TIMEZONE)).year == 2026


def _sembrar(path):
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM temporada")
        for fecha, uid in (("2026-10-02", 1), ("2026-10-03", 2)):
            db.execute("INSERT INTO registros (guild_id,user_id,username,fecha,hora,puntos_base,multiplicador,puntos_finales) VALUES (1,?,'U',?,'06:00',100,1,100)", (uid, fecha))
            db.execute("INSERT INTO lahora_registros (guild_id,user_id,username,fecha,ventana,momento,segundos,posicion,puntos_base,multiplicador,bonus_posicion,puntos_finales) VALUES (1,?,'U',?,'04:20',?,0,1,10,1,0,10)", (uid, fecha, fecha + "T04:20:00-03:00"))
        db.execute("INSERT INTO box_config_guild (guild_id,canticos) VALUES (1,3)")
        db.execute("INSERT INTO box_usuarios (guild_id,user_id,dinero) VALUES (1,1,99)")
        db.execute("INSERT INTO ssf_desafios VALUES (1,1,'viejo','2026-09-01','2026-09-30',1,1)")
        db.execute("INSERT INTO ssf_desafios VALUES (2,1,'actual','2026-10-03','2026-10-31',1,1)")
        for id_desafio in (1, 2):
            db.execute("INSERT INTO ssf_participantes (desafio_id,user_id,username,fecha_registro) VALUES (?,1,'U','2026-10-03T00:00:00-03:00')", (id_desafio,))
            db.execute("INSERT INTO ssf_registros VALUES (?,1,'2026-10-03','09:00')", (id_desafio,))
            db.execute("INSERT INTO ssf_revisiones VALUES (?,'2026-10-03')", (id_desafio,))
        # Puede haber inscripciones anticipadas a un desafío de la nueva temporada.
        db.execute("INSERT INTO ssf_participantes (desafio_id,user_id,username,fecha_registro) VALUES (2,3,'U','2026-10-02T00:00:00-03:00')")
        db.execute("INSERT INTO ssf_registros VALUES (2,3,'2026-10-03','09:00')")
        db.execute("INSERT INTO lahora_sincronizacion VALUES (42,1,'2026-10-01T00:00:00-03:00')")


def _corte(monkeypatch):
    inicio = datetime(2026, 10, 3, tzinfo=TIMEZONE)
    monkeypatch.setattr("core.temporada.inicio_temporada", lambda *_: inicio)
    return inicio


async def test_migracion_atomica_conserva_actuales_y_configuracion(base_datos_limpia, monkeypatch):
    _corte(monkeypatch)
    _sembrar(base_datos_limpia)
    # Varios accesos simultáneos no deben resetear más de una vez.
    await asyncio.gather(*(asyncio.to_thread(verificar_temporada) for _ in range(5)))
    with sqlite3.connect(base_datos_limpia) as db:
        for tabla in ("registros", "lahora_registros"):
            assert db.execute(f"SELECT fecha FROM {tabla}").fetchall() == [("2026-10-03",)]
        for tabla in ("ssf_participantes", "ssf_registros", "ssf_revisiones"):
            assert db.execute(f"SELECT desafio_id FROM {tabla}").fetchall() == [(2,)]
        assert db.execute("SELECT id FROM ssf_desafios").fetchall() == [(2,)]
        assert db.execute("SELECT * FROM box_usuarios").fetchall() == []
        assert db.execute("SELECT canticos FROM box_config_guild").fetchone() == (3,)
        assert db.execute("SELECT ultimo_chequeo FROM lahora_sincronizacion").fetchone()
        assert db.execute("SELECT inicio FROM temporada").fetchone() == ("2026-10-03",)
        db.execute("INSERT INTO box_usuarios (guild_id,user_id,dinero) VALUES (1,2,50)")
    verificar_temporada()
    with sqlite3.connect(base_datos_limpia) as db:
        assert db.execute("SELECT dinero FROM box_usuarios").fetchone() == (50,)


def test_fallo_revierte_todo_el_corte(base_datos_limpia, monkeypatch):
    _corte(monkeypatch)
    _sembrar(base_datos_limpia)
    with sqlite3.connect(base_datos_limpia) as db:
        db.execute("CREATE TRIGGER falla BEFORE DELETE ON box_usuarios BEGIN SELECT RAISE(ABORT, 'fallo simulado'); END")
    with pytest.raises(sqlite3.IntegrityError):
        verificar_temporada()
    with sqlite3.connect(base_datos_limpia) as db:
        assert db.execute("SELECT COUNT(*) FROM registros").fetchone() == (2,)
        assert db.execute("SELECT COUNT(*) FROM ssf_desafios").fetchone() == (2,)
        assert db.execute("SELECT COUNT(*) FROM temporada").fetchone() == (0,)
        db.execute("DROP TRIGGER falla")


async def test_acceso_siguiente_aplica_temporada_sin_reiniciar_proceso(base_datos_limpia, monkeypatch):
    import modules.box.database as box
    inicio = _corte(monkeypatch)
    with sqlite3.connect(base_datos_limpia) as db:
        db.execute("UPDATE temporada SET inicio='2025-10-03'")
        db.execute("INSERT INTO box_usuarios (guild_id,user_id,dinero) VALUES (1,2,50)")
    assert (await box.obtener_saldo(1, 2))[1] == 0
    with sqlite3.connect(base_datos_limpia) as db:
        assert db.execute("SELECT inicio FROM temporada").fetchone() == (inicio.date().isoformat(),)


async def test_importaciones_y_manual_no_aceptan_fechas_anteriores(base_datos_limpia, monkeypatch):
    from modules.lahora.services import importar_mensajes, agregar_manual
    from modules.madrugue.database import importar_registros
    inicio = _corte(monkeypatch)
    monkeypatch.setattr("modules.lahora.services.inicio_temporada", lambda: inicio)
    monkeypatch.setattr("modules.madrugue.database.inicio_temporada", lambda: inicio)
    antiguo = datetime(2026, 10, 2, 4, 20, tzinfo=TIMEZONE)
    actual = datetime(2026, 10, 3, 4, 20, tzinfo=TIMEZONE)
    resultado = await agregar_manual(1, 1, "U", antiguo)
    assert resultado.motivo == "temporada_anterior"
    async def mensajes():
        for momento, uid in ((antiguo, 1), (actual, 2)):
            yield SimpleNamespace(author=SimpleNamespace(id=uid, display_name="U", bot=False),
                                  content="420", created_at=momento, edited_at=None, id=uid)
    resumen = await importar_mensajes(1, mensajes())
    assert (resumen.anteriores, resumen.importados) == (1, 1)
    filas = [(1, 'U', '2026-10-03', '06:00', 100, 1.0, 100),
             (2, 'U', '2026-10-02', '06:00', 100, 1.0, 100)]
    with pytest.raises(ValueError, match="temporada"):
        await importar_registros(1, filas)
    with sqlite3.connect(base_datos_limpia) as db:
        assert db.execute("SELECT COUNT(*) FROM registros").fetchone() == (0,)


async def test_transacciones_que_cruzan_el_corte_no_se_confirman(base_datos_limpia, monkeypatch):
    from core.sqlite import conectar, conectar_sync
    anterior = datetime(2025, 10, 3, tzinfo=TIMEZONE)
    actual = datetime(2026, 10, 3, tzinfo=TIMEZONE)
    reloj = [anterior]
    # Simula la transición mientras ambas conexiones ya estaban abiertas.
    monkeypatch.setattr("core.temporada.inicio_temporada", lambda *_: reloj[0])
    monkeypatch.setattr("core.temporada.verificar_temporada", lambda: None)
    async with conectar() as db:
        await db.execute("INSERT INTO box_usuarios (guild_id,user_id,dinero) VALUES (1,1,50)")
        reloj[0] = actual
        with pytest.raises(RuntimeError, match="temporada cambió"):
            await db.commit()
    reloj[0] = anterior
    with conectar_sync() as db:
        db.execute("INSERT INTO box_usuarios (guild_id,user_id,dinero) VALUES (1,2,50)")
        reloj[0] = actual
        with pytest.raises(RuntimeError, match="temporada cambió"):
            db.commit()
    with sqlite3.connect(base_datos_limpia) as db:
        assert db.execute("SELECT COUNT(*) FROM box_usuarios").fetchone() == (0,)


async def test_sincronizacion_acota_checkpoint_antiguo(base_datos_limpia, monkeypatch):
    from core.lahora_sync import _sincronizar_canal
    from modules.lahora.database import guardar_ultimo_chequeo
    from tests.test_core_lahora_sync import CanalConHistorial, MensajeHistorial

    inicio = _corte(monkeypatch)
    monkeypatch.setattr("core.lahora_sync.inicio_temporada", lambda *_: inicio)
    monkeypatch.setattr("modules.lahora.services.inicio_temporada", lambda: inicio)
    monkeypatch.setattr("core.lahora_sync.ahora", lambda: datetime(2026, 10, 5, tzinfo=TIMEZONE))
    viejo = datetime(2026, 10, 2, 4, 20, tzinfo=TIMEZONE)
    nuevo = datetime(2026, 10, 3, 4, 20, tzinfo=TIMEZONE)
    canal = CanalConHistorial([MensajeHistorial("420", viejo), MensajeHistorial("420", nuevo)])
    await guardar_ultimo_chequeo(1, canal.id, viejo - timedelta(days=1))
    resultado = await _sincronizar_canal(1, canal)
    assert canal.llamadas[0]["after"] == inicio
    assert resultado.resumen.importados == 1
    with sqlite3.connect(base_datos_limpia) as db:
        assert db.execute("SELECT fecha FROM lahora_registros").fetchall() == [("2026-10-03",)]


async def test_primera_inicializacion_actualiza_base_sin_marca(base_datos_limpia, monkeypatch):
    from core.database import inicializar_db
    _corte(monkeypatch)
    _sembrar(base_datos_limpia)
    with sqlite3.connect(base_datos_limpia) as db:
        db.execute("DROP TABLE temporada")
    await inicializar_db()
    with sqlite3.connect(base_datos_limpia) as db:
        assert db.execute("SELECT inicio FROM temporada").fetchone() == ("2026-10-03",)
        assert db.execute("SELECT fecha FROM registros").fetchall() == [("2026-10-03",)]
        assert db.execute("SELECT COUNT(*) FROM box_usuarios").fetchone() == (0,)


def test_fusion_rechaza_una_copia_antigua(base_datos_limpia, monkeypatch):
    from pathlib import Path
    from scripts.combinar_db import verificar_origen_temporada
    monkeypatch.setattr("scripts.combinar_db.inicio_temporada", lambda: datetime(2026, 10, 3, tzinfo=TIMEZONE))
    with sqlite3.connect(base_datos_limpia) as db:
        db.execute("UPDATE temporada SET inicio='2025-10-03'")
    with pytest.raises(SystemExit, match="no pertenece a la temporada"):
        verificar_origen_temporada(Path(base_datos_limpia))
