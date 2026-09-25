"""Módulo laHora (canal 420) de NaikitoBot.

Premia a quienes escriben "420" en el canal configurado justo a las
04:20 o a las 16:20. Las ventanas, su duración y los puntos se
configuran desde ``.env`` con variables ``LAHORA_*``.

Submódulos:
* :mod:`models` — Modelo SQLAlchemy (tabla ``lahora_registros``).
* :mod:`database` — Consultas asíncronas.
* :mod:`logic` — Detección del mensaje, ventanas, puntos y rachas.
* :mod:`services` — Operaciones de alto nivel para los comandos.
"""
