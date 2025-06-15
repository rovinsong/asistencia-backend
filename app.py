from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from models import db, Alumno, Taller, Asistencia
from datetime import datetime
import os

app = Flask(__name__)
# Configurar la URL de la base de datos (PostgreSQL en Render o SQLite local)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///asistencia.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Habilitar CORS: permitir peticiones solo desde el frontend desplegado en Vercel,
# incluyendo métodos y cabeceras para preflight
CORS(
    app,
    resources={r"/*": {"origins": ["https://asistencia-frontend.vercel.app"],
                           "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                           "allow_headers": ["Content-Type", "Authorization"]}}
)

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
    return jsonify([{'id': t.id, 'nombre': t.nombre} for t in talleres])

@app.route('/talleres', methods=['POST'])
def crear_taller():
    data = request.get_json()
    nombre = data.get('nombre')
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    nuevo = Taller(nombre=nombre)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({'id': nuevo.id, 'nombre': nuevo.nombre}), 201

@app.route('/talleres/<int:id>', methods=['PUT'])
def actualizar_taller(id):
    data = request.get_json()
    nombre = data.get('nombre')
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    taller = Taller.query.get_or_404(id)
    taller.nombre = nombre
    db.session.commit()
    return jsonify({'id': taller.id, 'nombre': taller.nombre})

@app.route('/talleres/<int:id>', methods=['DELETE'])
def eliminar_taller(id):
    taller = Taller.query.get_or_404(id)
    db.session.delete(taller)
    db.session.commit()
    return jsonify({'message': 'Taller eliminado correctamente'})

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
    return jsonify(resultado)

@app.route('/alumnos', methods=['POST'])
def crear_alumno():
    data = request.get_json()
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

# ——— RUTAS de Asistencia e Historial —————————————————————————————
@app.route('/asistencias', methods=['GET'])
def get_asistencias():
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
            'nombre': alumno.nombre,
            'apellidos': alumno.apellidos,
            'presente': bool(reg.presente) if reg else False
        })
    if alumno_id:
        resultado = [r for r in resultado if r['alumno_id'] == alumno_id]
    return jsonify(resultado)

@app.route('/asistencias', methods=['POST'])
def guardar_asistencias():
    data = request.get_json()
    taller_id = data.get('taller_id')
    fecha = datetime.strptime(data.get('fecha'), '%Y-%m-%d').date()
    lista = data.get('asistencias', [])

    # 1) Obtener IDs de alumnos del taller
    alumno_ids = [
        a.id for a in Alumno.query
            .filter(Alumno.talleres.any(id=taller_id))
            .all()
    ]

    # 2) Borrar registros previos sin usar join()
    if alumno_ids:
        Asistencia.query \
            .filter(
                Asistencia.fecha == fecha,
                Asistencia.alumno_id.in_(alumno_ids)
            ) \
            .delete(synchronize_session=False)

    # 3) Crear nuevos registros
    for item in lista:
        a = Asistencia(
            fecha=fecha,
            presente=item.get('presente', False),
            alumno_id=item.get('alumno_id')
        )
        db.session.add(a)

    db.session.commit()
    return jsonify({'message': 'Asistencias registradas'}), 201

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
        # Validación mínima
        if not (nombre and apellidos and taller_id):
            errores.append({'index': idx, 'error': 'Faltan nombre, apellidos o tallerId'})
            continue
        taller = Taller.query.get(taller_id)
        if not taller:
            errores.append({'index': idx, 'error': f'Taller {taller_id} no existe'})
            continue
        alumno = Alumno(
            nombre=nombre,
            apellidos=apellidos,
            direccion=direccion,
            telefono=telefono
        )
        alumno.talleres.append(taller)
        db.session.add(alumno)
        importados.append({'index': idx, 'nombre': nombre, 'apellidos': apellidos})
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Fallo al guardar en la base', 'detalle': str(e)}), 500
    return jsonify({'importados': importados, 'errores': errores}), 201

if __name__ == '__main__':
    app.run(debug=True)
