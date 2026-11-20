"""Comandos de correlativas independientes del transporte de chat."""
import json
import re
from pathlib import Path

from core.sqlite import conectar_sync
from modules.correlativas.logic import habilitada, listado


class Bot:
    def __init__(self, db, admins=()):
        self.admins = {str(a).strip() for a in admins if str(a).strip()}
        self.db = db
        self.base = {p.stem: json.loads(p.read_text(encoding='utf8'))
                       for p in Path(__file__).with_name('planes').glob('*.json')}

    def catalogo(self):
        planes = {plan: materias.copy() for plan, materias in self.base.items()}
        for plan, in self.db.execute('SELECT plan FROM correlativas_planes'):
            planes.setdefault(plan, {})
        for plan, codigo, nombre, anio, previas in self.db.execute(
                'SELECT plan, codigo, nombre, anio, previas FROM correlativas_materias'):
            planes[plan][codigo] = dict(nombre=nombre, anio=anio, previas=json.loads(previas))
        return planes

    def administrar(self, texto, planes):
        uso = ('admin agregar plan <plan> | admin agregar materia <plan> <código> '
               '<año> <nombre> [| previa1,previa2]')
        partes = texto.split(maxsplit=3)
        if len(partes) != 4 or partes[1].casefold() != 'agregar':
            return uso
        tipo, argumentos = partes[2].casefold(), partes[3]
        if tipo == 'plan':
            plan = argumentos.casefold()
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', plan):
                return 'Usá un identificador con letras, números y guiones, sin espacios.'
            if plan in planes:
                return 'El plan ya existe.'
            alta = self.db.execute('INSERT OR IGNORE INTO correlativas_planes VALUES (?)', (plan,))
            self.db.commit()
            return 'Plan agregado: ' + plan if alta.rowcount else 'El plan ya existe.'
        if tipo != 'materia':
            return uso
        datos = argumentos.split(maxsplit=3)
        if len(datos) != 4:
            return uso
        plan, codigo, anio, detalle = datos
        plan, codigo = plan.casefold(), codigo.upper()
        if plan not in planes:
            return 'El plan no existe.'
        if not re.fullmatch(r'[A-Z0-9]+(?:-[A-Z0-9]+)*', codigo) or not re.fullmatch(r'[1-9][0-9]?', anio):
            return 'Código inválido o año fuera del rango 1–99.'
        existentes = {k.casefold(): k for k in planes[plan]}
        if codigo.casefold() in existentes:
            return 'El código ya existe en el plan.'
        nombre, separador, lista = detalle.partition('|')
        nombre = nombre.strip()
        if not nombre:
            return uso
        requisitos = []
        if separador:
            for previa in lista.split(','):
                clave = previa.strip().casefold()
                if clave not in existentes:
                    return 'Cada previa debe ser una materia existente del mismo plan.'
                requisitos.append({'codigo': existentes[clave]})
        alta = self.db.execute('INSERT OR IGNORE INTO correlativas_materias VALUES (?, ?, ?, ?, ?)',
                               (plan, codigo, nombre, int(anio), json.dumps([requisitos] if requisitos else [])))
        self.db.commit()
        return 'Materia agregada: ' + nombre if alta.rowcount else 'El código ya existe en el plan.'

    def responder(self, usuario, mensaje):
        palabras = mensaje.strip().lstrip('/').casefold().split()
        catalogo = self.catalogo()
        if palabras[:1] == ['admin']:
            if str(usuario) not in self.admins:
                return 'Comando reservado a administradores.'
            return self.administrar(mensaje.strip().lstrip('/'), catalogo)
        planes = 'Planes: ' + ', '.join(sorted(catalogo))
        if palabras == ["planes"]:
            return planes
        if palabras[:1] == ['unirse'] and len(palabras) == 2:
            plan = palabras[1]
            if plan not in catalogo:
                return planes
            self.db.execute('INSERT OR REPLACE INTO correlativas_usuarios VALUES (?, ?)', (usuario, plan))
            self.db.commit()
            return 'Plan activo: ' + plan
        if palabras[:2] in (['mostrar', 'anio'], ['mostrar', 'año']) and len(palabras) == 4:
            plan, anio = palabras[2:]
            if plan not in catalogo:
                return planes
            if not re.fullmatch('[1-9][0-9]*', anio):
                return 'Ingresá un año positivo.'
            return listado(catalogo[plan], lambda k, m: str(m['anio']) == anio)
        aprobar = palabras[:2] == ['aprobar', 'materia'] and len(palabras) >= 3
        if not aprobar and palabras != ['materias', 'quiensigue']:
            return ('unirse <plan> | aprobar materia <código o nombre> | mostrar anio <plan> <número> '
                    '| materias quiensigue\n' + planes)
        fila = self.db.execute('SELECT plan FROM correlativas_usuarios WHERE usuario=?', (usuario,)).fetchone()
        if not fila:
            return 'Primero usá /correlativas unirse. ' + planes
        plan, = fila
        materias = catalogo[plan]
        if aprobar:
            consulta = ' '.join(palabras[2:])
            opciones = [k for k, m in materias.items() if consulta in (k.casefold(), ' '.join(m['nombre'].casefold().split()))]
            if len(opciones) != 1:
                return 'No se identificó una materia única. Usá el código del plan.'
            codigo, = opciones
            alta = self.db.execute('INSERT OR IGNORE INTO correlativas_aprobadas VALUES (?, ?, ?)',
                                   (usuario, plan, codigo)).rowcount
            nombre = materias[codigo]['nombre']
            if not alta:
                self.db.commit()
                return 'Ya estaba aprobada: ' + nombre
            hechas = self._aprobadas(usuario, plan)
            self.db.commit()
            antes = hechas - {codigo}
            nuevas = listado(
                materias,
                lambda k, m: k not in hechas and habilitada(m, hechas) and not habilitada(m, antes),
                vacio='No se habilitaron materias nuevas.',
            )
            return f'Aprobada: {nombre}\n\n**Materias recién habilitadas**\n{nuevas}'
        hechas = self._aprobadas(usuario, plan)
        return listado(materias, lambda k, m: k not in hechas and habilitada(m, hechas))

    def _aprobadas(self, usuario, plan):
        return {codigo for codigo, in self.db.execute(
            'SELECT codigo FROM correlativas_aprobadas WHERE usuario=? AND plan=?', (usuario, plan)
        )}



def ejecutar(usuario, mensaje, administrador=False):
    """Ejecuta una operación de correlativas fuera del bucle de Discord."""
    with conectar_sync() as db:
        return Bot(db, admins=(usuario,) if administrador else ()).responder(str(usuario), mensaje)
