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


def listado(materias, incluir, vacio='No hay materias.', mostrar_anio=False, estados=None):
    lineas = []
    for codigo, materia in materias.items():
        if incluir(codigo, materia):
            nota = ' (elegir una asignatura del grupo)' if materia.get('elegir_una') else ''
            if mostrar_anio:
                anio = materia.get('anio')
                nota += f" ({anio}° año)" if anio is not None else " (optativa, sin año fijo)"
            if estados and estados.get(codigo) == 'cursando':
                nota += ' (cursando)'
            if materia.get("nota"):
                nota += f" ({materia['nota']})"
            lineas.append(f"{codigo} · {materia['nombre']}{nota}")
    return '\n'.join(lineas) or vacio


def listado_por_semestre(materias, incluir, semestre=None, vacio="No hay materias.", mostrar_anio=False, estados=None):
    """Agrupa por semestre sin inventar fechas para actividades sin dato."""
    secciones = []
    grupos = ((1, '1er Semestre'), (2, '2do Semestre'), (None, 'Ingreso o sin semestre indicado'))
    for numero, titulo in grupos:
        if semestre is not None and numero != semestre:
            continue
        lineas = listado(materias, lambda k, m: incluir(k, m) and m.get('semestre') == numero,
                         vacio='', mostrar_anio=mostrar_anio, estados=estados)
        if lineas:
            secciones.append(f'**{titulo}**\n{lineas}')
    return '\n\n'.join(secciones) or vacio


def progreso(materias, aprobadas, cursando=()):
    """Cuenta requisitos aprobados o en curso, con cupos para grupos de elección."""
    contabilizadas = set(aprobadas) | set(cursando)
    hechas = total = 0
    grupos = {}
    for codigo, materia in materias.items():
        if materia.get('ingreso'):
            continue
        grupo = materia.get('grupo_progreso', 'elegir_una' if materia.get('elegir_una') else None)
        if grupo is None:
            total += 1
            hechas += codigo in contabilizadas
        else:
            cupo, cantidad = grupos.get(grupo, (materia.get('cupo_progreso', 1), 0))
            grupos[grupo] = cupo, cantidad + (codigo in contabilizadas)
    return hechas + sum(min(cupo, cantidad) for cupo, cantidad in grupos.values()), total + sum(
        cupo for cupo, _ in grupos.values()
    )
