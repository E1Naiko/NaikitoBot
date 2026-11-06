# Despliegue en un servidor Ubuntu

Guía para correr NaikitoBot en un servidor Ubuntu propio (VPS, dedicado o una
máquina de tu red), con systemd para el arranque automático y respaldos
diarios de la base SQLite.

## 1. Resumen: qué hay que preparar

**El código no necesita cambios para Linux.** Es Python puro, no usa procesos
externos ni rutas de Windows, y no abre puertos: solo se conecta a Discord por
HTTPS/WSS. Lo que hay que preparar es el entorno.

| En el bot / repositorio | En el servidor |
| --- | --- |
| `.env` con token, IDs y `DATABASE` absoluta | Python 3.10+ y `python3-venv` |
| Permisos `600` del `.env` (tiene el token) | Usuario de sistema sin login para el bot |
| Una sola instancia por token y base | Servicio systemd con reinicio automático |
| Intents en el Developer Portal | Reloj sincronizado (NTP) |
| Copia de la base si migrás datos | Respaldos periódicos del `.db` |

Tres detalles que suelen morder en un servidor propio:

1. **`DATABASE` con ruta absoluta.** Por defecto es `naikito-v2.db`. Desde este
   cambio las rutas relativas se resuelven contra la raíz del proyecto (no
   contra el directorio de trabajo), pero con el servicio endurecido la carpeta
   del proyecto es de solo lectura: usá siempre
   `DATABASE=/var/lib/naikitobot/naikito-v2.db`.
2. **Una sola instancia.** Dos procesos con el mismo token y la misma base
   duplican tareas (narración de Box, cortes de temporada) y bloquean SQLite.
   Si venías de Wispbyte, apagá ese despliegue antes de arrancar este.
3. **Reloj exacto.** Madrugue, 420 y el corte de temporada dependen de la hora
   local (`TIMEZONE` en el `.env`, por defecto Buenos Aires). Sin NTP, un reloj
   atrasado cobra mal los bonus.

## 2. Requisitos del servidor

- Ubuntu 22.04 LTS (Python 3.10) o 24.04 LTS (Python 3.12). Cualquier distro
  con Python ≥ 3.10 sirve; los comandos de esta guía son de Ubuntu.
- 512 MB de RAM y 1 GB de disco sobran (la base ronda unos pocos MB).
- Salida a internet por **443/TCP** hacia `discord.com`,
  `gateway.discord.gg` y `cdn.discordapp.com`. **No hace falta abrir ningún
  puerto de entrada** salvo SSH.
- Reloj sincronizado: `sudo timedatectl set-ntp true` y comprobar con
  `timedatectl` que diga `System clock synchronized: yes`.
- `git` instalado (`sudo apt install git`). No es obligatorio, pero sin git la
  versión que muestra el arranque usa la fecha de hoy en vez de la del último
  commit.

## 3. Instalación rápida

```bash
sudo apt update
sudo apt install -y python3 python3-venv git

sudo mkdir -p /opt/naikitobot
sudo git clone <url-del-repositorio> /opt/naikitobot/app
cd /opt/naikitobot/app
sudo deploy/instalar.sh
```

El instalador:

- crea el usuario de sistema `naikito` (sin login) y el venv en
  `/opt/naikitobot/app/.venv`;
- crea `/var/lib/naikitobot` (base y respaldos) como único directorio
  escribible del servicio;
- genera el `.env` desde `.env.example` con
  `DATABASE=/var/lib/naikitobot/naikito-v2.db` y permisos `600`;
- instala `naikitobot.service` y el timer de respaldos diarios (04:30);
- habilita el arranque automático y **no arranca** el bot si el token sigue
  siendo el de ejemplo.

Después de completar el `.env` (sección 5):

```bash
sudo systemctl start naikitobot
journalctl -u naikitobot -f
```

Al conectarse, la consola muestra la versión, los sistemas cargados, las
tareas, la sincronización de comandos y los servidores. Confirmá en Discord con
`/ping` y después con `/admin test`, que revisa canales, permisos y base.

Opciones del instalador: `--actualizar` (git pull + dependencias + reinicio) y
variables `NAIKITO_USUARIO`, `NAIKITO_RESPALDOS`, `NAIKITO_SIN_APT`,
`NAIKITO_PERMITIR_HOME` (ver `sudo deploy/instalar.sh --help`).

## 4. Instalación manual

Si preferís no usar el script, los pasos equivalentes son:

```bash
sudo useradd --system --no-create-home --home-dir /nonexistent \
     --shell /usr/sbin/nologin naikito
sudo mkdir -p /var/lib/naikitobot/respaldos
sudo chown -R naikito:naikito /var/lib/naikitobot /opt/naikitobot/app

cd /opt/naikitobot/app
sudo -u naikito python3 -m venv .venv
sudo -u naikito .venv/bin/pip install -r requirements.txt
sudo -u naikito cp .env.example .env
sudo -u naikito nano .env          # token, IDs y DATABASE absoluta
sudo chmod 600 .env
```

Unidad mínima en `/etc/systemd/system/naikitobot.service` (la plantilla
completa, con endurecimiento, está en `deploy/naikitobot.service.in`):

```ini
[Unit]
Description=NaikitoBot (bot de Discord)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=naikito
Group=naikito
WorkingDirectory=/opt/naikitobot/app
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/naikitobot/app/.venv/bin/python main.py
Restart=always
RestartSec=10
StateDirectory=naikitobot

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now naikitobot
```

`StateDirectory=naikitobot` crea `/var/lib/naikitobot` con el dueño correcto y
lo deja escribible aunque el servicio use `ProtectSystem=strict`.

## 5. El `.env`

El archivo vive en la raíz del proyecto (`/opt/naikitobot/app/.env`), nunca en
el repositorio. Variables obligatorias: `DISCORD_TOKEN`, `ADMIN_USER_IDS`,
`GUILD_ID`, `GENERAL_CHANNEL_ID`, `MADRUGUE_CHANNEL_ID`, `BOX_CHANNEL_ID`,
`SSF_CANALES_ID`, `LAHORA_CANALES_ID` y `DATABASE`. El resto tiene valores por
defecto documentados en `.env.example`.

- **Permisos:** `chmod 600 .env` y dueño `naikito`. Contiene el token del bot.
- **`DATABASE`:** ruta absoluta a un archivo escribible, por ejemplo
  `/var/lib/naikitobot/naikito-v2.db`. No uses `DATABASE_URL`: el bot se niega
  a arrancar si la encuentra, para no cambiar de base sin avisar.
- **`TIMEZONE`:** `America/Argentina/Buenos_Aires` por defecto; define horarios
  de Madrugue, ventanas 420 y el corte anual del 3 de octubre.
- **Precedencia:** `python-dotenv` no sobreescribe variables que ya existan en
  el entorno del proceso. Si definís `DISCORD_TOKEN` en la unidad systemd
  (`Environment=`), esa variable vacía o vieja le gana al `.env`. Configurá
  todo en el `.env` y no dupliques nombres en la unidad. El diagnóstico de
  `main.py` distingue estos casos al arrancar.
- **Cambiar el `.env`:** `sudo systemctl restart naikitobot` (no se recarga
  solo).

## 6. Configuración en el Developer Portal de Discord

1. **Intents** (Bot → Privileged Gateway Intents): activá **Message Content**
   (el bot lee los "420" y los comandos) y **Server Members**; el código pide
   ambos. Si faltan, el bot no arranca o falla al iniciar sesión.
2. **Permisos del bot en el servidor:** Ver canales, Enviar mensajes, Insertar
   enlaces, Leer historial (para importar 420 y para las sincronizaciones),
   Añadir reacciones (🌿/🥇) y usar comandos de aplicación.
3. **Invitación:** el bot debe haberse unido con el scope
   `applications.commands`; si lo invitaste solo con `bot`, los slash commands
   no aparecen.
4. **`GUILD_ID`:** con el ID del servidor, los comandos se sincronizan al
   instante en ese servidor. Sin `GUILD_ID` la sincronización es global y puede
   tardar hasta una hora en propagarse.

## 7. Migrar la base desde el hosting anterior

La base es un único archivo SQLite; no hay servidor de base de datos.

```text
# 1. Detener el bot en el hosting viejo (y que no se reinicie solo).
# 2. Descargar el archivo .db.
# 3. En el servidor nuevo:
sudo install -o naikito -g naikito -m 0640 /tmp/naikito-v2.db \
     /var/lib/naikitobot/naikito-v2.db
sudo systemctl start naikitobot
```

- Detené el bot antes de copiar para que la copia sea consistente. Si no podés
  detenerlo, usá el respaldo en caliente:
  `python -m scripts.respaldar_db --destino /tmp/respaldos`.
- El bot **no usa WAL** (journal por defecto), así que con el proceso detenido
  el `.db` alcanza. Si junto al archivo aparecen `-wal`/`-shm`, copialos
  también.
- El esquema se crea o completa solo al arrancar; no borra datos existentes.
- Al abrir una base de otra temporada, se aplica el corte del 3 de octubre
  (ver README, «Temporada anual»). Hacé un respaldo antes del primer arranque.
- Con una base nueva, la sincronización 420 arranca desde el primer chequeo;
  para recuperar historial usá `/admin 420 importar`.

## 8. Operación diaria

```bash
sudo systemctl status naikitobot      # estado
sudo systemctl restart naikitobot     # tras cambiar .env o el código
sudo systemctl stop naikitobot        # antes de copiar/restaurar la base
journalctl -u naikitobot -f           # log en vivo
journalctl -u naikitobot --since today
journalctl -u naikitobot -u naikitobot-respaldo --since "1 hour ago"
```

- El log va a journald (stdout del proceso), con rotación automática: no hace
  falta logrotate ni archivos de log propios. `journalctl --vacuum-time=30d`
  limita el histórico si ocupa espacio.
- **Cierre:** `systemctl stop` manda SIGTERM. Las escrituras SQLite se
  confirman en cada operación, así que el archivo queda consistente aunque el
  proceso no cierre «prolijo». No hace falta `kill -9`.
- **Una sola instancia:** no levantes una segunda copia «para probar» con el
  mismo token y base. Para pruebas locales usá otro token y otro `DATABASE`.
- **Reinicios automáticos:** la unidad usa `Restart=always`. Si el bot falla al
  arrancar por configuración inválida, systemd corta el bucle a los 5 intentos
  en 5 minutos (`StartLimitBurst`); revisá el log y corregí el `.env`.

## 9. Respaldos

El instalador crea `naikitobot-respaldo.timer`, que corre todos los días a las
04:30 (hora del servidor) y conserva las últimas 14 copias en
`/var/lib/naikitobot/respaldos`.

```bash
sudo systemctl list-timers naikitobot-respaldo.timer   # próximo respaldo
sudo systemctl start naikitobot-respaldo.service       # respaldo ahora
sudo -u naikito /opt/naikitobot/app/.venv/bin/python \
     -m scripts.respaldar_db --conservar 30            # manual, otra retención
```

El respaldo usa la API de copia de SQLite, así que es consistente **aunque el
bot esté escribiendo**. Restaurar:

```bash
sudo systemctl stop naikitobot
sudo install -o naikito -g naikito -m 0640 \
     /var/lib/naikitobot/respaldos/naikito-v2-AAAAMMDD-HHMMSS.db \
     /var/lib/naikitobot/naikito-v2.db
sudo systemctl start naikitobot
```

Guardá copias fuera del servidor (`rsync`/`scp` a otra máquina): un respaldo en
el mismo disco no protege de perder el disco.

## 10. Actualizar el bot

```bash
cd /opt/naikitobot/app
sudo deploy/instalar.sh --actualizar
```

Equivale a `git pull --ff-only`, `pip install -r requirements.txt` y
`systemctl restart`. El proyecto quedó con dueño `naikito`, por eso el pull se
hace con `sudo`. Si cambiaron variables nuevas, compará `.env.example` con tu
`.env` antes de reiniciar.

## 11. Cosas que NO hacen falta

- No hace falta Docker, nginx, base de datos externa ni un puerto abierto.
- No hace falta `tzdata` extra: en Linux se usa la base de zonas del sistema
  (`sudo apt install tzdata` si el sistema quedó sin ella).
- No hace falta copiar `data/madrugue_historico.csv` a ningún lado: es
  material de importación manual (`scripts/importar_madrugue_historico.py`).
- No hace falta `requirements-dev.txt` en producción; solo `pytest` para
  correr las pruebas (`sudo -u naikito .venv/bin/pip install -r requirements-dev.txt`).

## 12. Problemas comunes

| Síntoma en el log | Causa y solución |
| --- | --- |
| `DIAGNÓSTICO: no se encontró DISCORD_TOKEN` | `.env` ausente, con la clave comentada o vacía, o una variable `DISCORD_TOKEN` vacía en la unidad systemd que le gana al archivo. Revisá permisos (`600`, dueño `naikito`). |
| `403 Forbidden` / `PrivilegedIntentsRequired` al conectar | Faltan los intents **Message Content** o **Server Members** en el Developer Portal. |
| `ZoneInfoNotFoundError` | Falta la base de zonas: `sudo apt install tzdata`. |
| `sqlite3.OperationalError: unable to open database file` | `DATABASE` apunta a una ruta que el usuario del servicio no puede escribir. Usá `/var/lib/naikitobot/...` (creado por `StateDirectory`) y revisá el dueño. |
| `database is locked` | Otra instancia del bot o un `git`/script abriendo la base. Una sola instancia por archivo. |
| `429` con HTML y `Cloudflare Error 1015` | Bloqueo temporal por IP de salida (muy común en hostings compartidos; menos en un servidor propio). El bot espera y reintenta solo al arrancar. No reinicies en bucle: dejalo esperar. |
| El servicio reinicia en bucle y no hay log útil | `journalctl -u naikitobot -n 100 --no-pager`; suele ser una variable inválida del `.env` (el mensaje nombra la variable culpable). |
| Los slash commands no aparecen | El bot no se invitó con `applications.commands`, o `GUILD_ID` está mal. Con `GUILD_ID` correcto aparecen al instante tras reiniciar. |
| `/420` no registra nada | Falta el intent Message Content o permisos de canal (Ver canal, Leer historial, Añadir reacciones). `/admin test` lo detalla. |

## 13. Checklist final

- [ ] Ubuntu con Python ≥ 3.10, `python3-venv`, `git` y NTP activo.
- [ ] Repositorio en `/opt/naikitobot/app` (fuera de `/home`).
- [ ] `.env` completo, `chmod 600`, sin `DATABASE_URL`, con `DATABASE` absoluta.
- [ ] Intents **Message Content** y **Server Members** activos; bot invitado con
      `applications.commands`.
- [ ] `systemctl status naikitobot` en `active (running)` y arranque
      habilitado (`enable`).
- [ ] `/ping` y `/admin test` responden en Discord.
- [ ] `timers` muestra el respaldo diario y hay al menos una copia en
      `/var/lib/naikitobot/respaldos`.
- [ ] El despliegue anterior (Wispbyte) está apagado.
