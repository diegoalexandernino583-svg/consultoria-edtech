import os

import sys

import csv

import random

import socket

import smtplib

import sqlite3

import webbrowser

import subprocess

import re

import json

import shutil

import atexit

import threading

import io

import html

import time

import queue

import hashlib

import urllib.request

from datetime import datetime, timedelta

from email.message import EmailMessage

from email.utils import formatdate, make_msgid

from typing import Optional, List, Dict, Any

from urllib.parse import unquote

import openpyxl

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from openpyxl.utils import get_column_letter

from openpyxl.chart import BarChart, PieChart, Reference

import bcrypt

import pyodbc

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Request

from fastapi.middleware.cors import CORSMiddleware

from fastapi.middleware.gzip import GZipMiddleware

from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse, StreamingResponse, Response, JSONResponse

from pydantic import BaseModel

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

TUNNEL_PUBLIC_URL = None

PROCESO_TUNEL = None

PUERTO_ACTUAL = 8080

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

CSV_AUDITORIA = os.path.join(BASE_DIR, "auditoria_transacciones.csv")

SQLITE_DB = os.path.join(BASE_DIR, "consultoria_local.db")

SERVER = os.getenv("DB_SERVER") or os.getenv("SERVIDOR_BD")

DATABASE = os.getenv("DB_NAME") or os.getenv("NOMBRE_BD")

USERNAME = os.getenv("DB_USER") or os.getenv("USUARIO_BD")

PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("CLAVE_BD")

DRIVER = '{ODBC Driver 18 for SQL Server}'

AZURE_CONN_STR = (
    f"Driver={DRIVER};Server=tcp:{SERVER},1433;Database={DATABASE};Uid={USERNAME};"
    f"Pwd={PASSWORD};Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=8;MARS_Connection=yes;"
)

CORREO_APP = os.getenv("EMAIL_APP") or os.getenv("CORREO_APP")

CLAVE_APP = os.getenv("EMAIL_PASS") or os.getenv("CLAVE_APP")

codigos_2fa_activos: Dict[str, Dict[str, Any]] = {}

codigos_recuperacion: Dict[str, Dict[str, Any]] = {}

_cache_auth_bcrypt: set = set()

_cache_ip_local = {"ip": "127.0.0.1", "ts": 0.0}

def obtener_ip_local() -> str:
    """Detecta la dirección IP de red local (Wi-Fi/LAN) con caché de 60s para latencia cero"""
    ahora = time.time()
    if ahora - _cache_ip_local["ts"] < 60.0 and _cache_ip_local["ip"] != "127.0.0.1":
        return _cache_ip_local["ip"]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        _cache_ip_local["ip"] = ip
        _cache_ip_local["ts"] = ahora
        return ip
    except Exception:
        _cache_ip_local["ts"] = ahora
        return _cache_ip_local["ip"]

_cola_auditoria: "queue.SimpleQueue" = queue.SimpleQueue()

def _sanitizar_org_nombre(val: Any) -> str:
    """Garantiza que el nombre de institución sea siempre una cadena limpia (sin [object Object])"""
    if val is None:
        return "Plataforma Global"
    if isinstance(val, dict):
        return str(val.get("nombre") or val.get("organizacion_nombre") or "Plataforma Global").strip()
    s = str(val).strip()
    if not s or "[object" in s.lower() or s.lower() in ("null", "undefined", "none"):
        return "Plataforma Global"
    return s

def _trabajador_auditoria_bg():
    """Hilo dedicado para escritura asíncrona en base de datos (auditoria_sistema + Azure SQL), CSV y logs HTTP sin bloquear peticiones"""
    archivo_existe = os.path.isfile(CSV_AUDITORIA)
    while True:
        try:
            item = _cola_auditoria.get()
            if not item:
                continue
            tipo = item[0]
            if tipo == "csv":
                _, fecha_hora_actual, correo, modulo, operacion, estado, detalles_error, org_id, org_nom_raw, rol_raw = item
                org_nom = _sanitizar_org_nombre(org_nom_raw)
                fecha_dia = fecha_hora_actual[:10] if fecha_hora_actual else datetime.now().strftime("%Y-%m-%d")
                try:
                    if "db" in globals() and db is not None:
                        rol_val = rol_raw
                        org_id_val = org_id
                        if correo and (not rol_val or org_nom == "Plataforma Global"):
                            u_info = db.execute_query(
                                "SELECT u.rol, u.organizacion_id, o.nombre as org_nombre FROM usuarios u LEFT JOIN organizaciones o ON o.id = u.organizacion_id WHERE LOWER(TRIM(u.correo)) = ?",
                                (str(correo).strip().lower(),),
                                fetchone=True
                            )
                            if u_info:
                                rol_val = rol_val or u_info.get("rol")
                                org_id_val = org_id_val or u_info.get("organizacion_id")
                                if org_nom == "Plataforma Global" and u_info.get("org_nombre"):
                                    org_nom = _sanitizar_org_nombre(u_info.get("org_nombre"))
                        if not rol_val:
                            c_low = str(correo or "").lower()
                            if "super" in c_low or "alexander.nino" in c_low:
                                rol_val = "Super Administrador"
                            elif "admin" in c_low:
                                rol_val = "Administrador"
                            elif "mentor" in c_low:
                                rol_val = "Mentor"
                            else:
                                rol_val = "Sistema"
                        db.execute_query(
                            """INSERT INTO auditoria_sistema
                               (fecha_hora, fecha_dia, correo_usuario, usuario_rol, organizacion_id, organizacion_nombre, modulo, operacion, estado, detalles)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                fecha_hora_actual,
                                fecha_dia,
                                str(correo or "Sistema"),
                                str(rol_val or "Sistema"),
                                org_id_val,
                                org_nom,
                                str(modulo or "General"),
                                str(operacion or "Acción"),
                                str(estado or "EXITO"),
                                str(detalles_error or "Ninguno")
                            ),
                            commit=True
                        )
                except Exception:
                    pass
                try:
                    if not archivo_existe:
                        archivo_existe = os.path.isfile(CSV_AUDITORIA)
                    with open(CSV_AUDITORIA, mode='a', newline='', encoding='utf-8') as archivo:
                        escritor = csv.writer(archivo)
                        if not archivo_existe:
                            escritor.writerow(['Fecha_Hora', 'Correo_Usuario', 'Modulo', 'Operacion', 'Estado', 'Detalles_Error'])
                            archivo_existe = True
                        escritor.writerow([fecha_hora_actual, correo, modulo, operacion, estado, detalles_error])
                except Exception:
                    pass
            elif tipo == "http_log":
                _, ip, metodo, ruta, status_code, duracion_ms, user_agent, amenaza = item
                db.execute_query(
                    """INSERT INTO logs_acceso (ip, metodo, ruta, codigo_estado, duracion_ms, user_agent, amenaza_detectada, fecha_hora)
                       VALUES (?, ?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))""",
                    (ip, metodo, ruta, status_code, duracion_ms, user_agent, amenaza),
                    commit=True
                )
        except Exception:
            pass

threading.Thread(target=_trabajador_auditoria_bg, name="auditoria-bg", daemon=True).start()

def registrar_movimiento(
    correo: str,
    modulo: str,
    operacion: str,
    estado: str,
    detalles_error: str = "Ninguno",
    organizacion_id: Optional[int] = None,
    organizacion_nombre: Optional[str] = None,
    usuario_rol: Optional[str] = None
):
    """Encola trazabilidad en auditoria_sistema (SQLite + Azure SQL) y CSV con latencia 0ms"""
    fecha_hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    org_clean = _sanitizar_org_nombre(organizacion_nombre) if organizacion_nombre else None
    _cola_auditoria.put(("csv", fecha_hora_actual, correo, modulo, operacion, estado, detalles_error, organizacion_id, org_clean, usuario_rol))

_sqlite_local = threading.local()

_lock_version = threading.Lock()

VERSION_CAMBIOS: Dict[str, int] = {"usuarios": 0, "organizaciones": 0, "global": 0}

RE_TABLA_ESCRITURA = re.compile(
    r"^\s*(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE
)

TABLAS_SIN_PULSO = {"logs_acceso", "ips_bloqueadas", "incidentes_seguridad", "codigos_2fa_persistentes"}

def notificar_escritura(sql: str):
    """Se invoca tras cada escritura: sube el contador de versión, marca la tabla para réplica a Azure y sincroniza usuarios entre nodos"""
    m = RE_TABLA_ESCRITURA.match(sql or "")
    tabla = m.group(1).lower() if m else None
    if tabla and tabla not in TABLAS_SIN_PULSO:
        with _lock_version:
            VERSION_CAMBIOS["global"] += 1
            if tabla in VERSION_CAMBIOS:
                VERSION_CAMBIOS[tabla] += 1
        try:
            replicador_azure.marcar(tabla)
        except NameError:
            pass
        if tabla == "usuarios":
            try:
                _disparar_sync_usuarios_nube()
            except Exception:
                pass

class ReplicadorAzure:
    """
    Mantiene Azure SQL sincronizado con la base local en segundo plano.
    - Las peticiones de la app nunca esperan a Azure (latencia cero para el usuario).
    - Cada escritura marca su tabla; el hilo envía SOLO las filas que cambiaron (diff por id).
    - Si Azure no está disponible (firewall, pausa, sin internet), reintenta solo y no pierde cambios.
    """
    INTERVALO_RECONCILIACION = 60  # segundos: barrido completo de seguridad

    def __init__(self):
        self.habilitado = os.getenv("AZURE_REPLICA", "true").lower() in ("1", "true", "yes")
        self.conn = None
        self.conectado = False
        self.ultimo_error = ""
        self.ultima_sync: Optional[str] = None
        self.filas_enviadas = 0
        self.pendientes: set = set()
        self.cache: Dict[str, Dict[Any, tuple]] = {}
        self.columnas_azure: Dict[str, List[str]] = {}
        self.identidad_azure: Dict[str, bool] = {}
        self._lock = threading.Lock()
        self._evento = threading.Event()
        self._ultimo_intento_conexion = 0.0
        self._ultima_reconciliacion = 0.0
        self._hilo: Optional[threading.Thread] = None

    # ---------- API pública ----------
    def iniciar(self):
        if not self.habilitado or self._hilo is not None:
            return
        self._hilo = threading.Thread(target=self._bucle, name="replica-azure", daemon=True)
        self._hilo.start()

    def marcar(self, tabla: Optional[str]):
        if not self.habilitado:
            return
        with self._lock:
            if tabla:
                self.pendientes.add(tabla)
            else:
                self.pendientes.add("*")
        self._evento.set()

    def forzar_sincronizacion_total(self):
        self._ultimo_intento_conexion = 0.0
        self.marcar(None)

    def estado(self) -> Dict[str, Any]:
        return {
            "habilitado": self.habilitado,
            "conectado": self.conectado,
            "ultima_sincronizacion": self.ultima_sync,
            "filas_enviadas_total": self.filas_enviadas,
            "tablas_pendientes": sorted(self.pendientes),
            "ultimo_error": self.ultimo_error,
            "servidor": SERVER or "No configurado",
        }

    # ---------- Internos ----------
    def _tablas_locales(self, sl) -> List[str]:
        return [r[0] for r in sl.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('logs_acceso', 'codigos_2fa_persistentes')"
        )]

    def _conectar(self) -> bool:
        if not (SERVER and DATABASE and USERNAME and PASSWORD):
            self.ultimo_error = "Credenciales de Azure SQL incompletas en .env"
            return False
        ahora = time.time()
        if ahora - self._ultimo_intento_conexion < 20:
            return False
        self._ultimo_intento_conexion = ahora
        try:
            self.conn = pyodbc.connect(AZURE_CONN_STR.replace("Connection Timeout=8", "Connection Timeout=30"), timeout=30, autocommit=False)
            self.conectado = True
            self.ultimo_error = ""
            self.cache.clear()
            self.columnas_azure.clear()
            self.identidad_azure.clear()
            db.use_azure = True
            db.last_error = ""
            print(">> [AZURE] Réplica conectada. Sincronizando cambios en tiempo real...")
            return True
        except Exception as e:
            self.conn = None
            self.conectado = False
            db.use_azure = False
            msg = str(e)
            if "is not allowed to access the server" in msg or "not allowed to" in msg:
                ip = re.search(r"IP address '([\d\.]+)'", msg)
                msg = f"Firewall de Azure bloquea la IP {ip.group(1) if ip else 'actual'}. Agrégala en Azure Portal > SQL Server > Redes."
            self.ultimo_error = msg[:300]
            db.last_error = self.ultimo_error
            return False

    @staticmethod
    def _tipo_sql(tipo_sqlite: str, es_id: bool) -> str:
        t = (tipo_sqlite or "").upper()
        if es_id:
            return "INT NOT NULL PRIMARY KEY"
        if "INT" in t:
            return "BIGINT NULL"
        if any(x in t for x in ("REAL", "FLOA", "DOUB")):
            return "FLOAT NULL"
        return "NVARCHAR(MAX) NULL"

    def _asegurar_esquema(self, cur, sl, tabla: str) -> List[str]:
        info = list(sl.execute(f"PRAGMA table_info({tabla})"))
        cols_local = [r[1] for r in info]
        tipos = {r[1]: r[2] for r in info}
        if "id" not in cols_local:
            return []
        if tabla not in self.columnas_azure:
            cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", tabla)
            existentes = [r[0] for r in cur.fetchall()]
            if not existentes:
                defs = ", ".join(f"[{c}] {self._tipo_sql(tipos[c], c == 'id')}" for c in cols_local)
                cur.execute(f"CREATE TABLE [{tabla}] ({defs})")
                existentes = list(cols_local)
            else:
                faltan = [c for c in cols_local if c.lower() not in {e.lower() for e in existentes}]
                for c in faltan:
                    cur.execute(f"ALTER TABLE [{tabla}] ADD [{c}] {self._tipo_sql(tipos[c], False)}")
                    existentes.append(c)
            self.conn.commit()
            cur.execute("SELECT COLUMNPROPERTY(OBJECT_ID(?), 'id', 'IsIdentity')", tabla)
            fila = cur.fetchone()
            self.identidad_azure[tabla] = bool(fila and fila[0] == 1)
            ex_lower = {e.lower() for e in existentes}
            self.columnas_azure[tabla] = [c for c in cols_local if c.lower() in ex_lower]
        return self.columnas_azure[tabla]

    def _cargar_cache_desde_azure(self, cur, tabla: str, cols: List[str]):
        lista = ", ".join(f"[{c}]" for c in cols)
        cur.execute(f"SELECT {lista} FROM [{tabla}]")
        idx = cols.index("id")
        self.cache[tabla] = {fila[idx]: tuple(self._normalizar(v) for v in fila) for fila in cur.fetchall()}

    @staticmethod
    def _normalizar(v):
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v

    def _sincronizar_tabla(self, cur, sl, tabla: str) -> int:
        cols = self._asegurar_esquema(cur, sl, tabla)
        if not cols:
            return 0
        if tabla not in self.cache:
            self._cargar_cache_desde_azure(cur, tabla, cols)
        lista = ", ".join(f"[{c}]" for c in cols)
        idx = cols.index("id")
        locales = {}
        for fila in sl.execute(f"SELECT {', '.join(cols)} FROM {tabla}"):
            t = tuple(self._normalizar(v) for v in fila)
            locales[t[idx]] = t
        remoto = self.cache[tabla]

        nuevos = [v for k, v in locales.items() if k not in remoto]
        cambiados = [v for k, v in locales.items() if k in remoto and remoto[k] != v]
        borrados = [k for k in remoto if k not in locales]
        if not (nuevos or cambiados or borrados):
            return 0

        cur.fast_executemany = False

        if borrados:
            for k in borrados:
                try:
                    cur.execute(f"DELETE FROM [{tabla}] WHERE [id] = ?", (k,))
                except Exception:
                    pass
        if cambiados:
            otras = [c for c in cols if c != "id"]
            if otras:
                set_sql = ", ".join(f"[{c}] = ?" for c in otras)
                filas = [tuple(v[cols.index(c)] for c in otras) + (v[idx],) for v in cambiados]
                try:
                    cur.executemany(f"UPDATE [{tabla}] SET {set_sql} WHERE [id] = ?", filas)
                except Exception:
                    cur.fast_executemany = False
                    for f in filas:
                        try:
                            cur.execute(f"UPDATE [{tabla}] SET {set_sql} WHERE [id] = ?", f)
                        except Exception:
                            pass
        if nuevos:
            marcas = ", ".join("?" for _ in cols)
            identidad = self.identidad_azure.get(tabla)
            if identidad:
                try:
                    cur.execute(f"SET IDENTITY_INSERT [{tabla}] ON")
                except Exception:
                    pass
            try:
                try:
                    cur.executemany(f"INSERT INTO [{tabla}] ({lista}) VALUES ({marcas})", nuevos)
                except Exception:
                    cur.fast_executemany = False
                    for n in nuevos:
                        try:
                            cur.execute(f"INSERT INTO [{tabla}] ({lista}) VALUES ({marcas})", n)
                        except Exception:
                            pass
            finally:
                if identidad:
                    try:
                        cur.execute(f"SET IDENTITY_INSERT [{tabla}] OFF")
                    except Exception:
                        pass
        try:
            self.conn.commit()
        except Exception:
            self.conn.rollback()

        for k in borrados:
            remoto.pop(k, None)
        for v in nuevos + cambiados:
            remoto[v[idx]] = v
        return len(nuevos) + len(cambiados) + len(borrados)

    def _ciclo(self):
        with self._lock:
            pendientes = set(self.pendientes)
            self.pendientes.clear()
        if time.time() - self._ultima_reconciliacion > self.INTERVALO_RECONCILIACION:
            pendientes.add("*")
        if not pendientes:
            return
        if not self.conectado and not self._conectar():
            with self._lock:
                self.pendientes |= pendientes
            return

        sl = sqlite3.connect(SQLITE_DB, timeout=10)
        try:
            todas = self._tablas_locales(sl)
            objetivo = todas if "*" in pendientes else [t for t in todas if t in pendientes]
            total = 0
            for tabla in objetivo:
                cur = None
                try:
                    cur = self.conn.cursor()
                    total += self._sincronizar_tabla(cur, sl, tabla)
                except pyodbc.Error as e:
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    if "08S01" in str(e) or "Communication link" in str(e) or "08001" in str(e):
                        raise
                    self.cache.pop(tabla, None)
                    self.columnas_azure.pop(tabla, None)
                    self.ultimo_error = f"{tabla}: {str(e)[:200]}"
                    print(f">> [AZURE] Aviso en tabla {tabla}: {str(e)[:160]}")
                finally:
                    if cur:
                        try:
                            cur.close()
                        except Exception:
                            pass
            if "*" in pendientes:
                self._ultima_reconciliacion = time.time()
            self.filas_enviadas += total
            self.ultima_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if total:
                print(f">> [AZURE] {total} fila(s) sincronizadas ({', '.join(objetivo[:6])}{'...' if len(objetivo) > 6 else ''})")
        except Exception as e:
            print(f">> [AZURE] Conexión perdida ({str(e)[:120]}). Reintentando en segundo plano...")
            self.conectado = False
            db.use_azure = False
            self.ultimo_error = str(e)[:300]
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            with self._lock:
                self.pendientes |= pendientes
        finally:
            sl.close()

    def hidratar_desde_azure(self) -> int:
        """
        Hidrata la base de datos local SQLite desde Azure SQL al iniciar el servidor.
        Evita que un reinicio en frío en Render borre las organizaciones, usuarios, colecciones
        o avances reales almacenados en Azure SQL.
        """
        if not self.habilitado:
            return 0
        if not self.conectado and not self._conectar():
            return 0
        sl = sqlite3.connect(SQLITE_DB, timeout=15)
        total_hidratadas = 0
        try:
            tablas = self._tablas_locales(sl)
            cur = self.conn.cursor()
            for tabla in tablas:
                try:
                    cols = self._asegurar_esquema(cur, sl, tabla)
                    if not cols or "id" not in cols:
                        continue
                    lista_azure = ", ".join(f"[{c}]" for c in cols)
                    cur.execute(f"SELECT {lista_azure} FROM [{tabla}]")
                    filas_remotas = cur.fetchall()
                    idx_id = cols.index("id")
                    self.cache[tabla] = {
                        f[idx_id]: tuple(self._normalizar(v) for v in f)
                        for f in filas_remotas
                    }
                    if not filas_remotas:
                        continue
                    cols_sql = ", ".join(cols)
                    placeholders = ", ".join("?" for _ in cols)
                    filas_norm = [tuple(self._normalizar(v) for v in f) for f in filas_remotas]
                    sl.execute(f"DELETE FROM {tabla}")
                    sl.executemany(
                        f"INSERT OR REPLACE INTO {tabla} ({cols_sql}) VALUES ({placeholders})",
                        filas_norm
                    )
                    total_hidratadas += len(filas_norm)
                except Exception as e_t:
                    print(f">> [AZURE-HIDRATAR] Aviso en tabla {tabla}: {str(e_t)[:140]}")
            sl.commit()
            if total_hidratadas > 0:
                print(f">> [AZURE-HIDRATAR] {total_hidratadas} registro(s) restaurados desde Azure SQL hacia el motor local.")
        except Exception as e_h:
            print(f">> [AZURE-HIDRATAR] Aviso general: {str(e_h)[:160]}")
        finally:
            try:
                sl.close()
            except Exception:
                pass
        return total_hidratadas

    def _bucle(self):
        self.marcar(None)
        while True:
            self._evento.wait(timeout=5)
            self._evento.clear()
            time.sleep(0.25)  # agrupa ráfagas de escrituras en un solo envío
            try:
                self._ciclo()
            except Exception as e:
                self.ultimo_error = str(e)[:300]

replicador_azure = ReplicadorAzure()

class DatabaseManager:
    def __init__(self):
        self.use_azure = False
        self.last_error = ""
        self._init_sqlite()
        self.test_azure()

    def _init_sqlite(self):
        """Crea tablas locales en SQLite si Azure no está disponible para demo 100% funcional"""
        conn = sqlite3.connect(SQLITE_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                tipo_organizacion TEXT NOT NULL, 
                dominio_permitido TEXT NOT NULL, 
                licencias_asignadas INTEGER DEFAULT 0, 
                max_administradores INTEGER DEFAULT 1,
                max_mentores INTEGER DEFAULT 5,
                fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
                estado_activo INTEGER DEFAULT 1
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organizacion_id INTEGER,
                mentor_id INTEGER NULL,
                nombre TEXT NOT NULL,
                correo TEXT UNIQUE NOT NULL,
                rol TEXT NOT NULL,
                password_hash TEXT,
                FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id),
                FOREIGN KEY (mentor_id) REFERENCES usuarios(id)
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalogo_cursos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_curso TEXT NOT NULL,
                descripcion TEXT
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progreso_cursos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                curso_id INTEGER,
                porcentaje_avance REAL DEFAULT 0.00,
                tiempo_dedicado_minutos INTEGER DEFAULT 0,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (curso_id) REFERENCES catalogo_cursos(id)
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS material_capacitacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                tipo_material TEXT,
                enlace_url TEXT NOT NULL,
                rol_destino TEXT DEFAULT 'Aprendiz',
                fecha_publicacion TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Migración segura: verificar columna rol_destino
        try:
            cursor.execute("ALTER TABLE material_capacitacion ADD COLUMN rol_destino TEXT DEFAULT 'Aprendiz'")
        except Exception:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asignacion_material (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER,
                organizacion_id INTEGER NULL,
                fecha_asignacion TEXT DEFAULT (DATETIME('now', 'localtime')),
                FOREIGN KEY (material_id) REFERENCES material_capacitacion(id),
                FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id)
            );
        """)
        
        # Migraciones seguras para módulos y trazabilidad de colecciones
        try:
            cursor.execute("ALTER TABLE material_capacitacion ADD COLUMN total_modulos INTEGER DEFAULT 3")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE material_capacitacion ADD COLUMN descripcion_modulos TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE asignacion_material ADD COLUMN fecha_asignacion TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE asignacion_material ADD COLUMN destinatario_tipo TEXT DEFAULT 'Institución'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE asignacion_material ADD COLUMN destinatario_id INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE asignacion_material ADD COLUMN asignado_por_id INTEGER DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE asignacion_material ADD COLUMN asignado_por_rol TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE progreso_cursos ADD COLUMN modulos_completados INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE progreso_cursos ADD COLUMN estado TEXT DEFAULT 'No Iniciado'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE progreso_cursos ADD COLUMN fecha_actualizacion TEXT DEFAULT NULL")
        except Exception:
            pass

        # Migraciones seguras para Colorimetría Institucional
        try:
            cursor.execute("ALTER TABLE organizaciones ADD COLUMN color_primario TEXT DEFAULT '#0a192f'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE organizaciones ADD COLUMN color_secundario TEXT DEFAULT '#0f273f'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE organizaciones ADD COLUMN color_acento TEXT DEFAULT '#06b6d4'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE organizaciones ADD COLUMN color_personalizado INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE organizaciones ADD COLUMN logo_url TEXT DEFAULT NULL")
        except Exception:
            pass

        # Migración para control manual de porcentaje de avance en organizaciones
        try:
            cursor.execute("ALTER TABLE organizaciones ADD COLUMN porcentaje_avance_manual REAL DEFAULT NULL")
        except Exception:
            pass

        # Migración para foto de perfil de usuario
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT DEFAULT NULL")
        except Exception:
            pass

        # Tabla de Papelera y Respaldo de Integrantes Eliminados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios_eliminados_papelera (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                organizacion_id INTEGER NULL,
                organizacion_nombre TEXT NULL,
                mentor_id INTEGER NULL,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                rol TEXT NOT NULL,
                password_hash TEXT NULL,
                foto_perfil TEXT NULL,
                datos_progreso_json TEXT NULL,
                fecha_eliminacion TEXT DEFAULT (DATETIME('now', 'localtime')),
                eliminado_por TEXT DEFAULT 'Administrador'
            );
        """)

        # Tabla de Temas Personalizados Guardados por Organización (Sin Límites)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS temas_personalizados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organizacion_id INTEGER NOT NULL,
                nombre_tema TEXT NOT NULL,
                color_primario TEXT NOT NULL,
                color_secundario TEXT NOT NULL,
                color_acento TEXT NOT NULL,
                fecha_creacion TEXT DEFAULT (DATETIME('now', 'localtime')),
                FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id)
            );
        """)

        # Tablas de Seguridad Militar, Firewall WAF y Monitoreo de Acceso
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ips_bloqueadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL UNIQUE,
                motivo TEXT NOT NULL,
                intentos_maliciosos INTEGER DEFAULT 1,
                bloqueo_activo INTEGER DEFAULT 1,
                fecha_bloqueo TEXT DEFAULT (DATETIME('now', 'localtime')),
                expira_en TEXT NULL,
                bloqueado_por TEXT DEFAULT 'Firewall_WAF'
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidentes_seguridad (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                tipo_amenaza TEXT NOT NULL,
                nivel_severidad TEXT DEFAULT 'CRITICA',
                detalles TEXT NOT NULL,
                payload_detectado TEXT NULL,
                ruta_afectada TEXT NULL,
                metodo_http TEXT NULL,
                correo_relacionado TEXT NULL,
                alerta_enviada INTEGER DEFAULT 0,
                fecha_hora TEXT DEFAULT (DATETIME('now', 'localtime'))
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs_acceso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                metodo TEXT NOT NULL,
                ruta TEXT NOT NULL,
                codigo_estado INTEGER DEFAULT 200,
                duracion_ms REAL DEFAULT 0.0,
                user_agent TEXT NULL,
                amenaza_detectada INTEGER DEFAULT 0,
                fecha_hora TEXT DEFAULT (DATETIME('now', 'localtime'))
            );
        """)

        # Migraciones seguras para Personalización de Espacio, Racha y Tiempos
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN tema_decorativo TEXT DEFAULT 'estandar'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN fondo_personalizado TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN racha_semanas INTEGER DEFAULT 5")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN ultima_semana_racha TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN minutos_dedicados_totales INTEGER DEFAULT 180")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN colores_personalizados TEXT DEFAULT NULL")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN disenos_personalizados_json TEXT DEFAULT NULL")
        except Exception:
            pass

        # Tabla de Quizzes y Evaluaciones creados por Mentores
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quizzes_evaluaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mentor_id INTEGER NOT NULL,
                organizacion_id INTEGER NULL,
                titulo TEXT NOT NULL,
                tipo TEXT DEFAULT 'Quiz',
                descripcion TEXT,
                duracion_minutos INTEGER DEFAULT 15,
                preguntas_json TEXT NOT NULL,
                fecha_creacion TEXT DEFAULT (DATETIME('now', 'localtime')),
                activo INTEGER DEFAULT 1,
                FOREIGN KEY (mentor_id) REFERENCES usuarios(id)
            );
        """)

        # Tabla de Progreso / Respuestas de Aprendices en Quizzes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progreso_quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                aprendiz_id INTEGER NOT NULL,
                calificacion REAL DEFAULT 0,
                aprobado INTEGER DEFAULT 0,
                tiempo_segundos INTEGER DEFAULT 0,
                respuestas_json TEXT,
                fecha_completado TEXT DEFAULT (DATETIME('now', 'localtime')),
                FOREIGN KEY (quiz_id) REFERENCES quizzes_evaluaciones(id),
                FOREIGN KEY (aprendiz_id) REFERENCES usuarios(id)
            );
        """)

        # Tabla de Registro de Actividades y Tiempos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registro_actividades_tiempo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                rol TEXT NOT NULL,
                tipo_actividad TEXT NOT NULL,
                minutos INTEGER DEFAULT 15,
                fecha TEXT DEFAULT (DATE('now', 'localtime')),
                fecha_hora TEXT DEFAULT (DATETIME('now', 'localtime')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            );
        """)

        # Tabla de Respaldos del Sistema (Metadatos en Base de Datos sin depender de archivos locales)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS respaldos_sistema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archivo TEXT NOT NULL,
                tipo TEXT DEFAULT 'excel',
                organizacion_id INTEGER NULL,
                fecha TEXT DEFAULT (DATETIME('now', 'localtime')),
                mes TEXT NOT NULL,
                tamano TEXT NOT NULL,
                bytes INTEGER DEFAULT 0
            );
        """)
        
        # Tabla persistente de Auditoría del Sistema (sincronizada con Azure SQL y con soporte de Backup)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_sistema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_hora TEXT DEFAULT (DATETIME('now', 'localtime')),
                fecha_dia TEXT DEFAULT (DATE('now', 'localtime')),
                correo_usuario TEXT NOT NULL,
                usuario_rol TEXT DEFAULT 'Sistema',
                organizacion_id INTEGER NULL,
                organizacion_nombre TEXT DEFAULT 'Plataforma Global',
                modulo TEXT NOT NULL,
                operacion TEXT NOT NULL,
                estado TEXT DEFAULT 'EXITO',
                detalles TEXT DEFAULT 'Ninguno'
            );
        """)

        # Limpiar cualquier rastro de '[object Object]' en tablas existentes
        try:
            cursor.execute("UPDATE auditoria_sistema SET organizacion_nombre = 'Plataforma Global' WHERE organizacion_nombre LIKE '%[object%' OR organizacion_nombre IS NULL OR TRIM(organizacion_nombre) = ''")
            cursor.execute("UPDATE historial_nuevos_integrantes SET organizacion_nombre = 'Plataforma Global' WHERE organizacion_nombre LIKE '%[object%'")
        except Exception:
            pass

        # Garantizar ÚNICAMENTE la cuenta blindada del Superadministrador (sin organizaciones ni usuarios de relleno que se reinicien solos)
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO usuarios (id, organizacion_id, mentor_id, nombre, correo, rol, password_hash)
                VALUES (1, NULL, NULL, 'Diego Alexander Niño Niño', 'alexander.nino.583@gmail.com', 'Super Administrador', '$2b$12$Nh5npfN6/cCS8MBclXRVNueVPr.MzcVGn4hq58M4ZfDNzndP3MzOu')
            """)
            cursor.execute("""
                UPDATE usuarios
                SET rol = 'Super Administrador', organizacion_id = NULL, mentor_id = NULL
                WHERE LOWER(TRIM(correo)) = 'alexander.nino.583@gmail.com'
            """)
            conn.commit()
        except Exception as e_super:
            print(f">> [SUPERADMIN INIT] Aviso: {e_super}")

        # Asegurar enlaces oficiales 100% válidos (sin 404) en el catálogo si existen colecciones
        try:
            reemplazos_urls = [
                ("https://learn.microsoft.com/es-es/training/modules/hybrid-learning-framework/", "https://learn.microsoft.com/es-es/training/educator-center/"),
                ("https://learn.microsoft.com/es-es/training/paths/ai-for-educators/", "https://learn.microsoft.com/es-es/training/paths/get-started-with-artificial-intelligence-on-azure/"),
                ("https://learn.microsoft.com/es-es/training/paths/responsible-ai-principles/", "https://learn.microsoft.com/es-es/training/paths/get-started-with-artificial-intelligence-on-azure/"),
                ("https://learn.microsoft.com/es-es/training/paths/data-analytics-microsoft/", "https://learn.microsoft.com/es-es/training/paths/prepare-data-for-analysis-power-bi/")
            ]
            for url_rota, url_valida in reemplazos_urls:
                cursor.execute("UPDATE material_capacitacion SET enlace_url = ? WHERE enlace_url = ?", (url_valida, url_rota))
            cursor.execute("UPDATE material_capacitacion SET total_modulos = 3 WHERE total_modulos IS NULL OR total_modulos = 0")
            conn.commit()
        except Exception as e_urls:
            print(f">> [URLS CATALOGO] Aviso: {e_urls}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_nuevos_integrantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NULL,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                rol TEXT NOT NULL,
                organizacion_id INTEGER NULL,
                organizacion_nombre TEXT NULL,
                origen_registro TEXT DEFAULT 'Registro Manual',
                fecha_registro TEXT DEFAULT (DATETIME('now', 'localtime')),
                fecha_dia TEXT DEFAULT (DATE('now', 'localtime'))
            );
        """)

        # Sembrar Quizzes de demostración para Mentores si está vacío
        cursor.execute("SELECT COUNT(*) FROM quizzes_evaluaciones")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT id, organizacion_id FROM usuarios WHERE rol = 'Mentor' LIMIT 1")
            mentor_row = cursor.fetchone()
            men_id = mentor_row[0] if mentor_row else 3
            men_org = mentor_row[1] if mentor_row else 1

            q1_preguntas = json.dumps([
                {
                    "pregunta": "¿Qué modelo de servicio en la nube ofrece el mayor nivel de control sobre los recursos de hardware y el sistema operativo?",
                    "opciones": ["SaaS (Software como Servicio)", "IaaS (Infraestructura como Servicio)", "PaaS (Plataforma como Servicio)", "Serverless"],
                    "respuesta_correcta": "B",
                    "explicacion": "IaaS proporciona el nivel más cercano al hardware físico tradicional, permitiendo configurar el sistema operativo y la red."
                },
                {
                    "pregunta": "¿Cuál es la principal ventaja de la escalabilidad horizontal en entornos cloud?",
                    "opciones": ["Aumentar la RAM de un solo servidor", "Agregar más instancias o nodos para distribuir la carga de trabajo", "Reducir la velocidad del procesador", "Eliminar copias de seguridad"],
                    "respuesta_correcta": "B",
                    "explicacion": "La escalabilidad horizontal consiste en añadir más máquinas o contenedores para balancear la carga de usuarios."
                },
                {
                    "pregunta": "¿Qué principio de seguridad establece que los usuarios solo deben tener los permisos mínimos indispensables para sus tareas?",
                    "opciones": ["Principio de Máxima Confianza", "Principio de Menor Privilegio (PoLP)", "Seguridad Perimetral Exclusiva", "Acceso Compartido Global"],
                    "respuesta_correcta": "B",
                    "explicacion": "El Principio de Menor Privilegio garantiza que cada identidad solo acceda a los recursos estrictamente necesarios."
                }
            ], ensure_ascii=False)

            q2_preguntas = json.dumps([
                {
                    "pregunta": "¿Cuál de los siguientes es uno de los seis principios fundamentales de IA Responsable de Microsoft?",
                    "opciones": ["Monopolio Tecnológico", "Equidad e Imparcialidad (Fairness)", "Opacidad de Algoritmos", "Ejecución sin Auditoría"],
                    "respuesta_correcta": "B",
                    "explicacion": "La equidad e imparcialidad busca que los sistemas de IA traten a todas las personas de manera justa y sin sesgos discriminatorios."
                },
                {
                    "pregunta": "¿Qué pilar garantiza que los usuarios entiendan cómo los modelos de IA toman sus decisiones?",
                    "opciones": ["Transparencia y Explicabilidad", "Aislamiento de Código", "Cifrado Irreversible", "Velocidad de Cómputo"],
                    "respuesta_correcta": "A",
                    "explicacion": "La transparencia y explicabilidad permite a los usuarios auditar y comprender el razonamiento de las predicciones."
                }
            ], ensure_ascii=False)

            cursor.execute("""
                INSERT INTO quizzes_evaluaciones (mentor_id, organizacion_id, titulo, tipo, descripcion, duracion_minutos, preguntas_json)
                VALUES 
                (?, ?, 'Quiz 1: Fundamentos de Cloud Computing y Azure', 'Quiz', 'Validación de conceptos clave de infraestructura y modelos de servicio', 15, ?),
                (?, ?, 'Evaluación 2: IA Responsable y Gobernanza Ética', 'Evaluación', 'Principios éticos de Microsoft y confiabilidad en inteligencia artificial', 20, ?)
            """, (men_id, men_org, q1_preguntas, men_id, men_org, q2_preguntas))

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS codigos_2fa_persistentes (
                correo TEXT NOT NULL,
                codigo TEXT NOT NULL,
                expira_ts REAL NOT NULL
            );
        """)

        # Índices de alta velocidad para consultas instantáneas (<0.2ms)
        indices_sql = [
            "CREATE INDEX IF NOT EXISTS idx_usuarios_correo_lower ON usuarios(LOWER(correo));",
            "CREATE INDEX IF NOT EXISTS idx_usuarios_org_rol ON usuarios(organizacion_id, rol);",
            "CREATE INDEX IF NOT EXISTS idx_usuarios_mentor ON usuarios(mentor_id);",
            "CREATE INDEX IF NOT EXISTS idx_progreso_usr_curso ON progreso_cursos(usuario_id, curso_id);",
            "CREATE INDEX IF NOT EXISTS idx_asignacion_org_mat ON asignacion_material(organizacion_id, material_id);",
            "CREATE INDEX IF NOT EXISTS idx_progreso_quiz_apr ON progreso_quizzes(aprendiz_id, quiz_id);",
            "CREATE INDEX IF NOT EXISTS idx_logs_acceso_fecha ON logs_acceso(fecha_hora DESC);",
            "CREATE INDEX IF NOT EXISTS idx_historial_int_org ON historial_nuevos_integrantes(organizacion_id, fecha_dia);",
            "CREATE INDEX IF NOT EXISTS idx_codigos_2fa_correo ON codigos_2fa_persistentes(correo);"
        ]
        for idx_q in indices_sql:
            try:
                cursor.execute(idx_q)
            except Exception:
                pass

        conn.commit()
        conn.close()

    def test_azure(self):
        """Prueba conexión a Azure SQL o prioriza Modo Ultra-Rápido Local para máxima velocidad"""
        modo_alta_vel = os.getenv("MODO_ALTA_VELOCIDAD", "true").lower() in ("1", "true", "yes")
        if modo_alta_vel:
            self.use_azure = False
            self.last_error = "Modo Ultra-Rápido Local activo (Cero latencia / 0 tráfico externo)"
            print(">> [BD] Modo Ultra-Rápido Local SQLite ACTIVO (Respuestas instantáneas <1ms, 0 tráfico externo).")
            return False

        return self.test_azure_force()

    def test_azure_force(self):
        """Fuerza conexión a Azure SQL y asegura tablas requeridas"""
        if not SERVER or not DATABASE or not USERNAME or not PASSWORD:
            self.use_azure = False
            self.last_error = "Credenciales de Azure SQL incompletas en .env"
            return False
            
        try:
            conn = pyodbc.connect(AZURE_CONN_STR)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            # Asegurar tabla historial_nuevos_integrantes en Azure SQL
            try:
                cursor.execute("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='historial_nuevos_integrantes' AND xtype='U')
                    CREATE TABLE historial_nuevos_integrantes (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        usuario_id INT NULL,
                        nombre NVARCHAR(255) NOT NULL,
                        correo NVARCHAR(255) NOT NULL,
                        rol NVARCHAR(100) NOT NULL,
                        organizacion_id INT NULL,
                        organizacion_nombre NVARCHAR(255) NULL,
                        origen_registro NVARCHAR(100) DEFAULT 'Registro Manual',
                        fecha_registro NVARCHAR(50) DEFAULT CONVERT(VARCHAR, GETDATE(), 120),
                        fecha_dia NVARCHAR(50) DEFAULT CONVERT(VARCHAR, GETDATE(), 23)
                    );
                """)
                conn.commit()
            except Exception:
                pass
                
            conn.close()
            self.use_azure = True
            self.last_error = ""
            print(">> [BD] Conectado exitosamente a Azure SQL Database.")
            return True
        except Exception as e:
            self.use_azure = False
            self.last_error = str(e)
            print(f">> [BD] Azure SQL no disponible ({e}). Operando en modo Local SQLite resiliente.")
            return False

    def _conexion_local(self):
        """Conexión SQLite persistente por hilo (WAL + Memory-Mapped I/O) para respuestas sub-milisegundo"""
        conn = getattr(_sqlite_local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(SQLITE_DB, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA temp_store=MEMORY;")
                conn.execute("PRAGMA cache_size=-32000;")
                conn.execute("PRAGMA mmap_size=268435456;")
            except Exception:
                pass
            _sqlite_local.conn = conn
        return conn

    def execute_query(self, query: str, params: tuple = (), fetchone=False, fetchall=False, commit=False, return_id=False):
        """Ejecuta SIEMPRE sobre SQLite local (instantáneo). Cada escritura se replica a Azure SQL en segundo plano."""
        sqlite_query = query.replace("[dbo].", "").replace("[", "").replace("]", "")
        sqlite_query = sqlite_query.replace("OUTPUT INSERTED.id", "")

        conn = self._conexion_local()
        cursor = conn.cursor()
        try:
            cursor.execute(sqlite_query, params)
            result = None
            if return_id:
                conn.commit()
                result = cursor.lastrowid
            elif fetchone:
                row = cursor.fetchone()
                result = dict(row) if row else None
            elif fetchall:
                rows = cursor.fetchall()
                result = [dict(r) for r in rows]
            elif commit:
                conn.commit()
                result = cursor.lastrowid or cursor.rowcount
            else:
                # Escrituras sin flag explícito: asegurar persistencia
                if conn.in_transaction:
                    conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cursor.close()

        if commit or return_id:
            notificar_escritura(sqlite_query)
        return result

    def optimize(self) -> bool:
        """Ejecuta mantenimiento y compactación sobre el motor de base de datos activo"""
        try:
            conn = self._conexion_local()
            conn.execute("VACUUM;")
            conn.execute("PRAGMA optimize;")
            return True
        except Exception:
            return False

    def get_storage_size_label(self) -> str:
        """Retorna el tamaño estimado del almacenamiento de base de datos sin acoplar endpoints a archivos"""
        try:
            r = self.execute_query(
                "SELECT (page_count * page_size) as total_bytes FROM pragma_page_count(), pragma_page_size()",
                fetchone=True
            )
            b = int((r or {}).get("total_bytes") or 0)
            return f"{round(b / 1024, 1)} KB" if b < 1024 * 1024 else f"{round(b / (1024 * 1024), 2)} MB"
        except Exception:
            return "Activo en Motor Principal"

db = DatabaseManager()
try:
    replicador_azure.hidratar_desde_azure()
    # Garantizar siempre al Superadministrador sin organización fija tras hidratar
    db.execute_query(
        """INSERT OR IGNORE INTO usuarios (id, organizacion_id, mentor_id, nombre, correo, rol, password_hash)
           VALUES (1, NULL, NULL, 'Diego Alexander Niño Niño', 'alexander.nino.583@gmail.com', 'Super Administrador', '$2b$12$Nh5npfN6/cCS8MBclXRVNueVPr.MzcVGn4hq58M4ZfDNzndP3MzOu')""",
        commit=True
    )
    db.execute_query(
        "UPDATE usuarios SET rol = 'Super Administrador', organizacion_id = NULL, mentor_id = NULL WHERE LOWER(TRIM(correo)) = 'alexander.nino.583@gmail.com'",
        commit=True
    )
except Exception as _e_hid:
    print(f">> [INIT] Aviso hidratando desde Azure SQL: {_e_hid}")
replicador_azure.iniciar()

def registrar_en_historial_integrantes(
    nombre: str, 
    correo: str, 
    rol: str, 
    organizacion_id: Optional[int] = None, 
    organizacion_nombre: Optional[str] = None, 
    origen: str = "Registro Manual", 
    usuario_id: Optional[int] = None
):
    """Registra a un nuevo integrante con su fecha y día para el historial cronológico y El Celador"""
    ahora_dt = datetime.now()
    fecha_actual = ahora_dt.strftime("%Y-%m-%d %H:%M:%S")
    dia_actual = ahora_dt.strftime("%Y-%m-%d")
    
    org_nom = organizacion_nombre
    if not org_nom and organizacion_id:
        org = db.execute_query("SELECT nombre FROM organizaciones WHERE id = ?", (organizacion_id,), fetchone=True)
        org_nom = org["nombre"] if org else "Institución General"
    elif not org_nom:
        org_nom = "Institución General"

    db.execute_query("""
        INSERT INTO historial_nuevos_integrantes 
        (usuario_id, nombre, correo, rol, organizacion_id, organizacion_nombre, origen_registro, fecha_registro, fecha_dia)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario_id, nombre.strip(), correo.strip().lower(), rol, organizacion_id, org_nom, origen, fecha_actual, dia_actual), commit=True)

def generar_html_correo_2fa(nombre: str, codigo: str, rol: str = "Integrante Institucional", correo: str = "", institucion_nombre: str = "Corporación Universitaria Minuto de Dios", organizacion_id: Optional[int] = None) -> str:
    """Plantilla ejecutiva de alta gama para el código de verificación 2FA de 6 dígitos que incluye bienvenida por nombre, cargo (rol), ID de institución e institución"""
    nombre_seguro = html.escape((nombre or "Usuario").strip())
    rol_seguro = html.escape((rol or "Integrante Institucional").strip())
    correo_seguro = html.escape((correo or "").strip())
    institucion_segura = html.escape((institucion_nombre or "Corporación Universitaria Minuto de Dios").strip())
    org_id_txt = f" (ID: {organizacion_id})" if organizacion_id else ""
    codigo_limpio = str(codigo).strip()
    fecha_str = datetime.now().strftime("%d/%m/%Y · %H:%M:%S")

    # Renderizar cada dígito en su propia celda de cristal/ejecutiva para máxima elegancia y legibilidad
    celdas_digitos = "".join([
        f'<td align="center" valign="middle" style="padding: 0 4px;">'
        f'<div style="width: 46px; height: 58px; line-height: 58px; background: #0f172a; color: #38bdf8; '
        f'font-family: \'Courier New\', Consolas, monospace; font-size: 30px; font-weight: 800; '
        f'border-radius: 12px; border: 1.5px solid #0284c7; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.18); '
        f'text-align: center;">{ html.escape(d) }</div></td>'
        for d in codigo_limpio
    ])

    bloque_cuenta = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px; margin-bottom: 24px; overflow: hidden;">
      <tr>
        <td style="padding: 12px 18px; border-bottom: 1px solid #e2e8f0; background-color: #f1f5f9;">
          <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #475569;">🏛️ Institución</span>
          <div style="font-size: 14px; font-weight: 800; color: #0f172a; margin-top: 2px;">{institucion_segura}{org_id_txt}</div>
        </td>
      </tr>
      <tr>
        <td style="padding: 12px 18px; border-bottom: 1px solid #e2e8f0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td>
                <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #64748b;">👤 Integrante &amp; Cargo</span>
                <div style="font-size: 14px; font-weight: 700; color: #0f172a; margin-top: 2px;">{nombre_seguro}</div>
              </td>
              <td align="right">
                <span style="display: inline-block; background-color: #0284c7; color: #ffffff; font-size: 11px; font-weight: 800; padding: 4px 12px; border-radius: 999px; letter-spacing: 0.5px; text-transform: uppercase;">
                  {rol_seguro}
                </span>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding: 10px 18px; border-bottom: 1px solid #e2e8f0; font-size: 12px; color: #334155;">
          <strong>Correo registrado:</strong> <span style="font-family: monospace; color: #0369a1;">{correo_seguro}</span>
        </td>
      </tr>
      <tr>
        <td style="padding: 9px 18px; font-size: 11px; color: #64748b; background-color: #f8fafc;">
          🕒 Solicitud registrada el <strong>{fecha_str}</strong> · Conexión Segura TLS/SSL
        </td>
      </tr>
    </table>
    """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Código de Seguridad 2FA - Consultoría EdTech</title>
</head>
<body style="margin: 0; padding: 0; background-color: #eef2f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; -webkit-font-smoothing: antialiased;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #eef2f6; padding: 32px 12px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 560px; background-color: #ffffff; border-radius: 20px; overflow: hidden; border: 1px solid #cbd5e1; box-shadow: 0 14px 36px rgba(15, 23, 42, 0.10);">
          
          <!-- Franja Superior Luminosa -->
          <tr>
            <td style="height: 5px; background: linear-gradient(90deg, #0284c7 0%, #06b6d4 50%, #3b82f6 100%); font-size: 0; line-height: 0;">&nbsp;</td>
          </tr>

          <!-- Cabecera Institucional Ejecutiva -->
          <tr>
            <td style="background: linear-gradient(135deg, #071324 0%, #0f2744 100%); padding: 30px 28px; text-align: center;">
              <div style="display: inline-block; background-color: rgba(56, 189, 248, 0.14); border: 1px solid rgba(56, 189, 248, 0.35); padding: 5px 14px; border-radius: 999px; font-size: 11px; font-weight: 800; color: #38bdf8; letter-spacing: 1.2px; text-transform: uppercase; margin-bottom: 12px;">
                🛡️ ESCUDO DE IDENTIDAD 2FA
              </div>
              <h1 style="color: #ffffff; margin: 0; font-size: 23px; font-weight: 800; letter-spacing: -0.4px;">{institucion_segura}</h1>
              <p style="color: #94a3b8; margin: 6px 0 0 0; font-size: 13px; font-weight: 500;">Plataforma Institucional Consultoría EdTech</p>
            </td>
          </tr>

          <!-- Cuerpo Principal -->
          <tr>
            <td style="padding: 32px 30px 26px 30px;">
              <p style="margin: 0 0 10px 0; font-size: 17px; color: #0f172a; line-height: 1.5;">
                ¡Hola, <strong>{nombre_seguro}</strong>! 👋 Te damos la más cordial bienvenida.
              </p>
              <p style="margin: 0 0 20px 0; font-size: 14px; color: #475569; line-height: 1.6;">
                Se ha iniciado el proceso de ingreso seguro a tu cuenta institucional en el cargo de <strong>{rol_seguro}</strong>. Utiliza el siguiente <strong>código único de verificación de 6 dígitos</strong> para autorizar tu acceso:
              </p>

              {bloque_cuenta}

              <!-- Tarjeta Central del Código de 6 Dígitos -->
              <div style="background: linear-gradient(180deg, #f0f9ff 0%, #e0f2fe 100%); border: 1.5px solid #bae6fd; border-radius: 16px; padding: 24px 14px; text-align: center; margin-bottom: 24px;">
                <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; color: #0369a1; margin-bottom: 14px;">
                  CÓDIGO DE AUTORIZACIÓN DE ACCESO
                </div>
                <table align="center" cellpadding="0" cellspacing="0" border="0" style="margin: 0 auto;" title="Código de acceso: {codigo_limpio}">
                  <tr>
                    {celdas_digitos}
                  </tr>
                </table>
                <div style="font-size: 0; line-height: 0; color: transparent; height: 0; overflow: hidden;">{codigo_limpio}</div>
                <div style="margin-top: 14px; font-size: 12px; color: #0284c7; font-weight: 600;">
                  ⏳ Válido durante los próximos <strong>30 minutos</strong>
                </div>
              </div>

              <!-- Aviso de Protección -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #fffbeb; border-left: 4px solid #f59e0b; border-radius: 8px; margin-bottom: 8px;">
                <tr>
                  <td style="padding: 12px 14px; font-size: 12px; color: #92400e; line-height: 1.45;">
                    <strong>🔒 Recomendación de Seguridad:</strong> Este código es personal e intransferible. La administración de <strong>{institucion_segura}</strong> nunca te solicitará esta clave por mensaje o llamada.
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Pie de Página Corporativo -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 18px 28px; text-align: center;">
              <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 700; color: #334155;">
                {institucion_segura} · Consultoría EdTech
              </p>
              <p style="margin: 0; font-size: 11px; color: #94a3b8;">
                Sistema de Seguridad Perimetral, Cifrado de Identidad y Analítica Académica
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

def generar_html_correo_bienvenida(
    nombre: str,
    rol: str,
    correo: str,
    institucion_nombre: str = "Corporación Universitaria Minuto de Dios",
    password_inicial: str = "123456"
) -> str:
    """Genera plantilla de correo de bienvenida ejecutiva con Institución, Nombre, Cargo (Administrador/Mentor/Aprendiz) y credenciales"""
    fecha_actual = datetime.now().strftime("%d/%m/%Y · %H:%M")
    rol_limpio = (rol or "Aprendiz").strip()
    institucion_limpia = (institucion_nombre or "Corporación Universitaria Minuto de Dios").strip()
    color_rol_bg = "#ecfeff"
    color_rol_txt = "#0e7490"
    color_rol_borde = "#a5f3fc"
    icono_rol = "🎓"
    if "admin" in rol_limpio.lower():
        color_rol_bg = "#f0f9ff"
        color_rol_txt = "#0369a1"
        color_rol_borde = "#bae6fd"
        icono_rol = "🏛️"
    elif "mentor" in rol_limpio.lower() or "docente" in rol_limpio.lower():
        color_rol_bg = "#f5f3ff"
        color_rol_txt = "#6d28d9"
        color_rol_borde = "#ddd6fe"
        icono_rol = "👨‍🏫"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bienvenido a Consultoría EdTech</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; color: #0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f1f5f9; padding: 36px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 580px; background-color: #ffffff; border-radius: 20px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);">
          
          <!-- FRANJA SUPERIOR DE ACENTO -->
          <tr>
            <td style="height: 6px; background: linear-gradient(90deg, #06b6d4 0%, #0284c7 50%, #1e3a8a 100%);"></td>
          </tr>

          <!-- CABECERA CORPORATIVA -->
          <tr>
            <td style="background: linear-gradient(135deg, #091b2c 0%, #0f273f 100%); padding: 34px 32px; text-align: center;">
              <div style="display: inline-block; padding: 6px 16px; border-radius: 999px; background-color: rgba(56, 189, 248, 0.14); border: 1px solid rgba(56, 189, 248, 0.35); margin-bottom: 14px;">
                <span style="color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase;">🎉 CREDENCIAL OFICIAL DE INCORPORACIÓN</span>
              </div>
              <h1 style="color: #ffffff; margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">Bienvenido a Consultoría EdTech</h1>
              <p style="color: #cbd5e1; margin: 8px 0 0 0; font-size: 13px; font-weight: 600;">
                🏛️ {institucion_limpia}
              </p>
            </td>
          </tr>

          <!-- CUERPO PRINCIPAL -->
          <tr>
            <td style="padding: 36px 32px 28px 32px;">
              <p style="margin: 0 0 12px 0; font-size: 16px; color: #0f172a;">
                Hola <strong style="color: #091b2c;">{nombre}</strong>,
              </p>
              <p style="margin: 0 0 24px 0; font-size: 14px; color: #475569; line-height: 1.65;">
                Te damos una cordial bienvenida a <strong>Consultoría EdTech</strong>. Tu cuenta institucional ha sido dada de alta exitosamente dentro del convenio de <strong>{institucion_limpia}</strong> con el cargo oficial de <strong>{rol_limpio}</strong>.
              </p>

              <!-- TARJETA DE IDENTIDAD INSTITUCIONAL Y CARGO -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: linear-gradient(180deg, #f8fafc 0%, #f0f9ff 100%); border: 1.5px solid #bae6fd; border-radius: 16px; margin-bottom: 24px;">
                <tr>
                  <td style="padding: 22px 24px;">
                    <div style="font-size: 11px; font-weight: 800; color: #0369a1; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 14px;">
                      📋 FICHA OFICIAL DEL INTEGRANTE
                    </div>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="font-size: 13px; color: #334155;">
                      <tr>
                        <td style="padding: 7px 0; color: #64748b; width: 42%;"><strong>Institución:</strong></td>
                        <td style="padding: 7px 0; font-weight: 800; color: #0f172a;">🏛️ {institucion_limpia}</td>
                      </tr>
                      <tr>
                        <td style="padding: 7px 0; color: #64748b; border-top: 1px solid #e2e8f0;"><strong>Nombre Completo:</strong></td>
                        <td style="padding: 7px 0; font-weight: 700; color: #0f172a; border-top: 1px solid #e2e8f0;">👤 {nombre}</td>
                      </tr>
                      <tr>
                        <td style="padding: 8px 0; color: #64748b; border-top: 1px solid #e2e8f0;"><strong>Cargo / Rol Asignado:</strong></td>
                        <td style="padding: 8px 0; border-top: 1px solid #e2e8f0;">
                          <span style="display: inline-block; padding: 4px 12px; border-radius: 999px; background-color: {color_rol_bg}; color: {color_rol_txt}; border: 1px solid {color_rol_borde}; font-weight: 800; font-size: 12px;">
                            {icono_rol} {rol_limpio}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding: 7px 0; color: #64748b; border-top: 1px solid #e2e8f0;"><strong>Correo Registrado:</strong></td>
                        <td style="padding: 7px 0; font-family: monospace; font-weight: 700; color: #0369a1; border-top: 1px solid #e2e8f0;">{correo}</td>
                      </tr>
                      <tr>
                        <td style="padding: 7px 0; color: #64748b; border-top: 1px solid #e2e8f0;"><strong>Contraseña Inicial:</strong></td>
                        <td style="padding: 7px 0; font-family: monospace; font-weight: 800; color: #0f172a; border-top: 1px solid #e2e8f0;">{password_inicial}</td>
                      </tr>
                      <tr>
                        <td style="padding: 7px 0; color: #64748b; border-top: 1px solid #e2e8f0;"><strong>Fecha de Alta:</strong></td>
                        <td style="padding: 7px 0; color: #475569; border-top: 1px solid #e2e8f0;">{fecha_actual}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- AVISO DE SEGURIDAD 2FA -->
              <div style="background-color: #f8fafc; border-left: 4px solid #0284c7; border-radius: 8px; padding: 14px 16px;">
                <p style="margin: 0; font-size: 12px; color: #334155; line-height: 1.5;">
                  🔒 <strong>Seguridad 2FA Activada:</strong> Cada vez que inicies sesión en la plataforma con tu correo y contraseña, recibirás automáticamente en este correo un <strong>código de seguridad de 6 dígitos</strong> para verificar tu identidad.
                </p>
              </div>
            </td>
          </tr>

          <!-- PIE DE PÁGINA -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 32px; text-align: center;">
              <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 700; color: #334155;">
                Consultoría EdTech · {institucion_limpia}
              </p>
              <p style="margin: 0; font-size: 11px; color: #94a3b8;">
                Notificación oficial de incorporación ({CORREO_APP or 'alexander.nino.583@gmail.com'}).
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

def generar_html_correo_recuperacion(nombre: str, codigo: str) -> str:
    """Genera plantilla de correo corporativa para recuperación de contraseña"""
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b;">
      <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 520px; background-color: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <tr>
          <td style="background-color: #091b2c; padding: 28px 24px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 800; letter-spacing: -0.5px;">Consultoría EdTech</h1>
            <p style="color: #38bdf8; margin: 4px 0 0 0; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Recuperación de Contraseña</p>
          </td>
        </tr>
        <tr>
          <td style="padding: 32px 28px;">
            <p style="margin: 0 0 16px 0; font-size: 15px; color: #334155;">Hola <strong>{nombre}</strong>,</p>
            <p style="margin: 0 0 24px 0; font-size: 14px; color: #64748b; line-height: 1.5;">
              Hemos recibido una solicitud para restablecer la contraseña de tu cuenta institucional. Ingresa el siguiente código de seguridad en la plataforma para definir tu nueva contraseña:
            </p>
            
            <div style="background-color: #fef2f2; border: 2px dashed #f87171; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
              <span style="font-family: 'Courier New', Courier, monospace; font-size: 38px; font-weight: 800; color: #991b1b; letter-spacing: 8px;">{codigo}</span>
            </div>
            
            <p style="margin: 0 0 8px 0; font-size: 12px; color: #94a3b8; text-align: center;">
              🔑 Este código es válido por tiempo limitado y es de un solo uso.
            </p>
            <p style="margin: 0; font-size: 12px; color: #94a3b8; text-align: center;">
              Si no solicitaste recuperar tu contraseña, puedes ignorar este mensaje de forma segura.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center;">
            <p style="margin: 0; font-size: 11px; color: #94a3b8;">
              Centro de Comando EdTech · Seguridad y Gobernanza de Acceso
            </p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

ultimo_error_smtp = ""

TUNNEL_RELAY_URL = ""

RELAY_SECRET = "edtech_relay_2026_vkwx"

def esta_correo_registrado_en_programa(correo: str) -> Optional[Dict[str, Any]]:
    """Verifica en tiempo real si el correo pertenece a un usuario registrado en la base de datos"""
    if not correo or "@" not in str(correo):
        return None
    try:
        correo_l = str(correo).strip().lower()
        u = db.execute_query(
            """SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.mentor_id,
                      COALESCE(o.nombre, 'Plataforma Global EdTech') as institucion_nombre
               FROM usuarios u
               LEFT JOIN organizaciones o ON o.id = u.organizacion_id
               WHERE LOWER(TRIM(u.correo)) = ?""",
            (correo_l,),
            fetchone=True
        )
        if u:
            return dict(u)
        return None
    except Exception as e:
        print(f">> [DB-ERROR] Error en esta_correo_registrado_en_programa para {correo}: {e}")
        return None

def _obtener_urls_puente_https() -> List[str]:
    """Obtiene las URLs activas del túnel HTTPS (puerto 443) para reenviar correos desde nubes con puertos SMTP bloqueados"""
    urls = []
    if TUNNEL_RELAY_URL and TUNNEL_RELAY_URL.startswith("http"):
        u = TUNNEL_RELAY_URL.rstrip("/")
        if u not in urls:
            urls.append(u)
    try:
        enlace_local = detectar_url_tunel_activa()
        if enlace_local and enlace_local.startswith("http") and enlace_local.rstrip("/") not in urls:
            urls.append(enlace_local.rstrip("/"))
    except Exception:
        pass
    try:
        req_gh = urllib.request.Request(
            f"https://raw.githubusercontent.com/diegoalexandernino583-svg/consultoria-edtech/main/ENLACE_PUBLICO.txt?t={int(time.time())}",
            headers={"User-Agent": "ConsultoriaEdTech-Relay/3.5", "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req_gh, timeout=4) as resp_gh:
            txt_gh = resp_gh.read().decode("utf-8", errors="ignore")
            matches_gh = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', txt_gh)
            for m in matches_gh:
                m_clean = m.rstrip("/")
                if m_clean not in urls:
                    urls.append(m_clean)
    except Exception:
        pass
    return urls

def _enviar_via_puente_https(destinatario: str, asunto: str, cuerpo_texto: str, cuerpo_html: Optional[str] = None, codigo_otp: Optional[str] = None) -> bool:
    """Envía el correo a través del puerto 443 HTTPS hacia el nodo local con SMTP 465 abierto, sincronizando al usuario si es nuevo y obteniendo su institución real"""
    global ultimo_error_smtp
    corr_l = (destinatario or "").strip().lower()
    usuario_reg = db.execute_query(
        """SELECT u.id, u.organizacion_id, u.mentor_id, u.nombre, u.correo, u.rol, u.password_hash,
                  COALESCE(o.nombre, 'Corporación Universitaria Minuto de Dios') as institucion_nombre
           FROM usuarios u
           LEFT JOIN organizaciones o ON o.id = u.organizacion_id
           WHERE LOWER(TRIM(u.correo)) = ?""",
        (corr_l,),
        fetchone=True
    )
    if not usuario_reg:
        usuario_reg = db.execute_query(
            """SELECT h.usuario_id as id, h.organizacion_id, NULL as mentor_id, h.nombre, h.correo, h.rol, NULL as password_hash,
                      COALESCE(o.nombre, h.organizacion_nombre, 'Corporación Universitaria Minuto de Dios') as institucion_nombre
               FROM historial_nuevos_integrantes h
               LEFT JOIN organizaciones o ON o.id = h.organizacion_id
               WHERE LOWER(TRIM(h.correo)) = ?
               ORDER BY h.id DESC LIMIT 1""",
            (corr_l,),
            fetchone=True
        )
        if usuario_reg:
            # Auto-insertar/sincronizar en la tabla usuarios para garantizar coherencia
            hash_defecto = bcrypt.hashpw("123456".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db.execute_query(
                "INSERT OR IGNORE INTO usuarios (nombre, correo, rol, organizacion_id, password_hash) VALUES (?, ?, ?, ?, ?)",
                (usuario_reg["nombre"], corr_l, usuario_reg["rol"], usuario_reg.get("organizacion_id") or 13, hash_defecto),
                commit=True
            )
            u_sync = db.execute_query(
                """SELECT u.id, u.organizacion_id, u.mentor_id, u.nombre, u.correo, u.rol, u.password_hash,
                          COALESCE(o.nombre, 'Corporación Universitaria Minuto de Dios') as institucion_nombre
                   FROM usuarios u
                   LEFT JOIN organizaciones o ON o.id = u.organizacion_id
                   WHERE LOWER(TRIM(u.correo)) = ?""",
                (corr_l,),
                fetchone=True
            )
            if u_sync:
                usuario_reg = u_sync

    if not usuario_reg:
        usuario_reg = esta_correo_registrado_en_programa(corr_l)

    cod_otp_val = str(codigo_otp).strip() if codigo_otp else ""
    if not cod_otp_val:
        m = re.search(r'\b(\d{6})\b', f"{asunto or ''} {cuerpo_texto or ''}")
        if m:
            cod_otp_val = m.group(1)
            codigo_otp = cod_otp_val

    if cod_otp_val or (isinstance(asunto, str) and ("2fa" in asunto.lower() or "código" in asunto.lower())):
        nom_val = (usuario_reg.get("nombre") if usuario_reg else None) or "Usuario"
        rol_val = (usuario_reg.get("rol") if usuario_reg else None) or "Aprendiz"
        inst_val = (usuario_reg.get("institucion_nombre") if usuario_reg else None) or "Corporación Universitaria Minuto de Dios"
        org_id_val = (usuario_reg.get("organizacion_id") if usuario_reg else None) or 13
        cod_final = cod_otp_val or "123456"
        codigo_otp = cod_final

        asunto = f"🛡️ [{cod_final}] Código de Seguridad 2FA · {inst_val}"
        cuerpo_texto = (
            f"¡Hola, {nom_val}! 👋 Te damos la más cordial bienvenida a Consultoría EdTech.\n\n"
            f"Información de tu cuenta:\n"
            f"• Nombre: {nom_val}\n"
            f"• Cargo / Rol: {rol_val}\n"
            f"• Institución: {inst_val} (ID: {org_id_val})\n"
            f"• Correo: {corr_l}\n\n"
            f"Tu código de verificación de 6 dígitos para autorizar el ingreso es:\n\n"
            f"    {cod_final}\n\n"
            f"Este código es personal, confidencial y válido durante los próximos 30 minutos.\n\n"
            f"{inst_val} · Consultoría EdTech"
        )
        cuerpo_html = generar_html_correo_2fa(
            nombre=nom_val,
            codigo=cod_final,
            rol=rol_val,
            correo=corr_l,
            institucion_nombre=inst_val,
            organizacion_id=org_id_val
        )

    urls_puente = _obtener_urls_puente_https()
    for base_url in urls_puente:
        try:
            endpoint = f"{base_url}/api/internal/smtp-relay"
            payload = json.dumps({
                "destinatario": destinatario,
                "asunto": asunto,
                "cuerpo_texto": cuerpo_texto,
                "cuerpo_html": cuerpo_html,
                "codigo_otp": codigo_otp,
                "usuario_registro": dict(usuario_reg) if usuario_reg else None,
                "secret": RELAY_SECRET
            }).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "ConsultoriaEdTech-CloudRelay/3.5"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    data_resp = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    if data_resp.get("enviado"):
                        ultimo_error_smtp = ""
                        print(f">> [HTTPS-443-RELAY] Correo entregado exitosamente a {destinatario} vía puente {base_url}", flush=True)
                        return True
        except Exception as e_rel:
            ultimo_error_smtp = f"Relay HTTPS ({base_url}): {e_rel}"
    return False

_enviar_por_puente_https = _enviar_via_puente_https

def enviar_correo_smtp(destinatario: str, asunto: str, cuerpo_texto: str, cuerpo_html: Optional[str] = None, evitar_relay: bool = False, codigo_otp: Optional[str] = None) -> bool:
    """Envía correo exclusivamente a usuarios registrados dentro del programa mediante Gmail SMTP (465 SSL / 587 STARTTLS) y Puente HTTPS 443"""
    global CORREO_APP, CLAVE_APP, ultimo_error_smtp
    correo_remitente = (os.getenv("EMAIL_APP") or os.getenv("CORREO_APP") or CORREO_APP or "").strip()
    clave_remitente = (os.getenv("EMAIL_PASS") or os.getenv("CLAVE_APP") or CLAVE_APP or "").replace(" ", "").strip()
    CORREO_APP = correo_remitente
    CLAVE_APP = clave_remitente

    destinatario_limpio = (destinatario or "").strip().lower()
    if not destinatario_limpio or "@" not in destinatario_limpio:
        ultimo_error_smtp = f"Correo inválido: '{destinatario_limpio}'"
        return False

    usuario_registrado = esta_correo_registrado_en_programa(destinatario_limpio)
    if not usuario_registrado:
        nom_val = destinatario_limpio.split('@')[0].replace('.', ' ').title()
        usuario_registrado = {
            "id": None,
            "nombre": nom_val,
            "correo": destinatario_limpio,
            "rol": "Aprendiz",
            "organizacion_id": 13,
            "institucion_nombre": "Corporación Universitaria Minuto de Dios"
        }

    cod_otp_val = str(codigo_otp).strip() if codigo_otp else ""
    if not cod_otp_val:
        m = re.search(r'\b(\d{6})\b', f"{asunto or ''} {cuerpo_texto or ''}")
        if m:
            cod_otp_val = m.group(1)
            codigo_otp = cod_otp_val

    if usuario_registrado and (cod_otp_val or (isinstance(asunto, str) and ("2fa" in asunto.lower() or "código" in asunto.lower()))):
        nom_val = usuario_registrado.get("nombre") or "Usuario"
        rol_val = usuario_registrado.get("rol") or "Aprendiz"
        inst_val = usuario_registrado.get("institucion_nombre") or "Corporación Universitaria Minuto de Dios"
        org_id_val = usuario_registrado.get("organizacion_id") or 13
        cod_final = cod_otp_val or "123456"
        codigo_otp = cod_final

        asunto = f"🛡️ [{cod_final}] Código de Seguridad 2FA · {inst_val}"
        cuerpo_texto = (
            f"¡Hola, {nom_val}! 👋 Te damos la más cordial bienvenida a Consultoría EdTech.\n\n"
            f"Información de tu cuenta:\n"
            f"• Nombre: {nom_val}\n"
            f"• Cargo / Rol: {rol_val}\n"
            f"• Institución: {inst_val} (ID: {org_id_val})\n"
            f"• Correo: {destinatario_limpio}\n\n"
            f"Tu código de verificación de 6 dígitos para autorizar el ingreso es:\n\n"
            f"    {cod_final}\n\n"
            f"Este código es personal, confidencial y válido durante los próximos 30 minutos.\n\n"
            f"{inst_val} · Consultoría EdTech"
        )
        cuerpo_html = generar_html_correo_2fa(
            nombre=nom_val,
            codigo=cod_final,
            rol=rol_val,
            correo=destinatario_limpio,
            institucion_nombre=inst_val,
            organizacion_id=org_id_val
        )

    if not CORREO_APP or not CLAVE_APP:
        ultimo_error_smtp = "Credenciales SMTP no configuradas en el entorno."
        print(f">> [SMTP] Credenciales no configuradas. Simulación para: {destinatario_limpio}")
        return False

    # Si estamos en Render Cloud (donde los puertos 465/587 están bloqueados por red), usar primero el Puente HTTPS 443
    es_render_cloud = bool(os.getenv("RENDER"))
    if es_render_cloud and not evitar_relay:
        if _enviar_via_puente_https(destinatario_limpio, asunto, cuerpo_texto, cuerpo_html, codigo_otp):
            return True
        
    try:
        msg = EmailMessage()
        msg['Subject'] = asunto
        msg['From'] = f"Consultoria EdTech <{CORREO_APP}>"
        msg['To'] = destinatario_limpio
        msg['Reply-To'] = CORREO_APP
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid(domain='gmail.com')
        msg['X-Mailer'] = 'Consultoria EdTech 2FA'
        
        if cuerpo_html:
            msg.set_content(cuerpo_texto, charset='utf-8')
            msg.add_alternative(cuerpo_html, subtype='html', charset='utf-8')
        else:
            msg['Importance'] = 'High'
            msg['Priority'] = 'Urgent'
            cuerpo_ascii = cuerpo_texto.encode('ascii', 'ignore').decode('ascii')
            msg.set_content(cuerpo_ascii, charset='us-ascii')
            
        webhook_url = os.getenv("GMAIL_WEBHOOK_URL", "").strip()
        if webhook_url:
            try:
                payload = json.dumps({
                    "to": destinatario_limpio,
                    "subject": asunto,
                    "body": cuerpo_texto,
                    "html": cuerpo_html or cuerpo_texto
                }).encode('utf-8')
                req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status in (200, 201, 302):
                        print(f">> [GMAIL-WEBHOOK] Correo entregado exitosamente vía HTTPS a {destinatario_limpio}")
                        return True
            except Exception as e_wh:
                ultimo_error_smtp = f"Webhook HTTPS: {e_wh}"

        enviado = False
        # Intento 1 y 2: Puerto 465 SSL con reintento automático ante micro-cortes de red
        for intento_ssl in range(2):
            try:
                with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=6) as smtp:
                    smtp.login(CORREO_APP, CLAVE_APP)
                    smtp.send_message(msg)
                    enviado = True
                    ultimo_error_smtp = ""
                    print(f">> [SMTP-465] Correo entregado exitosamente a {destinatario_limpio}", flush=True)
                    break
            except Exception as e_ssl:
                ultimo_error_smtp = f"SSL 465: {e_ssl}"
                if ("101" in str(e_ssl) or "unreachable" in str(e_ssl).lower()):
                    break
                time.sleep(0.3)

        if not enviado:
            try:
                with smtplib.SMTP('smtp.gmail.com', 587, timeout=6) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
                    smtp.login(CORREO_APP, CLAVE_APP)
                    smtp.send_message(msg)
                    enviado = True
                    ultimo_error_smtp = ""
                    print(f">> [SMTP-587] Correo entregado exitosamente a {destinatario_limpio} vía STARTTLS", flush=True)
            except Exception as e_tls:
                ultimo_error_smtp = f"STARTTLS 587: {e_tls}"
                print(f">> [SMTP-587-ERROR] Falló STARTTLS 587 para {destinatario_limpio}: {e_tls}")

        if not enviado and not evitar_relay:
            try:
                if _enviar_via_puente_https(destinatario_limpio, asunto, cuerpo_texto, cuerpo_html, codigo_otp):
                    enviado = True
                    ultimo_error_smtp = ""
                    print(f">> [PUENTE-HTTPS] Correo entregado exitosamente a {destinatario_limpio} vía puente Cloudflare", flush=True)
            except Exception as e_bridge:
                ultimo_error_smtp = f"Puente HTTPS: {e_bridge}"
                print(f">> [PUENTE-HTTPS-ERROR] Falló puente HTTPS para {destinatario_limpio}: {e_bridge}")

        return enviado
    except Exception as e:
        ultimo_error_smtp = f"Error general: {e}"
        print(f">> [SMTP] Error general preparando correo para {destinatario_limpio}: {e}")
        return False

cache_ips_bloqueadas = set()

intentos_fallidos_login: Dict[str, list] = {}

rate_limit_general: Dict[str, list] = {}

alerta_email_cooldown: Dict[str, datetime] = {}

def cargar_cache_ips_bloqueadas():
    """Carga las IPs bloqueadas desde la base de datos al inicio para validación instantánea (0ms)"""
    global cache_ips_bloqueadas
    try:
        filas = db.execute_query("SELECT ip FROM ips_bloqueadas WHERE bloqueo_activo = 1", fetchall=True)
        if filas:
            cache_ips_bloqueadas = set(f["ip"] for f in filas)
        else:
            cache_ips_bloqueadas = set()
        print(f">> [WAF] Base de datos de ciberseguridad cargada ({len(cache_ips_bloqueadas)} IPs bloqueadas en lista negra).")
    except Exception as e:
        print(f">> [WAF] Aviso cargando IPs bloqueadas: {e}")
        cache_ips_bloqueadas = set()

def bloquear_ip_inmediatamente(ip: str, motivo: str, minutos: Optional[int] = None, bloqueado_por: str = "Firewall_WAF"):
    """Bloquea una dirección IP tanto en memoria como en SQLite persistente"""
    global cache_ips_bloqueadas
    # Protección de IPs locales, túneles y redes privadas seguras
    if not ip or ip in ["127.0.0.1", "localhost", "::1"] or ip.startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")):
        print(f">> [WAF] Bloqueo evitado para dirección local o privada segura: {ip} ({motivo})")
        return

    cache_ips_bloqueadas.add(ip)
    expira_str = None
    if minutos:
        expira_dt = datetime.now() + timedelta(minutes=minutos)
        expira_str = expira_dt.strftime("%Y-%m-%d %H:%M:%S")

    try:
        existente = db.execute_query("SELECT id, intentos_maliciosos FROM ips_bloqueadas WHERE ip = ?", (ip,), fetchone=True)
        if existente:
            db.execute_query(
                """UPDATE ips_bloqueadas 
                   SET bloqueo_activo = 1, intentos_maliciosos = intentos_maliciosos + 1, motivo = ?, 
                       fecha_bloqueo = DATETIME('now', 'localtime'), expira_en = ?
                   WHERE id = ?""",
                (motivo, expira_str, existente["id"]),
                commit=True
            )
        else:
            db.execute_query(
                """INSERT INTO ips_bloqueadas (ip, motivo, intentos_maliciosos, bloqueo_activo, fecha_bloqueo, expira_en, bloqueado_por)
                   VALUES (?, ?, 1, 1, DATETIME('now', 'localtime'), ?, ?)""",
                (ip, motivo, expira_str, bloqueado_por),
                commit=True
            )
        print(f">> [WAF] IP {ip} BLOQUEADA. Motivo: {motivo}")
    except Exception as e:
        print(f">> [WAF] Error persistiendo bloqueo de IP {ip}: {e}")

def desbloquear_ip(ip: str) -> bool:
    """Desbloquea una dirección IP en memoria y en SQLite"""
    global cache_ips_bloqueadas
    if ip in cache_ips_bloqueadas:
        cache_ips_bloqueadas.remove(ip)
    try:
        db.execute_query("UPDATE ips_bloqueadas SET bloqueo_activo = 0 WHERE ip = ?", (ip,), commit=True)
        print(f">> [WAF] IP {ip} desbloqueada con éxito.")
        return True
    except Exception as e:
        print(f">> [WAF] Error desbloqueando IP {ip}: {e}")
        return False

def obtener_ip_cliente(request: Request) -> str:
    """Extrae la IP real del cliente, soportando Cloudflare Tunnel, Proxies y conexión local"""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()
    xf = request.headers.get("X-Forwarded-For")
    if xf and xf.strip():
        return xf.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"

def registrar_intento_fallido_login(ip: str) -> int:
    """Registra un fallo de login y devuelve el número acumulado en los últimos 10 minutos"""
    global intentos_fallidos_login
    ahora = datetime.now()
    ventana = ahora - timedelta(minutes=10)
    if ip not in intentos_fallidos_login:
        intentos_fallidos_login[ip] = []
    intentos_fallidos_login[ip] = [t for t in intentos_fallidos_login[ip] if t > ventana]
    intentos_fallidos_login[ip].append(ahora)
    return len(intentos_fallidos_login[ip])

def limpiar_intentos_fallidos_login(ip: str):
    """Limpia el contador de intentos fallidos al iniciar sesión exitosamente"""
    global intentos_fallidos_login
    if ip in intentos_fallidos_login:
        del intentos_fallidos_login[ip]

def verificar_rate_limit_general(ip: str, max_por_minuto: int = 240) -> bool:
    """Limita solicitudes para prevenir DDoS y saturación (240 req/min por IP)"""
    global rate_limit_general
    ahora = datetime.now()
    ventana = ahora - timedelta(minutes=1)
    if ip not in rate_limit_general:
        rate_limit_general[ip] = []
    rate_limit_general[ip] = [t for t in rate_limit_general[ip] if t > ventana]
    if len(rate_limit_general[ip]) >= max_por_minuto:
        return False
    rate_limit_general[ip].append(ahora)
    return True

def registrar_log_acceso(ip: str, metodo: str, ruta: str, status_code: int, duracion_ms: float, user_agent: str, amenaza: int = 0):
    """Encola accesos HTTP en segundo plano con latencia 0ms para el hilo de respuesta"""
    try:
        _cola_auditoria.put(("http_log", ip, metodo, ruta[:150], status_code, duracion_ms, str(user_agent)[:200], amenaza))
    except Exception:
        pass

def sanitizar_texto(texto: Optional[str]) -> str:
    """Sanitiza entradas para prevenir Stored XSS e inyección de HTML malicioso"""
    if not texto:
        return ""
    limpio = re.sub(r'<\s*(script|iframe|object|embed|applet)[\s\S]*?<\s*/\s*\1\s*>', '', str(texto), flags=re.IGNORECASE)
    limpio = limpio.replace('<', '&lt;').replace('>', '&gt;')
    return limpio.strip()

RE_SQLI = re.compile(
    r"(?i)(\bunion\b\s+(all\s+)?\bselect\b|;\s*(drop|delete|truncate|alter|insert|update)\b|\bor\b\s+['\"]?1['\"]?\s*=\s*['\"]?1|--\s*$|/\*.*?\*/|@@version|waitfor\s+delay|sleep\s*\(\d+\)|exec(\s|\+)+(s|x)p_|\bselect\b\s+.+\s+\bfrom\b\s+information_schema|\b(benchmark|extractvalue)\b\s*\()",
    re.IGNORECASE
)

RE_XSS = re.compile(
    r"(?i)(<\s*script[\s\S]*?>[\s\S]*?<\s*/\s*script\s*>|javascript\s*:|vbscript\s*:|<\s*img[^>]+onerror\s*=|onerror\s*=\s*['\"]?[a-zA-Z0-9_\(\)]+|<\s*iframe[\s\S]*?>|<\s*svg[^>]*onload\s*=|alert\s*\(\s*['\"][^'\"]*['\"]\s*\)|document\.cookie)",
    re.IGNORECASE
)

RE_PATH_TRAVERSAL = re.compile(
    r"(\.\./|\.\.\\|/etc/passwd|/windows/system32|boot\.ini|/proc/self)",
    re.IGNORECASE
)

RE_USER_AGENT_MALICIOSO = re.compile(
    r"(?i)(sqlmap|nikto|havij|acunetix|masscan|zgrab|dirbuster|gobuster|wpscan|censys|hydra|burpcollaborator)",
    re.IGNORECASE
)

RUTAS_HONEYPOT_BOTS = {
    "/wp-admin", "/wp-login.php", "/.env", "/config.php", "/phpmyadmin",
    "/xmlrpc.php", "/actuator/health", "/shell.php", "/backup.sql",
    "/admin/login.php", "/eval-stdin.php", "/wp-content", "/aws/credentials"
}

def inspeccionar_payload_waf(texto: str) -> tuple[bool, Optional[str]]:
    """Inspecciona cualquier texto en busca de patrones de ataque conocidos"""
    if not texto or len(texto) < 3:
        return False, None
    try:
        texto_dec = unquote(texto)
    except Exception:
        texto_dec = texto

    if RE_SQLI.search(texto_dec):
        return True, "INYECCIÓN_SQL"
    if RE_XSS.search(texto_dec):
        return True, "CROSS_SITE_SCRIPTING_XSS"
    if RE_PATH_TRAVERSAL.search(texto_dec):
        return True, "PATH_TRAVERSAL_INCLUSION"
        
    return False, None

def generar_html_correo_alerta_seguridad(tipo_amenaza: str, ip: str, detalles: str, payload: Optional[str] = None, ruta: Optional[str] = None, metodo: Optional[str] = None, severidad: str = "CRITICA") -> str:
    """Genera plantilla de alta prioridad para incidentes críticos de seguridad"""
    payload_html = ""
    if payload:
        escaped_payload = html.escape(str(payload)[:300])
        payload_html = f"""
        <div style="background-color: #0f172a; border-radius: 8px; padding: 12px; margin-top: 14px; overflow-x: auto;">
          <p style="color: #94a3b8; font-size: 11px; margin: 0 0 4px 0; font-family: monospace;">PAYLOAD INTERCEPTADO POR WAF:</p>
          <pre style="color: #f87171; font-size: 12px; margin: 0; font-family: monospace; white-space: pre-wrap; word-break: break-all;">{escaped_payload}</pre>
        </div>
        """
    
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ruta_metodo = f"{metodo + ' ' if metodo else ''}{ruta or 'N/A'}"
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0f19; margin: 0; padding: 24px; color: #f1f5f9;">
      <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #111827; border-radius: 16px; border: 1px solid #dc2626; overflow: hidden; box-shadow: 0 8px 30px rgba(220, 38, 38, 0.25);">
        <tr>
          <td style="background: linear-gradient(135deg, #7f1d1d, #991b1b); padding: 26px 24px; text-align: center;">
            <div style="display: inline-block; background-color: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 9999px; font-size: 11px; font-weight: 800; color: #ffffff; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">
              🛡️ ALERTA CRÍTICA · FIREWALL WAF DE CONSULTORÍA
            </div>
            <h1 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 800;">Actividad Sospechosa Bloqueada</h1>
            <p style="color: #fca5a5; margin: 4px 0 0 0; font-size: 12px;">Centro de Mando EdTech · Escudo Activo 24/7</p>
          </td>
        </tr>
        <tr>
          <td style="padding: 26px;">
            <div style="background-color: #1f2937; border-left: 4px solid #ef4444; border-radius: 8px; padding: 14px; margin-bottom: 18px;">
              <p style="margin: 0; font-size: 11px; color: #9ca3af; text-transform: uppercase; font-weight: 700;">Amenaza Neutralizada:</p>
              <p style="margin: 3px 0 0 0; font-size: 16px; font-weight: 800; color: #f87171;">{html.escape(tipo_amenaza)}</p>
              <p style="margin: 8px 0 0 0; font-size: 13px; color: #e5e7eb; line-height: 1.4;">{html.escape(detalles)}</p>
            </div>

            <table width="100%" cellpadding="6" cellspacing="0" style="font-size: 13px; color: #d1d5db; background-color: #1e293b; border-radius: 8px; margin-bottom: 16px;">
              <tr>
                <td width="35%" style="color: #94a3b8; font-weight: 600; padding: 9px 12px; border-bottom: 1px solid #334155;">Dirección IP Origen:</td>
                <td style="font-family: monospace; font-weight: 700; color: #38bdf8; padding: 9px 12px; border-bottom: 1px solid #334155;">{html.escape(ip)}</td>
              </tr>
              <tr>
                <td style="color: #94a3b8; font-weight: 600; padding: 9px 12px; border-bottom: 1px solid #334155;">Fecha y Hora:</td>
                <td style="font-family: monospace; color: #f3f4f6; padding: 9px 12px; border-bottom: 1px solid #334155;">{fecha_hora}</td>
              </tr>
              <tr>
                <td style="color: #94a3b8; font-weight: 600; padding: 9px 12px; border-bottom: 1px solid #334155;">Ruta Afectada:</td>
                <td style="font-family: monospace; color: #f3f4f6; padding: 9px 12px; border-bottom: 1px solid #334155;">{html.escape(ruta_metodo)}</td>
              </tr>
              <tr>
                <td style="color: #94a3b8; font-weight: 600; padding: 9px 12px;">Acción de Seguridad:</td>
                <td style="color: #34d399; font-weight: 700; padding: 9px 12px;">[✓ RECHAZADO HTTP 403 / IP BLOQUEADA]</td>
              </tr>
            </table>

            {payload_html}

            <p style="margin: 18px 0 0 0; font-size: 11px; color: #9ca3af; text-align: center; line-height: 1.4;">
              🔒 Esta notificación se emite exclusivamente ante eventos de ciberseguridad graves. Los movimientos rutinarios y usos normales no generan correos.
            </p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

def enviar_alerta_seguridad_critica(tipo_amenaza: str, ip: str, detalles: str, payload: Optional[str] = None, ruta: Optional[str] = None, metodo: Optional[str] = None, severidad: str = "CRITICA"):
    """
    Envía una alerta de seguridad de ALTA PRIORIDAD al correo del administrador.
    ÚNICAMENTE se activa ante incidentes genuinamente sospechosos.
    Aplica cooldown de 5 minutos por (tipo_amenaza, ip) para evitar saturación de bandeja.
    """
    global alerta_email_cooldown
    
    # Registrar en base de datos de incidentes
    try:
        db.execute_query(
            """INSERT INTO incidentes_seguridad (ip, tipo_amenaza, nivel_severidad, detalles, payload_detectado, ruta_afectada, metodo_http, alerta_enviada, fecha_hora)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, DATETIME('now', 'localtime'))""",
            (ip, tipo_amenaza, severidad, detalles, str(payload)[:500] if payload else None, ruta, metodo),
            commit=True
        )
    except Exception as e_db:
        print(f">> [WAF-DB] Error guardando incidente: {e_db}")

    # Cooldown para no saturar correo si un atacante envía ráfagas masivas
    clave_cooldown = f"{tipo_amenaza}:{ip}"
    ahora = datetime.now()
    ultimo_envio = alerta_email_cooldown.get(clave_cooldown)
    if ultimo_envio and (ahora - ultimo_envio).total_seconds() < 300:
        print(f">> [WAF-ALERTA] Cooldown activo para {clave_cooldown}. Incidente guardado en BD, correo omitido para evitar spam.")
        return False

    alerta_email_cooldown[clave_cooldown] = ahora
    destinatario = CORREO_APP or "alexander.nino.583@gmail.com"
    asunto = f"🚨 [ALERTA WAF] {tipo_amenaza} Neutralizado - IP {ip}"
    cuerpo_texto = f"ALERTA DE SEGURIDAD CRÍTICA:\n\nAmenaza: {tipo_amenaza}\nIP: {ip}\nDetalles: {detalles}\nRuta: {ruta or 'N/A'}\nMétodo: {metodo or 'N/A'}\nPayload: {payload or 'N/A'}\nFecha: {ahora}\nAcción: Petición neutralizada por WAF HTTP 403."
    cuerpo_html = generar_html_correo_alerta_seguridad(tipo_amenaza, ip, detalles, payload, ruta, metodo, severidad)

    def _enviar():
        try:
            exito = enviar_correo_smtp(destinatario, asunto, cuerpo_texto, cuerpo_html)
            if exito:
                print(f">> [WAF-ALERTA] Correo de alerta crítica enviado a {destinatario}")
        except Exception as e_env:
            print(f">> [WAF-ALERTA] Error despachando alerta por correo: {e_env}")

    t = threading.Thread(target=_enviar, daemon=True)
    t.start()
    return True

cargar_cache_ips_bloqueadas()

class IniciarLoginRequest(BaseModel):
    correo: str
    password: str
    honeypot: Optional[str] = None

class BloquearIpRequest(BaseModel):
    ip: str
    motivo: Optional[str] = "Bloqueo manual por Administrador"
    minutos: Optional[int] = None

class DesbloquearIpRequest(BaseModel):
    ip: str

class SolicitarRecuperacionRequest(BaseModel):
    correo: str

class CambiarPasswordRequest(BaseModel):
    correo: str
    codigo: str
    nueva_password: str

class RegistroUsuarioRequest(BaseModel):
    nombre: str
    correo: str
    password: str
    rol: str
    organizacion_id: Optional[int] = 1
    mentor_id: Optional[int] = None

class CrearIntegranteManualReq(BaseModel):
    organizacion_id: int
    nombre: str
    correo: str
    rol: str
    mentor_id: Optional[int] = None
    password: Optional[str] = "123456"

class CambiarPasswordSesionReq(BaseModel):
    usuario_id: int
    password_actual: str
    password_nueva: str

class CrearOrgRequest(BaseModel):
    nombre: str
    tipo_organizacion: str
    dominio_permitido: Optional[str] = "LIBRE"
    licencias_asignadas: Optional[int] = 100
    max_administradores: Optional[int] = 2
    max_mentores: Optional[int] = 5
    logo_url: Optional[str] = None

class ActualizarOrgRequest(BaseModel):
    nombre: str
    tipo_organizacion: str
    dominio_permitido: Optional[str] = "LIBRE"
    licencias_asignadas: int
    max_administradores: Optional[int] = 2
    max_mentores: Optional[int] = 15
    logo_url: Optional[str] = None

class SubirLogoOrgRequest(BaseModel):
    logo_url: str

class ActualizarUsuarioRequest(BaseModel):
    nombre: str
    correo: str
    rol: str
    organizacion_id: Optional[int] = None
    mentor_id: Optional[int] = None

class EliminarLoteReq(BaseModel):
    ids: List[int]
    eliminar_usuarios: Optional[bool] = False

class EliminarLoteAuditReq(BaseModel):
    ids: List[int]

class LimpiarBaseDatosReq(BaseModel):
    tipo: str = "todo"  # "todo", "historial_auditoria", "usuarios_prueba", "optimizar"
    preservar_superadmin: bool = True

class ColorimetriaReq(BaseModel):
    color_primario: str = "#0a192f"
    color_secundario: str = "#0f273f"
    color_acento: str = "#06b6d4"
    color_personalizado: bool = True

class GuardarTemaReq(BaseModel):
    nombre: Optional[str] = None
    nombre_tema: Optional[str] = None
    color_primario: str
    color_secundario: str
    color_acento: str

class LimpiarGranularReq(BaseModel):
    limpiar_auditoria: bool = False
    limpiar_historial_integrantes: bool = False
    limpiar_papelera: bool = False
    limpiar_usuarios_prueba: bool = False
    ejecutar_vacuum: bool = True

class CrearQuizRequest(BaseModel):
    mentor_id: int
    organizacion_id: Optional[int] = None
    titulo: str
    tipo: Optional[str] = "Quiz"
    descripcion: Optional[str] = ""
    duracion_minutos: Optional[int] = 15
    preguntas: List[Dict[str, Any]]

class ResponderQuizRequest(BaseModel):
    aprendiz_id: int
    respuestas: Any
    tiempo_segundos: Optional[int] = 60

class ActualizarTemaDecorativoRequest(BaseModel):
    tema_decorativo: str
    fondo_personalizado: Optional[str] = None

class PerfilFotoReq(BaseModel):
    usuario_id: int
    foto_perfil: str

class PerfilPasswordReq(BaseModel):
    usuario_id: int
    password_actual: Optional[str] = None
    password_nueva: str

class CrearMaterialReq(BaseModel):
    titulo: str
    tipo_material: str
    enlace_url: str
    rol_destino: Optional[str] = "Aprendiz"
    total_modulos: Optional[int] = 3
    descripcion_modulos: Optional[str] = None
    organizacion_id: Optional[int] = None

class EnviarColeccionOrgReq(BaseModel):
    material_id: int
    organizacion_id: int
    destinatario_tipo: Optional[str] = "Institución"  # 'Institución', 'Mentores', 'Aprendices'
    destinatario_id: Optional[int] = None             # ID de usuario si es individual, None/0 si es todos
    remitente_id: Optional[int] = None
    remitente_rol: Optional[str] = None

class ActualizarProgresoModulosReq(BaseModel):
    usuario_id: int
    curso_id: int
    modulos_completados: int
    tiempo_dedicado_minutos: Optional[int] = 20

class ReasignarAprendizReq(BaseModel):
    aprendiz_id: int
    mentor_id: Optional[int] = None

class AsignarLoteGrupoReq(BaseModel):
    mentor_id: int
    aprendices_ids: List[int]

class CompletarTestRequest(BaseModel):
    usuario_id: int
    curso_id: int
    respuestas_correctas: int
    total_preguntas: int
    tiempo_dedicado_minutos: Optional[int] = 20

class ControlAvanceInstitucionReq(BaseModel):
    organizacion_id: int
    porcentaje_avance: Optional[float] = None
    sincronizar_aprendices: Optional[bool] = True
    tiempo_dedicado_minutos: Optional[int] = None

class ControlAvanceGrupoReq(BaseModel):
    organizacion_id: int
    mentor_id: Optional[int] = None
    curso_id: Optional[int] = None
    porcentaje_avance: float
    modulos_completados: Optional[int] = None
    estado: Optional[str] = None
    tiempo_dedicado_minutos: Optional[int] = 60

class ControlAvanceIntegranteReq(BaseModel):
    usuario_id: int
    curso_id: Optional[int] = None
    porcentaje_avance: float
    modulos_completados: Optional[int] = None
    estado: Optional[str] = None
    tiempo_dedicado_minutos: Optional[int] = 45

def iniciar_tunel_cloudflare(puerto):
    """Inicia el binario oficial de Cloudflare Tunnel para habilitar acceso seguro HTTPS mundial"""
    global TUNNEL_PUBLIC_URL, PROCESO_TUNEL
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    cf_paths_to_check = [
        os.path.join(directorio_actual, "cloudflared.exe"),
        r"C:\Users\Dieguito\AppData\Local\cloudflared.exe",
        shutil.which("cloudflared") or ""
    ]
    cf_path = next((p for p in cf_paths_to_check if p and os.path.exists(p)), None)

    # Intentar leer URL activa de túnel previo si existe
    try:
        log_cf = r"C:\Users\Dieguito\AppData\Local\cloudflared_tunnel.log"
        if os.path.exists(log_cf):
            with open(log_cf, "r", encoding="utf-8", errors="ignore") as f_log:
                contenido = f_log.read()
                matches = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', contenido)
                if matches:
                    TUNNEL_PUBLIC_URL = matches[-1]
                    with open(os.path.join(directorio_actual, "ENLACE_PUBLICO.txt"), "w", encoding="utf-8") as f_pub:
                        f_pub.write(f"ENLACE PÚBLICO SEGURO (HTTPS) - CENTRO DE MANDO EDTECH:\n\n{TUNNEL_PUBLIC_URL}\n\nCualquier persona puede ingresar con cualquier conexión de internet (móvil, wifi, hogar o trabajo) sin instalar nada.\n")
    except Exception:
        pass

    if not cf_path:
        print(">> [i] cloudflared no encontrado. El servidor operará en Localhost y Red Local.")
        return

    # Si ya hay un proceso túnel corriendo en el sistema, no iniciar otro
    if PROCESO_TUNEL is not None:
        return

    try:
        print(">> [i] Conectando túnel seguro a Cloudflare...")
        cmd = [cf_path, "tunnel", "--url", f"http://127.0.0.1:{puerto}", "--no-autoupdate", "--logfile", r"C:\Users\Dieguito\AppData\Local\cloudflared_tunnel.log"]
        PROCESO_TUNEL = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        def monitorear_salida():
            global TUNNEL_PUBLIC_URL
            url_regex = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
            for line in iter(PROCESO_TUNEL.stdout.readline, ''):
                if not line:
                    break
                match = url_regex.search(line)
                if match:
                    TUNNEL_PUBLIC_URL = match.group(0)
                    print("\n" + "="*70)
                    print("🌐 ¡ENLACE MUNDIAL DE INTERNET LISTO (ACCESO GLOBAL HTTPS)!")
                    print("="*70)
                    print(f">> URL PÚBLICA:  {TUNNEL_PUBLIC_URL}")
                    print(">> Cualquier persona puede ingresar desde su celular o cualquier red.")
                    print("="*70 + "\n")
                    try:
                        with open(os.path.join(directorio_actual, "ENLACE_PUBLICO.txt"), "w", encoding="utf-8") as f_pub:
                            f_pub.write(f"{TUNNEL_PUBLIC_URL}\n")
                    except Exception:
                        pass
                    # Sincronizar inmediatamente la nueva URL del túnel hacia Render Cloud para el puente de correos
                    def _notificar_render_inmediato(t_url):
                        try:
                            for r_url in ["https://consultoria-edtech.onrender.com", "https://consultoria-edtech-visual.onrender.com"]:
                                try:
                                    req_r = urllib.request.Request(
                                        f"{r_url}/api/internal/registrar-tunel",
                                        data=json.dumps({"tunnel_url": t_url, "secret": RELAY_SECRET}).encode("utf-8"),
                                        headers={"Content-Type": "application/json", "User-Agent": "ConsultoriaEdTech-AutoRelay/3.5"}
                                    )
                                    with urllib.request.urlopen(req_r, timeout=6) as _:
                                        print(f">> [RELAY-RENDER] Túnel registrado exitosamente en {r_url}", flush=True)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    threading.Thread(target=_notificar_render_inmediato, args=(TUNNEL_PUBLIC_URL,), daemon=True).start()

                    if os.name == 'nt':
                        try:
                            subprocess.run(
                                ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{TUNNEL_PUBLIC_URL}'"],
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                timeout=4
                            )
                            print("📋 ¡Enlace copiado automáticamente al portapapeles de Windows!")
                        except Exception:
                            pass

        t = threading.Thread(target=monitorear_salida, daemon=True)
        t.start()
    except Exception as e:
        print(f"[!] Error iniciando túnel Cloudflare: {e}")

def _supervisar_tunel_cloudflare():
    """Vigila que el proceso cloudflared permanezca activo; si cae, lo relanza en segundo plano"""
    if os.getenv("RENDER"):
        return
    time.sleep(15)
    while True:
        try:
            global PROCESO_TUNEL, PUERTO_ACTUAL
            if PROCESO_TUNEL is None or PROCESO_TUNEL.poll() is not None:
                print(">> [VIGILANTE-TUNEL] Detectado túnel inactivo. Relanzando cloudflared...")
                PROCESO_TUNEL = None
                iniciar_tunel_cloudflare(PUERTO_ACTUAL)
        except Exception:
            pass
        time.sleep(30)

threading.Thread(target=_supervisar_tunel_cloudflare, name="vigilante-tunel-cf", daemon=True).start()

def limpiar_recursos():
    global PROCESO_TUNEL
    if PROCESO_TUNEL:
        try:
            PROCESO_TUNEL.terminate()
        except Exception:
            pass

atexit.register(limpiar_recursos)

_cache_tunel_url = {"url": "", "ts": 0.0}

def detectar_url_tunel_activa():
    """Busca la URL activa del túnel con caché en memoria de 30s para evitar lecturas de disco repetitivas"""
    ahora = time.time()
    if ahora - _cache_tunel_url["ts"] < 30.0:
        return _cache_tunel_url["url"]

    enlace_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ENLACE_PUBLICO.txt")
    if os.path.exists(enlace_file):
        try:
            with open(enlace_file, "r", encoding="utf-8", errors="ignore") as f:
                url = f.read().strip()
                if url.startswith("http"):
                    _cache_tunel_url["url"] = url
                    _cache_tunel_url["ts"] = ahora
                    return url
        except Exception:
            pass

    # Buscar en los logs más recientes ordenados por fecha de modificación
    candidatos = []
    rutas_fijas = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloudflared_tunnel.log"),
        r"C:\Users\Dieguito\AppData\Local\cloudflared_tunnel.log"
    ]
    for rf in rutas_fijas:
        if os.path.exists(rf):
            candidatos.append((os.path.getmtime(rf), rf))

    tasks_dir = r"C:\Users\Dieguito\.gemini\antigravity\brain\077c6eb3-d07c-47de-a96b-d0823be92f59\.system_generated\tasks"
    if os.path.exists(tasks_dir):
        for fname in os.listdir(tasks_dir):
            if fname.endswith(".log"):
                fp = os.path.join(tasks_dir, fname)
                try:
                    candidatos.append((os.path.getmtime(fp), fp))
                except Exception:
                    pass

    candidatos.sort(key=lambda x: x[0], reverse=True)
    for _, r in candidatos:
        try:
            with open(r, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
                matches = re.findall(r'https?://[a-zA-Z0-9-]+\.trycloudflare\.com', txt)
                if matches:
                    _cache_tunel_url["url"] = matches[-1]
                    _cache_tunel_url["ts"] = ahora
                    return matches[-1]
        except Exception:
            pass
    _cache_tunel_url["url"] = ""
    _cache_tunel_url["ts"] = ahora
    return ""

class RegistrarTunelReq(BaseModel):
    tunnel_url: Optional[str] = None
    usuarios: Optional[List[Dict[str, Any]]] = None
    secret: str

class SmtpRelayReq(BaseModel):
    destinatario: str
    asunto: str
    cuerpo_texto: str
    cuerpo_html: Optional[str] = None
    codigo_otp: Optional[str] = None
    usuario_registro: Optional[Dict[str, Any]] = None
    secret: str

def _fusionar_usuarios_recibidos(lista_usuarios: Optional[List[Dict[str, Any]]]):
    """Sincroniza únicamente usuarios pertenecientes a organizaciones activas sin recrear instituciones ni revivir eliminados"""
    if not lista_usuarios:
        return
    try:
        orgs_activas = {
            r["id"] for r in (db.execute_query("SELECT id FROM organizaciones", fetchall=True) or [])
        }
        eliminados = {
            (r["correo"] or "").strip().lower()
            for r in (db.execute_query("SELECT correo FROM usuarios_eliminados_papelera", fetchall=True) or [])
        }
        for u in lista_usuarios:
            correo_u = (u.get("correo") or "").strip().lower()
            if not correo_u or "@" not in correo_u or correo_u in eliminados:
                continue
            org_u = u.get("organizacion_id")
            if correo_u == "alexander.nino.583@gmail.com":
                org_u = None
            elif org_u not in orgs_activas:
                continue
            ex = db.execute_query(
                "SELECT id FROM usuarios WHERE LOWER(TRIM(correo)) = ?",
                (correo_u,),
                fetchone=True
            )
            if not ex:
                db.execute_query(
                    """INSERT OR IGNORE INTO usuarios (organizacion_id, mentor_id, nombre, correo, rol, password_hash)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        org_u,
                        u.get("mentor_id"),
                        (u.get("nombre") or "Integrante").strip(),
                        correo_u,
                        u.get("rol") or "Aprendiz",
                        u.get("password_hash") or "$2b$12$PWS97lBYHhK6hQ0ZsGIcy.ofr8kgkQ3zuVYB1ct0hk0yS4op.Cicu"
                    ),
                    commit=True
                )
    except Exception:
        pass

class ActualizarUsuarioRemotoReq(BaseModel):
    usuario: Dict[str, Any]
    secret: str

def _empujar_cambio_usuario_remoto(usuario_id: int):
    """Empuja en segundo plano el cambio de cargo, datos o contraseña de un usuario hacia Render Cloud / nodo par y fuerza réplica en Azure SQL"""
    try:
        replicador_azure.marcar("usuarios")
        replicador_azure.marcar("historial_nuevos_integrantes")
    except Exception:
        pass

    def _worker_push():
        try:
            u = db.execute_query(
                "SELECT id, organizacion_id, mentor_id, nombre, correo, rol, password_hash FROM usuarios WHERE id = ?",
                (usuario_id,), fetchone=True
            )
            if not u:
                return
            payload = json.dumps({"usuario": dict(u), "secret": RELAY_SECRET}).encode("utf-8")
            targets = _obtener_urls_puente_https() if os.getenv("RENDER") else [
                "https://consultoria-edtech-visual.onrender.com",
                "https://consultoria-edtech.onrender.com"
            ]
            for base_url in targets:
                try:
                    req = urllib.request.Request(
                        f"{base_url.rstrip('/')}/api/internal/actualizar-usuario-remoto",
                        data=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "ConsultoriaEdTech-RoleSync/3.5"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        if resp.status == 200:
                            break
                except Exception:
                    pass
        except Exception:
            pass

    threading.Thread(target=_worker_push, daemon=True).start()

def _ejecutar_ciclo_sync_nodos():
    """Sincroniza túnel y lista completa de usuarios registrados entre el nodo local y Render Cloud"""
    try:
        usuarios_locales = db.execute_query(
            "SELECT id, organizacion_id, mentor_id, nombre, correo, rol, password_hash FROM usuarios",
            fetchall=True
        ) or []
        lista_u = [dict(u) for u in usuarios_locales]
        if os.getenv("RENDER"):
            for base_url in _obtener_urls_puente_https():
                try:
                    payload = json.dumps({"usuarios": lista_u, "secret": RELAY_SECRET}).encode("utf-8")
                    req = urllib.request.Request(
                        f"{base_url}/api/internal/registrar-tunel",
                        data=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "ConsultoriaEdTech-UserSync/3.5"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        if resp.status == 200:
                            d = json.loads(resp.read().decode("utf-8", errors="ignore"))
                            if d.get("usuarios"):
                                _fusionar_usuarios_recibidos(d["usuarios"])
                            break
                except Exception:
                    pass
        else:
            url_t = detectar_url_tunel_activa()
            payload = json.dumps({
                "tunnel_url": url_t if (url_t and url_t.startswith("https://")) else None,
                "usuarios": lista_u,
                "secret": RELAY_SECRET
            }).encode("utf-8")
            for render_url in ["https://consultoria-edtech-visual.onrender.com", "https://consultoria-edtech.onrender.com"]:
                try:
                    req = urllib.request.Request(
                        f"{render_url}/api/internal/registrar-tunel",
                        data=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "ConsultoriaEdTech-TunnelSync/3.5"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        if resp.status == 200:
                            d = json.loads(resp.read().decode("utf-8", errors="ignore"))
                            if d.get("usuarios"):
                                _fusionar_usuarios_recibidos(d["usuarios"])
                except Exception:
                    pass
    except Exception:
        pass

def _disparar_sync_usuarios_nube():
    """Dispara en segundo plano la sincronización inmediata de usuarios recién creados o editados"""
    threading.Thread(target=_ejecutar_ciclo_sync_nodos, daemon=True).start()

def _latido_registro_tunel_en_render():
    """Sincroniza periódicamente (cada 35s) el túnel y todos los usuarios registrados entre Local y Render"""
    if os.getenv("RENDER"):
        return
    while True:
        _ejecutar_ciclo_sync_nodos()
        time.sleep(35)

threading.Thread(target=_latido_registro_tunel_en_render, name="sync-tunel-render", daemon=True).start()

class CambiarCargoTiempoRealReq(BaseModel):
    rol: str
    mentor_id: Optional[int] = None

def construir_libro_excel_completo(organizacion_id=None):
    """Construye un libro openpyxl profesional con 6 hojas, KPIs y gráficos nativos de mentores y aprendices"""
    now = datetime.now()
    wb = openpyxl.Workbook()

    # Estilos Corporativos
    fill_navy = PatternFill(start_color="0A192F", end_color="0A192F", fill_type="solid")
    fill_sub = PatternFill(start_color="0F273F", end_color="0F273F", fill_type="solid")
    fill_kpi = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    font_title = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    font_sub = Font(name="Segoe UI", size=9, italic=True, color="FFFFFF")
    font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    font_sec = Font(name="Segoe UI", size=11, bold=True, color="0A192F")
    font_kpi_num = Font(name="Segoe UI", size=16, bold=True, color="0A192F")
    font_kpi_lbl = Font(name="Segoe UI", size=9, bold=True, color="64748B")
    font_bold = Font(name="Segoe UI", size=9, bold=True)
    font_normal = Font(name="Segoe UI", size=9)

    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Filtrado por organización si aplica
    filtro_org_sql = " WHERE id = ?" if organizacion_id else ""
    filtro_org_u_sql = " WHERE organizacion_id = ?" if organizacion_id else ""
    params_org = (organizacion_id,) if organizacion_id else ()

    orgs = db.execute_query(f"SELECT id, nombre, tipo_organizacion, dominio_permitido, licencias_asignadas FROM organizaciones{filtro_org_sql}", params_org, fetchall=True) or []
    users = db.execute_query(f"SELECT id, nombre, correo, rol, organizacion_id, mentor_id, COALESCE(racha_semanas, 5) as racha, COALESCE(minutos_dedicados_totales, 180) as minutos FROM usuarios{filtro_org_u_sql}", params_org, fetchall=True) or []
    aprendices = [u for u in users if u.get("rol") in ("Aprendiz", "Estudiante")]
    mentores = [u for u in users if u.get("rol") == "Mentor"]
    cursos = db.execute_query("SELECT id, titulo, tipo_material, COALESCE(total_modulos, 3) as total_modulos, enlace_url FROM material_capacitacion", fetchall=True) or []
    progresos = db.execute_query("SELECT usuario_id, curso_id, porcentaje_avance, modulos_completados, tiempo_dedicado_minutos, estado FROM progreso_cursos", fetchall=True) or []
    quizzes = db.execute_query("SELECT id, mentor_id, organizacion_id, titulo, tipo, duracion_minutos, preguntas_json FROM quizzes_evaluaciones", fetchall=True) or []
    quizzes_prog = db.execute_query("SELECT quiz_id, aprendiz_id, calificacion, aprobado, tiempo_segundos FROM progreso_quizzes", fetchall=True) or []

    # -------------------------------------------------------------
    # HOJA 1: RESUMEN EJECUTIVO & TELEMETRÍA
    # -------------------------------------------------------------
    ws_res = wb.active
    ws_res.title = "Resumen & Métricas"
    ws_res.views.sheetView[0].showGridLines = True

    ws_res.merge_cells("A1:G1")
    t1 = ws_res["A1"]
    t1.value = "CENTRO DE MANDO EDTECH · REPORTE EJECUTIVO Y TELEMETRÍA DE PROCESOS"
    t1.font = font_title
    t1.fill = fill_navy
    t1.alignment = Alignment(horizontal="center", vertical="center")
    ws_res.row_dimensions[1].height = 36

    ws_res.merge_cells("A2:G2")
    sub1 = ws_res["A2"]
    org_tag = f" · {orgs[0]['nombre']}" if organizacion_id and orgs else " · Cobertura Global"
    sub1.value = f"Generado el {now.strftime('%d/%m/%Y a las %H:%M:%S')}{org_tag} · Métricas Certificadas"
    sub1.font = font_sub
    sub1.fill = fill_sub
    sub1.alignment = Alignment(horizontal="center", vertical="center")
    ws_res.row_dimensions[2].height = 20

    comp_count = sum(1 for p in progresos if float(p.get("porcentaje_avance", 0)) >= 80)
    prog_count = sum(1 for p in progresos if 0 < float(p.get("porcentaje_avance", 0)) < 80)
    noin_count = max(0, len(aprendices) * len(cursos) - comp_count - prog_count) if cursos else max(0, len(aprendices) - comp_count - prog_count)
    total_horas = round(sum(int(u.get("minutos", 0)) for u in users) / 60, 1)

    kpis = [
        ("Instituciones", len(orgs)),
        ("Estudiantes", len(aprendices)),
        ("Mentores Activos", len(mentores)),
        ("Horas de Estudio", total_horas),
        ("Cursos en Catálogo", len(cursos)),
        ("Quizzes Activos", len(quizzes))
    ]
    ws_res.row_dimensions[4].height = 18
    ws_res.row_dimensions[5].height = 28
    for col_i, (lbl, val) in enumerate(kpis, start=1):
        c_l = ws_res.cell(row=4, column=col_i, value=lbl)
        c_l.font = font_kpi_lbl
        c_l.fill = fill_kpi
        c_l.alignment = Alignment(horizontal="center", vertical="center")
        c_l.border = border_thin

        c_v = ws_res.cell(row=5, column=col_i, value=val)
        c_v.font = font_kpi_num
        c_v.fill = fill_kpi
        c_v.alignment = Alignment(horizontal="center", vertical="center")
        c_v.border = border_thin

    ws_res.cell(row=7, column=1, value="DESEMPEÑO Y AVANCE POR INSTITUCIÓN").font = font_sec
    headers_orgs = ["ID", "Institución", "Tipo", "Estudiantes", "Mentores", "Avance Promedio %"]
    ws_res.row_dimensions[8].height = 24
    for c_i, h in enumerate(headers_orgs, start=1):
        cell = ws_res.cell(row=8, column=c_i, value=h)
        cell.font = font_header
        cell.fill = fill_navy
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_thin

    r_org = 9
    for o in orgs:
        o_id = o["id"]
        c_apr = sum(1 for u in aprendices if u.get("organizacion_id") == o_id)
        c_men = sum(1 for u in mentores if u.get("organizacion_id") == o_id)
        u_ids = [u["id"] for u in aprendices if u.get("organizacion_id") == o_id]
        p_list = [float(p.get("porcentaje_avance", 0)) for p in progresos if p.get("usuario_id") in u_ids]
        prom_o = round(sum(p_list) / len(p_list), 1) if p_list else 0.0

        ws_res.cell(row=r_org, column=1, value=o_id).alignment = Alignment(horizontal="center")
        ws_res.cell(row=r_org, column=2, value=o.get("nombre", ""))
        ws_res.cell(row=r_org, column=3, value=o.get("tipo_organizacion", "")).alignment = Alignment(horizontal="center")
        ws_res.cell(row=r_org, column=4, value=c_apr).alignment = Alignment(horizontal="center")
        ws_res.cell(row=r_org, column=5, value=c_men).alignment = Alignment(horizontal="center")
        ws_res.cell(row=r_org, column=6, value=prom_o).alignment = Alignment(horizontal="center")

        for c in range(1, 7):
            ws_res.cell(row=r_org, column=c).border = border_thin
            ws_res.cell(row=r_org, column=c).font = font_normal
        r_org += 1

    total_r_orgs = max(r_org - 1, 9)
    if len(orgs) > 0:
        c_bar1 = BarChart()
        c_bar1.type = "col"
        c_bar1.style = 10
        c_bar1.title = "Avance Promedio (%) por Institución"
        c_bar1.y_axis.title = "% Avance"
        c_bar1.x_axis.title = "Institución"
        c_bar1.height = 10
        c_bar1.width = 15
        d_ref1 = Reference(ws_res, min_col=6, min_row=8, max_row=total_r_orgs)
        k_ref1 = Reference(ws_res, min_col=2, min_row=9, max_row=total_r_orgs)
        c_bar1.add_data(d_ref1, titles_from_data=True)
        c_bar1.set_categories(k_ref1)
        ws_res.add_chart(c_bar1, f"A{r_org + 2}")

    ws_res.cell(row=7, column=8, value="DISTRIBUCIÓN DE AVANCE").font = font_sec
    ws_res.cell(row=8, column=8, value="Estado").font = font_header
    ws_res.cell(row=8, column=8).fill = fill_navy
    ws_res.cell(row=8, column=9, value="Cantidad").font = font_header
    ws_res.cell(row=8, column=9).fill = fill_navy

    estados_datos = [
        ("Completados (≥80%)", comp_count),
        ("En Progreso (1-79%)", prog_count),
        ("No Iniciados (0%)", noin_count)
    ]
    for idx_e, (est_lbl, est_cnt) in enumerate(estados_datos, start=9):
        ws_res.cell(row=idx_e, column=8, value=est_lbl).border = border_thin
        ws_res.cell(row=idx_e, column=8).font = font_normal
        ws_res.cell(row=idx_e, column=9, value=est_cnt).border = border_thin
        ws_res.cell(row=idx_e, column=9).font = font_normal
        ws_res.cell(row=idx_e, column=9).alignment = Alignment(horizontal="center")

    c_pie1 = PieChart()
    c_pie1.title = "Distribución del Progreso"
    c_pie1.height = 10
    c_pie1.width = 13
    d_pie = Reference(ws_res, min_col=9, min_row=8, max_row=11)
    k_pie = Reference(ws_res, min_col=8, min_row=9, max_row=11)
    c_pie1.add_data(d_pie, titles_from_data=True)
    c_pie1.set_categories(k_pie)
    ws_res.add_chart(c_pie1, f"H{r_org + 2}")

    # -------------------------------------------------------------
    # HOJA 2: PROCESOS DE MENTORES (CON GRÁFICA DE MENTORES)
    # -------------------------------------------------------------
    ws_men = wb.create_sheet(title="Procesos Mentores")
    ws_men.views.sheetView[0].showGridLines = True
    ws_men.row_dimensions[1].height = 24
    m_headers = ["ID", "Mentor", "Correo", "Institución", "Aprendices a Cargo", "Tutoría (Horas)", "Quizzes Creados", "Avance Promedio Grupo %", "Tasa Finalización %"]
    for c_i, h in enumerate(m_headers, start=1):
        cell = ws_men.cell(row=1, column=c_i, value=h)
        cell.font = font_header
        cell.fill = fill_sub
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_thin

    r_men = 2
    for m in mentores:
        m_id = m["id"]
        apr_m = [a for a in aprendices if a.get("mentor_id") == m_id]
        apr_ids = [a["id"] for a in apr_m]
        p_apr_m = [float(p.get("porcentaje_avance", 0)) for p in progresos if p.get("usuario_id") in apr_ids]
        prom_m = round(sum(p_apr_m) / len(p_apr_m), 1) if p_apr_m else 0.0
        comp_m = sum(1 for p in p_apr_m if p >= 80)
        tasa_fin = round((comp_m / max(1, len(p_apr_m))) * 100, 1) if p_apr_m else 0.0
        q_creados = sum(1 for q in quizzes if q.get("mentor_id") == m_id)
        horas_tut = round(int(m.get("minutos", 120)) / 60, 1)
        org_n = next((o["nombre"] for o in orgs if o["id"] == m.get("organizacion_id")), "Global")

        ws_men.cell(row=r_men, column=1, value=m_id).alignment = Alignment(horizontal="center")
        ws_men.cell(row=r_men, column=2, value=m["nombre"]).font = font_bold
        ws_men.cell(row=r_men, column=3, value=m["correo"])
        ws_men.cell(row=r_men, column=4, value=org_n)
        ws_men.cell(row=r_men, column=5, value=len(apr_m)).alignment = Alignment(horizontal="center")
        ws_men.cell(row=r_men, column=6, value=horas_tut).alignment = Alignment(horizontal="center")
        ws_men.cell(row=r_men, column=7, value=q_creados).alignment = Alignment(horizontal="center")
        ws_men.cell(row=r_men, column=8, value=prom_m).alignment = Alignment(horizontal="center")
        ws_men.cell(row=r_men, column=9, value=tasa_fin).alignment = Alignment(horizontal="center")

        for c in range(1, 10):
            ws_men.cell(row=r_men, column=c).border = border_thin
            if c != 2:
                ws_men.cell(row=r_men, column=c).font = font_normal
        r_men += 1

    total_r_men = max(r_men - 1, 2)
    if len(mentores) > 0:
        c_bar_men = BarChart()
        c_bar_men.type = "col"
        c_bar_men.style = 11
        c_bar_men.title = "Avance Promedio (%) de Aprendices por Mentor Tutor"
        c_bar_men.y_axis.title = "% Avance Promedio"
        c_bar_men.x_axis.title = "Mentor"
        c_bar_men.height = 11
        c_bar_men.width = 17
        d_men = Reference(ws_men, min_col=8, min_row=1, max_row=total_r_men)
        k_men = Reference(ws_men, min_col=2, min_row=2, max_row=total_r_men)
        c_bar_men.add_data(d_men, titles_from_data=True)
        c_bar_men.set_categories(k_men)
        ws_men.add_chart(c_bar_men, f"A{r_men + 2}")

    # -------------------------------------------------------------
    # HOJA 3: PROCESOS DE APRENDICES (CON RANKING & HORAS)
    # -------------------------------------------------------------
    ws_apr = wb.create_sheet(title="Procesos Aprendices")
    ws_apr.views.sheetView[0].showGridLines = True
    ws_apr.row_dimensions[1].height = 24
    a_headers = ["Puesto", "Estudiante", "Correo", "Institución", "Mentor Tutor", "Avance Promedio %", "Módulos Aprobados", "Quizzes Rendidos", "Horas de Estudio", "Racha Semanal", "Estado Académico"]
    for c_i, h in enumerate(a_headers, start=1):
        cell = ws_apr.cell(row=1, column=c_i, value=h)
        cell.font = font_header
        cell.fill = fill_sub
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_thin

    ranking_apr = []
    for apr in aprendices:
        a_id = apr["id"]
        p_u = [p for p in progresos if p.get("usuario_id") == a_id]
        prom = round(sum(float(p_item.get("porcentaje_avance", 0)) for p_item in p_u) / len(p_u), 1) if p_u else 0.0
        mods = sum(int(p_item.get("modulos_completados", 0)) for p_item in p_u)
        q_u = [q for q in quizzes_prog if q.get("aprendiz_id") == a_id]
        q_count = len(q_u)
        horas = round(int(apr.get("minutos", 180)) / 60, 1)
        racha = apr.get("racha", 5)
        org_n = next((o["nombre"] for o in orgs if o["id"] == apr.get("organizacion_id")), "Sin Org")
        men_n = next((u["nombre"] for u in mentores if u["id"] == apr.get("mentor_id")), "Sin Tutor")
        estado_a = "Graduado / Aprobado" if prom >= 80 else ("En Progreso Activo" if prom > 0 else "Sin Iniciar")

        ranking_apr.append({
            "nombre": apr["nombre"],
            "correo": apr["correo"],
            "org": org_n,
            "mentor": men_n,
            "promedio": prom,
            "modulos": mods,
            "quizzes": q_count,
            "horas": horas,
            "racha": f"{racha} Semanas 🔥",
            "estado": estado_a
        })
    ranking_apr.sort(key=lambda x: (x["promedio"], x["modulos"], x["horas"]), reverse=True)

    r_apr = 2
    for idx_a, item in enumerate(ranking_apr, start=2):
        ws_apr.cell(row=idx_a, column=1, value=idx_a - 1).alignment = Alignment(horizontal="center")
        ws_apr.cell(row=idx_a, column=2, value=item["nombre"]).font = font_bold
        ws_apr.cell(row=idx_a, column=3, value=item["correo"])
        ws_apr.cell(row=idx_a, column=4, value=item["org"])
        ws_apr.cell(row=idx_a, column=5, value=item["mentor"])
        ws_apr.cell(row=idx_a, column=6, value=item["promedio"]).alignment = Alignment(horizontal="center")
        ws_apr.cell(row=idx_a, column=7, value=item["modulos"]).alignment = Alignment(horizontal="center")
        ws_apr.cell(row=idx_a, column=8, value=item["quizzes"]).alignment = Alignment(horizontal="center")
        ws_apr.cell(row=idx_a, column=9, value=item["horas"]).alignment = Alignment(horizontal="center")
        ws_apr.cell(row=idx_a, column=10, value=item["racha"]).alignment = Alignment(horizontal="center")
        ws_apr.cell(row=idx_a, column=11, value=item["estado"]).alignment = Alignment(horizontal="center")

        for c in range(1, 12):
            ws_apr.cell(row=idx_a, column=c).border = border_thin
            if c != 2:
                ws_apr.cell(row=idx_a, column=c).font = font_normal
        r_apr += 1

    # -------------------------------------------------------------
    # HOJA 4: QUIZZES Y EVALUACIONES
    # -------------------------------------------------------------
    ws_qz = wb.create_sheet(title="Quizzes & Evaluaciones")
    ws_qz.views.sheetView[0].showGridLines = True
    ws_qz.row_dimensions[1].height = 24
    q_headers = ["ID", "Título de la Evaluación", "Tipo", "Mentor Autor", "Duración (min)", "Total Preguntas", "Entregas Recibidas", "Promedio Calificación %"]
    for c_i, h in enumerate(q_headers, start=1):
        cell = ws_qz.cell(row=1, column=c_i, value=h)
        cell.font = font_header
        cell.fill = fill_navy
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_thin

    for idx_q, q in enumerate(quizzes, start=2):
        q_id = q["id"]
        men_n = next((m["nombre"] for m in mentores if m["id"] == q.get("mentor_id")), "Mentor General")
        try:
            preg_list = json.loads(q.get("preguntas_json") or "[]")
            c_preg = len(preg_list)
        except Exception:
            c_preg = 0
        resp_q = [rq for rq in quizzes_prog if rq.get("quiz_id") == q_id]
        prom_cal = round(sum(float(rq.get("calificacion", 0)) for rq in resp_q) / len(resp_q), 1) if resp_q else 0.0

        ws_qz.cell(row=idx_q, column=1, value=q_id).alignment = Alignment(horizontal="center")
        ws_qz.cell(row=idx_q, column=2, value=q["titulo"]).font = font_bold
        ws_qz.cell(row=idx_q, column=3, value=q.get("tipo", "Quiz")).alignment = Alignment(horizontal="center")
        ws_qz.cell(row=idx_q, column=4, value=men_n)
        ws_qz.cell(row=idx_q, column=5, value=q.get("duracion_minutos", 15)).alignment = Alignment(horizontal="center")
        ws_qz.cell(row=idx_q, column=6, value=c_preg).alignment = Alignment(horizontal="center")
        ws_qz.cell(row=idx_q, column=7, value=len(resp_q)).alignment = Alignment(horizontal="center")
        ws_qz.cell(row=idx_q, column=8, value=prom_cal).alignment = Alignment(horizontal="center")

        for c in range(1, 9):
            ws_qz.cell(row=idx_q, column=c).border = border_thin
            if c != 2:
                ws_qz.cell(row=idx_q, column=c).font = font_normal

    # -------------------------------------------------------------
    # HOJA 5: CATÁLOGO DE CONTENIDOS
    # -------------------------------------------------------------
    ws_cat = wb.create_sheet(title="Catálogo Cursos")
    ws_cat.views.sheetView[0].showGridLines = True
    c_headers = ["ID", "Título de la Colección", "Tipo", "Módulos", "Enlace Oficial Microsoft Learn"]
    ws_cat.row_dimensions[1].height = 24
    for c_i, h in enumerate(c_headers, start=1):
        cell = ws_cat.cell(row=1, column=c_i, value=h)
        cell.font = font_header
        cell.fill = fill_sub
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_thin

    for idx_c, cur in enumerate(cursos, start=2):
        ws_cat.cell(row=idx_c, column=1, value=cur["id"]).alignment = Alignment(horizontal="center")
        ws_cat.cell(row=idx_c, column=2, value=cur["titulo"]).font = font_bold
        ws_cat.cell(row=idx_c, column=3, value=cur.get("tipo_material", "Colección")).alignment = Alignment(horizontal="center")
        ws_cat.cell(row=idx_c, column=4, value=cur.get("total_modulos", 3)).alignment = Alignment(horizontal="center")
        ws_cat.cell(row=idx_c, column=5, value=cur.get("enlace_url", ""))
        for c in range(1, 6):
            ws_cat.cell(row=idx_c, column=c).border = border_thin
            if c != 2:
                ws_cat.cell(row=idx_c, column=c).font = font_normal

    # -------------------------------------------------------------
    # HOJA 6: REGISTRO DE ACTIVIDAD & AUDITORÍA
    # -------------------------------------------------------------
    ws_aud = wb.create_sheet(title="Registro Actividad")
    ws_aud.views.sheetView[0].showGridLines = True
    aud_headers = ["Fecha y Hora", "Usuario", "Módulo / Actividad", "Operación / Acción", "Estado", "Detalles"]
    ws_aud.row_dimensions[1].height = 24
    for c_i, h in enumerate(aud_headers, start=1):
        cell = ws_aud.cell(row=1, column=c_i, value=h)
        cell.font = font_header
        cell.fill = fill_sub
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_thin

    if os.path.isfile(CSV_AUDITORIA):
        try:
            with open(CSV_AUDITORIA, mode='r', encoding='utf-8') as f:
                lector = csv.DictReader(f)
                for idx_a, fila in enumerate(lector, start=2):
                    if idx_a > 500: break
                    ws_aud.cell(row=idx_a, column=1, value=fila.get("Fecha_Hora", ""))
                    ws_aud.cell(row=idx_a, column=2, value=fila.get("Correo_Usuario", ""))
                    ws_aud.cell(row=idx_a, column=3, value=fila.get("Modulo", ""))
                    ws_aud.cell(row=idx_a, column=4, value=fila.get("Operacion", ""))
                    ws_aud.cell(row=idx_a, column=5, value=fila.get("Estado", "")).alignment = Alignment(horizontal="center")
                    ws_aud.cell(row=idx_a, column=6, value=fila.get("Detalles_Error", ""))
                    for c in range(1, 7):
                        ws_aud.cell(row=idx_a, column=c).border = border_thin
                        ws_aud.cell(row=idx_a, column=c).font = font_normal
        except Exception as e_aud:
            print(f">> Error leyendo auditoria para excel: {e_aud}")

    # Autoajustar anchos de columnas en todas las hojas
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.value:
                    val_str = str(cell.value)
                    if len(val_str) > max_len and len(val_str) < 60:
                        max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    return wb

BANCO_TESTS_COLECCIONES = {
    "analisis_datos": {
        "id_tema": "analisis_datos",
        "titulo": "Evaluación: Análisis de Datos (ETL, Métricas y Visualización)",
        "duracion_minutos": 15,
        "descripcion": "Valida tus conocimientos fundamentales en extracción, transformación relacional, calidad del dato y visualización de métricas.",
        "preguntas": [
            {
                "id": 1,
                "pregunta": "¿Cuál es el primer paso crítico en el ciclo de vida del análisis de datos antes de construir cualquier reporte o modelo?",
                "opciones": [
                    {"id": "a", "texto": "Diseñar un dashboard con gráficos complejos"},
                    {"id": "b", "texto": "Extracción, exploración y limpieza de los datos (ETL)"},
                    {"id": "c", "texto": "Publicar conclusiones directas a la junta directiva"},
                    {"id": "d", "texto": "Eliminar todas las columnas que contengan texto"}
                ],
                "correcta": "b",
                "explicacion": "La fase de exploración, perfilado y limpieza (ETL) garantiza que los datos sean confiables, exactos y sin anomalías antes del análisis."
            },
            {
                "id": 2,
                "pregunta": "En bases de datos relacionales y SQL, ¿qué cláusula se utiliza para combinar registros de dos tablas basándose en una clave en común?",
                "opciones": [
                    {"id": "a", "texto": "INNER JOIN / LEFT JOIN"},
                    {"id": "b", "texto": "GROUP BY"},
                    {"id": "c", "texto": "ORDER BY DESC"},
                    {"id": "d", "texto": "DROP COLUMN"}
                ],
                "correcta": "a",
                "explicacion": "Las operaciones JOIN vinculan entidades relacionadas mediante claves primarias y foráneas para análisis cruzados."
            },
            {
                "id": 3,
                "pregunta": "¿Por qué la mediana suele ser preferible a la media (promedio) en presencia de valores atípicos (outliers)?",
                "opciones": [
                    {"id": "a", "texto": "Porque la mediana siempre es mayor que la media"},
                    {"id": "b", "texto": "Porque es una medida robusta que no se distorsiona por extremos atípicos"},
                    {"id": "c", "texto": "Porque la media solo se puede calcular en muestras impares"},
                    {"id": "d", "texto": "Son exactamente idénticas en cualquier distribución"}
                ],
                "correcta": "b",
                "explicacion": "La mediana representa el valor central ordenado, evitando el sesgo provocado por datos extremos que distorsionan el promedio."
            },
            {
                "id": 4,
                "pregunta": "¿Qué tipo de visualización es la más recomendada para mostrar la evolución o tendencia continua de una métrica a lo largo del tiempo?",
                "opciones": [
                    {"id": "a", "texto": "Gráfico circular o de pastel (pie chart) con 30 sectores"},
                    {"id": "b", "texto": "Gráfico de líneas temporales (time series)"},
                    {"id": "c", "texto": "Diagrama de Venn"},
                    {"id": "d", "texto": "Nube de palabras clave"}
                ],
                "correcta": "b",
                "explicacion": "Los gráficos de líneas conectan puntos temporales consecutivos, facilitando la identificación de patrones, tendencias y estacionalidades."
            },
            {
                "id": 5,
                "pregunta": "En gobernanza y analítica institucional, ¿qué significa el principio de 'Calidad del Dato' (Data Quality)?",
                "opciones": [
                    {"id": "a", "texto": "Al costo de la licencia del software de almacenamiento"},
                    {"id": "b", "texto": "A la exactitud, completitud, coherencia y validez de la información registrada"},
                    {"id": "c", "texto": "A poseer únicamente hojas de cálculo con más de un millón de registros"},
                    {"id": "d", "texto": "A impedir el acceso a cualquier usuario de la organización"}
                ],
                "correcta": "b",
                "explicacion": "La calidad del dato garantiza que las decisiones estratégicas se fundamenten en información verídica, consistente y verificada."
            }
        ]
    },
    "ia_responsable": {
        "id_tema": "ia_responsable",
        "titulo": "Evaluación: IA Responsable para Aprendices (Ética, Sesgos y Seguridad)",
        "duracion_minutos": 15,
        "descripcion": "Comprueba tu comprensión sobre justicia algorítmica, privacidad de datos, transparencia y buenas prácticas con IA generativa.",
        "preguntas": [
            {
                "id": 1,
                "pregunta": "En el marco ético de IA Responsable, ¿qué principio exige que los sistemas no discriminen y traten a todos los usuarios de forma equitativa?",
                "opciones": [
                    {"id": "a", "texto": "Equidad e Imparcialidad (Fairness)"},
                    {"id": "b", "texto": "Velocidad de procesamiento"},
                    {"id": "c", "texto": "Monetización de modelos"},
                    {"id": "d", "texto": "Automatización sin supervisión"}
                ],
                "correcta": "a",
                "explicacion": "La equidad previene la discriminación algorítmica por motivos de género, raza, estatus socioeconómico o edad."
            },
            {
                "id": 2,
                "pregunta": "¿Cuál es la causa principal del 'sesgo algorítmico' (algorithmic bias) en modelos de Machine Learning e Inteligencia Artificial?",
                "opciones": [
                    {"id": "a", "texto": "Una falla eléctrica en el centro de datos"},
                    {"id": "b", "texto": "Prejuicios o desbalances históricos presentes en los datos de entrenamiento"},
                    {"id": "c", "texto": "El uso de pantallas de baja resolución"},
                    {"id": "d", "texto": "La velocidad del procesador gráfico (GPU)"}
                ],
                "correcta": "b",
                "explicacion": "Los algoritmos aprenden de datos pasados; si los datos contienen disparidades o prejuicios, el modelo tenderá a reproducirlos si no se audita."
            },
            {
                "id": 3,
                "pregunta": "Como aprendiz, al utilizar herramientas de IA generativa (ChatGPT, Copilot, Gemini) para actividades académicas, ¿cuál es la conducta más ética?",
                "opciones": [
                    {"id": "a", "texto": "Copiar y pegar las respuestas directamente presentándolas como autoría propia"},
                    {"id": "b", "texto": "Usar la IA como asistente reflexivo, contrastar fuentes y declarar transparentemente su uso"},
                    {"id": "c", "texto": "Asumir que toda respuesta de la IA es 100% verídica sin necesidad de verificar"},
                    {"id": "d", "texto": "Compartir credenciales y contraseñas personales en las solicitudes"}
                ],
                "correcta": "b",
                "explicacion": "La integridad académica y la IA responsable requieren rigor crítico, verificación de hechos y atribución honesta."
            },
            {
                "id": 4,
                "pregunta": "¿A qué se refiere el principio de 'Transparencia y Explicabilidad' (Explainability) en soluciones de IA?",
                "opciones": [
                    {"id": "a", "texto": "A que el hardware sea transparente a la luz"},
                    {"id": "b", "texto": "A que los usuarios y auditores puedan entender la lógica y motivos detrás de una decisión del modelo"},
                    {"id": "c", "texto": "A que los modelos operen como una 'caja negra' indescifrable"},
                    {"id": "d", "texto": "A que el código no tenga comentarios ni documentación"}
                ],
                "correcta": "b",
                "explicacion": "La explicabilidad permite auditar decisiones de alto impacto y detectar razonamientos erróneos o alucinaciones del modelo."
            },
            {
                "id": 5,
                "pregunta": "En términos de privacidad y gobernanza, ¿qué precaución fundamental debe adoptar un estudiante con datos confidenciales?",
                "opciones": [
                    {"id": "a", "texto": "Subir bases de datos con información sensible o PII de compañeros a chatbots públicos"},
                    {"id": "b", "texto": "Anonimizar la información y nunca compartir secretos o datos sensibles en servicios de terceros"},
                    {"id": "c", "texto": "Desactivar la autenticación de dos factores (2FA)"},
                    {"id": "d", "texto": "Almacenar claves institucionales en documentos públicos de texto"}
                ],
                "correcta": "b",
                "explicacion": "La privacidad por diseño y la no difusión de datos sensibles protegen los derechos individuales y cumplen las normativas de protección de datos."
            }
        ]
    }
}

def obtener_test_para_curso(curso_id: int):
    c = db.execute_query("SELECT id, titulo, tipo_material FROM material_capacitacion WHERE id = ?", (curso_id,), fetchone=True)
    if not c:
        t = dict(BANCO_TESTS_COLECCIONES["analisis_datos"])
        t["curso_id"] = curso_id
        t["curso_titulo"] = "Evaluación Especializada"
        return t
    titulo_norm = c["titulo"].lower()
    if "responsable" in titulo_norm or "ética" in titulo_norm or "ia" in titulo_norm or "inteligencia" in titulo_norm:
        t = dict(BANCO_TESTS_COLECCIONES["ia_responsable"])
        t["curso_id"] = curso_id
        t["curso_titulo"] = c["titulo"]
        return t
    else:
        t = dict(BANCO_TESTS_COLECCIONES["analisis_datos"])
        t["curso_id"] = curso_id
        t["curso_titulo"] = c["titulo"]
        return t

class ColoresPersonalizadosReq(BaseModel):
    primario: Optional[str] = "#0a192f"
    acento: Optional[str] = "#06b6d4"
    fondo: Optional[str] = "#030712"

DISENOS_SUGERENCIAS_DEFAULT = [
    {
        "id": "estandar",
        "nombre": "Estándar Corporativo",
        "icono": "🏢",
        "descripcion": "Estilo base ejecutivo, azul oscuro y cian corporativo.",
        "tipo_base": "estandar",
        "color_gradiente": "from-[#0a192f] via-[#0f273f] to-[#00b4d8]"
    },
    {
        "id": "minimalista",
        "nombre": "Minimalista Limpio",
        "icono": "🤍",
        "descripcion": "Gris slate monocromático, sobrio y sin saturación visual.",
        "tipo_base": "minimalista",
        "color_gradiente": "from-slate-100 via-slate-200 to-slate-300"
    },
    {
        "id": "navidad",
        "nombre": "Navidad & Festividades",
        "icono": "🎄",
        "descripcion": "Ambiente invernal navideño con tonos esmeralda y rubí.",
        "tipo_base": "navidad",
        "color_gradiente": "from-red-900 via-emerald-950 to-slate-900"
    },
    {
        "id": "halloween",
        "nombre": "Noche de Halloween",
        "icono": "🎃",
        "descripcion": "Misterio nocturno en naranja calabaza y púrpura oscuro.",
        "tipo_base": "halloween",
        "color_gradiente": "from-amber-950 via-purple-950 to-slate-950"
    },
    {
        "id": "pascua",
        "nombre": "Pascua & Primavera",
        "icono": "🐰",
        "descripcion": "Colores pastel florales, frescura y energía primaveral.",
        "tipo_base": "pascua",
        "color_gradiente": "from-amber-200 via-teal-100 to-rose-200"
    },
    {
        "id": "superheroes",
        "nombre": "Superhéroes & Multiverso",
        "icono": "🦸",
        "descripcion": "Energía cósmica de cómics heroicos y contrastes épicos.",
        "tipo_base": "superheroes",
        "color_gradiente": "from-rose-900 via-blue-900 to-amber-700"
    },
    {
        "id": "galaxia",
        "nombre": "Galaxia & Nebulosa Profunda",
        "icono": "🌌",
        "descripcion": "Cielo estrellado estelar y misterio sideral infinito.",
        "tipo_base": "galaxia",
        "color_gradiente": "from-[#020617] via-indigo-950 to-purple-950"
    },
    {
        "id": "cyberpunk",
        "nombre": "Cyberpunk Synthwave",
        "icono": "🕹️",
        "descripcion": "Neón retrofuturista de videojuegos y mallas cibernéticas.",
        "tipo_base": "cyberpunk",
        "color_gradiente": "from-fuchsia-950 via-cyan-950 to-slate-950"
    }
]

class DisenosPersonalizadosReq(BaseModel):
    disenos: List[Dict[str, Any]]

def obtener_puerto_disponible(puerto_inicial=8080):
    for p in range(puerto_inicial, puerto_inicial + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', p))
                return p
            except OSError:
                continue
    return puerto_inicial

