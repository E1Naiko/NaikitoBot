import os
import time
from pathlib import Path

from dotenv import load_dotenv

RUTA_ENV = Path(__file__).resolve().parent / ".env"

load_dotenv(RUTA_ENV)

from core.bot import NaikitoBot
from core.discord_http import es_rate_limit, registrar_limite

# Evita un bucle agresivo cuando Cloudflare no informa cuándo termina el bloqueo.
ESPERA_INICIAL_ARRANQUE = 300.0
ESPERA_MAXIMA_ARRANQUE = 3600.0


def _leer_token():
    """Devuelve el token de Discord leyendo el ``.env`` directo.

    ``load_dotenv`` NO sobreescribe variables que ya existan en el
    entorno del proceso (``override=False`` por defecto): si el panel de
    Wispbyte (Pterodactyl) declara ``DISCORD_TOKEN`` vacía, esa variable
    taparía al archivo y el bot no arrancaría aunque el ``.env`` esté
    bien. Para evitar justo ese caso el token se lee primero del archivo
    y solo se cae al entorno si el archivo no lo declara.
    """

    token = os.getenv("DISCORD_TOKEN")

    if RUTA_ENV.exists():
        for linea in RUTA_ENV.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            clave, sep, valor = linea.lstrip().partition("=")
            if sep and clave.strip() == "DISCORD_TOKEN":
                token = valor.strip().strip("\"'").strip() or token
                break

    return token


def main():
    token = _leer_token()

    if not token:
        _diagnostico_token()
        raise RuntimeError(
            "No se encontró DISCORD_TOKEN en las variables de entorno."
        )

    espera = ESPERA_INICIAL_ARRANQUE
    while True:
        # Cada intento necesita un cliente nuevo: run() cierra el anterior.
        bot = NaikitoBot()
        try:
            bot.run(token)
            return
        except Exception as error:
            # No repetir setup_hook ni tareas que ya pudieran haberse iniciado.
            if bot.setup_iniciado or not es_rate_limit(error):
                raise

            indicado = registrar_limite(error, contexto="inicio de sesión")
            demora = max(espera, indicado)
            print(
                f"[DISCORD] Inicio bloqueado; próximo intento en {demora:.1f}s. "
                "Si persiste, revisá la IP de salida con el hosting.",
                flush=True,
            )
            time.sleep(demora)
            espera = min(espera * 2, ESPERA_MAXIMA_ARRANQUE)


def _diagnostico_token() -> None:
    """Imprime en el log por qué falta DISCORD_TOKEN sin revelar el token.

    El bot carga la configuración con ``load_dotenv``, que NO pisa
    variables que ya existen en el entorno del proceso. Por eso, si el
    panel (Pterodactyl/Wispbyte) declara ``DISCORD_TOKEN`` vacía, esa
    variable vacía gana sobre el archivo ``.env`` y produce justo este
    error. Este diagnóstico distingue ese caso de un ``.env`` ausente,
    con la clave comentada o con la clave vacía.
    """

    ruta_env = RUTA_ENV

    en_entorno = "DISCORD_TOKEN" in os.environ
    largo_entorno = len(os.environ.get("DISCORD_TOKEN", "") or "") if en_entorno else None

    # Largo (no el valor) de cada línea "DISCORD_TOKEN=..." activa del .env.
    largos_lineas = []
    if ruta_env.exists():
        for linea in ruta_env.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            clave, sep, _ = linea.lstrip().partition("=")
            if sep and clave.strip() == "DISCORD_TOKEN":
                largos_lineas.append(len(linea.split("=", 1)[1].strip()))

    print("=" * 64, flush=True)
    print("DIAGNÓSTICO: no se encontró DISCORD_TOKEN", flush=True)
    print(f"  .env buscado: {ruta_env}", flush=True)
    print(f"  ¿existe el archivo? {ruta_env.exists()}", flush=True)
    print(f"  ¿declarada en el entorno del proceso? {en_entorno}", flush=True)
    if en_entorno:
        print(f"  largo del valor en el entorno: {largo_entorno} caracteres", flush=True)
    print(
        f"  líneas 'DISCORD_TOKEN=' activas en el .env: "
        f"{largos_lineas or 'ninguna'}",
        flush=True,
    )

    if en_entorno and largo_entorno == 0:
        print(
            "  -> El panel declara DISCORD_TOKEN vacía y le gana al .env:",
            flush=True,
        )
        print(
            "     python-dotenv no sobreescribe variables ya existentes.",
            flush=True,
        )
        print(
            "     Borrá la variable del panel (Startup > Environment Variables)",
            flush=True,
        )
        print("     o cargala con el token real.", flush=True)
    elif ruta_env.exists() and not largos_lineas:
        print(
            "  -> El .env existe pero no tiene una línea DISCORD_TOKEN= activa:",
            flush=True,
        )
        print("     revisá que no esté comentada (#) ni mal escrita.", flush=True)
    elif ruta_env.exists() and largos_lineas == [0]:
        print(
            "  -> El .env existe pero DISCORD_TOKEN está vacía (sin valor).",
            flush=True,
        )
    else:
        print(
            "  -> Revisá nombre/ruta del archivo y sus permisos.",
            flush=True,
        )
    print("=" * 64, flush=True)


if __name__ == "__main__":
    main()
