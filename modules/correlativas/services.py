"""Comandos de correlativas independientes del transporte de chat."""
import json
import re
from pathlib import Path

from core.sqlite import conectar_sync
from modules.correlativas.logic import habilitada, listado_por_semestre, progreso


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
            alta = self.db.execute(
                'INSERT OR IGNORE INTO correlativas_usuarios_planes VALUES (?, ?)', (usuario, plan)
            )
            self.db.commit()
            return ('Plan agregado: ' if alta.rowcount else 'Ese plan ya estaba agregado: ') + plan
        if palabras[:2] in (['mostrar', 'anio'], ['mostrar', 'año']) and len(palabras) in (4, 5):
            plan, anio = palabras[2:4]
            semestre = int(palabras[4]) if palabras[4:] in (["1"], ["2"]) else None
            if plan not in catalogo:
                return planes
            if not re.fullmatch('[1-9][0-9]*', anio):
                return 'Ingresá un año positivo.'
            return listado_por_semestre(catalogo[plan], lambda k, m: str(m['anio']) == anio, semestre)
        aprobar = palabras[:2] == ['aprobar', 'materia'] and len(palabras) >= 3
        cursando = palabras[:2] == ['cursando', 'materia'] and len(palabras) >= 3
        siguientes = palabras[:2] == ['materias', 'quiensigue']
        faltantes = palabras == ['faltantes']
        if not aprobar and not cursando and not siguientes and not faltantes and palabras != ['progreso']:
            return ('unirse <plan> | aprobar materia <código o nombre> | mostrar anio <plan> <número> '
                    '| materias quiensigue | faltantes\n' + planes)
        planes_usuario = self._planes_usuario(usuario)
        if not planes_usuario:
            return 'Primero usá /correlativas unirse. ' + planes
        if len(planes_usuario) > 1:
            return self._responder_varios_planes(usuario, palabras, planes_usuario, catalogo)
        plan = planes_usuario[0]
        materias = catalogo[plan]
        if cursando:
            consultas = [consulta.strip() for consulta in ' '.join(palabras[2:]).split(',')]
            if not consultas or any(not consulta for consulta in consultas):
                return 'Ingresá códigos o nombres separados por comas.'
            codigos = []
            for consulta in consultas:
                normalizada = ' '.join(consulta.casefold().split())
                opciones = [k for k, m in materias.items()
                            if normalizada in (k.casefold(), ' '.join(m['nombre'].casefold().split()))]
                if len(opciones) != 1:
                    return f'No se identificó una materia única: {consulta}. Usá el código del plan.'
                if opciones[0] not in codigos:
                    codigos.append(opciones[0])
            estados = self._estados(usuario, plan)
            cambios = [codigo for codigo in codigos
                       if estados.get(codigo) not in ('aprobada', 'cursando')]
            for codigo in cambios:
                self._guardar_estado(usuario, plan, codigo, 'cursando')
            self.db.commit()
            if cambios:
                nombres = ', '.join(materias[codigo]['nombre'] for codigo in cambios)
                return 'Marcadas como cursando: ' + nombres
            return 'Las materias indicadas ya estaban aprobadas o cursándose.'
        if aprobar:
            consultas = [consulta.strip() for consulta in ' '.join(palabras[2:]).split(',')]
            if not consultas or any(not consulta for consulta in consultas):
                return 'Ingresá códigos o nombres separados por comas.'
            codigos = []
            for consulta in consultas:
                normalizada = ' '.join(consulta.casefold().split())
                opciones = [k for k, m in materias.items()
                            if normalizada in (k.casefold(), ' '.join(m['nombre'].casefold().split()))]
                if len(opciones) != 1:
                    return f'No se identificó una materia única: {consulta}. Usá el código del plan.'
                if opciones[0] not in codigos:
                    codigos.append(opciones[0])
            antes = self._aprobadas(usuario, plan)
            cursando_antes = self._cursando(usuario, plan)
            nuevas_aprobadas = [codigo for codigo in codigos if codigo not in antes]
            for codigo in nuevas_aprobadas:
                self._guardar_estado(usuario, plan, codigo, 'aprobada')
            hechas = self._aprobadas(usuario, plan)
            self.db.commit()
            if not nuevas_aprobadas:
                nombres = ', '.join(materias[codigo]['nombre'] for codigo in codigos)
                return 'Ya estaba aprobada: ' + nombres
            if len(codigos) == 1:
                encabezado = f'Aprobada: {materias[codigos[0]]["nombre"]}'
            else:
                aprobadas = ', '.join(materias[codigo]['nombre'] for codigo in nuevas_aprobadas)
                encabezado = f'Aprobadas: {aprobadas}'
                repetidas = [codigo for codigo in codigos if codigo in antes]
                if repetidas:
                    nombres = ', '.join(materias[codigo]['nombre'] for codigo in repetidas)
                    encabezado += f'\\nYa estaban aprobadas: {nombres}'
            nuevas = listado_por_semestre(
                materias,
                lambda k, m: k not in hechas and k not in cursando_antes and
                habilitada(m, hechas) and not habilitada(m, antes),
                vacio='No se habilitaron materias nuevas.',
                mostrar_anio=True,
            )
            return f'{encabezado}\\n\\n**Materias recién habilitadas**\\n{nuevas}'
        hechas = self._aprobadas(usuario, plan)
        if palabras == ['progreso']:
            cantidad, total = progreso(materias, hechas, self._cursando(usuario, plan))
            if not total:
                return f'El plan {plan} todavía no tiene requisitos para contar.'
            porcentaje = f'{cantidad / total:.1%}'.replace('.', ',')
            return f'**{plan}**\nAvance estimado: **{porcentaje}** ({cantidad} de {total} requisitos aprobados o cursando).'
        cursando_set = self._cursando(usuario, plan)
        if faltantes:
            pendientes = listado_por_semestre(
                materias, lambda k, m: k not in hechas,
                vacio='¡Felicitaciones! No te faltan materias aprobadas en este plan.',
                mostrar_anio=True,
                estados={codigo: 'cursando' for codigo in cursando_set},
            )
            return f'**Materias pendientes del plan {plan}**\n{pendientes}'
        semestre = int(palabras[2]) if palabras[2:] in (["1"], ["2"]) else None
        return listado_por_semestre(
            materias, lambda k, m: k not in hechas and k not in cursando_set and habilitada(m, hechas), semestre,
            mostrar_anio=True,
        )

    def _planes_usuario(self, usuario):
        return [plan for plan, in self.db.execute(
            'SELECT plan FROM correlativas_usuarios_planes WHERE usuario=? ORDER BY plan', (usuario,)
        )]

    def _responder_varios_planes(self, usuario, palabras, planes, catalogo):
        hechas_por_plan = {plan: self._aprobadas(usuario, plan) for plan in planes}
        cursando_por_plan = {plan: self._cursando(usuario, plan) for plan in planes}
        if palabras == ['progreso']:
            resultados = []
            for plan in planes:
                cantidad, total = progreso(
                    catalogo[plan], hechas_por_plan[plan], cursando_por_plan[plan]
                )
                if total:
                    porcentaje = f'{cantidad / total:.1%}'.replace('.', ',')
                    resultados.append(
                        f'**{plan}**\nAvance estimado: **{porcentaje}** ({cantidad} de {total} requisitos aprobados o cursando).'
                    )
                else:
                    resultados.append(f'**{plan}**\nTodavía no tiene requisitos para contar.')
            return '\n\n'.join(resultados)
        if palabras == ['faltantes']:
            resultados = []
            for plan in planes:
                listado = listado_por_semestre(
                    catalogo[plan], lambda k, m: k not in hechas_por_plan[plan],
                    vacio='¡Plan completado! No te faltan materias aprobadas.', mostrar_anio=True,
                    estados={codigo: 'cursando' for codigo in cursando_por_plan[plan]},
                )
                resultados.append(f'**Materias pendientes — {plan}**\n{listado}')
            return '\n\n'.join(resultados)
        if palabras[:2] == ['materias', 'quiensigue']:
            semestre = int(palabras[2]) if palabras[2:] in (["1"], ["2"]) else None
            return '\n\n'.join(
                f'**Siguientes — {plan}**\n' + listado_por_semestre(
                    catalogo[plan], lambda k, m: k not in hechas_por_plan[plan] and
                    k not in cursando_por_plan[plan] and habilitada(m, hechas_por_plan[plan]),
                    semestre, mostrar_anio=True,
                ) for plan in planes
            )
        es_aprobacion = palabras[:2] == ['aprobar', 'materia']
        es_cursando = palabras[:2] == ['cursando', 'materia']
        if (es_aprobacion or es_cursando) and len(palabras) >= 3:
            consultas = [consulta.strip() for consulta in ' '.join(palabras[2:]).split(',')]
            if not consultas or any(not consulta for consulta in consultas):
                return 'Ingresá códigos o nombres separados por comas.'
            seleccionadas = {plan: [] for plan in planes}
            for consulta in consultas:
                normalizada = ' '.join(consulta.casefold().split())
                coincidencias = []
                for plan in planes:
                    for codigo, materia in catalogo[plan].items():
                        if normalizada in (codigo.casefold(), ' '.join(materia['nombre'].casefold().split())):
                            coincidencias.append((plan, codigo))
                if not coincidencias:
                    return f'No se identificó una materia activa: {consulta}. Usá el código del plan.'
                for plan, codigo in coincidencias:
                    if codigo not in seleccionadas[plan]:
                        seleccionadas[plan].append(codigo)
            resultados = []
            for plan, codigos in seleccionadas.items():
                if not codigos:
                    continue
                antes = hechas_por_plan[plan]
                estado_deseado = 'cursando' if es_cursando else 'aprobada'
                estados_actuales = self._estados(usuario, plan)
                cambios = [codigo for codigo in codigos
                           if estados_actuales.get(codigo) != estado_deseado and
                           not (es_cursando and estados_actuales.get(codigo) == 'aprobada')]
                for codigo in cambios:
                    self._guardar_estado(usuario, plan, codigo, estado_deseado)
                nombres = ', '.join(catalogo[plan][codigo]['nombre'] for codigo in cambios)
                if cambios:
                    encabezado = f'En cursada: {nombres}' if es_cursando else f'Aprobadas: {nombres}'
                else:
                    encabezado = 'Las materias indicadas ya estaban aprobadas o cursándose.'
                if es_aprobacion and cambios:
                    hechas = self._aprobadas(usuario, plan)
                    nuevas = listado_por_semestre(
                        catalogo[plan],
                        lambda k, m: k not in hechas and k not in cursando_por_plan[plan] and
                        habilitada(m, hechas) and not habilitada(m, antes),
                        vacio='No se habilitaron materias nuevas.', mostrar_anio=True,
                    )
                    resultados.append(f'**{plan}**\n{encabezado}\n{nuevas}')
                else:
                    resultados.append(f'**{plan}**\n{encabezado}')
            self.db.commit()
            return '\n\n'.join(resultados)
        return 'Elegí una operación: aprobar, cursando, siguientes, faltantes o progreso.'

    def _estados(self, usuario, plan):
        estados = {codigo: estado for codigo, estado in self.db.execute(
            'SELECT codigo, estado FROM correlativas_estados WHERE usuario=? AND plan=?', (usuario, plan)
        )}
        for codigo, in self.db.execute(
            'SELECT codigo FROM correlativas_aprobadas WHERE usuario=? AND plan=?', (usuario, plan)
        ):
            estados.setdefault(codigo, 'aprobada')
        return estados

    def _aprobadas(self, usuario, plan):
        return {codigo for codigo, estado in self._estados(usuario, plan).items() if estado == 'aprobada'}

    def _cursando(self, usuario, plan):
        return {codigo for codigo, estado in self._estados(usuario, plan).items() if estado == 'cursando'}

    def _guardar_estado(self, usuario, plan, codigo, estado):
        self.db.execute(
            'INSERT INTO correlativas_estados VALUES (?, ?, ?, ?) '
            'ON CONFLICT(usuario, plan, codigo) DO UPDATE SET estado=excluded.estado',
            (usuario, plan, codigo, estado),
        )



def ejecutar(usuario, mensaje, administrador=False):
    """Ejecuta una operación de correlativas fuera del bucle de Discord."""
    with conectar_sync() as db:
        return Bot(db, admins=(usuario,) if administrador else ()).responder(str(usuario), mensaje)


def sugerir_aprobacion(usuario, consulta):
    """Busca hasta 25 materias pendientes y habilitadas del plan activo."""
    consulta = consulta.strip().casefold()
    with conectar_sync() as db:
        usuario = str(usuario)
        bot = Bot(db)
        catalogo = bot.catalogo()
        opciones = []
        for plan in bot._planes_usuario(usuario):
            hechas = bot._aprobadas(usuario, plan)
            for codigo, materia in catalogo.get(plan, {}).items():
                nombre = materia['nombre']
                if codigo in hechas or not habilitada(materia, hechas):
                    continue
                if consulta in codigo.casefold() or consulta in nombre.casefold():
                    opcion = (codigo, nombre)
                    if opcion not in opciones:
                        opciones.append(opcion)
        return sorted(opciones, key=lambda opcion: (
            not opcion[0].casefold().startswith(consulta), opcion[0]
        ))[:25]
