"""
models.py
Modelos de Datos Relacionales (SQLAlchemy / Azure SQL Database).
Estructura desacoplada para arquitectura SaaS Multi-Tenant con tenant_id obligatorio e índices compuestos.
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
    """Entidad raíz del Tenant (Colegio / Institución Educativa)."""
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

    @property
    def tenant_id(self):
        return self.id

    @property
    def cupos_contratados(self):
        return self.licencias_asignadas

    @cupos_contratados.setter
    def cupos_contratados(self, val):
        self.licencias_asignadas = val


Institucion = Organizacion


class Usuario(Base):
    """Usuarios pertenecientes a una institución educativa (RBAC)."""
    __tablename__ = "usuarios"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    organizacion_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=True, index=True)
    mentor_id = Column(BigInteger, ForeignKey("usuarios.id"), nullable=True, index=True)
    nombre = Column(String(255), nullable=False)
    correo = Column(String(255), nullable=False, unique=True, index=True)
    rol = Column(String(100), nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_usuarios_org_rol", "organizacion_id", "rol"),
        Index("ix_usuarios_org_correo", "organizacion_id", "correo"),
    )

    @property
    def tenant_id(self):
        return self.organizacion_id

    @tenant_id.setter
    def tenant_id(self, val):
        self.organizacion_id = val

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
    organizacion_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=True, index=True)
    nombre_curso = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)

    @property
    def tenant_id(self):
        return self.organizacion_id

    @tenant_id.setter
    def tenant_id(self, val):
        self.organizacion_id = val


class ProgresoCursos(Base):
    __tablename__ = "progreso_cursos"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    organizacion_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=True, index=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id"), index=True)
    curso_id = Column(BigInteger, ForeignKey("catalogo_cursos.id"), index=True)
    porcentaje_avance = Column(Float, default=0.0)
    tiempo_dedicado_minutos = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_progreso_usr_curso", "usuario_id", "curso_id"),
    )

    @property
    def tenant_id(self):
        return self.organizacion_id

    @tenant_id.setter
    def tenant_id(self, val):
        self.organizacion_id = val


class RegistroLogistica(Base):
    """
    Control y seguimiento de recursos logísticos del colegio (aulas, cómputo, despachos).
    Sincronizado en tiempo real vía WebSockets / SSE.
    """
    __tablename__ = "registro_logistica"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=False, index=True)
    categoria = Column(String(100), nullable=False)  # AULAS, EQUIPOS, MATERIAL_PEDAGOGICO, INFRAESTRUCTURA
    recurso = Column(String(255), nullable=False)
    cantidad = Column(Integer, default=1)
    estado = Column(String(50), default="DISPONIBLE")  # DISPONIBLE, ASIGNADO, EN_MANTENIMIENTO
    ubicacion = Column(String(255), nullable=True)
    observaciones = Column(Text, nullable=True)
    responsable_id = Column(BigInteger, ForeignKey("usuarios.id"), nullable=True)
    fecha_actualizacion = Column(String(100), default=func.datetime('now', 'localtime'))

    __table_args__ = (
        Index("ix_logistica_tenant_estado", "tenant_id", "estado"),
        Index("ix_logistica_tenant_categoria", "tenant_id", "categoria"),
    )

    @property
    def organizacion_id(self):
        return self.tenant_id

    @organizacion_id.setter
    def organizacion_id(self, val):
        self.tenant_id = val


class CalificacionNota(Base):
    """
    Registro y seguimiento de notas académicas por periodo y materia.
    Sincronizado en tiempo real vía WebSockets / SSE.
    """
    __tablename__ = "calificaciones_notas"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=False, index=True)
    estudiante_id = Column(BigInteger, ForeignKey("usuarios.id"), nullable=False, index=True)
    docente_id = Column(BigInteger, ForeignKey("usuarios.id"), nullable=True, index=True)
    curso_id = Column(BigInteger, ForeignKey("catalogo_cursos.id"), nullable=True)
    materia = Column(String(200), nullable=False)
    periodo = Column(String(100), nullable=False)
    nota = Column(Float, nullable=False)
    observaciones = Column(Text, nullable=True)
    fecha_registro = Column(String(100), default=func.datetime('now', 'localtime'))

    __table_args__ = (
        Index("ix_calificaciones_tenant_estudiante", "tenant_id", "estudiante_id"),
        Index("ix_calificaciones_tenant_materia", "tenant_id", "materia"),
    )

    @property
    def organizacion_id(self):
        return self.tenant_id

    @organizacion_id.setter
    def organizacion_id(self, val):
        self.tenant_id = val


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

    @property
    def tenant_id(self):
        return self.organizacion_id

    @tenant_id.setter
    def tenant_id(self, val):
        self.organizacion_id = val


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
    nivel = Column(String(50), nullable=False, index=True)
    categoria = Column(String(50), nullable=False)
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

    @property
    def tenant_id(self):
        return self.organizacion_id

    @tenant_id.setter
    def tenant_id(self, val):
        self.organizacion_id = val


class AuditLog(Base):
    """
    Tabla de Auditoría en Tiempo Real (audit_logs / registro_actividad).
    Registra cada inserción, modificación o eliminación de usuarios dentro de cualquier institución (tenant_id).
    """
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    tenant_id = Column(BigInteger, ForeignKey("organizaciones.id"), nullable=False, index=True)
    usuario_afectado = Column(String(255), nullable=False, index=True)
    accion = Column(String(50), nullable=False, index=True)  # REGISTRO, MODIFICACION, ELIMINACION, ALTA, BAJA
    detalles = Column(Text, nullable=True)
    ip_origen = Column(String(50), default="127.0.0.1")
    origen = Column(String(50), default="SISTEMA")  # WEBHOOK_MAKE, INTERFAZ, API
    timestamp = Column(String(100), default=func.datetime('now', 'localtime'))

    __table_args__ = (
        Index("ix_audit_logs_tenant_timestamp", "tenant_id", "timestamp"),
        Index("ix_audit_logs_tenant_accion", "tenant_id", "accion"),
    )

    @property
    def fecha_hora(self):
        return self.timestamp


# Alias para compatibilidad semántica
RegistroActividad = AuditLog
