"""Núcleo de NaikitoBot.

Contiene los componentes compartidos por todo el bot:
* :mod:`core.bot` — Clase principal del bot y árbol de comandos con restricciones de canal.
* :mod:`core.database` — Motor SQLAlchemy asíncrono, modelos base y utilidades de sesión.
* :mod:`core.mensajes` — Utilidades para crear respuestas en embed con formato uniforme.
* :mod:`core.permissions` — Comprobación de permisos de administrador.
* :mod:`core.utils` — Funciones auxiliares generales como la fecha/hora actual.
"""
