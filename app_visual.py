"""
Punto de entrada principal de la aplicación FastAPI - Consultoría EdTech.
Responsable únicamente de la inicialización de la app, configuración de CORS/Middleware,
registro de APIRouters modulares y montaje de archivos estáticos.
"""
import os
import time
import webbrowser
import threading
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import app.core as core
import database
import models
from app.core import (
    BASE_DIR,
    db,
    cache_ips_bloqueadas,
    RUTAS_HONEYPOT_BOTS,
    RE_USER_AGENT_MALICIOSO,
    obtener_ip_cliente,
    bloquear_ip_inmediatamente,
    enviar_alerta_seguridad_critica,
    verificar_rate_limit_general,
    inspeccionar_payload_waf,
    registrar_log_acceso,
    obtener_puerto_disponible,
    obtener_ip_local,
    iniciar_tunel_cloudflare,
)
from app.routers import auth, usuarios, aprendiz, organizaciones, seguridad, videojuego, realtime, webhooks
from app.middlewares.multitenant import MultiTenantSecurityMiddleware

app = FastAPI(
    title="Consultoría EdTech - Centro de Comando Visual",
    description="SaaS modular para gestión de organizaciones, mentores, aprendices y auditoría en tiempo real",
    version="3.0.0",
)

# Configuración de CORS con disponibilidad total (sin bloqueos de origen)
ALLOWED_ORIGINS = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    MultiTenantSecurityMiddleware,
    jwt_secret_key=os.getenv("JWT_SECRET_KEY", "CONSULTORIA_EDTECH_SECRET_2026_PROD_KEY"),
    enforce_https=False,
)


@app.exception_handler(core.HTTPException)
async def custom_http_exception_handler(request: Request, exc: core.HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "detail": str(exc.detail),
            "mensaje": str(exc.detail),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f">> [ERROR GLOBAL API] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "detail": f"Error interno del servidor: {str(exc)}",
            "mensaje": f"Error interno del servidor: {str(exc)}",
        },
    )


@app.middleware("http")
async def security_and_waf_middleware(request: Request, call_next):
    # Modo abierto y estable: sin bloqueos de IP, sin lista blanca restrictiva, disponibilidad total
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    client_ip = obtener_ip_cliente(request)

    start_time = time.time()
    response = await call_next(request)
    duracion_ms = round((time.time() - start_time) * 1000, 2)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Server"] = "ConsultoriaEdTech/3.5"

    es_estatico = path.startswith("/static/") or path.endswith(
        (".css", ".js", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2")
    )
    if not es_estatico and not path.startswith("/api/tiempo-real/pulso"):
        user_agent = request.headers.get("User-Agent", "")
        registrar_log_acceso(client_ip, request.method, path, response.status_code, duracion_ms, user_agent)

    return response

    return response


# Registro de Routers Modulares
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(aprendiz.router)
app.include_router(organizaciones.router)
app.include_router(seguridad.router)
app.include_router(videojuego.router)
app.include_router(realtime.router)
app.include_router(webhooks.router)

# Montaje de Frontend Estático
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.api_route("/", methods=["GET", "HEAD"])
def servir_interfaz():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "running", "mensaje": "Interfaz disponible en /static"}


@app.api_route("/index.html", methods=["GET", "HEAD"])
def servir_index_directo():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "error", "mensaje": "No se encontró index.html"}


if __name__ == "__main__":
    import uvicorn

    PUERTO = obtener_puerto_disponible(8080)
    core.PUERTO_ACTUAL = PUERTO
    ip_lan = obtener_ip_local()

    if not os.getenv("RENDER"):
        iniciar_tunel_cloudflare(PUERTO)

    print("\n" + "=" * 65)
    print(">>> CENTRO DE COMANDO VISUAL - CONSULTORIA EDTECH v3.0 (MODULAR)")
    print("=" * 65)
    print(f">> Acceso Local:      http://localhost:{PUERTO}")
    print(f">> Acceso Red Wi-Fi:  http://{ip_lan}:{PUERTO}")
    print(f">> Modo Base Datos:   {'Azure SQL' if db.use_azure else 'Motor Resiliente Activo'}")
    print("=" * 65 + "\n")

    def abrir_navegador():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{PUERTO}")

    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PUERTO, reload=False)
