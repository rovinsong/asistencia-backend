# backend/app.py

from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from models import db, Alumno, Taller, Asistencia, User
from datetime import datetime
import os

app = Flask(__name__)

# Configuración de la BD (Postgres en Render o SQLite local)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///asistencia.db')
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración JWT
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key')

# Habilitar CORS para el frontend (Vercel)
given_origins = ["https://asistencia-frontend.vercel.app"]
CORS(app, resources={r"/*": {"origins": given_origins}}, supports_credentials=True)

# Inicializar extensiones
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
db.init_app(app)
migrate = Migrate(app, db)

# Crear tablas si no existen
with app.app_context():
    db.create_all()


# ——— AUTH: Usuarios ————————————————————————
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username y password requeridos'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Usuario ya existe'}), 409
    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(username=username, password_hash=pw_hash)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Usuario creado'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Credenciales inválidas'}), 401
    access_token = create_access_token(identity=user.id)
    return jsonify({'access_token': access_token}), 200


@app.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    return jsonify({'id': user.id, 'username': user.username})


# ——— RUTAS de Talleres —————————————————————————————
@app.route('/talleres', methods=['GET'])
@jwt_required()
def get_talleres():
    talleres = Taller.query.order_by(Taller.nombre).all()
    return jsonify([{'id': t.id, 'nombre': t.nombre} for t in talleres])


@app.route('/talleres', methods=['POST'])
@jwt_required()
def crear_taller():
    data = request.get_json() or {}
    nombre = data.get('nombre')
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    nuevo = Taller(nombre=nombre)
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({'id': nuevo.id, 'nombre': nuevo.nombre}), 201


@app.route('/talleres/<int:id>', methods=['PUT'])
@jwt_required()
def actualizar_taller(id):
    data = request.get_json() or {}
    nombre = data.get('nombre')
    if not nombre:
        return jsonify({'error': 'El nombre es requerido'}), 400
    taller = Taller.query.get_or_404(id)
    taller.nombre = nombre
    db.session.commit()
    return jsonify({'id': taller.id, 'nombre': taller.nombre})


@app.route('/talleres/<int:id>', methods=['DELETE'])
@jwt_required()
def eliminar_taller(id):
    taller = Taller.query.get_or_404(id)
    db.session.delete(taller)
    db.session.commit()
    return jsonify({'message': 'Taller eliminado correctamente'})


# ——— RUTAS de Alumnos —————————————————————————————
@app.route('/alumnos', methods=['GET'])
@jwt_required()
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
@jwt_required()
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


# ——— RUTA: ELIMINAR ALUMNO DE TALLER —————————————————————————————
@app.route(
    '/alumnos/<int:alumno_id>/talleres/<int:taller_id>',
    methods=['DELETE', 'OPTIONS']
)
@jwt_required()
@cross_origin(
    origins="https://asistencia-frontend.vercel.app",
    methods=["DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"]
)
def remove_alumno_from_taller(alumno_id, taller_id):
    # Responder preflight OPTIONS
    if request.method == 'OPTIONS':
        return '', 200

    alumno = Alumno.query.get_or_404(alumno_id)
    taller = Taller.query.get_or_404(taller_id)

    if taller in alumno.talleres:
        alumno.talleres.remove(taller)
        db.session.commit()
        return jsonify({
            'message': f'Alumno {alumno_id} eliminado de taller {taller_id}'
        }), 200
    return jsonify({'error': 'El alumno no pertenece a ese taller'}), 400


# ——— RUTAS de Asistencia e Historial —————————————————————————————
@app.route('/asistencias', methods=['GET'])
@jwt_required()
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
@jwt_required()
def guardar_asistencias():
    data = request.get_json() or {}
    taller_id = data.get('taller_id')
    fecha = datetime.strptime(data.get('fecha'), '%Y-%m-%d').date()
    lista = data.get('asistencias', [])

    # Borrar registros previos de manera segura (sin join)
    alumno_ids = [
        a.id for a in Alumno.query
            .filter(Alumno.talleres.any(id=taller_id))
            .all()
    ]
    if alumno_ids:
        Asistencia.query \
            .filter(
                Asistencia.fecha == fecha,
                Asistencia.alumno_id.in_(alumno_ids)
            ) \
            .delete(synchronize_session=False)

    # Registrar nuevas asistencias
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
@jwt_required()
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

