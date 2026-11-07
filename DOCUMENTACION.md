# Documentación de NaikitoBot

Bot de Discord personalizado para servidores comunitarios hispanohablantes, con múltiples sistemas: boxeo (economía, combates, entrenamiento), recompensas por madrugar, el canal 420 y el evento Septiembre Sin FP, con sanciones por trampa por minijuego.

---

## 📋 Tabla de contenidos
1.  [Estructura del proyecto](#estructura-del-proyecto)
2.  [Arquitectura](#arquitectura)
3.  [Primeros pasos](#primeros-pasos)
4.  [Sistemas implementados](#sistemas-implementados)
5.  [Base de datos](#base-de-datos)
6.  [Restricciones por canal](#restricciones-por-canal)
7.  [Versión del bot](#versión-del-bot)
8.  [Extender el bot](#extender-el-bot)

---

## 📂 Estructura del proyecto

```
NaikitoBot/
├── main.py              # Punto de entrada del bot
├── requirements.txt     # Dependencias de producción
├── requirements-dev.txt # Dependencias de desarrollo y pruebas
├── pytest.ini           # Configuración de pytest
├── .env.example         # Plantilla de variables de entorno
├── core/                # Código central compartido
├── config/              # Carga y validación de configuración
├── commands/            # Cogs/comandos slash de Discord
├── modules/             # Lógica de negocio de cada sistema (incluye sanciones/)
├── migrations/          # Migraciones de base de datos
├── scripts/             # Scripts auxiliares
└── tests/               # Pruebas automatizadas
```

---

## 🏗️ Arquitectura

El bot sigue una arquitectura en capas clara:

```
┌─────────────────────────────────────────┐
│            Discord API (discord.py)     │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│              commands/                  │
│  (Cogs de comandos slash, interacciones)│
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│              modules/                   │
│  (Lógica de negocio de cada sistema)    │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│              core/                      │
│  (Base de datos, mensajes, permisos)    │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────▼─────────────────────┐
│              Base de datos              │
│  SQLite (archivo persistente)          │
└─────────────────────────────────────────┘
```

---

## 🚀 Primeros pasos

1.  **Instalar dependencias**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configurar variables de entorno**
    Copia `.env.example` a `.env` y completa:
    - `DISCORD_TOKEN`: Token de tu bot de Discord
    - `GUILD_ID`: ID del servidor donde se sincronizarán los comandos (opcional para desarrollo)
    - `DATABASE`: ruta del archivo SQLite (por defecto `naikito-v2.db`; las relativas se resuelven contra la raíz del proyecto)
    - IDs de canales y usuarios administradores

3.  **Ejecutar el bot**
    ```bash
    python main.py
    ```
    Al conectarse, la consola muestra la versión, la carga de los sistemas,
    sus tareas principales, la sincronización de comandos y los servidores.
    Para un diagnóstico operativo más completo usá `/admin test`.

---

## 🧩 Sistemas implementados

### 1. 🥊 Sistema Box
El sistema más completo: cada usuario puede crear un boxeador, entrenar para ganar experiencia y dinero, descansar, comprar equipamiento, combatir contra otros usuarios o sparrings controlados por el bot, y conseguir patrocinadores.

**Características clave:**
- Estadísticas de boxeador: vida, defensa, daño, cansancio, nivel, dinero
- Sistema de lesiones y médico para curarse
- Tienda con equipamiento y suministros
- Mejoras de entrenamiento, trabajo y crecimiento
- Combates narrativos con varios asaltos y posibilidad de KO
- Sistema de desafíos y promociones

### 2. 🌙 Sistema Madrugue
Recompensa a los usuarios que están conectados durante la madrugada (horas configurables en `.env`) con puntos que pueden canjear por recompensas.

### 3. 🌿 Sistema laHora (canal 420)
Registra automáticamente a quienes escriben "420" en el canal 420 justo a las 04:20 o a las 16:20 (ventanas configurables en `.env`), con puntos por velocidad, bonus al primero, rachas y ranking (`/420_top`, `/420_stats`, `/420_hoy`, `/420_ayuda`). Código en `commands/lahora/` y `modules/lahora/`.

Como el registro depende de que el bot esté conectado para ver el mensaje en
vivo, cada vez que se reconecta (`on_ready`) repasa sin bloquear el arranque
el historial de cada canal 420 configurado, en todos los servidores donde
está, y carga los "420" que se hayan perdido mientras estuvo offline. Guarda
un checkpoint por canal (`core/lahora_sync.py`, tabla
`lahora_sincronizacion`) para no reescanear todo el historial en cada
reconexión. Un administrador puede disparar la misma recuperación a mano con
`/admin 420 sincronizar`, sin esperar a un reinicio.

En la terminal, el registro en vivo imprime una línea por cada 420 que suma
(usuario, hora, ventana, segundos, posición y puntos), otra para el podio de la
ventana y, al terminar cada ventana, un resumen con el top 3 y la cantidad de
participantes (`commands/lahora/tareas.py`). Lo que no suma —fuera de
horario, repetido o de un usuario sancionado— no se imprime, salvo el caso de
la sanción, que deja una línea clara. Cuando la ventana se cierra, el resumen
tarda a lo sumo un minuto y se emite una sola vez.

### 4. 📅 Sistema SeptSinFP (Septiembre Sin FP)
Evento anual de septiembre donde los usuarios registran días consecutivos sin consumir contenido para adultos, acumulan puntos y siguen su racha.

### 5. ⚙️ Comandos administrativos
Comandos protegidos por ID de usuario para diagnóstico, mantenimiento, gestión de usuarios y configuración.

### 6. ⛔ Sanciones por trampa
Los administradores pueden bloquear a un usuario en un minijuego concreto
(`/admin sanciones aplicar`) indicando motivo y temporizador (`30m`, `12h`,
`7d`, `2d12h` o `permanente`, que es el valor por defecto). Cada sanción vive
en la tabla `sanciones`, tiene su propio vencimiento y se puede levantar con
`/admin sanciones levantar`; `/admin sanciones ver` muestra el tiempo restante
y `/admin sanciones limpiar` borra las vencidas.

El bloqueo se aplica en el punto donde cada minijuego entrega premios, no
solo en la presentación: `/madrugue`, `/ssf registrar`, `/ssf sobrevivi`, los
420 del canal (incluida la importación del historial), las acciones y desafíos
de Box y las compras de la tienda. Consultar el ranking o el propio saldo
sigue funcionando, y el saldo de Box muestra la sanción activa con su
temporizador. Código en `commands/admin/sanciones.py` y `modules/sanciones/`.

---

## 💾 Base de datos

El bot usa **SQLite** sin ORM ni servidor externo. La ruta se configura con
`DATABASE` (por defecto `naikito-v2.db`, resuelta contra la raíz del proyecto si
es relativa). El esquema está en `core/esquema.sql`
y `core/database.py` crea las tablas faltantes al iniciar.

Para desplegarlo en un servidor Ubuntu, con servicio systemd y respaldos
automáticos, ver [`DESPLIEGUE.md`](DESPLIEGUE.md). El respaldo en caliente se
hace con `python -m scripts.respaldar_db`.

- `core/sqlite.py` abre conexiones cortas con tiempo de espera de 30 segundos.
- Madrugue, 420 y SeptSinFP usan `aiosqlite`; Box ejecuta consultas SQLite
  bloqueantes en hilos para no bloquear el event loop de Discord.
- Las fechas se almacenan como texto ISO; las de hora incluyen zona horaria.
- `vaciar_db()` se usa únicamente para las pruebas.
- La primera sincronización 420 empieza desde el primer chequeo, salvo que se
  configure `LAHORA_IMPORTAR_HISTORIAL_INICIAL=1`. Tanto esa opción como la
  importación manual se limitan a la temporada actual.
- Las sanciones por trampa (`sanciones`) no se borran en el corte anual.
- Cada 3 de octubre a las 00:00 en `TIMEZONE` comienza una nueva temporada:
  se eliminan los datos anteriores de todos los sistemas y se conserva la
  configuración de cada servidor. La transición SQLite es transaccional y se
  ejecuta también cuando el bot arranca después de esa fecha.
- Al activar por primera vez el corte en una base existente se eliminan todos
  los datos de Box, porque su progreso no tiene fecha de origen; los registros
  de Madrugue y 420 de la temporada actual y los desafíos SSF iniciados en ella
  se conservan. No se crean archivos históricos automáticos.

Para empezar de cero, seleccioná un archivo que no exista y no ejecutes las
herramientas de importación o fusión de respaldos. Detené el bot para copiar
el archivo y asegurate de usar almacenamiento persistente.

---

## 🔒 Restricciones por canal

El bot usa una clase personalizada `RestrictedCommandTree` que **bloquea automáticamente comandos en canales no permitidos**:
- Los comandos `/box` solo funcionan en canales de Box configurados
- Los comandos `/madrugue` solo funcionan en canales de Madrugue
- Los comandos `/420_*` solo funcionan en canales 420 (`LAHORA_CANALES_ID`)
- Los comandos `/ssf` solo funcionan en canales de SeptSinFP
- En canales generales solo funciona `/ping`
- Los administradores pueden usar cualquier comando en cualquier canal

Cuando un usuario intenta usar un comando en un canal equivocado, recibe un mensaje efímero explicando qué comandos están permitidos ahí.

---

## 🎨 Formato de mensajes

Todas las respuestas del bot usan embeds con un formato uniforme gestionado por `core.mensajes`:
- Colores diferenciados por sistema (rojo para Box, dorado para Madrugue, verde oscuro para 420, verde azulado para SSF)
- Colores estándar para respuestas ok/error/aviso
- Funciones helper `responder()`, `responder_ok()`, `responder_error()` para simplificar el código
- Soporte para mensajes efímeros y vistas con botones

---

## 🧪 Pruebas

El proyecto incluye pruebas automatizadas con `pytest`. Para ejecutarlas:
```bash
pip install -r requirements-dev.txt
pytest
```

Las pruebas usan un archivo SQLite temporal que se vacía entre cada test.

---

## 🔖 Versión del bot

Al conectarse a Discord, el resumen de arranque muestra la versión, el estado
local de los sistemas y los servidores conectados. El estado de carga no
sustituye las pruebas automatizadas ni una revisión de permisos. La versión
usa el formato:

```
NaikitoBot<mayor>.<función>.<revisión>.<YYYYMMDD>
```

* `<mayor>`: versión mayor del bot, fija (`2`).
* `<función>`: número de la última función/sistema implementado. Se sube a
  mano en `core/version.py` (`VERSION_FUNCION`) cada vez que se agrega un
  sistema o una función nueva importante.
* `<revisión>`: ajustes sobre esa misma función. Arranca en `0` y se sube a
  mano (`VERSION_REVISION`) con cada corrección o retoque menor que no
  agregue una función nueva; vuelve a `0` cuando sube `VERSION_FUNCION`.
* `<YYYYMMDD>`: fecha del último commit del repositorio. Se lee sola con
  `git log` (no hace falta tocarla a mano); si el deploy no tiene `.git` o
  no tiene git instalado, se usa la fecha de hoy y se avisa por consola.

Código en `core/version.py`.

---

## ✨ Extender el bot

### Añadir un nuevo comando a un sistema existente
1.  Añade el método decorado con `@app_commands.command()` en el Cog correspondiente dentro de `commands/`
2.  Si necesitas nueva lógica de negocio, añádela en `modules/<sistema>/logic.py` o `services.py`
3.  Si necesitas nuevas tablas, agregá su esquema a `core/esquema.sql` y las consultas parametrizadas al módulo correspondiente.

### Añadir un nuevo sistema completo
1.  Crea una carpeta `modules/<nombresistema>/` con:
    - `database.py` con una función `inicializar_db()`
    - `logic.py` para tu lógica de negocio
    - `services.py` para operaciones de alto nivel
2.  Crea una carpeta `commands/<nombresistema>/` con:
    - Tu Cog heredando de `commands.Cog`
    - Un `__init__.py` con la función `setup()` que registre el Cog
3.  Carga la extensión en `core/bot.py` dentro de `setup_hook()`
4.  Añade la restricción de canal correspondiente en `RestrictedCommandTree.interaction_check()`
5.  Añade el color del nuevo sistema en `core/mensajes.py` si lo necesitas
6.  Configura las variables de entorno nuevas en `config/settings.py`
