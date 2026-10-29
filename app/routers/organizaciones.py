"""M?dulo de rutas REST: Organizaciones, Branding, Colecciones y Anal?tica."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, Response, JSONResponse
from app.core import *

router = APIRouter(tags=["Organizaciones, Branding, Colecciones y Anal?tica"])


@router.get("/api/organizaciones/{org_id}/mentores")
def listar_mentores_organizacion(org_id: int):
    """Retorna la lista de mentores de una organización para asignación de grupos"""
    mentores = db.execute_query("""
        SELECT id, nombre, correo
        FROM usuarios
        WHERE organizacion_id = ? AND rol = 'Mentor'
        ORDER BY nombre ASC
    """, (org_id,), fetchall=True) or []
    return {"status": "success", "data": mentores}


@router.get("/api/organizaciones/{org_id}/colores")
def obtener_colores_organizacion(org_id: int):
    org = db.execute_query("SELECT id, nombre, color_primario, color_secundario, color_acento, color_personalizado FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")
    return {"status": "success", "data": org}


@router.post("/api/organizaciones/{org_id}/colores")
def guardar_colores_organizacion(org_id: int, datos: ColorimetriaReq):
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")
    db.execute_query("""
        UPDATE organizaciones
        SET color_primario = ?, color_secundario = ?, color_acento = ?, color_personalizado = ?
        WHERE id = ?
    """, (datos.color_primario, datos.color_secundario, datos.color_acento, 1 if datos.color_personalizado else 0, org_id), commit=True)
    registrar_movimiento("Admin", "Organizaciones", "Colorimetria_Guardada", "EXITO", f"Colores asignados a {org['nombre']}: Primario={datos.color_primario}")
    return {"status": "success", "mensaje": f"Colores de '{org['nombre']}' aplicados y guardados exitosamente."}


@router.post("/api/organizaciones/{org_id}/colores/restablecer")
def restablecer_colores_organizacion(org_id: int):
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")
    db.execute_query("""
        UPDATE organizaciones
        SET color_primario = '#0a192f', color_secundario = '#0f273f', color_acento = '#06b6d4', color_personalizado = 0
        WHERE id = ?
    """, (org_id,), commit=True)
    registrar_movimiento("Admin", "Organizaciones", "Colorimetria_Restablecida", "EXITO", f"Diseño predeterminado restablecido para {org['nombre']}")
    return {"status": "success", "mensaje": f"Diseño predeterminado restablecido para '{org['nombre']}'."}


@router.get("/api/organizaciones/{org_id}/temas")
def listar_temas_organizacion(org_id: int):
    """Retorna los temas personalizados guardados para una organización"""
    temas = db.execute_query("""
        SELECT id, organizacion_id, nombre_tema, color_primario, color_secundario, color_acento, fecha_creacion
        FROM temas_personalizados
        WHERE organizacion_id = ?
        ORDER BY id DESC
    """, (org_id,), fetchall=True) or []
    for t in temas:
        t["nombre"] = t.get("nombre_tema", "Tema")
    return {"status": "success", "total": len(temas), "data": temas}


@router.post("/api/organizaciones/{org_id}/temas")
def guardar_tema_personalizado(org_id: int, datos: GuardarTemaReq):
    """Guarda un nuevo tema personalizado para la organización sin límite de cantidad"""
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")

    nombre_raw = datos.nombre_tema or datos.nombre or ""
    nombre_t = nombre_raw.strip() or f"Tema {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    
    db.execute_query("""
        INSERT INTO temas_personalizados (organizacion_id, nombre_tema, color_primario, color_secundario, color_acento)
        VALUES (?, ?, ?, ?, ?)
    """, (org_id, nombre_t, datos.color_primario, datos.color_secundario, datos.color_acento), commit=True)

    # Aplicarlo automáticamente a la organización
    db.execute_query("""
        UPDATE organizaciones
        SET color_primario = ?, color_secundario = ?, color_acento = ?, color_personalizado = 1
        WHERE id = ?
    """, (datos.color_primario, datos.color_secundario, datos.color_acento, org_id), commit=True)

    registrar_movimiento("Admin", "Organizaciones", "Guardar_Tema_Personalizado", "EXITO", f"Tema '{nombre_t}' creado y activado en {org['nombre']}")
    return {"status": "success", "mensaje": f"Tema '{nombre_t}' guardado y activado exitosamente en '{org['nombre']}'."}


@router.post("/api/organizaciones/{org_id}/temas/{tema_id}/aplicar")
def aplicar_tema_guardado(org_id: int, tema_id: int):
    """Aplica un tema personalizado existente a la organización"""
    tema = db.execute_query("SELECT * FROM temas_personalizados WHERE id = ? AND organizacion_id = ?", (tema_id, org_id), fetchone=True)
    if not tema:
        raise HTTPException(status_code=404, detail="Tema no encontrado.")

    db.execute_query("""
        UPDATE organizaciones
        SET color_primario = ?, color_secundario = ?, color_acento = ?, color_personalizado = 1
        WHERE id = ?
    """, (tema["color_primario"], tema["color_secundario"], tema["color_acento"], org_id), commit=True)

    registrar_movimiento("Admin", "Organizaciones", "Aplicar_Tema", "EXITO", f"Tema #{tema_id} '{tema['nombre_tema']}' activado")
    return {"status": "success", "mensaje": f"Tema '{tema['nombre_tema']}' activado en la institución.", "tema": tema}


@router.delete("/api/organizaciones/{org_id}/temas/{tema_id}")
def eliminar_tema_guardado(org_id: int, tema_id: int):
    """Elimina un tema personalizado guardado"""
    db.execute_query("DELETE FROM temas_personalizados WHERE id = ? AND organizacion_id = ?", (tema_id, org_id), commit=True)
    return {"status": "success", "mensaje": "Tema eliminado de la colección de la organización."}


@router.get("/api/organizaciones/{org_id}/logo")
def obtener_logo_organizacion(org_id: int):
    """Retorna el logo actual de la organización"""
    org = db.execute_query("SELECT id, nombre, logo_url FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")
    return {"status": "success", "logo_url": org.get("logo_url")}


@router.post("/api/organizaciones/{org_id}/logo")
def guardar_logo_organizacion(org_id: int, datos: SubirLogoOrgRequest):
    """Permite al administrador institucional subir o cambiar el logo corporativo/educativo"""
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")
    
    db.execute_query("UPDATE organizaciones SET logo_url = ? WHERE id = ?", (datos.logo_url, org_id), commit=True)
    registrar_movimiento("Admin", "Organizaciones", "Actualizar_Logo", "EXITO", f"Logo actualizado para {org['nombre']}")
    return {"status": "success", "mensaje": "Logo institucional actualizado exitosamente.", "logo_url": datos.logo_url}


@router.delete("/api/organizaciones/{org_id}/logo")
def eliminar_logo_organizacion(org_id: int):
    """Permite restablecer el logo de la organización"""
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")
    
    db.execute_query("UPDATE organizaciones SET logo_url = NULL WHERE id = ?", (org_id,), commit=True)
    registrar_movimiento("Admin", "Organizaciones", "Eliminar_Logo", "EXITO", f"Logo restablecido para {org['nombre']}")
    return {"status": "success", "mensaje": "Logo institucional restablecido exitosamente."}


@router.get("/api/organizaciones/{org_id}/colecciones-estado")
def obtener_colecciones_estado_organizacion(org_id: int):
    """Retorna las colecciones asignadas a una institución y las disponibles por asignar con métricas"""
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")

    # Colecciones asignadas
    asignadas = db.execute_query("""
        SELECT m.id, m.titulo, m.tipo_material, m.enlace_url,
               COALESCE(m.total_modulos, 3) as total_modulos,
               m.rol_destino, am.fecha_asignacion,
               COUNT(DISTINCT p.usuario_id) as total_estudiantes_cursando,
               ROUND(AVG(COALESCE(p.porcentaje_avance, 0)), 1) as avance_promedio
        FROM asignacion_material am
        JOIN material_capacitacion m ON am.material_id = m.id
        LEFT JOIN usuarios u ON u.organizacion_id = am.organizacion_id AND u.rol = 'Aprendiz'
        LEFT JOIN progreso_cursos p ON p.curso_id = m.id AND p.usuario_id = u.id
        WHERE am.organizacion_id = ?
        GROUP BY m.id, m.titulo, m.tipo_material, m.enlace_url, m.total_modulos, m.rol_destino, am.fecha_asignacion
        ORDER BY am.fecha_asignacion DESC
    """, (org_id,), fetchall=True) or []

    ids_asignados = [a["id"] for a in asignadas]
    placeholders = ",".join("?" for _ in ids_asignados) if ids_asignados else "0"

    # Colecciones disponibles en la plataforma aún no asignadas a esta institución
    if ids_asignados:
        disponibles = db.execute_query(f"""
            SELECT m.id, m.titulo, m.tipo_material, m.enlace_url,
                   COALESCE(m.total_modulos, 3) as total_modulos,
                   m.rol_destino, m.fecha_publicacion
            FROM material_capacitacion m
            WHERE m.id NOT IN ({placeholders})
            ORDER BY m.id DESC
        """, tuple(ids_asignados), fetchall=True) or []
    else:
        disponibles = db.execute_query("""
            SELECT m.id, m.titulo, m.tipo_material, m.enlace_url,
                   COALESCE(m.total_modulos, 3) as total_modulos,
                   m.rol_destino, m.fecha_publicacion
            FROM material_capacitacion m
            ORDER BY m.id DESC
        """, fetchall=True) or []

    return {
        "status": "success",
        "organizacion": org,
        "asignadas": asignadas,
        "disponibles": disponibles
    }


@router.post("/api/organizaciones/{org_id}/asignar-coleccion/{material_id}")
def asignar_coleccion_rapida(org_id: int, material_id: int):
    """Asigna rápidamente una colección disponible a una institución a un solo clic"""
    ya_existe = db.execute_query("SELECT id FROM asignacion_material WHERE material_id = ? AND organizacion_id = ?", (material_id, org_id), fetchone=True)
    if ya_existe:
        return {"status": "info", "mensaje": "Esta colección ya se encuentra asignada a esta institución."}
    
    db.execute_query("""
        INSERT INTO asignacion_material (material_id, organizacion_id, fecha_asignacion)
        VALUES (?, ?, DATETIME('now', 'localtime'))
    """, (material_id, org_id), commit=True)

    org = db.execute_query("SELECT nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    mat = db.execute_query("SELECT titulo FROM material_capacitacion WHERE id = ?", (material_id,), fetchone=True)
    org_nom = org["nombre"] if org else f"Org #{org_id}"
    mat_nom = mat["titulo"] if mat else f"Material #{material_id}"

    registrar_movimiento("Admin", "Materiales", "Asignar_Coleccion", "EXITO", f"Colección '{mat_nom}' asignada a {org_nom}")
    return {"status": "success", "mensaje": f"Colección '{mat_nom}' asignada exitosamente a '{org_nom}'."}


@router.get("/api/metricas/exportar-excel")
def exportar_metricas_excel(organizacion_id: Optional[int] = None):
    """Genera y descarga directamente en memoria el informe analítico en Excel (.xlsx) con gráficas de mentores y aprendices"""
    try:
        now = datetime.now()
        org_prefix = f"org_{organizacion_id}_" if organizacion_id else "global_"
        nombre_archivo = f"informe_metricas_{org_prefix}{now.strftime('%Y_%m_%d_%H%M%S')}.xlsx"

        wb = construir_libro_excel_completo(organizacion_id=organizacion_id)
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        registrar_movimiento("Admin", "Analitica", "Exportar_Excel_Metricas", "EXITO", f"Informe analítico '{nombre_archivo}' descargado")
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
        )
    except Exception as e:
        print(f">> Error exportando informe de métricas: {e}")
        raise HTTPException(status_code=500, detail=f"Error exportando métricas a Excel: {str(e)}")


@router.get("/api/organizaciones")
@router.get("/api/organizaciones/listar")
def listar_organizaciones():
    orgs = db.execute_query("""
        SELECT o.id, o.nombre, o.tipo_organizacion, o.dominio_permitido, o.licencias_asignadas,
               o.max_administradores, o.max_mentores, o.fecha_creacion, o.estado_activo,
               o.color_primario, o.color_secundario, o.color_acento, o.color_personalizado,
               o.logo_url, o.porcentaje_avance_manual,
               (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id) as total_usuarios,
               (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol = 'Aprendiz') as total_estudiantes_reales,
               (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol = 'Mentor') as total_mentores,
               (SELECT COUNT(*) FROM usuarios u WHERE u.organizacion_id = o.id AND u.rol = 'Administrador') as total_admins,
               (SELECT COUNT(DISTINCT a.material_id) FROM asignacion_material a WHERE a.organizacion_id = o.id) as total_colecciones,
               COALESCE((
                   SELECT ROUND(AVG(p.porcentaje_avance), 1)
                   FROM progreso_cursos p
                   JOIN usuarios u2 ON u2.id = p.usuario_id
                   WHERE u2.organizacion_id = o.id AND u2.rol = 'Aprendiz'
               ), 0.0) as promedio_avance_real
        FROM organizaciones o
        ORDER BY o.id ASC
    """, fetchall=True) or []
    for o in orgs:
        manual = o.get("porcentaje_avance_manual")
        real = float(o.get("promedio_avance_real") or 0.0)
        o["porcentaje_avance"] = round(float(manual), 1) if manual is not None else round(real, 1)
        o["es_avance_manual"] = manual is not None
    return {"status": "success", "data": orgs}


@router.post("/api/superadmin/organizaciones/crear")
def crear_organizacion(datos: CrearOrgRequest, request: Request):
    if datos.confirmacion_convenio_logos is False:
        raise HTTPException(
            status_code=400,
            detail="Es obligatorio confirmar la existencia del Convenio / Alianza de Cooperación y la autorización de uso recíproco de logos y marcas (Ley 1581 de 2012)."
        )
    dom_raw = (datos.dominio_permitido or "").strip().lower().replace("@", "")
    if not dom_raw or dom_raw in ["", "none", "null", "libre", "sin dominio"]:
        dom_final = "LIBRE"
    else:
        dom_final = dom_raw

    if dom_final != "LIBRE":
        existe = db.execute_query("SELECT id FROM organizaciones WHERE LOWER(dominio_permitido) = ?", (dom_final,), fetchone=True)
        if existe:
            raise HTTPException(status_code=400, detail=f"Ya existe una organización registrada con el dominio @{dom_final}.")

    nombre_limpio = datos.nombre.strip()
    org_id = db.execute_query("""
        INSERT INTO organizaciones (nombre, tipo_organizacion, dominio_permitido, licencias_asignadas, max_administradores, max_mentores, logo_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (nombre_limpio, datos.tipo_organizacion, dom_final, datos.licencias_asignadas or 1000000000, datos.max_administradores or 1000000000, datos.max_mentores or 1000000000, datos.logo_url), return_id=True)

    ip_cliente = obtener_ip_cliente(request) if request else "127.0.0.1"
    correo_resp = (datos.correo_responsable or "alexander.nino.583@gmail.com").strip().lower()
    declaracion = (
        f"ACTA DE APROVISIONAMIENTO Y CONVENIO INSTITUCIONAL: Se certifica la existencia de Convenio / Alianza de Cooperación "
        f"con la entidad '{nombre_limpio}' ({datos.tipo_organizacion}), autorización expresa de uso recíproco de signos distintivos/logos "
        f"y sujeción a la Ley 1581 de 2012 y Decreto 1377 de 2013 (Institución como Responsable vs. Consultoría EdTech como Encargada)."
    )
    registrar_evento_boveda_legal(
        categoria="CONVENIO_INSTITUCIONAL",
        correo_responsable=correo_resp,
        rol_responsable="Super Administrador",
        direccion_ip=ip_cliente,
        organizacion_id=org_id,
        organizacion_nombre=nombre_limpio,
        tipo_organizacion=datos.tipo_organizacion,
        estado_convenio=datos.estado_convenio or "CONVENIO / ALIANZA VIGENTE",
        logo_url=datos.logo_url,
        nombre_archivo=None,
        cantidad_registros=int(datos.licencias_asignadas or 100),
        confirmacion_ley1581=True,
        confirmacion_menores_art7=True,
        confirmacion_convenio_logos=True,
        declaracion_legal=declaracion,
        detalles_dict={
            "dominio_permitido": dom_final,
            "licencias_asignadas": datos.licencias_asignadas or 100,
            "max_administradores": datos.max_administradores or 2,
            "max_mentores": datos.max_mentores or 15,
            "tiene_logo_institucional": bool(datos.logo_url)
        }
    )

    try:
        replicador_azure.sincronizar_inmediato(["organizaciones", "boveda_legal_registros"])
    except Exception:
        pass
    registrar_movimiento("SuperAdmin", "Organizaciones", "Crear_Organizacion", "EXITO", f"Org: {nombre_limpio} - Dominio: {dom_final}", organizacion_id=org_id, organizacion_nombre=nombre_limpio, usuario_rol="Super Administrador")
    return {"status": "success", "mensaje": f"Organización '{nombre_limpio}' creada y persistida en Azure SQL y Bóveda Legal con éxito.", "id": org_id, "dominio_permitido": dom_final}


@router.put("/api/superadmin/organizaciones/{org_id}")
def actualizar_organizacion(org_id: int, datos: ActualizarOrgRequest, request: Request):
    """Permite editar instituciones y ampliar o ajustar cupos de licencias, guardando Snapshot previo en la Bóveda Legal"""
    org = db.execute_query("SELECT * FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="La organización no existe.")

    ip_cliente = obtener_ip_cliente(request) if request else "127.0.0.1"
    crear_snapshot_boveda_legal(
        operacion_origen="ACTUALIZACION_ORGANIZACION",
        entidad_afectada="organizaciones",
        entidad_id=org_id,
        entidad_nombre=org["nombre"],
        correo_responsable="alexander.nino.583@gmail.com",
        direccion_ip=ip_cliente,
        datos_respaldo={"organizacion_previa": dict(org)}
    )
        
    dom_raw = (datos.dominio_permitido or "").strip().lower().replace("@", "")
    if not dom_raw or dom_raw in ["", "none", "null", "libre", "sin dominio"]:
        dom_final = "LIBRE"
    else:
        dom_final = dom_raw

    if dom_final != "LIBRE":
        colision = db.execute_query("SELECT id FROM organizaciones WHERE LOWER(dominio_permitido) = ? AND id != ?", (dom_final, org_id), fetchone=True)
        if colision:
            raise HTTPException(status_code=400, detail=f"El dominio @{dom_final} ya está asignado a otra organización.")

    if datos.logo_url == "__REMOVE__":
        actualizar_logo_sql = ", logo_url = NULL"
        params_logo = ()
    elif datos.logo_url is not None:
        actualizar_logo_sql = ", logo_url = ?"
        params_logo = (datos.logo_url,)
    else:
        actualizar_logo_sql = ""
        params_logo = ()

    db.execute_query(f"""
        UPDATE organizaciones 
        SET nombre = ?, tipo_organizacion = ?, dominio_permitido = ?, licencias_asignadas = ?,
            max_administradores = ?, max_mentores = ? {actualizar_logo_sql}
        WHERE id = ?
    """, (datos.nombre.strip(), datos.tipo_organizacion, dom_final, datos.licencias_asignadas,
          datos.max_administradores or 2, datos.max_mentores or 15, *params_logo, org_id), commit=True)

    try:
        replicador_azure.sincronizar_inmediato(["organizaciones", "boveda_legal_snapshots"])
    except Exception:
        pass
          
    registrar_movimiento("SuperAdmin", "Organizaciones", "Modificar_Organizacion", "EXITO", f"Org #{org_id}: {datos.nombre} - Licencias: {datos.licencias_asignadas} - Dominio: {dom_final}", organizacion_id=org_id, organizacion_nombre=datos.nombre.strip(), usuario_rol="Super Administrador")
    return {"status": "success", "mensaje": f"Organización '{datos.nombre}' actualizada exitosamente en Azure SQL.", "dominio_permitido": dom_final}


@router.delete("/api/superadmin/organizaciones/{org_id}")
def eliminar_organizacion(org_id: int, request: Request):
    """Permite exclusivamente al SuperAdmin eliminar un nodo institucional, guardando copia de respaldo inmutable en Bóveda Legal y limpiando Azure SQL"""
    org = db.execute_query("SELECT * FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="La institución no existe.")

    usrs_org = db.execute_query("SELECT id, nombre, correo, rol, organizacion_id, mentor_id FROM usuarios WHERE organizacion_id = ? AND rol != 'Super Administrador'", (org_id,), fetchall=True) or []
    usr_ids = [u["id"] for u in usrs_org]
    progs_org = []
    if usr_ids:
        ph = ",".join("?" for _ in usr_ids)
        progs_org = db.execute_query(f"SELECT * FROM progreso_cursos WHERE usuario_id IN ({ph})", tuple(usr_ids), fetchall=True) or []
    asigs_org = db.execute_query("SELECT * FROM asignacion_material WHERE organizacion_id = ?", (org_id,), fetchall=True) or []

    ip_cliente = obtener_ip_cliente(request) if request else "127.0.0.1"
    crear_snapshot_boveda_legal(
        operacion_origen="ELIMINACION_INSTITUCION",
        entidad_afectada="organizaciones",
        entidad_id=org_id,
        entidad_nombre=org["nombre"],
        correo_responsable="alexander.nino.583@gmail.com",
        direccion_ip=ip_cliente,
        datos_respaldo={
            "organizacion": dict(org),
            "integrantes": [dict(u) for u in usrs_org],
            "progreso_cursos": [dict(p) for p in progs_org],
            "asignaciones_colecciones": [dict(a) for a in asigs_org]
        }
    )

    # Eliminar registros hijos antes de la organización para consistencia total en SQLite y Azure SQL
    for u_r in usrs_org:
        db.execute_query("DELETE FROM progreso_cursos WHERE usuario_id = ?", (u_r["id"],), commit=True)
        db.execute_query("DELETE FROM progreso_quizzes WHERE aprendiz_id = ?", (u_r["id"],), commit=True)
        db.execute_query("DELETE FROM registro_actividades_tiempo WHERE usuario_id = ?", (u_r["id"],), commit=True)
    db.execute_query("DELETE FROM quizzes_evaluaciones WHERE organizacion_id = ?", (org_id,), commit=True)
    db.execute_query("DELETE FROM historial_nuevos_integrantes WHERE organizacion_id = ?", (org_id,), commit=True)
    db.execute_query("DELETE FROM usuarios WHERE organizacion_id = ? AND rol != 'Super Administrador'", (org_id,), commit=True)
    db.execute_query("UPDATE usuarios SET organizacion_id = NULL WHERE organizacion_id = ?", (org_id,), commit=True)
    db.execute_query("DELETE FROM asignacion_material WHERE organizacion_id = ?", (org_id,), commit=True)
    db.execute_query("DELETE FROM temas_personalizados WHERE organizacion_id = ?", (org_id,), commit=True)
    db.execute_query("DELETE FROM organizaciones WHERE id = ?", (org_id,), commit=True)
    try:
        replicador_azure.sincronizar_inmediato([
            "progreso_cursos",
            "progreso_quizzes",
            "registro_actividades_tiempo",
            "quizzes_evaluaciones",
            "historial_nuevos_integrantes",
            "asignacion_material",
            "usuarios",
            "organizaciones",
            "boveda_legal_snapshots"
        ])
    except Exception:
        pass

    registrar_movimiento("SuperAdmin", "Organizaciones", "Eliminar_Organizacion", "EXITO", f"Institución eliminada: {org['nombre']} (ID {org_id}) con respaldo en Bóveda Legal", organizacion_id=org_id, organizacion_nombre=org["nombre"], usuario_rol="Super Administrador")
    return {"status": "success", "mensaje": f"Institución '{org['nombre']}' eliminada permanentemente de Azure SQL (respaldo conservado en Bóveda Legal)."}


@router.get("/api/admin/convenio/{organizacion_id}")
def obtener_datos_convenio_admin(organizacion_id: int):
    """Retorna los datos completos de la organización/convenio (Colegio o Empresa) con sus mentores y aprendices"""
    org = db.execute_query("""
        SELECT id, nombre, tipo_organizacion, dominio_permitido, licencias_asignadas,
               max_administradores, max_mentores, estado_activo,
               color_primario, color_secundario, color_acento, color_personalizado, logo_url
        FROM organizaciones
        WHERE id = ?
    """, (organizacion_id,), fetchone=True)
    if not org:
        org = db.execute_query("""
            SELECT id, nombre, tipo_organizacion, dominio_permitido, licencias_asignadas,
                   max_administradores, max_mentores, estado_activo,
                   color_primario, color_secundario, color_acento, color_personalizado, logo_url
            FROM organizaciones
            ORDER BY id ASC LIMIT 1
        """, fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="La organización en convenio no fue encontrada.")

    org_id_real = org["id"]

    # 1. Mentores de esta organización
    mentores = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.foto_perfil
        FROM usuarios u
        WHERE u.organizacion_id = ? AND u.rol = 'Mentor'
        ORDER BY u.nombre ASC
    """, (org_id_real,), fetchall=True) or []

    # 2. Conteo de aprendices por mentor
    aprendices_count_raw = db.execute_query("""
        SELECT mentor_id, COUNT(*) as conteo
        FROM usuarios
        WHERE organizacion_id = ? AND rol = 'Aprendiz' AND mentor_id IS NOT NULL
        GROUP BY mentor_id
    """, (org_id_real,), fetchall=True) or []
    aprendices_por_mentor = {r["mentor_id"]: r["conteo"] for r in aprendices_count_raw}

    for m in mentores:
        m["total_aprendices"] = aprendices_por_mentor.get(m["id"], 0)

    # 3. Aprendices de esta organización con métricas y tutores
    aprendices = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.mentor_id, u.foto_perfil,
               m.nombre as mentor_nombre, m.correo as mentor_correo, m.foto_perfil as mentor_foto_perfil,
               COALESCE(AVG(p.porcentaje_avance), 0) as promedio_avance,
               COALESCE(SUM(p.tiempo_dedicado_minutos), 0) as total_minutos,
               COUNT(p.id) as total_cursos,
               SUM(CASE WHEN p.porcentaje_avance >= 60 THEN 1 ELSE 0 END) as cursos_aprobados
        FROM usuarios u
        LEFT JOIN usuarios m ON u.mentor_id = m.id
        LEFT JOIN progreso_cursos p ON u.id = p.usuario_id
        WHERE u.organizacion_id = ? AND u.rol = 'Aprendiz'
        GROUP BY u.id, u.nombre, u.correo, u.rol, u.mentor_id, u.foto_perfil, m.nombre, m.correo, m.foto_perfil
        ORDER BY u.nombre ASC
    """, (org_id_real,), fetchall=True) or []

    for a in aprendices:
        a["promedio_avance"] = round(float(a["promedio_avance"]), 1)
        a["total_minutos"] = int(a["total_minutos"] or 0)
        a["total_cursos"] = int(a["total_cursos"] or 0)
        a["cursos_aprobados"] = int(a["cursos_aprobados"] or 0)

    # 4. Administradores de la entidad
    admins = db.execute_query("""
        SELECT id, nombre, correo, rol, foto_perfil
        FROM usuarios
        WHERE organizacion_id = ? AND rol = 'Administrador'
        ORDER BY nombre ASC
    """, (org_id_real,), fetchall=True) or []

    # Totales y KPIs
    total_estudiantes = len(aprendices)
    total_mentores = len(mentores)
    total_usuarios = total_estudiantes + total_mentores + len(admins)
    promedio_gral = round(sum(a["promedio_avance"] for a in aprendices) / total_estudiantes, 1) if total_estudiantes > 0 else 0.0
    total_minutos_gral = sum(a["total_minutos"] for a in aprendices)
    cursos_completados_gral = sum(a["cursos_aprobados"] for a in aprendices)

    return {
        "status": "success",
        "organizacion": org,
        "kpis": {
            "total_estudiantes": total_estudiantes,
            "total_mentores": total_mentores,
            "total_usuarios": total_usuarios,
            "licencias_asignadas": org["licencias_asignadas"],
            "licencias_disponibles": max(0, org["licencias_asignadas"] - total_usuarios),
            "porcentaje_ocupacion": round((total_usuarios / org["licencias_asignadas"]) * 100, 1) if org["licencias_asignadas"] > 0 else 0,
            "promedio_general": promedio_gral,
            "total_minutos": total_minutos_gral,
            "cursos_completados": cursos_completados_gral
        },
        "mentores": mentores,
        "aprendices": aprendices,
        "administradores": admins
    }


@router.get("/api/metricas/graficas-progreso")
def obtener_metricas_graficas(organizacion_id: Optional[int] = None):
    """Consolida métricas estructuradas de los aprendices para renderizar gráficas interactivas con Chart.js"""
    base_where = "WHERE u.rol = 'Aprendiz'"
    params = []
    if organizacion_id:
        base_where += " AND u.organizacion_id = ?"
        params.append(organizacion_id)
        
    query_aprendices = f"""
        SELECT u.id, u.nombre, u.correo, o.nombre as organizacion_nombre,
               COALESCE(AVG(p.porcentaje_avance), 0) as promedio_avance,
               COALESCE(SUM(p.tiempo_dedicado_minutos), 0) as total_minutos,
               COUNT(p.id) as cursos_iniciados
        FROM usuarios u
        LEFT JOIN organizaciones o ON u.organizacion_id = o.id
        LEFT JOIN progreso_cursos p ON p.usuario_id = u.id
        {base_where}
        GROUP BY u.id, u.nombre, u.correo, o.nombre
        ORDER BY promedio_avance DESC
    """
    aprendices = db.execute_query(query_aprendices, tuple(params), fetchall=True) or []
    
    completados = 0   # >= 90%
    avanzados = 0     # 60% - 89%
    en_progreso = 0   # 25% - 59%
    iniciales = 0     # < 25%
    
    for a in aprendices:
        pct = float(a.get("promedio_avance") or 0.0)
        if pct >= 90:
            completados += 1
        elif pct >= 60:
            avanzados += 1
        elif pct >= 25:
            en_progreso += 1
        else:
            iniciales += 1
            
    cursos_stats = db.execute_query("""
        SELECT m.id, m.titulo,
               COALESCE(AVG(p.porcentaje_avance), 0) as promedio_curso,
               COUNT(p.id) as estudiantes_activos
        FROM material_capacitacion m
        LEFT JOIN progreso_cursos p ON p.curso_id = m.id
        WHERE (m.rol_destino != 'Mentor' OR m.rol_destino IS NULL)
        GROUP BY m.id, m.titulo
        ORDER BY estudiantes_activos DESC, promedio_curso DESC
    """, fetchall=True) or []
    cursos_stats = cursos_stats[:6]
    
    return {
        "status": "success",
        "distribucion": {
            "completados": completados,
            "avanzados": avanzados,
            "en_progreso": en_progreso,
            "iniciales": iniciales
        },
        "cursos_estadisticas": cursos_stats,
        "top_aprendices": aprendices[:5],
        "total_aprendices": len(aprendices)
    }


@router.post("/api/organizaciones/{organizacion_id}/auto-repartir")
def auto_repartir_aprendices(organizacion_id: int, repartir_todos: bool = False):
    mentores = db.execute_query("SELECT id, nombre FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor'", (organizacion_id,), fetchall=True)
    if not mentores:
        raise HTTPException(status_code=400, detail="No hay mentores registrados en esta organización.")
        
    if repartir_todos:
        db.execute_query("UPDATE usuarios SET mentor_id = NULL WHERE organizacion_id = ? AND rol = 'Aprendiz'", (organizacion_id,), commit=True)

    aprendices = db.execute_query("SELECT id, nombre FROM usuarios WHERE organizacion_id = ? AND rol = 'Aprendiz' AND mentor_id IS NULL ORDER BY nombre ASC", (organizacion_id,), fetchall=True)
    if not aprendices:
        return {"status": "success", "mensaje": "Todos los aprendices de la organización ya tienen un mentor asignado."}
        
    mentor_ids = [m["id"] for m in mentores]
    for idx, apr in enumerate(aprendices):
        m_id = mentor_ids[idx % len(mentor_ids)]
        db.execute_query("UPDATE usuarios SET mentor_id = ? WHERE id = ?", (m_id, apr["id"]), commit=True)
        
    tipo = "Balanceo Total" if repartir_todos else "Reparto de Pendientes"
    registrar_movimiento("SuperAdmin", "Grupos", f"Reparto_Automatico_{tipo}", "EXITO", f"{len(aprendices)} aprendices asignados entre {len(mentor_ids)} mentores")
    return {"status": "success", "mensaje": f"{len(aprendices)} aprendices fueron repartidos equitativamente entre {len(mentor_ids)} mentores ({tipo})."}


@router.get("/api/admin/convenio/{organizacion_id}/mentores-rendimiento")
def obtener_mentores_rendimiento_admin(organizacion_id: int):
    """Retorna el listado exclusivo de mentores con su avance en capacitaciones docentes y rendimiento"""
    org = db.execute_query("SELECT id, nombre, dominio_permitido FROM organizaciones WHERE id = ?", (organizacion_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Institución / Convenio no encontrado.")

    mentores = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.foto_perfil,
               COALESCE(u.minutos_dedicados_totales, 240) as minutos_totales
        FROM usuarios u
        WHERE u.organizacion_id = ? AND u.rol = 'Mentor'
        ORDER BY u.id ASC
    """, (organizacion_id,), fetchall=True) or []

    cursos_docentes = db.execute_query("""
        SELECT id, titulo, tipo_material, COALESCE(total_modulos, 3) as total_modulos, enlace_url
        FROM material_capacitacion
        WHERE rol_destino = 'Mentor'
        ORDER BY id ASC
    """, fetchall=True) or []

    resultado = []
    total_formacion_acumulada = 0
    total_horas_docentes = 0

    for m in mentores:
        m_id = m["id"]
        cant_aprendices = db.execute_query("SELECT COUNT(*) as c FROM usuarios WHERE mentor_id = ? AND rol = 'Aprendiz'", (m_id,), fetchone=True)
        aprendices_count = cant_aprendices["c"] if cant_aprendices else 0

        progs = db.execute_query("""
            SELECT p.curso_id, p.porcentaje_avance, p.modulos_completados, p.tiempo_dedicado_minutos, p.estado,
                   m.titulo, m.total_modulos
            FROM progreso_cursos p
            JOIN material_capacitacion m ON p.curso_id = m.id
            WHERE p.usuario_id = ? AND m.rol_destino = 'Mentor'
        """, (m_id,), fetchall=True) or []

        cursos_detalle = []
        for cd in cursos_docentes:
            prog_match = next((p for p in progs if p["curso_id"] == cd["id"]), None)
            if prog_match:
                cursos_detalle.append({
                    "curso_id": cd["id"],
                    "titulo": cd["titulo"],
                    "total_modulos": cd.get("total_modulos", 3),
                    "modulos_completados": prog_match.get("modulos_completados", 0),
                    "porcentaje_avance": round(float(prog_match.get("porcentaje_avance", 0)), 1),
                    "tiempo_minutos": int(prog_match.get("tiempo_dedicado_minutos", 0)),
                    "estado": prog_match.get("estado", "No Iniciado")
                })
            else:
                cursos_detalle.append({
                    "curso_id": cd["id"],
                    "titulo": cd["titulo"],
                    "total_modulos": cd.get("total_modulos", 3),
                    "modulos_completados": 0,
                    "porcentaje_avance": 0.0,
                    "tiempo_minutos": 0,
                    "estado": "No Iniciado"
                })

        total_cd = len(cursos_detalle)
        prom_formacion = round(sum(c["porcentaje_avance"] for c in cursos_detalle) / total_cd, 1) if total_cd > 0 else 0.0
        minutos_formacion = sum(c["tiempo_minutos"] for c in cursos_detalle)
        horas_formacion = round(minutos_formacion / 60, 1)
        cursos_completados = sum(1 for c in cursos_detalle if c["porcentaje_avance"] >= 80)

        if prom_formacion >= 80:
            rendimiento = "🏆 Destacado"
            badge_color = "emerald"
        elif prom_formacion >= 40:
            rendimiento = "⚡ En Progreso"
            badge_color = "amber"
        else:
            rendimiento = "🌱 Inicial"
            badge_color = "slate"

        total_formacion_acumulada += prom_formacion
        total_horas_docentes += horas_formacion

        resultado.append({
            "id": m_id,
            "nombre": m["nombre"],
            "correo": m["correo"],
            "foto_perfil": m.get("foto_perfil"),
            "aprendices_a_cargo": aprendices_count,
            "promedio_formacion_pct": prom_formacion,
            "cursos_completados": cursos_completados,
            "total_cursos_docentes": total_cd,
            "minutos_formacion": minutos_formacion,
            "horas_formacion": horas_formacion,
            "rendimiento": rendimiento,
            "badge_color": badge_color,
            "cursos_detalle": cursos_detalle
        })

    cant_mentores = len(resultado)
    prom_general_equipo = round(total_formacion_acumulada / cant_mentores, 1) if cant_mentores > 0 else 0.0

    return {
        "status": "success",
        "organizacion_nombre": org["nombre"],
        "total_mentores": cant_mentores,
        "promedio_formacion_equipo": prom_general_equipo,
        "total_horas_docentes": round(total_horas_docentes, 1),
        "mentores_destacados": sum(1 for r in resultado if r["rendimiento"] == "🏆 Destacado"),
        "data": resultado
    }


@router.get("/api/admin/convenio/{organizacion_id}/reporte-excel-mentores")
def descargar_reporte_excel_mentores_admin(organizacion_id: int):
    """Genera y descarga informe oficial en Excel (.xlsx) de la formación docente y rendimiento de mentores"""
    try:
        org = db.execute_query("SELECT id, nombre, dominio_permitido FROM organizaciones WHERE id = ?", (organizacion_id,), fetchone=True)
        if not org:
            raise HTTPException(status_code=404, detail="Institución no encontrada.")

        now = datetime.now()
        wb = openpyxl.Workbook()

        fill_navy = PatternFill(start_color="0A192F", end_color="0A192F", fill_type="solid")
        fill_sub = PatternFill(start_color="0F273F", end_color="0F273F", fill_type="solid")
        fill_kpi = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

        font_title = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
        font_sub = Font(name="Segoe UI", size=9, italic=True, color="FFFFFF")
        font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        font_kpi_num = Font(name="Segoe UI", size=16, bold=True, color="0A192F")
        font_bold = Font(name="Segoe UI", size=9, bold=True)
        font_normal = Font(name="Segoe UI", size=9)

        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        datos_resp = obtener_mentores_rendimiento_admin(organizacion_id)
        mentores_data = datos_resp.get("data", [])

        # -------------------------------------------------------------
        # HOJA 1: RESUMEN FORMACIÓN DOCENTE
        # -------------------------------------------------------------
        ws_res = wb.active
        ws_res.title = "Resumen Formación Docente"
        ws_res.views.sheetView[0].showGridLines = True

        ws_res.merge_cells("A1:G1")
        t1 = ws_res["A1"]
        t1.value = "CENTRO DE MANDO EDTECH · REPORTE DE CAPACITACIÓN Y DESEMPEÑO DOCENTE"
        t1.font = font_title
        t1.fill = fill_navy
        t1.alignment = Alignment(horizontal="center", vertical="center")
        ws_res.row_dimensions[1].height = 36

        ws_res.merge_cells("A2:G2")
        sub1 = ws_res["A2"]
        sub1.value = f"Institución: {org['nombre']} · Dominio: {org.get('dominio_permitido', '')} · {now.strftime('%d/%m/%Y a las %H:%M:%S')}"
        sub1.font = font_sub
        sub1.fill = fill_sub
        sub1.alignment = Alignment(horizontal="center", vertical="center")
        ws_res.row_dimensions[2].height = 20

        kpis = [
            ("Total Mentores", str(datos_resp["total_mentores"]), "A4", "B5"),
            ("Promedio Formación Pedagógica", f"{datos_resp['promedio_formacion_equipo']}%", "C4", "D5"),
            ("Horas de Capacitación Acumuladas", f"{datos_resp['total_horas_docentes']} hrs", "E4", "F5"),
            ("Mentores con Desempeño Destacado", str(datos_resp["mentores_destacados"]), "A7", "B8"),
        ]
        for titulo, valor, top_left, bot_right in kpis:
            ws_res.merge_cells(f"{top_left}:{bot_right}")
            cell = ws_res[top_left]
            cell.value = f"{titulo}\n{valor}"
            cell.font = font_kpi_num
            cell.fill = fill_kpi
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            for row in ws_res[f"{top_left}:{bot_right}"]:
                for c in row:
                    c.border = border_thin

        ws_res.row_dimensions[4].height = 28
        ws_res.row_dimensions[5].height = 28
        ws_res.row_dimensions[7].height = 28
        ws_res.row_dimensions[8].height = 28

        # -------------------------------------------------------------
        # HOJA 2: DESEMPEÑO Y TABLA DE MENTORES (CON BAR CHART)
        # -------------------------------------------------------------
        ws_men = wb.create_sheet(title="Desempeño de Mentores")
        ws_men.views.sheetView[0].showGridLines = True
        ws_men.row_dimensions[1].height = 24

        headers_men = ["Puesto", "Mentor Tutor", "Correo Institucional", "Estudiantes a Cargo", "Avance Formación %", "Cursos Completados", "Horas Capacitación", "Nivel de Desempeño"]
        for c_i, h in enumerate(headers_men, start=1):
            cell = ws_men.cell(row=1, column=c_i, value=h)
            cell.font = font_header
            cell.fill = fill_navy
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_thin

        mentores_data.sort(key=lambda x: x["promedio_formacion_pct"], reverse=True)

        for r_i, m_item in enumerate(mentores_data, start=2):
            ws_men.cell(row=r_i, column=1, value=r_i - 1).alignment = Alignment(horizontal="center")
            ws_men.cell(row=r_i, column=2, value=m_item["nombre"]).font = font_bold
            ws_men.cell(row=r_i, column=3, value=m_item["correo"])
            ws_men.cell(row=r_i, column=4, value=m_item["aprendices_a_cargo"]).alignment = Alignment(horizontal="center")
            ws_men.cell(row=r_i, column=5, value=m_item["promedio_formacion_pct"]).alignment = Alignment(horizontal="center")
            ws_men.cell(row=r_i, column=6, value=f"{m_item['cursos_completados']} de {m_item['total_cursos_docentes']}").alignment = Alignment(horizontal="center")
            ws_men.cell(row=r_i, column=7, value=m_item["horas_formacion"]).alignment = Alignment(horizontal="center")
            ws_men.cell(row=r_i, column=8, value=m_item["rendimiento"]).alignment = Alignment(horizontal="center")
            for c in range(1, 9):
                ws_men.cell(row=r_i, column=c).border = border_thin
                if c != 2:
                    ws_men.cell(row=r_i, column=c).font = font_normal

        if len(mentores_data) > 0:
            chart_m = BarChart()
            chart_m.type = "col"
            chart_m.style = 11
            chart_m.title = "Avance en Formación Docente por Mentor (%)"
            chart_m.y_axis.title = "Porcentaje (%)"
            chart_m.x_axis.title = "Mentores"
            chart_m.width = 16
            chart_m.height = 10

            data_ref = Reference(ws_men, min_col=5, min_row=1, max_row=len(mentores_data) + 1)
            cats_ref = Reference(ws_men, min_col=2, min_row=2, max_row=len(mentores_data) + 1)
            chart_m.add_data(data_ref, titles_from_data=True)
            chart_m.set_categories(cats_ref)
            ws_men.add_chart(chart_m, "J3")

        # -------------------------------------------------------------
        # HOJA 3: DETALLE CURSOS PEDAGÓGICOS
        # -------------------------------------------------------------
        ws_det = wb.create_sheet(title="Detalle Cursos Pedagógicos")
        ws_det.views.sheetView[0].showGridLines = True
        ws_det.row_dimensions[1].height = 24

        headers_det = ["Mentor Tutor", "Correo", "Curso de Capacitación Docente", "Módulos Completados", "Avance %", "Tiempo (min)", "Estado"]
        for c_i, h in enumerate(headers_det, start=1):
            cell = ws_det.cell(row=1, column=c_i, value=h)
            cell.font = font_header
            cell.fill = fill_sub
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_thin

        fila_det = 2
        for m_item in mentores_data:
            for c_det in m_item.get("cursos_detalle", []):
                ws_det.cell(row=fila_det, column=1, value=m_item["nombre"]).font = font_bold
                ws_det.cell(row=fila_det, column=2, value=m_item["correo"])
                ws_det.cell(row=fila_det, column=3, value=c_det["titulo"])
                ws_det.cell(row=fila_det, column=4, value=f"{c_det['modulos_completados']} de {c_det['total_modulos']}").alignment = Alignment(horizontal="center")
                ws_det.cell(row=fila_det, column=5, value=c_det["porcentaje_avance"]).alignment = Alignment(horizontal="center")
                ws_det.cell(row=fila_det, column=6, value=c_det["tiempo_minutos"]).alignment = Alignment(horizontal="center")
                ws_det.cell(row=fila_det, column=7, value=c_det["estado"]).alignment = Alignment(horizontal="center")

                for c in range(1, 8):
                    ws_det.cell(row=fila_det, column=c).border = border_thin
                    if c != 1:
                        ws_det.cell(row=fila_det, column=c).font = font_normal
                fila_det += 1

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

        nombre_archivo = f"reporte_formacion_mentores_org_{organizacion_id}_{now.strftime('%Y_%m_%d_%H%M%S')}.xlsx"
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        registrar_movimiento("Admin", "Docencia", "Exportar_Excel_Mentores", "EXITO", f"Reporte de mentores '{nombre_archivo}' con gráficas descargado")
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
        )
    except Exception as e:
        print(f">> Error exportando reporte de mentores: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando reporte de mentores: {str(e)}")


@router.get("/api/organizaciones/{org_id}/integrantes-por-rol")
def listar_integrantes_por_rol(org_id: int):
    """Devuelve los integrantes de una organización agrupados por rol (Administradores, Mentores, Aprendices)"""
    admins = db.execute_query(
        "SELECT id, nombre, correo, rol FROM usuarios WHERE organizacion_id = ? AND rol IN ('Administrador', 'Super Administrador') ORDER BY nombre ASC",
        (org_id,), fetchall=True
    ) or []
    mentores = db.execute_query(
        "SELECT id, nombre, correo, rol FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor' ORDER BY nombre ASC",
        (org_id,), fetchall=True
    ) or []
    aprendices = db.execute_query(
        "SELECT id, nombre, correo, rol, mentor_id FROM usuarios WHERE organizacion_id = ? AND rol = 'Aprendiz' ORDER BY nombre ASC",
        (org_id,), fetchall=True
    ) or []
    return {
        "status": "success",
        "administradores": admins,
        "mentores": mentores,
        "aprendices": aprendices
    }


@router.post("/api/superadmin/colecciones/enviar-a-organizacion")
def enviar_coleccion_a_organizacion(datos: EnviarColeccionOrgReq):
    """Asigna y envía una colección siguiendo el flujo jerárquico: Institución -> Mentores -> Aprendices"""
    mat = db.execute_query("SELECT id, titulo, total_modulos, enlace_url FROM material_capacitacion WHERE id = ?", (datos.material_id,), fetchone=True)
    if not mat:
        raise HTTPException(status_code=404, detail="La colección o material no existe en el catálogo.")

    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (datos.organizacion_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="La institución u organización destino no fue encontrada.")

    nivel = (datos.destinatario_tipo or "Institución").strip()
    dest_id = datos.destinatario_id if (datos.destinatario_id and datos.destinatario_id > 0) else None

    # CASO 1: ENVIAR A LA INSTITUCIÓN (ADMINISTRADORES)
    if nivel == "Institución":
        ya_enviada = db.execute_query(
            "SELECT id, fecha_asignacion FROM asignacion_material WHERE material_id = ? AND organizacion_id = ? AND (destinatario_tipo = 'Institución' OR destinatario_tipo IS NULL)",
            (datos.material_id, datos.organizacion_id),
            fetchone=True
        )
        if ya_enviada:
            raise HTTPException(
                status_code=400,
                detail=f"⚠️ ¡Alerta! La colección '{mat['titulo']}' ya fue enviada previamente a la institución '{org['nombre']}'. Los administradores ya disponen de ella para distribuirla a sus mentores."
            )
        db.execute_query(
            "INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, destinatario_id, asignado_por_id, asignado_por_rol, fecha_asignacion) VALUES (?, ?, 'Institución', NULL, ?, ?, DATETIME('now', 'localtime'))",
            (datos.material_id, datos.organizacion_id, datos.remitente_id, datos.remitente_rol),
            commit=True
        )
        mensaje_resp = f"✓ Colección '{mat['titulo']}' enviada con éxito a la institución {org['nombre']}. Los administradores ya pueden distribuirla a sus mentores."

    # CASO 2: ENVIAR A MENTORES
    elif nivel == "Mentores":
        if dest_id:
            mentor = db.execute_query("SELECT id, nombre FROM usuarios WHERE id = ? AND rol = 'Mentor'", (dest_id,), fetchone=True)
            if not mentor:
                raise HTTPException(status_code=404, detail="El mentor seleccionado no fue encontrado.")
            ya_enviada = db.execute_query(
                "SELECT id FROM asignacion_material WHERE material_id = ? AND organizacion_id = ? AND destinatario_tipo = 'Mentores' AND destinatario_id = ?",
                (datos.material_id, datos.organizacion_id, dest_id),
                fetchone=True
            )
            if ya_enviada:
                raise HTTPException(
                    status_code=400,
                    detail=f"⚠️ ¡Alerta! La colección '{mat['titulo']}' ya fue asignada previamente al mentor '{mentor['nombre']}'."
                )
            db.execute_query(
                "INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, destinatario_id, asignado_por_id, asignado_por_rol, fecha_asignacion) VALUES (?, ?, 'Mentores', ?, ?, ?, DATETIME('now', 'localtime'))",
                (datos.material_id, datos.organizacion_id, dest_id, datos.remitente_id, datos.remitente_rol),
                commit=True
            )
            # Asegurar entrada en progreso_cursos para que el mentor la visualice
            existe_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (dest_id, datos.material_id), fetchone=True)
            if not existe_p:
                db.execute_query(
                    "INSERT INTO progreso_cursos (usuario_id, curso_id, modulos_completados, porcentaje_avance, tiempo_dedicado_minutos, estado, fecha_actualizacion) VALUES (?, ?, 0, 0.0, 0, 'No Iniciado', DATETIME('now', 'localtime'))",
                    (dest_id, datos.material_id),
                    commit=True
                )
            mensaje_resp = f"✓ Colección '{mat['titulo']}' enviada con éxito al mentor {mentor['nombre']} para preparación docente."
        else:
            ya_enviada = db.execute_query(
                "SELECT id FROM asignacion_material WHERE material_id = ? AND organizacion_id = ? AND destinatario_tipo = 'Mentores' AND (destinatario_id IS NULL OR destinatario_id = 0)",
                (datos.material_id, datos.organizacion_id),
                fetchone=True
            )
            if ya_enviada:
                raise HTTPException(
                    status_code=400,
                    detail=f"⚠️ ¡Alerta! La colección '{mat['titulo']}' ya fue asignada previamente a todos los mentores de '{org['nombre']}'."
                )
            db.execute_query(
                "INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, destinatario_id, asignado_por_id, asignado_por_rol, fecha_asignacion) VALUES (?, ?, 'Mentores', NULL, ?, ?, DATETIME('now', 'localtime'))",
                (datos.material_id, datos.organizacion_id, datos.remitente_id, datos.remitente_rol),
                commit=True
            )
            mentores = db.execute_query("SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor'", (datos.organizacion_id,), fetchall=True) or []
            for m in mentores:
                existe_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (m["id"], datos.material_id), fetchone=True)
                if not existe_p:
                    db.execute_query(
                        "INSERT INTO progreso_cursos (usuario_id, curso_id, modulos_completados, porcentaje_avance, tiempo_dedicado_minutos, estado, fecha_actualizacion) VALUES (?, ?, 0, 0.0, 0, 'No Iniciado', DATETIME('now', 'localtime'))",
                        (m["id"], datos.material_id),
                        commit=True
                    )
            mensaje_resp = f"✓ Colección '{mat['titulo']}' enviada con éxito a los {len(mentores)} mentores de {org['nombre']}."

    # CASO 3: ENVIAR A APRENDICES (ESTUDIANTES)
    else:
        if dest_id:
            apr = db.execute_query("SELECT id, nombre FROM usuarios WHERE id = ? AND rol = 'Aprendiz'", (dest_id,), fetchone=True)
            if not apr:
                raise HTTPException(status_code=404, detail="El aprendiz seleccionado no fue encontrado.")
            existe_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (dest_id, datos.material_id), fetchone=True)
            if existe_p:
                raise HTTPException(
                    status_code=400,
                    detail=f"⚠️ ¡Alerta! La colección '{mat['titulo']}' ya fue asignada previamente al estudiante '{apr['nombre']}'."
                )
            db.execute_query(
                "INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, destinatario_id, asignado_por_id, asignado_por_rol, fecha_asignacion) VALUES (?, ?, 'Aprendices', ?, ?, ?, DATETIME('now', 'localtime'))",
                (datos.material_id, datos.organizacion_id, dest_id, datos.remitente_id, datos.remitente_rol),
                commit=True
            )
            db.execute_query(
                "INSERT INTO progreso_cursos (usuario_id, curso_id, modulos_completados, porcentaje_avance, tiempo_dedicado_minutos, estado, fecha_actualizacion) VALUES (?, ?, 0, 0.0, 0, 'No Iniciado', DATETIME('now', 'localtime'))",
                (dest_id, datos.material_id),
                commit=True
            )
            mensaje_resp = f"✓ Colección '{mat['titulo']}' enviada y matriculada con éxito al estudiante {apr['nombre']}."
        else:
            ya_enviada = db.execute_query(
                "SELECT id FROM asignacion_material WHERE material_id = ? AND organizacion_id = ? AND destinatario_tipo = 'Aprendices' AND (destinatario_id IS NULL OR destinatario_id = 0)",
                (datos.material_id, datos.organizacion_id),
                fetchone=True
            )
            if ya_enviada:
                raise HTTPException(
                    status_code=400,
                    detail=f"⚠️ ¡Alerta! La colección '{mat['titulo']}' ya fue asignada previamente a todos los aprendices de '{org['nombre']}'."
                )
            db.execute_query(
                "INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, destinatario_id, asignado_por_id, asignado_por_rol, fecha_asignacion) VALUES (?, ?, 'Aprendices', NULL, ?, ?, DATETIME('now', 'localtime'))",
                (datos.material_id, datos.organizacion_id, datos.remitente_id, datos.remitente_rol),
                commit=True
            )
            aprendices = db.execute_query("SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Aprendiz'", (datos.organizacion_id,), fetchall=True) or []
            for ap in aprendices:
                existe_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (ap["id"], datos.material_id), fetchone=True)
                if not existe_p:
                    db.execute_query(
                        "INSERT INTO progreso_cursos (usuario_id, curso_id, modulos_completados, porcentaje_avance, tiempo_dedicado_minutos, estado, fecha_actualizacion) VALUES (?, ?, 0, 0.0, 0, 'No Iniciado', DATETIME('now', 'localtime'))",
                        (ap["id"], datos.material_id),
                        commit=True
                    )
            mensaje_resp = f"✓ Colección '{mat['titulo']}' enviada y matriculada con éxito a los {len(aprendices)} aprendices de {org['nombre']}."

    registrar_movimiento(
        datos.remitente_rol or "Administración", "Colecciones", "Enviar_Coleccion_Org", "EXITO",
        f"Colección '{mat['titulo']}' enviada a {org['nombre']} [Nivel: {nivel}, Destinatario ID: {dest_id or 'Todos'}]"
    )

    return {
        "status": "success",
        "mensaje": mensaje_resp,
        "material_id": datos.material_id,
        "organizacion_id": datos.organizacion_id,
        "destinatario_tipo": nivel,
        "destinatario_id": dest_id
    }


@router.get("/api/superadmin/colecciones/asignaciones-todas")
def listar_todas_las_asignaciones_colecciones():
    """Retorna un mapeo completo de asignaciones existentes para validación y alertas inmediatas en frontend"""
    filas = db.execute_query("""
        SELECT a.id, a.material_id, a.organizacion_id, a.fecha_asignacion,
               COALESCE(a.destinatario_tipo, 'Institución') as destinatario_tipo,
               a.destinatario_id,
               m.titulo as material_titulo, COALESCE(m.total_modulos, 3) as total_modulos,
               COALESCE(o.nombre, 'Acceso Global') as organizacion_nombre
        FROM asignacion_material a
        JOIN material_capacitacion m ON m.id = a.material_id
        LEFT JOIN organizaciones o ON o.id = a.organizacion_id
        ORDER BY a.id DESC
    """, fetchall=True) or []
    return {"status": "success", "data": filas}


@router.delete("/api/superadmin/colecciones/desvincular-organizacion/{material_id}/{organizacion_id}")
def desvincular_coleccion_organizacion(material_id: int, organizacion_id: int):
    """Permite al SuperAdmin revocar una colección asignada a una organización"""
    db.execute_query(
        "DELETE FROM asignacion_material WHERE material_id = ? AND organizacion_id = ?",
        (material_id, organizacion_id),
        commit=True
    )
    registrar_movimiento("SuperAdmin", "Colecciones", "Desvincular_Coleccion", "EXITO", f"Colección ID {material_id} desvinculada de Org ID {organizacion_id}")
    return {"status": "success", "mensaje": "Colección desvinculada de la organización exitosamente."}


def _construir_comparativa_instituciones():
    """Construye la lista comparativa de todas las instituciones activas con conteos reales de Aprendices, Mentores, Administradores y % de avance"""
    orgs_all = db.execute_query("""
        SELECT id, nombre, tipo_organizacion, dominio_permitido, licencias_asignadas,
               porcentaje_avance_manual, color_primario, color_acento, logo_url
        FROM organizaciones
        ORDER BY id ASC
    """, fetchall=True) or []
    comparativa = []
    for o in orgs_all:
        oid = o["id"]
        c_admin = (db.execute_query("SELECT COUNT(*) as c FROM usuarios WHERE organizacion_id = ? AND rol = 'Administrador'", (oid,), fetchone=True) or {}).get("c", 0)
        c_men = (db.execute_query("SELECT COUNT(*) as c FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor'", (oid,), fetchone=True) or {}).get("c", 0)
        c_apr = (db.execute_query("SELECT COUNT(*) as c FROM usuarios WHERE organizacion_id = ? AND rol = 'Aprendiz'", (oid,), fetchone=True) or {}).get("c", 0)
        cols = db.execute_query("""
            SELECT DISTINCT m.id, m.titulo, COALESCE(m.total_modulos, 3) as total_modulos
            FROM material_capacitacion m
            JOIN asignacion_material a ON m.id = a.material_id
            WHERE a.organizacion_id = ?
        """, (oid,), fetchall=True) or []
        progs = db.execute_query("""
            SELECT p.usuario_id, p.curso_id, COALESCE(p.porcentaje_avance, 0) as pct,
                   COALESCE(p.modulos_completados, 0) as mods, COALESCE(p.tiempo_dedicado_minutos, 0) as mins
            FROM progreso_cursos p
            JOIN usuarios u ON u.id = p.usuario_id
            WHERE u.organizacion_id = ? AND u.rol = 'Aprendiz'
        """, (oid,), fetchall=True) or []
        mods_comp = sum(int(p.get("mods") or 0) for p in progs)
        mods_asig = c_apr * sum(int(c.get("total_modulos") or 3) for c in cols)
        mins_tot = sum(int(p.get("mins") or 0) for p in progs)
        prom_real = round(sum(float(p.get("pct") or 0) for p in progs) / len(progs), 1) if progs else 0.0
        manual_val = o.get("porcentaje_avance_manual")
        pct_final = round(float(manual_val), 1) if manual_val is not None else prom_real
        comparativa.append({
            "id": oid,
            "nombre": o["nombre"],
            "tipo_organizacion": o.get("tipo_organizacion") or "Institución",
            "dominio_permitido": o.get("dominio_permitido") or "LIBRE",
            "licencias_asignadas": int(o.get("licencias_asignadas") or 100),
            "total_administradores": int(c_admin or 0),
            "total_mentores": int(c_men or 0),
            "total_aprendices": int(c_apr or 0),
            "total_integrantes": int((c_admin or 0) + (c_men or 0) + (c_apr or 0)),
            "total_colecciones": len(cols),
            "modulos_completados": mods_comp,
            "modulos_asignados": mods_asig,
            "horas_estudio": round(mins_tot / 60.0, 1),
            "promedio_real": prom_real,
            "porcentaje_avance_manual": round(float(manual_val), 1) if manual_val is not None else None,
            "porcentaje_avance": pct_final,
            "es_manual": manual_val is not None
        })
    return comparativa


@router.get("/api/superadmin/analitica-global")
@router.get("/api/superadmin/organizaciones/{org_id}/analitica-colecciones")
def obtener_analitica_colecciones_organizacion(org_id: int = 0):
    """Retorna la analítica detallada (Global Consolidada si org_id=0 o Individual por Institución) con desglose de Aprendices, Mentores y Administradores"""
    comparativa = _construir_comparativa_instituciones()

    if org_id == 0:
        # VISTA CONSOLIDADA GLOBAL DE TODAS LAS INSTITUCIONES
        aprendices = db.execute_query("""
            SELECT u.id, u.nombre, u.correo, u.organizacion_id, o.nombre as organizacion_nombre,
                   u.mentor_id, m.nombre as mentor_nombre
            FROM usuarios u
            LEFT JOIN organizaciones o ON u.organizacion_id = o.id
            LEFT JOIN usuarios m ON u.mentor_id = m.id
            WHERE u.rol = 'Aprendiz' AND u.organizacion_id IS NOT NULL
            ORDER BY o.nombre ASC, u.nombre ASC
        """, fetchall=True) or []
        mentores = db.execute_query("""
            SELECT u.id, u.nombre, u.correo, u.organizacion_id, o.nombre as organizacion_nombre,
                   (SELECT COUNT(*) FROM usuarios a WHERE a.mentor_id = u.id AND a.rol = 'Aprendiz') as total_aprendices_asignados
            FROM usuarios u
            LEFT JOIN organizaciones o ON u.organizacion_id = o.id
            WHERE u.rol = 'Mentor' AND u.organizacion_id IS NOT NULL
            ORDER BY o.nombre ASC, u.nombre ASC
        """, fetchall=True) or []
        admins = db.execute_query("""
            SELECT u.id, u.nombre, u.correo, u.organizacion_id, o.nombre as organizacion_nombre
            FROM usuarios u
            LEFT JOIN organizaciones o ON u.organizacion_id = o.id
            WHERE u.rol = 'Administrador' AND u.organizacion_id IS NOT NULL
            ORDER BY o.nombre ASC, u.nombre ASC
        """, fetchall=True) or []
        colecciones = db.execute_query("""
            SELECT DISTINCT m.id, m.titulo, m.tipo_material, m.enlace_url, m.rol_destino,
                   COALESCE(m.total_modulos, 3) as total_modulos,
                   MAX(a.fecha_asignacion) as fecha_asignacion
            FROM material_capacitacion m
            JOIN asignacion_material a ON m.id = a.material_id
            GROUP BY m.id, m.titulo, m.tipo_material, m.enlace_url, m.rol_destino, m.total_modulos
            ORDER BY m.id DESC
        """, fetchall=True) or []
        org_info = {
            "id": 0,
            "nombre": "Vista Consolidada Global (Todas las Instituciones)",
            "tipo_organizacion": "Consolidado Multi-Institucional",
            "dominio_permitido": "GLOBAL",
            "licencias_asignadas": sum(item["licencias_asignadas"] for item in comparativa),
            "porcentaje_avance_manual": None
        }
    else:
        org = db.execute_query("""
            SELECT id, nombre, tipo_organizacion, dominio_permitido, licencias_asignadas, porcentaje_avance_manual
            FROM organizaciones
            WHERE id = ?
        """, (org_id,), fetchone=True)
        if not org:
            raise HTTPException(status_code=404, detail="Organización no encontrada.")
        org_info = dict(org)

        colecciones = db.execute_query("""
            SELECT DISTINCT m.id, m.titulo, m.tipo_material, m.enlace_url, m.rol_destino,
                   COALESCE(m.total_modulos, 3) as total_modulos,
                   a.fecha_asignacion
            FROM material_capacitacion m
            JOIN asignacion_material a ON m.id = a.material_id
            WHERE a.organizacion_id = ?
            ORDER BY m.id DESC
        """, (org_id,), fetchall=True) or []

        aprendices = db.execute_query("""
            SELECT u.id, u.nombre, u.correo, u.organizacion_id, o.nombre as organizacion_nombre,
                   u.mentor_id, m.nombre as mentor_nombre
            FROM usuarios u
            LEFT JOIN organizaciones o ON u.organizacion_id = o.id
            LEFT JOIN usuarios m ON u.mentor_id = m.id
            WHERE u.organizacion_id = ? AND u.rol = 'Aprendiz'
            ORDER BY u.nombre ASC
        """, (org_id,), fetchall=True) or []

        mentores = db.execute_query("""
            SELECT u.id, u.nombre, u.correo, u.organizacion_id,
                   (SELECT COUNT(*) FROM usuarios a WHERE a.mentor_id = u.id AND a.organizacion_id = ?) as total_aprendices_asignados
            FROM usuarios u
            WHERE u.organizacion_id = ? AND u.rol = 'Mentor'
            ORDER BY u.nombre ASC
        """, (org_id, org_id), fetchall=True) or []

        admins = db.execute_query("""
            SELECT u.id, u.nombre, u.correo, u.organizacion_id
            FROM usuarios u
            WHERE u.organizacion_id = ? AND u.rol = 'Administrador'
            ORDER BY u.nombre ASC
        """, (org_id,), fetchall=True) or []

    aprendices_ids = [a["id"] for a in aprendices]
    colecciones_ids = [c["id"] for c in colecciones]

    progresos_map = {}
    if aprendices_ids and colecciones_ids:
        placeholders_u = ",".join("?" for _ in aprendices_ids)
        placeholders_c = ",".join("?" for _ in colecciones_ids)
        params = tuple(aprendices_ids + colecciones_ids)
        progs = db.execute_query(f"""
            SELECT p.usuario_id, p.curso_id, p.porcentaje_avance, p.tiempo_dedicado_minutos,
                   COALESCE(p.modulos_completados, 0) as modulos_completados,
                   COALESCE(p.estado, 'No Iniciado') as estado,
                   p.fecha_actualizacion
            FROM progreso_cursos p
            WHERE p.usuario_id IN ({placeholders_u}) AND p.curso_id IN ({placeholders_c})
        """, params, fetchall=True) or []
        for p in progs:
            progresos_map[(p["usuario_id"], p["curso_id"])] = dict(p)

    colecciones_analitica = []
    total_estudiantes_org = len(aprendices)

    for c in colecciones:
        c_id = c["id"]
        t_mod = int(c["total_modulos"] or 3)
        avances_col = []
        modulos_dist = {f"{i}_modulos": 0 for i in range(t_mod + 1)}
        completados_col = 0
        en_progreso_col = 0
        no_iniciados_col = 0
        tiempo_col = 0

        for a in aprendices:
            prog = progresos_map.get((a["id"], c_id))
            if prog:
                m_comp = min(int(prog.get("modulos_completados") or 0), t_mod)
                pct_guardado = float(prog.get("porcentaje_avance") or 0.0)
                pct = pct_guardado if pct_guardado > 0 else (round((m_comp / max(1, t_mod)) * 100, 1) if t_mod > 0 else 0.0)
                tiempo_col += int(prog.get("tiempo_dedicado_minutos") or 0)
            else:
                m_comp = 0
                pct = 0.0

            avances_col.append(pct)
            clave_mod = f"{m_comp}_modulos"
            modulos_dist[clave_mod] = modulos_dist.get(clave_mod, 0) + 1

            if pct >= 100 or (m_comp >= t_mod and t_mod > 0):
                completados_col += 1
            elif pct > 0 or m_comp > 0:
                en_progreso_col += 1
            else:
                no_iniciados_col += 1

        prom_col = round(sum(avances_col) / len(avances_col), 1) if avances_col else 0.0
        if org_id != 0 and org_info.get("porcentaje_avance_manual") is not None and not avances_col:
            prom_col = round(float(org_info["porcentaje_avance_manual"]), 1)

        colecciones_analitica.append({
            **dict(c),
            "total_aprendices_matriculados": total_estudiantes_org,
            "promedio_avance": prom_col,
            "estudiantes_completados": completados_col,
            "estudiantes_en_progreso": en_progreso_col,
            "estudiantes_no_iniciados": no_iniciados_col,
            "tiempo_dedicado_minutos": tiempo_col,
            "distribucion_modulos": modulos_dist
        })

    estudiantes_detalle = []
    for a in aprendices:
        cursos_estudiante = []
        suma_pct = 0.0
        total_mod_comp = 0
        tiempo_est = 0

        for c in colecciones:
            prog = progresos_map.get((a["id"], c["id"]))
            t_mod = int(c["total_modulos"] or 3)
            if prog:
                m_comp = min(int(prog.get("modulos_completados") or 0), t_mod)
                pct_guardado = float(prog.get("porcentaje_avance") or 0.0)
                pct = pct_guardado if pct_guardado > 0 else (round((m_comp / max(1, t_mod)) * 100, 1) if t_mod > 0 else 0.0)
                t_min = int(prog.get("tiempo_dedicado_minutos") or 0)
                est = prog.get("estado") or ("Completado" if pct >= 100 or m_comp >= t_mod else ("En Progreso" if pct > 0 or m_comp > 0 else "No Iniciado"))
            else:
                m_comp = 0
                pct = 0.0
                t_min = 0
                est = "No Iniciado"

            suma_pct += pct
            total_mod_comp += m_comp
            tiempo_est += t_min

            cursos_estudiante.append({
                "curso_id": c["id"],
                "titulo": c["titulo"],
                "total_modulos": t_mod,
                "modulos_completados": m_comp,
                "porcentaje_avance": pct,
                "tiempo_dedicado_minutos": t_min,
                "estado": est
            })

        # Si el aprendiz tiene progresos pero la org no tenía colecciones en asignacion_material, consultar sus cursos directos
        if not colecciones:
            progs_directos = db.execute_query("""
                SELECT p.curso_id, COALESCE(m.titulo, 'Módulo Institucional') as titulo,
                       COALESCE(m.total_modulos, 3) as total_modulos,
                       COALESCE(p.modulos_completados, 0) as modulos_completados,
                       COALESCE(p.porcentaje_avance, 0) as porcentaje_avance,
                       COALESCE(p.tiempo_dedicado_minutos, 0) as tiempo_dedicado_minutos,
                       COALESCE(p.estado, 'En Progreso') as estado
                FROM progreso_cursos p
                LEFT JOIN material_capacitacion m ON m.id = p.curso_id
                WHERE p.usuario_id = ?
            """, (a["id"],), fetchall=True) or []
            for pd in progs_directos:
                cursos_estudiante.append(dict(pd))
                suma_pct += float(pd.get("porcentaje_avance") or 0.0)
                total_mod_comp += int(pd.get("modulos_completados") or 0)
                tiempo_est += int(pd.get("tiempo_dedicado_minutos") or 0)

        divisor = len(cursos_estudiante) if cursos_estudiante else 1
        prom_est = round(suma_pct / divisor, 1) if cursos_estudiante else 0.0

        estudiantes_detalle.append({
            "usuario_id": a["id"],
            "nombre": a["nombre"],
            "correo": a["correo"],
            "organizacion_id": a.get("organizacion_id"),
            "organizacion_nombre": a.get("organizacion_nombre") or org_info.get("nombre"),
            "mentor_id": a["mentor_id"],
            "mentor_nombre": a["mentor_nombre"] or "Sin Mentor Asignado",
            "promedio_avance": prom_est,
            "total_modulos_completados": total_mod_comp,
            "tiempo_dedicado_minutos": tiempo_est,
            "cursos": cursos_estudiante
        })

    if org_id == 0:
        prom_general = round(sum(item["porcentaje_avance"] for item in comparativa) / len(comparativa), 1) if comparativa else 0.0
    else:
        manual_org = org_info.get("porcentaje_avance_manual")
        if manual_org is not None:
            prom_general = round(float(manual_org), 1)
        elif estudiantes_detalle:
            prom_general = round(sum(e["promedio_avance"] for e in estudiantes_detalle) / len(estudiantes_detalle), 1)
        elif colecciones_analitica:
            prom_general = round(sum(c["promedio_avance"] for c in colecciones_analitica) / len(colecciones_analitica), 1)
        else:
            prom_general = 0.0

    modulos_completados_tot = sum(e["total_modulos_completados"] for e in estudiantes_detalle)
    modulos_posibles_tot = max(total_estudiantes_org * sum(int(c["total_modulos"] or 3) for c in colecciones), modulos_completados_tot)
    tasa_finalizacion = prom_general if (org_id != 0 and org_info.get("porcentaje_avance_manual") is not None) else (
        round((modulos_completados_tot / max(1, modulos_posibles_tot)) * 100, 1) if modulos_posibles_tot > 0 else prom_general
    )

    return {
        "status": "success",
        "es_vista_global": org_id == 0,
        "organizacion": org_info,
        "kpis": {
            "total_instituciones": len(comparativa),
            "total_administradores": len(admins),
            "total_mentores": len(mentores),
            "total_aprendices": total_estudiantes_org,
            "total_colecciones": len(colecciones_analitica),
            "promedio_general_org": prom_general,
            "porcentaje_avance_manual": org_info.get("porcentaje_avance_manual"),
            "modulos_completados_totales": modulos_completados_tot,
            "modulos_asignados_totales": modulos_posibles_tot,
            "tasa_finalizacion_org": tasa_finalizacion,
            "horas_estudio_totales": round(sum(e["tiempo_dedicado_minutos"] for e in estudiantes_detalle) / 60, 1)
        },
        "instituciones_comparativa": comparativa,
        "colecciones": colecciones_analitica,
        "estudiantes": estudiantes_detalle,
        "mentores": [dict(m) for m in mentores],
        "administradores": [dict(ad) for ad in admins]
    }


@router.post("/api/superadmin/control-avance/institucion")
def controlar_avance_institucion(datos: ControlAvanceInstitucionReq):
    """Permite al Superadministrador definir o restablecer manualmente el porcentaje de avance de una institución y sincronizarlo en Azure SQL"""
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (datos.organizacion_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="La institución seleccionada no existe.")

    pct_val = round(max(0.0, min(100.0, float(datos.porcentaje_avance))), 1) if datos.porcentaje_avance is not None else None
    db.execute_query(
        "UPDATE organizaciones SET porcentaje_avance_manual = ? WHERE id = ?",
        (pct_val, datos.organizacion_id),
        commit=True
    )

    aprendices_actualizados = 0
    if pct_val is not None and datos.sincronizar_aprendices:
        aprendices = db.execute_query(
            "SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Aprendiz'",
            (datos.organizacion_id,),
            fetchall=True
        ) or []
        cols = db.execute_query("""
            SELECT DISTINCT m.id, COALESCE(m.total_modulos, 3) as total_modulos
            FROM material_capacitacion m
            JOIN asignacion_material a ON m.id = a.material_id
            WHERE a.organizacion_id = ?
        """, (datos.organizacion_id,), fetchall=True) or []
        if not cols:
            cols = db.execute_query("SELECT id, COALESCE(total_modulos, 3) as total_modulos FROM material_capacitacion WHERE rol_destino != 'Mentor' ORDER BY id ASC LIMIT 2", fetchall=True) or []
            for c_item in cols:
                ya_a = db.execute_query("SELECT id FROM asignacion_material WHERE material_id = ? AND organizacion_id = ?", (c_item["id"], datos.organizacion_id), fetchone=True)
                if not ya_a:
                    db.execute_query("INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, fecha_asignacion) VALUES (?, ?, 'Institución', DATETIME('now', 'localtime'))", (c_item["id"], datos.organizacion_id), commit=True)

        estado_calc = "Completado" if pct_val >= 100 else ("En Progreso" if pct_val > 0 else "No Iniciado")
        t_mins = datos.tiempo_dedicado_minutos if datos.tiempo_dedicado_minutos is not None else int(round((pct_val / 100.0) * 120))
        for ap in aprendices:
            aprendices_actualizados += 1
            for c_item in cols:
                t_mod = int(c_item.get("total_modulos") or 3)
                m_comp = int(round((pct_val / 100.0) * t_mod))
                ex_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (ap["id"], c_item["id"]), fetchone=True)
                if ex_p:
                    db.execute_query("""
                        UPDATE progreso_cursos
                        SET porcentaje_avance = ?, modulos_completados = ?, estado = ?, tiempo_dedicado_minutos = ?, fecha_actualizacion = DATETIME('now', 'localtime')
                        WHERE id = ?
                    """, (pct_val, m_comp, estado_calc, t_mins, ex_p["id"]), commit=True)
                else:
                    db.execute_query("""
                        INSERT INTO progreso_cursos (usuario_id, curso_id, porcentaje_avance, modulos_completados, estado, tiempo_dedicado_minutos, fecha_actualizacion)
                        VALUES (?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
                    """, (ap["id"], c_item["id"], pct_val, m_comp, estado_calc, t_mins), commit=True)

    try:
        replicador_azure.marcar("organizaciones")
        replicador_azure.marcar("progreso_cursos")
        replicador_azure.marcar("asignacion_material")
    except Exception:
        pass

    msg = (
        f"Avance de '{org['nombre']}' fijado manualmente en {pct_val}% ({aprendices_actualizados} aprendices sincronizados en Azure SQL)."
        if pct_val is not None
        else f"Modo automático restaurado para '{org['nombre']}'."
    )
    registrar_movimiento("SuperAdmin", "Control_Avance", "Ajuste_Manual_Institucion", "EXITO", msg, organizacion_id=datos.organizacion_id, organizacion_nombre=org["nombre"], usuario_rol="Super Administrador")
    return {"status": "success", "mensaje": msg, "porcentaje_avance": pct_val, "aprendices_actualizados": aprendices_actualizados}


@router.post("/api/superadmin/control-avance/grupo")
def controlar_avance_grupo(datos: ControlAvanceGrupoReq):
    """Permite al Superadministrador ajustar manualmente el avance, módulos y estado de un grupo de trabajo (por mentor o toda la institución)"""
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (datos.organizacion_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="La institución seleccionada no existe.")

    if datos.mentor_id:
        aprendices = db.execute_query(
            "SELECT id, nombre FROM usuarios WHERE organizacion_id = ? AND mentor_id = ? AND rol = 'Aprendiz'",
            (datos.organizacion_id, datos.mentor_id),
            fetchall=True
        ) or []
    else:
        aprendices = db.execute_query(
            "SELECT id, nombre FROM usuarios WHERE organizacion_id = ? AND rol = 'Aprendiz'",
            (datos.organizacion_id,),
            fetchall=True
        ) or []

    if not aprendices:
        raise HTTPException(status_code=400, detail="No hay aprendices registrados en el grupo seleccionado.")

    if datos.curso_id:
        cols = db.execute_query("SELECT id, COALESCE(total_modulos, 3) as total_modulos FROM material_capacitacion WHERE id = ?", (datos.curso_id,), fetchall=True) or []
    else:
        cols = db.execute_query("""
            SELECT DISTINCT m.id, COALESCE(m.total_modulos, 3) as total_modulos
            FROM material_capacitacion m
            JOIN asignacion_material a ON m.id = a.material_id
            WHERE a.organizacion_id = ?
        """, (datos.organizacion_id,), fetchall=True) or []
        if not cols:
            cols = db.execute_query("SELECT id, COALESCE(total_modulos, 3) as total_modulos FROM material_capacitacion WHERE rol_destino != 'Mentor' ORDER BY id ASC LIMIT 2", fetchall=True) or []
            for c_item in cols:
                db.execute_query("INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, fecha_asignacion) VALUES (?, ?, 'Institución', DATETIME('now', 'localtime'))", (c_item["id"], datos.organizacion_id), commit=True)

    pct_val = round(max(0.0, min(100.0, float(datos.porcentaje_avance))), 1)
    estado_final = datos.estado or ("Completado" if pct_val >= 100 else ("En Progreso" if pct_val > 0 else "No Iniciado"))
    t_mins = datos.tiempo_dedicado_minutos if datos.tiempo_dedicado_minutos is not None else 60

    for ap in aprendices:
        for c_item in cols:
            t_mod = int(c_item.get("total_modulos") or 3)
            m_comp = datos.modulos_completados if datos.modulos_completados is not None else int(round((pct_val / 100.0) * t_mod))
            m_comp = max(0, min(t_mod, int(m_comp)))
            ex_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (ap["id"], c_item["id"]), fetchone=True)
            if ex_p:
                db.execute_query("""
                    UPDATE progreso_cursos
                    SET porcentaje_avance = ?, modulos_completados = ?, estado = ?, tiempo_dedicado_minutos = ?, fecha_actualizacion = DATETIME('now', 'localtime')
                    WHERE id = ?
                """, (pct_val, m_comp, estado_final, t_mins, ex_p["id"]), commit=True)
            else:
                db.execute_query("""
                    INSERT INTO progreso_cursos (usuario_id, curso_id, porcentaje_avance, modulos_completados, estado, tiempo_dedicado_minutos, fecha_actualizacion)
                    VALUES (?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
                """, (ap["id"], c_item["id"], pct_val, m_comp, estado_final, t_mins), commit=True)

    try:
        replicador_azure.marcar("progreso_cursos")
    except Exception:
        pass

    msg = f"Grupo actualizado en '{org['nombre']}': {len(aprendices)} aprendices fijados en {pct_val}% ({estado_final}) en Azure SQL."
    registrar_movimiento("SuperAdmin", "Control_Avance", "Ajuste_Manual_Grupo", "EXITO", msg, organizacion_id=datos.organizacion_id, organizacion_nombre=org["nombre"], usuario_rol="Super Administrador")
    return {"status": "success", "mensaje": msg, "aprendices_actualizados": len(aprendices), "porcentaje_avance": pct_val}


@router.post("/api/superadmin/control-avance/integrante")
def controlar_avance_integrante(datos: ControlAvanceIntegranteReq):
    """Permite al Superadministrador modificar manualmente el avance, módulos completados y estado de un aprendiz o mentor específico en Azure SQL"""
    usr = db.execute_query("SELECT id, nombre, correo, rol, organizacion_id FROM usuarios WHERE id = ?", (datos.usuario_id,), fetchone=True)
    if not usr:
        raise HTTPException(status_code=404, detail="El integrante seleccionado no existe.")

    org_nom = "Plataforma Global"
    if usr.get("organizacion_id"):
        o_r = db.execute_query("SELECT nombre FROM organizaciones WHERE id = ?", (usr["organizacion_id"],), fetchone=True)
        if o_r:
            org_nom = o_r["nombre"]

    if datos.curso_id:
        cols = db.execute_query("SELECT id, COALESCE(total_modulos, 3) as total_modulos FROM material_capacitacion WHERE id = ?", (datos.curso_id,), fetchall=True) or []
    else:
        if usr.get("rol") == "Mentor":
            cols = db.execute_query("SELECT id, COALESCE(total_modulos, 3) as total_modulos FROM material_capacitacion WHERE rol_destino = 'Mentor'", fetchall=True) or []
        else:
            cols = db.execute_query("""
                SELECT DISTINCT m.id, COALESCE(m.total_modulos, 3) as total_modulos
                FROM material_capacitacion m
                JOIN asignacion_material a ON m.id = a.material_id
                WHERE a.organizacion_id = ?
            """, (usr.get("organizacion_id"),), fetchall=True) or []
            if not cols:
                cols = db.execute_query("SELECT id, COALESCE(total_modulos, 3) as total_modulos FROM material_capacitacion WHERE rol_destino != 'Mentor' ORDER BY id ASC LIMIT 2", fetchall=True) or []
                if usr.get("organizacion_id"):
                    for c_item in cols:
                        db.execute_query("INSERT INTO asignacion_material (material_id, organizacion_id, destinatario_tipo, fecha_asignacion) VALUES (?, ?, 'Institución', DATETIME('now', 'localtime'))", (c_item["id"], usr["organizacion_id"]), commit=True)

    pct_val = round(max(0.0, min(100.0, float(datos.porcentaje_avance))), 1)
    estado_final = datos.estado or ("Completado" if pct_val >= 100 else ("En Progreso" if pct_val > 0 else "No Iniciado"))
    t_mins = datos.tiempo_dedicado_minutos if datos.tiempo_dedicado_minutos is not None else 45

    for c_item in cols:
        t_mod = int(c_item.get("total_modulos") or 3)
        m_comp = datos.modulos_completados if datos.modulos_completados is not None else int(round((pct_val / 100.0) * t_mod))
        m_comp = max(0, min(t_mod, int(m_comp)))
        ex_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (usr["id"], c_item["id"]), fetchone=True)
        if ex_p:
            db.execute_query("""
                UPDATE progreso_cursos
                SET porcentaje_avance = ?, modulos_completados = ?, estado = ?, tiempo_dedicado_minutos = ?, fecha_actualizacion = DATETIME('now', 'localtime')
                WHERE id = ?
            """, (pct_val, m_comp, estado_final, t_mins, ex_p["id"]), commit=True)
        else:
            db.execute_query("""
                INSERT INTO progreso_cursos (usuario_id, curso_id, porcentaje_avance, modulos_completados, estado, tiempo_dedicado_minutos, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
            """, (usr["id"], c_item["id"], pct_val, m_comp, estado_final, t_mins), commit=True)

    try:
        replicador_azure.marcar("progreso_cursos")
    except Exception:
        pass

    msg = f"Avance de '{usr['nombre']}' ({usr['rol']}) actualizado manualmente a {pct_val}% ({estado_final}) en Azure SQL."
    registrar_movimiento("SuperAdmin", "Control_Avance", "Ajuste_Manual_Integrante", "EXITO", msg, organizacion_id=usr.get("organizacion_id"), organizacion_nombre=org_nom, usuario_rol="Super Administrador")
    return {"status": "success", "mensaje": msg, "usuario_id": usr["id"], "porcentaje_avance": pct_val, "estado": estado_final}


@router.get("/api/powerbi/exportar-metricas-colecciones.csv")
def exportar_csv_powerbi(organizacion_id: Optional[int] = None):
    """Genera y descarga un archivo CSV con UTF-8 BOM listo para importar directamente en Microsoft Power BI"""
    output = io.StringIO()
    # Escribir UTF-8 BOM
    output.write('\ufeff')
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Cabecera enriquecida para modelo dimensional Power BI
    writer.writerow([
        "ID_Organizacion",
        "Organizacion",
        "Tipo_Institucion",
        "ID_Coleccion",
        "Coleccion_Titulo",
        "Tipo_Material",
        "Total_Modulos",
        "ID_Estudiante",
        "Estudiante_Nombre",
        "Estudiante_Correo",
        "ID_Mentor",
        "Mentor_Nombre",
        "Modulos_Completados",
        "Modulos_Pendientes",
        "Porcentaje_Avance",
        "Estado_Progreso",
        "Tiempo_Minutos",
        "Tiempo_Horas",
        "Fecha_Actualizacion",
        "URL_Microsoft_Learn"
    ])

    query = """
        SELECT o.id as org_id, o.nombre as org_nombre, o.tipo_organizacion,
               m.id as col_id, m.titulo as col_titulo, m.tipo_material, COALESCE(m.total_modulos, 3) as total_modulos, m.enlace_url,
               u.id as usr_id, u.nombre as usr_nombre, u.correo as usr_correo,
               u.mentor_id, COALESCE(men.nombre, 'Sin Mentor') as mentor_nombre,
               COALESCE(p.modulos_completados, 0) as modulos_comp,
               COALESCE(p.porcentaje_avance, 0.0) as pct_avance,
               COALESCE(p.tiempo_dedicado_minutos, 0) as tiempo_min,
               COALESCE(p.estado, 'No Iniciado') as estado,
               COALESCE(p.fecha_actualizacion, CURRENT_TIMESTAMP) as fecha_act
        FROM organizaciones o
        JOIN usuarios u ON u.organizacion_id = o.id AND u.rol = 'Aprendiz'
        LEFT JOIN usuarios men ON u.mentor_id = men.id
        JOIN asignacion_material a ON a.organizacion_id = o.id
        JOIN material_capacitacion m ON m.id = a.material_id
        LEFT JOIN progreso_cursos p ON p.usuario_id = u.id AND p.curso_id = m.id
        WHERE 1=1
    """
    params = []
    if organizacion_id:
        query += " AND o.id = ?"
        params.append(organizacion_id)

    query += " ORDER BY o.nombre, m.titulo, u.nombre"
    filas = db.execute_query(query, tuple(params), fetchall=True) or []

    for f in filas:
        t_mod = f["total_modulos"]
        m_comp = f["modulos_comp"]
        m_pend = max(0, t_mod - m_comp)
        pct = round((m_comp / max(1, t_mod)) * 100, 1) if t_mod > 0 else f["pct_avance"]
        t_min = f["tiempo_min"]
        t_hrs = round(t_min / 60.0, 2)
        estado = "Completado" if m_comp >= t_mod and t_mod > 0 else ("En Progreso" if m_comp > 0 else "No Iniciado")

        writer.writerow([
            f["org_id"],
            f["org_nombre"],
            f["tipo_organizacion"],
            f["col_id"],
            f["col_titulo"],
            f["tipo_material"],
            t_mod,
            f["usr_id"],
            f["usr_nombre"],
            f["usr_correo"],
            f["mentor_id"] or "",
            f["mentor_nombre"],
            m_comp,
            m_pend,
            pct,
            estado,
            t_min,
            t_hrs,
            f["fecha_act"],
            f["enlace_url"]
        ])

    csv_content = output.getvalue()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_archivo = f"reporte_powerbi_edtech_colecciones_{timestamp_str}.csv"

    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={nombre_archivo}",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/api/powerbi/metricas-organizaciones-json")
def obtener_dataset_powerbi_json(organizacion_id: Optional[int] = None):
    """Endpoint REST JSON para integración en tiempo real con Power BI Service / Desktop Web Connector"""
    query = """
        SELECT o.id as org_id, o.nombre as org_nombre, o.tipo_organizacion,
               m.id as col_id, m.titulo as col_titulo, m.tipo_material, COALESCE(m.total_modulos, 3) as total_modulos, m.enlace_url,
               u.id as usr_id, u.nombre as usr_nombre, u.correo as usr_correo,
               u.mentor_id, COALESCE(men.nombre, 'Sin Mentor') as mentor_nombre,
               COALESCE(p.modulos_completados, 0) as modulos_comp,
               COALESCE(p.porcentaje_avance, 0.0) as pct_avance,
               COALESCE(p.tiempo_dedicado_minutos, 0) as tiempo_min,
               COALESCE(p.estado, 'No Iniciado') as estado,
               COALESCE(p.fecha_actualizacion, CURRENT_TIMESTAMP) as fecha_act
        FROM organizaciones o
        JOIN usuarios u ON u.organizacion_id = o.id AND u.rol = 'Aprendiz'
        LEFT JOIN usuarios men ON u.mentor_id = men.id
        JOIN asignacion_material a ON a.organizacion_id = o.id
        JOIN material_capacitacion m ON m.id = a.material_id
        LEFT JOIN progreso_cursos p ON p.usuario_id = u.id AND p.curso_id = m.id
        WHERE 1=1
    """
    params = []
    if organizacion_id:
        query += " AND o.id = ?"
        params.append(organizacion_id)

    query += " ORDER BY o.nombre, m.titulo, u.nombre"
    filas = db.execute_query(query, tuple(params), fetchall=True) or []

    datos = []
    for f in filas:
        t_mod = f["total_modulos"]
        m_comp = f["modulos_comp"]
        pct = round((m_comp / max(1, t_mod)) * 100, 1) if t_mod > 0 else f["pct_avance"]
        datos.append({
            "ID_Organizacion": f["org_id"],
            "Organizacion": f["org_nombre"],
            "Tipo_Institucion": f["tipo_organizacion"],
            "ID_Coleccion": f["col_id"],
            "Coleccion_Titulo": f["col_titulo"],
            "Tipo_Material": f["tipo_material"],
            "Total_Modulos": t_mod,
            "ID_Estudiante": f["usr_id"],
            "Estudiante_Nombre": f["usr_nombre"],
            "Estudiante_Correo": f["usr_correo"],
            "ID_Mentor": f["mentor_id"],
            "Mentor_Nombre": f["mentor_nombre"],
            "Modulos_Completados": m_comp,
            "Modulos_Pendientes": max(0, t_mod - m_comp),
            "Porcentaje_Avance": pct,
            "Estado_Progreso": "Completado" if m_comp >= t_mod and t_mod > 0 else ("En Progreso" if m_comp > 0 else "No Iniciado"),
            "Tiempo_Minutos": f["tiempo_min"],
            "Tiempo_Horas": round(f["tiempo_min"] / 60.0, 2),
            "Fecha_Actualizacion": f["fecha_act"],
            "URL_Microsoft_Learn": f["enlace_url"]
        })

    return {
        "status": "success",
        "total_registros": len(datos),
        "dataset": datos
    }

