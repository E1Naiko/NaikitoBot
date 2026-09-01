from modules.madrugue.database import (
    obtener_fechas_registradas,
)

from modules.madrugue.logic import (
    calcular_racha_actual,
    calcular_mejor_racha,
    calcular_racha_para_nuevo_registro as calcular_racha_logic,
)


def obtener_racha_actual(
    guild_id,
    user_id,
    fecha_actual,
):
    """
    Obtiene las fechas del usuario y calcula
    su racha actual.
    """

    fechas = obtener_fechas_registradas(
        guild_id,
        user_id,
    )

    return calcular_racha_actual(
        fechas,
        fecha_actual,
    )


def obtener_mejor_racha(
    guild_id,
    user_id,
):
    """
    Obtiene las fechas históricas del usuario
    y calcula su mejor racha.
    """

    fechas = obtener_fechas_registradas(
        guild_id,
        user_id,
        orden="ASC",
    )

    return calcular_mejor_racha(
        fechas,
    )


def calcular_racha_para_nuevo_registro(
    guild_id,
    user_id,
    fecha,
):
    """
    Obtiene las fechas del usuario y calcula
    la racha que tendrá el nuevo registro.
    """

    fechas = obtener_fechas_registradas(
        guild_id,
        user_id,
    )

    return calcular_racha_logic(
        fechas,
        fecha,
    )