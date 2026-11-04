"""Reintentos conservadores solo antes de configurar el bot."""

import discord
import pytest

import main


class Respuesta:
    status = 429
    reason = "Too Many Requests"

    def __init__(self, headers=None):
        self.headers = headers or {}


def error_429(headers=None):
    return discord.HTTPException(
        Respuesta(headers), "<html>Cloudflare Error 1015 <script>privado</script></html>"
    )


def preparar(monkeypatch, resultados):
    instancias = []
    esperas = []

    class BotFalso:
        def __init__(self):
            self.setup_iniciado = False
            instancias.append(self)

        def run(self, token):
            assert token == "token-de-prueba"
            resultado, self.setup_iniciado = resultados.pop(0)
            if resultado is not None:
                raise resultado

    monkeypatch.setattr(main, "_leer_token", lambda: "token-de-prueba")
    monkeypatch.setattr(main, "NaikitoBot", BotFalso)
    monkeypatch.setattr(main.time, "sleep", esperas.append)
    return instancias, esperas


def test_reintenta_con_cliente_nuevo_y_espera_creciente(monkeypatch, capsys):
    instancias, esperas = preparar(monkeypatch, [
        (error_429(), False), (error_429(), False), (None, False),
    ])

    main.main()

    assert len(instancias) == 3
    assert esperas == [300, 600]
    salida = capsys.readouterr().out
    assert "Cloudflare 1015" in salida
    assert "<html" not in salida and "privado" not in salida


def test_respeta_retry_after_mayor(monkeypatch):
    _, esperas = preparar(monkeypatch, [
        (error_429({"Retry-After": "5000"}), False), (None, False),
    ])
    main.main()
    assert esperas == [5000]


def test_tope_espera_progresiva(monkeypatch):
    _, esperas = preparar(monkeypatch, [(error_429(), False)] * 6 + [(None, False)])
    main.main()
    assert esperas == [300, 600, 1200, 2400, 3600, 3600]


@pytest.mark.parametrize("error, setup_iniciado", [
    (error_429(), True),
    (discord.LoginFailure("token inválido"), False),
    (RuntimeError("otro error"), False),
])
def test_no_reintenta_errores_de_setup_ni_otros_errores(monkeypatch, error, setup_iniciado):
    instancias, esperas = preparar(monkeypatch, [(error, setup_iniciado)])
    with pytest.raises(type(error)) as exc:
        main.main()
    assert exc.value is error
    assert len(instancias) == 1
    assert esperas == []
