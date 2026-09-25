"""Módulo del sistema de boxeo de NaikitoBot.

Es el sistema más grande del bot: cada usuario tiene un boxeador que entrena,
descansa, sube de nivel, compra equipamiento, se enfrenta a otros jugadores en
combates y consigue patrocinadores.

Submódulos:

* :mod:`models` — Definiciones SQLAlchemy de las tablas.
* :mod:`database` — Funciones para inicializar la base de datos.
* :mod:`constants` — Constantes de equilibrio del juego importadas de la configuración.
* :mod:`logic` — Cálculos estadísticos, progresión y economía.
* :mod:`fighting` — Motor de combate entre boxeadores.
* :mod:`combate` — Gestión de combates activos en canales.
* :mod:`narracion` — Generación de mensajes narrativos para los combates.
* :mod:`sparring` — Lógica de sparrings contra oponentes controlados por el bot.
* :mod:`services` — Operaciones de alto nivel usadas por los comandos.
"""
