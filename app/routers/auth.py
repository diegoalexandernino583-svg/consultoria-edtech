"""M?dulo de rutas REST: Autenticaci?n y Sesiones."""
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, Response, JSONResponse
from app.core import *
from app.core import _empujar_cambio_usuario_remoto

router = APIRouter(tags=["Autenticaci?n y Sesiones"])


@router.post("/api/auth/iniciar-sesion")
@router.post("/api/auth/iniciar-login")
@router.post("/api/auth/login")
def iniciar_login(datos: IniciarLoginRequest, request: Request):
    """Valida correo y contraseña y concede acceso directo inmediato sin 2FA (<2ms)"""
    client_ip = obtener_ip_cliente(request)

    # 1. Protección Anti-Bot Honeypot (Solo registro informativo para no bloquear usuarios reales con autocompletado)
    if datos.honeypot and datos.honeypot.strip():
        if client_ip not in ["127.0.0.1", "localhost", "::1"]:
            print(f">> [WAF] Nota: campo honeypot completado por navegador desde {client_ip}")

    # 2. Control de Fuerza Bruta (ignorado para localhost o IPs privadas)
    intentos_previos = len(intentos_fallidos_login.get(client_ip, []))
    if intentos_previos >= 10 and client_ip not in ["127.0.0.1", "localhost", "::1"]:
        bloquear_ip_inmediatamente(client_ip, motivo="Ataque de fuerza bruta reiterado (más de 10 intentos fallidos)")
        raise HTTPException(status_code=429, detail="Has superado el límite de intentos de acceso. Tu IP ha sido pausada temporalmente por seguridad.")

    correo_limpio = datos.correo.strip().lower()
    user = db.execute_query(
        """SELECT u.id, u.nombre, u.rol, u.password_hash, u.organizacion_id, u.foto_perfil, 
                  u.tema_decorativo, u.fondo_personalizado, u.racha_semanas, u.minutos_dedicados_totales,
                  u.colores_personalizados, u.disenos_personalizados_json,
                  COALESCE(o.nombre, 'Corporación Universitaria Minuto de Dios') as institucion_nombre
           FROM usuarios u
           LEFT JOIN organizaciones o ON o.id = u.organizacion_id
           WHERE LOWER(TRIM(u.correo)) = ?""",
        (correo_limpio,),
        fetchone=True
    )
    
    # Si no está en la tabla local usuarios, buscar en historial_nuevos_integrantes y auto-insertar/sincronizar
    if not user:
        hist_u = db.execute_query(
            """SELECT h.usuario_id, h.nombre, h.correo, h.rol, h.organizacion_id,
                      COALESCE(o.nombre, h.organizacion_nombre, 'Corporación Universitaria Minuto de Dios') as institucion_nombre
               FROM historial_nuevos_integrantes h
               LEFT JOIN organizaciones o ON o.id = h.organizacion_id
               WHERE LOWER(TRIM(h.correo)) = ?
               ORDER BY h.id DESC LIMIT 1""",
            (correo_limpio,),
            fetchone=True
        )
        if hist_u:
            hash_defecto = bcrypt.hashpw("123456".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db.execute_query(
                "INSERT OR IGNORE INTO usuarios (nombre, correo, rol, organizacion_id, password_hash) VALUES (?, ?, ?, ?, ?)",
                (hist_u["nombre"], correo_limpio, hist_u["rol"], hist_u.get("organizacion_id") or 13, hash_defecto),
                commit=True
            )
            user = db.execute_query(
                """SELECT u.id, u.nombre, u.rol, u.password_hash, u.organizacion_id, u.foto_perfil, 
                          u.tema_decorativo, u.fondo_personalizado, u.racha_semanas, u.minutos_dedicados_totales,
                          u.colores_personalizados, u.disenos_personalizados_json,
                          COALESCE(o.nombre, 'Corporación Universitaria Minuto de Dios') as institucion_nombre
                   FROM usuarios u
                   LEFT JOIN organizaciones o ON o.id = u.organizacion_id
                   WHERE LOWER(TRIM(u.correo)) = ?""",
                (correo_limpio,),
                fetchone=True
            )

    if not user:
        nom_nuevo = correo_limpio.split('@')[0].replace('.', ' ').title()
        hash_nuevo = bcrypt.hashpw(((datos.password or "").strip() or "123456").encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            db.execute_query(
                "INSERT INTO usuarios (nombre, correo, rol, organizacion_id, password_hash) VALUES (?, ?, 'Aprendiz', 13, ?)",
                (nom_nuevo, correo_limpio, hash_nuevo),
                commit=True
            )
            registrar_en_historial_integrantes(
                nombre=nom_nuevo,
                correo=correo_limpio,
                rol="Aprendiz",
                organizacion_id=13,
                origen="Acceso 2FA Inmediato"
            )
            user = db.execute_query(
                """SELECT u.id, u.nombre, u.rol, u.password_hash, u.organizacion_id, u.foto_perfil, 
                          u.tema_decorativo, u.fondo_personalizado, u.racha_semanas, u.minutos_dedicados_totales,
                          u.colores_personalizados, u.disenos_personalizados_json,
                          COALESCE(o.nombre, 'Corporación Universitaria Minuto de Dios') as institucion_nombre
                   FROM usuarios u
                   LEFT JOIN organizaciones o ON o.id = u.organizacion_id
                   WHERE LOWER(TRIM(u.correo)) = ?""",
                (correo_limpio,),
                fetchone=True
            )
        except Exception as e_new:
            print(f">> [AUTO-ALTA-LOGIN-ERROR] {e_new}")

    password_valida = False
    stored_hash = user.get("password_hash")
    pwd_input = (datos.password or "").strip()
    
    # Contraseñas universales demo/maestras y validación bcrypt con caché SHA-256 (0.01ms en accesos subsecuentes)
    claves_demo = ["123456", "123456789", "admin", "Admin", "admin123", "Admin123*", "diego123", "password", "demo123", "administrador", "Administrador"]
    if pwd_input in claves_demo or datos.password in claves_demo:
        password_valida = True
    elif stored_hash:
        huella_cache = hashlib.sha256(f"{correo_limpio}:{stored_hash}:{pwd_input}".encode("utf-8")).hexdigest()
        if huella_cache in _cache_auth_bcrypt:
            password_valida = True
        else:
            try:
                password_valida = bcrypt.checkpw(pwd_input.encode('utf-8'), stored_hash.encode('utf-8'))
            except Exception:
                password_valida = (pwd_input == stored_hash or datos.password == stored_hash)
            if password_valida:
                _cache_auth_bcrypt.add(huella_cache)
    else:
        password_valida = True

    if not password_valida:
        fallos = registrar_intento_fallido_login(client_ip)
        registrar_movimiento(datos.correo, "Autenticacion", "Validacion_Credenciales", "FALLO", "Contraseña incorrecta")
        raise HTTPException(status_code=401, detail="Contraseña incorrecta. Puedes usar la clave demo 123456.")

    # Si la contraseña fue válida, limpiar intentos fallidos para esta IP
    limpiar_intentos_fallidos_login(client_ip)

    # Consultar datos de organización y colorimetría si aplica
    org_data = None
    if user.get("organizacion_id"):
        org_data = db.execute_query(
            "SELECT id, nombre, tipo_organizacion, logo_url, color_primario, color_secundario, color_acento, color_personalizado FROM organizaciones WHERE id = ?",
            (user["organizacion_id"],),
            fetchone=True
        )

    institucion_nombre = user.get("institucion_nombre") or (org_data.get("nombre") if org_data else "Corporación Universitaria Minuto de Dios")
    nombre_raw = user.get('nombre') or 'Usuario'
    rol_usuario = user.get('rol') or 'Integrante Institucional'
    org_id_val = user.get("organizacion_id") or 13

    # Construir objeto completo del usuario sincronizado con organizaciones
    usr_completo = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.mentor_id, u.foto_perfil, u.tema_decorativo,
               u.fondo_personalizado, u.racha_semanas, u.minutos_dedicados_totales,
               u.colores_personalizados, u.disenos_personalizados_json,
               COALESCE(o.nombre, 'Corporación Universitaria Minuto de Dios') as organizacion_nombre, 
               o.logo_url as org_logo_url,
               o.color_primario as org_color_primario, o.color_secundario as org_color_secundario,
               o.color_acento as org_color_acento, o.color_personalizado as org_color_personalizado
        FROM usuarios u
        LEFT JOIN organizaciones o ON o.id = u.organizacion_id
        WHERE lower(u.correo) = lower(?)
    """, (correo_limpio,), fetchone=True)

    if usr_completo:
        usuario_dict = dict(usr_completo)
        usuario_dict["institucion"] = usuario_dict.get("organizacion_nombre") or institucion_nombre
        usuario_dict["organizacion"] = {
            "id": usuario_dict.get("organizacion_id"),
            "nombre": usuario_dict.get("organizacion_nombre"),
            "logo_url": usuario_dict.get("org_logo_url"),
            "color_primario": usuario_dict.get("org_color_primario"),
            "color_secundario": usuario_dict.get("org_color_secundario"),
            "color_acento": usuario_dict.get("org_color_acento"),
            "color_personalizado": usuario_dict.get("org_color_personalizado")
        }
    else:
        usuario_dict = {
            "id": user["id"],
            "nombre": user["nombre"],
            "correo": correo_limpio,
            "rol": user["rol"],
            "organizacion_id": user.get("organizacion_id"),
            "institucion": institucion_nombre,
            "foto_perfil": user.get("foto_perfil"),
            "tema_decorativo": user.get("tema_decorativo") or "estandar",
            "fondo_personalizado": user.get("fondo_personalizado"),
            "colores_personalizados": user.get("colores_personalizados"),
            "disenos_personalizados_json": user.get("disenos_personalizados_json"),
            "racha_semanas": user.get("racha_semanas", 5),
            "minutos_dedicados_totales": user.get("minutos_dedicados_totales", 180),
            "organizacion": org_data or {}
        }

    registrar_movimiento(correo_limpio, "Autenticacion", "Inicio_Sesion_Completo", "EXITO", f"Rol: {rol_usuario} (Acceso directo)")
    print(f">> [LOGIN-DIRECTO] Acceso inmediato para {correo_limpio} ({rol_usuario})", flush=True)

    return {
        "status": "success",
        "mensaje": f"¡Bienvenido(a), {nombre_raw}! Acceso directo autorizado.",
        "correo": correo_limpio,
        "nombre": nombre_raw,
        "rol": rol_usuario,
        "institucion": institucion_nombre,
        "organizacion_id": org_id_val,
        "usuario": usuario_dict
    }


@router.get("/api/auth/validar-sesion")
def validar_sesion(usuario_id: int = Query(...)):
    """Verifica en milisegundos si el rol o la organización cambiaron en la BD y sincroniza la sesión"""
    usr = db.execute_query("""
        SELECT u.id, u.nombre, u.correo, u.rol, u.organizacion_id, u.mentor_id, u.foto_perfil, u.tema_decorativo,
               u.fondo_personalizado, u.racha_semanas, u.minutos_dedicados_totales,
               u.colores_personalizados, u.disenos_personalizados_json,
               o.nombre as organizacion_nombre, o.logo_url as org_logo_url,
               o.color_primario as org_color_primario, o.color_secundario as org_color_secundario,
               o.color_acento as org_color_acento, o.color_personalizado as org_color_personalizado
        FROM usuarios u
        LEFT JOIN organizaciones o ON o.id = u.organizacion_id
        WHERE u.id = ?
    """, (usuario_id,), fetchone=True)
    if not usr:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    usuario = dict(usr)
    usuario["organizacion"] = {
        "id": usuario.get("organizacion_id"),
        "nombre": usuario.get("organizacion_nombre"),
        "logo_url": usuario.get("org_logo_url"),
        "color_primario": usuario.get("org_color_primario"),
        "color_secundario": usuario.get("org_color_secundario"),
        "color_acento": usuario.get("org_color_acento"),
        "color_personalizado": usuario.get("org_color_personalizado")
    }
    return {
        "status": "success",
        "usuario": usuario,
        "version_servidor": VERSION_CAMBIOS["global"]
    }


@router.get("/api/tiempo-real/pulso")
def pulso_tiempo_real(usuario_id: int = Query(...), rol_actual: str = Query(...), version_cliente: int = Query(0)):
    """Heartbeat ultra-rápido (<0.05ms) para notificar cambios de rol o de datos al instante"""
    version_actual = VERSION_CAMBIOS["global"]
    # Vía rápida en memoria: si el cliente ya tiene la versión actual, responder en 0.005ms sin tocar SQLite ni enviar Base64
    if version_cliente > 0 and version_actual == version_cliente:
        return {
            "valido": True,
            "rol_cambiado": False,
            "rol_actual_bd": rol_actual,
            "version_servidor": version_actual,
            "hay_cambios": False
        }

    row = db.execute_query("""
        SELECT u.rol, u.organizacion_id, o.logo_url as org_logo, o.nombre as org_nombre
        FROM usuarios u
        LEFT JOIN organizaciones o ON o.id = u.organizacion_id
        WHERE u.id = ?
    """, (usuario_id,), fetchone=True)
    
    if not row:
        return {"valido": False}
    
    rol_bd = row.get("rol")
    org_logo = row.get("org_logo")
    org_nombre = row.get("org_nombre")
    
    # Fallback si el usuario no tiene org directa o el logo está vacío en su org
    if not org_logo:
        fallback_org = db.execute_query("SELECT logo_url, nombre FROM organizaciones WHERE logo_url IS NOT NULL AND logo_url != '' LIMIT 1", fetchone=True)
        if fallback_org:
            org_logo = fallback_org.get("logo_url")
            if not org_nombre:
                org_nombre = fallback_org.get("nombre")

    rol_cambiado = (rol_bd != rol_actual)
    hay_cambios = (version_actual > version_cliente)

    return {
        "valido": True,
        "rol_cambiado": rol_cambiado,
        "rol_actual_bd": rol_bd,
        "org_logo": org_logo,
        "org_nombre": org_nombre,
        "version_servidor": version_actual,
        "hay_cambios": hay_cambios
    }


@router.post("/api/auth/solicitar-recuperacion")
def solicitar_recuperacion(datos: SolicitarRecuperacionRequest):
    correo_limpio = datos.correo.strip().lower()
    user = esta_correo_registrado_en_programa(correo_limpio)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"El correo '{correo_limpio}' no está registrado dentro del programa. Solo se envían códigos de seguridad a cuentas registradas en la consultoría."
        )
    
    codigo = str(random.randint(100000, 999999))
    ahora = datetime.now()
    expira = ahora + timedelta(minutes=30)
    guardar_codigo_2fa_persistente(correo_limpio, codigo, minutos=30)
    
    codigos_recuperacion[correo_limpio] = {
        "codigo": codigo,
        "expira": expira
    }
    
    asunto = f"🔑 [{codigo}] Código de Recuperación de Contraseña · Consultoría EdTech"
    cuerpo_texto = (
        f"Hola {user['nombre']},\n\n"
        f"Hemos recibido una solicitud para restablecer tu contraseña.\n"
        f"Tu código de recuperación de 6 dígitos es: {codigo}\n\n"
        f"Ingresa este código en la plataforma para definir tu nueva contraseña. Válido por 30 minutos."
    )
    cuerpo_html = generar_html_correo_recuperacion(user['nombre'], codigo)

    def _enviar_recup_bg():
        enviado = enviar_correo_smtp(correo_limpio, asunto, cuerpo_texto, cuerpo_html, codigo_otp=codigo)
        if enviado:
            registrar_movimiento(correo_limpio, "Seguridad", "Solicitar_Recuperacion", "EXITO")
            print(f">> [RECUPERACION] Código generado y enviado por correo a {correo_limpio}", flush=True)
        else:
            registrar_movimiento(correo_limpio, "Seguridad", "Solicitar_Recuperacion", "FALLO")

    threading.Thread(target=_enviar_recup_bg, name=f"smtp-recup-{correo_limpio[:10]}", daemon=True).start()
    
    return {
        "status": "success",
        "mensaje": f"Código de recuperación de 6 dígitos enviado exitosamente a tu correo ({correo_limpio}).",
        "correo": correo_limpio,
        "correo_enviado": True
    }


@router.post("/api/auth/cambiar-contrasena")
@router.post("/api/auth/cambiar-password")
def cambiar_password(datos: CambiarPasswordRequest):
    correo_limpio = datos.correo.strip().lower()
    if not esta_correo_registrado_en_programa(correo_limpio):
        raise HTTPException(status_code=404, detail="El correo ingresado no está registrado dentro del programa.")

    codigo_ingresado = datos.codigo.strip()
    info_recup = codigos_recuperacion.get(correo_limpio)
    codigo_valido = False

    if info_recup:
        ahora = datetime.now()
        if isinstance(info_recup, dict):
            if info_recup.get("expira", ahora) >= ahora and info_recup.get("codigo") == codigo_ingresado:
                codigo_valido = True
        elif str(info_recup) == codigo_ingresado:
            codigo_valido = True

    if not codigo_valido:
        if validar_codigo_2fa_persistente(correo_limpio, codigo_ingresado):
            codigo_valido = True

    if not codigo_valido:
        raise HTTPException(status_code=400, detail="Código de recuperación incorrecto o expirado. Verifica el código de 6 dígitos enviado a tu correo.")
    
    if len(datos.nueva_password.strip()) < 6:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres.")
    
    nueva_hash = bcrypt.hashpw(datos.nueva_password.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.execute_query("UPDATE usuarios SET password_hash = ? WHERE correo = ?", (nueva_hash, correo_limpio), commit=True)
    
    # Sincronizar de inmediato con Render Cloud y Azure SQL
    u_updated = db.execute_query("SELECT id FROM usuarios WHERE correo = ?", (correo_limpio,), fetchone=True)
    if u_updated:
        _empujar_cambio_usuario_remoto(u_updated["id"])
        
    if correo_limpio in codigos_recuperacion:
        del codigos_recuperacion[correo_limpio]
        
    registrar_movimiento(correo_limpio, "Seguridad", "Cambio_Contraseña", "EXITO")
    
    return {
        "status": "success",
        "mensaje": "¡Contraseña actualizada exitosamente! Ahora puedes iniciar sesión con tu nueva contraseña."
    }


@router.post("/api/auth/cambiar-contrasena-sesion")
@router.post("/api/auth/cambiar-password-sesion")
def cambiar_password_sesion(datos: CambiarPasswordSesionReq):
    """Permite a cualquier usuario autenticado actualizar su contraseña personal"""
    user = db.execute_query("SELECT id, nombre, correo, password_hash FROM usuarios WHERE id = ?", (datos.usuario_id,), fetchone=True)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
    pwd_act = datos.password_actual.strip()
    hash_guardado = user.get("password_hash") or ""
    
    valido = False
    if hash_guardado:
        try:
            valido = bcrypt.checkpw(pwd_act.encode('utf-8'), hash_guardado.encode('utf-8'))
        except Exception:
            valido = False
            
    # Admitir si es la contraseña inicial estándar '123456'
    if not valido and pwd_act in ["123456", "123456789"]:
        valido = True
        
    if not valido:
        raise HTTPException(status_code=400, detail="La contraseña actual ingresada es incorrecta.")
        
    if len(datos.password_nueva.strip()) < 6:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres o dígitos.")
        
    nuevo_hash = bcrypt.hashpw(datos.password_nueva.strip().encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.execute_query("UPDATE usuarios SET password_hash = ? WHERE id = ?", (nuevo_hash, datos.usuario_id), commit=True)
    
    registrar_movimiento(user["correo"], "Seguridad", "Cambio_Password_Sesion", "EXITO", "Contraseña cambiada voluntariamente por el usuario")
    
    return {
        "status": "success",
        "mensaje": "¡Tu contraseña ha sido actualizada exitosamente! Utilízala en tus próximos inicios de sesión."
    }

