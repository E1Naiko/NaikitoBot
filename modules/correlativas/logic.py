"""Reglas puras del catálogo académico."""

import re

def cumple(requisito, hechas):
    if 'codigo' in requisito:
        return requisito['codigo'] in hechas
    if 'minimo_de' in requisito:
        return len(hechas.intersection(requisito['codigos'])) >= requisito['minimo_de']
    cantidad = re.fullmatch(r'Tener (\d+) actividades', requisito.get('especial', ''))
    return bool(cantidad and len(hechas) >= int(cantidad[1]))


def habilitada(materia, hechas):
    """No da por cumplidas condiciones que la fuente no permite evaluar."""
    return not materia.get('requiere_consulta') and (
        not materia['previas'] or any(
            all(cumple(r, hechas) for r in opcion) for opcion in materia['previas']
        )
    )


def listado(materias, incluir, vacio='No hay materias.'):
    lineas = []
    for codigo, materia in materias.items():
        if incluir(codigo, materia):
            nota = ' (elegir una asignatura del grupo)' if materia.get('elegir_una') else ''
            if materia.get("nota"):
                nota += f" ({materia['nota']})"
            lineas.append(f"{codigo} · {materia['nombre']}{nota}")
    return '\n'.join(lineas) or vacio
