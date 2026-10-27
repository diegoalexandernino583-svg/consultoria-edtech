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
from app.routers import auth, usuarios, aprendiz, organizaciones, seguridad

app = FastAPI(
    title="Consultoría EdTech - Centro de Comando Visual",
    description="SaaS modular para gestión de organizaciones, mentores, aprendices y auditoría en tiempo real",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)


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
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if path in (
        "/ping",
        "/api/ping",
        "/api/interno/puente-correo",
        "/api/interno/registrar-tunel",
        "/api/internal/smtp-relay",
        "/api/internal/registrar-tunel",
    ):
        return await call_next(request)

    es_estatico = path.startswith("/static/") or path.endswith(
        (".css", ".js", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2")
    )
    if es_estatico and request.method == "GET":
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    client_ip = obtener_ip_cliente(request)

    if client_ip in cache_ips_bloqueadas:
        if not path.startswith("/api/seguridad/desbloquear-ip"):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "ACCESO_BLOQUEADO_WAF",
                    "mensaje": "Tu dirección IP ha sido bloqueada permanentemente por el Firewall de Ciberseguridad de Consultoría EdTech debido a actividad sospechosa.",
                    "ip": client_ip,
                },
            )

    if path.lower() in RUTAS_HONEYPOT_BOTS:
        bloquear_ip_inmediatamente(client_ip, motivo=f"Bot escáner intentó acceder a ruta trampa honeypot: {path}")
        enviar_alerta_seguridad_critica(
            tipo_amenaza="BOT_ESCANER_HONEYPOT",
            ip=client_ip,
            detalles=f"Un bot automatizado o escáner intentó ingresar a la ruta señuelo '{path}'. La IP ha sido neutralizada y bloqueada de inmediato.",
            ruta=path,
            metodo=request.method,
        )
        return JSONResponse(
            status_code=403,
            content={"error": "BOT_DETECTED", "mensaje": "Solicitud neutralizada por WAF"},
        )

    user_agent = request.headers.get("User-Agent", "")
    if user_agent and RE_USER_AGENT_MALICIOSO.search(user_agent):
        bloquear_ip_inmediatamente(
            client_ip, motivo=f"Herramienta de ataque automatizada interceptada (UA: {user_agent[:60]})"
        )
        enviar_alerta_seguridad_critica(
            tipo_amenaza="HERRAMIENTA_ATAQUE_BOT",
            ip=client_ip,
            detalles=f"Se interceptó una herramienta de hacking automatizada (User-Agent: {user_agent}).",
            ruta=path,
            metodo=request.method,
        )
        return JSONResponse(
            status_code=403,
            content={"error": "HERRAMIENTA_MALICIOSA_BLOQUEADA", "mensaje": "Herramienta de escaneo prohibida."},
        )

    if not verificar_rate_limit_general(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "mensaje": "Límite de solicitudes por minuto excedido. Por favor espera unos momentos.",
            },
        )

    if request.url.query:
        query_str = unquote(request.url.query)
        amenaza_query, tipo_q = inspeccionar_payload_waf(query_str)
        if amenaza_query:
            bloquear_ip_inmediatamente(client_ip, motivo=f"Inyección WAF detectada en Query Params: {tipo_q}")
            enviar_alerta_seguridad_critica(
                tipo_amenaza=tipo_q,
                ip=client_ip,
                detalles=f"Se detectó un patrón de ataque en los parámetros de la URL: {query_str[:200]}",
                payload=query_str,
                ruta=path,
                metodo=request.method,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "WAF_PAYLOAD_BLOQUEADO",
                    "mensaje": f"Petición neutralizada por WAF. Ataque {tipo_q} bloqueado.",
                },
            )

    content_type = request.headers.get("content-type", "")
    if request.method in ["POST", "PUT", "PATCH"] and "multipart/form-data" not in content_type:
        try:
            body_bytes = await request.body()
            if body_bytes:
                body_str = body_bytes.decode("utf-8", errors="ignore")
                amenaza_body, tipo_b = inspeccionar_payload_waf(body_str)
                if amenaza_body:
                    bloquear_ip_inmediatamente(client_ip, motivo=f"Inyección WAF detectada en Body: {tipo_b}")
                    enviar_alerta_seguridad_critica(
                        tipo_amenaza=tipo_b,
                        ip=client_ip,
                        detalles=f"Se detectó un payload malicioso en el cuerpo HTTP: {body_str[:200]}",
                        payload=body_str,
                        ruta=path,
                        metodo=request.method,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "WAF_PAYLOAD_BLOQUEADO",
                            "mensaje": f"Petición neutralizada por WAF. Ataque {tipo_b} bloqueado.",
                        },
                    )

                async def receive():
                    return {"type": "http.request", "body": body_bytes}

                request._receive = receive
        except Exception:
            pass

    start_time = time.time()
    response = await call_next(request)
    duracion_ms = round((time.time() - start_time) * 1000, 2)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Server"] = "ConsultoriaEdTech-WAF/3.0"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    if not es_estatico and not path.startswith("/api/tiempo-real/pulso"):
        registrar_log_acceso(client_ip, request.method, path, response.status_code, duracion_ms, user_agent)

    return response


# Registro de Routers Modulares
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(aprendiz.router)
app.include_router(organizaciones.router)
app.include_router(seguridad.router)

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
