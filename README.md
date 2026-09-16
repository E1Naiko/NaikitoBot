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

Crear un archivo `.env` en la raíz del proyecto a partir de `.env.example`.
No subas `.env` al repositorio: contiene el token del bot.

`requirements.txt` incluye `tzdata`. Es obligatorio en Windows: el sistema no
trae la base de datos de zonas horarias de IANA y `config/settings.py` construye
`ZoneInfo("America/Argentina/Buenos_Aires")` al importar el módulo, así que sin
ese paquete el bot falla al arrancar con
`ZoneInfoNotFoundError: 'No time zone found with key America/Argentina/Buenos_Aires'`.

## Pruebas

Las pruebas no necesitan token de Discord ni conexión: usan dobles de
`discord.Interaction` y una base de datos SQLite temporal.

```text
pip install -r requirements-dev.txt
pytest
```

```dotenv
DISCORD_TOKEN=<TOKEN_DEL_BOT>
ADMIN_USER_IDS=<ID_USUARIO_ADMIN>[,<ID_USUARIO_ADMIN_2>]
GUILD_ID=<ID_SERVIDOR>
GENERAL_CHANNEL_ID=<ID_CANAL_GENERAL>
MADRUGUE_CHANNEL_ID=<ID_CANAL_MADRUGUE>
BOX_CHANNEL_ID=<ID_CANAL_1>[,<ID_CANAL_2>]
SSF_CANALES_ID=<ID_CANAL>[,<ID_CANAL_2>]
TIMEZONE=America/Argentina/Buenos_Aires
SSF_FECHA_INICIO=YYYY-MM-DD
SSF_FECHA_FIN=YYYY-MM-DD
BOX_EXPERIENCIA_POR_MINUTO=10
BOX_DINERO_POR_MINUTO=100
BOX_PRECIO_MULTIPLICADOR=1.0
BOX_LESION_HORAS=3
BOX_DESAFIO_DURACION_HORAS=1
BOX_COMBATE_ACTIVO=1
BOX_COMBATE_TICK_SEGUNDOS=15
MADRUGUE_INICIO_100=05:30
MADRUGUE_INICIO_25=07:00
MADRUGUE_INICIO_5=09:00
MADRUGUE_FIN=10:00
MADRUGUE_PUNTOS_100=100
MADRUGUE_PUNTOS_25=25
MADRUGUE_PUNTOS_5=5
MADRUGUE_BONUS_MAXIMO=0.100
MADRUGUE_BONUS_MINIMO=0.001
```

El archivo `.env.example` documenta todas las variables disponibles, incluidas
las de balance de Box (precios de la tienda, lesiones, desafíos y sponsors).

En el proveedor de despliegue, configura estas mismas variables como variables
de entorno. No es necesario subir el archivo `.env`; el bot también funciona
con variables definidas directamente por la plataforma.

## Presentación

Las respuestas del bot usan la capa común `core/mensajes.py`, que arma embeds
con un color por área (Box, Madrugue, SeptSinFP, admin o general) y secciones
ordenadas (`crear_embed`, `responder`, `responder_error`, etc.). Usar esas
helpers mantiene el formato consistente entre comandos.

Iniciar el bot:

```text
python main.py
```

## Comandos generales

Los comandos están separados por canales: `GENERAL_CHANNEL_ID` permite los
comandos generales; `BOX_CHANNEL_ID` permite los comandos de Box;
`MADRUGUE_CHANNEL_ID` permite solo Madrugue; y `SSF_CANALES_ID` permite solo
SeptSinFP. Los IDs pueden separarse por comas. Los usuarios incluidos en
`ADMIN_USER_IDS` quedan exentos de la restricción de canal: pueden usar
cualquier comando desde cualquier canal.

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

Horarios de puntuación (valores por defecto; se configuran en `.env`):

- 05:30 a 06:59: 100 puntos.
- 07:00 a 08:59: 25 puntos.
- 09:00 a 09:59: 5 puntos.
- Desde las 10:00: fuera de horario.

La puntuación de Madrugue se configura con variables de entorno: las ventanas
con `MADRUGUE_INICIO_100`, `MADRUGUE_INICIO_25`, `MADRUGUE_INICIO_5` y
`MADRUGUE_FIN` (horas en formato `HH:MM`); los puntos de cada ventana con
`MADRUGUE_PUNTOS_100`, `MADRUGUE_PUNTOS_25` y `MADRUGUE_PUNTOS_5`; y el bonus
horario con `MADRUGUE_BONUS_MAXIMO` y `MADRUGUE_BONUS_MINIMO`: el
multiplicador baja linealmente de `1 + MADRUGUE_BONUS_MAXIMO` al abrir la
madrugada a `1 + MADRUGUE_BONUS_MINIMO` al cerrarla. Los textos de los
comandos (`/madrugue`, `/madrugue_ayuda` y `/admin manualadd`) se arman con
estos valores. Un valor inválido (una hora fuera del formato `HH:MM`, ventanas
desordenadas, puntos negativos o el bonus invertido) impide que el bot arranque
con un error que indica la variable culpable.

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
`ADMIN_USER_IDS` y están organizados en subgrupos por área (`/admin madrugue`,
`/admin ssf`, `/admin box`). Los administradores quedan exentos de la
restricción de canal: pueden usar cualquier comando desde cualquier canal.

### Sistema

| Comando | Parámetros | Descripción |
| --- | --- | --- |
| `/admin info` | Ninguno | Muestra la configuración del bot: canales, tasas de Box, fechas de SeptSinFP y zona horaria. |
| `/admin fileexecute` | `archivo` | Ejecuta comandos administrativos desde un archivo TXT. |

### Madrugue

| Comando | Parámetros | Descripción |
| --- | --- | --- |
| `/admin madrugue stats` | Ninguno | Muestra las estadísticas generales de Madrugue. |
| `/admin madrugue top` | Ninguno | Muestra el ranking de Madrugue. |
| `/admin madrugue ver` | `usuario` | Muestra el resumen, rachas y últimos registros de un usuario. |
| `/admin madrugue resetdia` | `usuario`, `fecha` | Elimina el registro de un usuario para una fecha. |
| `/admin madrugue resetusuario` | `usuario` | Elimina todos los registros de un usuario. |
| `/admin madrugue resettotal` | `confirmar`: `SI` o `NO` | Elimina todos los registros del servidor cuando se confirma. |
| `/admin madrugue manualadd` | `usuario`, `fecha`, `hora` | Agrega manualmente una madrugada. |

### SeptSinFP

| Comando | Parámetros | Descripción |
| --- | --- | --- |
| `/admin ssf estado` | `usuario` | Muestra el estado, rachas y rango de cualquier participante. |
| `/admin ssf desafio` | Ninguno | Muestra el estado global del desafío activo. |
| `/admin ssf participantes` | Ninguno | Lista los participantes con racha actual y mejor racha. |
| `/admin ssf ranking` | Ninguno | Muestra el ranking del desafío activo (o del último cerrado). |
| `/admin ssf iniciar` | `canal`, `fecha_inicio`?, `fecha_fin`?, `nombre`? | Inicia un desafío SeptSinFP. Por defecto usa las fechas de `SSF_FECHA_INICIO` y `SSF_FECHA_FIN`. |
| `/admin ssf revivir` | `usuario`, `fecha` | Revive a un participante eliminado en una fecha. |
| `/admin ssf eliminar` | `usuario`, `fecha` | Marca eliminado a un participante que no registró un día. |
| `/admin ssf agregar` | `usuario`, `fecha` | Agrega manualmente un día a un participante activo. |
| `/admin ssf quitar` | `usuario`, `fecha` | Quita manualmente un día a un participante. |
| `/admin ssf recalcular` | `usuario` | Recalcula las rachas desde los registros guardados. |
| `/admin ssf cerrar` | `confirmar`: `SI` o `NO` | Cierra el desafío activo y lo deja listo para su ranking final. |

### Box

| Comando | Parámetros | Descripción |
| --- | --- | --- |
| `/admin box info` | `usuario` | Muestra toda la información Box de un usuario. |
| `/admin box top` | Ninguno | Muestra el ranking del servidor por EXP y dinero. |
| `/admin box stats` | Ninguno | Muestra estadísticas globales de Box del servidor. |
| `/admin box historial` | `usuario` | Muestra los últimos combates de un usuario. |
| `/admin box sponsors` | `usuario` | Muestra los sponsors activos de un usuario. |
| `/admin box lesionados` | Ninguno | Lista los usuarios con lesión activa o probabilidad acumulada. |
| `/admin box dar_dinero` | `usuario`, `cantidad` | Suma o resta dinero Box a un usuario. |
| `/admin box dar_exp` | `usuario`, `cantidad` | Suma o resta experiencia Box a un usuario. |
| `/admin box curar` | `usuario` | Cura la lesión activa de un usuario. |
| `/admin box probabilidad` | `usuario`, `probabilidad` | Establece la probabilidad de lesión de un usuario. |
| `/admin box cancelar` | `usuario` | Cancela la acción Box activa de un usuario sin recompensa. |
| `/admin box finalizar` | `usuario` | Liquida ya la acción vencida de un usuario y le entrega la recompensa. |
| `/admin box procesar` | Ninguno | Liquida todas las acciones vencidas del servidor. |
| `/admin box dar_sponsor` | `usuario`, `tipo` | Otorga manualmente un sponsor a un usuario. |
| `/admin box quitar_sponsor` | `usuario`, `sponsor_id` | Elimina un sponsor específico de un usuario. |
| `/admin box reset` | `usuario` | Resetea completamente el progreso Box de un usuario. |
| `/admin box canticos` | `estado` | Activa, desactiva o consulta el consentimiento del servidor para los cánticos que nombran miembros. |
| `/admin box cerrar_combate` | Ninguno | Cierra la pelea narrada que está ocupando el canal, sin tocar acciones ni recompensas. |

Ejemplo de formatos para los parámetros:

```text
usuario: <ID_USUARIO> o <@ID_USUARIO>
fecha: YYYY-MM-DD
hora: HH:MM
canal: <ID_CANAL> o <#ID_CANAL>
probabilidad: número entre 0 y 100
tipo: redes | radio | equipamiento | medico
```

### Reparación manual de SeptSinFP

Los registros diarios (`ssf_registros`) son la fuente de verdad y ningún flujo
del juego los borra; las rachas mostradas son un caché calculado desde ellos.
Si la racha mostrada queda incorrecta, se corrige sin tocar el estado de
eliminado:

- `/admin ssf recalcular <usuario>`: restaura ambas rachas desde los registros.
  Es la reparación para participantes eliminados con la racha en 0.
- `/admin ssf agregar <usuario> <fecha>`: suma un día a un participante activo
  (rechaza eliminados —para ellos existe `revivir`— y fechas futuras).
- `/admin ssf quitar <usuario> <fecha>`: saca un día, incluso a eliminados, sin
  cambiar su estado.
- `/admin ssf eliminar <usuario> <fecha>`: replica la eliminación automática
  para un día que no se procesó (por ejemplo, si el bot estuvo caído). Rechaza
  a participantes que sí registraron ese día.

Ejemplo: un participante revivido con la fecha de hoy (`2026-09-05`) en vez del
día perdido (`2026-09-04`) queda con racha 1. Se corrige con
`/admin ssf quitar <usuario> 2026-09-05` seguido de
`/admin ssf agregar <usuario> 2026-09-04`, y vuelve a 4 días.

## Comandos de Box

| Comando | Parámetros | Descripción |
| --- | --- | --- |
| `/box entrenar` | `minutos` o `hasta` | Entrena durante el tiempo indicado o hasta una hora `HH:MM`. |
| `/box trabajar` | `minutos` o `hasta` | Trabaja durante el tiempo indicado o hasta una hora `HH:MM`. |
| `/box sparring` | `contrincante` | Envía un desafío de sparring de una hora a otro usuario. |
| `/box desafio` | `contrincante` | Envía un desafío de pelea de una hora a otro usuario. |
| `/box cancelar` | `contrincante` (opcional) | Retira una solicitud de sparring o pelea pendiente: la que mandaste o la que te mandaron. |
| `/box tienda` | Ninguno | Muestra el catálogo con el nivel actual y un botón por artículo para comprarlo. |
| `/box comprar` | `tipo` y `articulo` | Compra una mejora, una pieza de equipamiento o un tratamiento usando dinero. |
| `/box saldo` | Ninguno | Muestra la experiencia y el dinero del usuario. |
| `/box stats` | Ninguno | Muestra tus estadísticas de Box; la respuesta es privada. |
| `/box topdesafios` | Ninguno | Muestra victorias, derrotas y ratio de cada participante. |
| `/box combate` | Ninguno | Muestra cómo va tu pelea o sparring narrado en vivo. |
| `/box descanso` | Ninguno | Reinicia tu probabilidad de lesión a 0%. |
| `/box tratamiento` | `tipo` | Compra un tratamiento para quitar una lesión. |
| `/box suministro` | `tipo` | Usa suministros de recuperación (vida, cansancio, defensa o lesión). |
| `/box ayuda` | Ninguno | Envía por mensaje directo la lista de comandos de Box. |

Los comandos de Box solo pueden usarse en los canales incluidos en
`BOX_CHANNEL_ID`, salvo que el usuario esté en `ADMIN_USER_IDS`. Los botones
de la tienda y los de aceptar desafíos siguen la misma restricción.

La duración debe estar entre `BOX_MINUTOS_MINIMO` y `BOX_MINUTOS_MAXIMO`
minutos (1 y 1440 por defecto). Mientras una acción está activa, el usuario no
puede iniciar otra acción de Box. Las recompensas se calculan con
`BOX_EXPERIENCIA_POR_MINUTO` y `BOX_DINERO_POR_MINUTO`; ambas acciones se guardan
en la base de datos y continúan contando aunque el bot se reinicie.

El contrincante debe aceptar el desafío dentro de `BOX_DESAFIO_DURACION_HORAS`
(una hora por defecto). Al aceptarlo, ambos usuarios quedan en modo `SPARRING`
durante ese mismo tiempo y cada participante recibe como experiencia el 10%
de la experiencia de su contrincante, redondeado hacia abajo a una unidad
entera.

`/box desafio` funciona de forma similar, pero inicia el modo `FIGHTING` y
otorga experiencia equivalente a `BOX_DESAFIO_EXP_PELEA` veces (10 por defecto)
la recompensa de entrenamiento de una hora. El ganador se decide al aceptar mediante una probabilidad ponderada
por la experiencia acumulada de ambos usuarios; si uno tiene el doble de
experiencia, tiene el doble de probabilidad. El ganador recibe como dinero la
suma de la experiencia acumulada de ambos contrincantes.

**La tarjeta la ve el desafiado.** La solicitud se publica como un mensaje del
canal con el botón *Aceptar desafío*, y no como respuesta de la interacción:
el comando difiere efímero (para que la base no gaste la ventana de tres
segundos) y todo lo que salga por ahí viaja atado a quien ejecutó el comando,
o sea justo el que no tiene nada que aceptar. La mención al desafiado va en el
contenido del mensaje y no solo en el embed, porque dentro de un embed no
notifica a nadie. El que desafió recibe por separado un acuse privado con el
plazo, y la fila de `box_desafios` anota la modalidad (`tipo`), el canal y el
id de la tarjeta publicada.

**`/box cancelar`** retira una solicitud pendiente: la que mandaste (se anuncia
como *cancelada*) o la que te mandaron (*rechazada*). Borra la fila y reemplaza
la tarjeta del canal por un aviso sin botón, para que nadie acepte algo que ya
no existe; si la tarjeta ya no está (la borraron a mano, el bot se reinició y
perdió la caché del canal) alcanza con la fila, porque el botón huérfano
responde "desafío no disponible" y se retira solo. Con varias solicitudes
pendientes pide el parámetro `contrincante` para saber cuál. Las vencidas no
cuentan: ya no son una solicitud.

Cuando el botón no se puede aceptar **en ese momento** —el rival ya tiene una
acción activa, está lesionado o hay otra pelea narrándose— la solicitud sigue
pendiente y la tarjeta conserva su botón: el motivo se le responde en privado
al que intentó aceptar y vuelve a intentarlo cuando pueda. Solo los estados
definitivos (expirado, inexistente) retiran la tarjeta. El timeout de la view,
que vive en memoria hasta una hora después, consulta la base antes de escribir
"expirado" para no pisar una tarjeta que ya se canceló o ya se aceptó.

### Narración en vivo del combate

Al aceptar un desafío, el combate se resuelve completo y queda guardado como un
plan en `box_combates`; el bot no simula nada durante la pelea, solamente revela
ese plan. Cada **asalto es un mensaje del canal** y cada latido de
`BOX_COMBATE_TICK_SEGUNDOS` (15 segundos por defecto) agrega una línea a ese
mensaje, que al cerrar el asalto queda con su veredicto. Como todo se recalcula
desde la semilla del plan, un reinicio del bot no cambia lo ya publicado: el
asalto se vuelve a renderizar y la pelea sigue siendo la misma.

El primer mensaje lleva arriba la **cabecera de la velada** (`Pelea pactada a N
asaltos`, el motivo del favoritismo y `favorito al 62 %`) y la conserva durante
todo el asalto y también cuando cierra: editar un mensaje de Discord es
reemplazarlo entero, así que la cabecera se vuelve a armar en cada latido en vez
de concatenarse una sola vez al publicar. Los asaltos siguientes no la repiten
(el anuncio es uno solo), y si un asalto se estirara por encima del límite de la
descripción el recorte suelta líneas de relato, nunca la cabecera.

La cantidad de asaltos depende de la diferencia de experiencia comprimida
(`log1p` sobre `BOX_COMBATE_SUELO_EXP`, acotada entre `BOX_COMBATE_PROB_PISO` y
`BOX_COMBATE_PROB_TOPE`): una pelea pareja va a `BOX_COMBATE_ROUNDS_MAXIMO`
asaltos y una muy desigual se acorta hasta `BOX_COMBATE_ROUNDS_MINIMO`. La
probabilidad se sortea **una sola vez, a nivel combate**; los asaltos se reparten
de forma coherente con ese sorteo. Si el resultado emergiera de contar
intercambios, once asaltos con un 60 % por intercambio serían un 88 % de
victorias y acortar la pelea la convertiría en una moneda al aire.

El sorteo del **premio** sigue pesando la experiencia cruda de los dos
perfiles, como siempre: la probabilidad comprimida que muestra el relato
(`favorito al 62 %`) describe cómo se cuenta la pelea, no cuánto se paga. Así
una cuenta nueva con equipo Legendario puede darle pelea a un veterano en el
canal, pero no le copia el bote.

La narración se corta cuando el plan se agota (o antes, si el corner para la
pelea: `BOX_COMBATE_KO_BASE` y `BOX_COMBATE_KO_POR_BRECHA`), pero la acción
sigue bloqueada `BOX_DESAFIO_DURACION_HORAS`: la recompensa y el bloqueo no
dependen del relato, así una victoria rápida no se puede usar para entrenar de
más. El sparring usa el mismo motor con otras reglas: sin nocaut, sin ganador
declarado y sin escribir en el historial de desafíos.

Con los valores por defecto un asalto dura `(BOX_COMBATE_DIALOGOS_POR_ROUND + 1)
× BOX_COMBATE_TICK_SEGUNDOS` = 2 minutos y la velada completa va de 6 a 18
minutos (`BOX_COMBATE_ROUNDS_MINIMO` a `BOX_COMBATE_ROUNDS_MAXIMO` asaltos).

**Un solo combate a la vez.** Mientras hay una pelea narrándose, el siguiente
desafío se rechaza con un "hay una pelea en curso" y el desafío queda pendiente
para cuando la velada termine: el canal de Box es uno y dos relojes de relato
pisándose no son una velada, son ruido. `BOX_COMBATE_UNICO_GLOBAL=0` cambia el
candado de "por bot" a "por servidor". Si un canal se borra a mitad de una
pelea, el narrador cierra la fila pasada la ventana de narración
(`GRACIA_SIN_CANAL`, 5 minutos) y `/admin box cerrar_combate` hace lo mismo a
mano cuando haga falta.

**El equipamiento participa.** `box_equipo` guardaba los niveles de casco,
guantes, bucal, short y botas como una etiqueta de la tienda: ningún desafío los
leía. Ahora cada nivel suma `BOX_COMBATE_EQUIPO_POR_NIVEL` a la estadística que
le corresponde (guantes→daño, casco→defensa, bucal→vida, short→defensa,
botas→menos fatiga acumulada) y el conjunto pesa
`BOX_COMBATE_EQUIPO_FUERZA` por nivel en la probabilidad de victoria. El bono
está acotado a `NIVEL_MAXIMO_EQUIPAMIENTO` por pieza y se aplica antes de la
escala logarítmica de la experiencia: entre rivales parejos el equipo inclina
unos puntos y define si la pelea es un nocaut o una tarjeta, contra diez veces
de experiencia no la da vuelta. `BOX_COMBATE_EQUIPO_ACTIVO=0` vuelve al
comportamiento anterior.

El cántico del público nombra a un miembro real, así que no se decide con una
variable global: cada servidor lo consiente con `/admin box canticos activar` y
mientras nadie decida rige `BOX_COMBATE_CANTICOS` (apagado por defecto). Para
apagar toda la narración se usa `BOX_COMBATE_ACTIVO=0`; los desafíos y sus
recompensas siguen funcionando igual.

La tienda incluye estas mejoras, con un máximo de `BOX_MEJORA_NIVEL_MAXIMO`
nivel (10 por defecto). El primer nivel cuesta `BOX_PRECIO_MEJORA_ENTRENAMIENTO`
y `BOX_PRECIO_MEJORA_TRABAJO` (1000 por defecto) y cada compra posterior
aumenta el precio un `BOX_PRECIO_MEJORA_CRECIMIENTO` compuesto (+25% por
defecto), redondeando hacia arriba:

- `Creatina`: suma `BOX_MEJORA_ENTRENAMIENTO_EXP_POR_NIVEL` EXP por minuto de
  entrenamiento (5 por defecto).
- `Cafe`: suma `BOX_MEJORA_TRABAJO_DINERO_POR_NIVEL` de dinero por minuto de
  trabajo (50 por defecto).

Cada hora de una acción aumenta la probabilidad de lesión en
`BOX_LESION_PROBABILIDAD_POR_HORA` puntos (1% por defecto), con un techo de
`BOX_LESION_PROBABILIDAD_MAXIMA` (100% por defecto). Al finalizar, se realiza
un sorteo con esa probabilidad. Si el usuario se lesiona, queda en estado
`LESIONADO` durante `BOX_LESION_HORAS` horas (3 por defecto) y no puede iniciar
acciones ni desafíos. Mientras esté sin ninguna acción en curso (esté o no
lesionado), su probabilidad baja
`BOX_LESION_DECAIMIENTO_POR_HORA` puntos porcentuales por hora (0.01 por
defecto): el bot reduce ese monto una vez por hora para los usuarios inactivos,
sin pasar de 0%. `/box descanso` reinicia la probabilidad a 0%, pero no cura
una lesión activa. El `Tratamiento Fisioterapeutico` cuesta
`BOX_PRECIO_TRATAMIENTO_FISIOTERAPEUTICO` (10000 por defecto), quita la lesión
y conserva la probabilidad acumulada. El `Tratamiento 5 estrellas` cuesta
`BOX_PRECIO_TRATAMIENTO_CINCO_ESTRELLAS` (50000 por defecto), quita la lesión
y reinicia también la probabilidad a 0%.

Además, `BOX_PRECIO_MULTIPLICADOR` multiplica el precio de todos los artículos
de la tienda (mejoras, tratamientos, suministros y equipamiento; 1.0 por
defecto), y el precio de cada pieza de equipamiento se multiplica por
`BOX_PRECIO_EQUIPAMIENTO_CRECIMIENTO` en cada calidad (se duplica por
defecto).

### Suministros de recuperación

La tienda tiene el artículo `🎒 Suministros de recuperación`. Su botón abre un
menú efímero para elegir el tipo; también puede usarse con
`/box suministro <tipo>`. Cada suministro restaura al máximo una estadística y
solo cobra si la estadística no estaba ya llena:

| Tipo | Suministro | Precio | Efecto |
| --- | --- | --- | --- |
| `vida` | 🥤 Bebida isotónica | 1500 | Restaura la vida al máximo (`vida_maxima`). |
| `cansancio` | ⚡ Bebida energética | 1500 | Restaura la energía al máximo (`cansancio_maximo`). |
| `defensa` | 🔧 Servicio de reparación | 3000 | Repara la defensa hasta el máximo (`defensa_maxima`). |
| `lesion` | 🩹 Botiquín completo | 60000 | Cura la lesión activa y deja la probabilidad en 0%. |

El botón de suministros es de un solo uso: tras elegir el tipo, el menú queda
deshabilitado.

Para comprar una mejora se utiliza la opción correspondiente:

```text
/box comprar mejora: Creatina
/box comprar mejora: Cafe
```

### Comprar con los botones de la tienda

`/box tienda` muestra el catálogo y, debajo, un botón por artículo con el emoji
que lo representa. Tocar el botón compra ese artículo.

Cada botón guarda en su `custom_id` a qué usuario pertenece la tienda
(`box_comprar:<owner>:<categoría>:<artículo>`), así que solo funciona para quien
abrió esa tienda; si otro usuario lo toca, se le avisa que use `/box tienda`
para abrir la suya. Esto evita que compre a un precio distinto del que muestra
el mensaje, ya que los precios dependen del nivel de quien la abrió.

La confirmación de la compra es efímera: solo la ve quien compró y no ensucia
el canal.

Los botones se registran por patrón en `setup()`, de modo que siguen
funcionando en mensajes de tienda anteriores a un reinicio del bot.

`/box comprar`, `/box tratamiento` y `/box suministro` siguen disponibles para
quienes prefieran escribir el comando. `/box comprar tipo=suministro` orienta
al `/box suministro`, porque el artículo genérico necesita elegir el tipo.

El precio del siguiente nivel se calcula como
`ceil(precio_base x BOX_PRECIO_MEJORA_CRECIMIENTO^nivel_actual)`, con el
precio base ya multiplicado por `BOX_PRECIO_MULTIPLICADOR`. Con los valores
por defecto: nivel 0 cuesta 1000, nivel 1 cuesta 1250 y nivel 2 cuesta 1563.

`/box topdesafios` muestra cada participante como `ganadas/perdidas` y calcula
el ratio de victorias divididas por derrotas. Un usuario sin derrotas aparece
con ratio `∞`.



## Ejecución desde archivo

`/admin fileexecute` recibe un archivo `.txt` y ejecuta cada línea como un comando
administrativo independiente. El archivo puede contener hasta 50 comandos y medir
hasta 1 MiB.

Cada línea usa la misma estructura que los comandos: `grupo comando argumentos`.
Los grupos son `madrugue`, `ssf` y `box`:

```text
madrugue manualadd <ID_USUARIO> YYYY-MM-DD HH:MM
madrugue resetdia <@ID_USUARIO> YYYY-MM-DD
madrugue resetusuario <ID_USUARIO>
madrugue resettotal SI
madrugue ver <ID_USUARIO>
ssf estado <ID_USUARIO>
ssf revivir <ID_USUARIO> YYYY-MM-DD
ssf iniciar <ID_CANAL>
ssf agregar <ID_USUARIO> YYYY-MM-DD
ssf quitar <ID_USUARIO> YYYY-MM-DD
ssf eliminar <ID_USUARIO> YYYY-MM-DD
ssf recalcular <ID_USUARIO>
ssf cerrar SI
box top
box stats
box historial <ID_USUARIO>
box procesar
info
```

Por compatibilidad, los comandos de Madrugue también pueden escribirse sin el
subgrupo (la forma histórica):

```text
manualadd <ID_USUARIO> YYYY-MM-DD HH:MM
resetdia <@ID_USUARIO> YYYY-MM-DD
resetusuario <ID_USUARIO>
resettotal SI
stats
top
```

También se puede escribir `/admin` al comienzo de cada línea:

```text
/admin madrugue manualadd <ID_USUARIO> YYYY-MM-DD HH:MM
/admin ssf revivir <@ID_USUARIO> YYYY-MM-DD
```

Las líneas vacías y las que comienzan con `#` se ignoran. Solo se ejecutan comandos
del grupo `/admin`; no se permite ejecutar código Python ni comandos externos.
