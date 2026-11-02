"""Diagnóstico HTTP compacto y pausa cooperativa ante límites de Discord.

Cloudflare puede devolver un 429 con HTML, sin el ``retry_after`` JSON que
espera discord.py. No se reintenta inmediatamente ni se vuelca esa página
al log. Las tareas opcionales comparten una pausa dentro de este proceso;
no es un límite compartido entre procesos ni sustituye al de discord.py.
"""

import json
import math
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import discord

ESPERA_SIN_RETRY_AFTER = 300.0
_LARGO_DETALLE = 200


def _segundos(valor) -> float | None:
    try:
        segundos = float(valor)
    except (TypeError, ValueError, OverflowError):
        return None

    return segundos if math.isfinite(segundos) and segundos >= 0 else None


def _retry_after(error) -> float | None:
    """Segundos del encabezado HTTP, del JSON o de ``RateLimited``."""

    respuesta = getattr(error, "response", None)
    headers = getattr(respuesta, "headers", None) or {}
    valor = headers.get("Retry-After")

    if valor is None:
        valor = next(
            (v for k, v in headers.items() if k.lower() == "retry-after"),
            None,
        )

    if valor is not None:
        segundos = _segundos(valor)
        if segundos is not None:
            return segundos

        try:
            fecha = parsedate_to_datetime(valor)
            if fecha.tzinfo is None:
                fecha = fecha.replace(tzinfo=timezone.utc)
            return max(0.0, (fecha - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            pass

    texto = getattr(error, "text", "")
    if isinstance(texto, str) and texto.lstrip().startswith("{"):
        try:
            datos = json.loads(texto)
        except (ValueError, RecursionError):
            datos = None
        if isinstance(datos, dict):
            segundos = _segundos(datos.get("retry_after"))
            if segundos is not None:
                return segundos

    return _segundos(getattr(error, "retry_after", None))


def es_rate_limit(error: Exception) -> bool:
    """Incluye el 429 HTML y ``RateLimited`` (ajeno a HTTPException)."""

    return isinstance(error, discord.RateLimited) or (
        isinstance(error, discord.HTTPException) and error.status == 429
    )


def resumir_error(error: Exception) -> str:
    """Una línea acotada, sin HTML, scripts ni la IP de la salida HTTP."""

    if isinstance(error, discord.RateLimited):
        return "HTTP 429: límite de solicitudes de Discord"

    if not isinstance(error, discord.HTTPException):
        return f"{type(error).__name__}: consulta el diagnóstico del proceso"

    texto = error.text or ""
    if re.search(r"<!doctype\s+html|<html\b", texto, re.IGNORECASE):
        if error.status == 429:
            if "cloudflare" in texto.lower():
                codigo = " 1015" if re.search(
                    r"(?:error\s*|<span>)1015\b", texto, re.IGNORECASE
                ) else ""
                return f"HTTP 429: bloqueo temporal (Cloudflare{codigo})"
            return "HTTP 429: bloqueo temporal (respuesta HTML)"
        return f"HTTP {error.status}: respuesta HTML (cuerpo omitido)"

    if error.status == 429:
        return "HTTP 429: límite de solicitudes (Cloudflare/Discord)"

    detalle = " ".join(str(texto).split())[:_LARGO_DETALLE]
    resumen = f"HTTP {error.status} (code={error.code})"
    return f"{resumen}: {detalle}" if detalle else resumen


class PausaDiscord:
    """Plazo monotónico compartido; una espera menor nunca lo acorta."""

    def __init__(self, reloj=time.monotonic):
        self._reloj = reloj
        self._hasta: float | None = None

    def registrar(self, segundos: float) -> None:
        hasta = self._reloj() + segundos
        self._hasta = hasta if self._hasta is None else max(self._hasta, hasta)

    def restante(self) -> float:
        return 0.0 if self._hasta is None else max(0.0, self._hasta - self._reloj())


pausa_discord = PausaDiscord()


def registrar_limite(error: Exception, *, contexto: str) -> float:
    """Registra un 429 y devuelve su espera; otros errores no la activan."""

    if not es_rate_limit(error):
        return 0.0

    # Sin una indicación del servidor no se conoce la duración del bloqueo.
    # Cinco minutos es una pausa conservadora, no una garantía de desbloqueo.
    segundos = _retry_after(error)
    if segundos is None:
        segundos = ESPERA_SIN_RETRY_AFTER

    pausa_discord.registrar(segundos)
    print(
        f"[DISCORD] 429 contexto={contexto} espera={segundos:.1f}s "
        f"detalle={resumir_error(error)}",
        flush=True,
    )
    return segundos


def espera_restante() -> float:
    return pausa_discord.restante()
