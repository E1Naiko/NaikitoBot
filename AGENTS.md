# AGENTS.md

Guía para agentes de código (y para personas) que trabajen en este repositorio.
Complementa a `README.md` (uso y comandos), `DOCUMENTACION.md` (arquitectura) y
`DESPLIEGUE.md` (producción); si algo acá contradice al código, manda el código y
conviene corregir este archivo en el mismo cambio.

## Qué es este proyecto

NaikitoBot es un bot de Discord en **Python** (`discord.py` 2.7) con cuatro
minijuegos y una capa administrativa, todo persistido en un único archivo
**SQLite**:

| Sistema | Clave interna | Código |
| --- | --- | --- |
| Madrugue (recompensa por madrugar) | `madrugue` | `modules/madrugue`, `commands/madrugue` |
| Canal 420 (`laHora`) | `lahora` | `modules/lahora`, `commands/lahora` |
| SeptSinFP (desafío de rachas) | `ssf` | `modules/ssf`, `commands/ssf` |
| Box (boxeo, economía, combates) | `box` | `modules/box`, `commands/box` |
| Administración | — | `commands/admin` |
| Sanciones por trampa | — | `modules/sanciones`, `commands/admin/sanciones.py` |

Idioma del proyecto: **español** en identificadores, docstrings, comentarios,
mensajes al usuario y commits.

## Entorno y comandos

Requiere Python **3.10+** (se desarrolla y prueba con 3.11).

```bash
# Entorno (el repo ignora .venv/)
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

# Pruebas: no necesitan token ni red (conftest fija un SQLite temporal)
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_lahora_logs.py -k podio   # una sola prueba

# Estilo: el repo se mantiene sin errores nuevos de pyflakes
.venv/bin/python -m pyflakes $(git ls-files '*.py' | grep -v 'config/__init__.py')

# Ejecutar el bot (necesita .env con DISCORD_TOKEN)
.venv/bin/python main.py

# Respaldos de la base en caliente
.venv/bin/python -m scripts.respaldar_db
```

Estado esperado al empezar: `pytest` en verde (hoy ~864 pruebas, ~90 s). Si algo
falla antes de tocar código, resolvelo o avisá; no lo tapes con `xfail`.

`pyflakes` tiene **3 avisos preexistentes** (`commands/madrugue/registro.py`,
`modules/ssf/logic.py`, `tests/test_admin_madrugue_ver.py`) y decenas en
`config/__init__.py`, que es un módulo de reexportación a propósito. No hace
falta arreglarlos, pero **no agregues nuevos**.

## Mapa del repositorio

```text
main.py                  Arranque: lee el token, reintenta ante 429 de Cloudflare
core/                    Código transversal
  bot.py                 NaikitoBot: extensiones, RestrictedCommandTree, resumen de arranque
  esquema.sql            ÚNICO esquema de la base (todas las tablas)
  database.py            inicializar_db() / vaciar_db() (este último solo en pruebas)
  sqlite.py              conectar() async y conectar_sync(); commit con control de temporada
  temporada.py           Corte anual del 3 de octubre
  mensajes.py            Embeds y respuestas (responder, responder_error, colores por área)
  discord_http.py        Pausa por 429, espera_restante(), registrar_limite(), resumir_error()
  lahora_logs.py         Líneas de terminal del 420 (formato del log)
  lahora_sync.py         Recuperación de 420 perdidos al reconectar
  permissions.py         es_admin() sobre ADMIN_USER_IDS
  utils.py               ahora() en la zona horaria configurada
  version.py             Versionado manual (VERSION_FUNCION / VERSION_REVISION)
config/                  Lectura y validación de variables (.env → constantes)
commands/<area>/         Cogs y slash commands; <area>/__init__.py expone setup()
modules/<area>/          Lógica de negocio y persistencia (logic / database / services)
tests/                   pytest + dobles de Discord (harness.py)
scripts/                 respaldar_db, combinar_db, importar_madrugue_historico
deploy/                  systemd y script de instalación para Ubuntu
data/, metadata/, migrations/   Datos auxiliares; migrations/ está vacío (esquema en core/)
```

## Arquitectura y reglas de capas

Flujo normal de una funcionalidad:

```text
Discord → commands/(cog o view) → modules/<area>/services.py
                                      ├── logic.py     (reglas puras, sin I/O)
                                      ├── database.py  (SQL parametrizado)
                                      └── core/sqlite.py
```

- **`logic.py`**: funciones puras (sin Discord ni base). Todo lo que se pueda
  probar con fechas fijas va acá.
- **`database.py`**: SQL parametrizado (`?`), una operación por función, commit
  explícito antes de retornar. Las fechas se guardan como texto ISO **con zona**.
- **`services.py`**: fachada que usan los cogs; combina logic + database.
- **`commands/`**: presentación. No agregues SQL acá (hay excepciones históricas,
  no las imites).
- Leé las constantes desde `config` (`from config import X`), nunca `os.getenv`
  suelto en módulos.

### Reglas duras

- **No** edites `config/__init__.py` "limpiando" imports: es la fachada pública
  de `config/settings.py`.
- **Todos** los `datetime` que importan al juego salen de `core.utils.ahora()`
  (zona `TIMEZONE`). Nunca `datetime.now()` sin zona ni `date.today()`.
- Un archivo de `commands/` que use `allowlist` de canales no debe duplicar esa
  lógica: el filtro vive en `RestrictedCommandTree` (`core/bot.py`).
- No borres ni reescribas datos de usuarios desde comandos nuevos. Las únicas
  operaciones destructivas son las administrativas existentes y el corte anual.
- Nada de credenciales en el repo: `.env` está ignorado. No leas, imprimas ni
  commitees tokens, IDs de administradores reales ni `.db`.

## Persistencia

- **Un solo esquema**: `core/esquema.sql`, todo con `CREATE TABLE IF NOT EXISTS`.
  Para una tabla nueva: agregala ahí (con comentario del porqué) y listo; no hay
  migraciones versionadas. Los cambios de columnas de tablas existentes no están
  soportados por el esquema: si necesitás una columna nueva en una tabla vieja,
  agregá la tabla y documentá la decisión (hoy no hay `ALTER TABLE`).
- El bot crea las tablas faltantes en `setup_hook()` vía
  `modules/<area>/database.inicializar_db()` (todos delegan en
  `core/database.inicializar_db`). Un sistema nuevo debe sumarse ahí.
- `core/temporada.py` borra datos de todos los sistemas cada 3 de octubre.
  Excepción deliberada: `sanciones` **no** se borra.
- **Nunca** reintroduzcas `DATABASE_URL`: el proyecto usa solo `DATABASE`
  (archivo persistente) y falla al arrancar si aparece la variable vieja.

## Pruebas

- `tests/conftest.py` apunta `DATABASE` a un SQLite temporal antes de importar
  `config`; si necesitás configuración especial, hacelo en la prueba con
  `monkeypatch`, no cambiando `config` al importar.
- Dobles listos en `tests/harness.py`: `InteraccionFalsa`, `UsuarioFalso`,
  `GuildFalso`, `CanalFalso`, `construir_cog()` (instancia el cog sin arrancar
  tareas).
- Invocá callbacks reales, como lo hace el resto:
  `await type(cog).metodo.callback(cog, interaccion, ...)`.
- **Fechas históricas**: varias pruebas usan septiembre de 2026 y por eso están
  en la lista blanca `_temporada_en_pruebas_historicas` de `conftest.py`. Si un
  archivo nuevo usa fechas anteriores al 3 de octubre vigente, agregalo a esa
  lista o usá `core.utils.ahora()` como base.
- Las tareas periódicas se parchean con `monkeypatch.setattr(tasks.Loop, "start", ...)`;
  no las dejes correr de verdad en pruebas.
- Si tocás comandos, actualizá los manifiestos que fallan a propósito:
  `tests/test_admin_comandos.py::ARBOL_ESPERADO` y
  `commands/admin/diagnostico.py::COMANDOS_ESPERADOS`.
- `tests/test_descripciones_discord.py` valida que toda descripción enviada a
  Discord tenga 1–100 caracteres: cuidá el largo al redactar comandos y opciones.
- Cada bug corregido y cada función nueva debería traer su prueba. Las pruebas
  pueden escribir logs: para logs de terminal se usa `capsys`.

## Prácticas de Discord

- Responder siempre con `core.mensajes` (`responder`, `responder_error`,
  `responder_ok`) para conservar el estilo; los colores salen de `color_area`.
- La ventana de respuesta es de 3 s: si el comando toca la base varias veces,
  `await interaction.response.defer()` antes.
- Avisos que solo le importan a quien ejecuta → `ephemeral=True`. Lo que debe
  ver todo el canal (tarjetas de desafío) va por `interaction.channel` /
  `followup`, no por la respuesta efímera.
- `view=None` **no** es válido en `send_message`/`channel.send` (discord.py usa
  el centinela `MISSING`); en `Message.edit` sí.
- discord.py no permite dos cogs con el mismo `group_name`: cada área tiene un
  único `GroupCog` que compone mixins (`commands/box/cog.py`, `commands/admin/cog.py`).
- Toda llamada a Discord puede dar 429: usá `espera_restante()`/`registrar_limite()`
  de `core/discord_http.py` y nunca imprimas HTML ni el token en los errores
  (usá `resumir_error()`).

## Tareas en segundo plano

- Se arrancan en `cog_load()` (no en `__init__`: los mixins no tienen un
  `super().__init__` válido) y se cancelan en `cog_unload()`.
- `before_loop` espera `bot.wait_until_ready()`.
- Al agregar una tarea, sumá su estado al resumen de arranque en
  `core/bot.py::_imprimir_resumen_inicio()` para poder verla en los logs.

## Logs en terminal

Formato: `[ÁREA] mensaje clave=valor …` con `print(..., flush=True)`. Nada de
logs de depuración efímeros en el commit final.

El canal 420 tiene reglas propias (ver `core/lahora_logs.py` y `README.md`): se
imprime **solo lo que suma** —420 aceptado, podio (1.º–3.º) y cierre de ventana—,
más una línea `⛔` si el 420 se descartó por una sanción. Fuera de horario y
repetidos no se imprimen.

## Sanciones por trampa

Cada minijuego debe respetar `modules/sanciones`:

```python
from modules.sanciones.services import revisar_sancion

if not await revisar_sancion(interaction, "box"):   # clave del minijuego
    return
```

- Se llama en los comandos y botones que **entregan premio o hacen participar**,
  no en los de consulta.
- En código sin interacción (listeners, importaciones) se consulta
  `modules.sanciones.database.sancion_vigente(guild_id, user_id, clave, momento)`.
- Si agregás un minijuego, sumá su clave a `modules/sanciones/logic.py::MINIJUEGOS`
  y bloqueá su punto de entrada.
- Los admins están exentos a propósito.

## Cómo extender (checklists)

**Comando nuevo en un sistema existente**
1. Método en el mixin/cog correspondiente con `@app_commands.command` y
   `@app_commands.describe` (descripción ≤100 caracteres).
2. Lógica en `modules/<area>/logic.py` (puro) y/o `services.py` + `database.py`.
3. Prueba de punta a punta invocando el callback.
4. Si es de `/admin`, además: registralo en el mixin, en la clase `Admin`, en
   `ARBOL_ESPERADO` y en `COMANDOS_ESPERADOS`.

**Sistema nuevo**
1. `modules/<sistema>/` con `logic.py`, `database.py` (`inicializar_db()`) y
   `services.py`.
2. Tablas en `core/esquema.sql`.
3. `commands/<sistema>/` con cog(s) y `__init__.py` con `setup(bot)`.
4. Sumar la extensión a `_SISTEMAS` en `core/bot.py` (nombre, extensión, clase
   del cog, comando raíz y canales) y llamar a su `inicializar_db()` en
   `setup_hook()`.
5. Restricción de canal en `RestrictedCommandTree.interaction_check()`.
6. Color en `core/mensajes.py` si aplica; variables nuevas en
   `config/settings.py` (validadas con `_comprobar`, documentadas en
   `.env.example`).
7. Sanciones, pruebas y documentación.

## Git y entrega

- Trabajá en la rama activa de la sesión; no cambies de rama ni reescribas
  historia ajena.
- Commits en español, en imperativo y con el área adelante
  (`420: log en terminal …`, `Sanciones por trampa …`); el cuerpo explica el
  porqué.
- Subí `VERSION_FUNCION` (y volvé `VERSION_REVISION` a 0) en `core/version.py`
  cuando agregás un sistema o función importante; para retoques menores subí
  `VERSION_REVISION`.
- Actualizá `README.md`/`DOCUMENTACION.md` en el mismo commit que cambia el
  comportamiento visible (comandos, variables, formato de mensajes).
- No commitees `.venv/`, `*.db`, `.env`, `__pycache__/` ni artefactos de prueba.

**Definición de terminado**: `pytest -q` en verde, sin avisos nuevos de
`pyflakes`, comportamiento documentado y probado, y logs/mensajes al usuario en
español y con el formato del bot.

## Trampas conocidas

- Pruebas con fechas viejas que "no registran nada": casi siempre es el corte de
  temporada, no un bug del módulo.
- `interaction.response` ya usado (`InteractionResponded`): usá `responder()`,
  que decide entre `response` y `followup`.
- Un `print` con el error HTTP crudo puede filtrar una página HTML de Cloudflare:
  usá `resumir_error()`.
- Arrancar dos instancias sobre el mismo `.db` duplica tareas (narración de Box,
  corte de temporada) y bloquea SQLite.
