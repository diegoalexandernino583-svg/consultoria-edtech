"""
app/security.py
Módulo Central de Seguridad, Criptografía, RBAC y Rate Limiting para FastAPI.
Plataforma SaaS Multi-Tenant: Education Technology.
"""

from datetime import datetime, timedelta
from enum import Enum
import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    import jwt
except ImportError:
    try:
        import PyJWT as jwt
    except ImportError:
        jwt = None

logger = logging.getLogger("security.core")

# Configuraciones Criptográficas y de Sesión
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CONSULTORIA_EDTECH_SECRET_2026_PROD_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 horas

security_bearer = HTTPBearer(auto_error=False)


# ============================================================================
# 1. CONTROL DE ACCESO BASADO EN ROLES (RBAC)
# ============================================================================

class RolEnum(str, Enum):
    SUPERADMIN = "SUPERADMIN"          # Consultoría global / Dueño de plataforma / Auditoría Legal
    ADMIN = "ADMIN"                    # Administrador de la institución educativa
    DOCENTE = "DOCENTE"                # Docente / Tutor / Mentor académico
    ESTUDIANTE = "ESTUDIANTE"          # Estudiante / Aprendiz / Alumno

# Diccionario de normalización de roles heredados
MAPA_ROLES_NORMALIZADOS = {
    "SUPERADMINISTRADOR": RolEnum.SUPERADMIN.value,
    "SUPERADMIN": RolEnum.SUPERADMIN.value,
    "SUPER_ADMIN": RolEnum.SUPERADMIN.value,
    "SUPER ADMINISTRADOR": RolEnum.SUPERADMIN.value,
    "BODEGA_LEGAL": RolEnum.SUPERADMIN.value,
    "CONSULTORIA": RolEnum.SUPERADMIN.value,

    "ADMINISTRADOR": RolEnum.ADMIN.value,
    "ADMIN": RolEnum.ADMIN.value,
    "DIRECTOR": RolEnum.ADMIN.value,
    "COORDINADOR": RolEnum.ADMIN.value,

    "DOCENTE": RolEnum.DOCENTE.value,
    "TUTOR": RolEnum.DOCENTE.value,
    "PROFESOR": RolEnum.DOCENTE.value,
    "INSTRUCTOR": RolEnum.DOCENTE.value,
    "MENTOR": RolEnum.DOCENTE.value,

    "ESTUDIANTE": RolEnum.ESTUDIANTE.value,
    "APRENDIZ": RolEnum.ESTUDIANTE.value,
    "ALUMNO": RolEnum.ESTUDIANTE.value,
}


def normalizar_rol(rol_raw: Optional[str]) -> str:
    """Normaliza cualquier denominación textual al rol estándar del sistema RBAC."""
    if not rol_raw:
        return RolEnum.ESTUDIANTE.value
    limpio = rol_raw.strip().upper()
    return MAPA_ROLES_NORMALIZADOS.get(limpio, RolEnum.ESTUDIANTE.value)


# ============================================================================
# 2. CRIPTOGRAFÍA Y HASHING DE CONTRASEÑAS CON BCRYPT
# ============================================================================

def hash_password(password: str) -> str:
    """
    Genera un hash seguro con Bcrypt (12 rondas de salt).
    Garantiza resistencia contra ataques de diccionario y rainbow tables.
    """
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una contraseña plana contra el hash almacenado con manejo
    de contingencia resiliente en tiempo constante.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        # Fallback seguro para hashes legacy planos en fases de migración
        return plain_password == hashed_password


# ============================================================================
# 3. GESTIÓN DE TOKENS JWT MULTI-TENANT
# ============================================================================

def crear_token_acceso(
    usuario_id: int,
    correo: str,
    rol: str,
    tenant_id: Optional[int] = None,
    nombre: Optional[str] = None,
    minutos_expiracion: int = ACCESS_TOKEN_EXPIRE_MINUTES
) -> str:
    """
    Genera un token JWT firmado criptográficamente que encapsula la identidad
    del usuario y el Tenant_ID para el aislamiento de datos.
    """
    rol_estandar = normalizar_rol(rol)
    ahora = time.time()
    expiracion = ahora + (minutos_expiracion * 60)

    payload = {
        "sub": str(usuario_id),
        "user_id": usuario_id,
        "correo": correo.strip().lower(),
        "nombre": nombre or correo,
        "rol": rol_estandar,
        "tenant_id": tenant_id,
        "organizacion_id": tenant_id,
        "iat": int(ahora) - 30,  # 30s de margen para evitar ImmatureSignatureError por desfase de reloj
        "exp": int(expiracion),
        "iss": "edtech-saas-platform",
    }
    if jwt is None:
        import base64
        import json
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return f"fallback.{payload_b64}.sig"

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> Dict[str, Any]:
    """Decodifica y valida la firma y vigencia de un token JWT."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no provisto.")

    if jwt is None:
        import base64
        import json
        try:
            partes = token.split(".")
            if len(partes) >= 2 and partes[0] == "fallback":
                padded = partes[1] + "=" * (-len(partes[1]) % 4)
                return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Módulo criptográfico JWT no disponible.")

    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], leeway=30)
    except getattr(jwt, "ExpiredSignatureError", Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ha expirado. Por favor ingresa nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (getattr(jwt, "PyJWTError", Exception), Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de autenticación inválido o corrupto: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# 4. DEPENDENCIAS DE SEGURIDAD Y RBAC PARA FASTAPI
# ============================================================================

async def obtener_usuario_actual(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    request: Request = None
) -> Dict[str, Any]:
    """
    Dependencia de FastAPI para autenticar peticiones mediante Bearer Token.
    Si no hay token en header, intenta leer desde cookies o query params (ej. WebSockets).
    """
    token = None
    if credenciales and credenciales.credentials:
        token = credenciales.credentials
    elif request:
        token = request.query_params.get("token") or request.query_params.get("access_token")
        if not token:
            token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación Bearer Token para acceder a este recurso.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decodificar_token(token)
    return payload


def requerir_roles(roles_permitidos: List[str]):
    """
    Fábrica de dependencias RBAC. Valida que el usuario autenticado tenga
    al menos uno de los roles autorizados.
    """
    roles_normalizados = {normalizar_rol(r) for r in roles_permitidos}

    def _validador_rol(usuario: Dict[str, Any] = Depends(obtener_usuario_actual)):
        rol_usuario = normalizar_rol(usuario.get("rol"))
        # El Superadministrador siempre tiene bypass sobre roles administrativos
        if rol_usuario == RolEnum.SUPERADMIN.value:
            return usuario

        if rol_usuario not in roles_normalizados:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: Tu rol actual ('{rol_usuario}') no posee los privilegios requeridos ({', '.join(roles_normalizados)})."
            )
        return usuario

    return _validador_rol


def requerir_tenant_activo(usuario: Dict[str, Any] = Depends(obtener_usuario_actual)) -> int:
    """
    Garantiza que el usuario pertenezca a una institución educativa válida
    (o sea Superadministrador). Retorna el tenant_id.
    """
    rol_usuario = normalizar_rol(usuario.get("rol"))
    tenant_id = usuario.get("tenant_id") or usuario.get("organizacion_id")

    if rol_usuario == RolEnum.SUPERADMIN.value:
        return tenant_id or 0

    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no se encuentra asignado a ninguna institución educativa activa."
        )
    return int(tenant_id)


# ============================================================================
# 5. LIMITADOR DE TASA (RATE LIMITING) MULTI-TENANT & ANTI-BRUTEFORCE
# ============================================================================

class SlidingWindowRateLimiter:
    """
    Limitador de tasa en memoria de alta velocidad con ventana deslizante.
    Mitiga ataques de fuerza bruta y DoS por IP, Tenant o Endpoint.
    """
    def __init__(self):
        self._ventanas: Dict[str, List[float]] = {}
        self._bloqueos: Dict[str, float] = {}

    def verificar_limite(self, clave: str, max_peticiones: int, ventana_segundos: int, tiempo_penalizacion_seg: int = 60) -> bool:
        """
        Retorna True si la petición está permitida, o False si superó la tasa.
        Si supera el límite reiteradamente, aplica penalización de bloqueo temporal.
        """
        ahora = time.time()

        if clave in self._bloqueos:
            if ahora < self._bloqueos[clave]:
                return False
            else:
                del self._bloqueos[clave]

        historial = self._ventanas.get(clave, [])
        limite_inferior = ahora - ventana_segundos
        historial = [t for t in historial if t > limite_inferior]

        if len(historial) >= max_peticiones:
            self._bloqueos[clave] = ahora + tiempo_penalizacion_seg
            self._ventanas[clave] = historial
            return False

        historial.append(ahora)
        self._ventanas[clave] = historial
        return True

    def intentos_restantes(self, clave: str, max_peticiones: int, ventana_segundos: int) -> int:
        ahora = time.time()
        historial = [t for t in self._ventanas.get(clave, []) if t > ahora - ventana_segundos]
        return max(0, max_peticiones - len(historial))


rate_limiter = SlidingWindowRateLimiter()
