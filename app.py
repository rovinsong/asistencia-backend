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
        # Convertimos el CSV en lista
        dias_list = t.dias.split(',') if t.dias else []
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
    dias    = data.get('dias', [])  # esperamos un array de strings
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400

    # Validar que dias sea lista de strings
    if not isinstance(dias, list) or not all(isinstance(d, str) for d in dias):
        return jsonify({'error': 'dias debe ser un array de strings'}), 400

    nuevo = Taller(
        nombre=nombre,
        dias=','.join(dias)  # almacenamos como CSV
    )
    db.session.add(nuevo)
    db.session.commit()

    return jsonify({
        'id': nuevo.id,
        'nombre': nuevo.nombre,
        'dias': dias
    }), 201

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

# … resto de tus rutas de alumnos, asistencias, bulk, etc. …
# (sin cambios respecto a la versión que ya tienes)

if __name__ == '__main__':
    app.run(debug=True)
