"""
app/middlewares/multitenant.py
Middleware de Seguridad Global, Forzado HTTPS y Aislamiento Multi-Tenant Estricto para FastAPI.
Valida tokens JWT, inyecta TenantContext, bloquea ataques de fuerza bruta (Rate Limiting),
garantiza aislamiento anti-cross-tenant e inyecta políticas de cabeceras HTTP de nivel bancario.
"""

from contextvars import ContextVar
import json
import logging
import os
import re
from typing import Optional, Set
from fastapi import Request, status
from fastapi.responses import JSONResponse
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from app.security import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    RolEnum,
    normalizar_rol,
    rate_limiter,
)

logger = logging.getLogger("security.multitenant")

# Contexto de Tenant seguro por corrutina asíncrona (thread-safe)
tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_context", default=None)
user_context: ContextVar[Optional[dict]] = ContextVar("user_context", default=None)


def obtener_tenant_actual() -> Optional[str]:
    """Retorna el Tenant_ID asociado a la petición en curso desde el ContextVar."""
    return tenant_context.get()


def obtener_usuario_contexto() -> Optional[dict]:
    """Retorna los datos del usuario autenticado en la petición en curso."""
    return user_context.get()


class MultiTenantSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        jwt_secret_key: Optional[str] = None,
        jwt_algorithm: Optional[str] = None,
        enforce_https: Optional[bool] = None,
        public_paths: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.jwt_secret = jwt_secret_key or JWT_SECRET_KEY
        self.jwt_algorithm = jwt_algorithm or JWT_ALGORITHM
        self.enforce_https = (
            enforce_https
            if enforce_https is not None
            else (os.getenv("ENFORCE_HTTPS", "false").lower() in ("1", "true", "yes"))
        )
        self.public_paths = public_paths or {
            "/",
            "/healthz",
            "/ping",
            "/api/ping",
            "/api/estado-servidor",
            "/api/tiempo-real/pulso",
            "/api/auth/iniciar-sesion",
            "/api/auth/iniciar-login",
            "/api/auth/login",
            "/api/auth/validar-sesion",
            "/api/auth/recuperar-password",
            "/api/organizaciones/listar-registro",
            "/api/organizaciones/listar",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static",
            "/favicon.ico",
        }

    async def dispatch(self, request: Request, call_next):
        client_ip = self._obtener_ip_real(request)
        path = request.url.path

        # 1. FORZADO ESTRICTO DE HTTPS (Redirección permanente 308 en proxies de producción)
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme).lower()
        if self.enforce_https and proto != "https" and request.url.hostname not in ("localhost", "127.0.0.1"):
            secure_url = request.url.replace(scheme="https")
            return JSONResponse(
                status_code=status.HTTP_308_PERMANENT_REDIRECT,
                headers={"Location": str(secure_url)},
                content={"detail": "Upgrade to HTTPS required by SaaS Security Policy"}
            )

        # 2. MITIGACIÓN DE FUERZA BRUTA & RATE LIMITING SOBRE RUTAS CRÍTICAS
        if path in ("/api/auth/login", "/api/auth/iniciar-sesion", "/api/auth/iniciar-login"):
            clave_rate = f"rl:auth:ip:{client_ip}"
            # Máximo 7 peticiones de login por minuto por IP para evitar ataques de diccionario
            if not rate_limiter.verificar_limite(clave_rate, max_peticiones=7, ventana_segundos=60, tiempo_penalizacion_seg=120):
                logger.warning(f"🚨 [RATE-LIMIT LOGIN EXCEEDED] IP: {client_ip} bloqueada temporalmente por intentos reiterados.")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": "120"},
                    content={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "detail": "Has superado el límite de intentos de inicio de sesión. Por seguridad, espera 2 minutos."
                    }
                )

        # 3. BYPASS PARA RUTAS PÚBLICAS Y ACTIVOS ESTÁTICOS
        es_estatico = path.startswith("/static") or path.endswith(
            (".css", ".js", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2")
        )
        if es_estatico or any(path == p or path.startswith(f"{p}/") for p in self.public_paths):
            response = await call_next(request)
            self._aplicar_cabeceras_seguridad(response)
            return response

        # 4. EXTRACCIÓN Y VALIDACIÓN DE TOKEN JWT
        auth_header = request.headers.get("Authorization")
        token_str = None
        if auth_header and auth_header.startswith("Bearer "):
            token_str = auth_header.split(" ", 1)[1].strip()
        elif "token" in request.query_params:
            token_str = request.query_params.get("token")

        token_payload = None
        if token_str:
            try:
                token_payload = jwt.decode(
                    token_str,
                    self.jwt_secret,
                    algorithms=[self.jwt_algorithm],
                    options={"verify_exp": True}
                )
            except jwt.ExpiredSignatureError:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "TOKEN_EXPIRED", "detail": "La sesión institucional ha expirado. Ingresa de nuevo."}
                )
            except jwt.PyJWTError:
                token_payload = None

        # 5. VALIDACIÓN Y AISLAMIENTO MULTI-TENANT (ANTI CROSS-TENANT)
        if token_payload:
            token_tenant_id = str(token_payload.get("tenant_id") or token_payload.get("organizacion_id") or "")
            user_role = normalizar_rol(token_payload.get("rol"))
            es_super_admin = user_role == RolEnum.SUPERADMIN.value

            # Si el usuario NO es Superadministrador, no puede consultar datos de otros tenants
            if token_tenant_id and not es_super_admin:
                violacion = await self._verificar_violacion_cross_tenant(request, token_tenant_id)
                if violacion:
                    logger.critical(
                        f"🚨 [CROSS-TENANT VIOLATION] Usuario {token_payload.get('correo')} "
                        f"(Tenant {token_tenant_id}) intentó violar el aislamiento en: {path}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "CROSS_TENANT_VIOLATION",
                            "detail": "Acceso denegado: Aislamiento institucional estricto. Intento de consulta cruzada detectado y neutralizado."
                        }
                    )

            # Inyectar en contextvars para consumo seguro en corrutinas
            t_token = tenant_context.set(token_tenant_id if token_tenant_id else None)
            u_token = user_context.set(token_payload)
            try:
                response = await call_next(request)
            finally:
                tenant_context.reset(t_token)
                user_context.reset(u_token)
        else:
            response = await call_next(request)

        # 6. INYECCIÓN DE CABECERAS DE SEGURIDAD ESTRICTAS
        self._aplicar_cabeceras_seguridad(response)
        return response

    async def _verificar_violacion_cross_tenant(self, request: Request, tenant_esperado: str) -> bool:
        """Verifica que ningún parámetro de URL o cabecera intente consultar otro Tenant."""
        # A. Inspeccionar Query Params
        for param_key in ("tenant_id", "colegio_id", "organizacion_id", "org_id", "institucion_id"):
            val = request.query_params.get(param_key)
            if val and str(val).strip() != tenant_esperado:
                return True

        # B. Inspeccionar segmentos de Path
        matches = re.findall(
            r"/(?:colegios|tenants|organizaciones|instituciones)/([0-9]+)",
            request.url.path,
            re.IGNORECASE
        )
        for matched_id in matches:
            if str(matched_id).strip() != tenant_esperado:
                return True

        # C. Inspeccionar cabecera personalizada X-Tenant-ID
        header_tenant = request.headers.get("X-Tenant-ID")
        if header_tenant and str(header_tenant).strip() != tenant_esperado:
            return True

        return False

    def _obtener_ip_real(self, request: Request) -> str:
        """Extrae la IP del cliente considerando proxies inversos (Cloudflare, Render)."""
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
        xf = request.headers.get("X-Forwarded-For")
        if xf:
            return xf.split(",")[0].strip()
        return request.client.host if request.client else "127.0.0.1"

    def _aplicar_cabeceras_seguridad(self, response):
        """Inyecta cabeceras HTTP de nivel bancario según estándares OWASP Top 10."""
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Server"] = "EducationTechnology-SaaS-WAF/3.0"
