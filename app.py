# backend/app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, Alumno, Taller, Asistencia
from datetime import datetime
import os

app = Flask(__name__)

# Configuración de la BD (Postgres en Render o SQLite local)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///asistencia.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Habilitar CORS para el frontend en Vercel
CORS(app, origins=["https://asistencia-frontend.vercel.app"])

# Inicializar extensiones
db.init_app(app)
migrate = Migrate(app, db)

# Crear tablas si no existen
with app.app_context():
    db.create_all()


# ——— RUTAS de Talleres —————————————————————————————
@app.route('/talleres', methods=['GET'])
def get_talleres():
    talleres = Taller.query.order_by(Taller.nombre).all()
    resultado = []
    for t in talleres:
        dias_list = t.dias.split(',') if getattr(t, 'dias', None) else []
        resultado.append({
            'id': t.id,
            'nombre': t.nombre,
            'dias': dias_list
        })
    return jsonify(resultado), 200

@app.route('/talleres', methods=['POST'])
def crear_taller():
    data = request.get_json() or {}
    nombre = data.get('nombre')
    dias    = data.get('dias', [])
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    if not isinstance(dias, list) or not all(isinstance(d, str) for d in dias):
        return jsonify({'error': 'dias debe ser un array de strings'}), 400

    nuevo = Taller(nombre=nombre, dias=','.join(dias))
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({'id': nuevo.id, 'nombre': nuevo.nombre, 'dias': dias}), 201

@app.route('/talleres/<int:id>', methods=['PUT'])
def actualizar_taller(id):
    data = request.get_json() or {}
    nombre = data.get('nombre')
    dias    = data.get('dias')
    if not nombre and dias is None:
        return jsonify({'error': 'Debes enviar nombre y/o dias'}), 400

    taller = Taller.query.get_or_404(id)
    if nombre:
        taller.nombre = nombre
    if dias is not None:
        if not isinstance(dias, list) or not all(isinstance(d, str) for d in dias):
            return jsonify({'error': 'dias debe ser un array de strings'}), 400
        taller.dias = ','.join(dias)
    db.session.commit()

    return jsonify({
        'id': taller.id,
        'nombre': taller.nombre,
        'dias': taller.dias.split(',') if taller.dias else []
    }), 200

@app.route('/talleres/<int:id>', methods=['DELETE'])
def eliminar_taller(id):
    taller = Taller.query.get_or_404(id)
    db.session.delete(taller)
    db.session.commit()
    return jsonify({'message': 'Taller eliminado correctamente'}), 200


# ——— RUTAS de Alumnos —————————————————————————————
@app.route('/alumnos', methods=['GET'])
def get_alumnos():
    alumnos = Alumno.query.order_by(Alumno.apellidos).all()
    resultado = []
    for a in alumnos:
        resultado.append({
            'id': a.id,
            'nombre': a.nombre,
            'apellidos': a.apellidos,
            'direccion': a.direccion,
            'telefono': a.telefono,
            'talleres': [t.id for t in a.talleres]
        })
    return jsonify(resultado), 200

@app.route('/alumnos', methods=['POST'])
def crear_alumno():
    data = request.get_json() or {}
    alumno = Alumno(
        nombre=data.get('nombre'),
        apellidos=data.get('apellidos'),
        direccion=data.get('direccion'),
        telefono=data.get('telefono')
    )
    taller_id = data.get('tallerId')
    if taller_id:
        taller = Taller.query.get(taller_id)
        if taller:
            alumno.talleres.append(taller)
    db.session.add(alumno)
    db.session.commit()
    return jsonify({'message': 'Alumno creado correctamente'}), 201

@app.route('/alumnos/<int:id>', methods=['PUT'])
def actualizar_alumno(id):
    data = request.get_json() or {}
    alumno = Alumno.query.get_or_404(id)
    # Actualizar sólo campos enviados
    if data.get('nombre'):    alumno.nombre    = data['nombre']
    if data.get('apellidos'): alumno.apellidos = data['apellidos']
    if data.get('direccion'): alumno.direccion = data['direccion']
    if data.get('telefono'):  alumno.telefono  = data['telefono']
    db.session.commit()
    return jsonify({'message': 'Alumno actualizado correctamente'}), 200

@app.route('/alumnos/<int:alumno_id>/talleres/<int:taller_id>', methods=['DELETE'])
def remove_alumno_from_taller(alumno_id, taller_id):
    alumno = Alumno.query.get_or_404(alumno_id)
    taller = Taller.query.get_or_404(taller_id)
    if taller in alumno.talleres:
        alumno.talleres.remove(taller)
        db.session.commit()
        return jsonify({'message': f'Alumno {alumno_id} eliminado de taller {taller_id}'}), 200
    return jsonify({'error': 'El alumno no pertenece a ese taller'}), 400

@app.route('/alumnos/<int:id>', methods=['DELETE'])
def eliminar_alumno(id):
    alumno = Alumno.query.get_or_404(id)
    db.session.delete(alumno)
    db.session.commit()
    return jsonify({'message': 'Alumno eliminado correctamente'}), 200

@app.route('/alumnos/bulk', methods=['POST'])
def bulk_create_alumnos():
    data = request.get_json() or {}
    lista = data.get('alumnos', [])
    importados, errores = [], []
    for idx, item in enumerate(lista):
        nombre    = item.get('nombre')
        apellidos = item.get('apellidos')
        direccion = item.get('direccion')
        telefono  = item.get('telefono')
        taller_id = item.get('tallerId')
        if not (nombre and apellidos and taller_id):
            errores.append({'index': idx, 'error': 'Faltan nombre, apellidos o tallerId'})
            continue
        taller = Taller.query.get(taller_id)
        if not taller:
            errores.append({'index': idx, 'error': f'Taller {taller_id} no existe'})
            continue
        alumno = Alumno(nombre=nombre, apellidos=apellidos, direccion=direccion, telefono=telefono)
        alumno.talleres.append(taller)
        db.session.add(alumno)
        importados.append({'index': idx, 'nombre': nombre, 'apellidos': apellidos})
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Fallo al guardar en la base', 'detalle': str(e)}), 500
    return jsonify({'importados': importados, 'errores': errores}), 201


# ——— RUTAS de Asistencia e Historial —————————————————————————————
@app.route('/asistencias', methods=['GET'])
def get_asistencias():
    """
    Parámetros:
      - taller_id (int, requerido)
      - fecha     (YYYY-MM-DD, requerido)
      - alumno_id (int, opcional)
    """
    taller_id = request.args.get('taller_id', type=int)
    fecha_str = request.args.get('fecha')
    alumno_id = request.args.get('alumno_id', type=int)
    if not (taller_id and fecha_str):
        return jsonify({'error': 'taller_id y fecha son requeridos'}), 400

    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    alumnos = Alumno.query.join(Alumno.talleres) \
        .filter(Taller.id == taller_id) \
        .order_by(Alumno.apellidos).all()

    resultado = []
    for alumno in alumnos:
        reg = next((r for r in alumno.asistencias if r.fecha == fecha), None)
        resultado.append({
            'alumno_id': alumno.id,
            'nombre':    alumno.nombre,
            'apellidos': alumno.apellidos,
            'presente':  bool(reg.presente) if reg else False
        })

    if alumno_id:
        resultado = [r for r in resultado if r['alumno_id'] == alumno_id]
    return jsonify(resultado), 200

@app.route('/asistencias', methods=['POST'])
def guardar_asistencias():
    data = request.get_json() or {}
    taller_id = data.get('taller_id')
    fecha = datetime.strptime(data.get('fecha'), '%Y-%m-%d').date()
    lista = data.get('asistencias', [])

    # Borrar registros previos sin usar join
    alumno_ids = [a.id for a in Alumno.query.filter(Alumno.talleres.any(id=taller_id)).all()]
    if alumno_ids:
        Asistencia.query \
            .filter(Asistencia.fecha == fecha, Asistencia.alumno_id.in_(alumno_ids)) \
            .delete(synchronize_session=False)

    for item in lista:
        a = Asistencia(fecha=fecha, presente=item.get('presente', False), alumno_id=item.get('alumno_id'))
        db.session.add(a)

    db.session.commit()
    return jsonify({'message': 'Asistencias registradas'}), 201


if __name__ == '__main__':
    app.run(debug=True)
