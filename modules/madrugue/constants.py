"""Horarios y bonus estáticos de Madrugue.

Nada de este módulo depende de la base de datos ni de discord.py: son datos
planos que comparten los comandos y la lógica.
"""

from datetime import time


# 05:30 - 06:59 = 100 puntos
# 07:00 - 08:59 = 25 puntos
# 09:00 - 09:59 = 5 puntos
# 10:00 en adelante = fuera de horario

PUNTOS_100_DESDE = time(5, 30)
PUNTOS_25_DESDE = time(7, 0)
PUNTOS_5_DESDE = time(9, 0)

FIN_MADRUGADA = time(10, 0)


# El bonus disminuye linealmente a medida que avanza
# la madrugada.
#
# 05:30 = +0.100 -> x1.100
# 10:00 = +0.001 -> x1.001
#
# La racha no modifica el multiplicador.

BONUS_MAXIMO = 0.100
BONUS_MINIMO = 0.001
