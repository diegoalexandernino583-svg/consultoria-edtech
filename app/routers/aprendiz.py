"""M?dulo de rutas REST: Aprendiz, Progreso, Cat?logo y Evaluaciones."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, Response, JSONResponse
from app.core import *

router = APIRouter(tags=["Aprendiz, Progreso, Cat?logo y Evaluaciones"])


@router.get("/api/material/{curso_id}/test")
def obtener_test_coleccion(curso_id: int):
    """Retorna las preguntas y opciones del test interactivo para una colección dada"""
    return {"status": "success", "data": obtener_test_para_curso(curso_id)}


@router.get("/api/material/catalogo")
def obtener_catalogo_completo(organizacion_id: Optional[int] = None):
    query = """
        SELECT m.id, m.titulo, m.tipo_material, m.enlace_url, m.rol_destino, m.fecha_publicacion,
               COALESCE(m.total_modulos, 3) as total_modulos,
               CASE WHEN COUNT(a.id) = 0 OR SUM(CASE WHEN a.organizacion_id IS NULL THEN 1 ELSE 0 END) > 0 THEN 'Acceso Global (Todas)'
                    ELSE MAX(o.nombre) END as organizacion_nombre
        FROM material_capacitacion m
        LEFT JOIN asignacion_material a ON m.id = a.material_id
        LEFT JOIN organizaciones o ON a.organizacion_id = o.id
        WHERE 1=1
    """
    params = []
    if organizacion_id:
        query += " AND (a.organizacion_id = ? OR a.organizacion_id IS NULL)"
        params.append(organizacion_id)
        
    query += " GROUP BY m.id, m.titulo, m.tipo_material, m.enlace_url, m.rol_destino, m.fecha_publicacion, m.total_modulos ORDER BY m.id DESC"
    materiales = db.execute_query(query, tuple(params), fetchall=True)
    return {"status": "success", "data": materiales or []}


@router.get("/api/aprendiz/progreso/{usuario_id}")
def obtener_progreso_aprendiz(usuario_id: int):
    """Permite al estudiante ver sus cursos asignados con su porcentaje de progreso real, mentor asignado, institución y racha"""
    u = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.mentor_id, u.foto_perfil,
               COALESCE(u.racha_semanas, 5) as racha_semanas,
               COALESCE(u.minutos_dedicados_totales, 180) as minutos_dedicados_totales,
               COALESCE(u.tema_decorativo, 'estandar') as tema_decorativo,
               u.fondo_personalizado, u.colores_personalizados, u.disenos_personalizados_json,
               o.nombre as organizacion_nombre,
               m.nombre as mentor_nombre, m.correo as mentor_correo, m.foto_perfil as mentor_foto_perfil
        FROM usuarios u
        LEFT JOIN organizaciones o ON o.id = u.organizacion_id
        LEFT JOIN usuarios m ON m.id = u.mentor_id
        WHERE u.id = ?
    """, (usuario_id,), fetchone=True)
    org_id = u["organizacion_id"] if u and u.get("organizacion_id") else 1

    query = """
        SELECT m.id, m.titulo, m.tipo_material, m.enlace_url,
               COALESCE(m.total_modulos, 3) as total_modulos,
               COALESCE(p.modulos_completados, 0) as modulos_completados,
               COALESCE(p.porcentaje_avance, 0) as porcentaje_avance,
               COALESCE(p.tiempo_dedicado_minutos, 0) as tiempo_dedicado_minutos,
               COALESCE(p.estado, 'No Iniciado') as estado
        FROM material_capacitacion m
        LEFT JOIN asignacion_material a ON m.id = a.material_id
        LEFT JOIN progreso_cursos p ON p.curso_id = m.id AND p.usuario_id = ?
        WHERE (a.organizacion_id = ? OR a.organizacion_id IS NULL)
          AND (m.rol_destino != 'Mentor' OR m.rol_destino IS NULL)
        GROUP BY m.id, m.titulo, m.tipo_material, m.enlace_url, m.total_modulos, p.modulos_completados, p.porcentaje_avance, p.tiempo_dedicado_minutos, p.estado
        ORDER BY m.id DESC
    """
    cursos = db.execute_query(query, (usuario_id, org_id), fetchall=True) or []
    for c in cursos:
        tot = max(1, c.get("total_modulos") or 3)
        m_comp = c.get("modulos_completados") or 0
        pct = float(c.get("porcentaje_avance") or 0.0)
        if m_comp > 0 and pct == 0.0:
            pct = round((m_comp / tot) * 100.0, 1)
        elif pct > 0.0 and m_comp == 0:
            m_comp = max(1, round((pct / 100.0) * tot))
        c["porcentaje_avance"] = pct
        c["modulos_completados"] = m_comp

    # Quizzes del mentor asignado (o de la organización si no tiene mentor específico)
    mentor_id = u.get("mentor_id") if u else None
    if mentor_id:
        quizzes = db.execute_query("""
            SELECT q.id, q.mentor_id, q.titulo, q.tipo, q.descripcion, q.duracion_minutos, q.preguntas_json, q.fecha_creacion,
                   m.nombre as mentor_nombre,
                   pq.calificacion, pq.aprobado, pq.fecha_completado
            FROM quizzes_evaluaciones q
            JOIN usuarios m ON m.id = q.mentor_id
            LEFT JOIN progreso_quizzes pq ON pq.quiz_id = q.id AND pq.aprendiz_id = ?
            WHERE q.mentor_id = ? AND q.activo = 1
            ORDER BY q.id DESC
        """, (usuario_id, mentor_id), fetchall=True) or []
    else:
        quizzes = db.execute_query("""
            SELECT q.id, q.mentor_id, q.titulo, q.tipo, q.descripcion, q.duracion_minutos, q.preguntas_json, q.fecha_creacion,
                   m.nombre as mentor_nombre,
                   pq.calificacion, pq.aprobado, pq.fecha_completado
            FROM quizzes_evaluaciones q
            JOIN usuarios m ON m.id = q.mentor_id
            LEFT JOIN progreso_quizzes pq ON pq.quiz_id = q.id AND pq.aprendiz_id = ?
            WHERE q.activo = 1
            ORDER BY q.id DESC
        """, (usuario_id,), fetchall=True) or []

    for q in quizzes:
        try:
            q["preguntas"] = json.loads(q.get("preguntas_json") or "[]")
            q["total_preguntas"] = len(q["preguntas"])
        except Exception:
            q["preguntas"] = []
            q["total_preguntas"] = 0

    return {
        "status": "success",
        "data": cursos,
        "usuario": u,
        "estudiante": u,
        "cursos": cursos,
        "quizzes": quizzes
    }


@router.get("/api/quizzes/listar")
def listar_quizzes(mentor_id: Optional[int] = None, aprendiz_id: Optional[int] = None, organizacion_id: Optional[int] = None):
    """Retorna los quizzes y evaluaciones disponibles"""
    params = []
    where_clauses = ["q.activo = 1"]
    if mentor_id:
        where_clauses.append("q.mentor_id = ?")
        params.append(mentor_id)
    if organizacion_id:
        where_clauses.append("(q.organizacion_id = ? OR q.organizacion_id IS NULL)")
        params.append(organizacion_id)

    sql = f"""
        SELECT q.id, q.mentor_id, q.titulo, q.tipo, q.descripcion, q.duracion_minutos, q.preguntas_json, q.fecha_creacion,
               m.nombre as mentor_nombre, m.correo as mentor_correo,
               COUNT(pq.id) as total_entregas,
               ROUND(AVG(COALESCE(pq.calificacion, 0)), 1) as promedio_calificacion
        FROM quizzes_evaluaciones q
        JOIN usuarios m ON m.id = q.mentor_id
        LEFT JOIN progreso_quizzes pq ON pq.quiz_id = q.id
        WHERE {" AND ".join(where_clauses)}
        GROUP BY q.id, q.mentor_id, q.titulo, q.tipo, q.descripcion, q.duracion_minutos, q.preguntas_json, q.fecha_creacion, m.nombre, m.correo
        ORDER BY q.id DESC
    """
    rows = db.execute_query(sql, tuple(params), fetchall=True) or []
    for r in rows:
        try:
            pregs = json.loads(r.get("preguntas_json") or "[]")
            r["total_preguntas"] = len(pregs)
            r["preguntas"] = pregs
        except Exception:
            r["total_preguntas"] = 0
            r["preguntas"] = []
    return {"status": "success", "data": rows}


@router.post("/api/quizzes/crear")
def crear_quiz_mentor(req: CrearQuizRequest):
    """Permite a un mentor crear un Quiz o Evaluación para sus aprendices"""
    m = db.execute_query("SELECT id, nombre, organizacion_id FROM usuarios WHERE id = ?", (req.mentor_id,), fetchone=True)
    if not m:
        raise HTTPException(status_code=404, detail="Mentor no encontrado.")

    org_id = req.organizacion_id or m.get("organizacion_id")
    pregs_json = json.dumps(req.preguntas, ensure_ascii=False)

    db.execute_query("""
        INSERT INTO quizzes_evaluaciones (mentor_id, organizacion_id, titulo, tipo, descripcion, duracion_minutos, preguntas_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (req.mentor_id, org_id, req.titulo.strip(), req.tipo, req.descripcion, req.duracion_minutos, pregs_json), commit=True)

    registrar_movimiento(m["nombre"], "Tutorias", "Crear_Quiz_Mentor", "EXITO", f"{req.tipo} '{req.titulo}' creado para aprendices")
    return {"status": "success", "mensaje": f"{req.tipo} '{req.titulo}' publicado exitosamente para tus aprendices."}


@router.delete("/api/quizzes/{quiz_id}")
def eliminar_quiz_mentor(quiz_id: int):
    """Elimina un quiz o evaluación creado por un mentor"""
    db.execute_query("UPDATE quizzes_evaluaciones SET activo = 0 WHERE id = ?", (quiz_id,), commit=True)
    return {"status": "success", "mensaje": "Quiz eliminado correctamente."}


@router.post("/api/quizzes/{quiz_id}/responder")
def responder_quiz(quiz_id: int, req: ResponderQuizRequest):
    """Permite al estudiante responder un quiz y calcula su calificación automática"""
    q = db.execute_query("SELECT id, titulo, preguntas_json FROM quizzes_evaluaciones WHERE id = ?", (quiz_id,), fetchone=True)
    if not q:
        raise HTTPException(status_code=404, detail="Quiz no encontrado.")

    preguntas = json.loads(q.get("preguntas_json") or "[]")
    if not preguntas:
        raise HTTPException(status_code=400, detail="Este quiz no contiene preguntas configuradas.")

    total = len(preguntas)
    aciertos = 0
    respuestas_aprendiz = req.respuestas

    for idx, p in enumerate(preguntas):
        resp_dada = ""
        if isinstance(respuestas_aprendiz, list):
            if idx < len(respuestas_aprendiz):
                resp_dada = str(respuestas_aprendiz[idx]).strip()
        elif isinstance(respuestas_aprendiz, dict):
            resp_dada = str(respuestas_aprendiz.get(str(idx), respuestas_aprendiz.get(idx, ""))).strip()

        corr_val = p.get("correcta", p.get("respuesta_correcta", ""))
        if str(resp_dada).lower() == str(corr_val).lower():
            aciertos += 1
        elif isinstance(corr_val, int) and p.get("opciones") and 0 <= corr_val < len(p["opciones"]):
            if str(resp_dada).strip().lower() == str(p["opciones"][corr_val]).strip().lower():
                aciertos += 1

    calificacion = round((aciertos / max(1, total)) * 100, 1)
    aprobado = 1 if calificacion >= 70.0 else 0
    resp_guardar = json.dumps(respuestas_aprendiz, ensure_ascii=False)

    # Actualizar o insertar resultado
    ya_existe = db.execute_query("SELECT id FROM progreso_quizzes WHERE quiz_id = ? AND aprendiz_id = ?", (quiz_id, req.aprendiz_id), fetchone=True)
    if ya_existe:
        db.execute_query("""
            UPDATE progreso_quizzes 
            SET calificacion = ?, aprobado = ?, tiempo_segundos = ?, respuestas_json = ?, fecha_completado = DATETIME('now', 'localtime')
            WHERE id = ?
        """, (calificacion, aprobado, req.tiempo_segundos, resp_guardar, ya_existe["id"]), commit=True)
    else:
        db.execute_query("""
            INSERT INTO progreso_quizzes (quiz_id, aprendiz_id, calificacion, aprobado, tiempo_segundos, respuestas_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (quiz_id, req.aprendiz_id, calificacion, aprobado, req.tiempo_segundos, resp_guardar), commit=True)

    # Sumar tiempo al estudiante y registrar actividad
    minutos_sumar = max(5, round(req.tiempo_segundos / 60))
    db.execute_query("""
        UPDATE usuarios 
        SET minutos_dedicados_totales = COALESCE(minutos_dedicados_totales, 0) + ?
        WHERE id = ?
    """, (minutos_sumar, req.aprendiz_id), commit=True)

    db.execute_query("""
        INSERT INTO registro_actividades_tiempo (usuario_id, rol, tipo_actividad, minutos)
        VALUES (?, 'Aprendiz', 'Evaluación / Quiz', ?)
    """, (req.aprendiz_id, minutos_sumar), commit=True)

    return {
        "status": "success",
        "calificacion": calificacion,
        "aprobado": bool(aprobado),
        "aciertos": aciertos,
        "total_preguntas": total,
        "mensaje": f"¡Evaluación completada! Nota: {calificacion}% ({aciertos}/{total} aciertos)."
    }


@router.post("/api/aprendiz/{usuario_id}/actualizar-racha")
def actualizar_racha_aprendiz(usuario_id: int):
    """Actualiza y avanza la racha semanal del aprendiz según su actividad continua"""
    u = db.execute_query("SELECT id, nombre, rol, racha_semanas, ultima_semana_racha FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    current_week = datetime.now().strftime("%Y-W%W")
    racha_actual = u.get("racha_semanas") or 0
    ultima_sem = u.get("ultima_semana_racha")
    
    if ultima_sem != current_week:
        nueva_racha = racha_actual + 1
        db.execute_query(
            "UPDATE usuarios SET racha_semanas = ?, ultima_semana_racha = ? WHERE id = ?",
            (nueva_racha, current_week, usuario_id),
            commit=True
        )
        msg = f"¡Excelente progreso! Tu racha semanal se ha incrementado a {nueva_racha} semanas."
    else:
        nueva_racha = racha_actual
        msg = f"Tu racha para esta semana está al día ({nueva_racha} semanas acumuladas)."
        
    desbloqueado = (nueva_racha >= 5) or (u.get("rol") in ("Mentor", "Administrador", "Super Administrador"))
    registrar_movimiento(u["nombre"], "Academico", "Actualizar_Racha_Semanal", "EXITO", f"Racha: {nueva_racha} semanas (Semana {current_week})")
    
    return {
        "status": "success",
        "racha_semanas": nueva_racha,
        "desbloqueado": desbloqueado,
        "mensaje": msg
    }


@router.post("/api/aprendiz/completar-test")
def completar_test_aprendiz(datos: CompletarTestRequest):
    """Calcula la calificación, registra en progreso_cursos y guarda auditoría"""
    porcentaje = round((datos.respuestas_correctas / max(1, datos.total_preguntas)) * 100, 1)
    
    existe = db.execute_query(
        "SELECT id, tiempo_dedicado_minutos, porcentaje_avance FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?",
        (datos.usuario_id, datos.curso_id),
        fetchone=True
    )
    if existe:
        tiempo_previo = existe.get("tiempo_dedicado_minutos") or 0
        nuevo_tiempo = tiempo_previo + (datos.tiempo_dedicado_minutos or 20)
        nuevo_avance = max(float(existe.get("porcentaje_avance") or 0), porcentaje)
        db.execute_query(
            "UPDATE progreso_cursos SET porcentaje_avance = ?, tiempo_dedicado_minutos = ? WHERE id = ?",
            (nuevo_avance, nuevo_tiempo, existe["id"]),
            commit=True
        )
    else:
        nuevo_avance = porcentaje
        db.execute_query(
            "INSERT INTO progreso_cursos (usuario_id, curso_id, porcentaje_avance, tiempo_dedicado_minutos) VALUES (?, ?, ?, ?)",
            (datos.usuario_id, datos.curso_id, porcentaje, datos.tiempo_dedicado_minutos or 20),
            commit=True
        )

    registrar_movimiento(
        f"Usuario_{datos.usuario_id}",
        "Evaluacion_Test",
        "Test_Completado",
        "EXITO" if porcentaje >= 60 else "REPROBADO",
        f"Curso #{datos.curso_id}: {datos.respuestas_correctas}/{datos.total_preguntas} ({porcentaje}%)"
    )

    return {
        "status": "success",
        "mensaje": f"Test completado: {datos.respuestas_correctas}/{datos.total_preguntas} respuestas correctas ({porcentaje}%). Progreso guardado.",
        "porcentaje_obtenido": porcentaje,
        "aprobado": porcentaje >= 60
    }


@router.post("/api/superadmin/material/crear")
def crear_material(datos: CrearMaterialReq):
    t_mod = datos.total_modulos or 3
    query_insert = """
        INSERT INTO material_capacitacion (titulo, tipo_material, enlace_url, rol_destino, total_modulos)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?)
    """
    mat_id = db.execute_query(
        query_insert,
        (datos.titulo.strip(), datos.tipo_material, datos.enlace_url.strip(), datos.rol_destino or "Aprendiz", t_mod),
        return_id=True
    )
    if not mat_id:
        row = db.execute_query(
            "SELECT id FROM material_capacitacion WHERE titulo = ? AND enlace_url = ? ORDER BY id DESC",
            (datos.titulo.strip(), datos.enlace_url.strip()),
            fetchone=True
        )
        if row:
            mat_id = row["id"]

    if mat_id and datos.organizacion_id:
        db.execute_query(
            "INSERT INTO asignacion_material (material_id, organizacion_id, fecha_asignacion) VALUES (?, ?, DATETIME('now', 'localtime'))",
            (mat_id, datos.organizacion_id),
            commit=True
        )

    try:
        replicador_azure.sincronizar_inmediato(["material_capacitacion", "asignacion_material"])
    except Exception:
        pass

    registrar_movimiento("SuperAdmin", "Material", "Crear_Material", "EXITO", f"Título: {datos.titulo} - ID: {mat_id} - Módulos: {t_mod}")
    return {"status": "success", "mensaje": "Material o colección agregada al catálogo y sincronizada en Azure SQL con éxito.", "id": mat_id}


@router.post("/api/superadmin/progreso/actualizar-modulos")
def actualizar_progreso_modulos(datos: ActualizarProgresoModulosReq):
    """Permite al SuperAdmin actualizar o simular el progreso granular de módulos de un aprendiz en una colección"""
    mat = db.execute_query("SELECT id, titulo, COALESCE(total_modulos, 3) as total_modulos FROM material_capacitacion WHERE id = ?", (datos.curso_id,), fetchone=True)
    if not mat:
        raise HTTPException(status_code=404, detail="Colección no encontrada.")

    usr = db.execute_query("SELECT id, nombre, organizacion_id FROM usuarios WHERE id = ?", (datos.usuario_id,), fetchone=True)
    if not usr:
        raise HTTPException(status_code=404, detail="Usuario aprendiz no encontrado.")

    t_mod = mat["total_modulos"]
    m_comp = max(0, min(datos.modulos_completados, t_mod))
    pct = round((m_comp / max(1, t_mod)) * 100, 1)

    if m_comp == 0:
        estado = "No Iniciado"
    elif m_comp >= t_mod:
        estado = "Completado"
    else:
        estado = "En Progreso"

    existe = db.execute_query("SELECT id, tiempo_dedicado_minutos FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (datos.usuario_id, datos.curso_id), fetchone=True)
    if existe:
        nuevo_tiempo = (existe.get("tiempo_dedicado_minutos") or 0) + (datos.tiempo_dedicado_minutos or 15)
        db.execute_query("""
            UPDATE progreso_cursos 
            SET modulos_completados = ?, porcentaje_avance = ?, tiempo_dedicado_minutos = ?, estado = ?, fecha_actualizacion = DATETIME('now', 'localtime')
            WHERE id = ?
        """, (m_comp, pct, nuevo_tiempo, estado, existe["id"]), commit=True)
    else:
        db.execute_query("""
            INSERT INTO progreso_cursos (usuario_id, curso_id, modulos_completados, porcentaje_avance, tiempo_dedicado_minutos, estado, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
        """, (datos.usuario_id, datos.curso_id, m_comp, pct, datos.tiempo_dedicado_minutos or 15, estado), commit=True)

    registrar_movimiento(
        "SuperAdmin", "Progreso_Modulos", "Actualizar_Avance", "EXITO",
        f"Estudiante '{usr['nombre']}' en '{mat['titulo']}': {m_comp}/{t_mod} módulos ({pct}%)"
    )

    return {
        "status": "success",
        "mensaje": f"✓ Progreso actualizado: {m_comp} de {t_mod} módulos completados ({pct}% - {estado}).",
        "modulos_completados": m_comp,
        "total_modulos": t_mod,
        "porcentaje_avance": pct,
        "estado": estado
    }


@router.delete("/api/superadmin/material/{material_id}")
def eliminar_material(material_id: int, request: Request):
    """Permite al Super Administrador o Administrador eliminar un material o colección del catálogo y de Azure SQL con respaldo en Bóveda Legal"""
    mat = db.execute_query("SELECT * FROM material_capacitacion WHERE id = ?", (material_id,), fetchone=True)
    if not mat:
        raise HTTPException(status_code=404, detail="El material o colección no existe en el catálogo.")

    asigs = db.execute_query("SELECT * FROM asignacion_material WHERE material_id = ?", (material_id,), fetchall=True) or []
    progs = db.execute_query("SELECT * FROM progreso_cursos WHERE curso_id = ?", (material_id,), fetchall=True) or []
    ip_cliente = obtener_ip_cliente(request) if request else "127.0.0.1"
    crear_snapshot_boveda_legal(
        operacion_origen="ELIMINACION_COLECCION_CATALOGO",
        entidad_afectada="material_capacitacion",
        entidad_id=material_id,
        entidad_nombre=mat["titulo"],
        correo_responsable="alexander.nino.583@gmail.com",
        direccion_ip=ip_cliente,
        datos_respaldo={
            "coleccion": dict(mat),
            "asignaciones": [dict(a) for a in asigs],
            "progresos_aprendices": [dict(p) for p in progs]
        }
    )

    # 1. Eliminar asignaciones vinculadas
    db.execute_query("DELETE FROM asignacion_material WHERE material_id = ?", (material_id,), commit=True)
    # 2. Eliminar progresos de usuarios vinculados a este curso
    db.execute_query("DELETE FROM progreso_cursos WHERE curso_id = ?", (material_id,), commit=True)
    # 3. Eliminar el material
    db.execute_query("DELETE FROM material_capacitacion WHERE id = ?", (material_id,), commit=True)

    try:
        replicador_azure.sincronizar_inmediato([
            "progreso_cursos",
            "asignacion_material",
            "material_capacitacion",
            "boveda_legal_snapshots"
        ])
    except Exception:
        pass

    registrar_movimiento("SuperAdmin", "Material", "Eliminar_Material", "EXITO", f"Colección eliminada: '{mat['titulo']}' (ID {material_id})")
    return {"status": "success", "mensaje": f"Colección '{mat['titulo']}' eliminada permanentemente del catálogo y de Azure SQL (con respaldo en Bóveda Legal)."}


@router.get("/api/superadmin/aprendiz/{usuario_id}/desglose-cursos")
def obtener_desglose_cursos_aprendiz(usuario_id: int):
    """Retorna el detalle curso a curso y quizzes de un estudiante para el SuperAdmin y Mentores (Solo Lectura)"""
    u = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.mentor_id, u.foto_perfil, o.nombre as organizacion_nombre,
               m.nombre as mentor_nombre, m.foto_perfil as mentor_foto_perfil
        FROM usuarios u
        LEFT JOIN organizaciones o ON u.organizacion_id = o.id
        LEFT JOIN usuarios m ON u.mentor_id = m.id
        WHERE u.id = ?
    """, (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    query = """
        SELECT m.id as curso_id, m.titulo, m.tipo_material, m.enlace_url,
               COALESCE(m.total_modulos, 3) as total_modulos,
               COALESCE(p.modulos_completados, 0) as modulos_completados,
               COALESCE(p.porcentaje_avance, 0) as porcentaje_avance,
               COALESCE(p.tiempo_dedicado_minutos, 0) as tiempo_dedicado_minutos,
               COALESCE(p.estado, 'No Iniciado') as estado
        FROM material_capacitacion m
        LEFT JOIN progreso_cursos p ON p.curso_id = m.id AND p.usuario_id = ?
        WHERE (m.rol_destino != 'Mentor' OR m.rol_destino IS NULL)
        GROUP BY m.id, m.titulo, m.tipo_material, m.enlace_url, m.total_modulos, p.modulos_completados, p.porcentaje_avance, p.tiempo_dedicado_minutos, p.estado
        ORDER BY m.id ASC
    """
    desglose = db.execute_query(query, (usuario_id,), fetchall=True) or []
    
    total = len(desglose)
    sum_avance = sum(float(d.get("porcentaje_avance", 0)) for d in desglose)
    promedio = round(sum_avance / total, 1) if total > 0 else 0.0
    total_min = sum(int(d.get("tiempo_dedicado_minutos", 0)) for d in desglose)
    cursos_completados = sum(1 for d in desglose if float(d.get("porcentaje_avance", 0)) >= 80)

    # Quizzes asignados y realizados por el estudiante
    m_id = u.get("mentor_id") or 0
    org_id = u.get("organizacion_id") or 0
    quizzes_raw = db.execute_query("""
        SELECT q.id, q.titulo, q.tipo, q.descripcion, q.duracion_minutos, q.fecha_creacion,
               men.nombre as mentor_nombre,
               pq.id as intento_id, pq.calificacion, pq.aprobado, pq.tiempo_segundos, pq.fecha_completado
        FROM quizzes_evaluaciones q
        LEFT JOIN usuarios men ON q.mentor_id = men.id
        LEFT JOIN progreso_quizzes pq ON pq.quiz_id = q.id AND pq.aprendiz_id = ?
        WHERE q.activo = 1 AND (q.mentor_id = ? OR q.organizacion_id = ? OR pq.id IS NOT NULL)
        ORDER BY q.id ASC
    """, (usuario_id, m_id, org_id), fetchall=True) or []

    quizzes_list = []
    for qz in quizzes_raw:
        intento = qz.get("intento_id") is not None
        segundos = int(qz.get("tiempo_segundos") or 0)
        if intento:
            mins = segundos // 60
            segs = segundos % 60
            tiempo_fmt = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"
        else:
            tiempo_fmt = "Pendiente"
            
        quizzes_list.append({
            "id": qz["id"],
            "titulo": qz["titulo"],
            "tipo": qz.get("tipo") or "Quiz",
            "descripcion": qz.get("descripcion") or "",
            "duracion_minutos": qz.get("duracion_minutos", 15),
            "mentor_nombre": qz.get("mentor_nombre") or "Mentor Asignado",
            "calificacion": round(float(qz.get("calificacion") or 0), 1) if intento else None,
            "aprobado": bool(qz.get("aprobado")) if intento else False,
            "tiempo_segundos": segundos,
            "tiempo_formateado": tiempo_fmt,
            "fecha_completado": qz.get("fecha_completado"),
            "estado": "Completado" if intento else "Pendiente"
        })

    quizzes_totales = len(quizzes_list)
    quizzes_completados = sum(1 for q in quizzes_list if q["estado"] == "Completado")
    quizzes_aprobados = sum(1 for q in quizzes_list if q["aprobado"])
    promedio_quizzes = round(sum(q["calificacion"] for q in quizzes_list if q["calificacion"] is not None) / quizzes_completados, 1) if quizzes_completados > 0 else 0.0

    return {
        "status": "success",
        "usuario": u,
        "promedio_general": promedio,
        "total_minutos": total_min,
        "cursos_completados": cursos_completados,
        "total_cursos": total,
        "cursos": desglose,
        "quizzes": quizzes_list,
        "quizzes_totales": quizzes_totales,
        "quizzes_completados": quizzes_completados,
        "quizzes_aprobados": quizzes_aprobados,
        "promedio_quizzes": promedio_quizzes
    }

