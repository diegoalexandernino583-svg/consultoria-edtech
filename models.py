"""
Modelos de Datos Relacionales (SQLAlchemy / Azure SQL Database).
Estructura relacional optimizada con tipos e índices compuestos.
"""
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.sql import func
from database import Base


class Organizacion(Base):
    __tablename__ = "organizaciones"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    nombre = Column(String(500), nullable=False)
    tipo_organizacion = Column(String(100), nullable=False)
    dominio_permitido = Column(String(255), nullable=False)
    licencias_asignadas = Column(BigInteger, default=500)
    max_administradores = Column(BigInteger, default=50)
    max_mentores = Column(BigInteger, default=100)
    fecha_creacion = Column(String(100), default=func.datetime('now', 'localtime'))
    estado_activo = Column(Integer, default=1)

    # Alias semántico para compatibilidad institucional
    @property
    def cupos_contratados(self):
        return self.licencias_asignadas

    @cupos_contratados.setter
    def cupos_contratados(self, val):
        self.licencias_asignadas = val


# Alias de clase para interoperabilidad
Institucion = Organizacion


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    organizacion_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=True, index=True)
    mentor_id = Column(BigInteger, ForeignKey("usuarios.id"), nullable=True, index=True)
    nombre = Column(String(255), nullable=False)
    correo = Column(String(255), nullable=False, unique=True, index=True)
    rol = Column(String(100), nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)

    # Índices compuestos para responder búsquedas y conteos masivos en milisegundos
    __table_args__ = (
        Index("ix_usuarios_org_rol", "organizacion_id", "rol"),
        Index("ix_usuarios_org_correo", "organizacion_id", "correo"),
    )

    @property
    def institucion_id(self):
        return self.organizacion_id

    @institucion_id.setter
    def institucion_id(self, val):
        self.organizacion_id = val

    @property
    def email(self):
        return self.correo

    @email.setter
    def email(self, val):
        self.correo = val


class CatalogoCursos(Base):
    __tablename__ = "catalogo_cursos"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    nombre_curso = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)


class ProgresoCursos(Base):
    __tablename__ = "progreso_cursos"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id"), index=True)
    curso_id = Column(BigInteger, ForeignKey("catalogo_cursos.id"), index=True)
    porcentaje_avance = Column(Float, default=0.0)
    tiempo_dedicado_minutos = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_progreso_usr_curso", "usuario_id", "curso_id"),
    )


class BodegaLegalArchivo(Base):
    __tablename__ = "bodega_legal_archivos"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    categoria = Column(String(100), nullable=False)
    organizacion_id = Column(BigInteger, nullable=True, index=True)
    nombre_archivo = Column(String(500), nullable=False)
    descripcion = Column(Text, nullable=True)
    tamano_bytes = Column(BigInteger, default=0)
    contenido_b64 = Column(Text, nullable=True)
    subido_por = Column(String(255), default="diegoalexander.nino.583@hotmail.com")
    fecha_subida = Column(String(100), default=func.datetime('now', 'localtime'))


class ConfiguracionBodegaLegal(Base):
    __tablename__ = "configuracion_boveda_legal"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    correo_autorizado = Column(String(255), unique=True, nullable=False)
    nombre_responsable = Column(String(255), default="Diego Alexander Niño")
    cargo = Column(String(255), default="Oficial de Cumplimiento & Bodega Legal")
    activo = Column(Integer, default=1)
    clave_plana = Column(String(255), default="123456")
    asignado_por = Column(String(255), default="alexander.nino.583@gmail.com")
    fecha_asignacion = Column(String(100), default=func.datetime('now', 'localtime'))


class VideojuegoMatematicasEjercicios(Base):
    __tablename__ = "videojuego_matematicas_ejercicios"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    nivel = Column(String(50), nullable=False, index=True)  # escolarizado, educativo, vocacional
    categoria = Column(String(50), nullable=False)  # conteo, problema, finanzas, etc.
    titulo = Column(String(255), nullable=False)
    enunciado = Column(Text, nullable=False)
    imagen_o_icono = Column(String(100), nullable=True)
    opciones_json = Column(Text, nullable=False)
    respuesta_correcta = Column(String(255), nullable=False)
    explicacion = Column(Text, nullable=True)
    puntos = Column(Integer, default=100)
    tiempo_limite_segundos = Column(Integer, default=60)
    activo = Column(Integer, default=1)


class ProgresoVideojuegoMatematicas(Base):
    __tablename__ = "progreso_videojuego_matematicas"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id"), nullable=False, index=True)
    organizacion_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=True, index=True)
    nivel = Column(String(50), nullable=False, index=True)
    puntaje_obtenido = Column(Integer, nullable=False)
    aciertos = Column(Integer, nullable=False)
    total_preguntas = Column(Integer, nullable=False)
    tiempo_empleado_segundos = Column(Integer, default=0)
    recompensas_json = Column(Text, nullable=True)
    feedback_mensaje = Column(Text, nullable=True)
    fecha_registro = Column(String(100), default=func.datetime('now', 'localtime'))

