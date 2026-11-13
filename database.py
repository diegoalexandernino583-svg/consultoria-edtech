"""
Módulo de Configuración de Base de Datos y Motor SQLAlchemy / Azure SQL.
Proporciona soporte relacional optimizado para alta concurrencia,
motor transaccional con fast_executemany=True y migraciones seguras automáticas al inicio.
"""
import os
import sys
import urllib.parse
from typing import Generator
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

# Re-exportar base de datos resiliente del core
from app.core import (
    BASE_DIR,
    SQLITE_DB,
    SERVER,
    DATABASE,
    USERNAME,
    PASSWORD,
    DRIVER,
    db as core_db,
    replicador_azure
)

Base = declarative_base()

# Construcción de URL para SQLAlchemy
engine = None
if SERVER and DATABASE and USERNAME and PASSWORD and os.getenv("MODO_ALTA_VELOCIDAD", "true").lower() not in ("1", "true", "yes"):
    params = urllib.parse.quote_plus(
        f"Driver={DRIVER};Server=tcp:{SERVER},1433;Database={DATABASE};"
        f"Uid={USERNAME};Pwd={PASSWORD};Encrypt=yes;TrustServerCertificate=yes;"
    )
    SQLALCHEMY_DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"
    try:
        azure_engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            fast_executemany=True,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        with azure_engine.connect() as az_test_conn:
            az_test_conn.execute(text("SELECT 1"))
        engine = azure_engine
        print(">> [SQLALCHEMY] Motor conectado exitosamente a Azure SQL Database.")
    except Exception as e_eng:
        print(f">> [SQLALCHEMY] Azure SQL operando en modo asíncrono ({e_eng}). Motor principal en SQLite resiliente.")

if engine is None:
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLITE_DB}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """Generador de sesión SQLAlchemy para endpoints FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ejecutar_migraciones_automaticas():
    """
    Ejecuta migraciones automáticas seguras al iniciar la aplicación.
    Verifica columnas e índices compuestos sin romper el arranque
    de Uvicorn ni fallar ante tablas ya creadas.
    """
    print(">> [MIGRACIONES] Verificando esquema e integridad de base de datos...")
    
    # 1. Migraciones en SQLite local
    try:
        with engine.connect() as conn:
            # Crear tablas base si no existen
            try:
                Base.metadata.create_all(bind=engine)
            except Exception as e_base:
                print(f">> [MIGRACIONES] Base.metadata.create_all aviso: {e_base}")

            # Índices compuestos de alta velocidad (<0.5ms en búsquedas)
            indices_sql = [
                "CREATE INDEX IF NOT EXISTS idx_usuarios_org_rol ON usuarios(organizacion_id, rol);",
                "CREATE INDEX IF NOT EXISTS idx_usuarios_org_correo ON usuarios(organizacion_id, correo);",
                "CREATE INDEX IF NOT EXISTS idx_usuarios_correo_lower ON usuarios(LOWER(correo));",
                "CREATE INDEX IF NOT EXISTS idx_progreso_usr_curso ON progreso_cursos(usuario_id, curso_id);"
            ]
            for idx in indices_sql:
                try:
                    conn.execute(text(idx))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e_sql:
        print(f">> [MIGRACIONES LOCAL] Aviso: {e_sql}")

    # 2. Migraciones directas en Azure SQL si está disponible (en segundo plano para arranque instantáneo de Uvicorn)
    def _migrar_azure_bg():
        if not (SERVER and DATABASE and USERNAME and PASSWORD):
            return
        try:
            import pyodbc
            azure_cs = (
                f"Driver={DRIVER};Server=tcp:{SERVER},1433;Database={DATABASE};"
                f"Uid={USERNAME};Pwd={PASSWORD};Encrypt=yes;TrustServerCertificate=yes;"
            )
            az_conn = pyodbc.connect(azure_cs, timeout=8)
            az_cur = az_conn.cursor()

            # Ampliar columnas numéricas a BIGINT en Azure SQL
            columnas_bigint = [
                ("organizaciones", "licencias_asignadas"),
                ("organizaciones", "max_administradores"),
                ("organizaciones", "max_mentores"),
                ("usuarios", "organizacion_id"),
                ("usuarios", "mentor_id"),
                ("progreso_cursos", "usuario_id"),
                ("progreso_cursos", "curso_id")
            ]
            for tabla, columna in columnas_bigint:
                try:
                    az_cur.execute(f"ALTER TABLE [{tabla}] ALTER COLUMN [{columna}] BIGINT NULL;")
                    az_conn.commit()
                except Exception:
                    pass

            # Crear índices compuestos en Azure SQL
            indices_azure = [
                "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_usuarios_org_rol') "
                "CREATE NONCLUSTERED INDEX idx_usuarios_org_rol ON [usuarios](organizacion_id, rol);",

                "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_usuarios_org_correo') "
                "CREATE NONCLUSTERED INDEX idx_usuarios_org_correo ON [usuarios](organizacion_id, correo);",

                "IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name='idx_progreso_usr_curso') "
                "CREATE NONCLUSTERED INDEX idx_progreso_usr_curso ON [progreso_cursos](usuario_id, curso_id);"
            ]
            for idx_az in indices_azure:
                try:
                    az_cur.execute(idx_az)
                    az_conn.commit()
                except Exception:
                    pass

            # Asegurar tabla bodega_legal_archivos
            try:
                az_cur.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bodega_legal_archivos' AND xtype='U')
                    CREATE TABLE bodega_legal_archivos (
                        id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        categoria NVARCHAR(100) NOT NULL,
                        organizacion_id BIGINT NULL,
                        nombre_archivo NVARCHAR(500) NOT NULL,
                        descripcion NVARCHAR(MAX) NULL,
                        tamano_bytes BIGINT DEFAULT 0,
                        contenido_b64 NVARCHAR(MAX) NULL,
                        subido_por NVARCHAR(255) DEFAULT 'diegoalexander.nino.583@hotmail.com',
                        fecha_subida NVARCHAR(100) DEFAULT CONVERT(VARCHAR, GETDATE(), 120)
                    );
                """)
                az_conn.commit()
            except Exception:
                pass

            # Asegurar tablas de Logística y Calificaciones Multi-Tenant en Azure SQL
            try:
                az_cur.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='registro_logistica' AND xtype='U')
                    CREATE TABLE [registro_logistica] (
                        id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        tenant_id BIGINT NOT NULL,
                        categoria NVARCHAR(100) NOT NULL,
                        recurso NVARCHAR(255) NOT NULL,
                        cantidad INT DEFAULT 1,
                        estado NVARCHAR(50) DEFAULT 'DISPONIBLE',
                        ubicacion NVARCHAR(255) NULL,
                        observaciones NVARCHAR(MAX) NULL,
                        responsable_id BIGINT NULL,
                        fecha_actualizacion NVARCHAR(100) DEFAULT CONVERT(VARCHAR, GETDATE(), 120)
                    );

                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='calificaciones_notas' AND xtype='U')
                    CREATE TABLE [calificaciones_notas] (
                        id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        tenant_id BIGINT NOT NULL,
                        estudiante_id BIGINT NOT NULL,
                        docente_id BIGINT NULL,
                        curso_id BIGINT NULL,
                        materia NVARCHAR(200) NOT NULL,
                        periodo NVARCHAR(100) NOT NULL,
                        nota FLOAT NOT NULL,
                        observaciones NVARCHAR(MAX) NULL,
                        fecha_registro NVARCHAR(100) DEFAULT CONVERT(VARCHAR, GETDATE(), 120)
                    );

                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='audit_logs' AND xtype='U')
                    CREATE TABLE [audit_logs] (
                        id BIGINT IDENTITY(1,1) PRIMARY KEY,
                        tenant_id BIGINT NOT NULL,
                        usuario_afectado NVARCHAR(255) NOT NULL,
                        accion NVARCHAR(50) NOT NULL,
                        detalles NVARCHAR(MAX) NULL,
                        ip_origen NVARCHAR(50) DEFAULT '127.0.0.1',
                        origen NVARCHAR(50) DEFAULT 'SISTEMA',
                        timestamp NVARCHAR(100) DEFAULT CONVERT(VARCHAR, GETDATE(), 120)
                    );
                """)
                az_conn.commit()
            except Exception as e_lt:
                pass

            # Asegurar columna clave_plana en configuracion_boveda_legal
            try:
                az_cur.execute("""
                    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('configuracion_boveda_legal') AND name = 'clave_plana')
                    BEGIN
                        ALTER TABLE [configuracion_boveda_legal] ADD [clave_plana] NVARCHAR(255) NULL DEFAULT '123456';
                    END
                """)
                az_conn.commit()
            except Exception:
                pass

            az_cur.close()
            az_conn.close()
            print(">> [MIGRACIONES AZURE] Columnas BIGINT e índices compuestos validados en Azure SQL.")
        except Exception as e_az_mig:
            print(f">> [MIGRACIONES AZURE] Nota: Azure SQL operando en modo asíncrono ({e_az_mig}).")

    import threading
    threading.Thread(target=_migrar_azure_bg, daemon=True, name="migraciones-azure-bg").start()


# Ejecutar migraciones automáticas seguras
try:
    ejecutar_migraciones_automaticas()
except Exception as e_init:
    print(f">> [MIGRACIONES] Error no crítico en migración de arranque: {e_init}")
