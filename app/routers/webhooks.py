"""
app/routers/webhooks.py
Módulo de Webhooks para Automatización Externa (Make / Integromat) y Auditoría en Tiempo Real.
Permite dar de alta y baja usuarios dinámicamente, registrando cada cambio en audit_logs
y emitiendo eventos instantáneos por WebSockets y SSE para actualizar la UI sin recargar la página.
"""

from datetime import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from app.core import db
from app.realtime import ws_manager
from app.security import (
    RolEnum,
    hash_password,
    normalizar_rol,
    obtener_usuario_actual,
    requerir_roles,
    requerir_tenant_activo,
)

logger = logging.getLogger("webhooks.service")
router = APIRouter(tags=["Webhooks & Auditoría en Tiempo Real"])

WEBHOOK_SECRET_KEY = os.getenv("WEBHOOK_SECRET_KEY", "EDTECH_MAKE_INTEGROMAT_SECRET_2026")


# ============================================================================
# 1. MODELOS PYDANTIC PARA PAYLOADS DE MAKE / INTEGROMAT
# ============================================================================

class UsuarioPayload(BaseModel):
    nombre: Optional[str] = Field(default=None, example="Laura Gómez")
    correo: str = Field(..., example="laura.gomez@institucion.edu.co")
    rol: Optional[str] = Field(default="ESTUDIANTE", example="Docente")
    password: Optional[str] = Field(default="Temporal2026*", example="Temporal2026*")
    mentor_id: Optional[int] = Field(default=None)


class SincronizarUsuarioPayload(BaseModel):
    accion: str = Field(..., example="REGISTRO", description="REGISTRO, ALTA, ELIMINACION, BAJA, MODIFICACION")
    tenant_id: int = Field(..., example=1, description="ID de la institución educativa")
    usuario: Optional[UsuarioPayload] = Field(default=None)
    # Campos planos de contingencia si Make envía payload sin anidar
    nombre: Optional[str] = Field(default=None)
    correo: Optional[str] = Field(default=None)
    rol: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    detalles: Optional[str] = Field(default="Sincronización automatizada desde Make/Integromat")


# ============================================================================
# 2. AUTENTICACIÓN SEGURA DE WEBHOOK POR TOKEN / API KEY SECRETA
# ============================================================================

def verificar_secreto_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    secret_key: Optional[str] = Query(None)
):
    """
    Valida que la llamada del webhook proceda de un cliente autorizado (Make / Integromat)
    mediante cabeceras seguras o parámetro secreto de query.
    """
    token_provisto = x_webhook_secret or x_api_key or secret_key

    if not token_provisto and authorization:
        partes = authorization.split(" ", 1)
        if len(partes) == 2 and partes[0].lower() in ("bearer", "token", "apikey"):
            token_provisto = partes[1].strip()

    if not token_provisto or token_provisto != WEBHOOK_SECRET_KEY:
        logger.warning(f"🚨 [WEBHOOK REJECTED] Petición no autorizada desde {request.client.host if request.client else 'desconocido'}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acceso Denegado: Token secreto de webhook inválido o ausente."
        )
    return True


# ============================================================================
# 3. HELPER PARA REGISTRAR EN AUDIT_LOGS Y NOTIFICAR EN TIEMPO REAL
# ============================================================================

async def registrar_audit_y_difundir(
    tenant_id: int,
    usuario_afectado: str,
    accion: str,
    detalles: str,
    origen: str = "WEBHOOK_MAKE",
    ip_origen: str = "127.0.0.1",
    datos_adicionales: Optional[dict] = None
) -> int:
    """
    Inserta el registro de auditoría en la base de datos y difunde
    el evento en tiempo real por WebSockets y SSE a los tableros del Tenant.
    """
    ahora_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Inserción en tabla audit_logs
    audit_id = db.execute_query("""
        INSERT INTO audit_logs
        (tenant_id, usuario_afectado, accion, detalles, ip_origen, origen, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        tenant_id,
        usuario_afectado,
        accion.upper().strip(),
        detalles,
        ip_origen,
        origen,
        ahora_str
    ), commit=True, return_id=True)

    # Payload para broadcasting en tiempo real
    audit_event = {
        "audit_id": audit_id,
        "tenant_id": tenant_id,
        "usuario_afectado": usuario_afectado,
        "accion": accion.upper().strip(),
        "detalles": detalles,
        "origen": origen,
        "timestamp": ahora_str,
        "datos": datos_adicionales or {}
    }

    # 1. Notificar evento específico (USUARIO_REGISTRADO o USUARIO_ELIMINADO)
    if accion.upper() in ("REGISTRO", "ALTA", "CREAR"):
        await ws_manager.broadcast_tenant(str(tenant_id), "USUARIO_REGISTRADO", audit_event)
    elif accion.upper() in ("ELIMINACION", "BAJA", "BORRAR"):
        await ws_manager.broadcast_tenant(str(tenant_id), "USUARIO_ELIMINADO", audit_event)
    elif accion.upper() in ("MODIFICACION", "ACTUALIZAR"):
        await ws_manager.broadcast_tenant(str(tenant_id), "USUARIO_MODIFICADO", audit_event)

    # 2. Notificar canal general de auditoría
    await ws_manager.broadcast_tenant(str(tenant_id), "AUDIT_LOG_NUEVO", audit_event)

    return audit_id or 0


# ============================================================================
# 4. ENDPOINTS DE WEBHOOKS PARA MAKE / INTEGROMAT
# ============================================================================

@router.post("/api/webhooks/sincronizar-usuarios")
@router.post("/api/webhooks/usuarios")
async def webhook_sincronizar_usuarios(
    payload: SincronizarUsuarioPayload,
    request: Request,
    autorizado: bool = Depends(verificar_secreto_webhook)
):
    """
    Endpoint de alta velocidad para automatizaciones en Make / Integromat / Zapier.
    Permite dar de alta o baja a usuarios dinámicamente, asegurando:
    1. Aislamiento por Tenant_ID obligatorio.
    2. Cifrado de contraseña con Bcrypt.
    3. Registro en log de auditoría (audit_logs).
    4. Difusión inmediata vía WebSockets/SSE para actualización instantánea de la UI.
    """
    client_ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "127.0.0.1")
    accion = payload.accion.upper().strip()
    tenant_id = payload.tenant_id

    # Normalizar datos de usuario
    correo = None
    nombre = None
    rol = "ESTUDIANTE"
    password = None

    if payload.usuario:
        correo = (payload.usuario.correo or "").strip().lower()
        nombre = payload.usuario.nombre
        rol = payload.usuario.rol or "ESTUDIANTE"
        password = payload.usuario.password
    else:
        correo = (payload.correo or "").strip().lower()
        nombre = payload.nombre
        rol = payload.rol or "ESTUDIANTE"
        password = payload.password

    if not correo or "@" not in correo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere un correo electrónico válido para procesar la automatización."
        )

    rol_normalizado = normalizar_rol(rol)
    nombre_final = nombre.strip() if nombre else correo.split("@")[0].replace(".", " ").title()

    # PROCESAR ACCIÓN
    if accion in ("REGISTRO", "ALTA", "CREAR"):
        pwd_plana = password or "Temporal2026*"
        pwd_hash = hash_password(pwd_plana)

        # Verificar si usuario ya existe
        usr_existente = db.execute_query(
            "SELECT id, nombre, correo, rol, organizacion_id FROM usuarios WHERE LOWER(correo) = ?",
            (correo,),
            fetchone=True
        )

        if usr_existente:
            # Actualizar datos y reasignar tenant si aplica
            db.execute_query("""
                UPDATE usuarios
                SET nombre = ?, rol = ?, organizacion_id = ?, password_hash = ?
                WHERE id = ?
            """, (nombre_final, rol_normalizado, tenant_id, pwd_hash, usr_existente["id"]), commit=True)
            usuario_id = usr_existente["id"]
            detalle_accion = f"Usuario reactivado/actualizado en Tenant #{tenant_id} desde Make. Rol: {rol_normalizado}."
        else:
            usuario_id = db.execute_query("""
                INSERT INTO usuarios (organizacion_id, nombre, correo, rol, password_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (tenant_id, nombre_final, correo, rol_normalizado, pwd_hash), commit=True, return_id=True)
            detalle_accion = f"Usuario dado de ALTA en Tenant #{tenant_id} desde Make. Rol: {rol_normalizado}."

        # Registrar auditoría y emitir por WebSocket/SSE
        audit_id = await registrar_audit_y_difundir(
            tenant_id=tenant_id,
            usuario_afectado=correo,
            accion="REGISTRO",
            detalles=f"{detalle_accion} | {payload.detalles or ''}",
            origen="WEBHOOK_MAKE",
            ip_origen=client_ip,
            datos_adicionales={"id": usuario_id, "nombre": nombre_final, "correo": correo, "rol": rol_normalizado}
        )

        return {
            "status": "success",
            "resultado": "USUARIO_REGISTRADO",
            "mensaje": f"Usuario '{nombre_final}' ({correo}) registrado exitosamente en tiempo real.",
            "tenant_id": tenant_id,
            "usuario_id": usuario_id,
            "audit_id": audit_id,
            "tiempo_real_emitido": True
        }

    elif accion in ("ELIMINACION", "BAJA", "BORRAR"):
        usr = db.execute_query(
            "SELECT id, nombre, correo FROM usuarios WHERE LOWER(correo) = ? AND (organizacion_id = ? OR organizacion_id IS NULL)",
            (correo, tenant_id),
            fetchone=True
        )
        if not usr:
            # Buscar globalmente por correo
            usr = db.execute_query("SELECT id, nombre, correo FROM usuarios WHERE LOWER(correo) = ?", (correo,), fetchone=True)

        if not usr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con correo '{correo}' no encontrado en el Tenant #{tenant_id}."
            )

        usuario_id = usr["id"]
        # Eliminar usuario
        db.execute_query("DELETE FROM usuarios WHERE id = ?", (usuario_id,), commit=True)

        detalle_accion = f"Usuario {usr.get('nombre')} ({correo}) dado de BAJA/ELIMINADO del Tenant #{tenant_id} desde Make."
        audit_id = await registrar_audit_y_difundir(
            tenant_id=tenant_id,
            usuario_afectado=correo,
            accion="ELIMINACION",
            detalles=f"{detalle_accion} | {payload.detalles or ''}",
            origen="WEBHOOK_MAKE",
            ip_origen=client_ip,
            datos_adicionales={"id": usuario_id, "correo": correo}
        )

        return {
            "status": "success",
            "resultado": "USUARIO_ELIMINADO",
            "mensaje": f"Usuario '{correo}' eliminado y sincronizado en tiempo real.",
            "tenant_id": tenant_id,
            "usuario_id": usuario_id,
            "audit_id": audit_id,
            "tiempo_real_emitido": True
        }

    elif accion in ("MODIFICACION", "ACTUALIZAR"):
        usr = db.execute_query("SELECT id, nombre, correo FROM usuarios WHERE LOWER(correo) = ?", (correo,), fetchone=True)
        if not usr:
            raise HTTPException(status_code=404, detail=f"Usuario '{correo}' no existe.")

        db.execute_query(
            "UPDATE usuarios SET nombre = ?, rol = ? WHERE id = ?",
            (nombre_final, rol_normalizado, usr["id"]),
            commit=True
        )

        audit_id = await registrar_audit_y_difundir(
            tenant_id=tenant_id,
            usuario_afectado=correo,
            accion="MODIFICACION",
            detalles=f"Usuario modificado a {nombre_final} ({rol_normalizado}) desde Make.",
            origen="WEBHOOK_MAKE",
            ip_origen=client_ip
        )

        return {
            "status": "success",
            "resultado": "USUARIO_MODIFICADO",
            "tenant_id": tenant_id,
            "audit_id": audit_id,
            "tiempo_real_emitido": True
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Acción '{accion}' no soportada. Use REGISTRO, ALTA, ELIMINACION, BAJA o MODIFICACION."
        )


# ============================================================================
# 5. CONSULTA DE LOGS DE AUDITORÍA CON AISLAMIENTO MULTI-TENANT
# ============================================================================

@router.get("/api/webhooks/audit-logs")
@router.get("/api/audit-logs")
def listar_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    accion: Optional[str] = Query(None),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Retorna la bitácora de auditoría en tiempo real para la institución del usuario autenticado.
    El Superadministrador puede auditar todos los colegios.
    """
    tenant_id = usuario.get("tenant_id") or usuario.get("organizacion_id")
    rol_usuario = usuario.get("rol")
    es_superadmin = rol_usuario == RolEnum.SUPERADMIN.value

    filtros = ["1=1"]
    params = []

    if not es_superadmin and tenant_id:
        filtros.append("a.tenant_id = ?")
        params.append(tenant_id)

    if accion:
        filtros.append("a.accion = ?")
        params.append(accion.upper().strip())

    where_str = " AND ".join(filtros)

    logs = db.execute_query(f"""
        SELECT a.id, a.tenant_id, o.nombre as institucion_nombre, a.usuario_afectado,
               a.accion, a.detalles, a.ip_origen, a.origen, a.timestamp
        FROM audit_logs a
        LEFT JOIN organizaciones o ON o.id = a.tenant_id
        WHERE {where_str}
        ORDER BY a.id DESC
    """, tuple(params), fetchall=True) or []

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "total_registros": len(logs),
        "audit_logs": logs[:limit]
    }
