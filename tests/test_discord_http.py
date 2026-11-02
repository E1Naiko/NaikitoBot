"""Errores HTTP compactos y pausa compartida ante límites de Discord."""

import math
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import discord
import pytest

from core import discord_http


class Respuesta:
    def __init__(self, status=429, headers=None):
        self.status = status
        self.reason = "Too Many Requests" if status == 429 else "Error"
        self.headers = headers or {}


@pytest.fixture(autouse=True)
def pausa_aislada(monkeypatch):
    reloj = [100.0]
    pausa = discord_http.PausaDiscord(reloj=lambda: reloj[0])
    monkeypatch.setattr(discord_http, "pausa_discord", pausa)
    return reloj


HTML_CLOUDFLARE = """<!doctype html><html><head>
<title>Access denied | discord.com used Cloudflare to restrict access</title>
</head><body><span>Error</span><span>1015</span>
You are being rate limited. Your IP: 203.0.113.10
<script>window.secret = 'no va al log';</script></body></html>"""


def test_cloudflare_se_resume_sin_html_ip_ni_scripts(capsys):
    error = discord.HTTPException(Respuesta(), HTML_CLOUDFLARE)

    resumen = discord_http.resumir_error(error)
    discord_http.registrar_limite(error, contexto="prueba")

    assert "429" in resumen
    assert "Cloudflare 1015" in resumen
    salida = capsys.readouterr().out
    assert "429" in salida and "prueba" in salida
    for privado in ("<html", "<script", "203.0.113.10", "no va al log"):
        assert privado not in resumen + salida
    assert len(salida.splitlines()) == 1


def test_sin_retry_after_pausa_cinco_minutos(pausa_aislada):
    discord_http.registrar_limite(
        discord.HTTPException(Respuesta(), HTML_CLOUDFLARE), contexto="prueba"
    )

    assert discord_http.espera_restante() == 300
    pausa_aislada[0] += 299
    assert discord_http.espera_restante() == 1
    pausa_aislada[0] += 1
    assert discord_http.espera_restante() == 0


@pytest.mark.parametrize(
    "headers, espera",
    [
        ({"Retry-After": "7.5"}, 7.5),
        ({"retry-after": "12"}, 12),
        ({"Retry-After": "0"}, 0),
    ],
)
def test_respeta_retry_after_en_segundos(headers, espera):
    error = discord.HTTPException(Respuesta(headers=headers), HTML_CLOUDFLARE)

    assert discord_http.registrar_limite(error, contexto="prueba") == espera
    assert discord_http.espera_restante() == espera


def test_retry_after_como_fecha_http():
    fecha = datetime.now(timezone.utc) + timedelta(seconds=45)
    error = discord.HTTPException(
        Respuesta(headers={"Retry-After": format_datetime(fecha, usegmt=True)}),
        "rate limited",
    )

    assert 43 <= discord_http.registrar_limite(error, contexto="prueba") <= 45


def test_rate_limited_de_discord_py_usa_retry_after():
    error = discord.RateLimited(42.5)

    assert discord_http.es_rate_limit(error)
    assert discord_http.registrar_limite(error, contexto="prueba") == 42.5
    assert "429" in discord_http.resumir_error(error)


def test_429_json_con_retry_after():
    error = discord.HTTPException(Respuesta(), '{"retry_after": 18.25}')

    assert discord_http.registrar_limite(error, contexto="prueba") == 18.25


@pytest.mark.parametrize("valor", ["nan", "inf", "-inf", "-10", "no es un número"])
def test_retry_after_invalido_no_acorta_la_pausa(valor):
    error = discord.HTTPException(
        Respuesta(headers={"Retry-After": valor}), HTML_CLOUDFLARE
    )

    assert discord_http.registrar_limite(error, contexto="prueba") == 300


def test_una_pausa_menor_no_reemplaza_a_una_mayor(pausa_aislada):
    discord_http.registrar_limite(discord.RateLimited(600), contexto="sync")
    pausa_aislada[0] += 10
    discord_http.registrar_limite(discord.RateLimited(2), contexto="reaccion")

    assert discord_http.espera_restante() == 590
    pausa_aislada[0] += 590
    assert discord_http.espera_restante() == 0


def test_error_que_no_es_429_no_activa_pausa():
    error = discord.Forbidden(Respuesta(status=403), "Missing Permissions")

    assert not discord_http.es_rate_limit(error)
    assert discord_http.registrar_limite(error, contexto="prueba") == 0
    assert discord_http.espera_restante() == 0
    assert "Missing Permissions" in discord_http.resumir_error(error)


def test_error_html_generico_tampoco_se_vuelca_al_log():
    error = discord.HTTPException(
        Respuesta(status=503), "<html><body>Servicio no disponible</body></html>"
    )

    assert discord_http.resumir_error(error) == (
        "HTTP 503: respuesta HTML (cuerpo omitido)"
    )


def test_429_html_no_se_atribuye_a_cloudflare_sin_evidencia():
    error = discord.HTTPException(Respuesta(), "<html>Rate limited</html>")

    assert discord_http.resumir_error(error) == (
        "HTTP 429: bloqueo temporal (respuesta HTML)"
    )


def test_detalle_normal_es_una_sola_linea_y_acotado():
    error = discord.HTTPException(Respuesta(status=400), "x" * 1000 + "\nTRACEBACK")
    resumen = discord_http.resumir_error(error)

    assert len(resumen) < 300
    assert "\n" not in resumen


def test_espera_no_devuelve_numeros_negativos(pausa_aislada):
    discord_http.registrar_limite(discord.RateLimited(1), contexto="prueba")
    pausa_aislada[0] = math.nextafter(pausa_aislada[0], math.inf) + 100

    assert discord_http.espera_restante() == 0
