"""
app/middlewares/multitenant.py
Middleware de Seguridad, Forzado HTTPS y Aislamiento Multi-Tenant Estricto para FastAPI.
Valida tokens JWT, inyecta TenantContext y bloquea consultas cruzadas no autorizadas entre colegios/instituciones.
"""

from contextvars import ContextVar
import json
import logging
import re
from typing import Optional, Set
from fastapi import Request, status
from fastapi.responses import JSONResponse
import jwt
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("security.multitenant")

# Contexto de Tenant seguro para corrutinas asíncronas
tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_context", default=None)
user_context: ContextVar[Optional[dict]] = ContextVar("user_context", default=None)


class MultiTenantSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        jwt_secret_key: str = "CONSULTORIA_EDTECH_SECRET_2026_PROD_KEY",
        jwt_algorithm: str = "HS256",
        enforce_https: bool = False,
        public_paths: Optional[Set[str]] = None,
    ):
        super().__init__(app)
        self.jwt_secret = jwt_secret_key
        self.jwt_algorithm = jwt_algorithm
        self.enforce_https = enforce_https
        self.public_paths = public_paths or {
            "/",
            "/healthz",
            "/ping",
            "/api/ping",
            "/api/estado-servidor",
            "/api/tiempo-real/pulso",
            "/api/auth/login",
            "/api/auth/validar-sesion",
            "/api/auth/recuperar-password",
            "/api/organizaciones/listar-registro",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static",
            "/favicon.ico",
        }

    async def dispatch(self, request: Request, call_next):
        # 1. FORZADO DE HTTPS (Inspección de terminación TLS en Render / Cloudflare)
        proto = request.headers.get("X-Forwarded-Proto", request.url.scheme).lower()
        if self.enforce_https and proto != "https" and request.url.hostname not in ("localhost", "127.0.0.1"):
            secure_url = request.url.replace(scheme="https")
            return JSONResponse(
                status_code=status.HTTP_308_PERMANENT_REDIRECT,
                headers={"Location": str(secure_url)},
                content={"detail": "Upgrade to HTTPS required"}
            )

        path = request.url.path

        # 2. BYPASS CONTROLADO PARA RUTAS PÚBLICAS Y ARCHIVOS ESTÁTICOS
        es_estatico = path.startswith("/static") or path.endswith(
            (".css", ".js", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2")
        )
        if es_estatico or any(path == p or path.startswith(f"{p}/") for p in self.public_paths):
            response = await call_next(request)
            self._aplicar_cabeceras_hsts(response)
            return response

        # 3. EXTRACCIÓN Y VALIDACIÓN DE TOKEN JWT
        auth_header = request.headers.get("Authorization")
        token_payload = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                token_payload = jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=[self.jwt_algorithm],
                    options={"verify_exp": True}
                )
            except jwt.ExpiredSignatureError:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "TOKEN_EXPIRED", "detail": "La sesión de la institución ha expirado."}
                )
            except jwt.PyJWTError:
                # Si el token no es decodificable pero no es requerido por endpoint, continuamos
                token_payload = None

        # 4. EXTRACCIÓN Y VALIDACIÓN ANTI CROSS-TENANT
        if token_payload:
            token_tenant_id = str(token_payload.get("tenant_id") or token_payload.get("organizacion_id") or "")
            user_role = str(token_payload.get("rol", "")).upper()
            es_super_admin = "SUPER" in user_role

            if token_tenant_id and not es_super_admin:
                violacion = await self._verificar_violacion_cross_tenant(request, token_tenant_id)
                if violacion:
                    logger.critical(
                        f"🚨 [CROSS-TENANT VIOLATION] Usuario: {token_payload.get('sub')} "
                        f"Tenant: {token_tenant_id} intentó acceder a recursos ajenos en {path}."
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={
                            "error": "CROSS_TENANT_VIOLATION",
                            "detail": "Acceso denegado: Aislamiento institucional estricto. Intento de consulta cruzada detectado."
                        }
                    )

            t_token = tenant_context.set(token_tenant_id if token_tenant_id else None)
            u_token = user_context.set(token_payload)
            try:
                response = await call_next(request)
            finally:
                tenant_context.reset(t_token)
                user_context.reset(u_token)
        else:
            response = await call_next(request)

        self._aplicar_cabeceras_hsts(response)
        return response

    async def _verificar_violacion_cross_tenant(self, request: Request, tenant_esperado: str) -> bool:
        """Verifica que ningún parámetro o cabecera consulte un Tenant distinto al del token."""
        # A. Query Params
        for param_key in ("tenant_id", "colegio_id", "organizacion_id", "org_id"):
            val = request.query_params.get(param_key)
            if val and str(val).strip() != tenant_esperado:
                return True

        # B. Path segments
        path_matches = re.findall(r"/(?:colegios|tenants|organizaciones|instituciones)/([0-9]+)", request.url.path, re.IGNORECASE)
        for matched_id in path_matches:
            if str(matched_id).strip() != tenant_esperado:
                return True

        # C. Cabecera personalizada
        header_tenant = request.headers.get("X-Tenant-ID")
        if header_tenant and str(header_tenant).strip() != tenant_esperado:
            return True

        return False

    def _aplicar_cabeceras_hsts(self, response):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
