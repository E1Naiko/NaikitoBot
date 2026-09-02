# NaikitoBot

Bot de Discord para uso personal.

## Requisitos

- Python 3.10 o superior.
- Un bot de Discord con los intents necesarios habilitados.
- Permisos para usar comandos y enviar mensajes en los canales configurados.

## Instalación

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Crear un archivo `.env` en la raíz del proyecto:

```dotenv
DISCORD_TOKEN=<TOKEN_DEL_BOT>
ADMIN_USER_IDS=<ID_USUARIO_ADMIN>[,<ID_USUARIO_ADMIN_2>]
GUILD_ID=<ID_SERVIDOR>
SSF_CANALES_ID=<ID_CANAL>[,<ID_CANAL_2>]
TIMEZONE=America/Argentina/Buenos_Aires
SSF_FECHA_INICIO=YYYY-MM-DD
SSF_FECHA_FIN=YYYY-MM-DD
```

Iniciar el bot:

```text
python main.py
```

## Comandos generales

| Comando | Descripción |
| --- | --- |
| `/ping` | Comprueba que el bot está funcionando y muestra su latencia. |

## Comandos de Madrugue

| Comando | Descripción |
| --- | --- |
| `/madrugue` | Registra la madrugada del usuario actual. |
| `/madrugue_stats` | Muestra los puntos acumulados y la mejor racha del usuario actual. |
| `/madrugue_top` | Muestra el ranking histórico de madrugadores del servidor. |
| `/madrugue_ayuda` | Muestra la ayuda y los horarios de Madrugue. |

Horarios de puntuación:

- 05:30 a 06:59: 100 puntos.
- 07:00 a 08:59: 25 puntos.
- 09:00 a 09:59: 5 puntos.
- Desde las 10:00: fuera de horario.

## Comandos de SeptSinFP

| Comando | Descripción |
| --- | --- |
| `/ssf registrar` | Registra al usuario actual como participante. |
| `/ssf sobrevivi` | Registra que el usuario actual sobrevivió el día. |
| `/ssf estado` | Muestra el estado y las rachas del usuario actual. |
| `/ssf participantes` | Muestra los participantes activos y eliminados. |
| `/ssf ayuda` | Muestra la ayuda del desafío. |

Estos comandos deben utilizarse en los canales incluidos en `SSF_CANALES_ID`,
salvo los que no requieren un canal específico según su implementación.

## Comandos administrativos

Todos los comandos bajo `/admin` requieren que el usuario esté incluido en
`ADMIN_USER_IDS`.

| Comando | Parámetros | Descripción |
| --- | --- | --- |
| `/admin info` | Ninguno | Muestra información de configuración. |
| `/admin stats` | Ninguno | Muestra las estadísticas generales de Madrugue. |
| `/admin top` | Ninguno | Muestra el ranking de Madrugue. |
| `/admin resetdia` | `usuario`, `fecha` | Elimina el registro de un usuario para una fecha. |
| `/admin resetusuario` | `usuario` | Elimina todos los registros de un usuario. |
| `/admin resettotal` | `confirmar`: `SI` o `NO` | Elimina todos los registros del servidor cuando se confirma. |
| `/admin manualadd` | `usuario`, `fecha`, `hora` | Agrega manualmente una madrugada. |
| `/admin ssf revivir` | `usuario`, `fecha` | Revive a un participante eliminado en una fecha. |
| `/admin ssf iniciar` | `canal` | Inicia un desafío SeptSinFP en un canal. |
| `/admin fileexecute` | `archivo` | Ejecuta comandos administrativos desde un archivo TXT. |

Ejemplo de formatos para los parámetros:

```text
usuario: <ID_USUARIO> o <@ID_USUARIO>
fecha: YYYY-MM-DD
hora: HH:MM
canal: <ID_CANAL> o <#ID_CANAL>
```

## Ejecución desde archivo

`/admin fileexecute` recibe un archivo `.txt` y ejecuta cada línea como un comando
administrativo independiente. El archivo puede contener hasta 50 comandos y medir
hasta 1 MiB.

Se aceptan estas formas:

```text
manualadd <ID_USUARIO> YYYY-MM-DD HH:MM
resetdia <@ID_USUARIO> YYYY-MM-DD
resetusuario <ID_USUARIO>
resettotal SI
ssf revivir <ID_USUARIO> YYYY-MM-DD
ssf iniciar <ID_CANAL>
info
stats
top
```

También se puede escribir `/admin` al comienzo de cada línea:

```text
/admin manualadd <ID_USUARIO> YYYY-MM-DD HH:MM
/admin ssf revivir <@ID_USUARIO> YYYY-MM-DD
```

Las líneas vacías y las que comienzan con `#` se ignoran. Solo se ejecutan comandos
del grupo `/admin`; no se permite ejecutar código Python ni comandos externos.
