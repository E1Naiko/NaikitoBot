from config import ADMIN_USER_IDS


def es_admin(user_id: int) -> bool:
    """Comprueba si un usuario tiene permisos administrativos."""
    return user_id in ADMIN_USER_IDS