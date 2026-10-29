"""M?dulo de rutas REST: Usuarios, Perfil, Mentores y Grupos."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, Response, JSONResponse
from app.core import *
from app.core import _empujar_cambio_usuario_remoto, _disparar_sync_usuarios_nube

router = APIRouter(tags=["Usuarios, Perfil, Mentores y Grupos"])


@router.post("/api/usuarios/registrar")
def registrar_usuario(datos: RegistroUsuarioRequest, background_tasks: BackgroundTasks):
    """Registra a cualquier usuario nuevo (Aprendiz, Mentor, Administrador, etc.), lo incorpora en la base de datos y despacha el correo de bienvenida/2FA"""
    correo_limpio = datos.correo.strip().lower()
    if not correo_limpio or "@" not in correo_limpio:
        raise HTTPException(status_code=400, detail="El correo electrónico es requerido y debe ser válido.")
        
    pwd_raw = (datos.password or "123456").strip()
    if len(pwd_raw) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")
        
    pwd_hash = bcrypt.hashpw(pwd_raw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    rol_elegido = (datos.rol or "Aprendiz").strip()
    nom_elegido = (datos.nombre or "").strip() or correo_limpio.split('@')[0].replace('.', ' ').title()
    org_id_elegido = getattr(datos, 'organizacion_id', None)
    
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id_elegido,), fetchone=True) if org_id_elegido else None
    if not org:
        org = db.execute_query("SELECT id, nombre FROM organizaciones ORDER BY id ASC LIMIT 1", fetchone=True)
    org_nombre = org["nombre"] if org else "Plataforma Global EdTech"
    org_id_real = org["id"] if org else None

    existe = db.execute_query("SELECT id FROM usuarios WHERE correo = ?", (correo_limpio,), fetchone=True)
    if existe:
        db.execute_query(
            "UPDATE usuarios SET nombre = ?, password_hash = ?, rol = ?, organizacion_id = ? WHERE correo = ?",
            (nom_elegido, pwd_hash, rol_elegido, org_id_real, correo_limpio),
            commit=True
        )
        u_id = existe["id"]
    else:
        db.execute_query(
            "INSERT INTO usuarios (nombre, correo, password_hash, rol, organizacion_id) VALUES (?, ?, ?, ?, ?)",
            (nom_elegido, correo_limpio, pwd_hash, rol_elegido, org_id_real),
            commit=True
        )
        u_creado = db.execute_query("SELECT id FROM usuarios WHERE correo = ?", (correo_limpio,), fetchone=True)
        u_id = u_creado["id"] if u_creado else None

    registrar_en_historial_integrantes(
        nombre=nom_elegido,
        correo=correo_limpio,
        rol=rol_elegido,
        organizacion_id=org_id_real,
        origen="Registro Web",
        usuario_id=u_id
    )

    if u_id:
        _empujar_cambio_usuario_remoto(u_id)

    # Despachar correo de bienvenida ejecutivo
    asunto_b = f"✨ Bienvenido(a) a Consultoría EdTech · {org_nombre}"
    cuerpo_txt = (
        f"¡Hola, {nom_elegido}! 👋 Te damos la más cordial bienvenida a Consultoría EdTech.\n\n"
        f"Información de tu cuenta:\n"
        f"• Nombre: {nom_elegido}\n"
        f"• Cargo / Rol: {rol_elegido}\n"
        f"• Institución: {org_nombre} (ID: {org_id_real})\n"
        f"• Correo registrado: {correo_limpio}\n"
        f"• Contraseña inicial: {pwd_raw}\n\n"
        f"Tu acceso a la plataforma está activo para ingresar directamente con tus credenciales."
    )
    cuerpo_h = generar_html_correo_bienvenida(
        nombre=nom_elegido,
        rol=rol_elegido,
        correo=correo_limpio,
        institucion_nombre=org_nombre,
        password_inicial=pwd_raw
    )
    threading.Thread(
        target=enviar_correo_smtp,
        args=(correo_limpio, asunto_b, cuerpo_txt, cuerpo_h),
        daemon=True
    ).start()

    registrar_movimiento(correo_limpio, "Registro", "Registro_Usuario", "EXITO", f"Rol: {rol_elegido} · Org: {org_nombre}")

    return {
        "status": "success",
        "mensaje": f"¡Cuenta creada con éxito para {nom_elegido} ({rol_elegido}) en {org_nombre}! Acceso directo habilitado.",
        "usuario": {
            "id": u_id,
            "nombre": nom_elegido,
            "correo": correo_limpio,
            "rol": rol_elegido,
            "organizacion_id": org_id_real,
            "institucion": org_nombre
        }
    }


@router.post("/api/superadmin/usuarios/crear-manual")
def crear_integrante_manual(datos: CrearIntegranteManualReq, background_tasks: BackgroundTasks):
    """Permite al Super Administrador incorporar manualmente un Estudiante, Mentor o Administrador a una institución con contraseña por defecto 123456"""
    correo_limpio = datos.correo.strip().lower()
    if not correo_limpio:
        raise HTTPException(status_code=400, detail="El correo electrónico es requerido.")
        
    existe = db.execute_query("SELECT id, nombre FROM usuarios WHERE correo = ?", (correo_limpio,), fetchone=True)
    if existe:
        raise HTTPException(status_code=400, detail=f"El correo '{correo_limpio}' ya pertenece al usuario '{existe['nombre']}' en el sistema.")
        
    org = db.execute_query("SELECT id, nombre, max_administradores, max_mentores, licencias_asignadas FROM organizaciones WHERE id = ?", (datos.organizacion_id,), fetchone=True)
    if not org:
        org = db.execute_query("SELECT id, nombre, max_administradores, max_mentores, licencias_asignadas FROM organizaciones ORDER BY id ASC LIMIT 1", fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="La institución u organización seleccionada no fue encontrada.")
    org_id_real = org["id"]
        
    rol_normalizado = (datos.rol or "Aprendiz").strip()
    if not rol_normalizado:
        rol_normalizado = "Aprendiz"
        
    pwd_raw = (datos.password or "123456").strip()
    if len(pwd_raw) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 dígitos o caracteres.")
        
    pwd_hash = bcrypt.hashpw(pwd_raw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Validar mentor si se especificó para un aprendiz
    mentor_id_val = None
    if rol_normalizado == "Aprendiz":
        if datos.mentor_id:
            mentor = db.execute_query("SELECT id, nombre FROM usuarios WHERE id = ? AND rol = 'Mentor'", (datos.mentor_id,), fetchone=True)
            if mentor:
                mentor_id_val = mentor["id"]
        if not mentor_id_val:
            mentor_def = db.execute_query("SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor' ORDER BY id ASC LIMIT 1", (org_id_real,), fetchone=True)
            if mentor_def:
                mentor_id_val = mentor_def["id"]
            
    db.execute_query(
        "INSERT INTO usuarios (nombre, correo, password_hash, rol, organizacion_id, mentor_id) VALUES (?, ?, ?, ?, ?, ?)",
        (datos.nombre.strip(), correo_limpio, pwd_hash, rol_normalizado, org_id_real, mentor_id_val),
        commit=True
    )
    
    u_creado = db.execute_query("SELECT id FROM usuarios WHERE correo = ?", (correo_limpio,), fetchone=True)
    u_id_val = u_creado["id"] if u_creado else None
    
    # Registrar en historial cronológico de nuevos integrantes (visible en El Celador y por días)
    registrar_en_historial_integrantes(
        nombre=datos.nombre.strip(),
        correo=correo_limpio,
        rol=rol_normalizado,
        organizacion_id=org_id_real,
        origen="Registro Manual",
        usuario_id=u_id_val
    )
    
    # Si es aprendiz, auto-matricular en colecciones asignadas previamente a la organización
    if rol_normalizado == "Aprendiz" and u_id_val:
        colecciones_org = db.execute_query(
            "SELECT material_id FROM asignacion_material WHERE organizacion_id = ?",
            (org_id_real,),
            fetchall=True
        ) or []
        for c in colecciones_org:
            mat_id = c["material_id"]
            ya_p = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (u_id_val, mat_id), fetchone=True)
            if not ya_p:
                db.execute_query(
                    "INSERT INTO progreso_cursos (usuario_id, curso_id, modulos_completados, porcentaje_avance, tiempo_dedicado_minutos, estado, fecha_actualizacion) VALUES (?, ?, 0, 0.0, 0, 'No Iniciado', DATETIME('now', 'localtime'))",
                    (u_id_val, mat_id),
                    commit=True
                )
                
    registrar_movimiento(
        "SuperAdmin", "Usuarios", "Crear_Integrante_Manual", "EXITO",
        f"Usuario '{datos.nombre.strip()}' ({rol_normalizado}) creado en '{org['nombre']}'. Clave inicial: {pwd_raw}"
    )
    
    # Sincronizar de inmediato entre Local, Azure SQL y Render Cloud
    if u_id_val:
        _empujar_cambio_usuario_remoto(u_id_val)
    else:
        _disparar_sync_usuarios_nube()
    try:
        replicador_azure.marcar("usuarios")
        replicador_azure.marcar("historial_nuevos_integrantes")
    except Exception:
        pass
    asunto = f"🎉 Bienvenido a Consultoría EdTech · {org['nombre']} ({rol_normalizado})"
    cuerpo_txt = (
        f"Bienvenido a Consultoría EdTech\n\n"
        f"Hola {datos.nombre.strip()},\n"
        f"Institución: {org['nombre']}\n"
        f"Nombre: {datos.nombre.strip()}\n"
        f"Cargo / Rol: {rol_normalizado}\n"
        f"Correo registrado: {correo_limpio}\n"
        f"Contraseña inicial: {pwd_raw}\n\n"
        f"Tu cuenta se encuentra lista para iniciar sesión directamente con tus credenciales."
    )
    cuerpo_html = generar_html_correo_bienvenida(
        nombre=datos.nombre.strip(),
        rol=rol_normalizado,
        correo=correo_limpio,
        institucion_nombre=org["nombre"],
        password_inicial=pwd_raw
    )
    threading.Thread(
        target=enviar_correo_smtp,
        args=(correo_limpio, asunto, cuerpo_txt, cuerpo_html),
        daemon=True
    ).start()
    
    return {
        "status": "success",
        "mensaje": f"✓ Integrante '{datos.nombre}' ({rol_normalizado}) incorporado exitosamente a '{org['nombre']}'. Correo de bienvenida enviado a {correo_limpio}.",
        "usuario": {
            "id": u_id_val,
            "nombre": datos.nombre.strip(),
            "correo": correo_limpio,
            "rol": rol_normalizado,
            "organizacion_id": org_id_real,
            "mentor_id": mentor_id_val
        }
    }


@router.post("/api/usuarios/{usuario_id}/cambiar-cargo")
def cambiar_cargo_usuario_tiempo_real(usuario_id: int, datos: CambiarCargoTiempoRealReq):
    """Permite cambiar en tiempo real el cargo (Administrador, Mentor, Aprendiz) de un usuario y sincroniza con Azure SQL y Render Cloud"""
    u = db.execute_query("SELECT id, nombre, correo, rol, organizacion_id, mentor_id FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="El usuario no existe.")

    if u.get("rol") == "Super Administrador":
        raise HTTPException(status_code=400, detail="La cuenta principal de Super Administrador está blindada y no puede cambiar de cargo.")

    nuevo_rol = (datos.rol or "").strip()
    if not nuevo_rol:
        raise HTTPException(status_code=400, detail="El cargo o rol no puede estar vacío.")

    org_id = u.get("organizacion_id") or 13
    mentor_id_final = None
    if nuevo_rol == "Aprendiz":
        mentor_id_final = datos.mentor_id or u.get("mentor_id")
        if not mentor_id_final:
            m_row = db.execute_query(
                "SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor' AND id != ? ORDER BY id ASC LIMIT 1",
                (org_id, usuario_id), fetchone=True
            )
            if m_row:
                mentor_id_final = m_row["id"]

    db.execute_query(
        "UPDATE usuarios SET rol = ?, organizacion_id = ?, mentor_id = ? WHERE id = ?",
        (nuevo_rol, org_id, mentor_id_final, usuario_id),
        commit=True
    )

    # Si pasó a Mentor o Administrador y tenía aprendices a cargo (cuando era Mentor y pasa a otro cargo), reasignar si deja de ser Mentor
    if u.get("rol") == "Mentor" and nuevo_rol != "Mentor":
        otro_mentor = db.execute_query(
            "SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor' AND id != ? ORDER BY id ASC LIMIT 1",
            (org_id, usuario_id), fetchone=True
        )
        nuevo_m_id = otro_mentor["id"] if otro_mentor else None
        db.execute_query("UPDATE usuarios SET mentor_id = ? WHERE mentor_id = ?", (nuevo_m_id, usuario_id), commit=True)

    try:
        db.execute_query(
            "UPDATE historial_nuevos_integrantes SET rol = ?, organizacion_id = ? WHERE usuario_id = ?",
            (nuevo_rol, org_id, usuario_id),
            commit=True
        )
    except Exception:
        pass

    _empujar_cambio_usuario_remoto(usuario_id)
    registrar_movimiento("Administrador", "Usuarios", "Cambio_Cargo_Tiempo_Real", "EXITO", f"Usuario #{usuario_id} ({u['correo']}): {u['rol']} -> {nuevo_rol}")

    return {
        "status": "success",
        "mensaje": f"Cargo de '{u['nombre']}' actualizado en tiempo real a '{nuevo_rol}' (Sincronizado en Azure SQL y Nube).",
        "usuario": {
            "id": usuario_id,
            "nombre": u["nombre"],
            "correo": u["correo"],
            "rol": nuevo_rol,
            "organizacion_id": org_id,
            "mentor_id": mentor_id_final
        }
    }


@router.put("/api/usuarios/{usuario_id}")
@router.put("/api/superadmin/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: int, datos: ActualizarUsuarioRequest):
    """Permite modificar o corregir cargos duplicados, nombres, roles o mentores asignados"""
    u = db.execute_query("SELECT id, nombre, correo, rol, organizacion_id, mentor_id FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="El usuario no existe.")
        
    # Protección de la cuenta y jerarquía de Super Administrador
    if u.get("rol") == "Super Administrador" and datos.rol != "Super Administrador":
        raise HTTPException(status_code=400, detail="La cuenta principal de Super Administrador está blindada y no puede ser modificada desde la jerarquía institucional.")

    if not datos.rol or not datos.rol.strip():
        raise HTTPException(status_code=400, detail="El cargo o rol es requerido.")

    correo_nuevo = datos.correo.strip().lower()
    # Verificar si el nuevo correo colisiona con otro usuario distinto
    colision = db.execute_query("SELECT id FROM usuarios WHERE correo = ? AND id != ?", (correo_nuevo, usuario_id), fetchone=True)
    if colision:
        raise HTTPException(status_code=400, detail="El correo ya pertenece a otro usuario registrado.")

    org_id_final = datos.organizacion_id or u.get("organizacion_id") or 13
    mentor_id_final = datos.mentor_id if datos.rol == "Aprendiz" else None
    if datos.rol == "Aprendiz" and not mentor_id_final:
        m_row = db.execute_query(
            "SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor' AND id != ? ORDER BY id ASC LIMIT 1",
            (org_id_final, usuario_id), fetchone=True
        )
        if m_row:
            mentor_id_final = m_row["id"]

    db.execute_query("""
        UPDATE usuarios
        SET nombre = ?, correo = ?, rol = ?, organizacion_id = ?, mentor_id = ?
        WHERE id = ?
    """, (datos.nombre.strip(), correo_nuevo, datos.rol, org_id_final, mentor_id_final, usuario_id), commit=True)

    # Sincronizar en historial de integrantes en tiempo real
    try:
        db.execute_query("""
            UPDATE historial_nuevos_integrantes
            SET nombre = ?, correo = ?, rol = ?, organizacion_id = ?
            WHERE usuario_id = ?
        """, (datos.nombre.strip(), correo_nuevo, datos.rol, org_id_final, usuario_id), commit=True)
    except Exception:
        pass

    # Invalidar caches de 2FA si existían para evitar estados huérfanos
    if u.get("correo"):
        codigos_2fa_activos.pop(u["correo"].lower().strip(), None)
    codigos_2fa_activos.pop(correo_nuevo, None)

    _empujar_cambio_usuario_remoto(usuario_id)
    registrar_movimiento("Administrador", "Usuarios", "Modificar_Usuario", "EXITO", f"Usuario #{usuario_id}: {datos.nombre} (Nuevo Rol: {datos.rol})")
    return {
        "status": "success",
        "mensaje": f"Usuario '{datos.nombre}' actualizado exitosamente con cargo '{datos.rol}' (Sincronizado en Azure SQL).",
        "usuario": {
            "id": usuario_id,
            "nombre": datos.nombre.strip(),
            "correo": correo_nuevo,
            "rol": datos.rol,
            "organizacion_id": org_id_final,
            "mentor_id": mentor_id_final
        }
    }


@router.delete("/api/usuarios/{usuario_id}")
@router.delete("/api/superadmin/usuarios/{usuario_id}")
def eliminar_usuario(usuario_id: int, request: Request):
    """Elimina usuarios con respaldo automático a la Papelera de Integrantes y Snapshot inmutable en la Bóveda Legal"""
    u = db.execute_query("SELECT id, organizacion_id, mentor_id, nombre, correo, rol, password_hash, foto_perfil FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="El usuario no existe.")

    if u.get("rol") == "Super Administrador":
        raise HTTPException(status_code=400, detail="La cuenta principal de Super Administrador está blindada y no puede ser eliminada.")

    org_nom = "Sin Organización"
    if u.get("organizacion_id"):
        org_row = db.execute_query("SELECT nombre FROM organizaciones WHERE id = ?", (u["organizacion_id"],), fetchone=True)
        if org_row:
            org_nom = org_row.get("nombre", "Sin Organización")

    # Obtener respaldo del progreso del estudiante si aplica
    progresos = db.execute_query("SELECT curso_id, porcentaje_avance, tiempo_dedicado_minutos, modulos_completados, estado FROM progreso_cursos WHERE usuario_id = ?", (usuario_id,), fetchall=True) or []
    progresos_json = json.dumps(progresos, ensure_ascii=False)

    ip_cliente = obtener_ip_cliente(request) if request else "127.0.0.1"
    crear_snapshot_boveda_legal(
        operacion_origen="ELIMINACION_INTEGRANTE",
        entidad_afectada="usuarios",
        entidad_id=usuario_id,
        entidad_nombre=f"{u['nombre']} ({u['correo']} - {org_nom})",
        correo_responsable="alexander.nino.583@gmail.com",
        direccion_ip=ip_cliente,
        datos_respaldo={
            "integrante": {k: v for k, v in dict(u).items() if k != "password_hash"},
            "organizacion_nombre": org_nom,
            "progreso_cursos": [dict(p) for p in progresos]
        }
    )

    # Insertar en Papelera de Reciclaje
    try:
        db.execute_query("""
            INSERT INTO usuarios_eliminados_papelera (
                usuario_id, organizacion_id, organizacion_nombre, mentor_id,
                nombre, correo, rol, password_hash, foto_perfil, datos_progreso_json,
                fecha_eliminacion, eliminado_por
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'), 'Administrador')
        """, (
            u["id"], u.get("organizacion_id"), org_nom, u.get("mentor_id"),
            u["nombre"], u["correo"], u["rol"], u.get("password_hash"), u.get("foto_perfil"),
            progresos_json
        ), commit=True)
    except Exception as e_papelera:
        print(f">> [!] Error al guardar en papelera: {e_papelera}")

    db.execute_query("DELETE FROM progreso_cursos WHERE usuario_id = ?", (usuario_id,), commit=True)
    db.execute_query("DELETE FROM progreso_quizzes WHERE aprendiz_id = ?", (usuario_id,), commit=True)
    db.execute_query("DELETE FROM registro_actividades_tiempo WHERE usuario_id = ?", (usuario_id,), commit=True)
    db.execute_query("UPDATE usuarios SET mentor_id = NULL WHERE mentor_id = ?", (usuario_id,), commit=True)
    db.execute_query("DELETE FROM usuarios WHERE id = ?", (usuario_id,), commit=True)

    try:
        replicador_azure.sincronizar_inmediato([
            "progreso_cursos",
            "progreso_quizzes",
            "registro_actividades_tiempo",
            "usuarios",
            "usuarios_eliminados_papelera",
            "boveda_legal_snapshots"
        ])
    except Exception:
        pass

    registrar_movimiento("Administrador", "Usuarios", "Eliminar_Usuario_Con_Respaldo", "EXITO", f"Usuario respaldado en papelera y Bóveda Legal: {u['nombre']} ({u['correo']}) - Org: {org_nom}", organizacion_id=u.get("organizacion_id"), organizacion_nombre=org_nom)
    return {"status": "success", "mensaje": f"Integrante '{u['nombre']}' eliminado de Azure SQL y respaldado en Papelera y Bóveda Legal."}


@router.get("/api/papelera/usuarios")
def listar_papelera_usuarios(organizacion_id: Optional[int] = None):
    """Lista integrantes eliminados con posibilidad de recuperación instantánea"""
    query = "SELECT * FROM usuarios_eliminados_papelera WHERE 1=1"
    params = []
    if organizacion_id:
        query += " AND organizacion_id = ?"
        params.append(organizacion_id)
    query += " ORDER BY id DESC"
    items = db.execute_query(query, tuple(params), fetchall=True) or []
    return {"status": "success", "total": len(items), "data": items}


@router.post("/api/papelera/usuarios/restaurar/{papelera_id}")
def restaurar_usuario_papelera(papelera_id: int):
    """Restaura un usuario eliminado con su historial de cursos y roles previos"""
    p = db.execute_query("SELECT * FROM usuarios_eliminados_papelera WHERE id = ?", (papelera_id,), fetchone=True)
    if not p:
        raise HTTPException(status_code=404, detail="El registro en la papelera no existe.")

    # Verificar si el correo ya está registrado actualmente
    colision = db.execute_query("SELECT id FROM usuarios WHERE correo = ?", (p["correo"],), fetchone=True)
    if colision:
        raise HTTPException(status_code=400, detail=f"Ya existe un usuario activo con el correo '{p['correo']}'.")

    # Restaurar en tabla usuarios
    nuevo_id = db.execute_query("""
        INSERT INTO usuarios (organizacion_id, mentor_id, nombre, correo, rol, password_hash, foto_perfil)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (p.get("organizacion_id"), p.get("mentor_id"), p["nombre"], p["correo"], p["rol"], p.get("password_hash"), p.get("foto_perfil")), commit=True, return_id=True)

    if not nuevo_id:
        row = db.execute_query("SELECT id FROM usuarios WHERE correo = ?", (p["correo"],), fetchone=True)
        nuevo_id = row["id"] if row else None

    # Restaurar historial de cursos y módulos
    if nuevo_id and p.get("datos_progreso_json"):
        try:
            progs = json.loads(p["datos_progreso_json"])
            for pr in progs:
                db.execute_query("""
                    INSERT INTO progreso_cursos (usuario_id, curso_id, porcentaje_avance, tiempo_dedicado_minutos, modulos_completados, estado)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nuevo_id, pr.get("curso_id"), pr.get("porcentaje_avance", 0), pr.get("tiempo_dedicado_minutos", 0), pr.get("modulos_completados", 0), pr.get("estado", "En Progreso")), commit=True)
        except Exception as e_progs:
            print(f">> [!] Error restaurando progresos: {e_progs}")

    # Eliminar de la papelera
    db.execute_query("DELETE FROM usuarios_eliminados_papelera WHERE id = ?", (papelera_id,), commit=True)
    registrar_movimiento("Administrador", "Papelera", "Restaurar_Usuario", "EXITO", f"Usuario restaurado: {p['nombre']} ({p['correo']})")
    return {"status": "success", "mensaje": f"Integrante '{p['nombre']}' restaurado exitosamente con todo su progreso."}


@router.delete("/api/papelera/usuarios/purgar/{papelera_id}")
def purgar_usuario_papelera(papelera_id: int):
    """Elimina definitivamente un registro de la papelera"""
    p = db.execute_query("SELECT id, nombre, correo FROM usuarios_eliminados_papelera WHERE id = ?", (papelera_id,), fetchone=True)
    if not p:
        raise HTTPException(status_code=404, detail="El registro no existe.")
    db.execute_query("DELETE FROM usuarios_eliminados_papelera WHERE id = ?", (papelera_id,), commit=True)
    registrar_movimiento("Administrador", "Papelera", "Purgar_Usuario_Definitivo", "EXITO", f"Eliminación definitiva: {p['nombre']}")
    return {"status": "success", "mensaje": f"Integrante '{p['nombre']}' eliminado permanentemente de la papelera."}


@router.delete("/api/papelera/usuarios/vaciar")
def vaciar_papelera(organizacion_id: Optional[int] = None):
    if organizacion_id:
        db.execute_query("DELETE FROM usuarios_eliminados_papelera WHERE organizacion_id = ?", (organizacion_id,), commit=True)
    else:
        db.execute_query("DELETE FROM usuarios_eliminados_papelera", commit=True)
    return {"status": "success", "mensaje": "Papelera vaciada correctamente."}


@router.get("/api/usuarios/perfil")
def obtener_perfil_usuario(usuario_id: int = Query(...)):
    """Obtiene los datos completos del perfil del usuario autenticado en español estandarizado"""
    u = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.mentor_id, u.foto_perfil,
               u.tema_decorativo, u.fondo_personalizado, u.racha_semanas, u.minutos_dedicados_totales,
               u.colores_personalizados, u.disenos_personalizados_json,
               o.nombre as organizacion_nombre
        FROM usuarios u
        LEFT JOIN organizaciones o ON o.id = u.organizacion_id
        WHERE u.id = ?
    """, (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    u_dict = dict(u)
    if u_dict.get("rol") == "Super Administrador":
        u_dict["organizacion_id"] = None
        u_dict["organizacion_nombre"] = None
    return {"status": "success", "usuario": u_dict}


@router.put("/api/usuarios/perfil")
def actualizar_perfil_usuario(usuario_id: int = Query(...), datos: Optional[ActualizarUsuarioRequest] = None):
    """Actualiza la información básica del perfil del usuario autenticado"""
    u = db.execute_query("SELECT id, nombre, correo, rol, organizacion_id, mentor_id FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if datos:
        db.execute_query(
            "UPDATE usuarios SET nombre = ?, correo = ? WHERE id = ?",
            (datos.nombre.strip(), datos.correo.strip().lower(), usuario_id),
            commit=True
        )
        _empujar_cambio_usuario_remoto(usuario_id)
    return {"status": "success", "mensaje": "Perfil de usuario actualizado correctamente."}


@router.post("/api/usuarios/perfil/foto")
def actualizar_foto_perfil(datos: PerfilFotoReq):
    u = db.execute_query("SELECT id, nombre, correo FROM usuarios WHERE id = ?", (datos.usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    db.execute_query("UPDATE usuarios SET foto_perfil = ? WHERE id = ?", (datos.foto_perfil, datos.usuario_id), commit=True)
    registrar_movimiento(u["correo"], "Perfil", "Actualizar_Foto", "EXITO", "Foto de perfil actualizada")
    return {"status": "success", "mensaje": "Foto de perfil guardada exitosamente."}


@router.delete("/api/usuarios/perfil/foto/{usuario_id}")
def eliminar_foto_perfil(usuario_id: int):
    u = db.execute_query("SELECT id, nombre, correo FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    db.execute_query("UPDATE usuarios SET foto_perfil = NULL WHERE id = ?", (usuario_id,), commit=True)
    registrar_movimiento(u["correo"], "Perfil", "Eliminar_Foto", "EXITO", "Foto de perfil eliminada")
    return {"status": "success", "mensaje": "Foto de perfil eliminada. Se mostrarán las iniciales."}


@router.post("/api/usuarios/perfil/contrasena")
@router.post("/api/usuarios/perfil/password")
def cambiar_password_perfil(datos: PerfilPasswordReq):
    u = db.execute_query("SELECT id, nombre, correo, password_hash FROM usuarios WHERE id = ?", (datos.usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if len(datos.password_nueva.strip()) < 6:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres.")

    # Validar contraseña actual si fue provista
    if datos.password_actual:
        valido = False
        stored = u.get("password_hash")
        if stored:
            try:
                valido = bcrypt.checkpw(datos.password_actual.encode('utf-8'), stored.encode('utf-8'))
            except Exception:
                valido = (datos.password_actual == stored)
        else:
            valido = datos.password_actual in ["123456", "123456789"]

        if not valido:
            raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")

    hash_nuevo = bcrypt.hashpw(datos.password_nueva.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.execute_query("UPDATE usuarios SET password_hash = ? WHERE id = ?", (hash_nuevo, datos.usuario_id), commit=True)
    _empujar_cambio_usuario_remoto(datos.usuario_id)
    registrar_movimiento(u["correo"], "Seguridad", "Cambiar_Password_Perfil", "EXITO", "Contraseña actualizada desde panel de cuenta")
    return {"status": "success", "mensaje": "¡Contraseña actualizada con éxito y sincronizada en Azure SQL y en la Nube!"}


@router.get("/api/usuarios/jerarquia")
def obtener_jerarquia_usuarios(organizacion_id: Optional[int] = None):
    """Retorna los usuarios clasificados en 3 jerarquías paralelas con progreso y asignaciones"""
    base_query = """
        SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.foto_perfil, o.nombre as organizacion_nombre,
               u.mentor_id, m.nombre as mentor_nombre, m.correo as mentor_correo, m.foto_perfil as mentor_foto_perfil
        FROM usuarios u
        LEFT JOIN organizaciones o ON u.organizacion_id = o.id
        LEFT JOIN usuarios m ON u.mentor_id = m.id
        WHERE 1=1
    """
    params = []
    if organizacion_id:
        base_query += " AND u.organizacion_id = ?"
        params.append(organizacion_id)
        
    base_query += " ORDER BY u.nombre ASC"
    todos = db.execute_query(base_query, tuple(params), fetchall=True) or []
    
    administradores = []
    mentores = []
    aprendices = []
    
    # Progreso de cada estudiante
    progresos = db.execute_query("""
        SELECT usuario_id,
               COALESCE(AVG(porcentaje_avance), 0) as promedio_avance,
               COALESCE(SUM(tiempo_dedicado_minutos), 0) as total_minutos,
               COUNT(id) as total_cursos
        FROM progreso_cursos
        GROUP BY usuario_id
    """, fetchall=True) or []
    
    progreso_map = {p["usuario_id"]: p for p in progresos}
    
    # Aprendices vinculados a cada mentor
    aprendices_por_mentor = {}
    for u in todos:
        if u.get("mentor_id"):
            aprendices_por_mentor.setdefault(u["mentor_id"], []).append({
                "id": u["id"],
                "nombre": u["nombre"],
                "correo": u["correo"]
            })
            
    def _clasificar_rol_estricto(rol_raw: str) -> str:
        r = str(rol_raw or "").strip().upper()
        if r in ("SUPER_ADMIN", "SUPER ADMINISTRADOR", "ADMIN", "ADMINISTRADOR", "ADMINISTRATIVO", "BODEGA_LEGAL", "BODEGA LEGAL") or "ADMIN" in r or "BODEGA" in r or "SUPER" in r or "DIRECTIV" in r or "RECTOR" in r:
            return "ADMIN"
        if r in ("MENTOR", "TUTOR", "DOCENTE", "PROFESOR", "INSTRUCTOR", "LIDER") or "MENTOR" in r or "TUTOR" in r or "DOCENT" in r:
            return "MENTOR"
        return "APRENDIZ"

    for u in todos:
        categoria_rol = _clasificar_rol_estricto(u.get("rol"))
        if categoria_rol == "ADMIN":
            administradores.append(u)
        elif categoria_rol == "MENTOR":
            u["aprendices_a_cargo"] = aprendices_por_mentor.get(u["id"], [])
            u["total_aprendices"] = len(u["aprendices_a_cargo"])
            mentores.append(u)
        else:
            prog = progreso_map.get(u["id"], {})
            u["promedio_avance"] = round(prog.get("promedio_avance", 0.0), 1)
            u["total_minutos"] = prog.get("total_minutos", 0)
            u["total_cursos"] = prog.get("total_cursos", 0)
            aprendices.append(u)
            
    return {
        "status": "success",
        "administradores": administradores,
        "mentores": mentores,
        "aprendices": aprendices,
        "totales": {
            "administradores": len(administradores),
            "mentores": len(mentores),
            "aprendices": len(aprendices),
            "total_general": len(todos)
        }
    }


@router.get("/api/superadmin/usuarios/descargar-plantilla-excel")
def descargar_plantilla_excel():
    """Genera y descarga un archivo Excel oficial con 3 hojas estructuradas (Administradores, Mentores y Aprendices)"""
    wb = openpyxl.Workbook()
    header_fill = openpyxl.styles.PatternFill(start_color="091B2C", end_color="091B2C", fill_type="solid")
    header_font = openpyxl.styles.Font(color="FFFFFF", bold=True, size=11)
    center_align = openpyxl.styles.Alignment(horizontal="center", vertical="center")

    # HOJA 1: ADMINISTRADORES
    ws1 = wb.active
    ws1.title = "1_Administradores"
    enc1 = ["Nombre", "Correo", "Rol"]
    ws1.append(enc1)
    for col_num in range(1, len(enc1) + 1):
        cell = ws1.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
    ws1.append(["Coordinador Institucional", "coordinador@institucion.edu.co", "Administrador"])
    ws1.append(["Director Académico", "director@institucion.edu.co", "Administrador"])
    for col in ws1.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws1.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 4, 20)

    # HOJA 2: MENTORES
    ws2 = wb.create_sheet(title="2_Mentores")
    enc2 = ["Nombre", "Correo", "Rol"]
    ws2.append(enc2)
    for col_num in range(1, len(enc2) + 1):
        cell = ws2.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
    ws2.append(["Profesor Carlos Mentor", "profesor.carlos@institucion.edu.co", "Mentor"])
    ws2.append(["Docente María Tutora", "docente.maria@institucion.edu.co", "Mentor"])
    for col in ws2.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws2.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 4, 20)

    # HOJA 3: APRENDICES
    ws3 = wb.create_sheet(title="3_Aprendices")
    enc3 = ["Nombre", "Correo", "Rol", "Mentor_Correo"]
    ws3.append(enc3)
    for col_num in range(1, len(enc3) + 1):
        cell = ws3.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
    ws3.append(["Carlos Gómez Estudiante", "carlos.gomez@institucion.edu.co", "Aprendiz", "profesor.carlos@institucion.edu.co"])
    ws3.append(["Laura Fernández Estudiante", "laura.fernandez@institucion.edu.co", "Aprendiz", "profesor.carlos@institucion.edu.co"])
    ws3.append(["Mateo Ruiz Estudiante", "mateo.ruiz@institucion.edu.co", "Aprendiz", "docente.maria@institucion.edu.co"])
    for col in ws3.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws3.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 4, 24)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_multidisciplinaria_edtech.xlsx"}
    )


@router.post("/api/superadmin/usuarios/cargar-excel")
async def cargar_usuarios_excel(
    request: Request,
    background_tasks: BackgroundTasks,
    archivo: UploadFile = File(...),
    organizacion_id: Optional[Any] = Form(None),
    modo_dominio: Optional[str] = Form("flexible"),
    confirmacion_habeas_data: Optional[str] = Form("true"),
    correo_responsable: Optional[str] = Form(None),
    rol_responsable: Optional[str] = Form("Super Administrador"),
    org_id_query: Optional[Any] = Query(None, alias="organizacion_id"),
    modo_query: Optional[str] = Query(None, alias="modo_dominio")
):
    """Carga masiva multi-rol procesando TODAS las hojas del archivo Excel con motor de alto rendimiento (Bulk Insert):
    - Resuelve la organización de forma ultra flexible (ID, nombre, sufijos) evitando errores de inexistencia
    - Lectura en memoria sin límites de filas (300, 2.000, 100.000+ registros)
    - Deduplicación previa instantánea en 1 sola consulta
    - Inserción masiva por bloques (Bulk executemany) en SQLite y replicación en Azure SQL
    - Auto-matriculación masiva en una sola sentencia SQL
    - Registro inmutable de Acta de Consentimiento Habeas Data en Bodega Legal
    """
    if str(confirmacion_habeas_data or "true").strip().lower() in ("false", "0", "no"):
        raise HTTPException(
            status_code=400,
            detail="Es obligatorio marcar la declaración juramentada de Habeas Data (Ley 1581 de 2012 y autorización de padres/acudientes Art. 7 para menores de edad) antes de importar la base de datos."
        )

    ident_org = organizacion_id if organizacion_id is not None and str(organizacion_id).strip() != "" else org_id_query
    org = resolver_organizacion(ident_org)
    if not org:
        raise HTTPException(status_code=404, detail="La organización seleccionada no existe en la base de datos. Verifique la institución destino.")

    final_org_id = org["id"]
    final_modo = (modo_dominio or modo_query or "flexible").strip().lower()

    nombre_archivo = archivo.filename.lower()
    contenido = await archivo.read()
    filas_procesar = []

    if nombre_archivo.endswith(".xlsx") or nombre_archivo.endswith(".xls"):
        try:
            wb = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
            try:
                sheet_names = wb.sheetnames
                if not sheet_names:
                    raise HTTPException(status_code=400, detail="El archivo Excel no contiene hojas de cálculo.")

                for s_name in sheet_names:
                    sheet = wb[s_name]
                    hoja_titulo = str(s_name).lower().strip()
                    rol_default = None
                    if any(k in hoja_titulo for k in ["admin", "directiv", "coordinad", "rector"]):
                        rol_default = "Administrador"
                    elif any(k in hoja_titulo for k in ["mentor", "docent", "profes", "tutor", "instructor", "lider"]):
                        rol_default = "Mentor"
                    elif any(k in hoja_titulo for k in ["aprendiz", "estudiant", "alumn", "participante", "empleado"]):
                        rol_default = "Aprendiz"

                    header_map = {}
                    primera_fila = True
                    idx_nom = 0
                    idx_corr = 1
                    idx_rol = None
                    idx_men = None

                    for fila in sheet.iter_rows(values_only=True):
                        if not fila or not any(fila):
                            continue
                        if primera_fila:
                            primera_fila = False
                            fila_str = [str(c).lower().strip() if c is not None else "" for c in fila]
                            if any("nombre" in c or "correo" in c or "email" in c or "rol" in c for c in fila_str):
                                for idx, c in enumerate(fila_str):
                                    if "nombre" in c: header_map["nombre"] = idx
                                    elif ("correo" in c or "email" in c) and "mentor" not in c and "tutor" not in c: header_map["correo"] = idx
                                    elif "rol" in c or "cargo" in c or "puesto" in c: header_map["rol"] = idx
                                    elif "mentor" in c or "tutor" in c or "profesor" in c: header_map["mentor"] = idx
                                idx_nom = header_map.get("nombre", 0)
                                idx_corr = header_map.get("correo", 1)
                                idx_rol = header_map.get("rol", 2 if "rol" in header_map else None)
                                idx_men = header_map.get("mentor", 3 if "mentor" in header_map else None)
                                continue

                        if len(fila) > max(idx_nom, idx_corr) and fila[idx_nom] and fila[idx_corr]:
                            nom = str(fila[idx_nom]).strip()
                            corr = str(fila[idx_corr]).strip()
                            if not nom or not corr:
                                continue

                            if idx_rol is not None and len(fila) > idx_rol and fila[idx_rol] and str(fila[idx_rol]).strip():
                                rol = str(fila[idx_rol]).strip()
                            elif rol_default:
                                rol = rol_default
                            else:
                                rol = "Aprendiz"

                            men_corr = None
                            if idx_men is not None and len(fila) > idx_men and fila[idx_men]:
                                men_corr = str(fila[idx_men]).strip()

                            filas_procesar.append((nom, corr, rol, men_corr))
            finally:
                wb.close()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al leer el archivo Excel: {str(e)}")
    else:
        try:
            texto = contenido.decode("utf-8", errors="ignore")
            lector = csv.reader(io.StringIO(texto))
            todas_filas = list(lector)
            inicio_datos = 0
            if todas_filas and ("nombre" in todas_filas[0][0].lower() or "correo" in todas_filas[0][0].lower()):
                inicio_datos = 1

            for fila in todas_filas[inicio_datos:]:
                if fila and len(fila) >= 2 and fila[0] and fila[1]:
                    nom = fila[0].strip()
                    corr = fila[1].strip()
                    rol = fila[2].strip() if len(fila) > 2 and fila[2] else "Aprendiz"
                    men = fila[3].strip() if len(fila) > 3 and fila[3] else None
                    filas_procesar.append((nom, corr, rol, men))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al leer archivo CSV: {str(e)}")

    if not filas_procesar:
        raise HTTPException(status_code=400, detail="No se encontraron filas con datos válidos en ninguna de las hojas del archivo.")

    # Deduplicación y validación masiva ultra-rápida (1 sola consulta en memoria)
    filas_correos = db.execute_query("SELECT LOWER(correo) as correo FROM usuarios", fetchall=True) or []
    correos_existentes = {r["correo"].strip().lower() for r in filas_correos if r.get("correo")}
    correos_vistos_archivo = set()

    conteo_admins = 0
    conteo_mentores = 0
    conteo_aprendices = 0
    alertas = []
    dominio_org = (org["dominio_permitido"] or "").strip().lower()
    hash_generico = bcrypt.hashpw("123456".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    usuarios_para_insertar = []
    usuarios_insertados_info = []

    for idx, (nom, corr, rol_raw, mentor_correo) in enumerate(filas_procesar):
        corr_limpio = corr.lower().strip()
        
        if "@" not in corr_limpio or "." not in corr_limpio.split("@")[-1]:
            alertas.append(f"Fila {idx+1} ({nom}): Formato de correo '{corr_limpio}' inválido (omitido).")
            continue

        dominio_corr = corr_limpio.split("@")[-1].strip()
        
        if final_modo == "estricto":
            if dominio_org and dominio_org != "libre" and dominio_corr != dominio_org:
                alertas.append(f"Fila {idx+1} ({nom}): Correo @{dominio_corr} no coincide con el dominio institucional @{dominio_org} (Modo Estricto).")
                continue

        if corr_limpio in correos_existentes or corr_limpio in correos_vistos_archivo:
            alertas.append(f"Fila {idx+1} ({corr_limpio}): Ya se encuentra registrado en el sistema o duplicado en el archivo (omitido).")
            continue

        correos_vistos_archivo.add(corr_limpio)

        rol_lower = rol_raw.lower().strip()
        if "super" in rol_lower:
            rol_final = "Administrador"
            conteo_admins += 1
        elif "admin" in rol_lower or "coordinador" in rol_lower or "rector" in rol_lower or "director" in rol_lower:
            rol_final = "Administrador"
            conteo_admins += 1
        elif any(k in rol_lower for k in ["mentor", "docente", "profesor", "tutor", "instructor", "lider"]):
            rol_final = "Mentor"
            conteo_mentores += 1
        else:
            rol_final = "Aprendiz"
            conteo_aprendices += 1

        usuarios_para_insertar.append((nom, corr_limpio, hash_generico, rol_final, final_org_id, None))
        usuarios_insertados_info.append({
            "nombre": nom,
            "correo": corr_limpio,
            "rol": rol_final,
            "mentor_correo": mentor_correo.lower().strip() if mentor_correo else None
        })

    registrados = len(usuarios_para_insertar)

    # Inserción masiva por bloques (Bulk insert con executemany)
    if registrados > 0:
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now_dia = datetime.now().strftime("%Y-%m-%d")
        conn = db._conexion_local()
        cursor = conn.cursor()
        
        CHUNK_SIZE = 1000
        for i in range(0, registrados, CHUNK_SIZE):
            chunk = usuarios_para_insertar[i:i + CHUNK_SIZE]
            cursor.executemany(
                "INSERT INTO usuarios (nombre, correo, password_hash, rol, organizacion_id, mentor_id) VALUES (?, ?, ?, ?, ?, ?)",
                chunk
            )
        conn.commit()

        # Historial de nuevos integrantes por bloques
        historial_datos = [
            (u["nombre"], u["correo"], u["rol"], final_org_id, org["nombre"], "Carga Excel", now_ts, now_dia)
            for u in usuarios_insertados_info
        ]
        for i in range(0, len(historial_datos), CHUNK_SIZE):
            chunk_h = historial_datos[i:i + CHUNK_SIZE]
            cursor.executemany(
                "INSERT INTO historial_nuevos_integrantes (nombre, correo, rol, organizacion_id, organizacion_nombre, origen_registro, fecha_registro, fecha_dia) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                chunk_h
            )
        conn.commit()
        notificar_escritura("INSERT INTO usuarios")
        notificar_escritura("INSERT INTO historial_nuevos_integrantes")

        # Asignar mentor por defecto si hay aprendices
        mentor_defecto = db.execute_query(
            "SELECT id FROM usuarios WHERE organizacion_id = ? AND rol = 'Mentor' ORDER BY id ASC LIMIT 1",
            (final_org_id,), fetchone=True
        )
        if mentor_defecto and conteo_aprendices > 0:
            db.execute_query(
                "UPDATE usuarios SET mentor_id = ? WHERE organizacion_id = ? AND rol = 'Aprendiz' AND mentor_id IS NULL",
                (mentor_defecto["id"], final_org_id),
                commit=True
            )

        # Auto-matricular instantáneamente en 1 sola consulta SQL sin bloqueos
        if conteo_aprendices > 0:
            try:
                cursor.execute("""
                    INSERT INTO progreso_cursos (usuario_id, curso_id, porcentaje_avance, tiempo_dedicado_minutos, modulos_completados, estado, fecha_actualizacion)
                    SELECT u.id, am.material_id, 0.0, 0, 0, 'No Iniciado', DATETIME('now', 'localtime')
                    FROM usuarios u
                    JOIN asignacion_material am ON am.organizacion_id = u.organizacion_id
                    WHERE u.organizacion_id = ? AND u.rol = 'Aprendiz'
                    AND NOT EXISTS (
                        SELECT 1 FROM progreso_cursos pc WHERE pc.usuario_id = u.id AND pc.curso_id = am.material_id
                    )
                """, (final_org_id,))
                conn.commit()
                notificar_escritura("INSERT INTO progreso_cursos")
            except Exception as e_mat:
                print(f">> [BULK-MATRICULAS] Aviso: {e_mat}")

        # Despachar correos en segundo plano (Background tasks con límite amigable para no saturar SMTP)
        for u in usuarios_insertados_info[:150]:
            cuerpo_html = generar_html_correo_bienvenida(
                nombre=u["nombre"],
                rol=u["rol"],
                correo=u["correo"],
                institucion_nombre=org["nombre"],
                password_inicial="123456"
            )
            asunto_bienvenida = f"✨ Bienvenido a Consultoría EdTech | {org['nombre']} ({u['rol']})"
            background_tasks.add_task(enviar_correo_smtp, u["correo"], asunto_bienvenida, cuerpo_html)

    # Registro legal inmutable en Bodega Legal
    ip_cliente = obtener_ip_cliente(request) if request else "127.0.0.1"
    correo_autor = (correo_responsable or "alexander.nino.583@gmail.com").strip().lower()
    rol_autor = (rol_responsable or "Super Administrador").strip()
    declaracion_habeas = (
        f"ACTA DE CONSENTIMIENTO EXPRESO HABEAS DATA (LEY 1581 DE 2012 Y DECRETO 1377 DE 2013): "
        f"El usuario responsable '{correo_autor}' ({rol_autor}) desde la IP {ip_cliente} declara bajo la gravedad de juramento "
        f"que el archivo '{archivo.filename}' cargado para la institución '{org['nombre']}' ({len(filas_procesar)} filas leídas, "
        f"{registrados} titulares nuevos incorporados) cuenta con autorización previa, expresa e informada de cada titular "
        f"y, tratándose de estudiantes menores de edad en colegios/entidades educativas, cuenta con el consentimiento "
        f"expreso de sus padres de familia o acudientes legales conforme al Artículo 7 de la Ley 1581 de 2012."
    )
    acta_id = registrar_evento_boveda_legal(
        categoria="ACTA_HABEAS_DATA_EXCEL",
        correo_responsable=correo_autor,
        rol_responsable=rol_autor,
        direccion_ip=ip_cliente,
        organizacion_id=final_org_id,
        organizacion_nombre=org["nombre"],
        tipo_organizacion=org.get("tipo_organizacion") or "Institución en Convenio",
        estado_convenio="HABEAS DATA CERTIFICADO (LEY 1581 & ART. 7)",
        logo_url=None,
        nombre_archivo=archivo.filename,
        cantidad_registros=registrados if registrados > 0 else len(filas_procesar),
        confirmacion_ley1581=True,
        confirmacion_menores_art7=True,
        confirmacion_convenio_logos=True,
        declaracion_legal=declaracion_habeas,
        detalles_dict={
            "archivo_original": archivo.filename,
            "filas_totales_leidas": len(filas_procesar),
            "registros_nuevos_insertados": registrados,
            "administradores": conteo_admins,
            "mentores": conteo_mentores,
            "aprendices": conteo_aprendices,
            "modo_dominio": final_modo
        }
    )
    crear_snapshot_boveda_legal(
        operacion_origen="CARGA_MASIVA_EXCEL_HABEAS_DATA",
        entidad_afectada="usuarios",
        entidad_id=final_org_id,
        entidad_nombre=f"{org['nombre']} ({archivo.filename})",
        correo_responsable=correo_autor,
        direccion_ip=ip_cliente,
        datos_respaldo={
            "acta_legal_id": acta_id,
            "archivo_nombre": archivo.filename,
            "organizacion_id": final_org_id,
            "organizacion_nombre": org["nombre"],
            "usuarios_incorporados": usuarios_insertados_info[:500]
        }
    )

    if registrados > 0:
        try:
            replicador_azure.sincronizar_inmediato([
                "usuarios",
                "progreso_cursos",
                "historial_nuevos_integrantes",
                "boveda_legal_registros",
                "boveda_legal_snapshots"
            ])
        except Exception:
            pass
        _disparar_sync_usuarios_nube()

    modo_legible = "Flexible (Multi-dominio)" if final_modo == "flexible" else "Estricto (Dominio Institucional)"
    return {
        "status": "success",
        "mensaje": f"Se procesaron e inscribieron {registrados} usuarios en {org['nombre']} [{modo_legible}] ({conteo_admins} Administradores, {conteo_mentores} Mentores, {conteo_aprendices} Aprendices). Acta Habeas Data #{acta_id or 1} registrada en Bóveda Legal.",
        "registrados": registrados,
        "acta_legal_id": acta_id,
        "modo_dominio": final_modo,
        "desglose": {
            "administradores": conteo_admins,
            "mentores": conteo_mentores,
            "aprendices": conteo_aprendices
        },
        "alertas": alertas
    }


@router.get("/api/mentores/mis-capacitaciones/{mentor_id}")
def obtener_capacitaciones_mentor(mentor_id: int):
    """Retorna los cursos y materiales pedagógicos dirigidos específicamente a los Mentores/Docentes"""
    m = db.execute_query("SELECT id, organizacion_id FROM usuarios WHERE id = ?", (mentor_id,), fetchone=True)
    org_id = m["organizacion_id"] if m and m.get("organizacion_id") else 1
    
    query = """
        SELECT DISTINCT m.id, m.titulo, m.tipo_material, m.enlace_url, m.rol_destino, m.fecha_publicacion
        FROM material_capacitacion m
        LEFT JOIN asignacion_material a ON m.id = a.material_id
        WHERE (m.rol_destino IN ('Mentor', 'Todos'))
          AND (a.organizacion_id = ? OR a.organizacion_id IS NULL)
        ORDER BY m.id DESC
    """
    materiales = db.execute_query(query, (org_id,), fetchall=True) or []
    return {"status": "success", "data": materiales}


@router.get("/api/mentores/progreso-aprendices/{mentor_id}")
def obtener_progreso_alumnos_mentor(mentor_id: int):
    """Permite al mentor supervisar el progreso real y tiempo de estudio de los estudiantes a su cargo"""
    query = """
        SELECT u.id, u.nombre, u.correo, u.organizacion_id,
               COALESCE(AVG(p.porcentaje_avance), 0) as promedio_avance,
               COALESCE(SUM(p.tiempo_dedicado_minutos), 0) as total_minutos,
               COUNT(p.id) as cursos_iniciados
        FROM usuarios u
        LEFT JOIN progreso_cursos p ON p.usuario_id = u.id
        WHERE u.mentor_id = ? AND u.rol = 'Aprendiz'
        GROUP BY u.id, u.nombre, u.correo, u.organizacion_id
        ORDER BY u.nombre ASC
    """
    alumnos = db.execute_query(query, (mentor_id,), fetchall=True)
    return {"status": "success", "data": alumnos or []}


@router.get("/api/superadmin/mentores/{mentor_id}/descargar-plantilla-excel")
def descargar_plantilla_aprendices_mentor(mentor_id: int):
    """Genera una plantilla Excel para cargar estudiantes directamente a un mentor específico"""
    m = db.execute_query("SELECT id, nombre, correo, organizacion_id FROM usuarios WHERE id = ? AND rol = 'Mentor'", (mentor_id,), fetchone=True)
    if not m:
        raise HTTPException(status_code=404, detail="Mentor no encontrado.")
        
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (m["organizacion_id"],), fetchone=True)
    org_nombre = org["nombre"] if org else "Institución"
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Aprendices"
    
    header_fill = openpyxl.styles.PatternFill(start_color="0A192F", end_color="0A192F", fill_type="solid")
    header_font = openpyxl.styles.Font(color="FFFFFF", bold=True, size=11)
    center_align = openpyxl.styles.Alignment(horizontal="center", vertical="center")
    
    enc = ["Nombre", "Correo", "Documento_Opcional"]
    ws.append(enc)
    for col_num in range(1, len(enc) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        
    ws.append(["Juan Camilo Martínez", f"juan.martinez@{org_nombre.lower().replace(' ', '')}.edu.co", "1023456789"])
    ws.append(["Valentina Rodríguez", f"valentina.rodriguez@{org_nombre.lower().replace(' ', '')}.edu.co", "1098765432"])
    
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = max(max_len + 4, 26)
        
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    
    nombre_limpio = "".join(c for c in m["nombre"] if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
    filename = f"plantilla_aprendices_mentor_{nombre_limpio}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/api/superadmin/mentores/{mentor_id}/cargar-aprendices-excel")
async def cargar_aprendices_mentor_excel(
    mentor_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    confirmacion_habeas_data: Optional[str] = Form("true"),
    correo_responsable: Optional[str] = Form(None)
):
    """Carga masiva de aprendices para un mentor específico vía archivo Excel o CSV:
    - Si el estudiante ya existe, se le asigna este mentor y se actualiza su organización.
    - Si no existe, se crea con rol Aprendiz, contraseña estándar 123456, se auto-matricula en colecciones
      activas y se registra en el Historial de Nuevos Integrantes.
    """
    mentor = db.execute_query("SELECT id, nombre, correo, organizacion_id FROM usuarios WHERE id = ? AND rol = 'Mentor'", (mentor_id,), fetchone=True)
    if not mentor:
        raise HTTPException(status_code=404, detail="El mentor especificado no existe o no tiene rol de Mentor.")
        
    org_id = mentor["organizacion_id"]
    org = db.execute_query("SELECT id, nombre FROM organizaciones WHERE id = ?", (org_id,), fetchone=True)
    org_nombre = org["nombre"] if org else "Institución General"
    
    contenido = await archivo.read()
    nombre_archivo = archivo.filename.lower()
    filas_estudiantes = []
    
    if nombre_archivo.endswith(".xlsx") or nombre_archivo.endswith(".xls"):
        try:
            wb = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True)
            for sheet in wb.worksheets:
                todas_filas = list(sheet.iter_rows(values_only=True))
                if not todas_filas:
                    continue
                header_map = {}
                inicio = 0
                if any(todas_filas[0]):
                    primera = [str(c).lower().strip() if c is not None else "" for c in todas_filas[0]]
                    for idx, h in enumerate(primera):
                        if "nombre" in h or "estudiante" in h or "alumno" in h:
                            header_map["nombre"] = idx
                        elif "correo" in h or "email" in h:
                            header_map["correo"] = idx
                    if "nombre" in header_map or "correo" in header_map:
                        inicio = 1
                idx_nom = header_map.get("nombre", 0)
                idx_corr = header_map.get("correo", 1)
                for f in todas_filas[inicio:]:
                    if f and len(f) > max(idx_nom, idx_corr) and f[idx_nom] and f[idx_corr]:
                        n = str(f[idx_nom]).strip()
                        c = str(f[idx_corr]).strip().lower()
                        if "@" in c:
                            filas_estudiantes.append((n, c))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al leer archivo Excel: {str(e)}")
    elif nombre_archivo.endswith(".csv"):
        try:
            texto = contenido.decode('utf-8-sig', errors='ignore')
            lector = csv.reader(io.StringIO(texto))
            filas_csv = list(lector)
            if filas_csv:
                header_map = {}
                inicio = 0
                primera = [c.lower().strip() for c in filas_csv[0]]
                for idx, h in enumerate(primera):
                    if "nombre" in h or "estudiante" in h: header_map["nombre"] = idx
                    elif "correo" in h or "email" in h: header_map["correo"] = idx
                if "nombre" in header_map or "correo" in header_map:
                    inicio = 1
                idx_nom = header_map.get("nombre", 0)
                idx_corr = header_map.get("correo", 1)
                for f in filas_csv[inicio:]:
                    if f and len(f) > max(idx_nom, idx_corr) and f[idx_nom] and f[idx_corr]:
                        n = f[idx_nom].strip()
                        c = f[idx_corr].strip().lower()
                        if "@" in c:
                            filas_estudiantes.append((n, c))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al leer archivo CSV: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Formato no soportado. Suba un archivo Excel (.xlsx) o CSV.")
        
    if not filas_estudiantes:
        raise HTTPException(status_code=400, detail="No se encontraron registros válidos de estudiantes con nombre y correo en el archivo.")
        
    colecciones_org = db.execute_query("SELECT material_id FROM asignacion_material WHERE organizacion_id = ?", (org_id,), fetchall=True) or []
    colecciones_ids = [c["material_id"] for c in colecciones_org]
    
    hash_defecto = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode('utf-8')
    fecha_actual_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dia_actual_str = datetime.now().strftime("%Y-%m-%d")
    
    total_nuevos = 0
    total_reasignados = 0
    nuevos_para_correo = []
    
    for nombre_est, correo_est in filas_estudiantes:
        u_existente = db.execute_query("SELECT id, rol, organizacion_id, mentor_id FROM usuarios WHERE LOWER(correo) = ?", (correo_est,), fetchone=True)
        
        if u_existente:
            u_id = u_existente["id"]
            db.execute_query("UPDATE usuarios SET mentor_id = ?, organizacion_id = COALESCE(organizacion_id, ?), rol = 'Aprendiz' WHERE id = ?", (mentor_id, org_id, u_id), commit=True)
            total_reasignados += 1
        else:
            u_id = db.execute_query("INSERT INTO usuarios (nombre, correo, rol, organizacion_id, mentor_id, password_hash) VALUES (?, ?, 'Aprendiz', ?, ?, ?)", (nombre_est, correo_est, org_id, mentor_id, hash_defecto))
            total_nuevos += 1
            nuevos_para_correo.append((nombre_est, correo_est))
            
            db.execute_query("""
                INSERT INTO historial_nuevos_integrantes (
                    usuario_id, nombre, correo, rol, organizacion_id, 
                    organizacion_nombre, origen_registro, fecha_registro, fecha_dia
                ) VALUES (?, ?, ?, 'Aprendiz', ?, ?, ?, ?, ?)
            """, (
                u_id, nombre_est, correo_est, org_id, 
                org_nombre, f"📊 Excel Asignado a Mentor: {mentor['nombre']}",
                fecha_actual_str, dia_actual_str
            ))
            
        for mat_id in colecciones_ids:
            prog = db.execute_query("SELECT id FROM progreso_cursos WHERE usuario_id = ? AND curso_id = ?", (u_id, mat_id), fetchone=True)
            if not prog:
                db.execute_query("INSERT INTO progreso_cursos (usuario_id, curso_id, porcentaje_avance, tiempo_dedicado_minutos, modulos_completados, estado, fecha_actualizacion) VALUES (?, ?, 0.0, 0, 0, 'No Iniciado', ?)", (u_id, mat_id, fecha_actual_str), commit=True)
                
    ip_cliente = obtener_ip_cliente(request) if request else "127.0.0.1"
    correo_autor = (correo_responsable or mentor.get("correo") or "alexander.nino.583@gmail.com").strip().lower()
    registrar_evento_boveda_legal(
        categoria="ACTA_HABEAS_DATA_EXCEL",
        correo_responsable=correo_autor,
        rol_responsable="Mentor / Gestor Académico",
        direccion_ip=ip_cliente,
        organizacion_id=org_id,
        organizacion_nombre=org_nombre,
        tipo_organizacion="Grupo de Mentoría",
        estado_convenio="HABEAS DATA CERTIFICADO (LEY 1581 & ART. 7)",
        logo_url=None,
        nombre_archivo=archivo.filename,
        cantidad_registros=len(filas_estudiantes),
        confirmacion_ley1581=True,
        confirmacion_menores_art7=True,
        confirmacion_convenio_logos=True,
        declaracion_legal=(
            f"ACTA HABEAS DATA GRUPO MENTORÍA: Carga de archivo '{archivo.filename}' ({len(filas_estudiantes)} aprendices) "
            f"al grupo del mentor '{mentor['nombre']}' en '{org_nombre}', con confirmación expresa de autorización de titulares y acudientes (Art. 7 Ley 1581)."
        ),
        detalles_dict={
            "mentor_id": mentor_id,
            "mentor_nombre": mentor["nombre"],
            "total_procesados": len(filas_estudiantes),
            "nuevos": total_nuevos,
            "reasignados": total_reasignados
        }
    )

    try:
        replicador_azure.sincronizar_inmediato(['usuarios', 'progreso_cursos', 'historial_nuevos_integrantes', 'boveda_legal_registros'])
    except Exception:
        pass
    _disparar_sync_usuarios_nube()

    if nuevos_para_correo:
        def _enviar_bienvenidas_mentor_bg(lista_est, inst_nom):
            for nom_e, corr_e in lista_est:
                try:
                    html_b = generar_html_correo_bienvenida(
                        nombre=nom_e,
                        rol="Aprendiz",
                        correo=corr_e,
                        institucion_nombre=inst_nom,
                        password_inicial="123456"
                    )
                    asunto_b = f"✨ Bienvenido a Consultoría EdTech | {inst_nom} (Aprendiz)"
                    enviar_correo_smtp(corr_e, asunto_b, f"Bienvenido a Consultoría EdTech. Tu usuario es {corr_e} con clave inicial 123456.", html_b)
                except Exception as e_mail:
                    print(f"[BIENVENIDA MENTOR EXCEL ERROR] {e_mail}")
        threading.Thread(target=_enviar_bienvenidas_mentor_bg, args=(nuevos_para_correo, org_nombre), daemon=True).start()
    
    detalle_msg = f"Mentor: {mentor['nombre']} - Total procesados: {len(filas_estudiantes)} ({total_nuevos} nuevos con clave 123456, {total_reasignados} reasignados)."
    registrar_movimiento("SuperAdmin", "Grupos", "Carga_Excel_Mentor", "EXITO", detalle_msg)
    
    return {
        "status": "success",
        "mensaje": f"Se asignaron exitosamente {len(filas_estudiantes)} aprendices al mentor {mentor['nombre']} ({total_nuevos} nuevos creados, {total_reasignados} reasignados).",
        "mentor_id": mentor_id,
        "mentor_nombre": mentor["nombre"],
        "total_procesados": len(filas_estudiantes),
        "total_nuevos": total_nuevos,
        "total_reasignados": total_reasignados
    }


@router.get("/api/superadmin/grupos/detalle/{organizacion_id}")
def obtener_detalle_grupos_organizacion(organizacion_id: int):
    org = db.execute_query("SELECT id, nombre, tipo_organizacion FROM organizaciones WHERE id = ?", (organizacion_id,), fetchone=True)
    if not org:
        raise HTTPException(status_code=404, detail="Organización no encontrada.")

    # Mentores de la organización
    mentores = db.execute_query(
        """SELECT u.id, u.nombre, u.correo,
                  COUNT(a.id) as total_asignados
           FROM usuarios u
           LEFT JOIN usuarios a ON a.mentor_id = u.id AND a.rol = 'Aprendiz'
           WHERE u.organizacion_id = ? AND u.rol = 'Mentor'
           GROUP BY u.id, u.nombre, u.correo
           ORDER BY u.nombre ASC""",
        (organizacion_id,),
        fetchall=True
    ) or []

    # Detalle de alumnos por mentor
    mentores_con_alumnos = []
    for m in mentores:
        m_dict = dict(m)
        alumnos = db.execute_query(
            """SELECT u.id, u.nombre, u.correo,
                      COALESCE(AVG(p.porcentaje_avance), 0) as promedio_avance
               FROM usuarios u
               LEFT JOIN progreso_cursos p ON p.usuario_id = u.id
               WHERE u.mentor_id = ? AND u.rol = 'Aprendiz'
               GROUP BY u.id, u.nombre, u.correo
               ORDER BY u.nombre ASC""",
            (m["id"],),
            fetchall=True
        ) or []
        m_dict["aprendices"] = alumnos
        mentores_con_alumnos.append(m_dict)

    # Aprendices sin mentor asignado
    sin_mentor = db.execute_query(
        """SELECT u.id, u.nombre, u.correo,
                  COALESCE(AVG(p.porcentaje_avance), 0) as promedio_avance
           FROM usuarios u
           LEFT JOIN progreso_cursos p ON p.usuario_id = u.id
           WHERE u.organizacion_id = ? AND u.rol = 'Aprendiz' AND u.mentor_id IS NULL
           GROUP BY u.id, u.nombre, u.correo
           ORDER BY u.nombre ASC""",
        (organizacion_id,),
        fetchall=True
    ) or []

    total_aprendices = db.execute_query(
        "SELECT COUNT(*) as total FROM usuarios WHERE organizacion_id = ? AND rol = 'Aprendiz'",
        (organizacion_id,),
        fetchone=True
    )
    total_apr_count = total_aprendices["total"] if total_aprendices else 0

    return {
        "status": "success",
        "data": {
            "organizacion": org,
            "mentores": mentores_con_alumnos,
            "sin_mentor": sin_mentor,
            "metricas": {
                "total_mentores": len(mentores_con_alumnos),
                "total_aprendices": total_apr_count,
                "aprendices_asignados": total_apr_count - len(sin_mentor),
                "aprendices_sin_mentor": len(sin_mentor)
            }
        }
    }


@router.put("/api/superadmin/grupos/reasignar")
def reasignar_aprendiz_grupo(datos: ReasignarAprendizReq):
    aprendiz = db.execute_query("SELECT id, nombre, rol FROM usuarios WHERE id = ?", (datos.aprendiz_id,), fetchone=True)
    if not aprendiz or aprendiz["rol"] != "Aprendiz":
        raise HTTPException(status_code=404, detail="El aprendiz especificado no existe o no tiene rol Aprendiz.")

    if datos.mentor_id:
        mentor = db.execute_query("SELECT id, nombre, rol FROM usuarios WHERE id = ?", (datos.mentor_id,), fetchone=True)
        if not mentor or mentor["rol"] != "Mentor":
            raise HTTPException(status_code=400, detail="El mentor de destino especificado no es válido.")

        db.execute_query("UPDATE usuarios SET mentor_id = ? WHERE id = ?", (datos.mentor_id, datos.aprendiz_id), commit=True)
        registrar_movimiento("SuperAdmin", "Grupos", "Reasignar_Aprendiz", "EXITO", f"Aprendiz {aprendiz['nombre']} asignado a {mentor['nombre']}")
        return {"status": "success", "mensaje": f"{aprendiz['nombre']} fue asignado a {mentor['nombre']} exitosamente."}
    else:
        db.execute_query("UPDATE usuarios SET mentor_id = NULL WHERE id = ?", (datos.aprendiz_id,), commit=True)
        registrar_movimiento("SuperAdmin", "Grupos", "Desvincular_Aprendiz", "EXITO", f"Aprendiz {aprendiz['nombre']} pasado a banco sin mentor.")
        return {"status": "success", "mensaje": f"{aprendiz['nombre']} ahora está en la bandeja de aprendices sin mentor."}


@router.put("/api/superadmin/grupos/desvincular/{aprendiz_id}")
def desvincular_aprendiz_grupo(aprendiz_id: int):
    aprendiz = db.execute_query("SELECT id, nombre, rol FROM usuarios WHERE id = ?", (aprendiz_id,), fetchone=True)
    if not aprendiz or aprendiz["rol"] != "Aprendiz":
        raise HTTPException(status_code=404, detail="Aprendiz no encontrado.")
    db.execute_query("UPDATE usuarios SET mentor_id = NULL WHERE id = ?", (aprendiz_id,), commit=True)
    registrar_movimiento("SuperAdmin", "Grupos", "Desvincular_Aprendiz", "EXITO", f"Aprendiz {aprendiz['nombre']} desvinculado de su grupo.")
    return {"status": "success", "mensaje": f"{aprendiz['nombre']} desvinculado del mentor exitosamente."}


@router.put("/api/superadmin/grupos/asignar-lote")
def asignar_lote_grupo(datos: AsignarLoteGrupoReq):
    mentor = db.execute_query("SELECT id, nombre, rol FROM usuarios WHERE id = ?", (datos.mentor_id,), fetchone=True)
    if not mentor or mentor["rol"] != "Mentor":
        raise HTTPException(status_code=400, detail="El mentor seleccionado no es válido.")
    if not datos.aprendices_ids:
        return {"status": "success", "mensaje": "No se enviaron aprendices para asignar."}

    for a_id in datos.aprendices_ids:
        db.execute_query("UPDATE usuarios SET mentor_id = ? WHERE id = ? AND rol = 'Aprendiz'", (datos.mentor_id, a_id), commit=True)

    registrar_movimiento("SuperAdmin", "Grupos", "Asignacion_Lote", "EXITO", f"{len(datos.aprendices_ids)} aprendices asignados a {mentor['nombre']}")
    return {"status": "success", "mensaje": f"{len(datos.aprendices_ids)} aprendices asignados al mentor {mentor['nombre']} exitosamente."}


@router.get("/api/usuarios/{usuario_id}/espacio-trabajo")
def obtener_espacio_trabajo(usuario_id: int):
    """Retorna el tema decorativo, racha semanal, colores y opciones de diseño del usuario"""
    u = db.execute_query("""
        SELECT id, nombre, rol, foto_perfil,
               COALESCE(tema_decorativo, 'estandar') as tema_decorativo,
               fondo_personalizado,
               colores_personalizados,
               disenos_personalizados_json,
               COALESCE(racha_semanas, 5) as racha_semanas,
               COALESCE(minutos_dedicados_totales, 180) as minutos_dedicados_totales
        FROM usuarios WHERE id = ?
    """, (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # Desbloqueado si racha >= 5 o rol es Mentor, Administrador, Super Administrador
    desbloqueado = (u.get("racha_semanas", 0) >= 5) or (u.get("rol") in ("Mentor", "Administrador", "Super Administrador"))
    horas = round(u.get("minutos_dedicados_totales", 0) / 60, 1)

    return {
        "status": "success",
        "usuario_id": usuario_id,
        "foto_perfil": u.get("foto_perfil"),
        "tema_decorativo": u.get("tema_decorativo", "estandar"),
        "fondo_personalizado": u.get("fondo_personalizado"),
        "colores_personalizados": u.get("colores_personalizados"),
        "disenos_personalizados_json": u.get("disenos_personalizados_json"),
        "racha_semanas": u.get("racha_semanas", 5),
        "minutos_dedicados": u.get("minutos_dedicados_totales", 180),
        "horas_dedicadas": horas,
        "desbloqueado": desbloqueado
    }


@router.post("/api/usuarios/{usuario_id}/tema-decorativo")
def actualizar_tema_decorativo(usuario_id: int, req: ActualizarTemaDecorativoRequest):
    """Actualiza el tema decorativo y wallpaper del usuario"""
    u = db.execute_query("SELECT id, nombre, rol, racha_semanas FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    db.execute_query("""
        UPDATE usuarios 
        SET tema_decorativo = ?, fondo_personalizado = ?
        WHERE id = ?
    """, (req.tema_decorativo, req.fondo_personalizado, usuario_id), commit=True)

    registrar_movimiento(u["nombre"], "Personalizacion", "Actualizar_Tema_Decorativo", "EXITO", f"Tema decorativo '{req.tema_decorativo}' aplicado")
    return {"status": "success", "mensaje": f"¡Tema decorativo '{req.tema_decorativo}' guardado exitosamente!"}


@router.post("/api/usuarios/{usuario_id}/colores-personalizados")
def guardar_colores_personalizados(usuario_id: int, req: ColoresPersonalizadosReq):
    """Guarda la paleta de colores propia del usuario en la base de datos para persistencia total"""
    u = db.execute_query("SELECT id, nombre, correo FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    colores_dict = {
        "primario": req.primario or "#0a192f",
        "acento": req.acento or "#06b6d4",
        "fondo": req.fondo or "#030712"
    }
    colores_json = json.dumps(colores_dict)
    
    db.execute_query("UPDATE usuarios SET colores_personalizados = ? WHERE id = ?", (colores_json, usuario_id), commit=True)
    registrar_movimiento(u["correo"], "Personalizacion", "Guardar_Colores", "EXITO", f"Paleta guardada: {colores_json}")
    return {"status": "success", "mensaje": "Paleta de colores guardada exitosamente.", "colores": colores_dict}


@router.get("/api/usuarios/{usuario_id}/disenos-sugerencias")
def obtener_disenos_sugerencias(usuario_id: int):
    """Retorna las opciones y sugerencias de diseños temáticos editables por el usuario"""
    u = db.execute_query("SELECT id, disenos_personalizados_json, tema_decorativo FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    disenos = DISENOS_SUGERENCIAS_DEFAULT
    if u.get("disenos_personalizados_json"):
        try:
            disenos = json.loads(u["disenos_personalizados_json"])
        except Exception:
            disenos = DISENOS_SUGERENCIAS_DEFAULT
            
    return {
        "status": "success",
        "disenos": disenos,
        "tema_actual": u.get("tema_decorativo") or "estandar"
    }


@router.post("/api/usuarios/{usuario_id}/disenos-sugerencias")
def guardar_disenos_sugerencias(usuario_id: int, req: DisenosPersonalizadosReq):
    """Guarda las opciones y sugerencias de diseño editadas, agregadas o eliminadas por el usuario"""
    u = db.execute_query("SELECT id, nombre, correo FROM usuarios WHERE id = ?", (usuario_id,), fetchone=True)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
    disenos_str = json.dumps(req.disenos, ensure_ascii=False)
    db.execute_query("UPDATE usuarios SET disenos_personalizados_json = ? WHERE id = ?", (disenos_str, usuario_id), commit=True)
    registrar_movimiento(u["correo"], "Personalizacion", "Guardar_Disenos_Sugerencias", "EXITO", f"{len(req.disenos)} opciones de diseño guardadas")
    return {"status": "success", "mensaje": "Opciones y sugerencias de diseño actualizadas exitosamente.", "disenos": req.disenos}


@router.get("/api/mentor/{mentor_id}/alumnos-detalle")
def obtener_alumnos_detalle_mentor(mentor_id: int):
    """Retorna el listado enriquecido de aprendices a cargo del mentor con tiempos, rachas y decoraciones"""
    m = db.execute_query("SELECT id, organizacion_id FROM usuarios WHERE id = ?", (mentor_id,), fetchone=True)
    if not m:
        raise HTTPException(status_code=404, detail="Mentor no encontrado.")

    alumnos = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.foto_perfil,
               COALESCE(u.racha_semanas, 5) as racha_semanas,
               COALESCE(u.minutos_dedicados_totales, 180) as minutos_dedicados_totales,
               COALESCE(u.tema_decorativo, 'estandar') as tema_decorativo,
               u.fondo_personalizado,
               o.nombre as organizacion_nombre
        FROM usuarios u
        LEFT JOIN organizaciones o ON o.id = u.organizacion_id
        WHERE u.mentor_id = ? AND u.rol = 'Aprendiz'
        ORDER BY u.id ASC
    """, (mentor_id,), fetchall=True) or []

    # Progresos y quizzes para cada alumno
    resultado = []
    for a in alumnos:
        a_id = a["id"]
        progs = db.execute_query("SELECT porcentaje_avance, modulos_completados, estado FROM progreso_cursos WHERE usuario_id = ?", (a_id,), fetchall=True) or []
        prom_avance = round(sum(float(p.get("porcentaje_avance", 0)) for p in progs) / len(progs), 1) if progs else 0.0
        cursos_comp = sum(1 for p in progs if float(p.get("porcentaje_avance", 0)) >= 80)
        
        qz_hechos = db.execute_query("SELECT id, calificacion, aprobado FROM progreso_quizzes WHERE aprendiz_id = ?", (a_id,), fetchall=True) or []
        mins = int(a.get("minutos_dedicados_totales", 180))
        horas = round(mins / 60, 1)
        prom_qz = round(sum(float(q.get("calificacion", 0)) for q in qz_hechos) / len(qz_hechos), 1) if qz_hechos else 0.0

        resultado.append({
            "id": a_id,
            "nombre": a["nombre"],
            "correo": a["correo"],
            "foto_perfil": a.get("foto_perfil"),
            "organizacion_nombre": a.get("organizacion_nombre", "Sin Institución"),
            "promedio_avance": prom_avance,
            "cursos_iniciados": len(progs),
            "cursos_completados": cursos_comp,
            "cursos_totales": len(progs),
            "minutos_dedicados": mins,
            "tiempo_dedicado_horas": horas,
            "racha_semanas": a.get("racha_semanas", 5),
            "tema_decorativo": a.get("tema_decorativo", "estandar"),
            "fondo_personalizado": a.get("fondo_personalizado"),
            "quizzes_aprobados": sum(1 for q in qz_hechos if q.get("aprobado")),
            "quizzes_completados": len(qz_hechos),
            "quizzes_totales": len(qz_hechos),
            "promedio_quizzes": prom_qz
        })

    return {"status": "success", "total": len(resultado), "data": resultado}


@router.get("/api/mentor/{mentor_id}/metricas-clase")
def obtener_metricas_clase_mentor(mentor_id: int):
    """Calcula y retorna estadísticas y series de Chart.js para la clase del mentor"""
    m = db.execute_query("SELECT id, nombre, organizacion_id FROM usuarios WHERE id = ?", (mentor_id,), fetchone=True)
    if not m:
        raise HTTPException(status_code=404, detail="Mentor no encontrado.")

    alumnos = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.foto_perfil,
               COALESCE(u.racha_semanas, 5) as racha_semanas,
               COALESCE(u.minutos_dedicados_totales, 180) as minutos_dedicados_totales
        FROM usuarios u
        WHERE u.mentor_id = ? AND u.rol = 'Aprendiz'
        ORDER BY u.id ASC
    """, (mentor_id,), fetchall=True) or []

    # Quizzes del mentor
    quizzes_mentor = db.execute_query("SELECT id FROM quizzes_evaluaciones WHERE mentor_id = ? AND activo = 1", (mentor_id,), fetchall=True) or []
    num_quizzes_creados = len(quizzes_mentor)

    labels = []
    avances_cursos = []
    califs_quizzes = []
    tiempos_mins = []
    total_quizzes_aprobados = 0
    total_quizzes_no_aprobados = 0
    total_quizzes_pendientes = 0

    for a in alumnos:
        a_id = a["id"]
        partes = a["nombre"].split()
        nombre_corto = f"{partes[0]} {partes[1][0]}." if len(partes) > 1 else a["nombre"]
        labels.append(nombre_corto)

        progs = db.execute_query("SELECT porcentaje_avance FROM progreso_cursos WHERE usuario_id = ?", (a_id,), fetchall=True) or []
        prom_avance = round(sum(float(p.get("porcentaje_avance", 0)) for p in progs) / len(progs), 1) if progs else 0.0
        avances_cursos.append(prom_avance)

        qz_hechos = db.execute_query("SELECT calificacion, aprobado FROM progreso_quizzes WHERE aprendiz_id = ?", (a_id,), fetchall=True) or []
        prom_qz = round(sum(float(q.get("calificacion", 0)) for q in qz_hechos) / len(qz_hechos), 1) if qz_hechos else 0.0
        califs_quizzes.append(prom_qz)

        min_u = int(a.get("minutos_dedicados_totales") or 180)
        tiempos_mins.append(min_u)

        aprob = sum(1 for q in qz_hechos if q.get("aprobado"))
        no_aprob = len(qz_hechos) - aprob
        total_quizzes_aprobados += aprob
        total_quizzes_no_aprobados += no_aprob
        
        pend = max(0, num_quizzes_creados - len(qz_hechos))
        total_quizzes_pendientes += pend

    total_alumnos = len(alumnos)
    prom_general_cursos = round(sum(avances_cursos) / total_alumnos, 1) if total_alumnos > 0 else 0.0
    prom_general_quizzes = round(sum(califs_quizzes) / total_alumnos, 1) if total_alumnos > 0 else 0.0
    tiempo_total_min = sum(tiempos_mins)
    tiempo_total_horas = round(tiempo_total_min / 60, 1)

    return {
        "status": "success",
        "mentor_nombre": m["nombre"],
        "total_alumnos": total_alumnos,
        "promedio_avance_cursos": prom_general_cursos,
        "promedio_calif_quizzes": prom_general_quizzes,
        "tiempo_total_minutos": tiempo_total_min,
        "tiempo_total_horas": tiempo_total_horas,
        "labels": labels,
        "series_avance_cursos": avances_cursos,
        "series_calif_quizzes": califs_quizzes,
        "series_tiempo_minutos": tiempos_mins,
        "distribucion_quizzes": {
            "aprobados": total_quizzes_aprobados,
            "no_aprobados": total_quizzes_no_aprobados,
            "pendientes": total_quizzes_pendientes
        }
    }


@router.get("/api/mentor/{mentor_id}/reporte-excel-clase")
def descargar_reporte_excel_clase_mentor(mentor_id: int):
    """Genera y descarga informe oficial en Excel (.xlsx) de la clase del mentor con gráficas nativas openpyxl"""
    try:
        m = db.execute_query("""
            SELECT u.id, u.nombre, u.correo, u.organizacion_id, o.nombre as organizacion_nombre
            FROM usuarios u
            LEFT JOIN organizaciones o ON u.organizacion_id = o.id
            WHERE u.id = ?
        """, (mentor_id,), fetchone=True)
        if not m:
            raise HTTPException(status_code=404, detail="Mentor no encontrado.")

        now = datetime.now()
        wb = openpyxl.Workbook()

        # Estilos Corporativos
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

        alumnos = db.execute_query("""
            SELECT u.id, u.nombre, u.correo,
                   COALESCE(u.racha_semanas, 5) as racha,
                   COALESCE(u.minutos_dedicados_totales, 180) as minutos
            FROM usuarios u
            WHERE u.mentor_id = ? AND u.rol = 'Aprendiz'
            ORDER BY u.id ASC
        """, (mentor_id,), fetchall=True) or []

        cursos_cat = db.execute_query("SELECT id, titulo, tipo_material, total_modulos FROM material_capacitacion WHERE (rol_destino != 'Mentor' OR rol_destino IS NULL)", fetchall=True) or []
        progresos = db.execute_query("SELECT usuario_id, curso_id, porcentaje_avance, modulos_completados, tiempo_dedicado_minutos, estado FROM progreso_cursos", fetchall=True) or []
        quizzes = db.execute_query("SELECT id, titulo, tipo, duracion_minutos FROM quizzes_evaluaciones WHERE mentor_id = ? AND activo = 1", (mentor_id,), fetchall=True) or []
        quizzes_prog = db.execute_query("SELECT id, quiz_id, aprendiz_id, calificacion, aprobado, tiempo_segundos, fecha_completado FROM progreso_quizzes", fetchall=True) or []

        total_alumnos = len(alumnos)
        org_nombre = m.get("organizacion_nombre") or "Institución Principal"

        # -------------------------------------------------------------
        # HOJA 1: RESUMEN DE CLASE
        # -------------------------------------------------------------
        ws_res = wb.active
        ws_res.title = "Resumen de Clase"
        ws_res.views.sheetView[0].showGridLines = True

        ws_res.merge_cells("A1:G1")
        t1 = ws_res["A1"]
        t1.value = "CENTRO DE MANDO EDTECH · REPORTE OFICIAL DE CLASE Y RENDIMIENTO"
        t1.font = font_title
        t1.fill = fill_navy
        t1.alignment = Alignment(horizontal="center", vertical="center")
        ws_res.row_dimensions[1].height = 36

        ws_res.merge_cells("A2:G2")
        sub1 = ws_res["A2"]
        sub1.value = f"Mentor: {m['nombre']} ({m['correo']}) · Institución: {org_nombre} · {now.strftime('%d/%m/%Y a las %H:%M:%S')}"
        sub1.font = font_sub
        sub1.fill = fill_sub
        sub1.alignment = Alignment(horizontal="center", vertical="center")
        ws_res.row_dimensions[2].height = 20

        alumnos_ranking = []
        tot_avance_sum = 0
        tot_calif_sum = 0
        tot_quizzes_rendidos = 0
        tot_quizzes_aprobados = 0
        tot_minutos = 0

        for apr in alumnos:
            a_id = apr["id"]
            p_u = [p for p in progresos if p.get("usuario_id") == a_id]
            prom_cur = round(sum(float(p.get("porcentaje_avance", 0)) for p in p_u) / len(p_u), 1) if p_u else 0.0
            
            q_u = [q for q in quizzes_prog if q.get("aprendiz_id") == a_id]
            prom_qz = round(sum(float(q.get("calificacion", 0)) for q in q_u) / len(q_u), 1) if q_u else 0.0
            aprob_qz = sum(1 for q in q_u if q.get("aprobado"))

            mins = int(apr.get("minutos") or 180)
            horas = round(mins / 60, 1)

            tot_avance_sum += prom_cur
            if q_u:
                tot_calif_sum += prom_qz
                tot_quizzes_rendidos += len(q_u)
                tot_quizzes_aprobados += aprob_qz
            tot_minutos += mins

            estado = "Graduado / Aprobado" if prom_cur >= 80 else ("En Progreso Activo" if prom_cur > 0 else "Sin Iniciar")

            alumnos_ranking.append({
                "id": a_id,
                "nombre": apr["nombre"],
                "correo": apr["correo"],
                "avance_cursos": prom_cur,
                "promedio_quizzes": prom_qz,
                "quizzes_aprobados": aprob_qz,
                "quizzes_hechos": len(q_u),
                "horas": horas,
                "minutos": mins,
                "racha": apr.get("racha", 5),
                "estado": estado
            })

        prom_clase_cursos = round(tot_avance_sum / total_alumnos, 1) if total_alumnos > 0 else 0.0
        prom_clase_quizzes = round(tot_calif_sum / total_alumnos, 1) if total_alumnos > 0 else 0.0
        horas_clase_total = round(tot_minutos / 60, 1)

        kpi_defs = [
            ("Estudiantes en Clase", str(total_alumnos), "A4", "B5"),
            ("Promedio Avance Cursos", f"{prom_clase_cursos}%", "C4", "D5"),
            ("Promedio Calificación Quizzes", f"{prom_clase_quizzes}%", "E4", "F5"),
            ("Horas de Estudio Totales", f"{horas_clase_total} hrs", "A7", "B8"),
            ("Quizzes Aprobados", f"{tot_quizzes_aprobados}", "C7", "D8"),
            ("Quizzes Publicados", str(len(quizzes)), "E7", "F8"),
        ]
        for titulo, valor, top_left, bot_right in kpi_defs:
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
        # HOJA 2: ESTUDIANTES Y RENDIMIENTO (CON GRÁFICA NATIVA)
        # -------------------------------------------------------------
        ws_est = wb.create_sheet(title="Estudiantes y Rendimiento")
        ws_est.views.sheetView[0].showGridLines = True
        ws_est.row_dimensions[1].height = 24

        headers_est = ["Puesto", "Estudiante", "Correo", "Avance Cursos %", "Promedio Quizzes %", "Quizzes Aprobados", "Horas de Estudio", "Racha Semanal", "Estado Académico"]
        for c_i, h in enumerate(headers_est, start=1):
            cell = ws_est.cell(row=1, column=c_i, value=h)
            cell.font = font_header
            cell.fill = fill_navy
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_thin

        alumnos_ranking.sort(key=lambda x: (x["avance_cursos"], x["promedio_quizzes"]), reverse=True)

        for r_i, apr in enumerate(alumnos_ranking, start=2):
            ws_est.cell(row=r_i, column=1, value=r_i - 1).alignment = Alignment(horizontal="center")
            ws_est.cell(row=r_i, column=2, value=apr["nombre"]).font = font_bold
            ws_est.cell(row=r_i, column=3, value=apr["correo"])
            ws_est.cell(row=r_i, column=4, value=apr["avance_cursos"]).alignment = Alignment(horizontal="center")
            ws_est.cell(row=r_i, column=5, value=apr["promedio_quizzes"]).alignment = Alignment(horizontal="center")
            ws_est.cell(row=r_i, column=6, value=apr["quizzes_aprobados"]).alignment = Alignment(horizontal="center")
            ws_est.cell(row=r_i, column=7, value=apr["horas"]).alignment = Alignment(horizontal="center")
            ws_est.cell(row=r_i, column=8, value=apr["racha"]).alignment = Alignment(horizontal="center")
            ws_est.cell(row=r_i, column=9, value=apr["estado"]).alignment = Alignment(horizontal="center")
            for c in range(1, 10):
                ws_est.cell(row=r_i, column=c).border = border_thin
                if c != 2:
                    ws_est.cell(row=r_i, column=c).font = font_normal

        if len(alumnos_ranking) > 0:
            chart_bar = BarChart()
            chart_bar.type = "col"
            chart_bar.style = 10
            chart_bar.title = "Avance en Cursos vs Calificación en Quizzes (%)"
            chart_bar.y_axis.title = "Porcentaje (%)"
            chart_bar.x_axis.title = "Estudiantes"
            chart_bar.width = 18
            chart_bar.height = 11

            data_ref = Reference(ws_est, min_col=4, min_row=1, max_col=5, max_row=len(alumnos_ranking) + 1)
            cats_ref = Reference(ws_est, min_col=2, min_row=2, max_row=len(alumnos_ranking) + 1)
            chart_bar.add_data(data_ref, titles_from_data=True)
            chart_bar.set_categories(cats_ref)
            ws_est.add_chart(chart_bar, "K3")

        # -------------------------------------------------------------
        # HOJA 3: COLECCIONES MICROSOFT LEARN (DESGLOSE GRANULAR)
        # -------------------------------------------------------------
        ws_col = wb.create_sheet(title="Colecciones Microsoft Learn")
        ws_col.views.sheetView[0].showGridLines = True
        ws_col.row_dimensions[1].height = 24

        headers_col = ["Estudiante", "Correo", "Colección / Ruta Microsoft", "Tipo", "Módulos Completados", "Avance %", "Tiempo (min)", "Estado"]
        for c_i, h in enumerate(headers_col, start=1):
            cell = ws_col.cell(row=1, column=c_i, value=h)
            cell.font = font_header
            cell.fill = fill_sub
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_thin

        fila_c = 2
        for apr in alumnos:
            a_id = apr["id"]
            p_u = [p for p in progresos if p.get("usuario_id") == a_id]
            for cur in cursos_cat:
                c_id = cur["id"]
                match_p = next((p for p in p_u if p.get("curso_id") == c_id), None)
                avance = round(float(match_p.get("porcentaje_avance", 0)), 1) if match_p else 0.0
                mods = match_p.get("modulos_completados", 0) if match_p else 0
                tot_m = cur.get("total_modulos", 3)
                mins = match_p.get("tiempo_dedicado_minutos", 0) if match_p else 0
                est = match_p.get("estado", "No Iniciado") if match_p else "No Iniciado"

                ws_col.cell(row=fila_c, column=1, value=apr["nombre"]).font = font_bold
                ws_col.cell(row=fila_c, column=2, value=apr["correo"])
                ws_col.cell(row=fila_c, column=3, value=cur["titulo"])
                ws_col.cell(row=fila_c, column=4, value=cur.get("tipo_material", "Colección")).alignment = Alignment(horizontal="center")
                ws_col.cell(row=fila_c, column=5, value=f"{mods} de {tot_m}").alignment = Alignment(horizontal="center")
                ws_col.cell(row=fila_c, column=6, value=avance).alignment = Alignment(horizontal="center")
                ws_col.cell(row=fila_c, column=7, value=mins).alignment = Alignment(horizontal="center")
                ws_col.cell(row=fila_c, column=8, value=est).alignment = Alignment(horizontal="center")

                for c in range(1, 9):
                    ws_col.cell(row=fila_c, column=c).border = border_thin
                    if c != 1:
                        ws_col.cell(row=fila_c, column=c).font = font_normal
                fila_c += 1

        # -------------------------------------------------------------
        # HOJA 4: QUIZZES Y EVALUACIONES (DESGLOSE Y GRÁFICA CIRCULAR)
        # -------------------------------------------------------------
        ws_qsheet = wb.create_sheet(title="Quizzes y Evaluaciones")
        ws_qsheet.views.sheetView[0].showGridLines = True
        ws_qsheet.row_dimensions[1].height = 24

        headers_q = ["Estudiante", "Correo", "Evaluación / Quiz", "Tipo", "Calificación %", "Aprobado", "Tiempo Empleado", "Fecha Completado", "Estado"]
        for c_i, h in enumerate(headers_q, start=1):
            cell = ws_qsheet.cell(row=1, column=c_i, value=h)
            cell.font = font_header
            cell.fill = fill_navy
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_thin

        fila_q = 2
        aprob_total_conteo = 0
        no_aprob_conteo = 0
        pend_conteo = 0

        for apr in alumnos:
            a_id = apr["id"]
            for qz in quizzes:
                q_id = qz["id"]
                match_qz = next((pq for pq in quizzes_prog if pq.get("quiz_id") == q_id and pq.get("aprendiz_id") == a_id), None)
                if match_qz:
                    calif = round(float(match_qz.get("calificacion") or 0), 1)
                    aprob = bool(match_qz.get("aprobado"))
                    if aprob:
                        aprob_total_conteo += 1
                    else:
                        no_aprob_conteo += 1
                    segs = int(match_qz.get("tiempo_segundos") or 0)
                    t_fmt = f"{segs // 60}m {segs % 60}s" if segs >= 60 else f"{segs}s"
                    f_comp = match_qz.get("fecha_completado") or "Completado"
                    estado_q = "Aprobado" if aprob else "No Aprobado"
                else:
                    calif = "-"
                    aprob = "-"
                    t_fmt = "-"
                    f_comp = "-"
                    estado_q = "Pendiente"
                    pend_conteo += 1

                ws_qsheet.cell(row=fila_q, column=1, value=apr["nombre"]).font = font_bold
                ws_qsheet.cell(row=fila_q, column=2, value=apr["correo"])
                ws_qsheet.cell(row=fila_q, column=3, value=qz["titulo"])
                ws_qsheet.cell(row=fila_q, column=4, value=qz.get("tipo", "Quiz")).alignment = Alignment(horizontal="center")
                ws_qsheet.cell(row=fila_q, column=5, value=calif).alignment = Alignment(horizontal="center")
                ws_qsheet.cell(row=fila_q, column=6, value="Sí" if aprob is True else ("No" if aprob is False else "-")).alignment = Alignment(horizontal="center")
                ws_qsheet.cell(row=fila_q, column=7, value=t_fmt).alignment = Alignment(horizontal="center")
                ws_qsheet.cell(row=fila_q, column=8, value=f_comp).alignment = Alignment(horizontal="center")
                ws_qsheet.cell(row=fila_q, column=9, value=estado_q).alignment = Alignment(horizontal="center")

                for c in range(1, 10):
                    ws_qsheet.cell(row=fila_q, column=c).border = border_thin
                    if c != 1:
                        ws_qsheet.cell(row=fila_q, column=c).font = font_normal
                fila_q += 1

        ws_qsheet.cell(row=2, column=11, value="Estado").font = font_header
        ws_qsheet.cell(row=2, column=11).fill = fill_sub
        ws_qsheet.cell(row=2, column=12, value="Cantidad").font = font_header
        ws_qsheet.cell(row=2, column=12).fill = fill_sub

        ws_qsheet.cell(row=3, column=11, value="Aprobados").font = font_bold
        ws_qsheet.cell(row=3, column=12, value=aprob_total_conteo)
        ws_qsheet.cell(row=4, column=11, value="No Aprobados").font = font_bold
        ws_qsheet.cell(row=4, column=12, value=no_aprob_conteo)
        ws_qsheet.cell(row=5, column=11, value="Pendientes").font = font_bold
        ws_qsheet.cell(row=5, column=12, value=pend_conteo)

        for r_pie in range(3, 6):
            ws_qsheet.cell(row=r_pie, column=11).border = border_thin
            ws_qsheet.cell(row=r_pie, column=12).border = border_thin

        chart_pie = PieChart()
        chart_pie.title = "Distribución de Entregas y Quizzes"
        chart_pie.width = 14
        chart_pie.height = 9
        labels_pie = Reference(ws_qsheet, min_col=11, min_row=3, max_row=5)
        data_pie = Reference(ws_qsheet, min_col=12, min_row=2, max_row=5)
        chart_pie.add_data(data_pie, titles_from_data=True)
        chart_pie.set_categories(labels_pie)
        ws_qsheet.add_chart(chart_pie, "K7")

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

        nombre_archivo = f"reporte_clase_mentor_{mentor_id}_{now.strftime('%Y_%m_%d_%H%M%S')}.xlsx"
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        registrar_movimiento(m["correo"], "Docencia", "Exportar_Excel_Clase_Mentor", "EXITO", f"Reporte de clase '{nombre_archivo}' con gráficas descargado")
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
        )
    except Exception as e:
        print(f">> Error exportando reporte de clase mentor: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando reporte de clase: {str(e)}")


@router.get("/api/historial-integrantes/listar")
def listar_historial_integrantes(
    fecha: Optional[str] = None,
    rol: Optional[str] = None,
    busqueda: Optional[str] = None,
    organizacion_id: Optional[int] = None
):
    """Retorna los nuevos integrantes agrupados cronológicamente por día, con métricas y filtros"""
    query = """
        SELECT h.id, h.usuario_id, h.nombre, h.correo, h.rol, h.organizacion_id,
               h.organizacion_nombre, h.origen_registro, h.fecha_registro, h.fecha_dia
        FROM historial_nuevos_integrantes h
        WHERE 1=1
    """
    params = []

    if fecha and fecha.strip():
        query += " AND h.fecha_dia = ?"
        params.append(fecha.strip())

    if rol and rol.strip() and rol.strip().upper() != "TODOS":
        query += " AND h.rol = ?"
        params.append(rol.strip())

    if organizacion_id:
        query += " AND h.organizacion_id = ?"
        params.append(organizacion_id)

    if busqueda and busqueda.strip():
        b_like = f"%{busqueda.strip().lower()}%"
        query += " AND (LOWER(h.nombre) LIKE ? OR LOWER(h.correo) LIKE ? OR LOWER(h.organizacion_nombre) LIKE ?)"
        params.extend([b_like, b_like, b_like])

    query += " ORDER BY h.fecha_registro DESC, h.id DESC"

    filas = db.execute_query(query, tuple(params), fetchall=True) or []

    # Agrupar registros por día
    registros_por_dia = {}
    hoy_str = datetime.now().strftime("%Y-%m-%d")
    ayer_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    total_hoy = 0
    total_ayer = 0

    for f in filas:
        dia = f.get("fecha_dia") or (f.get("fecha_registro", "")[:10] if f.get("fecha_registro") else hoy_str)
        if dia == hoy_str:
            total_hoy += 1
        elif dia == ayer_str:
            total_ayer += 1

        if dia not in registros_por_dia:
            registros_por_dia[dia] = []
        registros_por_dia[dia].append(dict(f))

    # Resumen de días registrados
    resumen_dias = db.execute_query("""
        SELECT fecha_dia, COUNT(*) as total_integrantes
        FROM historial_nuevos_integrantes
        GROUP BY fecha_dia
        ORDER BY fecha_dia DESC
    """, fetchall=True) or []

    return {
        "status": "success",
        "total": len(filas),
        "metricas": {
            "total_general": len(filas),
            "hoy": total_hoy,
            "ayer": total_ayer,
            "dias_activos": len(registros_por_dia)
        },
        "resumen_dias": resumen_dias,
        "registros_por_dia": registros_por_dia,
        "fecha_actual": hoy_str
    }


@router.delete("/api/historial-integrantes/{registro_id}")
def eliminar_registro_integrante(registro_id: int, eliminar_usuario: bool = False):
    """Elimina una entrada del historial de nuevos integrantes, con opción de eliminar también la cuenta del usuario"""
    reg = db.execute_query("SELECT id, usuario_id, nombre, correo, rol FROM historial_nuevos_integrantes WHERE id = ?", (registro_id,), fetchone=True)
    if not reg:
        raise HTTPException(status_code=404, detail="El registro del historial no fue encontrado.")

    db.execute_query("DELETE FROM historial_nuevos_integrantes WHERE id = ?", (registro_id,), commit=True)

    mensaje_extra = ""
    if eliminar_usuario and reg.get("correo"):
        u = db.execute_query("SELECT id, rol FROM usuarios WHERE correo = ?", (reg["correo"],), fetchone=True)
        if u and u["rol"] != "Super Administrador":
            db.execute_query("DELETE FROM progreso_cursos WHERE usuario_id = ?", (u["id"],), commit=True)
            db.execute_query("UPDATE usuarios SET mentor_id = NULL WHERE mentor_id = ?", (u["id"],), commit=True)
            db.execute_query("DELETE FROM usuarios WHERE id = ?", (u["id"],), commit=True)
            mensaje_extra = f" y la cuenta de usuario '{reg['correo']}' fue dada de baja del sistema."

    registrar_movimiento("SuperAdmin", "Historial_Integrantes", "Eliminar_Registro", "EXITO", f"Registro #{registro_id}: {reg['nombre']} ({reg['correo']}){mensaje_extra}")
    return {
        "status": "success",
        "mensaje": f"Registro de {reg['nombre']} eliminado del historial{mensaje_extra} exitosamente."
    }


@router.delete("/api/historial-integrantes/por-dia/{fecha_dia}")
def eliminar_historial_por_dia(fecha_dia: str):
    """Elimina todos los registros del historial pertenecientes a una fecha específica"""
    conteo = db.execute_query("SELECT COUNT(*) as total FROM historial_nuevos_integrantes WHERE fecha_dia = ?", (fecha_dia,), fetchone=True)
    total = conteo["total"] if conteo else 0

    if total == 0:
        return {"status": "success", "mensaje": f"No hay registros del historial en el día {fecha_dia}."}

    db.execute_query("DELETE FROM historial_nuevos_integrantes WHERE fecha_dia = ?", (fecha_dia,), commit=True)
    registrar_movimiento("SuperAdmin", "Historial_Integrantes", "Limpiar_Dia", "EXITO", f"Se eliminaron {total} registros del día {fecha_dia}")
    return {
        "status": "success",
        "mensaje": f"Se eliminaron los {total} registros del historial correspondientes al día {fecha_dia}."
    }


@router.delete("/api/historial-integrantes/limpiar-todo")
def vaciar_historial_integrantes():
    """Elimina todo el historial acumulado de nuevos integrantes"""
    conteo = db.execute_query("SELECT COUNT(*) as total FROM historial_nuevos_integrantes", fetchone=True)
    total = conteo["total"] if conteo else 0

    db.execute_query("DELETE FROM historial_nuevos_integrantes", commit=True)
    registrar_movimiento("SuperAdmin", "Historial_Integrantes", "Vaciar_Todo", "EXITO", f"Historial vaciado ({total} registros eliminados)")
    return {
        "status": "success",
        "mensaje": f"El historial de nuevos integrantes fue vaciado por completo ({total} registros eliminados)."
    }


@router.post("/api/historial-integrantes/eliminar-lote")
@router.delete("/api/historial-integrantes/eliminar-lote")
def eliminar_lote_historial_integrantes(datos: EliminarLoteReq):
    """Elimina una selección múltiple de registros del historial cronológico estilo Google History"""
    if not datos.ids:
        return {"status": "success", "mensaje": "No se enviaron registros para eliminar.", "eliminados": 0}

    placeholders = ",".join("?" for _ in datos.ids)
    conteo_usuarios_baja = 0

    if datos.eliminar_usuarios:
        correos_registros = db.execute_query(f"SELECT correo FROM historial_nuevos_integrantes WHERE id IN ({placeholders})", tuple(datos.ids), fetchall=True) or []
        for reg in correos_registros:
            c = reg.get("correo")
            if c:
                u = db.execute_query("SELECT id, rol FROM usuarios WHERE correo = ?", (c,), fetchone=True)
                if u and u["rol"] != "Super Administrador":
                    db.execute_query("DELETE FROM progreso_cursos WHERE usuario_id = ?", (u["id"],), commit=True)
                    db.execute_query("UPDATE usuarios SET mentor_id = NULL WHERE mentor_id = ?", (u["id"],), commit=True)
                    db.execute_query("DELETE FROM usuarios WHERE id = ?", (u["id"],), commit=True)
                    conteo_usuarios_baja += 1

    db.execute_query(f"DELETE FROM historial_nuevos_integrantes WHERE id IN ({placeholders})", tuple(datos.ids), commit=True)

    msg = f"Se eliminaron {len(datos.ids)} registros del historial"
    if conteo_usuarios_baja > 0:
        msg += f" y se dieron de baja {conteo_usuarios_baja} cuentas de usuario"
    msg += " exitosamente."

    registrar_movimiento("SuperAdmin", "Historial_Integrantes", "Eliminar_Lote", "EXITO", msg)
    return {"status": "success", "mensaje": msg, "eliminados": len(datos.ids)}

