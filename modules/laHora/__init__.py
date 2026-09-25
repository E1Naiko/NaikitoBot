"""Módulo del sistema laHora de NaikitoBot.

Recompensa a los usuarios que están activos en el servidor durante la
hora de decir la hora, entregando puntos canjeables por recompensas.
Las horas de bonus y los valores de puntos se configuran desde ``.env``.

Submódulos:
* :mod:`models` — Modelos SQLAlchemy.
* :mod:`database` — Inicialización de la base de datos.
* :mod:`logic` — Cálculo de puntos y horarios.
* :mod:`services` — Operaciones de alto nivel para los comandos.
"""
