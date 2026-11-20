"""Reglas puras del catálogo académico."""

import re

def cumple(requisito, hechas):
    if 'codigo' in requisito:
        return requisito['codigo'] in hechas
    cantidad = re.fullmatch(r'Tener (\d+) actividades', requisito.get('especial', ''))
    return bool(cantidad and len(hechas) >= int(cantidad[1]))


def listado(materias, incluir):
    return '\n'.join(f"{k} · {m['nombre']}" for k, m in materias.items() if incluir(k, m)) or 'No hay materias.'
