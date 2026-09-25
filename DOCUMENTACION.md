# Documentación de NaikitoBot

Bot de Discord personalizado para servidores comunitarios hispanohablantes, con múltiples sistemas: boxeo (economía, combates, entrenamiento), recompensas por madrugar y el evento Septiembre Sin FP.

---

## 📋 Tabla de contenidos
1.  [Estructura del proyecto](#estructura-del-proyecto)
2.  [Arquitectura](#arquitectura)
3.  [Primeros pasos](#primeros-pasos)
4.  [Sistemas implementados](#sistemas-implementados)
5.  [Base de datos](#base-de-datos)
6.  [Restricciones por canal](#restricciones-por-canal)
7.  [Extender el bot](#extender-el-bot)

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
├── modules/             # Lógica de negocio de cada sistema
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
│  PostgreSQL (prod) / SQLite (desarrollo)│
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
    - `DATABASE_URL`: URL de conexión a la base de datos (usa SQLite por defecto para desarrollo)
    - IDs de canales y usuarios administradores

3.  **Ejecutar el bot**
    ```bash
    python main.py
    ```

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

### 3. 📅 Sistema SeptSinFP (Septiembre Sin FP)
Evento anual de septiembre donde los usuarios registran días consecutivos sin consumir contenido para adultos, acumulan puntos y siguen su racha.

### 4. ⚙️ Comandos administrativos
Comandos protegidos por ID de usuario para diagnóstico, mantenimiento, gestión de usuarios y configuración.

---

## 💾 Base de datos

El bot usa **SQLAlchemy asíncrono** como ORM:
- **Producción**: PostgreSQL con driver `asyncpg`
- **Desarrollo/Pruebas**: SQLite con `aiosqlite` (sin necesidad de servidor)

### Características importantes:
- Soporte de fechas con zona horaria que funciona correctamente en SQLite (tipo personalizado `TZDateTime`)
- Sesiones asíncronas por operación
- Creación automática de tablas al iniciar el bot
- Función `vaciar_db()` para reiniciar la base en pruebas

Los modelos se definen en cada submódulo de `modules/*/models.py` y heredan de `core.database.Base`.

---

## 🔒 Restricciones por canal

El bot usa una clase personalizada `RestrictedCommandTree` que **bloquea automáticamente comandos en canales no permitidos**:
- Los comandos `/box` solo funcionan en canales de Box configurados
- Los comandos `/madrugue` solo funcionan en canales de Madrugue
- Los comandos `/ssf` solo funcionan en canales de SeptSinFP
- En canales generales solo funciona `/ping`
- Los administradores pueden usar cualquier comando en cualquier canal

Cuando un usuario intenta usar un comando en un canal equivocado, recibe un mensaje efímero explicando qué comandos están permitidos ahí.

---

## 🎨 Formato de mensajes

Todas las respuestas del bot usan embeds con un formato uniforme gestionado por `core.mensajes`:
- Colores diferenciados por sistema (rojo para Box, dorado para Madrugue, verde azulado para SSF)
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

Las pruebas usan una base de datos SQLite en memoria que se vacía entre cada test.

---

## ✨ Extender el bot

### Añadir un nuevo comando a un sistema existente
1.  Añade el método decorado con `@app_commands.command()` en el Cog correspondiente dentro de `commands/`
2.  Si necesitas nueva lógica de negocio, añádela en `modules/<sistema>/logic.py` o `services.py`
3.  Si necesitas nuevas tablas, añade el modelo en `modules/<sistema>/models.py` y asegúrate de importarlo en `core/database.py` en la función `registrar_modelos()`

### Añadir un nuevo sistema completo
1.  Crea una carpeta `modules/<nombresistema>/` con:
    - `models.py` para tus modelos SQLAlchemy
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
