from flask_sqlalchemy import SQLAlchemy

# Inicializar SQLAlchemy
db = SQLAlchemy()

# Tabla de relación muchos-a-muchos Alumno ⇄ Taller
alumno_taller = db.Table(
    'alumno_taller',
    db.Column('alumno_id', db.Integer, db.ForeignKey('alumno.id'), primary_key=True),
    db.Column('taller_id', db.Integer, db.ForeignKey('taller.id'), primary_key=True),
)

class Taller(db.Model):
    __tablename__ = 'taller'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)

    alumnos = db.relationship(
        'Alumno',
        secondary=alumno_taller,
        back_populates='talleres'
    )

class Alumno(db.Model):
    __tablename__ = 'alumno'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(50))

    talleres = db.relationship(
        'Taller',
        secondary=alumno_taller,
        back_populates='alumnos'
    )
    asistencias = db.relationship(
        'Asistencia',
        back_populates='alumno',
        cascade='all, delete-orphan'
    )

class Asistencia(db.Model):
    __tablename__ = 'asistencia'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    presente = db.Column(db.Boolean, nullable=False, default=False)

    alumno_id = db.Column(db.Integer, db.ForeignKey('alumno.id'), nullable=False)
    alumno = db.relationship('Alumno', back_populates='asistencias')

# ——— NUEVO: Modelo de Usuarios ——————————————————————————
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
