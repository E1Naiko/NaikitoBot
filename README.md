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
BOX_CHANNEL_ID=<ID_CANAL_1>[,<ID_CANAL_2>]
SSF_CANALES_ID=<ID_CANAL>[,<ID_CANAL_2>]
TIMEZONE=America/Argentina/Buenos_Aires
SSF_FECHA_INICIO=YYYY-MM-DD
SSF_FECHA_FIN=YYYY-MM-DD
BOX_EXPERIENCIA_POR_MINUTO=10
BOX_DINERO_POR_MINUTO=100
```

Iniciar el bot:

```text
python main.py
```

## Comandos generales

Todos los comandos y respuestas del bot están limitados a los canales cuyos IDs
se configuren en `BOX_CHANNEL_ID`, separados por comas. En cualquier otro
canal, el bot ignora los comandos slash sin responder.

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

## Comandos de Box

| Comando | Parámetros | Descripción |
| --- | --- | --- |
| `/box entrenar` | `minutos` | Entrena durante el tiempo indicado y otorga experiencia al finalizar. |
| `/box trabajar` | `minutos` | Trabaja durante el tiempo indicado y otorga dinero al finalizar. |
| `/box sparring` | `contrincante` | Envía un desafío de sparring de una hora a otro usuario. |
| `/box desafio` | `contrincante` | Envía un desafío de pelea de una hora a otro usuario. |
| `/box tienda` | Ninguno | Muestra las mejoras y el nivel actual del usuario. |
| `/box comprar` | `mejora` | Compra un nivel de mejora usando dinero. |
| `/box saldo` | Ninguno | Muestra la experiencia y el dinero del usuario. |
| `/box stats` | Ninguno | Muestra tus estadísticas de Box; la respuesta es privada. |
| `/box topdesafios` | Ninguno | Muestra victorias, derrotas y ratio de cada participante. |
| `/box descanso` | Ninguno | Reinicia tu probabilidad de lesión a 0%. |
| `/box tratamiento` | `tipo` | Compra un tratamiento para quitar una lesión. |

La duración debe estar entre 1 y 1440 minutos. Mientras una acción está activa,
el usuario no puede iniciar otra acción de Box. Las recompensas se calculan con
`BOX_EXPERIENCIA_POR_MINUTO` y `BOX_DINERO_POR_MINUTO`; ambas acciones se guardan
en la base de datos y continúan contando aunque el bot se reinicie.

El contrincante debe aceptar el desafío dentro de una hora. Al aceptarlo,
ambos usuarios quedan en modo `SPARRING` durante una hora y reciben experiencia
equivalente a cinco veces la recompensa de entrenamiento de ese mismo tiempo.

`/box desafio` funciona de forma similar, pero inicia el modo `FIGHTING` y
otorga experiencia equivalente a diez veces la recompensa de entrenamiento de
una hora. El ganador se decide al aceptar mediante una probabilidad ponderada
por la experiencia acumulada de ambos usuarios; si uno tiene el doble de
experiencia, tiene el doble de probabilidad. El ganador recibe como dinero la
suma de la experiencia acumulada de ambos contrincantes.

La tienda incluye estas mejoras, con un máximo de nivel 10. El primer nivel
cuesta 1000 y cada compra posterior aumenta el precio un 25% compuesto,
redondeando hacia arriba:

- `Creatina`: suma 5 EXP por minuto de entrenamiento.
- `Cafe`: suma 50 de dinero por minuto de trabajo.

Cada hora de una acción aumenta la probabilidad de lesión en 1%. Al finalizar,
se realiza un sorteo con esa probabilidad. Si el usuario se lesiona, queda en
estado `LESIONADO` durante 24 horas y no puede iniciar acciones ni desafíos.
`/box descanso` reinicia la probabilidad a 0%, pero no cura una lesión activa.
El `Tratamiento Fisioterapeutico` cuesta 10000, quita la lesión y conserva la
probabilidad acumulada. El `Tratamiento 5 estrellas` cuesta 50000, quita la
lesión y reinicia también la probabilidad a 0%.

Para comprar una mejora se utiliza la opción correspondiente:

```text
/box comprar mejora: Creatina
/box comprar mejora: Cafe
```

El precio del siguiente nivel se calcula como `ceil(1000 x 1.25^nivel_actual)`.
Por ejemplo: nivel 0 cuesta 1000, nivel 1 cuesta 1250 y nivel 2 cuesta 1563.

`/box topdesafios` muestra cada participante como `ganadas/perdidas` y calcula
el ratio de victorias divididas por derrotas. Un usuario sin derrotas aparece
con ratio `∞`.

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
