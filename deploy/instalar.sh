#!/usr/bin/env bash
# Instalación de NaikitoBot como servicio systemd en Ubuntu.
#
#   sudo deploy/instalar.sh              # primera instalación / reconfiguración
#   sudo deploy/instalar.sh --actualizar # git pull + dependencias + reinicio
#
# Qué hace:
#   1. Comprueba Python 3.10+, git y el módulo venv.
#   2. Crea un usuario de sistema sin login y un venv en la carpeta del proyecto.
#   3. Deja el .env con permisos 600 y una ruta ABSOLUTA de base SQLite.
#   4. Genera e instala naikitobot.service y el timer de respaldos diarios.
#   5. Habilita el arranque automático (no arranca el bot si el token sigue
#      siendo el de ejemplo).
#
# Variables opcionales:
#   NAIKITO_USUARIO=naikito    usuario del servicio
#   NAIKITO_RESPALDOS=14       copias que conserva la rotación
#   NAIKITO_PERMITIR_HOME=1    permitir el proyecto dentro de /home
#   NAIKITO_SIN_APT=1          no intentar instalar paquetes con apt
#
# Ver DESPLIEGUE.md para el paso a paso y la operación diaria.

set -euo pipefail

USUARIO="${NAIKITO_USUARIO:-naikito}"
CONSERVAR="${NAIKITO_RESPALDOS:-14}"
NOMBRE_DIRECTORIO_ESTADO="naikitobot"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIRECTORIO_ESTADO="/var/lib/${NOMBRE_DIRECTORIO_ESTADO}"
UNIDADES="/etc/systemd/system"
MODO_ACTUALIZAR=0

mostrar_ayuda() {
    cat <<'AYUDA'
Uso: sudo deploy/instalar.sh [--actualizar]

  (sin argumentos)  instala o reconfigura el servicio y el respaldo diario.
  --actualizar      trae los últimos cambios (git pull), actualiza las
                    dependencias y reinicia el bot.
  --help            muestra esta ayuda.

Variables de entorno opcionales:
  NAIKITO_USUARIO       usuario de sistema que corre el bot (naikito)
  NAIKITO_RESPALDOS     copias que conserva la rotación (14)
  NAIKITO_PERMITIR_HOME 1 para aceptar el proyecto dentro de /home
  NAIKITO_SIN_APT       1 para no instalar paquetes con apt
AYUDA
}

for argumento in "$@"; do
    case "$argumento" in
        --actualizar) MODO_ACTUALIZAR=1 ;;
        -h|--help) mostrar_ayuda; exit 0 ;;
        *) echo "Argumento desconocido: $argumento" >&2; mostrar_ayuda >&2; exit 2 ;;
    esac
done

informe() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
paso()   { printf '  - %s\n' "$*"; }
fallo()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
aviso()  { printf '  ! %s\n' "$*" >&2; }

[[ $EUID -eq 0 ]] || fallo "Ejecutá el instalador con sudo."
[[ -f "$APP_DIR/main.py" && -f "$APP_DIR/requirements.txt" ]] \
    || fallo "No encuentro main.py en $APP_DIR. ¿Moviste el instalador de deploy/?."
[[ -f "$APP_DIR/deploy/naikitobot.service.in" ]] \
    || fallo "Falta deploy/naikitobot.service.in en $APP_DIR."
[[ "$APP_DIR" != "/" ]] || fallo "Ruta de proyecto inválida."

if [[ -z "${NAIKITO_PERMITIR_HOME:-}" && "$APP_DIR" == /home/* ]]; then
    fallo "El proyecto está dentro de /home ($APP_DIR), que el servicio no puede
leer. Cloná el repositorio en /opt/naikitobot/app y volvé a ejecutar:
  sudo mkdir -p /opt/naikitobot
  sudo git clone <url-del-repo> /opt/naikitobot/app
Si querés mantenerlo en /home, ejecutá con NAIKITO_PERMITIR_HOME=1 (el
servicio tendrá acceso a esa home y menos aislamiento)."
fi

PROTEGER_HOME="yes"
[[ "$APP_DIR" == /home/* ]] && PROTEGER_HOME="no"

# ------------------------------------------------------------------
# Python y dependencias del sistema
# ------------------------------------------------------------------

informe "Comprobando Python"
command -v python3 >/dev/null 2>&1 || fallo "Falta python3 (apt install python3)."

VERSION_PYTHON="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
paso "python3 encontrado: $VERSION_PYTHON"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    || fallo "Se necesita Python 3.10 o superior; este servidor tiene $VERSION_PYTHON.
Ubuntu 22.04 trae 3.10 y Ubuntu 24.04 trae 3.12."

if ! python3 -m venv --help >/dev/null 2>&1 && [[ -z "${NAIKITO_SIN_APT:-}" ]]; then
    informe "Instalando python3-venv"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv
fi
python3 -m venv --help >/dev/null 2>&1 \
    || fallo "Falta el módulo venv (apt install python3-venv)."

if ! command -v git >/dev/null 2>&1; then
    aviso "No hay git: el bot funciona igual, pero la versión mostrará la fecha"
    aviso "de hoy en vez de la del último commit."
fi

# ------------------------------------------------------------------
# Usuario y directorios de datos
# ------------------------------------------------------------------

informe "Usuario y directorios"
if id -u "$USUARIO" >/dev/null 2>&1; then
    paso "El usuario '$USUARIO' ya existe."
else
    useradd --system --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin "$USUARIO"
    paso "Creado el usuario de sistema '$USUARIO' (sin login)."
fi

install -d -o "$USUARIO" -g "$USUARIO" -m 0750 "$DIRECTORIO_ESTADO"
install -d -o "$USUARIO" -g "$USUARIO" -m 0750 "$DIRECTORIO_ESTADO/respaldos"
paso "$DIRECTORIO_ESTADO queda como único directorio escribible del servicio."

# HOME inexistente: pip no debe intentar escribir su caché en /nonexistent.
HOME_USUARIO="$DIRECTORIO_ESTADO"
como_usuario() { sudo -u "$USUARIO" env HOME="$HOME_USUARIO" "$@"; }

# ------------------------------------------------------------------
# Código y dependencias
# ------------------------------------------------------------------

if [[ $MODO_ACTUALIZAR -eq 1 ]]; then
    informe "Actualizando el código"
    command -v git >/dev/null 2>&1 \
        || fallo "No hay git instalado (apt install git) para usar --actualizar."
    como_usuario git -C "$APP_DIR" pull --ff-only
fi

informe "Instalando dependencias en el venv"
chown -R "$USUARIO:$USUARIO" "$APP_DIR"
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
    como_usuario python3 -m venv "$APP_DIR/.venv"
    paso "Venv creado en $APP_DIR/.venv"
fi
como_usuario "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
como_usuario "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
paso "requirements.txt instalado."

# ------------------------------------------------------------------
# Configuración (.env)
# ------------------------------------------------------------------

informe "Configuración"
RUTA_BASE="$DIRECTORIO_ESTADO/naikito-v2.db"

if [[ ! -f "$APP_DIR/.env" ]]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    sed -i "s|^DATABASE=.*|DATABASE=$RUTA_BASE|" "$APP_DIR/.env"
    paso "Creado .env a partir de .env.example."
fi
chown "$USUARIO:$USUARIO" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

PENDIENTES=0

if grep -q '^DATABASE_URL=.\+' "$APP_DIR/.env"; then
    fallo "El .env define DATABASE_URL, que ya no está soportada: borrá esa línea."
fi

if ! grep -q '^DATABASE=' "$APP_DIR/.env"; then
    printf '\nDATABASE=%s\n' "$RUTA_BASE" >> "$APP_DIR/.env"
    paso "Agregado DATABASE=$RUTA_BASE al .env."
elif ! grep -q '^DATABASE=/' "$APP_DIR/.env"; then
    PENDIENTES=1
    aviso "DATABASE no es una ruta absoluta. Con el servicio endurecido el"
    aviso "proyecto es de solo lectura; cambiala a DATABASE=$RUTA_BASE"
else
    RUTA_BASE="$(sed -n 's/^DATABASE=//p' "$APP_DIR/.env" | head -n1)"
    paso "Base configurada: $RUTA_BASE"
fi

if grep -q '^DISCORD_TOKEN=replace_with_your_bot_token' "$APP_DIR/.env" \
   || ! grep -q '^DISCORD_TOKEN=.\+' "$APP_DIR/.env"; then
    PENDIENTES=1
    aviso "Falta cargar DISCORD_TOKEN, ADMIN_USER_IDS, GUILD_ID y los canales"
    aviso "en $APP_DIR/.env."
fi

# ------------------------------------------------------------------
# Unidades systemd
# ------------------------------------------------------------------

informe "Instalando unidades systemd"
renderizar() {
    # $1 plantilla de origin, $2 destino
    sed -e "s|@APP_DIR@|$APP_DIR|g" \
        -e "s|@USUARIO@|$USUARIO|g" \
        -e "s|@DIRECTORIO_ESTADO@|$NOMBRE_DIRECTORIO_ESTADO|g" \
        -e "s|@PROTEGER_HOME@|$PROTEGER_HOME|g" \
        -e "s|@CONSERVAR@|$CONSERVAR|g" \
        "$1" > "$2"
    chmod 644 "$2"
}

renderizar "$APP_DIR/deploy/naikitobot.service.in" \
    "$UNIDADES/naikitobot.service"
renderizar "$APP_DIR/deploy/naikitobot-respaldo.service.in" \
    "$UNIDADES/naikitobot-respaldo.service"
renderizar "$APP_DIR/deploy/naikitobot-respaldo.timer" \
    "$UNIDADES/naikitobot-respaldo.timer"
paso "naikitobot.service + naikitobot-respaldo.service/.timer"

systemctl daemon-reload
systemctl enable --quiet naikitobot.service
systemctl enable --quiet naikitobot-respaldo.timer
systemctl start naikitobot-respaldo.timer
paso "Arranque automático y respaldo diario habilitados."

if [[ $MODO_ACTUALIZAR -eq 1 ]]; then
    systemctl restart naikitobot.service
    paso "Servicio reiniciado."
elif [[ $PENDIENTES -eq 1 ]]; then
    systemctl stop naikitobot.service 2>/dev/null || true
    paso "El servicio queda habilitado pero detenido hasta completar el .env."
else
    systemctl restart naikitobot.service
    paso "Servicio iniciado."
fi

# ------------------------------------------------------------------
# Resumen
# ------------------------------------------------------------------

informe "Listo"
cat <<FIN
  Proyecto:   $APP_DIR
  Usuario:    $USUARIO
  Base:       $RUTA_BASE
  Respaldos:  $DIRECTORIO_ESTADO/respaldos ($CONSERVAR copias, diario 04:30)
  Estado:     systemctl status naikitobot
  Log:        journalctl -u naikitobot -f
  Actualizar: sudo deploy/instalar.sh --actualizar
FIN

if [[ $PENDIENTES -eq 1 ]]; then
cat <<FIN

  Falta completar $APP_DIR/.env (sudoedit, permisos 600):
    DISCORD_TOKEN=...
    ADMIN_USER_IDS=...
    GUILD_ID=...
    GENERAL_CHANNEL_ID=... / MADRUGUE_CHANNEL_ID=... / BOX_CHANNEL_ID=...
    SSF_CANALES_ID=... / LAHORA_CANALES_ID=...

  Después:
    sudo systemctl start naikitobot
    journalctl -u naikitobot -f
FIN
fi
