"""
app/realtime.py
Capa de Comunicación Asíncrona en Tiempo Real: WebSockets y Server-Sent Events (SSE).
Permite la sincronización instantánea de tableros de logística y notas entre clientes
con estricto aislamiento por Tenant_ID (ningún colegio ve eventos de otro).
"""

import asyncio
from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.core import db
from app.security import (
    RolEnum,
    decodificar_token,
    obtener_usuario_actual,
    requerir_roles,
    requerir_tenant_activo,
)

logger = logging.getLogger("realtime.service")
router = APIRouter(prefix="/api/realtime", tags=["Sincronización en Tiempo Real"])


# ============================================================================
# 1. GESTOR DE CONEXIONES WEBSOCKET AISLADO POR TENANT
# ============================================================================

class TenantConnectionManager:
    """
    Administrador de conexiones WebSocket con particionamiento estricto por Tenant.
    Evita que mensajes de una institución se filtren a otra.
    """
    def __init__(self):
        # Mapeo: tenant_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Mapeo: tenant_id -> asyncio.Queue para Server-Sent Events (SSE)
        self.sse_queues: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def connect_ws(self, websocket: WebSocket, tenant_id: str, usuario_info: dict):
        """Acepta y registra una conexión WebSocket asignada al Tenant."""
        await websocket.accept()
        tenant_key = str(tenant_id)
        async with self._lock:
            if tenant_key not in self.active_connections:
                self.active_connections[tenant_key] = set()
            self.active_connections[tenant_key].add(websocket)

        logger.info(
            f">> [WS CONNECT] Usuario {usuario_info.get('correo')} conectado al Tenant {tenant_key}. "
            f"Total activos en tenant: {len(self.active_connections[tenant_key])}"
        )
        # Notificar al cliente confirmación de enlace
        await websocket.send_json({
            "tipo": "SISTEMA_CONEXION_ESTABLECIDA",
            "tenant_id": tenant_key,
            "servidor_timestamp": datetime.utcnow().isoformat(),
            "mensaje": "Enlace en tiempo real activo con aislamiento multi-tenant."
        })

    async def disconnect_ws(self, websocket: WebSocket, tenant_id: str):
        """Elimina una conexión WebSocket cuando el cliente se desconecta."""
        tenant_key = str(tenant_id)
        async with self._lock:
            if tenant_key in self.active_connections:
                self.active_connections[tenant_key].discard(websocket)
                if not self.active_connections[tenant_key]:
                    del self.active_connections[tenant_key]
        logger.info(f">> [WS DISCONNECT] Cliente desconectado del Tenant {tenant_key}.")

    async def register_sse_client(self, tenant_id: str) -> asyncio.Queue:
        """Registra una cola de eventos para un cliente SSE conectado."""
        tenant_key = str(tenant_id)
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            if tenant_key not in self.sse_queues:
                self.sse_queues[tenant_key] = set()
            self.sse_queues[tenant_key].add(queue)
        return queue

    async def unregister_sse_client(self, tenant_id: str, queue: asyncio.Queue):
        """Desregistra una cola SSE."""
        tenant_key = str(tenant_id)
        async with self._lock:
            if tenant_key in self.sse_queues:
                self.sse_queues[tenant_key].discard(queue)
                if not self.sse_queues[tenant_key]:
                    del self.sse_queues[tenant_key]

    async def broadcast_tenant(self, tenant_id: str, evento: str, payload: dict):
        """
        Emite un mensaje en tiempo real a TODOS los clientes conectados
        exclusivamente a ese Tenant (tanto por WebSockets como por SSE).
        """
        tenant_key = str(tenant_id)
        mensaje = {
            "evento": evento,
            "tenant_id": tenant_key,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "datos": payload,
        }
        json_str = json.dumps(mensaje, ensure_ascii=False)

        # 1. Enviar a conexiones WebSocket
        conexiones_vivas = set()
        async with self._lock:
            websockets = set(self.active_connections.get(tenant_key, []))

        for ws in websockets:
            try:
                await ws.send_text(json_str)
                conexiones_vivas.add(ws)
            except Exception as e:
                logger.warning(f">> [WS SEND ERROR] Fallo enviando a websocket: {e}")

        async with self._lock:
            if tenant_key in self.active_connections:
                self.active_connections[tenant_key] = conexiones_vivas

        # 2. Enviar a colas de SSE
        async with self._lock:
            queues = set(self.sse_queues.get(tenant_key, []))

        for q in queues:
            try:
                if not q.full():
                    q.put_nowait(mensaje)
            except Exception:
                pass


# Instancia singleton del administrador de tiempo real
ws_manager = TenantConnectionManager()


# ============================================================================
# 2. MODELOS PYDANTIC PARA ACTUALIZACIONES EN TIEMPO REAL
# ============================================================================

class ActualizarLogisticaPayload(BaseModel):
    categoria: str = Field(..., example="AULAS", description="AULAS, EQUIPOS, MATERIAL_PEDAGOGICO, INFRAESTRUCTURA")
    recurso: str = Field(..., example="Laboratorio de Cómputo 3")
    cantidad: int = Field(default=1, ge=0)
    estado: str = Field(..., example="DISPONIBLE", description="DISPONIBLE, ASIGNADO, EN_MANTENIMIENTO, RESERVADO")
    ubicacion: Optional[str] = Field(default="Bloque A")
    observaciones: Optional[str] = Field(default=None)


class ActualizarNotaPayload(BaseModel):
    estudiante_id: int
    curso_id: int
    materia: str = Field(..., example="Matemáticas Avanzadas")
    periodo: str = Field(..., example="Periodo 1 - 2026")
    nota: float = Field(..., ge=0.0, le=5.0, example=4.8)
    observaciones: Optional[str] = Field(default="Excelente razonamiento matemático y resolución de problemas.")


# ============================================================================
# 3. ENDPOINT WEBSOCKET AUTENTICADO CON AISLAMIENTO MULTI-TENANT
# ============================================================================

@router.websocket("/ws/{tenant_id}")
async def websocket_tenant_endpoint(websocket: WebSocket, tenant_id: str, token: Optional[str] = Query(None)):
    """
    Canal WebSocket bidireccional seguro.
    Requiere token JWT válido. Valida que el usuario pertenezca al Tenant solicitado
    (o sea Superadministrador) para evitar espionaje cross-tenant.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        usuario_info = decodificar_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    rol_usuario = usuario_info.get("rol", "")
    token_tenant = str(usuario_info.get("tenant_id") or usuario_info.get("organizacion_id") or "")

    # Blindaje Cross-Tenant: El usuario no puede conectarse al canal de otro colegio
    if rol_usuario != RolEnum.SUPERADMIN.value and token_tenant != str(tenant_id):
        logger.warning(f">> [WS CROSS-TENANT REJECT] Usuario {usuario_info.get('correo')} intentó conectar al Tenant {tenant_id}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect_ws(websocket, tenant_id, usuario_info)

    try:
        while True:
            # Mantener conexión viva y procesar 'pings' o consultas cliente
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("tipo") == "PING":
                    await websocket.send_json({"tipo": "PONG", "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect_ws(websocket, tenant_id)
    except Exception as e:
        logger.error(f">> [WS ERROR] Error en canal WebSocket tenant {tenant_id}: {e}")
        await ws_manager.disconnect_ws(websocket, tenant_id)


# ============================================================================
# 4. SERVER-SENT EVENTS (SSE) - FALLBACK EN TIEMPO REAL
# ============================================================================

@router.get("/sse/{tenant_id}")
async def sse_tenant_stream(
    tenant_id: str,
    request: Request,
    token: Optional[str] = Query(None)
):
    """
    Canal de Server-Sent Events (SSE) para clientes HTTP convencionales
    que no puedan usar WebSockets por restricciones de firewall.
    """
    token_str = token or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token_str:
        raise HTTPException(status_code=401, detail="Token requerido para flujo SSE.")

    usuario_info = decodificar_token(token_str)
    rol_usuario = usuario_info.get("rol", "")
    token_tenant = str(usuario_info.get("tenant_id") or usuario_info.get("organizacion_id") or "")

    if rol_usuario != RolEnum.SUPERADMIN.value and token_tenant != str(tenant_id):
        raise HTTPException(status_code=403, detail="Aislamiento Multi-Tenant: Acceso no autorizado a este flujo institucional.")

    queue = await ws_manager.register_sse_client(tenant_id)

    async def event_generator():
        # Mensaje inicial de handshake
        yield f"event: handshake\ndata: {json.dumps({'mensaje': 'SSE conectado exitosamente', 'tenant_id': tenant_id})}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    mensaje = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"event: {mensaje.get('evento', 'actualizacion')}\ndata: {json.dumps(mensaje, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # Enviar pulso Keep-Alive para evitar timeouts del proxy
                    yield ": keep-alive\n\n"
        finally:
            await ws_manager.unregister_sse_client(tenant_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# 5. TABLEROS DE LOGÍSTICA EN TIEMPO REAL
# ============================================================================

@router.get("/logistica/estado")
def obtener_estado_logistica(
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Retorna el estado de recursos logísticos del Tenant con métricas en vivo.
    """
    tenant_id = usuario.get("tenant_id") or usuario.get("organizacion_id")
    es_superadmin = usuario.get("rol") == RolEnum.SUPERADMIN.value

    filtro_sql = "WHERE 1=1"
    params = []
    if not es_superadmin:
        filtro_sql += " AND tenant_id = ?"
        params.append(tenant_id)

    recursos = db.execute_query(f"""
        SELECT id, tenant_id, categoria, recurso, cantidad, estado, ubicacion, observaciones, fecha_actualizacion
        FROM registro_logistica
        {filtro_sql}
        ORDER BY fecha_actualizacion DESC
    """, tuple(params), fetchall=True) or []

    # Métricas agregadas
    total_recursos = len(recursos)
    disponibles = sum(1 for r in recursos if r.get("estado") == "DISPONIBLE")
    mantenimiento = sum(1 for r in recursos if r.get("estado") == "EN_MANTENIMIENTO")

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "resumen": {
            "total_recursos": total_recursos,
            "disponibles": disponibles,
            "en_mantenimiento": mantenimiento,
            "ocupacion_pct": round(((total_recursos - disponibles) / total_recursos * 100), 1) if total_recursos > 0 else 0
        },
        "recursos": recursos
    }


@router.post("/logistica/actualizar")
async def actualizar_recurso_logistica(
    payload: ActualizarLogisticaPayload,
    usuario: dict = Depends(requerir_roles([RolEnum.SUPERADMIN.value, RolEnum.ADMIN.value]))
):
    """
    Registra o actualiza un recurso logístico y emite una notificación
    en tiempo real a todos los tableros del Tenant conectados.
    """
    tenant_id = usuario.get("tenant_id") or usuario.get("organizacion_id")
    if not tenant_id and usuario.get("rol") != RolEnum.SUPERADMIN.value:
        raise HTTPException(status_code=400, detail="Tenant ID no encontrado para este usuario.")

    tenant_val = tenant_id or 1
    ahora_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Inserción / actualización en base de datos
    item_id = db.execute_query("""
        INSERT INTO registro_logistica
        (tenant_id, categoria, recurso, cantidad, estado, ubicacion, observaciones, responsable_id, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tenant_val,
        payload.categoria.upper().strip(),
        payload.recurso.strip(),
        payload.cantidad,
        payload.estado.upper().strip(),
        payload.ubicacion,
        payload.observaciones,
        usuario.get("user_id"),
        ahora_str
    ), commit=True, return_id=True)

    # Disparar emisión en tiempo real
    evento_payload = {
        "id": item_id,
        "categoria": payload.categoria.upper().strip(),
        "recurso": payload.recurso.strip(),
        "cantidad": payload.cantidad,
        "estado": payload.estado.upper().strip(),
        "ubicacion": payload.ubicacion,
        "actualizado_por": usuario.get("nombre") or usuario.get("correo"),
        "fecha": ahora_str
    }
    await ws_manager.broadcast_tenant(str(tenant_val), "LOGISTICA_ACTUALIZADA", evento_payload)

    return {
        "status": "success",
        "mensaje": f"Recurso logístico '{payload.recurso}' actualizado y sincronizado en tiempo real.",
        "item": evento_payload
    }


# ============================================================================
# 6. TABLEROS DE NOTAS Y CALIFICACIONES EN TIEMPO REAL
# ============================================================================

@router.get("/notas/estado")
def obtener_estado_notas(
    curso_id: Optional[int] = Query(None),
    estudiante_id: Optional[int] = Query(None),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Retorna las notas y desempeño académico del Tenant actual,
    filtrado según rol (un Estudiante solo ve sus propias notas).
    """
    tenant_id = usuario.get("tenant_id") or usuario.get("organizacion_id")
    rol_usuario = usuario.get("rol")
    user_id = usuario.get("user_id")

    filtros = ["1=1"]
    params = []

    if rol_usuario != RolEnum.SUPERADMIN.value and tenant_id:
        filtros.append("n.tenant_id = ?")
        params.append(tenant_id)

    # Si es estudiante, restringir forzosamente a su propio ID
    if rol_usuario == RolEnum.ESTUDIANTE.value:
        filtros.append("n.estudiante_id = ?")
        params.append(user_id)
    elif estudiante_id:
        filtros.append("n.estudiante_id = ?")
        params.append(estudiante_id)

    if curso_id:
        filtros.append("n.curso_id = ?")
        params.append(curso_id)

    where_clause = " AND ".join(filtros)

    notas = db.execute_query(f"""
        SELECT n.id, n.tenant_id, n.estudiante_id, u.nombre as estudiante_nombre,
               n.docente_id, d.nombre as docente_nombre,
               n.curso_id, n.materia, n.periodo, n.nota, n.observaciones, n.fecha_registro
        FROM calificaciones_notas n
        LEFT JOIN usuarios u ON u.id = n.estudiante_id
        LEFT JOIN usuarios d ON d.id = n.docente_id
        WHERE {where_clause}
        ORDER BY n.fecha_registro DESC
    """, tuple(params), fetchall=True) or []

    promedio_general = 0.0
    if notas:
        promedio_general = round(sum(float(n.get("nota") or 0) for n in notas) / len(notas), 2)

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "total_registros": len(notas),
        "promedio_general": promedio_general,
        "calificaciones": notas
    }


@router.post("/notas/actualizar")
async def registrar_actualizar_nota(
    payload: ActualizarNotaPayload,
    usuario: dict = Depends(requerir_roles([RolEnum.SUPERADMIN.value, RolEnum.ADMIN.value, RolEnum.DOCENTE.value]))
):
    """
    Registra o actualiza una calificación académica y notifica en tiempo real
    al tablero del estudiante y al panel del docente/administrador.
    """
    tenant_id = usuario.get("tenant_id") or usuario.get("organizacion_id") or 1
    ahora_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Inserción en tabla calificaciones_notas
    nota_id = db.execute_query("""
        INSERT INTO calificaciones_notas
        (tenant_id, estudiante_id, docente_id, curso_id, materia, periodo, nota, observaciones, fecha_registro)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tenant_id,
        payload.estudiante_id,
        usuario.get("user_id"),
        payload.curso_id,
        payload.materia.strip(),
        payload.periodo.strip(),
        payload.nota,
        payload.observaciones,
        ahora_str
    ), commit=True, return_id=True)

    # Consultar nombre del estudiante
    est = db.execute_query("SELECT nombre, correo FROM usuarios WHERE id = ?", (payload.estudiante_id,), fetchone=True)
    nombre_est = est.get("nombre") if est else f"Estudiante #{payload.estudiante_id}"

    evento_payload = {
        "nota_id": nota_id,
        "estudiante_id": payload.estudiante_id,
        "estudiante_nombre": nombre_est,
        "curso_id": payload.curso_id,
        "materia": payload.materia.strip(),
        "periodo": payload.periodo.strip(),
        "nota": payload.nota,
        "docente_nombre": usuario.get("nombre") or usuario.get("correo"),
        "observaciones": payload.observaciones,
        "fecha": ahora_str
    }

    # Difusión a todo el tenant en tiempo real
    await ws_manager.broadcast_tenant(str(tenant_id), "NOTA_CALIFICADA", evento_payload)

    return {
        "status": "success",
        "mensaje": f"Calificación de {payload.materia} ({payload.nota}) para {nombre_est} registrada y sincronizada en tiempo real.",
        "nota": evento_payload
    }
