// =====================================================================
// CLIENTE JAVASCRIPT - CENTRO DE COMANDO EDTECH v2.0
// GOBERNANZA MULTI-ROL, JERARQUÍAS, EDICIÓN, CHART.JS & RED LOCAL
// =====================================================================

const API_BASE = (window.location.protocol === 'file:') ? 'http://localhost:8080' : '';

let currentUser = null;
let current2FAEmail = null;
let currentContingencyCode = '123456';
let allAuditLogs = [];
let allOrganizations = [];
let allHierarchyData = { administradores: [], mentores: [], aprendices: [] };
let nodoAEliminar = { id: null, nombre: '' };
let usuarioAEliminar = { id: null, nombre: '', correo: '' };
let networkUrl = '';
// Instancias de Chart.js
let chartDonaInstance = null;
let chartBarrasInstance = null;
let chartOrgColeccionesInstance = null;
let chartOrgModulosInstance = null;
let todasAsignacionesColecciones = [];
let analiticaOrgActual = null;
let analiticaEstudiantesActuales = [];
let catalogoColeccionesActuales = [];

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
  refrescarIconos();
  
  // Cargar modo visual guardado (predeterminado, oscuro, claro, artístico)
  const temaGuardado = localStorage.getItem('edtech_tema_visual') || 'predeterminado';
  seleccionarTemaVisual(temaGuardado);

  comprobarSesionExistente();
  verificarEstadoServidor();
  if (!currentUser) {
    cargarOrganizacionesRegistro();
  }

  // Escuchar cambio de rol en el modal de edición de usuario
  const selectRol = document.getElementById('edit-user-rol');
  if (selectRol) {
    selectRol.addEventListener('change', (e) => {
      const contMentor = document.getElementById('container-edit-mentor');
      if (contMentor) {
        contMentor.style.display = (e.target.value === 'Aprendiz') ? 'block' : 'none';
      }
    });
  }
});

let _rafIconosPendiente = false;
function refrescarIconos() {
  if (_rafIconosPendiente) return;
  _rafIconosPendiente = true;
  requestAnimationFrame(() => {
    _rafIconosPendiente = false;
    if (window.lucide) {
      lucide.createIcons();
    }
  });
}

// =====================================================================
// 1. GESTIÓN DE SESIÓN & TIEMPO REAL ULTRA-RÁPIDO (<1MS)
// =====================================================================
let intervaloPulsoTiempoReal = null;
let versionDatosServidor = 0;

function comprobarSesionExistente() {
  const guardada = localStorage.getItem('edtech_usuario') || sessionStorage.getItem('edtech_usuario');
  if (guardada) {
    try {
      currentUser = JSON.parse(guardada);
      mostrarDashboardPrincipal();
      // Validar inmediatamente con la BD si el rol fue cambiado por un administrador
      validarSesionConServidor();
    } catch (e) {
      console.error("Error al restaurar sesión:", e);
      localStorage.removeItem('edtech_usuario');
      sessionStorage.removeItem('edtech_usuario');
      mostrarPantallaLogin();
    }
  } else {
    mostrarPantallaLogin();
  }
}

async function validarSesionConServidor() {
  if (!currentUser || !currentUser.id) return;
  try {
    const res = await fetch(`${API_BASE}/api/auth/validar-sesion?usuario_id=${currentUser.id}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === 'success' && data.usuario) {
      const rolAnterior = currentUser.rol;
      const nuevoRol = data.usuario.rol;

      currentUser = { ...currentUser, ...data.usuario };
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      versionDatosServidor = data.version_servidor || 0;

      if (rolAnterior !== nuevoRol) {
        mostrarToast(`⚡ Tu perfil ha sido actualizado a ${nuevoRol}.`, 'info');
        configurarVistasSegunRol();
        actualizarPerfilSidebar();
      } else {
        actualizarBrandingOrganizacionUI();
      }
    }
  } catch (e) {
    console.debug('Aviso validación sesión:', e);
  }
}

function iniciarPulsoTiempoReal() {
  if (intervaloPulsoTiempoReal) clearInterval(intervaloPulsoTiempoReal);
  // Latido en tiempo real cada 2 segundos para sincronización fluida con cero sobrecarga
  intervaloPulsoTiempoReal = setInterval(verificarPulsoTiempoReal, 2000);
}

let isRefrescandoTiempoReal = false;
let _pulsoEnVuelo = false;

async function refrescarDatosEnTiempoReal() {
  if (isRefrescandoTiempoReal) return;
  isRefrescandoTiempoReal = true;
  try {
    // 1. Refrescar listado de organizaciones y branding institucional
    const resOrg = await fetch(`${API_BASE}/api/organizaciones/listar`);
    if (resOrg.ok) {
      const jsonOrg = await resOrg.json();
      allOrganizations = jsonOrg.data || [];
      const labelConteo = document.getElementById('label-nodos-conteo');
      if (labelConteo) {
        labelConteo.innerText = `${allOrganizations.length} institución(es) · haz clic para ver el detalle`;
      }
      actualizarBrandingOrganizacionUI();
    }

    // 2. Refrescar la vista actualmente activa en segundo plano
    const todasVistas = ['nodos', 'admin-convenio', 'directorio', 'aprendiz', 'mentor-clase', 'metricas', 'catalogo', 'celador', 'configuraciones'];
    const vistaActiva = todasVistas.find(v => {
      const el = document.getElementById(`vista-${v}`);
      return el && !el.classList.contains('hidden');
    });

    if (vistaActiva === 'directorio') {
      if (typeof cargarJerarquia3Columnas === 'function') await cargarJerarquia3Columnas();
    } else if (vistaActiva === 'nodos') {
      if (typeof cargarNodosInstitucionales === 'function') await cargarNodosInstitucionales();
    } else if (vistaActiva === 'admin-convenio') {
      if (typeof cargarVistaAdminConvenio === 'function') await cargarVistaAdminConvenio();
      if (typeof cargarMentoresRendimientoAdmin === 'function') await cargarMentoresRendimientoAdmin();
    } else if (vistaActiva === 'mentor-clase') {
      if (typeof cargarClasesMentor === 'function') await cargarClasesMentor();
    } else if (vistaActiva === 'aprendiz') {
      if (typeof cargarCursosAprendiz === 'function') await cargarCursosAprendiz();
    } else if (vistaActiva === 'catalogo') {
      if (typeof cargarCatalogoContenidos === 'function') await cargarCatalogoContenidos();
    } else if (vistaActiva === 'metricas') {
      if (typeof cargarMetricasYGraficas === 'function') await cargarMetricasYGraficas();
    } else if (vistaActiva === 'celador') {
      if (typeof cargarLogsCelador === 'function') await cargarLogsCelador();
    }
  } catch (err) {
    console.debug('Aviso refresco tiempo real:', err);
  } finally {
    isRefrescandoTiempoReal = false;
  }
}

async function verificarPulsoTiempoReal() {
  if (!currentUser || !currentUser.id || document.hidden || _pulsoEnVuelo) return;
  _pulsoEnVuelo = true;
  try {
    const res = await fetch(`${API_BASE}/api/tiempo-real/pulso?usuario_id=${currentUser.id}&rol_actual=${encodeURIComponent(currentUser.rol)}&version_cliente=${versionDatosServidor}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.valido) return;

    // 1. Detección de cambio de rol en tiempo real (milisegundos)
    if (data.rol_cambiado && data.rol_actual_bd) {
      const nuevoRol = data.rol_actual_bd;
      currentUser.rol = nuevoRol;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));

      mostrarToast(`🚀 ¡Rol actualizado en tiempo real! Ahora tienes acceso como ${nuevoRol}.`, 'exito');
      configurarVistasSegunRol(true);
      actualizarPerfilSidebar();
      actualizarBrandingOrganizacionUI();

      if (nuevoRol === 'Mentor') {
        if (typeof cargarClasesMentor === 'function') cargarClasesMentor();
      } else if (nuevoRol === 'Aprendiz' || nuevoRol === 'Estudiante') {
        if (typeof cargarCursosAprendiz === 'function') cargarCursosAprendiz();
      } else if (nuevoRol === 'Administrador') {
        if (typeof cargarVistaAdminConvenio === 'function') cargarVistaAdminConvenio();
      } else if (nuevoRol === 'Super Administrador') {
        if (typeof cargarNodosInstitucionales === 'function') cargarNodosInstitucionales();
      }
    }

    // 2. Propagación en tiempo real del logo institucional para todos los roles
    if (data.org_logo !== undefined) {
      if (!currentUser.organizacion) currentUser.organizacion = {};
      if (currentUser.organizacion.logo_url !== data.org_logo || (data.org_nombre && currentUser.organizacion.nombre !== data.org_nombre)) {
        currentUser.organizacion.logo_url = data.org_logo;
        currentUser.org_logo_url = data.org_logo;
        if (data.org_nombre) {
          currentUser.organizacion.nombre = data.org_nombre;
          currentUser.organizacion_nombre = data.org_nombre;
        }
        localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
        actualizarBrandingOrganizacionUI();
      }
    }

    // 3. Notificación de cambios globales de la base de datos (usuarios, roles, instituciones, etc.)
    if (data.hay_cambios) {
      versionDatosServidor = data.version_servidor || (versionDatosServidor + 1);
      refrescarDatosEnTiempoReal();
    } else if (data.version_servidor) {
      versionDatosServidor = data.version_servidor;
    }
  } catch (e) {
    // Latido silencioso
  } finally {
    _pulsoEnVuelo = false;
  }
}

function mostrarPantallaLogin() {
  if (intervaloPulsoTiempoReal) clearInterval(intervaloPulsoTiempoReal);
  const pantallaAuth = document.getElementById('pantalla-auth-fullscreen');
  const appLayout = document.getElementById('app-layout');

  if (pantallaAuth) pantallaAuth.classList.remove('hidden');
  if (appLayout) appLayout.classList.add('hidden');
  cancelar2FA();
  if (typeof cambiarPestanaAuth === 'function') {
    cambiarPestanaAuth('login');
  }
  cargarOrganizacionesRegistro();
  refrescarIconos();
}

function mostrarDashboardPrincipal() {
  const pantallaAuth = document.getElementById('pantalla-auth-fullscreen');
  const appLayout = document.getElementById('app-layout');

  if (pantallaAuth) pantallaAuth.classList.add('hidden');
  if (appLayout) appLayout.classList.remove('hidden');

  if (currentUser) {
    if (typeof currentUser.colores_personalizados === 'string') {
      try { currentUser.colores_personalizados = JSON.parse(currentUser.colores_personalizados); } catch (e) {}
    }
    if (typeof currentUser.disenos_personalizados_json === 'string') {
      try { currentUser.disenos_personalizados = JSON.parse(currentUser.disenos_personalizados_json); } catch (e) {}
    }
    if (typeof aplicarEstilosTemaWeb === 'function') {
      aplicarEstilosTemaWeb(currentUser.tema_decorativo || 'estandar', currentUser.fondo_personalizado);
    }
  }

  actualizarPerfilSidebar();
  actualizarBrandingOrganizacionUI();
  configurarVistasSegunRol(true);
  actualizarVisibilidadTemasSegunRol();
  iniciarPulsoTiempoReal();
  actualizarEstiloModoDominio('modo-dominio-excel');
  actualizarEstiloModoDominio('modo-dominio-convenio');
  refrescarIconos();
}

function cargarOrganizaciones() {
  cargarNodosInstitucionales();
}

function cerrarSesion() {
  currentUser = null;
  localStorage.removeItem('edtech_usuario');
  sessionStorage.removeItem('edtech_usuario');
  mostrarToast('Has cerrado la sesión de forma segura.', 'info');
  mostrarPantallaLogin();
}

function obtenerIniciales(nombre) {
  if (!nombre) return 'ED';
  const partes = String(nombre).trim().split(' ').filter(Boolean);
  if (partes.length >= 2) return (partes[0][0] + partes[1][0]).toUpperCase();
  return String(nombre).trim().substring(0, 2).toUpperCase();
}

function actualizarPerfilSidebar() {
  if (!currentUser) return;

  const avatar = document.getElementById('sidebar-avatar');
  const title = document.getElementById('sidebar-user-title');
  const role = document.getElementById('sidebar-user-role');
  const topPill = document.getElementById('top-user-pill');
  const topAvatarContainer = document.getElementById('top-user-avatar-container');
  const topNameText = document.getElementById('top-user-name-text');

  const partes = currentUser.nombre.split(' ');
  const iniciales = partes.length >= 2 ? (partes[0][0] + partes[1][0]).toUpperCase() : currentUser.nombre.substring(0, 2).toUpperCase();

  if (avatar) {
    if (currentUser.foto_perfil) {
      avatar.innerHTML = `<img src="${currentUser.foto_perfil}" class="w-full h-full object-cover rounded-full">`;
    } else {
      avatar.innerText = iniciales;
    }
  }

  if (topAvatarContainer) {
    if (currentUser.foto_perfil) {
      topAvatarContainer.innerHTML = `<img src="${currentUser.foto_perfil}" class="w-full h-full object-cover rounded-full">`;
    } else {
      topAvatarContainer.innerHTML = `<span id="top-user-avatar-text">${iniciales}</span>`;
    }
  }

  if (topNameText) topNameText.innerText = currentUser.nombre;
  const claveRol = currentUser.rol === 'Super Administrador' ? 'rol_superadmin' : currentUser.rol === 'Mentor' ? 'rol_mentor' : (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante') ? 'rol_aprendiz' : 'rol_admin';
  const rolTexto = t(claveRol, currentUser.rol);
  if (role) role.innerText = rolTexto;

  if (topPill) {
    topPill.innerText = rolTexto;
    topPill.className = 'badge-corp font-bold ' + obtenerClaseBadgeRol(currentUser.rol);
  }

  // Aplicar colores de la organización si los tiene personalizados
  if (currentUser.organizacion) {
    aplicarColoresInstitucion(currentUser.organizacion);
  }
  actualizarBrandingOrganizacionUI();
  if (typeof aplicarEstilosTemaWeb === 'function') {
    aplicarEstilosTemaWeb(currentUser.tema_decorativo || 'estandar', currentUser.fondo_personalizado);
  }
}

// Actualiza el logo y nombre institucional tanto en sidebar como en top-header
function actualizarBrandingOrganizacionUI() {
  if (!currentUser) return;

  const headerBranding = document.getElementById('header-org-branding');
  const headerLogo = document.getElementById('header-org-logo');
  const headerNombre = document.getElementById('header-org-nombre');

  const sidebarBranding = document.getElementById('sidebar-org-branding');
  const sidebarLogo = document.getElementById('sidebar-org-logo');
  const sidebarNombre = document.getElementById('sidebar-org-nombre');
  const sidebarPlaceholder = document.getElementById('sidebar-org-logo-placeholder');

  // Para Administradores institucionales, Mentores y Aprendices, y también para Super Administrador si hay una organización:
  let org = currentUser.organizacion || {};
  let orgNombre = org.nombre || currentUser.organizacion_nombre || '';
  let orgLogo = org.logo_url || currentUser.org_logo_url || '';

  if ((!orgNombre || !orgLogo) && allOrganizations && allOrganizations.length > 0) {
    const orgEncontrada = allOrganizations.find(o => o.id == currentUser.organizacion_id) || allOrganizations[0];
    if (orgEncontrada) {
      if (!orgNombre) orgNombre = orgEncontrada.nombre;
      if (!orgLogo) orgLogo = orgEncontrada.logo_url;
      if (!currentUser.organizacion) currentUser.organizacion = {};
      if (!currentUser.organizacion.nombre) currentUser.organizacion.nombre = orgNombre;
      if (!currentUser.organizacion.logo_url) currentUser.organizacion.logo_url = orgLogo;
    }
  }

  if (orgNombre) {
    if (headerBranding) {
      headerBranding.classList.remove('hidden');
      headerBranding.classList.add('flex');
    }
    if (headerNombre) headerNombre.innerText = orgNombre;

    if (sidebarBranding) {
      sidebarBranding.classList.remove('hidden');
      sidebarBranding.classList.add('flex');
    }
    if (sidebarNombre) sidebarNombre.innerText = orgNombre;

    if (orgLogo) {
      if (headerLogo) {
        headerLogo.src = orgLogo;
        headerLogo.classList.remove('hidden');
      }
      if (sidebarLogo) {
        sidebarLogo.src = orgLogo;
        sidebarLogo.classList.remove('hidden');
      }
      if (sidebarPlaceholder) sidebarPlaceholder.classList.add('hidden');
    } else {
      if (headerLogo) headerLogo.classList.add('hidden');
      if (sidebarLogo) sidebarLogo.classList.add('hidden');
      if (sidebarPlaceholder) sidebarPlaceholder.classList.remove('hidden');
    }
  } else {
    if (headerBranding) headerBranding.classList.add('hidden');
    if (sidebarBranding) sidebarBranding.classList.add('hidden');
  }

  // Previsualización en el panel de configuración de identidad si existe
  const previewIcon = document.getElementById('preview-box-icon');
  const previewTitle = document.getElementById('preview-box-title');
  if (previewTitle && orgNombre) previewTitle.innerText = orgNombre;
  if (previewIcon) {
    if (orgLogo) {
      previewIcon.innerHTML = `<img src="${orgLogo}" class="w-full h-full object-contain p-1 rounded-lg bg-white">`;
    } else {
      previewIcon.innerHTML = `<i data-lucide="building-2" class="w-5 h-5"></i>`;
    }
  }

  // Hacer interactivo el branding en el header y sidebar para administradores
  const esAdminOsuper = currentUser && (currentUser.rol === 'Super Administrador' || currentUser.rol === 'Administrador');
  if (headerBranding) {
    if (esAdminOsuper) {
      headerBranding.style.cursor = 'pointer';
      headerBranding.title = 'Haz clic para cambiar el logotipo institucional';
      headerBranding.onclick = () => {
        const input = document.getElementById('input-logo-org-admin');
        if (input) input.click();
      };
    } else {
      headerBranding.style.cursor = 'default';
      headerBranding.title = '';
      headerBranding.onclick = null;
    }
  }
  if (sidebarBranding) {
    if (esAdminOsuper) {
      sidebarBranding.style.cursor = 'pointer';
      sidebarBranding.title = 'Haz clic para cambiar el logotipo institucional';
      sidebarBranding.onclick = () => {
        const input = document.getElementById('input-logo-org-admin');
        if (input) input.click();
      };
    } else {
      sidebarBranding.style.cursor = 'default';
      sidebarBranding.title = '';
      sidebarBranding.onclick = null;
    }
  }
}

// ---------------------------------------------------------------------
// INTERNACIONALIZACIÓN (SISTEMA MULTI-IDIOMA: ES, EN, PT)
// ---------------------------------------------------------------------
const I18N_DICCIONARIO = {
  es: {
    // Header
    hdr_menu_principal: 'Menú Principal',
    hdr_centro_comando: 'Centro de Comando EdTech',
    hdr_modo: 'Modo',
    hdr_mi_cuenta: 'Mi Cuenta & Ajustes',
    hdr_cerrar_sesion: 'Cerrar Sesión',

    // Sidebar Secciones
    side_sec_entornos: 'Entornos & Institución',
    side_sec_metricas: 'Métricas & Contenidos',
    side_sec_seguridad: 'Seguridad & Ajustes',
    side_sec_formacion: 'Formación & Clases',
    side_sec_mi_formacion: 'Mi Formación',
    side_sec_metricas_cursos: 'Métricas & Cursos',
    side_sec_mi_espacio: 'Mi Espacio & Registro',

    // Sidebar Enlaces
    side_creador_entornos: 'Creador de Entornos',
    side_estructura_equipos: 'Estructura & Equipos',
    side_metricas_graficas: 'Métricas & Gráficas',
    side_catalogo_contenidos: 'Catálogo de Contenidos',
    side_registro_actividad: 'Registro de Actividad',
    side_configuracion_espacio: 'Configuración & Espacio',
    side_mis_clases: 'Mis Clases & Tutorías',
    side_mis_rutas: 'Mis Rutas de Aprendizaje',
    side_mis_metricas: 'Mis Métricas & Gráficas',
    side_catalogo_cursos: 'Catálogo de Cursos',
    side_ocultar_menu: 'Ocultar Menú',
    side_mostrar_menu: 'Mostrar Menú',

    // Roles
    rol_superadmin: 'Super Administrador',
    rol_admin: 'Administrador Institucional',
    rol_mentor: 'Mentor',
    rol_aprendiz: 'Aprendiz',

    // Configuración & Preferencias
    cfg_categoria: 'CENTRO DE AJUSTES & MI CUENTA',
    cfg_titulo: 'Configuración & Preferencias',
    cfg_subtitulo: 'Personalización institucional, datos personales, conectividad, copias de seguridad y papelera.',
    cfg_volver: 'Volver a Centro de Mando',

    // Configuración Tabs
    cfg_tab_perfil: '👤 Mi Perfil & Cuenta',
    cfg_tab_idioma_apariencia: '🌐 Idioma & Apariencia',
    cfg_tab_conectividad: '🌐 Conectividad & Sistema',
    cfg_tab_backups: '💾 Copias de Seguridad',
    cfg_tab_papelera: '♻️ Papelera de Integrantes',
    cfg_tab_powerbi: '📊 Microsoft Power BI',

    // Perfil
    cfg_subir_foto: 'Subir Foto de Perfil',
    cfg_quitar_foto: 'Quitar Foto',
    cfg_info_personal: 'Información Personal de la Cuenta',
    cfg_nombre_completo: 'Nombre Completo',
    cfg_correo: 'Correo Electrónico',
    cfg_cargo: 'Cargo / Rol en Plataforma',
    cfg_institucion: 'Institución / Convenio',
    cfg_act_pwd: 'Actualización Segura de Contraseña',
    cfg_act_pwd_desc: 'Define una contraseña de al menos 6 dígitos. Podrás verificarla con el icono de visualización.',
    cfg_pwd_nueva: 'Nueva Contraseña (mínimo 6 caracteres)',
    cfg_pwd_conf: 'Confirmar Contraseña',
    cfg_btn_act_pwd: 'Actualizar Contraseña',

    // Idioma & Apariencia
    cfg_idioma_titulo: 'Idioma de la Plataforma',
    cfg_idioma_desc: 'Selecciona el idioma oficial para la interfaz y los textos de todo el sistema.',
    cfg_modo_titulo: 'Modo Visual del Sistema',
    cfg_modo_desc: 'Alterna entre el Modo Oscuro y el Modo Claro de acuerdo a tus preferencias de visualización y confort visual.',
    cfg_modo_oscuro_tit: 'Modo Oscuro',
    cfg_modo_oscuro_sub: 'Confort Nocturno OLED',
    cfg_modo_oscuro_desc: 'Superficies en gris profundo OLED, alto contraste visual equilibrado y acentos cian/azul para reducir la fatiga ocular durante sesiones prolongadas.',
    cfg_btn_modo_oscuro: 'Activar Modo Oscuro',
    cfg_modo_claro_tit: 'Modo Claro',
    cfg_modo_claro_sub: 'Claridad Diurna Ejecutiva',
    cfg_modo_claro_desc: 'Superficies blancas inmaculadas, tipografía con óptimo contraste diurno y acabados en azul navy corporativo para máxima nitidez y presentación profesional.',
    cfg_btn_modo_claro: 'Activar Modo Claro',

    // Catálogo de Contenidos
    cat_categoria: 'BIBLIOTECA & COLECCIONES MICROSOFT',
    cat_titulo: 'Catálogo de Contenidos',
    cat_desc: 'Explora las rutas formativas y envía colecciones a cada colegio, empresa o institución con alertas anti-duplicados.',
    cat_btn_enviar: 'Enviar Colección a Organización',
    cat_btn_subir: '+ Subir Nuevo Material',
    cat_explorar_material: 'Explorar Material',
    cat_btn_enviar_org: 'Enviar a Org',
    cat_btn_enviar_org_title: 'Enviar / Asignar esta colección a una institución',
    cat_modulos: 'Módulos',
    cat_para_mentores: 'Para Mentores',
    cat_para_aprendices: 'Para Aprendices',
    cat_global: 'Global',
    cat_institucion: 'Institución',
    cat_acceso_global: 'Acceso Global (Todas)',

    // Vistas principales
    v_nodos_cat: 'ENTORNOS & COMUNIDADES',
    v_nodos_tit: 'Creador de Entornos',
    v_nodos_desc: 'Gestión integral de colegios, empresas aliados, comunidades y asignación de licencias.',
    v_nodos_sub: 'Instituciones y Entornos Activos',
    v_nodos_btn_nuevo: 'Nueva Institución',

    v_dir_cat: 'GESTIÓN ESTRUCTURAL Y ROLES',
    v_dir_tit: 'Estructura & Equipos',
    v_dir_desc: 'Organigrama institucional, distribución de roles de trabajo y carga de personal.',
    v_dir_btn_plantilla: 'Descargar Plantilla Excel (.xlsx)',

    v_met_cat: 'TELEMETRÍA, ANALÍTICA & RENDIMIENTOS',
    v_met_tit: 'Métricas y Desempeño',
    v_met_desc: 'Supervisión integral de progreso, avance por módulos y rendimientos académicos de la institución.',
    v_met_btn_excel: 'Descargar Métricas & Gráficas (.xlsx)',
    v_met_lbl_institucion: 'Institución:',

    v_cat_cat: 'MATERIAL & RUTAS',
    v_cat_tit: 'Catálogo de Capacitaciones & Contenidos',
    v_cat_desc: 'Rutas de aprendizaje oficiales de Microsoft Learn, SENA y programas de certificación.',

    v_cel_cat: 'AUDITORÍA Y TRAZABILIDAD',
    v_cel_tit: 'Registro de Actividad',
    v_cel_desc: 'Control diario de nuevos integrantes y bitácora de auditoría en tiempo real en una sola vista.',

    v_mentor_cat: 'AULA & TUTORÍA',
    v_mentor_tit: 'Mi Clase & Supervisión de Progreso',
    v_mentor_desc: 'Monitorea el avance académico real, tiempo dedicado y rendimiento en quizzes de tus aprendices (Solo Lectura).',

    toast_idioma_cambiado: '✓ Idioma actualizado a Español.'
  },
  en: {
    // Header
    hdr_menu_principal: 'Main Menu',
    hdr_centro_comando: 'EdTech Command Center',
    hdr_modo: 'Mode',
    hdr_mi_cuenta: 'My Account & Settings',
    hdr_cerrar_sesion: 'Log Out',

    // Sidebar Secciones
    side_sec_entornos: 'Environments & Institution',
    side_sec_metricas: 'Metrics & Contents',
    side_sec_seguridad: 'Security & Settings',
    side_sec_formacion: 'Training & Classes',
    side_sec_mi_formacion: 'My Learning',
    side_sec_metricas_cursos: 'Metrics & Courses',
    side_sec_mi_espacio: 'My Space & Records',

    // Sidebar Enlaces
    side_creador_entornos: 'Environment Creator',
    side_estructura_equipos: 'Structure & Teams',
    side_metricas_graficas: 'Metrics & Analytics',
    side_catalogo_contenidos: 'Content Catalog',
    side_registro_actividad: 'Activity Log',
    side_configuracion_espacio: 'Settings & Workspace',
    side_mis_clases: 'My Classes & Tutoring',
    side_mis_rutas: 'My Learning Paths',
    side_mis_metricas: 'My Metrics & Charts',
    side_catalogo_cursos: 'Course Catalog',
    side_ocultar_menu: 'Hide Menu',
    side_mostrar_menu: 'Show Menu',

    // Roles
    rol_superadmin: 'Super Administrator',
    rol_admin: 'Institutional Administrator',
    rol_mentor: 'Mentor',
    rol_aprendiz: 'Apprentice',

    // Configuración & Preferencias
    cfg_categoria: 'SETTINGS & MY ACCOUNT',
    cfg_titulo: 'Settings & Preferences',
    cfg_subtitulo: 'Institutional customization, personal data, connectivity, backups and recycle bin.',
    cfg_volver: 'Back to Command Center',

    // Configuración Tabs
    cfg_tab_perfil: '👤 My Profile & Account',
    cfg_tab_idioma_apariencia: '🌐 Language & Appearance',
    cfg_tab_conectividad: '🌐 Connectivity & System',
    cfg_tab_backups: '💾 System Backups',
    cfg_tab_papelera: '♻️ Member Recycle Bin',
    cfg_tab_powerbi: '📊 Microsoft Power BI',

    // Perfil
    cfg_subir_foto: 'Upload Profile Photo',
    cfg_quitar_foto: 'Remove Photo',
    cfg_info_personal: 'Personal Account Information',
    cfg_nombre_completo: 'Full Name',
    cfg_correo: 'Email Address',
    cfg_cargo: 'Platform Role',
    cfg_institucion: 'Institution / Agreement',
    cfg_act_pwd: 'Secure Password Update',
    cfg_act_pwd_desc: 'Set a password with at least 6 digits. You can verify it with the eye icon.',
    cfg_pwd_nueva: 'New Password (minimum 6 characters)',
    cfg_pwd_conf: 'Confirm Password',
    cfg_btn_act_pwd: 'Update Password',

    // Idioma & Apariencia
    cfg_idioma_titulo: 'Platform Language',
    cfg_idioma_desc: 'Select the official language for the interface and texts across the entire system.',
    cfg_modo_titulo: 'System Visual Mode',
    cfg_modo_desc: 'Switch between Dark Mode and Light Mode according to your visual preferences.',
    cfg_modo_oscuro_tit: 'Dark Mode',
    cfg_modo_oscuro_sub: 'Night OLED Comfort',
    cfg_modo_oscuro_desc: 'OLED deep gray surfaces, balanced high contrast and cyan/blue accents to reduce eye fatigue during long sessions.',
    cfg_btn_modo_oscuro: 'Activate Dark Mode',
    cfg_modo_claro_tit: 'Light Mode',
    cfg_modo_claro_sub: 'Executive Day Clarity',
    cfg_modo_claro_desc: 'Immaculate white surfaces, optimal daylight contrast typography and corporate navy blue accents for maximum clarity.',
    cfg_btn_modo_claro: 'Activate Light Mode',

    // Content Catalog
    cat_categoria: 'MICROSOFT LIBRARY & COLLECTIONS',
    cat_titulo: 'Content Catalog',
    cat_desc: 'Explore learning pathways and send collections to each school, partner company or institution with anti-duplicate alerts.',
    cat_btn_enviar: 'Send Collection to Organization',
    cat_btn_subir: '+ Upload New Material',
    cat_explorar_material: 'Explore Material',
    cat_btn_enviar_org: 'Send to Org',
    cat_btn_enviar_org_title: 'Send / Assign this collection to an institution',
    cat_modulos: 'Modules',
    cat_para_mentores: 'For Mentors',
    cat_para_aprendices: 'For Apprentices',
    cat_global: 'Global',
    cat_institucion: 'Institution',
    cat_acceso_global: 'Global Access (All)',

    // Main views
    v_nodos_cat: 'ENVIRONMENTS & COMMUNITIES',
    v_nodos_tit: 'Environment Creator',
    v_nodos_desc: 'Comprehensive management of schools, partner companies, communities and license allocation.',
    v_nodos_sub: 'Active Institutions & Environments',
    v_nodos_btn_nuevo: 'New Institution',

    v_dir_cat: 'STRUCTURAL MANAGEMENT & ROLES',
    v_dir_tit: 'Organizational Structure & Teams',
    v_dir_desc: 'Institutional chart, job role distribution and staff load.',
    v_dir_btn_plantilla: 'Download Excel Template (.xlsx)',

    v_met_cat: 'TELEMETRY, ANALYTICS & PERFORMANCE',
    v_met_tit: 'Metrics & Performance',
    v_met_desc: 'Comprehensive monitoring of progress, module advancements and academic performance of the institution.',
    v_met_btn_excel: 'Download Metrics & Charts (.xlsx)',
    v_met_lbl_institucion: 'Institution:',

    v_cat_cat: 'TRAINING & PATHS',
    v_cat_tit: 'Training & Content Catalog',
    v_cat_desc: 'Official Microsoft Learn, SENA and certification learning pathways.',

    v_cel_cat: 'AUDIT & TRACEABILITY',
    v_cel_tit: 'Activity Log',
    v_cel_desc: 'Daily monitoring of new members and real-time audit log in a single unified view.',

    v_mentor_cat: 'CLASSROOM & TUTORING',
    v_mentor_tit: 'My Classroom & Progress Supervision',
    v_mentor_desc: 'Monitor real academic progress, study time and quiz performance of your apprentices (Read Only).',

    toast_idioma_cambiado: '✓ Language updated to English.'
  },
  pt: {
    // Header
    hdr_menu_principal: 'Menu Principal',
    hdr_centro_comando: 'Centro de Comando EdTech',
    hdr_modo: 'Modo',
    hdr_mi_cuenta: 'Minha Conta & Ajustes',
    hdr_cerrar_sesion: 'Encerrar Sessão',

    // Sidebar Secciones
    side_sec_entornos: 'Ambientes & Instituição',
    side_sec_metricas: 'Métricas & Conteúdos',
    side_sec_seguridad: 'Segurança & Ajustes',
    side_sec_formacion: 'Formação & Aulas',
    side_sec_mi_formacion: 'Minha Formação',
    side_sec_metricas_cursos: 'Métricas & Cursos',
    side_sec_mi_espacio: 'Meu Espaço & Registro',

    // Sidebar Enlaces
    side_creador_entornos: 'Criador de Ambientes',
    side_estructura_equipos: 'Estrutura & Equipes',
    side_metricas_graficas: 'Métricas & Gráficos',
    side_catalogo_contenidos: 'Catálogo de Conteúdos',
    side_registro_actividad: 'Registro de Atividade',
    side_configuracion_espacio: 'Configurações & Espaço',
    side_mis_clases: 'Minhas Aulas & Tutorias',
    side_mis_rutas: 'Minhas Trilhas de Aprendizagem',
    side_mis_metricas: 'Minhas Métricas & Gráficos',
    side_catalogo_cursos: 'Catálogo de Cursos',
    side_ocultar_menu: 'Ocultar Menu',
    side_mostrar_menu: 'Mostrar Menu',

    // Roles
    rol_superadmin: 'Super Administrador',
    rol_admin: 'Administrador Institucional',
    rol_mentor: 'Mentor',
    rol_aprendiz: 'Aprendiz',

    // Configuración & Preferencias
    cfg_categoria: 'CENTRO DE AJUSTES & MINHA CONTA',
    cfg_titulo: 'Configurações & Preferências',
    cfg_subtitulo: 'Personalização institucional, dados pessoais, conectividade, cópias de segurança e lixeira.',
    cfg_volver: 'Voltar ao Painel',

    // Configuración Tabs
    cfg_tab_perfil: '👤 Meu Perfil & Conta',
    cfg_tab_idioma_apariencia: '🌐 Idioma & Aparência',
    cfg_tab_conectividad: '🌐 Conectividade & Sistema',
    cfg_tab_backups: '💾 Cópias de Segurança',
    cfg_tab_papelera: '♻️ Lixeira de Membros',
    cfg_tab_powerbi: '📊 Microsoft Power BI',

    // Perfil
    cfg_subir_foto: 'Carregar Foto de Perfil',
    cfg_quitar_foto: 'Remover Foto',
    cfg_info_personal: 'Informações Pessoais da Conta',
    cfg_nombre_completo: 'Nome Completo',
    cfg_correo: 'E-mail',
    cfg_cargo: 'Cargo / Função na Plataforma',
    cfg_institucion: 'Instituição / Convênio',
    cfg_act_pwd: 'Atualização Segura de Senha',
    cfg_act_pwd_desc: 'Defina uma senha com pelo menos 6 dígitos. Você pode verificá-la com o ícone do olho.',
    cfg_pwd_nueva: 'Nova Senha (mínimo 6 caracteres)',
    cfg_pwd_conf: 'Confirmar Senha',
    cfg_btn_act_pwd: 'Atualizar Senha',

    // Idioma & Apariencia
    cfg_idioma_titulo: 'Idioma da Plataforma',
    cfg_idioma_desc: 'Selecione o idioma oficial para a interface e textos em todo o sistema.',
    cfg_modo_titulo: 'Modo Visual do Sistema',
    cfg_modo_desc: 'Alterne entre o Modo Escuro e o Modo Claro de acordo com suas preferências visuais.',
    cfg_modo_oscuro_tit: 'Modo Escuro',
    cfg_modo_oscuro_sub: 'Conforto Noturno OLED',
    cfg_modo_oscuro_desc: 'Superfícies em cinza profundo OLED, alto contraste visual equilibrado e toques ciano/azul para reduzir a fadiga ocular.',
    cfg_btn_modo_oscuro: 'Ativar Modo Escuro',
    cfg_modo_claro_tit: 'Modo Claro',
    cfg_modo_claro_sub: 'Clareza Diurna Executiva',
    cfg_modo_claro_desc: 'Superfícies brancas impecáveis, tipografia com ótimo contraste diurno e acabamentos em azul navy corporativo.',
    cfg_btn_modo_claro: 'Ativar Modo Claro',

    // Catálogo de Conteúdos
    cat_categoria: 'BIBLIOTECA & COLEÇÕES MICROSOFT',
    cat_titulo: 'Catálogo de Conteúdos',
    cat_desc: 'Explore as trilhas formativas e envie coleções para cada escola, empresa parceira ou instituição com alertas anti-duplicação.',
    cat_btn_enviar: 'Enviar Coleção para Organização',
    cat_btn_subir: '+ Enviar Novo Material',
    cat_explorar_material: 'Explorar Material',
    cat_btn_enviar_org: 'Enviar para Org',
    cat_btn_enviar_org_title: 'Enviar / Atribuir esta coleção a uma instituição',
    cat_modulos: 'Módulos',
    cat_para_mentores: 'Para Mentores',
    cat_para_aprendices: 'Para Aprendizes',
    cat_global: 'Global',
    cat_institucion: 'Instituição',
    cat_acceso_global: 'Acesso Global (Todas)',

    // Vistas principales
    v_nodos_cat: 'AMBIENTES & COMUNIDADES',
    v_nodos_tit: 'Criador de Ambientes',
    v_nodos_desc: 'Gestão integrada de escolas, empresas parceiras, comunidades e atribuição de licenças.',
    v_nodos_sub: 'Instituições e Ambientes Ativos',
    v_nodos_btn_nuevo: 'Nova Instituição',

    v_dir_cat: 'GESTÃO ESTRUTURAL & FUNÇÕES',
    v_dir_tit: 'Estrutura Organizacional & Equipes',
    v_dir_desc: 'Organograma institucional, distribuição de funções de trabalho e carga de pessoal.',
    v_dir_btn_plantilla: 'Baixar Modelo Excel (.xlsx)',

    v_met_cat: 'TELEMETRIA, ANÁLISE & DESEMPENHO',
    v_met_tit: 'Métricas e Desempenho',
    v_met_desc: 'Supervisão integral de progresso, avanço por módulos e rendimentos acadêmicos da instituição.',
    v_met_btn_excel: 'Baixar Métricas & Gráficos (.xlsx)',
    v_met_lbl_institucion: 'Instituição:',

    v_cat_cat: 'CAPACITAÇÃO & TRILHAS',
    v_cat_tit: 'Catálogo de Capacitações & Conteúdos',
    v_cat_desc: 'Trilhas oficiais de aprendizagem Microsoft Learn, SENA e programas de certificação.',

    v_cel_cat: 'AUDITORIA & RASTREABILIDADE',
    v_cel_tit: 'Registro de Atividade',
    v_cel_desc: 'Controle diário de novos membros e registro de auditoria em tempo real em uma única visualização.',

    v_mentor_cat: 'SALA DE AULA & TUTORIA',
    v_mentor_tit: 'Minha Turma & Supervisão de Progresso',
    v_mentor_desc: 'Monitore o progresso acadêmico real, tempo dedicado e desempenho em questionários dos seus aprendizes (Somente Leitura).',

    toast_idioma_cambiado: '✓ Idioma atualizado para Português.'
  }
};

let idiomaAppActual = localStorage.getItem('app_idioma') || 'es';

function t(clave, fallback = '') {
  const dict = I18N_DICCIONARIO[idiomaAppActual] || I18N_DICCIONARIO['es'];
  if (dict && dict[clave] !== undefined) return dict[clave];
  return fallback || clave;
}

function alternarDropdownIdiomaHeader(event) {
  if (event) event.stopPropagation();
  const menu = document.getElementById('dropdown-header-idioma-menu');
  if (menu) menu.classList.toggle('hidden');
}

function cerrarDropdownIdiomaHeader() {
  const menu = document.getElementById('dropdown-header-idioma-menu');
  if (menu) menu.classList.add('hidden');
}

document.addEventListener('click', (e) => {
  const wrapper = document.getElementById('dropdown-header-idioma-wrapper');
  if (wrapper && !wrapper.contains(e.target)) {
    cerrarDropdownIdiomaHeader();
  }
});

function cambiarIdiomaApp(lang, mostrarToastNotif = false) {
  if (!I18N_DICCIONARIO[lang]) lang = 'es';
  idiomaAppActual = lang;
  localStorage.setItem('app_idioma', lang);
  document.documentElement.lang = lang;

  // 1. Traducir todos los elementos con atributo data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const clave = el.getAttribute('data-i18n');
    const texto = t(clave);
    if (texto) {
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = texto;
      } else {
        el.textContent = texto;
      }
    }
  });

  // 2. Actualizar botones selectores de idioma en Configuración
  const botones = document.querySelectorAll('.btn-selector-idioma');
  botones.forEach(btn => {
    const l = btn.getAttribute('data-lang');
    const check = btn.querySelector('.badge-idioma-check');
    if (l === lang) {
      btn.classList.add('activo');
      if (check) check.classList.remove('hidden');
    } else {
      btn.classList.remove('activo');
      if (check) check.classList.add('hidden');
    }
  });

  // 3. Actualizar botón en el header superior
  const flagMap = { es: '🇪🇸', en: '🇺🇸', pt: '🇧🇷' };
  const lblMap = { es: 'ES', en: 'EN', pt: 'PT' };
  const headerFlag = document.getElementById('header-idioma-flag');
  const headerLbl = document.getElementById('header-idioma-lbl');
  if (headerFlag) headerFlag.textContent = flagMap[lang] || '🌐';
  if (headerLbl) headerLbl.textContent = lblMap[lang] || lang.toUpperCase();

  // 4. Reconfigurar sidebar para que todas las secciones y enlaces queden en el nuevo idioma (sin cambiar de vista)
  if (typeof configurarVistasSegunRol === 'function') {
    configurarVistasSegunRol(false);
  }

  // 5. Actualizar pastilla de rol en el header
  if (typeof actualizarPerfilSidebar === 'function') {
    actualizarPerfilSidebar();
  }

  // 6. Refrescar tarjetas de catálogo si están disponibles
  if (typeof cargarMateriales === 'function' && typeof catalogoColeccionesActuales !== 'undefined' && catalogoColeccionesActuales && catalogoColeccionesActuales.length > 0) {
    cargarMateriales();
  }

  // 7. Refrescar iconos de Lucide
  if (typeof refrescarIconos === 'function') {
    refrescarIconos();
  }

  // 8. Notificación Toast (solo si fue solicitada explícitamente al pulsar el botón)
  if (mostrarToastNotif) {
    mostrarToast(t('toast_idioma_cambiado', '✓ Idioma actualizado.'), 'exito');
  }
}

function inicializarIdiomaApp() {
  const lang = localStorage.getItem('app_idioma') || 'es';
  cambiarIdiomaApp(lang, false);
}

// ---------------------------------------------------------------------
// SELECCIÓN Y GESTIÓN DE MODOS VISUALES (SOLO MODO OSCURO & MODO CLARO)
// ---------------------------------------------------------------------
function seleccionarTemaVisual(modo) {
  if (modo !== 'oscuro') modo = 'claro';

  document.body.classList.remove('tema-predeterminado', 'tema-oscuro', 'tema-claro', 'tema-institucional', 'tema-artistico');
  document.body.classList.add(`tema-${modo}`);
  localStorage.setItem('edtech_tema_visual', modo);

  // Limpiar estilos manuales inline para respetar el modo al 100%
  document.documentElement.style.removeProperty('--navy-sidebar');
  document.documentElement.style.removeProperty('--navy-hover');
  document.documentElement.style.removeProperty('--cyan-accent');

  const badgeOscuro = document.getElementById('badge-tema-oscuro');
  const badgeClaro = document.getElementById('badge-tema-claro');

  if (badgeOscuro) {
    if (modo === 'oscuro') badgeOscuro.classList.remove('hidden');
    else badgeOscuro.classList.add('hidden');
  }
  if (badgeClaro) {
    if (modo === 'claro') badgeClaro.classList.remove('hidden');
    else badgeClaro.classList.add('hidden');
  }

  const lblHeaderModo = document.getElementById('lbl-header-modo');
  if (lblHeaderModo) {
    lblHeaderModo.innerText = (modo === 'oscuro') ? '☀️ Modo Claro' : '🌙 Modo Oscuro';
  }

  const btnPerfilClaro = document.getElementById('btn-perfil-modo-claro');
  const btnPerfilOscuro = document.getElementById('btn-perfil-modo-oscuro');
  if (btnPerfilClaro && btnPerfilOscuro) {
    if (modo === 'oscuro') {
      btnPerfilOscuro.className = 'px-4 py-3 rounded-xl border-2 border-cyan-400 bg-[#131314] text-cyan-300 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md cursor-pointer ring-2 ring-cyan-500/20';
      btnPerfilClaro.className = 'px-4 py-3 rounded-xl border border-slate-300 bg-white text-slate-700 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-xs cursor-pointer opacity-80 hover:opacity-100';
    } else {
      btnPerfilClaro.className = 'px-4 py-3 rounded-xl border-2 border-cyan-600 bg-cyan-50/70 text-[#0a192f] font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md cursor-pointer ring-2 ring-cyan-500/20';
      btnPerfilOscuro.className = 'px-4 py-3 rounded-xl border border-slate-700 bg-[#131314] text-slate-300 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-xs cursor-pointer opacity-85 hover:opacity-100';
    }
  }

  refrescarIconos();
}

function alternarTemaVisualRapido() {
  const actual = localStorage.getItem('edtech_tema_visual') || 'claro';
  const nuevo = (actual === 'oscuro') ? 'claro' : 'oscuro';
  seleccionarTemaVisual(nuevo);
  mostrarToast(nuevo === 'oscuro' ? '🌙 Modo Oscuro (Negro) activado' : '☀️ Modo Claro (Blanco) activado', 'info');
}

function actualizarVisibilidadTemasSegunRol() {
  const modo = localStorage.getItem('edtech_tema_visual') || 'claro';
  seleccionarTemaVisual(modo);
}

// ---------------------------------------------------------------------
// GESTIÓN DE SUBIDA Y RESTABLECIMIENTO DEL LOGO INSTITUCIONAL
// ---------------------------------------------------------------------
let orgIdParaSubirLogo = null;

function cambiarLogoOrgDirecto(orgId, orgNombre) {
  orgIdParaSubirLogo = orgId;
  const input = document.getElementById('input-logo-org-admin');
  if (input) input.click();
}

async function procesarSubidaLogoOrg(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  if (file.size > 2 * 1024 * 1024) {
    event.target.value = '';
    return mostrarToast('La imagen de logo institucional no debe superar los 2MB.', 'advertencia');
  }

  const orgId = orgIdParaSubirLogo ||
                (currentUser && currentUser.organizacion_id) || 
                (currentUser && currentUser.organizacion && currentUser.organizacion.id) || 
                (allOrganizations && allOrganizations.length > 0 ? allOrganizations[0].id : 1);
  orgIdParaSubirLogo = null;

  const reader = new FileReader();
  reader.onload = async (e) => {
    const base64Data = e.target.result;
    try {
      const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/logo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ logo_url: base64Data })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al guardar el logo institucional');

      if (!currentUser.organizacion) currentUser.organizacion = {};
      currentUser.organizacion.logo_url = base64Data;
      currentUser.org_logo_url = base64Data;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));

      // Actualizar en allOrganizations en memoria
      const orgIdx = allOrganizations.findIndex(o => parseInt(o.id) === parseInt(orgId));
      if (orgIdx !== -1) {
        allOrganizations[orgIdx].logo_url = base64Data;
      }

      actualizarBrandingOrganizacionUI();
      if (typeof cargarNodosInstitucionales === 'function') cargarNodosInstitucionales();
      mostrarToast('✅ ¡Logo institucional guardado y publicado en tiempo real para todos los roles!', 'exito');
    } catch (err) {
      mostrarToast(err.message, 'error');
    } finally {
      event.target.value = '';
    }
  };
  reader.readAsDataURL(file);
}

async function eliminarLogoOrgActual() {
  const orgId = (currentUser && currentUser.organizacion_id) || 
                (currentUser && currentUser.organizacion && currentUser.organizacion.id) || 
                (allOrganizations && allOrganizations.length > 0 ? allOrganizations[0].id : 1);

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/logo`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al restablecer el logo');

    if (currentUser.organizacion) currentUser.organizacion.logo_url = null;
    currentUser.org_logo_url = null;
    localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));

    const orgIdx = allOrganizations.findIndex(o => parseInt(o.id) === parseInt(orgId));
    if (orgIdx !== -1) {
      allOrganizations[orgIdx].logo_url = null;
    }

    actualizarBrandingOrganizacionUI();
    if (typeof cargarNodosInstitucionales === 'function') cargarNodosInstitucionales();
    mostrarToast('Logo institucional restablecido exitosamente.', 'info');
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------------------------------------------------------------------
// GESTIÓN DE LOGOS INSTITUCIONALES DENTRO DE MODALES (CREAR / EDITAR)
// ---------------------------------------------------------------------
let crearOrgLogoBase64 = null;
let editOrgLogoBase64 = null;
let editOrgLogoEliminado = false;

function previsualizarLogoCrearOrg(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  if (file.size > 2 * 1024 * 1024) {
    mostrarToast('La imagen de logo no debe superar los 2MB.', 'advertencia');
    event.target.value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    crearOrgLogoBase64 = e.target.result;
    const img = document.getElementById('img-preview-crear-org-logo');
    const icon = document.getElementById('icono-preview-crear-org-logo');
    const lbl = document.getElementById('label-crear-org-logo-text');
    const btnRemover = document.getElementById('btn-remover-crear-org-logo');

    if (img) {
      img.src = crearOrgLogoBase64;
      img.classList.remove('hidden');
    }
    if (icon) icon.classList.add('hidden');
    if (lbl) lbl.innerText = file.name;
    if (btnRemover) btnRemover.classList.remove('hidden');
  };
  reader.readAsDataURL(file);
}

function removerLogoCrearOrg() {
  crearOrgLogoBase64 = null;
  const input = document.getElementById('crear-org-logo-file');
  if (input) input.value = '';
  const img = document.getElementById('img-preview-crear-org-logo');
  const icon = document.getElementById('icono-preview-crear-org-logo');
  const lbl = document.getElementById('label-crear-org-logo-text');
  const btnRemover = document.getElementById('btn-remover-crear-org-logo');

  if (img) {
    img.src = '';
    img.classList.add('hidden');
  }
  if (icon) icon.classList.remove('hidden');
  if (lbl) lbl.innerText = 'Añadir logo institucional';
  if (btnRemover) btnRemover.classList.add('hidden');
}

function previsualizarLogoEditarOrg(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  if (file.size > 2 * 1024 * 1024) {
    mostrarToast('La imagen de logo no debe superar los 2MB.', 'advertencia');
    event.target.value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    editOrgLogoBase64 = e.target.result;
    editOrgLogoEliminado = false;
    const img = document.getElementById('img-preview-edit-org-logo');
    const txtSin = document.getElementById('txt-sin-logo-edit-org');
    const lbl = document.getElementById('label-edit-org-logo-status');
    const btnRemover = document.getElementById('btn-remover-edit-org-logo');

    if (img) {
      img.src = editOrgLogoBase64;
      img.classList.remove('hidden');
    }
    if (txtSin) txtSin.classList.add('hidden');
    if (lbl) lbl.innerText = 'Nueva imagen seleccionada';
    if (btnRemover) btnRemover.classList.remove('hidden');
  };
  reader.readAsDataURL(file);
}

function removerLogoEditarOrg() {
  editOrgLogoBase64 = null;
  editOrgLogoEliminado = true;
  const input = document.getElementById('edit-org-logo-file');
  if (input) input.value = '';
  const img = document.getElementById('img-preview-edit-org-logo');
  const txtSin = document.getElementById('txt-sin-logo-edit-org');
  const lbl = document.getElementById('label-edit-org-logo-status');
  const btnRemover = document.getElementById('btn-remover-edit-org-logo');

  if (img) {
    img.src = '';
    img.classList.add('hidden');
  }
  if (txtSin) txtSin.classList.remove('hidden');
  if (lbl) lbl.innerText = 'Logo eliminado (sin logo)';
  if (btnRemover) btnRemover.classList.add('hidden');
}

function obtenerClaseBadgeRol(rol) {
  if (!rol) return 'badge-corp-aprendiz';
  if (rol.includes('Super')) return 'badge-corp-superadmin';
  if (rol === 'Administrador') return 'badge-corp-admin';
  if (rol === 'Mentor') return 'badge-corp-mentor';
  return 'badge-corp-aprendiz';
}

function actualizarEstiloModoDominio(nameGroup) {
  const radios = document.querySelectorAll(`input[name="${nameGroup}"]`);
  radios.forEach(r => {
    const label = r.closest('.radio-opc-modo');
    if (label) {
      if (r.checked) {
        label.classList.add('seleccionado');
      } else {
        label.classList.remove('seleccionado');
      }
    }
  });
}

// =====================================================================
// 2. SEPARACIÓN ESTRICTA DE VISTAS Y MENÚ POR ROL
// =====================================================================
function configurarVistasSegunRol(forzarNavegacionInicial = false) {
  const rolRaw = currentUser ? String(currentUser.rol || '').trim() : '';
  const rol = rolRaw.toLowerCase().trim();
  const navContainer = document.getElementById('sidebar-nav-container');
  if (!navContainer) return;

  let linksHtml = '';

  if (rol.includes('super')) {
    linksHtml = `
      <div class="px-3 pt-1 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_entornos', 'Entornos & Institución')}</span>
      </div>
      <a id="nav-item-nodos" onclick="navegarVista('nodos')" class="sidebar-link">
        <i data-lucide="building-2" class="w-4 h-4 shrink-0 text-cyan-400"></i>
        <span>${t('side_creador_entornos', 'Creador de Entornos')}</span>
      </a>
      <a id="nav-item-directorio" onclick="navegarVista('directorio')" class="sidebar-link">
        <i data-lucide="users-2" class="w-4 h-4 shrink-0 text-emerald-400"></i>
        <span>${t('side_estructura_equipos', 'Estructura & Equipos')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_metricas', 'Métricas & Contenidos')}</span>
      </div>
      <a id="nav-item-metricas" onclick="navegarVista('metricas')" class="sidebar-link">
        <i data-lucide="bar-chart-2" class="w-4 h-4 shrink-0 text-amber-400"></i>
        <span>${t('side_metricas_graficas', 'Métricas & Gráficas')}</span>
      </a>
      <a id="nav-item-catalogo" onclick="navegarVista('catalogo')" class="sidebar-link">
        <i data-lucide="layers" class="w-4 h-4 shrink-0 text-cyan-300"></i>
        <span>${t('side_catalogo_contenidos', 'Catálogo de Contenidos')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_seguridad', 'Seguridad & Ajustes')}</span>
      </div>
      <a id="nav-item-celador" onclick="navegarVista('celador')" class="sidebar-link">
        <i data-lucide="clipboard-list" class="w-4 h-4 shrink-0 text-cyan-400"></i>
        <span>${t('side_registro_actividad', 'Registro de Actividad')}</span>
      </a>
      <a id="nav-item-configuraciones" onclick="navegarVista('configuraciones')" class="sidebar-link">
        <i data-lucide="settings" class="w-4 h-4 shrink-0 text-slate-300"></i>
        <span>${t('side_configuracion_espacio', 'Configuración & Espacio')}</span>
      </a>
    `;
  } else if (rol === 'Mentor') {
    linksHtml = `
      <div class="px-3 pt-1 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_formacion', 'Formación & Clases')}</span>
      </div>
      <a id="nav-item-mentor-clase" onclick="navegarVista('mentor-clase')" class="sidebar-link">
        <i data-lucide="graduation-cap" class="w-4 h-4 shrink-0 text-purple-400"></i>
        <span>${t('side_mis_clases', 'Mis Clases & Tutorías')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_metricas', 'Métricas & Contenidos')}</span>
      </div>
      <a id="nav-item-metricas" onclick="navegarVista('metricas')" class="sidebar-link">
        <i data-lucide="bar-chart-2" class="w-4 h-4 shrink-0 text-amber-400"></i>
        <span>${t('side_metricas_graficas', 'Métricas & Gráficas')}</span>
      </a>
      <a id="nav-item-catalogo" onclick="navegarVista('catalogo')" class="sidebar-link">
        <i data-lucide="layers" class="w-4 h-4 shrink-0 text-cyan-300"></i>
        <span>${t('side_catalogo_contenidos', 'Catálogo de Contenidos')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_seguridad', 'Seguridad & Ajustes')}</span>
      </div>
      <a id="nav-item-celador" onclick="navegarVista('celador')" class="sidebar-link">
        <i data-lucide="clipboard-list" class="w-4 h-4 shrink-0 text-cyan-400"></i>
        <span>${t('side_registro_actividad', 'Registro de Actividad')}</span>
      </a>
      <a id="nav-item-configuraciones" onclick="navegarVista('configuraciones')" class="sidebar-link">
        <i data-lucide="settings" class="w-4 h-4 shrink-0 text-slate-300"></i>
        <span>${t('side_configuracion_espacio', 'Configuración & Espacio')}</span>
      </a>
    `;
  } else if (rol === 'Aprendiz' || rol === 'Estudiante') {
    linksHtml = `
      <div class="px-3 pt-1 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_mi_formacion', 'Mi Formación')}</span>
      </div>
      <a id="nav-item-aprendiz" onclick="navegarVista('aprendiz')" class="sidebar-link">
        <i data-lucide="book-open" class="w-4 h-4 shrink-0 text-sky-400"></i>
        <span>${t('side_mis_rutas', 'Mis Rutas de Aprendizaje')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_metricas_cursos', 'Métricas & Cursos')}</span>
      </div>
      <a id="nav-item-metricas" onclick="navegarVista('metricas')" class="sidebar-link">
        <i data-lucide="bar-chart-2" class="w-4 h-4 shrink-0 text-amber-400"></i>
        <span>${t('side_mis_metricas', 'Mis Métricas & Gráficas')}</span>
      </a>
      <a id="nav-item-catalogo" onclick="navegarVista('catalogo')" class="sidebar-link">
        <i data-lucide="layers" class="w-4 h-4 shrink-0 text-cyan-300"></i>
        <span>${t('side_catalogo_cursos', 'Catálogo de Cursos')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_mi_espacio', 'Mi Espacio & Registro')}</span>
      </div>
      <a id="nav-item-celador" onclick="navegarVista('celador')" class="sidebar-link">
        <i data-lucide="clipboard-list" class="w-4 h-4 shrink-0 text-cyan-400"></i>
        <span>${t('side_registro_actividad', 'Mi Registro de Actividad')}</span>
      </a>
      <a id="nav-item-configuraciones" onclick="navegarVista('configuraciones')" class="sidebar-link">
        <i data-lucide="settings" class="w-4 h-4 shrink-0 text-slate-300"></i>
        <span>${t('side_configuracion_espacio', 'Mi Espacio & Preferencias')}</span>
      </a>
    `;
  } else {
    // Administrador Institucional
    linksHtml = `
      <div class="px-3 pt-1 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_entornos', 'Gestión Institucional')}</span>
      </div>
      <a id="nav-item-admin-convenio" onclick="navegarVista('admin-convenio')" class="sidebar-link">
        <i data-lucide="building" class="w-4 h-4 shrink-0 text-cyan-400"></i>
        <span>${t('side_creador_entornos', 'Centro de Mando')}</span>
      </a>
      <a id="nav-item-directorio" onclick="navegarVista('directorio')" class="sidebar-link">
        <i data-lucide="users-2" class="w-4 h-4 shrink-0 text-emerald-400"></i>
        <span>${t('side_estructura_equipos', 'Estructura & Equipos')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_metricas', 'Desempeño & Formación')}</span>
      </div>
      <a id="nav-item-admin-desempeno" onclick="navegarVista('admin-desempeno')" class="sidebar-link">
        <i data-lucide="award" class="w-4 h-4 shrink-0 text-sky-400"></i>
        <span>${t('side_metricas_graficas', 'Desempeño Unificado')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_metricas', 'Métricas & Contenidos')}</span>
      </div>
      <a id="nav-item-metricas" onclick="navegarVista('metricas')" class="sidebar-link">
        <i data-lucide="bar-chart-2" class="w-4 h-4 shrink-0 text-amber-400"></i>
        <span>${t('side_metricas_graficas', 'Métricas & Gráficas')}</span>
      </a>
      <a id="nav-item-catalogo" onclick="navegarVista('catalogo')" class="sidebar-link">
        <i data-lucide="layers" class="w-4 h-4 shrink-0 text-cyan-300"></i>
        <span>${t('side_catalogo_contenidos', 'Catálogo de Contenidos')}</span>
      </a>

      <div class="px-3 pt-3 pb-1">
        <span class="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">${t('side_sec_seguridad', 'Seguridad & Ajustes')}</span>
      </div>
      <a id="nav-item-celador" onclick="navegarVista('celador')" class="sidebar-link">
        <i data-lucide="clipboard-list" class="w-4 h-4 shrink-0 text-cyan-400"></i>
        <span>${t('side_registro_actividad', 'Registro de Actividad')}</span>
      </a>
      <a id="nav-item-configuraciones" onclick="navegarVista('configuraciones')" class="sidebar-link">
        <i data-lucide="settings" class="w-4 h-4 shrink-0 text-slate-300"></i>
        <span>${t('side_configuracion_espacio', 'Configuración & Espacio')}</span>
      </a>
    `;
  }

  navContainer.innerHTML = linksHtml;

  // Visibilidad de botones del catálogo según rol (Aprendices no suben material ni envían colecciones)
  const contAccionesCat = document.getElementById('contenedor-acciones-catalogo');
  if (contAccionesCat) {
    if (rol.includes('aprendiz') || rol.includes('estudiante')) {
      contAccionesCat.classList.add('hidden');
    } else {
      contAccionesCat.classList.remove('hidden');
    }
  }

  const todasVistas = ['nodos', 'admin-convenio', 'directorio', 'aprendiz', 'mentor-clase', 'metricas', 'catalogo', 'celador', 'configuraciones'];
  const vistaActivaActual = todasVistas.find(v => {
    const el = document.getElementById(`vista-${v}`);
    return el && !el.classList.contains('hidden');
  });

  if (forzarNavegacionInicial || !vistaActivaActual) {
    // Selección de vista de aterrizaje inicial según rol normalizado
    if (rol.includes('super')) {
      navegarVista('nodos');
    } else if (rol.includes('mentor')) {
      navegarVista('mentor-clase');
    } else if (rol.includes('aprendiz') || rol.includes('estudiante')) {
      navegarVista('aprendiz');
    } else {
      // Administrador Institucional y cualquier rol nuevo
      navegarVista('admin-convenio');
    }
  } else {
    // Mantener la vista activa y marcar el enlace en el menú lateral
    const link = document.getElementById(`nav-item-${vistaActivaActual}`);
    if (link) link.classList.add('active');
  }

  refrescarIconos();
}

function volverDesdeConfiguraciones() {
  const rol = currentUser ? String(currentUser.rol || '').toLowerCase().trim() : '';
  if (rol.includes('super')) {
    navegarVista('nodos');
  } else if (rol.includes('mentor')) {
    navegarVista('mentor-clase');
  } else if (rol.includes('aprendiz') || rol.includes('estudiante')) {
    navegarVista('aprendiz');
  } else {
    navegarVista('admin-convenio');
  }
}

function navegarVista(vistaId) {
  if (vistaId === 'nuevos-integrantes') {
    vistaId = 'celador';
    cambiarTabCelador('integrantes');
  }

  let subTabApertura = null;
  if (vistaId === 'temas') {
    vistaId = 'configuraciones';
    subTabApertura = 'personalizacion';
  } else if (vistaId === 'admin-aprendices' || vistaId === 'admin-desempeno') {
    vistaId = 'admin-convenio';
    subTabApertura = 'aprendices';
  } else if (vistaId === 'admin-mentores') {
    vistaId = 'admin-convenio';
    subTabApertura = 'mentores';
  }

  const todasVistas = ['nodos', 'admin-convenio', 'directorio', 'aprendiz', 'mentor-clase', 'metricas', 'catalogo', 'celador', 'configuraciones'];
  const todosLinks = ['nodos', 'admin-convenio', 'admin-desempeno', 'admin-aprendices', 'admin-mentores', 'directorio', 'aprendiz', 'mentor-clase', 'metricas', 'catalogo', 'celador', 'configuraciones'];

  // Marcar link activo en el menú lateral
  todosLinks.forEach(lId => {
    const link = document.getElementById(`nav-item-${lId}`);
    if (link) {
      const debeActivarse = (lId === vistaId && !subTabApertura) || 
                            (subTabApertura === 'aprendices' && (lId === 'admin-aprendices' || lId === 'admin-desempeno')) || 
                            (subTabApertura === 'mentores' && (lId === 'admin-mentores' || lId === 'admin-desempeno'));
      if (debeActivarse) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    }
  });

  // Mostrar únicamente la sección activa
  todasVistas.forEach(v => {
    const seccion = document.getElementById(`vista-${v}`);
    if (seccion) {
      if (v === vistaId) seccion.classList.remove('hidden');
      else seccion.classList.add('hidden');
    }
  });

  // Cargar datos correspondientes de la vista
  if (vistaId === 'nodos') {
    cargarNodosInstitucionales();
  } else if (vistaId === 'admin-convenio') {
    cargarVistaAdminConvenio();
    if (subTabApertura) {
      cambiarSubTabAdminConvenio(subTabApertura);
    }
  } else if (vistaId === 'directorio') {
    cargarJerarquia3Columnas();
  } else if (vistaId === 'aprendiz') {
    cargarCursosAprendiz();
  } else if (vistaId === 'mentor-clase') {
    cargarProgresoAlumnosMentor();
  } else if (vistaId === 'metricas') {
    const isAprendiz = currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante');
    if (isAprendiz) {
      cargarMetricasPrivadasAprendiz();
    } else {
      actualizarMetricas();
      cargarAnaliticaPorOrganizacion();
    }
  } else if (vistaId === 'catalogo') {
    cargarMateriales();
  } else if (vistaId === 'celador') {
    const isAprendiz = currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante');
    const isMentor = currentUser && currentUser.rol === 'Mentor';
    if (isAprendiz || isMentor) {
      cambiarTabCelador('eventos');
    } else {
      refrescarTodosSelectoresOrganizaciones();
      cambiarTabCelador('integrantes');
    }
  } else if (vistaId === 'configuraciones') {
    inicializarVistaConfiguraciones(subTabApertura);
  }

  // Si se eligió una subpestaña específica (Estudiantes o Mentores), scroll suave al área
  if (subTabApertura === 'aprendices') {
    setTimeout(() => {
      document.getElementById('sec-admin-tab-aprendices')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 250);
  } else if (subTabApertura === 'mentores') {
    setTimeout(() => {
      document.getElementById('sec-admin-tab-mentores')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 250);
  }

  if (window.innerWidth < 1024) {
    cerrarMenuDesplegable();
  }

  refrescarIconos();
}

function toggleMenuDesplegable() {
  const sidebar = document.getElementById('main-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (!sidebar) return;

  if (window.innerWidth < 1024) {
    sidebar.classList.toggle('sidebar-drawer-abierto');
    if (backdrop) {
      if (sidebar.classList.contains('sidebar-drawer-abierto')) {
        backdrop.classList.remove('hidden');
      } else {
        backdrop.classList.add('hidden');
      }
    }
  } else {
    sidebar.classList.toggle('sidebar-colapsado');
  }
  refrescarIconos();
}

function cerrarMenuDesplegable() {
  const sidebar = document.getElementById('main-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (sidebar) {
    sidebar.classList.remove('sidebar-drawer-abierto');
    sidebar.classList.add('sidebar-colapsado');
  }
  if (backdrop) backdrop.classList.add('hidden');
}

function toggleSidebar() {
  toggleMenuDesplegable();
}

function toggleSidebarMobile() {
  toggleMenuDesplegable();
}

// =====================================================================
// 3. AUTENTICACIÓN 2FA Y REGISTRO INSTITUCIONAL
// =====================================================================
function llenarCredencialesDemo(correo, password) {
  cambiarPestanaAuth('login');
  document.getElementById('login-email').value = correo;
  document.getElementById('login-password').value = password;
  const alertaNoReg = document.getElementById('alerta-no-registrado');
  if (alertaNoReg) alertaNoReg.classList.add('hidden');
  mostrarToast(`Credenciales cargadas para ${correo}.`, 'info');
}

function togglePasswordVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';
  if (btnEl) {
    btnEl.innerHTML = `<i data-lucide="${isPassword ? 'eye-off' : 'eye'}" class="w-4 h-4 text-cyan-600"></i>`;
    refrescarIconos();
  }
}

function cambiarPestanaAuth(tab) {
  const panelLogin = document.getElementById('panel-auth-login');
  const panelRecuperar = document.getElementById('panel-auth-recuperar');
  const alertaNoReg = document.getElementById('alerta-no-registrado');

  if (alertaNoReg) alertaNoReg.classList.add('hidden');

  if (tab === 'recuperar') {
    if (panelRecuperar) panelRecuperar.classList.remove('hidden');
    if (panelLogin) panelLogin.classList.add('hidden');
    volverARecuperarPaso1();
    const emailLogin = document.getElementById('login-email')?.value.trim();
    if (emailLogin) {
      const recInput = document.getElementById('recuperar-email');
      if (recInput) recInput.value = emailLogin;
    }
  } else {
    if (panelLogin) panelLogin.classList.remove('hidden');
    if (panelRecuperar) panelRecuperar.classList.add('hidden');
    cancelar2FA();
  }
  refrescarIconos();
}

function validarCoincidenciaPasswordRegistro() {
  const p1 = document.getElementById('reg-password')?.value || '';
  const p2 = document.getElementById('reg-password-confirm')?.value || '';
  const msg = document.getElementById('msg-password-match');
  if (!msg) return;

  if (!p2) {
    msg.classList.add('hidden');
    return;
  }

  msg.classList.remove('hidden');
  if (p1 === p2) {
    msg.innerText = '✓ Las contraseñas coinciden';
    msg.className = 'text-[11px] font-semibold mt-1 text-emerald-600';
  } else {
    msg.innerText = '✕ Las contraseñas no coinciden';
    msg.className = 'text-[11px] font-semibold mt-1 text-rose-600';
  }
}

function validarCoincidenciaPasswordRecuperar() {
  const p1 = document.getElementById('recuperar-nueva-pwd')?.value || '';
  const p2 = document.getElementById('recuperar-confirm-pwd')?.value || '';
  const msg = document.getElementById('msg-recuperar-pwd-match');
  if (!msg) return;

  if (!p2) {
    msg.classList.add('hidden');
    return;
  }

  msg.classList.remove('hidden');
  if (p1 === p2) {
    msg.innerText = '✓ Las contraseñas coinciden';
    msg.className = 'text-[11px] font-semibold mt-1 text-emerald-600';
  } else {
    msg.innerText = '✕ Las contraseñas no coinciden';
    msg.className = 'text-[11px] font-semibold mt-1 text-rose-600';
  }
}

let correoEnRecuperacion = '';

async function solicitarCodigoRecuperacion(event) {
  event.preventDefault();
  const emailInput = document.getElementById('recuperar-email');
  const email = emailInput ? emailInput.value.trim().toLowerCase() : '';
  if (!email) return mostrarToast('Ingresa tu correo electrónico registrado.', 'advertencia');

  const btn = document.getElementById('btn-recuperar-solicitar');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Enviando código militar...</span>`;
    refrescarIconos();
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/solicitar-recuperacion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo: email })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al solicitar código');

    correoEnRecuperacion = email;
    mostrarToast('✓ Código de recuperación enviado a tu correo.', 'exito');

    currentCodigoAuxiliarRecuperar = json.codigo_auxiliar || '';
    const cajaAuxRec = document.getElementById('caja-auxiliar-recuperar');
    const lblAuxRec = document.getElementById('label-codigo-auxiliar-recuperar');
    if (cajaAuxRec && lblAuxRec && currentCodigoAuxiliarRecuperar) {
      lblAuxRec.innerText = currentCodigoAuxiliarRecuperar;
      cajaAuxRec.classList.remove('hidden');
    }

    document.getElementById('form-recuperar-paso1').classList.add('hidden');
    document.getElementById('form-recuperar-paso2').classList.remove('hidden');
    document.getElementById('lbl-recuperar-email-destino').innerText = email;
    const otpInput = document.getElementById('recuperar-codigo-otp');
    if (otpInput) {
      otpInput.value = '';
      otpInput.focus();
    }
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span>Enviar Código de Recuperación</span>`;
      refrescarIconos();
    }
  }
}

function volverARecuperarPaso1() {
  document.getElementById('form-recuperar-paso2').classList.add('hidden');
  document.getElementById('form-recuperar-paso1').classList.remove('hidden');
}

async function reenviarCodigoRecuperacion() {
  if (!correoEnRecuperacion) return mostrarToast('No hay correo en proceso de recuperación.', 'advertencia');
  try {
    mostrarToast('Reenviando nuevo código a tu correo...', 'info');
    const res = await fetch(`${API_BASE}/api/auth/solicitar-recuperacion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo: correoEnRecuperacion })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al reenviar código');
    mostrarToast('✓ Nuevo código de recuperación enviado a tu correo.', 'exito');
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

async function ejecutarCambioPassword(event) {
  event.preventDefault();
  const codigo = document.getElementById('recuperar-codigo-otp').value.trim();
  const pwd1 = document.getElementById('recuperar-nueva-pwd').value;
  const pwd2 = document.getElementById('recuperar-confirm-pwd').value;

  if (!codigo || (codigo.length !== 6 && codigo.length !== 4)) {
    return mostrarToast('Introduce el código de 6 dígitos que llegó a tu correo.', 'advertencia');
  }

  if (pwd1.length < 6) {
    return mostrarToast('La contraseña debe tener al menos 6 caracteres.', 'advertencia');
  }

  if (pwd1 !== pwd2) {
    return mostrarToast('Las contraseñas no coinciden. Por favor rectifícalas.', 'error');
  }

  const btn = document.getElementById('btn-recuperar-confirmar');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Guardando contraseña...</span>`;
    refrescarIconos();
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/cambiar-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        correo: correoEnRecuperacion,
        codigo: codigo,
        nueva_password: pwd1
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al cambiar contraseña');

    mostrarToast('🎉 ¡Contraseña restablecida con éxito! Ingresa ahora con tu nueva clave.', 'exito');

    document.getElementById('recuperar-codigo-otp').value = '';
    document.getElementById('recuperar-nueva-pwd').value = '';
    document.getElementById('recuperar-confirm-pwd').value = '';
    volverARecuperarPaso1();

    cambiarPestanaAuth('login');
    document.getElementById('login-email').value = correoEnRecuperacion;
    document.getElementById('login-password').value = '';
    document.getElementById('login-password').focus();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="check-circle-2" class="w-4 h-4"></i><span>Actualizar Contraseña y Entrar</span>`;
      refrescarIconos();
    }
  }
}

function irARegistroConCorreo() {
  const email = document.getElementById('login-email').value.trim();
  cambiarPestanaAuth('registro');
  if (email) {
    document.getElementById('reg-email').value = email;
  }
  const inputNombre = document.getElementById('reg-nombre');
  if (inputNombre) inputNombre.focus();
}

let organizacionesCargadasParaRegistro = false;
async function cargarOrganizacionesRegistro() {
  const select = document.getElementById('reg-organizacion');
  if (!select) return;
  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/listar`);
    const data = await res.json();
    if (data.status === 'success' && data.data && data.data.length > 0) {
      select.innerHTML = data.data.map(org => `
        <option value="${org.id}">${org.nombre} (${org.tipo_organizacion})</option>
      `).join('');
      organizacionesCargadasParaRegistro = true;
    } else {
      select.innerHTML = `<option value="1">UNIMINUTO Sede Principal (Educativa)</option>`;
    }
  } catch (err) {
    console.warn("No se pudieron cargar organizaciones para registro:", err);
    select.innerHTML = `<option value="1">UNIMINUTO Sede Principal (Educativa)</option>`;
  }
}

async function procesarLoginPaso1(event) {
  event.preventDefault();
  const correo = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value.trim();
  const alertaNoReg = document.getElementById('alerta-no-registrado');
  if (alertaNoReg) alertaNoReg.classList.add('hidden');

  await iniciarLoginConCredenciales(correo, password);
}

async function solicitarCodigo2FA(correo, password) {
  return await iniciarLoginConCredenciales(correo, password);
}
window.solicitarCodigo2FA = solicitarCodigo2FA;

async function iniciarLoginConCredenciales(correo, password) {
  const btnSubmit = document.getElementById('btn-login-submit');
  if (btnSubmit) {
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Iniciando sesión...</span>`;
    refrescarIconos();
  }

  const honeypotInput = document.getElementById('login-honeypot');
  const honeypotVal = honeypotInput ? honeypotInput.value : '';

  try {
    const res = await fetch(`${API_BASE}/api/auth/iniciar-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo, password, honeypot: honeypotVal })
    });
    const data = await res.json();

    if (!res.ok) {
      if (res.status === 404) {
        const alertaNoReg = document.getElementById('alerta-no-registrado');
        if (alertaNoReg) alertaNoReg.classList.remove('hidden');
        mostrarToast('Este correo no está en el sistema. Puedes crear tu cuenta aquí.', 'advertencia');
        return;
      }
      throw new Error(data.detail || 'Credenciales incorrectas');
    }

    if (data.usuario) {
      currentUser = data.usuario;
      if (currentUser) {
        currentUser.rol_normalizado = String(currentUser.rol || 'aprendiz').toLowerCase().trim();
      }
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      if (typeof aplicarEstilosTemaWeb === 'function') {
        aplicarEstilosTemaWeb(currentUser.tema_decorativo || 'estandar', currentUser.fondo_personalizado);
      }
      const orgNombre = currentUser.organizacion?.nombre || currentUser.organizacion_nombre || currentUser.institucion || 'Corporación Universitaria Minuto de Dios';
      mostrarToast(`¡Bienvenido(a), ${currentUser.nombre}! (${currentUser.rol} · ${orgNombre})`, 'exito');
      mostrarDashboardPrincipal();
    }
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = `<span>Iniciar Sesión</span><i data-lucide="arrow-right" class="w-4 h-4"></i>`;
      refrescarIconos();
    }
  }
}

async function procesarRegistroUsuario(event) {
  event.preventDefault();
  const nombre = document.getElementById('reg-nombre').value.trim();
  const correo = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const passwordConfirm = document.getElementById('reg-password-confirm')?.value || '';
  const orgSelect = document.getElementById('reg-organizacion');
  const organizacion_id = parseInt(orgSelect.value) || 1;
  const rol = document.getElementById('reg-rol').value;
  const btnSubmit = document.getElementById('btn-registro-submit');

  if (!nombre || !correo || !password) {
    return mostrarToast('Por favor completa todos los campos requeridos.', 'advertencia');
  }

  if (password.length < 6) {
    return mostrarToast('La contraseña debe tener mínimo 6 caracteres.', 'advertencia');
  }

  if (password !== passwordConfirm) {
    mostrarToast('Las contraseñas no coinciden. Por favor rectifícalas.', 'error');
    const inputConfirm = document.getElementById('reg-password-confirm');
    if (inputConfirm) inputConfirm.focus();
    return;
  }

  btnSubmit.disabled = true;
  btnSubmit.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Creando cuenta e ingresando...</span>`;
  refrescarIconos();

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/registrar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nombre,
        correo,
        password,
        rol,
        organizacion_id
      })
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Error al crear la cuenta');
    }

    mostrarToast(`✓ ¡Cuenta creada con éxito! Ingresando a la plataforma...`, 'exito');

    // Cambiar a la pestaña login e ingresar directamente
    cambiarPestanaAuth('login');
    document.getElementById('login-email').value = correo;
    document.getElementById('login-password').value = password;
    await iniciarLoginConCredenciales(correo, password);

  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.innerHTML = `<span>Crear Cuenta e Ingresar</span><i data-lucide="arrow-right" class="w-4 h-4"></i>`;
    refrescarIconos();
  }
}

function cancelar2FA() {}
function reenviarCodigo2FA() {}
function procesarLoginPaso2() {}

// =====================================================================
// 4. GOBERNANZA DE NODOS INSTITUCIONALES (APROVISIONAR, EDITAR, ELIMINAR)
// =====================================================================
const PALETA_AVATARES = ['#0c2340', '#1b4332', '#581c87', '#7f1d1d', '#0f766e', '#1e3a8a'];

async function cargarNodosInstitucionales() {
  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/listar`);
    const json = await res.json();
    allOrganizations = json.data || [];

    const labelConteo = document.getElementById('label-nodos-conteo');
    if (labelConteo) {
      labelConteo.innerText = `${allOrganizations.length} institución(es) · haz clic para ver el detalle`;
    }

    const grid = document.getElementById('grid-nodos-institucionales');
    if (!grid) return;

    const esSuperAdmin = currentUser && currentUser.rol === 'Super Administrador';

    // Cuadrito de Nueva Institución (con un '+', exactamente del mismo tamaño y estilo de tarjeta que las instituciones)
    const cardNuevaOrg = esSuperAdmin ? `
      <div onclick="abrirModalCrearOrg()" class="nodo-card nodo-card-crear border-2 border-dashed cursor-pointer flex flex-col justify-between transition-all group min-h-[118px]">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3.5">
            <div class="nodo-avatar nodo-avatar-crear transition-all shadow-xs flex items-center justify-center font-bold">
              <i data-lucide="plus" class="w-5 h-5 stroke-[2.5]"></i>
            </div>
            <div>
              <div class="flex items-center space-x-2">
                <h4 class="text-sm font-bold nodo-title-crear transition-colors leading-snug">Nueva Institución</h4>
                <span class="nodo-badge-crear text-[10px] font-bold px-1.5 py-0.5 rounded">
                  + Crear
                </span>
              </div>
              <p class="text-xs nodo-desc-crear font-medium mt-0.5">
                Aprovisionar colegio, empresa o comunidad
              </p>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <span class="w-8 h-8 rounded-full nodo-circle-plus flex items-center justify-center shadow-xs transition-all">
              <i data-lucide="arrow-up-right" class="w-4 h-4 text-cyan-600 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform"></i>
            </span>
          </div>
        </div>

        <div class="mt-4 pt-2.5 border-t nodo-footer-crear flex items-center justify-between text-[11px] font-semibold">
          <span class="flex items-center gap-1.5 nodo-footer-text">
            <i data-lucide="sparkles" class="w-3.5 h-3.5 text-cyan-500"></i>
            Configura identidad, dominios y licencias
          </span>
          <span class="nodo-footer-cta group-hover:translate-x-0.5 transition-transform">Crear entorno →</span>
        </div>
      </div>
    ` : '';

    const cardsOrgs = allOrganizations.map((org, index) => {
      const colorAvatar = PALETA_AVATARES[index % PALETA_AVATARES.length];
      const inicial = org.nombre ? org.nombre.trim().charAt(0).toUpperCase() : 'I';
      const cupos = org.licencias_asignadas || 500;
      const estudiantesReales = org.total_estudiantes_reales || 0;
      const porcentaje = Math.min(100, Math.round((estudiantesReales / cupos) * 100)) || 1;
      const nombreEscapado = (org.nombre || '').replace(/'/g, "\\'");
      const tipoEscapado = (org.tipo_organizacion || 'Institución').replace(/'/g, "\\'");
      const dominioEscapado = (org.dominio_permitido || '').replace(/'/g, "\\'");

      // Botones de acción para Super Administrador
      const botonesAccion = esSuperAdmin ? `
        <div class="flex items-center space-x-1" onclick="event.stopPropagation();">
          <button onclick="cambiarLogoOrgDirecto(${org.id}, '${nombreEscapado}')" class="btn-icon-edit hover:text-cyan-500" title="Cambiar Logo Institucional">
            <i data-lucide="camera" class="w-3.5 h-3.5 text-cyan-500"></i>
          </button>
          <button onclick="abrirModalEditarOrg(${org.id}, '${nombreEscapado}', '${tipoEscapado}', '${dominioEscapado}', ${cupos})" class="btn-icon-edit" title="Editar Institución y Cupos">
            <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
          </button>
          <button onclick="abrirModalConfirmarEliminar(${org.id}, '${nombreEscapado}')" class="btn-icon-delete" title="Eliminar Institución">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      ` : '';

      const esLibre = !org.dominio_permitido || org.dominio_permitido === 'LIBRE';
      const claseChip = esLibre ? 'chip-dominio-libre' : 'chip-dominio-especifico';
      const textoChip = esLibre ? '🌐 Libre' : `@${org.dominio_permitido}`;

      return `
        <div onclick="verDetalleNodo(${org.id}, '${nombreEscapado}')" class="nodo-card cursor-pointer">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3.5">
              <div class="nodo-avatar overflow-hidden ${esSuperAdmin ? 'hover:ring-2 hover:ring-cyan-400 cursor-pointer' : ''}" style="background-color: ${colorAvatar};" ${esSuperAdmin ? `onclick="event.stopPropagation(); cambiarLogoOrgDirecto(${org.id}, '${nombreEscapado}')" title="Haz clic para cambiar el logo"` : ''}>
                ${org.logo_url ? `<img src="${org.logo_url}" class="w-full h-full object-contain p-0.5 rounded-full bg-white">` : inicial}
              </div>
              <div>
                <div class="flex items-center space-x-2">
                  <h4 class="text-sm font-bold nodo-org-title leading-snug">${escapeHtml(org.nombre)}</h4>
                  <span class="text-[10px] font-mono px-1.5 py-0.5 rounded ${claseChip}">
                    ${textoChip}
                  </span>
                </div>
                <p class="text-xs text-slate-500 font-medium">
                  <span class="txt-estudiantes-reales font-bold">${estudiantesReales} estudiantes reales</span> · ${cupos} cupos (${porcentaje}% ocupado)
                </p>
              </div>
            </div>
            <div class="flex items-center space-x-2">
              ${botonesAccion}
              <i data-lucide="chevron-right" class="w-4 h-4 text-slate-400"></i>
            </div>
          </div>

          <!-- Barra de Progreso Cian Idéntica a la Referencia -->
          <div class="mt-4 progress-track-cyan">
            <div class="progress-bar-cyan" style="width: ${porcentaje}%;"></div>
          </div>
        </div>
      `;
    }).join('');

    grid.innerHTML = cardNuevaOrg + cardsOrgs;

    refrescarIconos();
    cargarOrganizacionesEnSelects();
  } catch (e) {
    console.error('Error cargando nodos:', e);
  }
}

function verDetalleNodo(id, nombre) {
  mostrarToast(`Filtrando directorio por: ${nombre}.`, 'info');
  const sel = document.getElementById('select-filtro-org-jerarquia');
  if (sel) sel.value = id;
  navegarVista('directorio');
  cargarJerarquia3Columnas(id);
}

function toggleDominioOrg(tipo) {
  if (tipo === 'crear') {
    const radioConDominio = document.querySelector('input[name="org-tipo-dominio"][value="especifico"]')?.checked;
    const contInput = document.getElementById('container-org-dominio-input');
    const contAyuda = document.getElementById('container-org-dominio-ayuda');
    const inputDom = document.getElementById('org-dominio');

    if (radioConDominio) {
      if (contInput) contInput.classList.remove('hidden');
      if (contAyuda) contAyuda.classList.add('hidden');
      if (inputDom) inputDom.focus();
    } else {
      if (contInput) contInput.classList.add('hidden');
      if (contAyuda) contAyuda.classList.remove('hidden');
      if (inputDom) inputDom.value = '';
    }
  } else if (tipo === 'editar') {
    const radioConDominio = document.querySelector('input[name="edit-org-tipo-dominio"][value="especifico"]')?.checked;
    const contInput = document.getElementById('container-edit-org-dominio-input');
    const contAyuda = document.getElementById('container-edit-org-dominio-ayuda');
    const inputDom = document.getElementById('edit-org-dominio');

    if (radioConDominio) {
      if (contInput) contInput.classList.remove('hidden');
      if (contAyuda) contAyuda.classList.add('hidden');
      if (inputDom) inputDom.focus();
    } else {
      if (contInput) contInput.classList.add('hidden');
      if (contAyuda) contAyuda.classList.remove('hidden');
      if (inputDom) inputDom.value = '';
    }
  }
}

// Modal Crear Org
function abrirModalCrearOrg() {
  document.getElementById('org-nombre').value = '';
  document.getElementById('org-tipo').value = 'Educativa';
  document.getElementById('org-licencias').value = '500';
  const radioLibre = document.querySelector('input[name="org-tipo-dominio"][value="libre"]');
  if (radioLibre) radioLibre.checked = true;
  toggleDominioOrg('crear');
  removerLogoCrearOrg();
  document.getElementById('modal-crear-org').classList.remove('hidden');
  refrescarIconos();
}

async function guardarNuevaOrg(event) {
  event.preventDefault();
  const nombre = document.getElementById('org-nombre').value.trim();
  const tipo_organizacion = document.getElementById('org-tipo').value;
  const licencias_asignadas = parseInt(document.getElementById('org-licencias').value) || 500;

  const radioConDominio = document.querySelector('input[name="org-tipo-dominio"][value="especifico"]')?.checked;
  let dominio_permitido = "LIBRE";
  if (radioConDominio) {
    const domRaw = document.getElementById('org-dominio').value.trim().replace('@', '');
    if (!domRaw) {
      return mostrarToast('Ingresa el dominio autorizado (ej: colegio.edu.co) o selecciona "Sin Dominio".', 'advertencia');
    }
    dominio_permitido = domRaw;
  }

  const payload = {
    nombre,
    tipo_organizacion,
    dominio_permitido,
    licencias_asignadas,
    max_administradores: 2,
    max_mentores: 15
  };
  if (crearOrgLogoBase64) {
    payload.logo_url = crearOrgLogoBase64;
  }

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/organizaciones/crear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al crear institución');

    const descDom = dominio_permitido !== 'LIBRE' ? `@${dominio_permitido}` : 'Sin restricción de dominio';
    mostrarToast(`✓ Institución '${nombre}' aprovisionada con éxito (${descDom}).`, 'exito');
    cerrarModal('modal-crear-org');
    removerLogoCrearOrg();
    cargarNodosInstitucionales();
    await refrescarTodosSelectoresOrganizaciones(data.id);
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// Modal Editar Org (Permite modificar cupos ej. 500 a 1000/2000, dominio y logo)
function abrirModalEditarOrg(id, nombre, tipo, dominio, licencias) {
  document.getElementById('edit-org-id').value = id;
  document.getElementById('edit-org-nombre').value = nombre;
  document.getElementById('edit-org-tipo').value = tipo;
  document.getElementById('edit-org-licencias').value = licencias;

  const tieneDominio = dominio && dominio !== 'LIBRE' && dominio !== 'null';
  const radioLibre = document.querySelector('input[name="edit-org-tipo-dominio"][value="libre"]');
  const radioEsp = document.querySelector('input[name="edit-org-tipo-dominio"][value="especifico"]');

  if (tieneDominio) {
    if (radioEsp) radioEsp.checked = true;
    document.getElementById('edit-org-dominio').value = dominio;
  } else {
    if (radioLibre) radioLibre.checked = true;
    document.getElementById('edit-org-dominio').value = '';
  }
  toggleDominioOrg('editar');

  // Inicializar estado del logo en edición
  editOrgLogoBase64 = null;
  editOrgLogoEliminado = false;
  const inputLogo = document.getElementById('edit-org-logo-file');
  if (inputLogo) inputLogo.value = '';

  const org = (allOrganizations || []).find(o => parseInt(o.id) === parseInt(id));
  const logoActual = org ? org.logo_url : null;

  const img = document.getElementById('img-preview-edit-org-logo');
  const txtSin = document.getElementById('txt-sin-logo-edit-org');
  const lbl = document.getElementById('label-edit-org-logo-status');
  const btnRemover = document.getElementById('btn-remover-edit-org-logo');

  if (logoActual) {
    if (img) {
      img.src = logoActual;
      img.classList.remove('hidden');
    }
    if (txtSin) txtSin.classList.add('hidden');
    if (lbl) lbl.innerText = 'Logo institucional activo';
    if (btnRemover) btnRemover.classList.remove('hidden');
  } else {
    if (img) {
      img.src = '';
      img.classList.add('hidden');
    }
    if (txtSin) txtSin.classList.remove('hidden');
    if (lbl) lbl.innerText = 'Sin logo configurado';
    if (btnRemover) btnRemover.classList.add('hidden');
  }

  document.getElementById('modal-editar-org').classList.remove('hidden');
  refrescarIconos();
}

async function guardarEdicionOrg(event) {
  event.preventDefault();
  const id = document.getElementById('edit-org-id').value;
  const nombre = document.getElementById('edit-org-nombre').value.trim();
  const tipo_organizacion = document.getElementById('edit-org-tipo').value;
  const licencias_asignadas = parseInt(document.getElementById('edit-org-licencias').value);

  const radioConDominio = document.querySelector('input[name="edit-org-tipo-dominio"][value="especifico"]')?.checked;
  let dominio_permitido = "LIBRE";
  if (radioConDominio) {
    const domRaw = document.getElementById('edit-org-dominio').value.trim().replace('@', '');
    if (!domRaw) {
      return mostrarToast('Ingresa el dominio autorizado o selecciona "Sin Dominio".', 'advertencia');
    }
    dominio_permitido = domRaw;
  }

  const payload = {
    nombre,
    tipo_organizacion,
    dominio_permitido,
    licencias_asignadas,
    max_administradores: 2,
    max_mentores: 20
  };

  if (editOrgLogoBase64) {
    payload.logo_url = editOrgLogoBase64;
  } else if (editOrgLogoEliminado) {
    payload.logo_url = "__REMOVE__";
  }

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/organizaciones/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al actualizar institución');

    // Actualizar datos en memoria local
    const orgIndex = allOrganizations.findIndex(o => parseInt(o.id) === parseInt(id));
    if (orgIndex !== -1) {
      if (editOrgLogoBase64) allOrganizations[orgIndex].logo_url = editOrgLogoBase64;
      else if (editOrgLogoEliminado) allOrganizations[orgIndex].logo_url = null;
    }

    if (currentUser && currentUser.organizacion_id && parseInt(currentUser.organizacion_id) === parseInt(id)) {
      if (editOrgLogoBase64) {
        currentUser.org_logo_url = editOrgLogoBase64;
        if (currentUser.organizacion) currentUser.organizacion.logo_url = editOrgLogoBase64;
      } else if (editOrgLogoEliminado) {
        currentUser.org_logo_url = null;
        if (currentUser.organizacion) currentUser.organizacion.logo_url = null;
      }
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      actualizarBrandingOrganizacionUI();
    }

    mostrarToast(`✓ Institución '${nombre}' actualizada. Cupos: ${licencias_asignadas}.`, 'exito');
    cerrarModal('modal-editar-org');
    cargarNodosInstitucionales();
    cargarJerarquia3Columnas();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// Modal Confirmar Eliminar Org
function abrirModalConfirmarEliminar(id, nombre) {
  nodoAEliminar = { id, nombre };
  const label = document.getElementById('label-eliminar-mensaje');
  if (label) {
    label.innerHTML = `⚠️ Estás a punto de eliminar la institución <strong>${nombre}</strong>.<br><br>Esta acción desvinculará a todos sus estudiantes y eliminará sus configuraciones permanentemente.`;
  }
  document.getElementById('modal-confirmar-eliminar').classList.remove('hidden');
  refrescarIconos();
}

async function ejecutarEliminarNodo() {
  if (!nodoAEliminar.id) return;

  const btnEliminar = document.getElementById('btn-ejecutar-eliminar');
  btnEliminar.disabled = true;
  btnEliminar.innerText = 'Eliminando...';

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/organizaciones/${nodoAEliminar.id}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al eliminar');

    mostrarToast(data.mensaje, 'exito');
    cerrarModal('modal-confirmar-eliminar');
    cargarNodosInstitucionales();
    cargarJerarquia3Columnas();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    btnEliminar.disabled = false;
    btnEliminar.innerText = 'Sí, Eliminar';
  }
}

function cargarOrganizacionesEnSelects() {
  const selects = ['excel-org-select', 'mat-asignar-org', 'select-filtro-org-jerarquia', 'edit-user-org'];
  selects.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;

    let html = '';
    if (id === 'mat-asignar-org') html = '<option value="">Todas las instituciones (Global)</option>';
    else if (id === 'select-filtro-org-jerarquia') html = '<option value="">Todas las instituciones</option>';
    
    allOrganizations.forEach(org => {
      html += `<option value="${org.id}">${org.nombre} (@${org.dominio_permitido})</option>`;
    });
    el.innerHTML = html;
  });
}

// =====================================================================
// 5. EXCEL: DESCARGAR PLANTILLA Y CARGA MASIVA MULTI-ROL
// =====================================================================
function descargarPlantillaExcel() {
  window.location.href = `${API_BASE}/api/superadmin/usuarios/descargar-plantilla-excel`;
  mostrarToast('Descargando plantilla oficial en formato Excel (.xlsx)...', 'info');
}

async function procesarCargaExcel(event) {
  event.preventDefault();
  const orgId = document.getElementById('excel-org-select').value;
  const fileInput = document.getElementById('excel-file-input');
  const btnSubmit = document.getElementById('btn-submit-excel');

  if (!orgId) return mostrarToast('Selecciona una institución destino.', 'advertencia');
  if (!fileInput.files || fileInput.files.length === 0) {
    return mostrarToast('Selecciona un archivo Excel (.xlsx) o CSV.', 'advertencia');
  }

  const modoRadio = document.querySelector('input[name="modo-dominio-excel"]:checked');
  const modo_dominio = modoRadio ? modoRadio.value : 'flexible';

  const formData = new FormData();
  formData.append('organizacion_id', orgId);
  formData.append('modo_dominio', modo_dominio);
  formData.append('archivo', fileInput.files[0]);

  btnSubmit.disabled = true;
  btnSubmit.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Importando (${modo_dominio})...</span>`;
  refrescarIconos();

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/usuarios/cargar-excel`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error procesando el archivo Excel');

    const des = data.desglose || {};
    mostrarToast(`✓ ${data.registrados} usuarios registrados (${des.administradores || 0} Admins, ${des.mentores || 0} Mentores, ${des.aprendices || 0} Aprendices).`, 'exito');
    
    if (data.alertas && data.alertas.length > 0) {
      data.alertas.slice(0, 3).forEach(a => mostrarToast(a, 'advertencia'));
    }

    fileInput.value = '';
    cargarJerarquia3Columnas(orgId);
    cargarNodosInstitucionales();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.innerHTML = `<i data-lucide="upload" class="w-4 h-4"></i><span>Procesar y Cargar Base de Datos Excel</span>`;
    refrescarIconos();
  }
}

// =====================================================================
// 6. TABLERO DE JERARQUÍA EN 3 COLUMNAS & DIRECTORIO
// =====================================================================
async function cargarJerarquia3Columnas(orgId = null) {
  try {
    const cardExcel = document.getElementById('card-carga-masiva-excel');
    const btnPlantilla = document.getElementById('btn-descargar-plantilla-excel');
    const esSuperAdmin = currentUser && currentUser.rol === 'Super Administrador';
    if (cardExcel) {
      if (esSuperAdmin) cardExcel.classList.remove('hidden');
      else cardExcel.classList.add('hidden');
    }
    if (btnPlantilla) {
      if (esSuperAdmin) btnPlantilla.classList.remove('hidden');
      else btnPlantilla.classList.add('hidden');
    }

    let url = `${API_BASE}/api/usuarios/jerarquia`;
    if (orgId) url += `?organizacion_id=${orgId}`;

    const res = await fetch(url);
    const json = await res.json();
    allHierarchyData = json;

    renderizarTableroJerarquico(json);
    renderizarDirectorioTabular(json);
  } catch (e) {
    console.error('Error cargando jerarquías:', e);
  }
}

function cambiarFiltroOrgJerarquia() {
  const orgId = document.getElementById('select-filtro-org-jerarquia').value;
  cargarJerarquia3Columnas(orgId || null);
}

function cambiarModoVistaDirectorio(modo) {
  const contenedor3Col = document.getElementById('contenedor-jerarquia-3col');
  const contenedorTabular = document.getElementById('contenedor-directorio-tabular');
  const btn3Col = document.getElementById('btn-view-3col');
  const btnTab = document.getElementById('btn-view-table');

  if (modo === '3col') {
    contenedor3Col.classList.remove('hidden');
    contenedorTabular.classList.add('hidden');
    btn3Col.className = 'px-3 py-1.5 rounded-lg font-bold bg-white text-[#0a192f] shadow-sm transition-all flex items-center gap-1.5';
    btnTab.className = 'px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:text-slate-900 transition-all flex items-center gap-1.5';
  } else {
    contenedor3Col.classList.add('hidden');
    contenedorTabular.classList.remove('hidden');
    btnTab.className = 'px-3 py-1.5 rounded-lg font-bold bg-white text-[#0a192f] shadow-sm transition-all flex items-center gap-1.5';
    btn3Col.className = 'px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:text-slate-900 transition-all flex items-center gap-1.5';
  }
}

async function cambiarCargoUsuarioTiempoReal(usuarioId, nuevoRol) {
  if (!usuarioId || !nuevoRol) return;
  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${usuarioId}/cambiar-cargo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rol: nuevoRol })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al actualizar el cargo');

    mostrarToast(`✓ ${data.mensaje}`, 'exito');

    if (currentUser && currentUser.id == usuarioId) {
      currentUser.rol = nuevoRol;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      configurarVistasSegunRol(true);
      actualizarPerfilSidebar();
    }

    cargarJerarquia3Columnas();
    cargarNodosInstitucionales();
    if (typeof cargarVistaAdminConvenio === 'function') cargarVistaAdminConvenio();
    if (typeof cargarMentoresRendimientoAdmin === 'function') cargarMentoresRendimientoAdmin();
  } catch (err) {
    mostrarToast(err.message, 'error');
    cargarJerarquia3Columnas();
    if (typeof cargarVistaAdminConvenio === 'function') cargarVistaAdminConvenio();
  }
}

function renderizarTableroJerarquico(data) {
  const admins = data.administradores || [];
  const mentores = data.mentores || [];
  const aprendices = data.aprendices || [];

  document.getElementById('badge-total-admins').innerText = admins.length;
  document.getElementById('badge-total-mentores').innerText = mentores.length;
  document.getElementById('badge-total-aprendices').innerText = aprendices.length;

  const puedeEditarCargos = currentUser && (currentUser.rol === 'Super Administrador' || currentUser.rol === 'Administrador');

  // Render Columna 1: Administradores
  const contAdmins = document.getElementById('lista-jerarquia-admins');
  if (admins.length === 0) {
    contAdmins.innerHTML = `
      <div class="py-10 px-4 text-center rounded-2xl border border-dashed border-slate-200/80 bg-slate-50/50 flex flex-col items-center justify-center">
        <i data-lucide="shield-alert" class="w-7 h-7 text-slate-300 mb-2"></i>
        <p class="text-xs font-bold text-slate-600">Sin administradores</p>
        <p class="text-[10px] text-slate-400 mt-0.5">No hay administradores registrados en este filtro.</p>
      </div>`;
  } else {
    contAdmins.innerHTML = admins.map(u => `
      <div class="card-jerarquia card-jerarquia-admin">
        <div class="flex items-start justify-between">
          <div class="flex items-center space-x-2.5 min-w-0">
            <div class="w-9 h-9 rounded-xl bg-sky-50 text-sky-700 font-bold flex items-center justify-center text-xs overflow-hidden shrink-0 border border-sky-200 shadow-2xs">
              ${u.foto_perfil ? `<img src="${u.foto_perfil}" alt="${escapeHtml(u.nombre)}" class="w-full h-full object-cover">` : obtenerIniciales(u.nombre)}
            </div>
            <div class="min-w-0">
              <h4 class="text-xs font-bold nodo-org-title leading-snug truncate">${escapeHtml(u.nombre)}</h4>
              <p class="text-[11px] font-mono text-cyan-700 truncate">${u.correo}</p>
            </div>
          </div>
          ${(puedeEditarCargos && u.rol !== 'Super Administrador') ? `
            <div class="flex items-center space-x-1 shrink-0">
              <button onclick="abrirModalEditarUsuario(${u.id}, '${escapeHtml(u.nombre)}', '${u.correo}', '${u.rol}', ${u.organizacion_id || 'null'}, null)" class="btn-icon-edit" title="Editar Cargo">
                <i data-lucide="edit-2" class="w-3 h-3"></i>
              </button>
              <button onclick="abrirModalEliminarUsuario(${u.id}, '${escapeHtml(u.nombre)}', '${u.correo}')" class="btn-icon-delete" title="Eliminar / Corregir">
                <i data-lucide="trash-2" class="w-3 h-3"></i>
              </button>
            </div>
          ` : ''}
        </div>
        <div class="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] gap-2">
          ${(puedeEditarCargos && u.rol !== 'Super Administrador') ? `
            <select onchange="cambiarCargoUsuarioTiempoReal(${u.id}, this.value)" class="px-2 py-1 rounded-lg border border-cyan-300 bg-cyan-50/70 text-[#0a192f] text-[10px] font-bold cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500" title="Cambiar cargo en tiempo real">
              <option value="Administrador" ${u.rol === 'Administrador' ? 'selected' : ''}>🛡️ Administrador</option>
              <option value="Mentor" ${u.rol === 'Mentor' ? 'selected' : ''}>🎓 Mentor</option>
              <option value="Aprendiz" ${u.rol === 'Aprendiz' ? 'selected' : ''}>📘 Aprendiz</option>
            </select>
          ` : `<span class="badge-corp ${obtenerClaseBadgeRol(u.rol)} text-[10px]">${u.rol}</span>`}
          <span class="text-slate-500 font-medium text-[10px] truncate max-w-[130px] flex items-center gap-1">
            <i data-lucide="building-2" class="w-3 h-3 text-slate-400"></i>
            <span>${u.organizacion_nombre || 'Corporación Universitaria Minuto de Dios'}</span>
          </span>
        </div>
      </div>
    `).join('');
  }

  // Render Columna 2: Mentores
  const contMentores = document.getElementById('lista-jerarquia-mentores');
  if (mentores.length === 0) {
    contMentores.innerHTML = `
      <div class="py-10 px-4 text-center rounded-2xl border border-dashed border-slate-200/80 bg-slate-50/50 flex flex-col items-center justify-center">
        <i data-lucide="graduation-cap" class="w-7 h-7 text-slate-300 mb-2"></i>
        <p class="text-xs font-bold text-slate-600">Sin mentores registrados</p>
        <p class="text-[10px] text-slate-400 mt-0.5">Añade o importa mentores para tutoría académica.</p>
      </div>`;
  } else {
    contMentores.innerHTML = mentores.map(m => `
      <div class="card-jerarquia card-jerarquia-mentor">
        <div class="flex items-start justify-between">
          <div class="flex items-center space-x-2.5 min-w-0">
            <div class="w-9 h-9 rounded-xl bg-cyan-50 text-cyan-700 font-bold flex items-center justify-center text-xs overflow-hidden shrink-0 border border-cyan-200 shadow-2xs">
              ${m.foto_perfil ? `<img src="${m.foto_perfil}" alt="${escapeHtml(m.nombre)}" class="w-full h-full object-cover">` : obtenerIniciales(m.nombre)}
            </div>
            <div class="min-w-0">
              <h4 class="text-xs font-bold nodo-org-title leading-snug truncate">${escapeHtml(m.nombre)}</h4>
              <p class="text-[11px] font-mono text-cyan-700 truncate">${m.correo}</p>
            </div>
          </div>
          ${puedeEditarCargos ? `
            <div class="flex items-center space-x-1 shrink-0">
              <button onclick="abrirModalEditarUsuario(${m.id}, '${escapeHtml(m.nombre)}', '${m.correo}', '${m.rol}', ${m.organizacion_id || 'null'}, null)" class="btn-icon-edit" title="Editar Cargo">
                <i data-lucide="edit-2" class="w-3 h-3"></i>
              </button>
              <button onclick="abrirModalEliminarUsuario(${m.id}, '${escapeHtml(m.nombre)}', '${m.correo}')" class="btn-icon-delete" title="Eliminar">
                <i data-lucide="trash-2" class="w-3 h-3"></i>
              </button>
            </div>
          ` : ''}
        </div>
        <div class="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] gap-2">
          ${puedeEditarCargos ? `
            <select onchange="cambiarCargoUsuarioTiempoReal(${m.id}, this.value)" class="px-2 py-1 rounded-lg border border-cyan-300 bg-cyan-50/70 text-[#0a192f] text-[10px] font-bold cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500" title="Cambiar cargo en tiempo real">
              <option value="Administrador" ${m.rol === 'Administrador' ? 'selected' : ''}>🛡️ Administrador</option>
              <option value="Mentor" ${m.rol === 'Mentor' ? 'selected' : ''}>🎓 Mentor</option>
              <option value="Aprendiz" ${m.rol === 'Aprendiz' ? 'selected' : ''}>📘 Aprendiz</option>
            </select>
          ` : ''}
          <span class="px-2 py-0.5 rounded-full bg-cyan-50 text-cyan-800 font-bold text-[10px] border border-cyan-200 flex items-center gap-1">
            <i data-lucide="users" class="w-3 h-3 text-cyan-600"></i>
            <span>${m.total_aprendices || 0} aprendices</span>
          </span>
        </div>
        ${puedeEditarCargos ? `
          <button onclick="abrirModalOrganizarGrupos(${m.organizacion_id || 13}, ${m.id})" class="btn-ver-metricas mt-2.5" title="Ver y reorganizar aprendices asignados a este mentor">
            <i data-lucide="network" class="w-3.5 h-3.5"></i>
            <span>Gestionar Grupo de Aprendices</span>
          </button>
        ` : ''}
      </div>
    `).join('');
  }

  // Render Columna 3: Aprendices
  const contAprendices = document.getElementById('lista-jerarquia-aprendices');
  if (aprendices.length === 0) {
    contAprendices.innerHTML = `
      <div class="py-10 px-4 text-center rounded-2xl border border-dashed border-slate-200/80 bg-slate-50/50 flex flex-col items-center justify-center">
        <i data-lucide="users" class="w-7 h-7 text-slate-300 mb-2"></i>
        <p class="text-xs font-bold text-slate-600">Sin aprendices</p>
        <p class="text-[10px] text-slate-400 mt-0.5">No hay aprendices registrados en este filtro.</p>
      </div>`;
  } else {
    contAprendices.innerHTML = aprendices.map(a => {
      const avance = Math.round(a.promedio_avance || 0);
      return `
        <div class="card-jerarquia card-jerarquia-aprendiz">
          <div class="flex items-start justify-between">
            <div class="flex items-center space-x-2.5 min-w-0">
              <div class="w-9 h-9 rounded-xl bg-blue-50 text-blue-800 font-bold flex items-center justify-center text-xs overflow-hidden shrink-0 border border-blue-200 shadow-2xs">
                ${a.foto_perfil ? `<img src="${a.foto_perfil}" alt="${escapeHtml(a.nombre)}" class="w-full h-full object-cover">` : obtenerIniciales(a.nombre)}
              </div>
              <div class="min-w-0">
                <h4 class="text-xs font-bold nodo-org-title leading-snug truncate">${escapeHtml(a.nombre)}</h4>
                <p class="text-[11px] font-mono text-cyan-700 truncate">${a.correo}</p>
              </div>
            </div>
            ${puedeEditarCargos ? `
              <div class="flex items-center space-x-1 shrink-0">
                <button onclick="abrirModalEditarUsuario(${a.id}, '${escapeHtml(a.nombre)}', '${a.correo}', '${a.rol}', ${a.organizacion_id || 'null'}, ${a.mentor_id || 'null'})" class="btn-icon-edit" title="Editar / Reasignar">
                  <i data-lucide="edit-2" class="w-3 h-3"></i>
                </button>
                <button onclick="abrirModalEliminarUsuario(${a.id}, '${escapeHtml(a.nombre)}', '${a.correo}')" class="btn-icon-delete" title="Eliminar">
                  <i data-lucide="trash-2" class="w-3 h-3"></i>
                </button>
              </div>
            ` : ''}
          </div>

          <div class="mt-2.5 pt-2 border-t border-slate-100">
            ${puedeEditarCargos ? `
              <div class="flex items-center justify-between mb-2">
                <span class="text-[10px] font-bold text-slate-500">Cargo en Tiempo Real:</span>
                <select onchange="cambiarCargoUsuarioTiempoReal(${a.id}, this.value)" class="px-2 py-0.5 rounded-lg border border-cyan-300 bg-cyan-50/70 text-[#0a192f] text-[10px] font-bold cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500" title="Cambiar cargo en tiempo real">
                  <option value="Administrador" ${a.rol === 'Administrador' ? 'selected' : ''}>🛡️ Administrador</option>
                  <option value="Mentor" ${a.rol === 'Mentor' ? 'selected' : ''}>🎓 Mentor</option>
                  <option value="Aprendiz" ${a.rol === 'Aprendiz' ? 'selected' : ''}>📘 Aprendiz</option>
                </select>
              </div>
            ` : ''}
            <div class="flex items-center justify-between text-[10px] text-slate-500 mb-1">
              <span>Mentor: <strong class="text-cyan-700 font-semibold">${a.mentor_nombre || 'alvaro Niño'}</strong></span>
              <span class="font-bold text-[#0a192f]">${avance}%</span>
            </div>
            <div class="progress-track-cyan">
              <div class="progress-bar-cyan" style="width: ${avance}%;"></div>
            </div>
            <div class="flex items-center justify-between text-[10px] text-slate-400 mt-1.5">
              <span>${a.total_minutos || 0} min dedicados</span>
              <span class="font-semibold text-cyan-700">${a.total_cursos || 0} colecciones</span>
            </div>
            <button onclick="abrirDetalleProgresoAprendiz(${a.id})" class="btn-ver-metricas mt-2.5">
              <i data-lucide="trending-up" class="w-3.5 h-3.5"></i>
              <span>Ver Avance & Métricas</span>
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  refrescarIconos();
}

function renderizarDirectorioTabular(data) {
  const todos = [
    ...(data.administradores || []),
    ...(data.mentores || []),
    ...(data.aprendices || [])
  ];

  const tbody = document.getElementById('tabla-usuarios-body');
  if (!tbody) return;

  const puedeEditarCargos = currentUser && (currentUser.rol === 'Super Administrador' || currentUser.rol === 'Administrador');

  if (todos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="p-4 text-center text-slate-400">No hay usuarios para mostrar.</td></tr>`;
    return;
  }

  tbody.innerHTML = todos.map(u => `
    <tr class="hover:bg-slate-50 transition-colors">
      <td class="py-2.5 text-slate-400 font-mono">#${u.id}</td>
      <td class="py-2.5">
        <div class="flex items-center gap-2.5">
          <div class="w-7 h-7 rounded-full bg-slate-100 text-[#0a192f] font-bold flex items-center justify-center text-[10px] overflow-hidden shrink-0 border border-slate-200 shadow-2xs">
            ${u.foto_perfil ? `<img src="${u.foto_perfil}" alt="${escapeHtml(u.nombre)}" class="w-full h-full object-cover">` : obtenerIniciales(u.nombre)}
          </div>
          <span class="font-bold text-[#0a192f] text-xs">${u.nombre}</span>
        </div>
      </td>
      <td class="py-2.5 font-mono text-cyan-700 text-xs">${u.correo}</td>
      <td class="py-2.5">
        ${(puedeEditarCargos && u.rol !== 'Super Administrador') ? `
          <select onchange="cambiarCargoUsuarioTiempoReal(${u.id}, this.value)" class="px-2.5 py-1 rounded-lg border border-cyan-300 bg-cyan-50/70 text-[#0a192f] text-xs font-bold cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500">
            <option value="Administrador" ${u.rol === 'Administrador' ? 'selected' : ''}>🛡️ Administrador</option>
            <option value="Mentor" ${u.rol === 'Mentor' ? 'selected' : ''}>🎓 Mentor</option>
            <option value="Aprendiz" ${u.rol === 'Aprendiz' ? 'selected' : ''}>📘 Aprendiz</option>
          </select>
        ` : `<span class="badge-corp ${obtenerClaseBadgeRol(u.rol)}">${u.rol}</span>`}
      </td>
      <td class="py-2.5 text-slate-600 text-xs">${u.organizacion_nombre || 'Corporación Universitaria Minuto de Dios'}</td>
      <td class="py-2.5 text-slate-500 text-xs">${u.mentor_nombre || (u.mentor_id ? `#${u.mentor_id}` : '-')}</td>
      <td class="py-2.5 text-right">
        ${puedeEditarCargos ? `
          <div class="flex items-center justify-end space-x-1">
            ${u.rol !== 'Super Administrador' ? `
              <button onclick="abrirModalEditarUsuario(${u.id}, '${escapeHtml(u.nombre)}', '${u.correo}', '${u.rol}', ${u.organizacion_id || 'null'}, ${u.mentor_id || 'null'})" class="btn-icon-edit" title="Editar">
                <i data-lucide="edit-2" class="w-3 h-3"></i>
              </button>
              <button onclick="abrirModalEliminarUsuario(${u.id}, '${escapeHtml(u.nombre)}', '${u.correo}')" class="btn-icon-delete" title="Eliminar">
                <i data-lucide="trash-2" class="w-3 h-3"></i>
              </button>
            ` : `<span class="text-[10px] font-mono text-slate-400 italic px-2">Protegido</span>`}
          </div>
        ` : '-'}
      </td>
    </tr>
  `).join('');

  refrescarIconos();
}

function filtrarJerarquia() {
  const inputEl = document.getElementById('input-buscar-jerarquia');
  const query = inputEl ? inputEl.value.toLowerCase().trim() : '';
  if (!query) {
    return renderizarTableroJerarquico(allHierarchyData);
  }

  const matchFilter = (u) => (
    u.nombre.toLowerCase().includes(query) ||
    u.correo.toLowerCase().includes(query) ||
    u.rol.toLowerCase().includes(query) ||
    (u.organizacion_nombre && u.organizacion_nombre.toLowerCase().includes(query)) ||
    (u.mentor_nombre && u.mentor_nombre.toLowerCase().includes(query))
  );

  const filteredData = {
    administradores: (allHierarchyData.administradores || []).filter(matchFilter),
    mentores: (allHierarchyData.mentores || []).filter(matchFilter),
    aprendices: (allHierarchyData.aprendices || []).filter(matchFilter),
  };

  renderizarTableroJerarquico(filteredData);
}

// =====================================================================
// 7. EDICIÓN Y ELIMINACIÓN DE USUARIOS (CORREGIR CARGOS DUPLICADOS)
// =====================================================================
function abrirModalEditarUsuario(id, nombre, correo, rol, orgId, mentorId) {
  if (rol === 'Super Administrador') {
    return mostrarToast('La cuenta de Super Administrador está protegida y no puede ser modificada desde la jerarquía.', 'advertencia');
  }

  document.getElementById('edit-user-id').value = id;
  document.getElementById('edit-user-nombre').value = nombre;
  document.getElementById('edit-user-correo').value = correo;
  document.getElementById('edit-user-rol').value = rol;

  // Llenar select de organizaciones
  const selOrg = document.getElementById('edit-user-org');
  if (selOrg) {
    if (allOrganizations && allOrganizations.length > 0) {
      selOrg.innerHTML = allOrganizations.map(o => `<option value="${o.id}" ${o.id == orgId ? 'selected' : ''}>${o.nombre}</option>`).join('');
    } else if (adminConvenioData && adminConvenioData.organizacion) {
      selOrg.innerHTML = `<option value="${adminConvenioData.organizacion.id}" selected>${adminConvenioData.organizacion.nombre}</option>`;
    }
  }

  // Llenar select de mentores de esa organización
  const selMentor = document.getElementById('edit-user-mentor');
  if (selMentor) {
    let mentoresDisponibles = (allHierarchyData.mentores || []).filter(m => !orgId || m.organizacion_id == orgId);
    if (mentoresDisponibles.length === 0 && adminConvenioData && adminConvenioData.mentores) {
      mentoresDisponibles = adminConvenioData.mentores;
    }
    selMentor.innerHTML = `<option value="">Sin mentor asignado</option>` + mentoresDisponibles.map(m => `
      <option value="${m.id}" ${m.id == mentorId ? 'selected' : ''}>${m.nombre} (${m.correo})</option>
    `).join('');
  }

  // Mostrar selector de mentor solo si es aprendiz
  const contMentor = document.getElementById('container-edit-mentor');
  if (contMentor) {
    contMentor.style.display = (rol === 'Aprendiz') ? 'block' : 'none';
  }

  document.getElementById('modal-editar-usuario').classList.remove('hidden');
}

async function guardarEdicionUsuario(event) {
  event.preventDefault();
  const id = document.getElementById('edit-user-id').value;
  const nombre = document.getElementById('edit-user-nombre').value.trim();
  const correo = document.getElementById('edit-user-correo').value.trim();
  const rol = document.getElementById('edit-user-rol').value;

  if (rol === 'Super Administrador' || !['Administrador', 'Mentor', 'Aprendiz'].includes(rol)) {
    return mostrarToast('No se puede asignar el rol de Super Administrador. Selecciona Administrador, Mentor o Aprendiz.', 'advertencia');
  }

  const orgVal = document.getElementById('edit-user-org').value;
  const organizacion_id = orgVal ? parseInt(orgVal) : null;
  const mentorVal = document.getElementById('edit-user-mentor').value;
  const mentor_id = (rol === 'Aprendiz' && mentorVal) ? parseInt(mentorVal) : null;

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/usuarios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, correo, rol, organizacion_id, mentor_id })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al actualizar usuario');

    mostrarToast(`✓ Usuario '${nombre}' actualizado exitosamente con rol '${rol}'.`, 'exito');
    cerrarModal('modal-editar-usuario');

    // Si el usuario editado es la sesión activa en esta ventana, actualizar rol de inmediato
    if (currentUser && currentUser.id == id) {
      currentUser.rol = rol;
      currentUser.nombre = nombre;
      currentUser.correo = correo;
      currentUser.organizacion_id = organizacion_id;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      configurarVistasSegunRol(true);
      actualizarPerfilSidebar();
    }

    cargarJerarquia3Columnas();
    cargarNodosInstitucionales();
    if (typeof cargarVistaAdminConvenio === 'function') cargarVistaAdminConvenio();
    if (typeof cargarMentoresRendimientoAdmin === 'function') cargarMentoresRendimientoAdmin();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function abrirModalEliminarUsuario(id, nombre, correo) {
  usuarioAEliminar = { id, nombre, correo };
  const label = document.getElementById('label-eliminar-usuario-msg');
  if (label) {
    label.innerHTML = `⚠️ Estás a punto de eliminar al usuario <strong>${nombre}</strong> (${correo}).<br><br>Se respaldará automáticamente en la Papelera de Integrantes y se desvinculará de las clases.`;
  }
  document.getElementById('modal-confirmar-eliminar-usuario').classList.remove('hidden');
}

async function ejecutarEliminarUsuario() {
  if (!usuarioAEliminar.id) return;

  const btn = document.getElementById('btn-ejecutar-eliminar-usuario');
  btn.disabled = true;
  btn.innerText = 'Eliminando...';

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/usuarios/${usuarioAEliminar.id}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al eliminar usuario');

    mostrarToast(`✓ Usuario '${usuarioAEliminar.nombre}' eliminado correctamente.`, 'exito');
    cerrarModal('modal-confirmar-eliminar-usuario');
    cargarJerarquia3Columnas();
    cargarNodosInstitucionales();
    if (typeof cargarVistaAdminConvenio === 'function') cargarVistaAdminConvenio();
    if (typeof cargarMentoresRendimientoAdmin === 'function') cargarMentoresRendimientoAdmin();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Sí, Eliminar';
  }
}

// =====================================================================
// 8. VISTA APRENDIZ: RUTAS & PROGRESO REAL, BANNER Y QUIZZES
// =====================================================================
let aprendizQuizzesActuales = [];

async function cargarCursosAprendiz() {
  if (!currentUser) return;
  const gridCursos = document.getElementById('grid-cursos-aprendiz');
  const gridQuizzes = document.getElementById('grid-quizzes-aprendiz');
  const badgeTotalQuizzes = document.getElementById('badge-total-quizzes-aprendiz');

  try {
    const res = await fetch(`${API_BASE}/api/aprendiz/progreso/${currentUser.id}`);
    const json = await res.json();
    
    // Extraer estructura enriquecida
    const estudiante = json.estudiante || json.usuario || (json.data && json.data.estudiante) || currentUser;
    const cursos = Array.isArray(json.cursos) ? json.cursos : (Array.isArray(json.data) ? json.data : (json.data && json.data.cursos ? json.data.cursos : []));
    const quizzes = Array.isArray(json.quizzes) ? json.quizzes : (json.data && json.data.quizzes ? json.data.quizzes : []);
    aprendizQuizzesActuales = quizzes;

    // Actualizar Banner Superior
    const orgNombreEl = document.getElementById('aprendiz-org-nombre');
    const mentorNombreEl = document.getElementById('aprendiz-mentor-nombre');
    const mentorCorreoEl = document.getElementById('aprendiz-mentor-correo');
    const rachaEl = document.getElementById('aprendiz-racha-semanas');
    const tiempoEl = document.getElementById('aprendiz-tiempo-dedicado');
    const saludoEl = document.getElementById('aprendiz-saludo-nombre');
    const txtRachaEl = document.getElementById('texto-estado-racha');
    const iconoRachaEl = document.getElementById('badge-icono-racha');

    if (saludoEl) saludoEl.innerText = `¡Hola, ${estudiante.nombre || currentUser.nombre}!`;
    if (orgNombreEl) orgNombreEl.innerText = estudiante.organizacion_nombre || currentUser.organizacion_nombre || 'Institución Registrada';
    
    if (mentorNombreEl) {
      if (estudiante.mentor_nombre) {
        mentorNombreEl.innerText = estudiante.mentor_nombre;
        if (mentorCorreoEl) mentorCorreoEl.innerText = `(${estudiante.mentor_correo || ''})`;
      } else {
        mentorNombreEl.innerText = 'Mentor pendiente de asignación';
        if (mentorCorreoEl) mentorCorreoEl.innerText = '';
      }
    }

    const mentorAvatarEl = document.getElementById('aprendiz-mentor-avatar');
    if (mentorAvatarEl) {
      if (estudiante.mentor_foto_perfil) {
        mentorAvatarEl.innerHTML = `<img src="${estudiante.mentor_foto_perfil}" alt="Mentor" class="w-full h-full object-cover">`;
      } else if (estudiante.mentor_nombre) {
        mentorAvatarEl.innerHTML = `<span class="text-xs font-bold text-cyan-300">${obtenerIniciales(estudiante.mentor_nombre)}</span>`;
      } else {
        mentorAvatarEl.innerHTML = `<i data-lucide="graduation-cap" class="w-4 h-4"></i>`;
      }
    }

    const rachaSemanas = (estudiante.racha_semanas !== undefined) ? estudiante.racha_semanas : (currentUser.racha_semanas !== undefined ? currentUser.racha_semanas : 5);
    const tiempoMinutos = estudiante.tiempo_dedicado_minutos || estudiante.minutos_dedicados_totales || currentUser.minutos_dedicados_totales || 0;
    if (rachaEl) rachaEl.innerText = rachaSemanas;
    if (tiempoEl) tiempoEl.innerText = tiempoMinutos;

    if (txtRachaEl) {
      if (rachaSemanas >= 5) {
        if (iconoRachaEl) iconoRachaEl.innerText = '🎉';
        txtRachaEl.innerHTML = `<strong class="text-amber-300">¡Racha de 5 Semanas Lograda!</strong> Tienes desbloqueados todos los temas temáticos y fotos personalizadas en tu perfil.`;
      } else {
        if (iconoRachaEl) iconoRachaEl.innerText = '🔥';
        txtRachaEl.innerHTML = `Llevas <strong>${rachaSemanas}/5 semanas</strong> de racha continua para desbloquear temas festivos y fotos personalizadas.`;
      }
    }

    // Renderizar Cursos Microsoft Learn (Sin test simulado, directo a la plataforma)
    if (gridCursos) {
      if (cursos.length === 0) {
        gridCursos.innerHTML = `<div class="p-8 text-center text-slate-400 col-span-full border border-dashed border-slate-200 rounded-xl bg-white">No tienes rutas de Microsoft asignadas actualmente.</div>`;
      } else {
        gridCursos.innerHTML = cursos.map(c => {
          const totMod = c.total_modulos || 3;
          let modComp = (c.modulos_completados !== undefined && c.modulos_completados !== null) ? c.modulos_completados : 0;
          let avance = (c.porcentaje_avance !== undefined && c.porcentaje_avance !== null) ? Math.round(c.porcentaje_avance) : 0;
          if (modComp > 0 && avance === 0) {
            avance = Math.round((modComp / totMod) * 100);
          } else if (avance > 0 && modComp === 0) {
            modComp = Math.max(1, Math.round((avance / 100) * totMod));
          }
          const completado = avance >= 100 || modComp >= totMod;
          const enProgreso = (avance > 0 || modComp > 0) && !completado;

          // Generar pastillas interactivas para cada módulo de la colección
          let modulosBotonesHtml = '';
          for (let m = 1; m <= totMod; m++) {
            const isActivo = m <= modComp;
            modulosBotonesHtml += `
              <button type="button" 
                onclick="marcarModuloColeccion(${c.id}, ${m}, ${totMod})"
                class="px-2.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${isActivo ? 'bg-cyan-600 text-white shadow-xs hover:bg-cyan-700' : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'}"
                title="Haz clic para marcar avance en el Módulo ${m}">
                <i data-lucide="${isActivo ? 'check-circle-2' : 'circle'}" class="w-3.5 h-3.5 ${isActivo ? 'text-white' : 'text-slate-400'}"></i>
                <span>Módulo ${m}</span>
              </button>
            `;
          }

          return `
            <div class="corp-card p-6 flex flex-col justify-between hover:shadow-md transition-shadow border ${completado ? 'border-emerald-300' : (enProgreso ? 'border-cyan-300' : 'border-slate-200')}">
              <div>
                <div class="flex items-center justify-between mb-2">
                  <span class="text-[10px] font-bold text-cyan-600 uppercase tracking-wider">${c.tipo_material || 'Colección Microsoft Learn'}</span>
                  <span class="text-[10px] font-bold px-2.5 py-0.5 rounded-full ${completado ? 'bg-emerald-100 text-emerald-800' : (enProgreso ? 'bg-cyan-100 text-cyan-800' : 'bg-slate-100 text-slate-600')}">
                    ${completado ? '🏆 Completado (100%)' : (enProgreso ? `⚡ En Progreso (${avance}%)` : 'Disponible')}
                  </span>
                </div>
                <h3 class="text-base font-bold text-[#0a192f] mb-3 leading-snug">${c.titulo}</h3>

                <!-- Barra de Progreso del Alumno -->
                <div class="progress-track-cyan mb-2">
                  <div class="progress-bar-cyan" style="width: ${avance}%;"></div>
                </div>
                <div class="flex items-center justify-between text-[11px] text-slate-500 font-medium mb-3">
                  <span>Progreso en Ruta: <strong class="text-[#0a192f]">${avance}%</strong> (${modComp}/${totMod} módulos)</span>
                  <span>${c.tiempo_dedicado_minutos || 0} min dedicados</span>
                </div>

                <!-- Selector Interactivo de Módulos de la Colección -->
                <div class="p-3 bg-slate-50 rounded-xl border border-slate-200/80 mb-2 space-y-1.5">
                  <div class="flex items-center justify-between text-[11px]">
                    <span class="font-bold text-slate-700">Módulos de la Colección:</span>
                    <span class="text-[10px] text-slate-500 font-medium">Toca un módulo para registrar tu avance</span>
                  </div>
                  <div class="flex flex-wrap items-center gap-1.5 pt-1">
                    ${modulosBotonesHtml}
                  </div>
                </div>
              </div>

              <div class="pt-3 border-t border-slate-100 mt-2 flex flex-col sm:flex-row items-center gap-2">
                <a href="${c.enlace_url || '#'}" target="_blank" onclick="notificarAperturaMicrosoft('${c.titulo}')" class="w-full py-2.5 rounded-xl bg-[#0a192f] hover:bg-[#0f273f] text-white text-xs font-bold flex items-center justify-center gap-2 transition-all shadow-sm">
                  <span>Estudiar en Microsoft Learn</span>
                  <i data-lucide="external-link" class="w-3.5 h-3.5 text-cyan-400"></i>
                </a>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Renderizar Quizzes de Mentores
    if (badgeTotalQuizzes) badgeTotalQuizzes.innerText = `${quizzes.length} asignados`;
    if (gridQuizzes) {
      if (quizzes.length === 0) {
        gridQuizzes.innerHTML = `
          <div class="col-span-full p-8 text-center bg-white border border-dashed border-slate-200 rounded-2xl">
            <span class="text-3xl mb-2 block">📝</span>
            <h4 class="text-xs font-bold text-slate-800">Aún no tienes Quizzes o Evaluaciones asignados</h4>
            <p class="text-[11px] text-slate-400 mt-1">Tu tutor creará cuestionarios y retos para evaluar tus conocimientos de las rutas.</p>
          </div>
        `;
      } else {
        gridQuizzes.innerHTML = quizzes.map(q => {
          const completado = Boolean(q.completado);
          const calif = (q.calificacion !== null && q.calificacion !== undefined) ? Math.round(q.calificacion) : 0;
          const aprobado = q.aprobado || (calif >= 70);
          return `
            <div class="corp-card p-5 flex flex-col justify-between hover:shadow-md transition-shadow border ${completado ? (aprobado ? 'border-emerald-200' : 'border-amber-200') : 'border-purple-200'}">
              <div class="space-y-2.5">
                <div class="flex items-center justify-between">
                  <span class="px-2.5 py-0.5 rounded text-[10px] font-extrabold uppercase ${completado ? (aprobado ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800') : 'bg-purple-100 text-purple-800'}">
                    ${q.tipo || 'Quiz'}
                  </span>
                  <span class="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
                    <i data-lucide="clock" class="w-3 h-3"></i>
                    <span>${q.duracion_minutos || 15} min</span>
                  </span>
                </div>

                <h3 class="text-sm font-bold text-[#0a192f] leading-snug">${q.titulo}</h3>
                <p class="text-[11px] text-slate-500 line-clamp-2">${q.descripcion || 'Evaluación asignada por tu tutor docente.'}</p>

                <div class="p-2.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between text-[11px]">
                  <span class="text-slate-500">Tutor: <strong class="text-slate-700">${q.mentor_nombre || 'Docente'}</strong></span>
                  <span class="text-slate-500 font-bold">${q.preguntas_count || (q.preguntas ? q.preguntas.length : 0)} preguntas</span>
                </div>

                ${completado ? `
                  <div class="p-2.5 rounded-xl ${aprobado ? 'bg-emerald-50 text-emerald-900 border border-emerald-200' : 'bg-amber-50 text-amber-900 border border-amber-200'} flex items-center justify-between text-xs font-bold">
                    <span>Resultado: ${calif}%</span>
                    <span>${aprobado ? '✅ Aprobado' : '⚠️ En Revisión'}</span>
                  </div>
                ` : ''}
              </div>

              <div class="pt-3 border-t border-slate-100 mt-3">
                <button onclick="abrirModalResolverQuiz(${q.id})" class="w-full py-2 rounded-xl ${completado ? 'bg-slate-100 hover:bg-slate-200 text-slate-700' : 'bg-purple-700 hover:bg-purple-800 text-white'} text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-1.5">
                  <i data-lucide="${completado ? 'rotate-ccw' : 'play-circle'}" class="w-4 h-4"></i>
                  <span>${completado ? 'Repetir Quiz' : 'Comenzar Quiz'}</span>
                </button>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    refrescarIconos();
  } catch (e) {
    console.error('Error cargando cursos del aprendiz:', e);
  }
}

// =====================================================================
// JUGADOR INTERACTIVO DE QUIZZES (APRENDICES)
// =====================================================================
let currentQuizActive = null;
let currentQuizPreguntas = [];
let currentQuizIndex = 0;
let currentQuizRespuestas = {};
let quizTimerInterval = null;
let quizSecondsElapsed = 0;

function abrirModalResolverQuiz(quizId) {
  const quiz = (aprendizQuizzesActuales || []).find(q => q.id === quizId);
  if (!quiz) {
    mostrarToast('No se encontró información del quiz seleccionado.', 'error');
    return;
  }

  currentQuizActive = quiz;
  let preguntas = [];
  try {
    preguntas = Array.isArray(quiz.preguntas) ? quiz.preguntas : JSON.parse(quiz.preguntas_json || '[]');
  } catch (e) {
    preguntas = [];
  }

  if (preguntas.length === 0) {
    mostrarToast('Este quiz aún no tiene preguntas configuradas.', 'advertencia');
    return;
  }

  currentQuizPreguntas = preguntas;
  currentQuizIndex = 0;
  currentQuizRespuestas = {};
  quizSecondsElapsed = 0;

  // Resetear vistas
  const elTipo = document.getElementById('player-quiz-tipo');
  const elTit = document.getElementById('player-quiz-titulo');
  if (elTipo) elTipo.innerText = quiz.tipo || 'Quiz';
  if (elTit) elTit.innerText = quiz.titulo;

  const elCuerpo = document.getElementById('player-quiz-cuerpo');
  const elFooter = document.getElementById('player-quiz-footer');
  const elRes = document.getElementById('player-quiz-resultados');
  if (elCuerpo) elCuerpo.classList.remove('hidden');
  if (elFooter) elFooter.classList.remove('hidden');
  if (elRes) elRes.classList.add('hidden');

  // Iniciar Cronómetro
  if (quizTimerInterval) clearInterval(quizTimerInterval);
  quizTimerInterval = setInterval(() => {
    quizSecondsElapsed++;
    const mins = String(Math.floor(quizSecondsElapsed / 60)).padStart(2, '0');
    const secs = String(quizSecondsElapsed % 60).padStart(2, '0');
    const timerEl = document.getElementById('player-quiz-timer-text');
    if (timerEl) timerEl.innerText = `${mins}:${secs}`;
  }, 1000);

  renderizarPreguntaPlayerQuiz();
  const modal = document.getElementById('modal-resolver-quiz');
  if (modal) modal.classList.remove('hidden');
  refrescarIconos();
}

function renderizarPreguntaPlayerQuiz() {
  if (currentQuizPreguntas.length === 0) return;
  const total = currentQuizPreguntas.length;
  const p = currentQuizPreguntas[currentQuizIndex];

  const indEl = document.getElementById('player-quiz-indicador-pregunta');
  if (indEl) indEl.innerText = `Pregunta ${currentQuizIndex + 1} de ${total}`;

  const pct = Math.round(((currentQuizIndex + 1) / total) * 100);
  const barEl = document.getElementById('player-quiz-progress-bar');
  if (barEl) barEl.style.width = `${pct}%`;

  const txtEl = document.getElementById('player-quiz-pregunta-texto');
  if (txtEl) txtEl.innerText = p.pregunta;

  const respuestaSeleccionada = currentQuizRespuestas[currentQuizIndex];
  const container = document.getElementById('player-quiz-opciones-container');

  const letras = ['A', 'B', 'C', 'D'];
  if (container) {
    container.innerHTML = (p.opciones || []).map((opt, idx) => {
      const isSelected = (respuestaSeleccionada === idx);
      return `
        <div onclick="seleccionarOpcionPlayerQuiz(${idx})" class="p-3 rounded-xl border text-xs font-semibold cursor-pointer transition-all flex items-center justify-between ${isSelected ? 'bg-cyan-50 border-cyan-500 text-cyan-950 shadow-sm ring-1 ring-cyan-400' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}">
          <div class="flex items-center gap-3">
            <span class="w-6 h-6 rounded-lg flex items-center justify-center font-bold text-xs ${isSelected ? 'bg-cyan-600 text-white' : 'bg-slate-100 text-slate-600'}">
              ${letras[idx] || (idx + 1)}
            </span>
            <span class="text-xs">${opt}</span>
          </div>
          <div class="w-4 h-4 rounded-full border flex items-center justify-center ${isSelected ? 'border-cyan-600 bg-cyan-600 text-white' : 'border-slate-300'}">
            ${isSelected ? '<i data-lucide="check" class="w-2.5 h-2.5"></i>' : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  const btnAnt = document.getElementById('btn-quiz-anterior');
  const btnSig = document.getElementById('btn-quiz-siguiente');
  const btnFin = document.getElementById('btn-quiz-finalizar');

  if (btnAnt) btnAnt.disabled = (currentQuizIndex === 0);

  if (currentQuizIndex === total - 1) {
    if (btnSig) btnSig.classList.add('hidden');
    if (btnFin) btnFin.classList.remove('hidden');
  } else {
    if (btnSig) btnSig.classList.remove('hidden');
    if (btnFin) btnFin.classList.add('hidden');
  }

  refrescarIconos();
}

function seleccionarOpcionPlayerQuiz(opcionIdx) {
  currentQuizRespuestas[currentQuizIndex] = opcionIdx;
  renderizarPreguntaPlayerQuiz();
}

function navegarPreguntaQuiz(delta) {
  if (delta > 0 && currentQuizRespuestas[currentQuizIndex] === undefined) {
    return mostrarToast('Por favor selecciona una respuesta para avanzar.', 'advertencia');
  }
  const nuevoIdx = currentQuizIndex + delta;
  if (nuevoIdx >= 0 && nuevoIdx < currentQuizPreguntas.length) {
    currentQuizIndex = nuevoIdx;
    renderizarPreguntaPlayerQuiz();
  }
}

async function enviarRespuestasQuiz() {
  if (currentQuizRespuestas[currentQuizIndex] === undefined) {
    return mostrarToast('Por favor selecciona tu respuesta final.', 'advertencia');
  }

  if (quizTimerInterval) {
    clearInterval(quizTimerInterval);
    quizTimerInterval = null;
  }

  // Enviar a backend
  const respuestasArray = [];
  for (let i = 0; i < currentQuizPreguntas.length; i++) {
    respuestasArray.push(currentQuizRespuestas[i] !== undefined ? currentQuizRespuestas[i] : -1);
  }

  try {
    const res = await fetch(`${API_BASE}/api/quizzes/${currentQuizActive.id}/responder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        aprendiz_id: currentUser.id,
        respuestas: respuestasArray,
        tiempo_segundos: quizSecondsElapsed
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al calificar quiz');

    const calif = Math.round(json.calificacion || 0);
    const aprobado = json.aprobado;

    // Mostrar pantalla de resultados
    document.getElementById('player-quiz-cuerpo')?.classList.add('hidden');
    document.getElementById('player-quiz-footer')?.classList.add('hidden');
    document.getElementById('player-quiz-resultados')?.classList.remove('hidden');

    const resCalif = document.getElementById('player-quiz-res-calif');
    const resTiempo = document.getElementById('player-quiz-res-tiempo');
    const resRacha = document.getElementById('player-quiz-res-racha');

    if (resCalif) resCalif.innerText = `${calif}%`;
    const minsDed = Math.max(1, Math.round(quizSecondsElapsed / 60));
    if (resTiempo) resTiempo.innerText = `${minsDed} min`;
    if (resRacha) resRacha.innerText = `🔥 ${json.racha_semanas || 5} sem`;

    const iconRes = document.getElementById('player-quiz-icono-resultado');
    const titleRes = document.getElementById('player-quiz-resultado-titulo');
    const subRes = document.getElementById('player-quiz-resultado-subtitulo');

    if (aprobado) {
      if (iconRes) {
        iconRes.className = 'w-20 h-20 rounded-full mx-auto flex items-center justify-center text-4xl shadow-xl bg-emerald-100 text-emerald-600';
        iconRes.innerText = '🏆';
      }
      if (titleRes) titleRes.innerText = '¡Felicitaciones, Has Aprobado!';
      if (subRes) subRes.innerText = `Obtuviste ${calif}%. Tu racha y tiempo de dedicación han sido incrementados.`;
    } else {
      if (iconRes) {
        iconRes.className = 'w-20 h-20 rounded-full mx-auto flex items-center justify-center text-4xl shadow-xl bg-amber-100 text-amber-600';
        iconRes.innerText = '📚';
      }
      if (titleRes) titleRes.innerText = 'Buen Intento';
      if (subRes) subRes.innerText = `Obtuviste ${calif}%. Puedes repasar los temas y presentar nuevamente el cuestionario.`;
    }

    if (currentUser) {
      currentUser.racha_semanas = json.racha_semanas;
    }

    refrescarIconos();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// CREADOR DE QUIZZES Y GESTIÓN DE MENTOR
// =====================================================================
let quizBuilderPreguntas = [];

function abrirModalCrearQuizMentor() {
  const inTit = document.getElementById('quiz-input-titulo');
  const inDesc = document.getElementById('quiz-input-descripcion');
  const inDur = document.getElementById('quiz-input-duracion');
  const inTipo = document.getElementById('quiz-input-tipo');

  if (inTit) inTit.value = '';
  if (inDesc) inDesc.value = '';
  if (inDur) inDur.value = '20';
  if (inTipo) inTipo.value = 'Quiz';

  // Iniciar con 2 preguntas de ejemplo
  quizBuilderPreguntas = [
    {
      id: 1,
      pregunta: '¿Cuál es uno de los principios fundamentales de la computación en la nube?',
      opciones: ['Alta disponibilidad y escalabilidad bajo demanda', 'Almacenamiento exclusivo en discos locales', 'Conexión obligatoria por cable serial', 'Ausencia de copias de seguridad'],
      correcta: 0
    },
    {
      id: 2,
      pregunta: '¿Qué componente asegura la privacidad de los datos en tránsito?',
      opciones: ['Protocolo HTTP sin cifrado', 'Protocolo HTTPS / TLS con certificados digitales', 'Impresión de logs en texto claro', 'Desactivación de contraseñas'],
      correcta: 1
    }
  ];

  renderizarPreguntasQuizBuilder();
  const modal = document.getElementById('modal-crear-quiz-mentor');
  if (modal) modal.classList.remove('hidden');
  refrescarIconos();
}

function agregarPreguntaQuizBuilder() {
  const nuevoId = Date.now();
  quizBuilderPreguntas.push({
    id: nuevoId,
    pregunta: '',
    opciones: ['', '', '', ''],
    correcta: 0
  });
  renderizarPreguntasQuizBuilder();
}

function eliminarPreguntaQuizBuilder(id) {
  if (quizBuilderPreguntas.length <= 1) {
    return mostrarToast('El quiz debe tener al menos una pregunta.', 'advertencia');
  }
  quizBuilderPreguntas = quizBuilderPreguntas.filter(p => p.id !== id);
  renderizarPreguntasQuizBuilder();
}

function renderizarPreguntasQuizBuilder() {
  const container = document.getElementById('contenedor-preguntas-builder');
  const contador = document.getElementById('contador-preguntas-quiz');
  if (!container) return;

  if (contador) contador.innerText = quizBuilderPreguntas.length;

  container.innerHTML = quizBuilderPreguntas.map((p, idx) => `
    <div class="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-xs font-bold text-purple-900">Pregunta ${idx + 1}</span>
        <button type="button" onclick="eliminarPreguntaQuizBuilder(${p.id})" class="text-rose-500 hover:text-rose-700 text-xs font-semibold flex items-center gap-1">
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          <span>Eliminar</span>
        </button>
      </div>

      <div>
        <label class="block text-[11px] font-bold text-slate-600 mb-1">Enunciado de la Pregunta:</label>
        <input type="text" value="${escapeHtml(p.pregunta)}" oninput="actualizarEnunciadoBuilder(${idx}, this.value)" placeholder="Escribe el enunciado de la pregunta..." required class="corp-input w-full px-3 py-1.5 rounded-xl text-xs font-medium bg-white">
      </div>

      <div class="space-y-1.5">
        <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider">Opciones (Selecciona la opción correcta):</label>
        ${[0, 1, 2, 3].map(optIdx => `
          <div class="flex items-center gap-2">
            <input type="radio" name="correcta_p_${p.id}" value="${optIdx}" ${p.correcta === optIdx ? 'checked' : ''} onchange="actualizarCorrectaBuilder(${idx}, ${optIdx})" class="text-purple-600 focus:ring-purple-500" title="Marcar como respuesta correcta">
            <span class="text-xs font-mono font-bold text-slate-400 w-4">${['A', 'B', 'C', 'D'][optIdx]}</span>
            <input type="text" value="${escapeHtml(p.opciones[optIdx] || '')}" oninput="actualizarOpcionBuilder(${idx}, ${optIdx}, this.value)" placeholder="Opción ${['A', 'B', 'C', 'D'][optIdx]}" required class="corp-input flex-1 px-3 py-1.5 rounded-xl text-xs bg-white">
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');

  refrescarIconos();
}

function actualizarEnunciadoBuilder(idx, val) {
  if (quizBuilderPreguntas[idx]) quizBuilderPreguntas[idx].pregunta = val;
}

function actualizarOpcionBuilder(pIdx, optIdx, val) {
  if (quizBuilderPreguntas[pIdx]) quizBuilderPreguntas[pIdx].opciones[optIdx] = val;
}

function actualizarCorrectaBuilder(pIdx, optIdx) {
  if (quizBuilderPreguntas[pIdx]) quizBuilderPreguntas[pIdx].correcta = optIdx;
}

async function guardarQuizMentor(event) {
  event.preventDefault();
  if (!currentUser) return;

  const titulo = document.getElementById('quiz-input-titulo').value.trim();
  const tipo = document.getElementById('quiz-input-tipo').value;
  const descripcion = document.getElementById('quiz-input-descripcion').value.trim();
  const duracion = parseInt(document.getElementById('quiz-input-duracion').value) || 20;

  for (let i = 0; i < quizBuilderPreguntas.length; i++) {
    const p = quizBuilderPreguntas[i];
    if (!p.pregunta.trim()) {
      return mostrarToast(`Ingresa el enunciado para la Pregunta ${i + 1}.`, 'advertencia');
    }
    for (let j = 0; j < 4; j++) {
      if (!p.opciones[j] || !p.opciones[j].trim()) {
        return mostrarToast(`Completa las 4 opciones de la Pregunta ${i + 1}.`, 'advertencia');
      }
    }
  }

  const payloadPreguntas = quizBuilderPreguntas.map(p => ({
    pregunta: p.pregunta.trim(),
    opciones: p.opciones.map(o => o.trim()),
    correcta: p.correcta
  }));

  try {
    const res = await fetch(`${API_BASE}/api/quizzes/crear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mentor_id: currentUser.id,
        organizacion_id: currentUser.organizacion_id,
        titulo,
        tipo,
        descripcion,
        duracion_minutos: duracion,
        preguntas: payloadPreguntas
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al guardar quiz');

    mostrarToast(`¡${tipo} '${titulo}' creado y asignado a tus estudiantes!`, 'exito');
    cerrarModal('modal-crear-quiz-mentor');
    cargarQuizzesMentor();
    if (typeof cargarProgresoAlumnosMentor === 'function') cargarProgresoAlumnosMentor();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function cargarQuizzesMentor() {
  if (!currentUser) return;
  const grid = document.getElementById('grid-mentor-quizzes');
  if (!grid) return;

  try {
    const res = await fetch(`${API_BASE}/api/quizzes/listar?mentor_id=${currentUser.id}`);
    const json = await res.json();
    const quizzes = json.data || [];

    if (quizzes.length === 0) {
      grid.innerHTML = `
        <div class="col-span-full p-6 text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
          <p class="font-bold text-slate-600">Aún no has creado Quizzes o Evaluaciones para tu clase.</p>
          <p class="text-[11px] text-slate-400 mt-1">Haz clic en '+ Crear Quiz / Evaluación' para publicar tu primer cuestionario evaluativo.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = quizzes.map(q => `
      <div class="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs hover:shadow-md transition-all space-y-3">
        <div class="flex items-center justify-between">
          <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase bg-purple-100 text-purple-800">
            ${q.tipo || 'Quiz'}
          </span>
          <span class="text-[11px] text-slate-400 font-mono">${q.duracion_minutos || 15} min</span>
        </div>
        <div>
          <h4 class="text-xs font-bold text-[#0a192f]">${q.titulo}</h4>
          <p class="text-[11px] text-slate-400 mt-0.5">${q.preguntas_count || 0} preguntas registradas</p>
        </div>
        <div class="p-2 bg-slate-50 rounded-lg flex items-center justify-between text-[11px]">
          <span class="text-slate-500">Alumnos evaluados:</span>
          <span class="font-bold text-purple-900">${q.total_respuestas || 0}</span>
        </div>
        <div class="pt-2 border-t border-slate-100 flex items-center justify-end">
          <button onclick="eliminarQuizMentor(${q.id}, '${escapeHtml(q.titulo)}')" class="text-xs text-rose-600 hover:text-rose-800 font-semibold flex items-center gap-1">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            <span>Eliminar</span>
          </button>
        </div>
      </div>
    `).join('');

    refrescarIconos();
  } catch (err) {
    console.error('Error cargando quizzes del mentor:', err);
  }
}

async function eliminarQuizMentor(quizId, titulo) {
  if (!confirm(`¿Deseas eliminar el quiz '${titulo}'?`)) return;
  try {
    const res = await fetch(`${API_BASE}/api/quizzes/${quizId}`, { method: 'DELETE' });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al eliminar');

    mostrarToast(`Quiz '${titulo}' eliminado.`, 'info');
    cargarQuizzesMentor();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// ESTADO Y GESTIÓN DE EVALUACIONES (TESTS INTERACTIVOS)
// =====================================================================
let currentTestCursoId = null;
let currentTestPreguntas = [];
let currentTestIndex = 0;
let currentTestRespuestas = {};
let materialIdAEliminar = null;

async function abrirModalTest(cursoId, cursoTitulo) {
  try {
    mostrarToast('Cargando cuestionario de evaluación...', 'info');
    const res = await fetch(`${API_BASE}/api/material/${cursoId}/test`);
    const json = await res.json();
    if (!res.ok || !json.data) throw new Error('No se pudo cargar el test');

    const testData = json.data;
    currentTestCursoId = cursoId;
    currentTestPreguntas = testData.preguntas || [];
    currentTestIndex = 0;
    currentTestRespuestas = {};

    document.getElementById('test-modal-titulo').innerText = testData.titulo || cursoTitulo;
    document.getElementById('test-modal-desc').innerText = testData.descripcion || 'Responde las preguntas para certificar tu avance.';
    document.getElementById('test-duracion-badge').innerHTML = `<i data-lucide="clock" class="w-3 h-3"></i> ${testData.duracion_minutos || 15} min`;

    // Resetear vistas
    document.getElementById('test-vista-preguntas').classList.remove('hidden');
    document.getElementById('test-vista-resultados').classList.add('hidden');
    document.getElementById('test-footer-navegacion').classList.remove('hidden');
    document.getElementById('test-footer-resultado').classList.add('hidden');

    renderizarPreguntaActual();
    document.getElementById('modal-test-conocimiento').classList.remove('hidden');
    refrescarIconos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function renderizarPreguntaActual() {
  if (currentTestPreguntas.length === 0) return;
  const total = currentTestPreguntas.length;
  const p = currentTestPreguntas[currentTestIndex];

  document.getElementById('test-num-actual').innerText = currentTestIndex + 1;
  document.getElementById('test-total-preguntas').innerText = total;

  const pct = Math.round(((currentTestIndex + 1) / total) * 100);
  document.getElementById('test-progress-bar').style.width = `${pct}%`;
  document.getElementById('test-porcentaje-progreso-preguntas').innerText = `${pct}% contestado`;

  document.getElementById('test-enunciado').innerText = p.pregunta;

  const respuestaSeleccionada = currentTestRespuestas[currentTestIndex];
  const listContainer = document.getElementById('test-opciones-list');
  listContainer.innerHTML = p.opciones.map(opt => {
    const isChecked = respuestaSeleccionada === opt.id;
    return `
      <div onclick="seleccionarOpcionTest('${opt.id}')" class="p-3 rounded-xl border text-xs font-semibold cursor-pointer transition-all flex items-center justify-between ${isChecked ? 'bg-cyan-50 border-cyan-500 text-cyan-950 shadow-sm' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}">
        <div class="flex items-center space-x-2.5">
          <span class="w-5 h-5 rounded-full flex items-center justify-center font-bold text-[11px] ${isChecked ? 'bg-cyan-600 text-white' : 'bg-slate-100 text-slate-600'}">
            ${opt.id.toUpperCase()}
          </span>
          <span>${opt.texto}</span>
        </div>
        <div class="w-4 h-4 rounded-full border flex items-center justify-center ${isChecked ? 'border-cyan-600 bg-cyan-600 text-white' : 'border-slate-300'}">
          ${isChecked ? '<i data-lucide="check" class="w-2.5 h-2.5"></i>' : ''}
        </div>
      </div>
    `;
  }).join('');

  // Botones de navegación
  const btnAnt = document.getElementById('btn-test-anterior');
  const btnSig = document.getElementById('btn-test-siguiente');
  const btnFin = document.getElementById('btn-test-finalizar');

  btnAnt.disabled = (currentTestIndex === 0);

  if (currentTestIndex === total - 1) {
    btnSig.classList.add('hidden');
    btnFin.classList.remove('hidden');
  } else {
    btnSig.classList.remove('hidden');
    btnFin.classList.add('hidden');
  }

  refrescarIconos();
}

function seleccionarOpcionTest(optId) {
  currentTestRespuestas[currentTestIndex] = optId;
  renderizarPreguntaActual();
}

function avanzarPreguntaTest() {
  if (!currentTestRespuestas[currentTestIndex]) {
    return mostrarToast('Por favor selecciona una opción para continuar.', 'advertencia');
  }
  if (currentTestIndex < currentTestPreguntas.length - 1) {
    currentTestIndex++;
    renderizarPreguntaActual();
  }
}

function retrocederPreguntaTest() {
  if (currentTestIndex > 0) {
    currentTestIndex--;
    renderizarPreguntaActual();
  }
}

async function enviarTestFinalizado() {
  if (!currentTestRespuestas[currentTestIndex]) {
    return mostrarToast('Por favor selecciona una opción para la última pregunta.', 'advertencia');
  }

  const total = currentTestPreguntas.length;
  let correctas = 0;
  currentTestPreguntas.forEach((p, idx) => {
    if (currentTestRespuestas[idx] === p.correcta) {
      correctas++;
    }
  });

  const porcentaje = Math.round((correctas / total) * 100);

  const btnFin = document.getElementById('btn-test-finalizar');
  if (btnFin) {
    btnFin.disabled = true;
    btnFin.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Guardando...</span>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/aprendiz/completar-test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        usuario_id: currentUser.id,
        curso_id: currentTestCursoId,
        respuestas_correctas: correctas,
        total_preguntas: total,
        tiempo_dedicado_minutos: 20
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al guardar test');

    // Cambiar a vista de resultados
    document.getElementById('test-vista-preguntas').classList.add('hidden');
    document.getElementById('test-vista-resultados').classList.remove('hidden');
    document.getElementById('test-footer-navegacion').classList.add('hidden');
    document.getElementById('test-footer-resultado').classList.remove('hidden');

    document.getElementById('test-resultado-porcentaje').innerText = `${porcentaje}%`;
    document.getElementById('test-resultado-aciertos').innerText = `${correctas} de ${total} respuestas correctas`;

    if (porcentaje >= 60) {
      document.getElementById('test-resultado-titulo').innerText = '🎉 ¡Felicitaciones! Has Aprobado la Evaluación';
    } else {
      document.getElementById('test-resultado-titulo').innerText = '📝 Evaluación Completada';
    }

    // Renderizar retroalimentación
    const feedbackList = document.getElementById('test-retroalimentacion-list');
    feedbackList.innerHTML = currentTestPreguntas.map((p, idx) => {
      const respUser = currentTestRespuestas[idx];
      const esCorrecta = respUser === p.correcta;
      return `
        <div class="p-3 rounded-xl border ${esCorrecta ? 'bg-emerald-50/70 border-emerald-200' : 'bg-rose-50/70 border-rose-200'}">
          <div class="flex items-center gap-1.5 font-bold mb-1 ${esCorrecta ? 'text-emerald-900' : 'text-rose-900'}">
            <i data-lucide="${esCorrecta ? 'check-circle' : 'x-circle'}" class="w-3.5 h-3.5 flex-shrink-0"></i>
            <span>Pregunta ${idx + 1}: ${p.pregunta}</span>
          </div>
          <p class="text-[11px] ${esCorrecta ? 'text-emerald-800' : 'text-rose-800'} mt-1">
            <strong>Explicación:</strong> ${p.explicacion}
          </p>
        </div>
      `;
    }).join('');

    mostrarToast(`✓ Calificación registrada: ${porcentaje}%. Progreso actualizado.`, 'exito');
    refrescarIconos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btnFin) {
      btnFin.disabled = false;
      btnFin.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5"></i><span>Calificar Evaluación</span>`;
    }
  }
}

function cerrarTestYActualizar() {
  cerrarModal('modal-test-conocimiento');
  cargarCursosAprendiz();
  cargarMateriales();
}

// =====================================================================
// DETALLE DE PROGRESO Y TESTS DEL APRENDIZ (SUPERADMIN & MENTOR - SOLO LECTURA)
// =====================================================================
async function abrirDetalleProgresoAprendiz(usuarioId) {
  try {
    mostrarToast('Consultando evaluaciones y cursos del estudiante...', 'info');
    const res = await fetch(`${API_BASE}/api/superadmin/aprendiz/${usuarioId}/desglose-cursos`);
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error cargando datos del estudiante');

    const u = json.usuario;
    const cursos = json.cursos || [];
    const quizzes = json.quizzes || [];

    document.getElementById('detalle-apr-nombre').innerText = u.nombre;
    document.getElementById('detalle-apr-correo').innerText = u.correo;
    document.getElementById('detalle-apr-meta').innerText = `${u.organizacion_nombre || 'Institución Base'} · Mentor: ${u.mentor_nombre || 'Sin asignar'}`;
    
    const avatarEl = document.getElementById('detalle-apr-avatar');
    if (avatarEl) {
      if (u.foto_perfil) {
        avatarEl.innerHTML = `<img src="${u.foto_perfil}" alt="${escapeHtml(u.nombre)}" class="w-full h-full object-cover rounded-2xl">`;
      } else {
        avatarEl.innerText = obtenerIniciales(u.nombre);
      }
    }

    document.getElementById('detalle-apr-promedio').innerText = `${json.promedio_general}%`;
    document.getElementById('detalle-apr-cursos-completados').innerText = `${json.cursos_completados} de ${json.total_cursos}`;
    
    const elPromQz = document.getElementById('detalle-apr-promedio-quizzes');
    if (elPromQz) elPromQz.innerText = `${json.promedio_quizzes || 0}%`;
    
    const elQzComp = document.getElementById('detalle-apr-quizzes-aprobados');
    if (elQzComp) elQzComp.innerText = `${json.quizzes_aprobados || 0} de ${json.quizzes_totales || 0}`;

    document.getElementById('detalle-apr-tiempo').innerText = `${json.total_minutos} min`;

    // Renderizar Cursos
    const lista = document.getElementById('detalle-apr-lista-cursos');
    if (cursos.length === 0) {
      lista.innerHTML = `<div class="p-6 text-center text-slate-400 text-xs">No hay cursos registrados para este estudiante.</div>`;
    } else {
      lista.innerHTML = cursos.map(c => {
        const avance = Math.round(c.porcentaje_avance || 0);
        const completado = avance >= 80;
        return `
          <div class="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
            <div class="flex items-start justify-between gap-2">
              <div>
                <span class="text-[10px] font-bold uppercase tracking-wider text-cyan-700">${c.tipo_material || 'Colección'}</span>
                <h5 class="text-xs font-bold text-[#0a192f] mt-0.5">${c.titulo}</h5>
              </div>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded ${completado ? 'bg-emerald-100 text-emerald-800' : (avance > 0 ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-600')}">
                ${completado ? '🏆 Aprobado' : (avance > 0 ? 'En Progreso' : 'Sin Iniciar')}
              </span>
            </div>
            <div class="mt-2.5">
              <div class="flex items-center justify-between text-[11px] mb-1">
                <span class="text-slate-500 font-medium">Nota / Avance en Test:</span>
                <span class="font-extrabold text-[#0a192f]">${avance}%</span>
              </div>
              <div class="progress-track-cyan">
                <div class="progress-bar-cyan" style="width: ${avance}%;"></div>
              </div>
              <p class="text-[10px] text-slate-400 mt-1 font-medium">${c.tiempo_dedicado_minutos || 0} minutos dedicados</p>
            </div>
          </div>
        `;
      }).join('');
    }

    // Renderizar Quizzes y Evaluaciones (Solo Lectura)
    const listaQz = document.getElementById('detalle-apr-lista-quizzes');
    if (listaQz) {
      if (quizzes.length === 0) {
        listaQz.innerHTML = `<div class="p-6 text-center text-slate-400 text-xs">No hay quizzes asignados a este estudiante en este momento.</div>`;
      } else {
        listaQz.innerHTML = quizzes.map(q => {
          const esComp = q.estado === 'Completado';
          const calif = q.calificacion !== null ? `${q.calificacion}%` : 'Sin presentar';
          const badgeColor = q.aprobado ? 'bg-emerald-100 text-emerald-800' : (esComp ? 'bg-rose-100 text-rose-800' : 'bg-slate-200 text-slate-600');
          const badgeTxt = q.aprobado ? '🏆 Aprobado' : (esComp ? '❌ No Aprobado' : '⏳ Pendiente');

          return `
            <div class="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
              <div class="flex items-start justify-between gap-2">
                <div>
                  <span class="text-[10px] font-bold uppercase tracking-wider text-purple-700">${escapeHtml(q.tipo || 'Quiz')} · Autor: ${escapeHtml(q.mentor_nombre || 'Mentor')}</span>
                  <h5 class="text-xs font-bold text-[#0a192f] mt-0.5">${escapeHtml(q.titulo)}</h5>
                  ${q.descripcion ? `<p class="text-[11px] text-slate-500 mt-0.5">${escapeHtml(q.descripcion)}</p>` : ''}
                </div>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded ${badgeColor}">
                  ${badgeTxt}
                </span>
              </div>
              <div class="mt-2.5 grid grid-cols-3 gap-2 text-[11px] bg-white p-2.5 rounded-lg border border-slate-100">
                <div>
                  <span class="text-slate-400 block text-[10px]">Calificación:</span>
                  <strong class="text-sm font-extrabold ${q.aprobado ? 'text-emerald-600' : (esComp ? 'text-rose-600' : 'text-slate-500')}">${calif}</strong>
                </div>
                <div>
                  <span class="text-slate-400 block text-[10px]">Tiempo Empleado:</span>
                  <strong class="font-bold text-[#0a192f] text-xs">⏱️ ${q.tiempo_formateado || '0s'}</strong>
                </div>
                <div>
                  <span class="text-slate-400 block text-[10px]">Fecha Entrega:</span>
                  <span class="font-medium text-slate-600 text-[10px] block truncate">${q.fecha_completado || 'Pendiente'}</span>
                </div>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    cambiarTabDetalleAprendiz('cursos');
    document.getElementById('modal-detalle-progreso-aprendiz').classList.remove('hidden');
    refrescarIconos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function cambiarTabDetalleAprendiz(tab) {
  const btnCursos = document.getElementById('btn-tab-detalle-cursos');
  const btnQuizzes = document.getElementById('btn-tab-detalle-quizzes');
  const contCursos = document.getElementById('detalle-apr-contenedor-cursos');
  const contQuizzes = document.getElementById('detalle-apr-contenedor-quizzes');
  if (!contCursos || !contQuizzes) return;

  if (tab === 'cursos') {
    btnCursos?.classList.remove('bg-slate-100', 'text-slate-700');
    btnCursos?.classList.add('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnQuizzes?.classList.remove('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnQuizzes?.classList.add('bg-slate-100', 'text-slate-700');
    contCursos.classList.remove('hidden');
    contQuizzes.classList.add('hidden');
  } else {
    btnQuizzes?.classList.remove('bg-slate-100', 'text-slate-700');
    btnQuizzes?.classList.add('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnCursos?.classList.remove('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnCursos?.classList.add('bg-slate-100', 'text-slate-700');
    contCursos.classList.add('hidden');
    contQuizzes.classList.remove('hidden');
  }
  refrescarIconos();
}

// =====================================================================
// ELIMINACIÓN DE COLECCIONES / MATERIALES DEL CATÁLOGO
// =====================================================================
function confirmarEliminarMaterial(id, titulo) {
  materialIdAEliminar = id;
  const lbl = document.getElementById('lbl-eliminar-material-titulo');
  if (lbl) lbl.innerText = `"${titulo}"`;
  document.getElementById('modal-confirmar-eliminar-material').classList.remove('hidden');
}

async function ejecutarEliminarMaterial() {
  if (!materialIdAEliminar) return;
  const btn = document.getElementById('btn-ejecutar-eliminar-material');
  if (btn) {
    btn.disabled = true;
    btn.innerText = 'Eliminando...';
  }

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/material/${materialIdAEliminar}`, {
      method: 'DELETE'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al eliminar material');

    mostrarToast(json.mensaje || 'Colección eliminada exitosamente.', 'exito');
    cerrarModal('modal-confirmar-eliminar-material');
    cargarMateriales();
    if (typeof cargarCursosAprendiz === 'function') cargarCursosAprendiz();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = 'Sí, Eliminar';
    }
  }
}

// =====================================================================
// 8.5. VISTA ADMINISTRADOR INSTITUCIONAL: GESTIÓN DE CONVENIO (COLEGIO/EMPRESA)
// =====================================================================
let adminConvenioData = null;
let adminAprendicesFiltrados = [];

async function cargarVistaAdminConvenio() {
  if (!currentUser) return;
  const orgId = currentUser.organizacion_id || 13;

  try {
    const res = await fetch(`${API_BASE}/api/admin/convenio/${orgId}`);
    const json = await res.json();
    if (!res.ok || !json.organizacion) throw new Error(json.detail || 'Error al cargar datos del convenio');

    adminConvenioData = json;
    const org = json.organizacion;
    const kpis = json.kpis;

    // Encabezado
    const lblNombre = document.getElementById('admin-org-nombre');
    const lblTipo = document.getElementById('admin-org-tipo');
    const cardTitulo = document.getElementById('admin-card-org-titulo');
    const cardDom = document.getElementById('admin-card-org-dominio');
    const cardLicText = document.getElementById('admin-card-licencias-texto');
    const cardLicDisp = document.getElementById('admin-card-licencias-disp');
    const cardBar = document.getElementById('admin-card-progress-bar');

    if (lblNombre) lblNombre.innerText = org.nombre;
    if (lblTipo) lblTipo.innerText = `${org.tipo_organizacion} · Convenio ID #${org.id}`;
    if (cardTitulo) cardTitulo.innerText = org.nombre;
    if (cardDom) cardDom.innerText = (org.dominio_permitido && org.dominio_permitido !== 'LIBRE') ? `@${org.dominio_permitido}` : 'Sin restricción (Acceso Libre)';
    if (cardLicText) cardLicText.innerText = `${kpis.total_usuarios} / ${kpis.licencias_asignadas} licencias`;
    if (cardLicDisp) cardLicDisp.innerText = `${kpis.licencias_disponibles} cupos disponibles (${kpis.porcentaje_ocupacion}% ocupación)`;
    if (cardBar) cardBar.style.width = `${Math.min(100, kpis.porcentaje_ocupacion)}%`;

    // KPIs
    const kpiMentores = document.getElementById('kpi-admin-mentores');
    const kpiAprendices = document.getElementById('kpi-admin-aprendices');
    const kpiPromedio = document.getElementById('kpi-admin-promedio');
    const kpiTiempo = document.getElementById('kpi-admin-tiempo');

    if (kpiMentores) kpiMentores.innerText = kpis.total_mentores;
    if (kpiAprendices) kpiAprendices.innerText = kpis.total_estudiantes;
    if (kpiPromedio) kpiPromedio.innerText = `${kpis.promedio_general}%`;
    if (kpiTiempo) kpiTiempo.innerText = `${kpis.total_minutos} min`;

    // Renderizar Mentores
    const gridMentores = document.getElementById('grid-admin-mentores');
    const badgeMentores = document.getElementById('badge-admin-total-mentores');
    if (badgeMentores) badgeMentores.innerText = `${json.mentores.length} mentores`;

    if (gridMentores) {
      if (json.mentores.length === 0) {
        gridMentores.innerHTML = `<div class="p-6 text-center text-slate-400 col-span-full font-medium text-xs">No hay mentores registrados en este convenio aún.</div>`;
      } else {
        gridMentores.innerHTML = json.mentores.map(m => `
          <div class="p-4 rounded-xl border border-slate-200 bg-white hover:border-purple-300 transition-all flex items-start gap-3">
            <div class="w-10 h-10 rounded-xl bg-purple-100 text-purple-800 flex items-center justify-center font-bold text-xs flex-shrink-0 overflow-hidden">
              ${m.foto_perfil ? `<img src="${m.foto_perfil}" class="w-full h-full object-cover rounded-xl">` : obtenerIniciales(m.nombre)}
            </div>
            <div class="flex-1 overflow-hidden">
              <div class="flex items-center justify-between gap-2">
                <h4 class="text-xs font-bold text-[#0a192f] truncate">${m.nombre}</h4>
                <button onclick="abrirModalEditarUsuario(${m.id}, '${escapeHtml(m.nombre)}', '${m.correo}', 'Mentor', ${org.id}, null)" class="btn-icon-edit" title="Editar Mentor">
                  <i data-lucide="edit-2" class="w-3 h-3"></i>
                </button>
              </div>
              <p class="text-[11px] text-slate-500 font-mono truncate">${m.correo}</p>
              <div class="mt-2 flex flex-wrap items-center justify-between gap-2">
                <div class="flex items-center gap-1.5 text-[10px] font-semibold text-purple-800 bg-purple-50 px-2 py-0.5 rounded-lg w-fit">
                  <i data-lucide="users" class="w-3 h-3"></i>
                  <span>${m.total_aprendices || 0} alumnos a su cargo</span>
                </div>
                <select onchange="cambiarCargoUsuarioTiempoReal(${m.id}, this.value)" class="px-2 py-0.5 rounded-lg border border-cyan-300 bg-cyan-50/70 text-[#0a192f] text-[10px] font-bold cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500" title="Cambiar cargo en tiempo real">
                  <option value="Administrador">🛡️ Administrador</option>
                  <option value="Mentor" selected>🎓 Mentor</option>
                  <option value="Aprendiz">📘 Aprendiz</option>
                </select>
              </div>
            </div>
          </div>
        `).join('');
      }
    }

    // Renderizar Aprendices
    adminAprendicesFiltrados = json.aprendices || [];
    renderizarTablaAprendicesAdmin();
    renderizarCuadroHonorTop10AprendicesAdmin(adminAprendicesFiltrados);

    // Actualizar Cuadro de Honor del Mejor Estudiante
    if (adminAprendicesFiltrados.length > 0) {
      const topApr = [...adminAprendicesFiltrados].sort((a, b) => ((b.promedio_avance || 0) - (a.promedio_avance || 0)) || ((b.total_minutos || 0) - (a.total_minutos || 0)))[0];
      const elTopNom = document.getElementById('top-aprendiz-admin-nombre');
      const elTopCor = document.getElementById('top-aprendiz-admin-correo');
      const elTopMen = document.getElementById('top-aprendiz-admin-mentor');
      const elTopAv = document.getElementById('top-aprendiz-admin-avance');
      const elTopTi = document.getElementById('top-aprendiz-admin-tiempo');
      const elTopRa = document.getElementById('top-aprendiz-admin-racha');
      const elTopAvWrap = document.getElementById('top-aprendiz-admin-avatar-wrap');

      if (elTopNom) elTopNom.innerText = topApr.nombre || 'Estudiante';
      if (elTopCor) elTopCor.innerText = topApr.correo || '--';
      if (elTopMen) elTopMen.innerText = `Mentor: ${topApr.mentor_nombre || 'Asignado'}`;
      if (elTopAv) elTopAv.innerText = `${Math.round(topApr.promedio_avance || 0)}%`;
      if (elTopTi) elTopTi.innerText = `${topApr.total_minutos || 0} min`;
      if (elTopRa) elTopRa.innerText = `🔥 ${topApr.racha_semanal || 1}`;
      if (elTopAvWrap) {
        if (topApr.foto_perfil) {
          elTopAvWrap.innerHTML = `<img src="${topApr.foto_perfil}" class="w-full h-full object-cover">`;
        } else {
          elTopAvWrap.innerHTML = `<span id="top-aprendiz-admin-iniciales">${obtenerIniciales(topApr.nombre)}</span>`;
        }
      }

      // Cohorte metric bars
      const promAvance = Math.round(adminAprendicesFiltrados.reduce((acc, a) => acc + (a.promedio_avance || 0), 0) / adminAprendicesFiltrados.length);
      const tasaQuizzes = Math.min(100, Math.round(promAvance * 1.05));
      const tasaRacha = Math.round((adminAprendicesFiltrados.filter(a => (a.racha_semanal || 0) >= 1).length / adminAprendicesFiltrados.length) * 100);

      const barMsft = document.getElementById('metric-admin-bar-msft');
      const barMsftVal = document.getElementById('metric-admin-bar-msft-val');
      const barQz = document.getElementById('metric-admin-bar-quizzes');
      const barQzVal = document.getElementById('metric-admin-bar-quizzes-val');
      const barRa = document.getElementById('metric-admin-bar-racha');
      const barRaVal = document.getElementById('metric-admin-bar-racha-val');

      if (barMsft) barMsft.style.width = `${promAvance}%`;
      if (barMsftVal) barMsftVal.innerText = `${promAvance}%`;
      if (barQz) barQz.style.width = `${tasaQuizzes}%`;
      if (barQzVal) barQzVal.innerText = `${tasaQuizzes}%`;
      if (barRa) barRa.style.width = `${tasaRacha}%`;
      if (barRaVal) barRaVal.innerText = `${tasaRacha}%`;
    }

    cambiarSubTabAdminConvenio('aprendices');
    refrescarIconos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function renderizarTablaAprendicesAdmin() {
  const tbody = document.getElementById('tabla-admin-aprendices-body');
  const badgeTotal = document.getElementById('badge-admin-total-aprendices');
  if (!tbody) return;

  if (badgeTotal) badgeTotal.innerText = `${adminAprendicesFiltrados.length} estudiantes`;

  if (adminAprendicesFiltrados.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-400 font-medium">No se encontraron estudiantes para este convenio.</td></tr>`;
    return;
  }

  tbody.innerHTML = adminAprendicesFiltrados.map(a => {
    const avance = Math.round(a.promedio_avance || 0);
    return `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-3">
          <div class="flex items-center gap-2.5">
            ${a.foto_perfil ? `<img src="${a.foto_perfil}" class="w-7 h-7 rounded-full object-cover border border-slate-200 shrink-0 shadow-2xs">` : `<div class="w-7 h-7 rounded-full bg-slate-200 text-[#0a192f] font-bold text-[10px] flex items-center justify-center shrink-0">${obtenerIniciales(a.nombre)}</div>`}
            <span class="font-bold text-[#0a192f]">${a.nombre}</span>
          </div>
        </td>
        <td class="py-3 font-mono text-[11px] text-slate-500">${a.correo}</td>
        <td class="py-3">
          ${a.mentor_nombre ? `
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-purple-50 text-purple-800 text-[10px] font-bold">
              ${a.mentor_foto_perfil ? `<img src="${a.mentor_foto_perfil}" class="w-4 h-4 rounded-full object-cover">` : `<i data-lucide="user-check" class="w-3 h-3"></i>`}
              <span>${a.mentor_nombre}</span>
            </span>
          ` : `
            <span class="text-slate-400 text-[10px] italic">Sin tutor asignado</span>
          `}
        </td>
        <td class="py-3">
          <div class="flex items-center space-x-2">
            <div class="progress-track-cyan w-20">
              <div class="progress-bar-cyan" style="width: ${avance}%;"></div>
            </div>
            <span class="font-extrabold text-xs text-[#0a192f]">${avance}%</span>
          </div>
        </td>
        <td class="py-3 text-slate-600 font-medium">${a.total_minutos || 0} min</td>
        <td class="py-3 text-right">
          <div class="flex items-center justify-end gap-1.5 flex-wrap">
            <select onchange="cambiarCargoUsuarioTiempoReal(${a.id}, this.value)" class="px-2 py-1 rounded-lg border border-cyan-300 bg-cyan-50/70 text-[#0a192f] text-[10px] font-bold cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500" title="Cambiar cargo en tiempo real">
              <option value="Administrador">🛡️ Administrador</option>
              <option value="Mentor">🎓 Mentor</option>
              <option value="Aprendiz" selected>📘 Aprendiz</option>
            </select>
            <button onclick="abrirDetalleProgresoAprendiz(${a.id})" class="px-2 py-1 rounded-lg bg-[#091b2c] hover:bg-[#0f273f] text-cyan-300 hover:text-white text-[11px] font-bold inline-flex items-center gap-1 transition-colors shadow-2xs" title="Ver auditoría académica completa">
              <i data-lucide="eye" class="w-3 h-3 text-cyan-400"></i>
              <span>Auditoría</span>
            </button>
            <button onclick="abrirModalEditarUsuario(${a.id}, '${escapeHtml(a.nombre)}', '${a.correo}', 'Aprendiz', ${a.organizacion_id || (adminConvenioData?.organizacion?.id || 13)}, ${a.mentor_id || 'null'})" class="px-2 py-1 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 text-[11px] font-bold inline-flex items-center gap-1 transition-colors border border-amber-200" title="Editar datos del estudiante">
              <i data-lucide="edit-3" class="w-3 h-3 text-amber-600"></i>
              <span>Editar</span>
            </button>
            <button onclick="abrirModalEliminarUsuario(${a.id}, '${escapeHtml(a.nombre)}', '${a.correo}')" class="px-2 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 text-[11px] font-bold inline-flex items-center gap-1 transition-colors border border-rose-200" title="Eliminar estudiante con respaldo en papelera">
              <i data-lucide="trash-2" class="w-3 h-3 text-rose-600"></i>
              <span>Eliminar</span>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
  refrescarIconos();
}

function filtrarAprendicesAdminConvenio() {
  const query = (document.getElementById('input-buscar-aprendiz-admin')?.value || '').toLowerCase().trim();
  if (!adminConvenioData || !adminConvenioData.aprendices) return;

  if (!query) {
    adminAprendicesFiltrados = adminConvenioData.aprendices;
  } else {
    adminAprendicesFiltrados = adminConvenioData.aprendices.filter(a =>
      a.nombre.toLowerCase().includes(query) ||
      a.correo.toLowerCase().includes(query) ||
      (a.mentor_nombre && a.mentor_nombre.toLowerCase().includes(query))
    );
  }
  renderizarTablaAprendicesAdmin();
}

// =====================================================================
// CUADROS DE HONOR & RANKINGS POR ROL (TOP 10 APRENDICES, TOP 5 MENTORES, TOP 5 MI AULA)
// =====================================================================
function renderizarCuadroHonorTop10AprendicesAdmin(aprendices) {
  const tbody = document.getElementById('tabla-top10-aprendices-admin-body');
  if (!tbody) return;

  if (!aprendices || aprendices.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-400 font-medium">No se encontraron estudiantes para el Cuadro de Honor.</td></tr>`;
    return;
  }

  const top10 = [...aprendices]
    .sort((a, b) => ((b.promedio_avance || 0) - (a.promedio_avance || 0)) || ((b.total_minutos || 0) - (a.total_minutos || 0)))
    .slice(0, 10);

  const medallas = ['🥇 #1', '🥈 #2', '🥉 #3'];
  const insignias = [
    'bg-amber-100 text-amber-900 border-amber-300 font-black',
    'bg-slate-200 text-slate-800 border-slate-300 font-black',
    'bg-orange-100 text-orange-900 border-orange-300 font-black'
  ];

  tbody.innerHTML = top10.map((a, idx) => {
    const puesto = idx + 1;
    const medalla = puesto <= 3 ? medallas[idx] : `#${puesto}`;
    const estiloInsignia = puesto <= 3 ? insignias[idx] : 'bg-slate-100 text-slate-700 border-slate-200 font-bold';
    const avance = Math.round(a.promedio_avance || 0);
    const tiempo = a.total_minutos || 0;
    const racha = a.racha_semanal || 1;

    return `
      <tr class="hover:bg-slate-50 transition-colors ${puesto <= 3 ? 'bg-amber-50/20' : ''}">
        <td class="py-3 text-center">
          <span class="inline-flex items-center justify-center px-2.5 py-1 rounded-xl text-xs border shadow-2xs ${estiloInsignia}">
            ${medalla}
          </span>
        </td>
        <td class="py-3">
          <div class="flex items-center gap-3">
            ${a.foto_perfil 
              ? `<img src="${a.foto_perfil}" class="w-8 h-8 rounded-full object-cover border border-slate-200 shrink-0 shadow-2xs">` 
              : `<div class="w-8 h-8 rounded-full bg-cyan-100 text-cyan-900 font-bold text-xs flex items-center justify-center shrink-0 border border-cyan-200">${obtenerIniciales(a.nombre)}</div>`}
            <div class="min-w-0">
              <strong class="font-bold text-[#0a192f] block truncate">${escapeHtml(a.nombre)}</strong>
              <span class="font-mono text-[11px] text-slate-500 block truncate">${escapeHtml(a.correo)}</span>
            </div>
          </div>
        </td>
        <td class="py-3">
          <div class="flex items-center gap-1.5 text-xs text-purple-800 font-semibold">
            <i data-lucide="graduation-cap" class="w-3.5 h-3.5 text-purple-600 shrink-0"></i>
            <span class="truncate">${escapeHtml(a.mentor_nombre || 'Sin tutor asignado')}</span>
          </div>
        </td>
        <td class="py-3">
          <div class="flex items-center gap-2">
            <div class="w-24 bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
              <div class="bg-gradient-to-r from-cyan-600 to-blue-600 h-2 rounded-full" style="width: ${avance}%"></div>
            </div>
            <span class="font-extrabold text-[#0a192f] text-xs">${avance}%</span>
          </div>
        </td>
        <td class="py-3 font-semibold text-xs text-slate-700">
          ⏱️ ${tiempo} min
        </td>
        <td class="py-3 text-center">
          <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-black text-xs">
            🔥 ${racha}
          </span>
        </td>
      </tr>
    `;
  }).join('');
  refrescarIconos();
}

function renderizarCuadroHonorTop5MentoresAdmin(mentores) {
  const container = document.getElementById('contenedor-cards-top5-mentores-admin');
  if (!container) return;

  if (!mentores || mentores.length === 0) {
    container.innerHTML = `<div class="p-6 text-center text-purple-300/70 col-span-full font-medium">No se encontraron mentores para el Cuadro de Honor docente.</div>`;
    return;
  }

  const top5 = [...mentores]
    .sort((a, b) => ((b.promedio_formacion_pct || 0) - (a.promedio_formacion_pct || 0)) || ((b.cursos_completados || 0) - (a.cursos_completados || 0)) || ((b.aprendices_a_cargo || 0) - (a.aprendices_a_cargo || 0)))
    .slice(0, 5);

  const medallas = ['🥇 #1', '🥈 #2', '🥉 #3', '#4', '#5'];
  const gradientes = [
    'from-amber-500/20 via-amber-900/30 to-slate-900/40 border-amber-400/50',
    'from-slate-400/20 via-slate-700/30 to-slate-900/40 border-slate-300/50',
    'from-orange-500/20 via-orange-900/30 to-slate-900/40 border-orange-400/50',
    'from-purple-900/40 to-slate-900/40 border-purple-700/40',
    'from-purple-900/40 to-slate-900/40 border-purple-700/40'
  ];

  container.innerHTML = top5.map((m, idx) => {
    const puesto = idx + 1;
    const medalla = medallas[idx];
    const grad = gradientes[idx];
    const pct = Math.round(m.promedio_formacion_pct || 0);
    const alumnos = m.aprendices_a_cargo || 0;
    const cursos = m.cursos_completados || 0;
    const racha = m.racha || 3;

    return `
      <div class="rounded-2xl p-4 bg-gradient-to-b ${grad} border flex flex-col justify-between transition-all hover:scale-[1.02] shadow-sm">
        <div>
          <div class="flex items-center justify-between mb-3">
            <span class="px-2.5 py-1 rounded-xl text-xs font-black bg-white/10 text-white border border-white/20 shadow-2xs">
              ${medalla}
            </span>
            <span class="text-[10px] font-bold text-amber-300">🔥 ${racha} sem</span>
          </div>

          <div class="flex items-center gap-3 mb-3">
            ${m.foto_perfil 
              ? `<img src="${m.foto_perfil}" class="w-10 h-10 rounded-xl object-cover border-2 border-purple-300 shrink-0 shadow-sm">` 
              : `<div class="w-10 h-10 rounded-xl bg-purple-600/40 text-purple-200 font-black text-xs flex items-center justify-center shrink-0 border border-purple-400/40">${obtenerIniciales(m.nombre)}</div>`}
            <div class="min-w-0">
              <h5 class="font-extrabold text-white text-xs truncate" title="${escapeHtml(m.nombre)}">${escapeHtml(m.nombre)}</h5>
              <p class="text-[10px] text-purple-200/80 font-mono truncate" title="${escapeHtml(m.correo)}">${escapeHtml(m.correo)}</p>
            </div>
          </div>
        </div>

        <div class="space-y-2 pt-2.5 border-t border-white/10 text-xs">
          <div>
            <div class="flex justify-between text-[11px] font-bold mb-1">
              <span class="text-purple-200">Formación</span>
              <span class="text-emerald-300 font-extrabold">${pct}%</span>
            </div>
            <div class="w-full bg-slate-900/60 rounded-full h-1.5 overflow-hidden">
              <div class="bg-gradient-to-r from-emerald-400 to-teal-400 h-1.5 rounded-full" style="width: ${pct}%"></div>
            </div>
          </div>

          <div class="flex items-center justify-between text-[10px] text-purple-200/90 pt-1 font-semibold">
            <span>👥 ${alumnos} alumnos</span>
            <span>📚 ${cursos} cursos</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
  refrescarIconos();
}

function renderizarCuadroHonorTop5AprendicesMentor(alumnos) {
  const tbody = document.getElementById('tabla-top5-aprendices-mentor-body');
  if (!tbody) return;

  if (!alumnos || alumnos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-400 font-medium">No se encontraron estudiantes para el Cuadro de Honor de tu clase.</td></tr>`;
    return;
  }

  const top5 = [...alumnos]
    .sort((a, b) => ((b.promedio_avance || 0) - (a.promedio_avance || 0)) || ((b.quizzes_aprobados || 0) - (a.quizzes_aprobados || 0)) || ((b.minutos_dedicados || b.total_minutos || 0) - (a.minutos_dedicados || a.total_minutos || 0)))
    .slice(0, 5);

  const medallas = ['🥇 #1', '🥈 #2', '🥉 #3', '#4', '#5'];
  const insignias = [
    'bg-amber-100 text-amber-900 border-amber-300 font-black',
    'bg-slate-200 text-slate-800 border-slate-300 font-black',
    'bg-orange-100 text-orange-900 border-orange-300 font-black',
    'bg-slate-100 text-slate-700 border-slate-200 font-bold',
    'bg-slate-100 text-slate-700 border-slate-200 font-bold'
  ];

  tbody.innerHTML = top5.map((a, idx) => {
    const puesto = idx + 1;
    const medalla = medallas[idx];
    const estiloInsignia = insignias[idx];
    const avance = Math.round(a.promedio_avance || 0);
    const mins = a.minutos_dedicados || a.total_minutos || 0;
    const racha = (a.racha_semanas !== undefined) ? a.racha_semanas : (a.racha_semanal || 5);
    const quizzesAprob = a.quizzes_aprobados || 0;
    const quizzesTotal = a.quizzes_completados || 0;

    return `
      <tr class="hover:bg-slate-50 transition-colors ${idx < 3 ? 'bg-amber-50/20' : ''}">
        <td class="py-3 text-center">
          <span class="inline-flex items-center justify-center px-2.5 py-1 rounded-xl text-xs border shadow-2xs ${estiloInsignia}">
            ${medalla}
          </span>
        </td>
        <td class="py-3">
          <div class="flex items-center gap-3">
            ${a.foto_perfil 
              ? `<img src="${a.foto_perfil}" class="w-8 h-8 rounded-full object-cover border border-slate-200 shrink-0 shadow-2xs">` 
              : `<div class="w-8 h-8 rounded-full bg-cyan-100 text-cyan-900 font-bold text-xs flex items-center justify-center shrink-0 border border-cyan-200">${obtenerIniciales(a.nombre)}</div>`}
            <div class="min-w-0">
              <strong class="font-bold text-[#0a192f] block truncate">${escapeHtml(a.nombre)}</strong>
              <span class="font-mono text-[11px] text-cyan-700 block truncate">${escapeHtml(a.correo)}</span>
            </div>
          </div>
        </td>
        <td class="py-3">
          <div class="flex items-center gap-2">
            <div class="w-24 bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
              <div class="bg-gradient-to-r from-cyan-600 to-blue-600 h-2 rounded-full" style="width: ${avance}%"></div>
            </div>
            <span class="font-extrabold text-[#0a192f] text-xs">${avance}%</span>
          </div>
        </td>
        <td class="py-3">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-purple-50 text-purple-800 border border-purple-200 font-bold text-xs">
            <i data-lucide="award" class="w-3.5 h-3.5 text-purple-600"></i>
            <span>${quizzesAprob} de ${quizzesTotal} (${quizzesTotal > 0 ? Math.round((quizzesAprob/quizzesTotal)*100) : 0}%)</span>
          </span>
        </td>
        <td class="py-3 font-semibold text-xs text-slate-700">
          ⏱️ ${mins} min
        </td>
        <td class="py-3 text-center">
          <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-black text-xs">
            🔥 ${racha} sem
          </span>
        </td>
      </tr>
    `;
  }).join('');
  refrescarIconos();
}

function abrirModalCargarExcelConvenio() {
  const finp = document.getElementById('excel-file-convenio-input');
  if (finp) finp.value = '';
  document.getElementById('modal-cargar-excel-convenio').classList.remove('hidden');
  refrescarIconos();
}

async function procesarCargaExcelConvenio(event) {
  event.preventDefault();
  if (!currentUser || !currentUser.organizacion_id) {
    return mostrarToast('No se encontró la organización asociada a tu cuenta institucional.', 'error');
  }

  const fileInput = document.getElementById('excel-file-convenio-input');
  const btnSubmit = document.getElementById('btn-submit-excel-convenio');
  if (!fileInput.files || fileInput.files.length === 0) {
    return mostrarToast('Selecciona un archivo Excel (.xlsx) o CSV.', 'advertencia');
  }

  const modoRadio = document.querySelector('input[name="modo-dominio-convenio"]:checked');
  const modo_dominio = modoRadio ? modoRadio.value : 'flexible';

  const formData = new FormData();
  formData.append('organizacion_id', currentUser.organizacion_id);
  formData.append('modo_dominio', modo_dominio);
  formData.append('archivo', fileInput.files[0]);

  btnSubmit.disabled = true;
  btnSubmit.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Importando (${modo_dominio})...</span>`;
  refrescarIconos();

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/usuarios/cargar-excel`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al procesar el archivo Excel');

    const des = data.desglose || {};
    mostrarToast(`✓ ${data.registrados} usuarios registrados (${des.administradores || 0} Admins, ${des.mentores || 0} Mentores, ${des.aprendices || 0} Aprendices).`, 'exito');

    if (data.alertas && data.alertas.length > 0) {
      data.alertas.slice(0, 3).forEach(a => mostrarToast(a, 'advertencia'));
    }

    cerrarModal('modal-cargar-excel-convenio');
    cargarVistaAdminConvenio();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.innerHTML = `<i data-lucide="upload" class="w-4 h-4"></i><span>Procesar y Cargar</span>`;
    refrescarIconos();
  }
}

// =====================================================================
// 9. VISTA MENTOR: SUPERVISIÓN & CAPACITACIONES PARA MENTORES
// =====================================================================
let chartMentorRendimiento = null;
let chartMentorQuizzes = null;

async function cargarProgresoAlumnosMentor() {
  if (!currentUser) return;
  const tbody = document.getElementById('tabla-mentor-alumnos-body');
  const badgeTotal = document.getElementById('badge-mentor-total-alumnos');
  if (!tbody) return;

  try {
    let res = await fetch(`${API_BASE}/api/mentor/${currentUser.id}/alumnos-detalle`);
    let json = await res.json();
    let alumnos = json.data || [];

    if (alumnos.length === 0) {
      res = await fetch(`${API_BASE}/api/mentores/progreso-aprendices/${currentUser.id}`);
      json = await res.json();
      alumnos = json.data || [];
    }

    if (badgeTotal) badgeTotal.innerText = `${alumnos.length} alumnos`;
    window.mentorAlumnosActuales = alumnos;
    renderizarCuadroHonorTop5AprendicesMentor(alumnos);

    if (alumnos.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-slate-400">No tienes aprendices asignados en este momento.</td></tr>`;
    } else {
      const mapeoTemas = {
        'estandar': { icono: '🏛️', nombre: 'Estándar' },
        'navidad': { icono: '🎄', nombre: 'Navideño' },
        'halloween': { icono: '🎃', nombre: 'Halloween' },
        'pascua': { icono: '🐰', nombre: 'Pascuas' },
        'superheroes': { icono: '🦸', nombre: 'Superhéroes' },
        'galaxia': { icono: '🌌', nombre: 'Galaxia' },
        'cyberpunk': { icono: '🕹️', nombre: 'Cyberpunk' }
      };

      tbody.innerHTML = alumnos.map(a => {
        const pct = Math.round(a.promedio_avance || 0);
        const temaKey = a.tema_decorativo || 'estandar';
        const temaInfo = mapeoTemas[temaKey] || { icono: '✨', nombre: temaKey };
        const tieneFoto = Boolean(a.fondo_personalizado);
        const racha = (a.racha_semanas !== undefined) ? a.racha_semanas : 5;
        const mins = a.minutos_dedicados || a.total_minutos || 0;
        const quizzesHechos = a.quizzes_completados || 0;
        const quizzesAprob = a.quizzes_aprobados || 0;

        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="py-3">
              <div class="flex items-center gap-3">
                ${a.foto_perfil 
                  ? `<img src="${a.foto_perfil}" class="w-9 h-9 rounded-full object-cover border border-slate-200 shrink-0 shadow-2xs">` 
                  : `<div class="w-9 h-9 rounded-full bg-slate-200 text-[#0a192f] font-bold text-xs flex items-center justify-center shrink-0">${obtenerIniciales(a.nombre)}</div>`}
                <div class="min-w-0">
                  <strong class="font-bold text-[#0a192f] block truncate">${escapeHtml(a.nombre)}</strong>
                  <span class="font-mono text-[11px] text-cyan-700 block truncate">${escapeHtml(a.correo)}</span>
                </div>
              </div>
            </td>
            <td class="py-3 text-slate-700 font-semibold text-xs">
              ⏱️ ${mins} min
            </td>
            <td class="py-3">
              <span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-extrabold text-xs">
                🔥 ${racha} sem
              </span>
            </td>
            <td class="py-3">
              <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-slate-100 text-slate-800 text-xs font-bold border border-slate-200">
                <span>${temaInfo.icono}</span>
                <span>${temaInfo.nombre}</span>
                ${tieneFoto ? '<span title="Foto personalizada activa">🖼️</span>' : ''}
              </span>
            </td>
            <td class="py-3">
              <div class="flex items-center space-x-2">
                <div class="progress-track-cyan w-20">
                  <div class="progress-bar-cyan" style="width: ${pct}%;"></div>
                </div>
                <span class="font-bold text-xs text-[#0a192f]">${pct}%</span>
              </div>
            </td>
            <td class="py-3">
              <span class="px-2.5 py-1 rounded-lg bg-purple-50 text-purple-800 font-bold text-xs border border-purple-200">
                ${quizzesHechos} hechos (${quizzesAprob} aprob.)
              </span>
            </td>
            <td class="py-3 text-right">
              <button onclick="abrirDetalleProgresoAprendiz(${a.id})" class="px-3 py-1.5 rounded-xl bg-[#091b2c] hover:bg-[#0f273f] text-cyan-300 hover:text-white text-xs font-bold inline-flex items-center gap-1.5 transition-colors shadow-2xs" title="Ver auditoría académica completa">
                <i data-lucide="eye" class="w-3.5 h-3.5"></i>
                <span>Ver Auditoría</span>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    cargarMetricasYGraficasMentor();
    cargarQuizzesMentor();
    cargarCapacitacionesMentor(currentUser.id);
    refrescarIconos();
  } catch (e) {
    console.error('Error cargando alumnos del mentor:', e);
  }
}

async function cargarMetricasYGraficasMentor() {
  if (!currentUser) return;
  try {
    const res = await fetch(`${API_BASE}/api/mentor/${currentUser.id}/metricas-clase`);
    if (!res.ok) return;
    const data = await res.json();

    const elTot = document.getElementById('kpi-mentor-total-alumnos');
    if (elTot) elTot.innerText = `${data.total_alumnos || 0}`;
    const elCur = document.getElementById('kpi-mentor-promedio-cursos');
    if (elCur) elCur.innerText = `${data.promedio_avance_cursos || 0}%`;
    const elQz = document.getElementById('kpi-mentor-promedio-quizzes');
    if (elQz) elQz.innerText = `${data.promedio_calif_quizzes || 0}%`;
    const elTime = document.getElementById('kpi-mentor-tiempo-total');
    if (elTime) elTime.innerText = `${data.tiempo_total_horas || 0} hrs`;

    // Gráfica de Barras: Rendimiento Cursos vs Quizzes
    const ctxBar = document.getElementById('chart-mentor-rendimiento-clase');
    if (ctxBar && typeof Chart !== 'undefined') {
      if (chartMentorRendimiento) chartMentorRendimiento.destroy();
      chartMentorRendimiento = new Chart(ctxBar, {
        type: 'bar',
        data: {
          labels: data.labels && data.labels.length ? data.labels : ['Sin estudiantes'],
          datasets: [
            {
              label: 'Avance Cursos (%)',
              data: data.series_avance_cursos && data.series_avance_cursos.length ? data.series_avance_cursos : [0],
              backgroundColor: '#0284C7',
              borderRadius: 6
            },
            {
              label: 'Calificación Quizzes (%)',
              data: data.series_calif_quizzes && data.series_calif_quizzes.length ? data.series_calif_quizzes : [0],
              backgroundColor: '#8B5CF6',
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              max: 100,
              ticks: { callback: v => `${v}%` }
            }
          },
          plugins: {
            legend: { position: 'top' }
          }
        }
      });
    }

    // Gráfica de Dona: Distribución Quizzes
    const ctxPie = document.getElementById('chart-mentor-distribucion-quizzes');
    if (ctxPie && typeof Chart !== 'undefined') {
      if (chartMentorQuizzes) chartMentorQuizzes.destroy();
      const dist = data.distribucion_quizzes || { aprobados: 0, no_aprobados: 0, pendientes: 0 };
      const totalDist = dist.aprobados + dist.no_aprobados + dist.pendientes;
      chartMentorQuizzes = new Chart(ctxPie, {
        type: 'doughnut',
        data: {
          labels: ['Aprobados', 'No Aprobados', 'Pendientes'],
          datasets: [{
            data: totalDist > 0 ? [dist.aprobados, dist.no_aprobados, dist.pendientes] : [1, 0, 0],
            backgroundColor: totalDist > 0 ? ['#10B981', '#F59E0B', '#94A3B8'] : ['#E2E8F0'],
            borderWidth: 2,
            borderColor: '#FFFFFF'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom' }
          }
        }
      });
    }
  } catch (err) {
    console.error('Error cargando métricas y gráficas del mentor:', err);
  }
}

function descargarInformeExcelMentor() {
  if (!currentUser) return;
  mostrarToast('Generando informe de mi clase en Excel (.xlsx) con gráficas nativas...', 'info');
  window.location.href = `${API_BASE}/api/mentor/${currentUser.id}/reporte-excel-clase`;
}

// Subtabs y Gestión de Formación de Mentores para Administradores Institucionales
let adminMentoresFormacionData = null;

function cambiarSubTabAdminConvenio(tab) {
  const btnApr = document.getElementById('btn-subtab-admin-aprendices');
  const btnMen = document.getElementById('btn-subtab-admin-mentores');
  const secApr = document.getElementById('sec-admin-tab-aprendices');
  const secMen = document.getElementById('sec-admin-tab-mentores');
  if (!secApr || !secMen) return;

  if (tab === 'aprendices') {
    btnApr?.classList.remove('bg-slate-100', 'text-slate-700');
    btnApr?.classList.add('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnMen?.classList.remove('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnMen?.classList.add('bg-slate-100', 'text-slate-700');
    secApr.classList.remove('hidden');
    secMen.classList.add('hidden');
  } else {
    btnMen?.classList.remove('bg-slate-100', 'text-slate-700');
    btnMen?.classList.add('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnApr?.classList.remove('bg-[#091b2c]', 'text-white', 'shadow-xs');
    btnApr?.classList.add('bg-slate-100', 'text-slate-700');
    secApr.classList.add('hidden');
    secMen.classList.remove('hidden');
    cargarMentoresRendimientoAdmin();
  }
  refrescarIconos();
}

async function cargarMentoresRendimientoAdmin() {
  if (!adminConvenioData || !adminConvenioData.organizacion) return;
  const orgId = adminConvenioData.organizacion.id;
  const tbody = document.getElementById('tabla-admin-mentores-formacion-body');
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/admin/convenio/${orgId}/mentores-rendimiento`);
    if (!res.ok) throw new Error('Error consultando formación docente');
    const json = await res.json();
    adminMentoresFormacionData = json.data || [];

    const elTot = document.getElementById('kpi-admin-docentes-total');
    if (elTot) elTot.innerText = `${json.total_mentores || 0}`;
    const elProm = document.getElementById('kpi-admin-docentes-promedio');
    if (elProm) elProm.innerText = `${json.promedio_formacion_equipo || 0}%`;
    const elHoras = document.getElementById('kpi-admin-docentes-horas');
    if (elHoras) elHoras.innerText = `${json.total_horas_docentes || 0} hrs`;
    const elDest = document.getElementById('kpi-admin-docentes-destacados');
    if (elDest) elDest.innerText = `${json.mentores_destacados || 0}`;

    // Actualizar Cuadro de Honor del Mejor Mentor Docente
    if (adminMentoresFormacionData.length > 0) {
      const topMen = [...adminMentoresFormacionData].sort((a, b) => ((b.promedio_formacion_pct || 0) - (a.promedio_formacion_pct || 0)) || ((b.aprendices_a_cargo || 0) - (a.aprendices_a_cargo || 0)))[0];
      const elTopMenNom = document.getElementById('top-mentor-admin-nombre');
      const elTopMenCor = document.getElementById('top-mentor-admin-correo');
      const elTopMenAlu = document.getElementById('top-mentor-admin-alumnos');
      const elTopMenAv = document.getElementById('top-mentor-admin-avance');
      const elTopMenCur = document.getElementById('top-mentor-admin-cursos');
      const elTopMenRa = document.getElementById('top-mentor-admin-racha');
      const elTopMenAvWrap = document.getElementById('top-mentor-admin-avatar-wrap');

      if (elTopMenNom) elTopMenNom.innerText = topMen.nombre || 'Mentor';
      if (elTopMenCor) elTopMenCor.innerText = topMen.correo || '--';
      if (elTopMenAlu) elTopMenAlu.innerText = `${topMen.aprendices_a_cargo || 0}`;
      if (elTopMenAv) elTopMenAv.innerText = `${Math.round(topMen.promedio_formacion_pct || 0)}%`;
      if (elTopMenCur) elTopMenCur.innerText = `${topMen.cursos_completados || 0}`;
      if (elTopMenRa) elTopMenRa.innerText = `🔥 ${topMen.racha || 3}`;
      if (elTopMenAvWrap) {
        if (topMen.foto_perfil) {
          elTopMenAvWrap.innerHTML = `<img src="${topMen.foto_perfil}" class="w-full h-full object-cover">`;
        } else {
          elTopMenAvWrap.innerHTML = `<span id="top-mentor-admin-iniciales">${obtenerIniciales(topMen.nombre)}</span>`;
        }
      }
    }

    renderizarCuadroHonorTop5MentoresAdmin(adminMentoresFormacionData);

    if (adminMentoresFormacionData.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-center text-slate-400">No hay mentores registrados en esta institución.</td></tr>`;
    } else {
      tbody.innerHTML = adminMentoresFormacionData.map(m => {
        const pct = Math.round(m.promedio_formacion_pct || 0);
        return `
          <tr class="hover:bg-slate-50 transition-colors">
            <td class="py-3">
              <div class="flex items-center gap-3">
                ${m.foto_perfil 
                  ? `<img src="${m.foto_perfil}" class="w-8 h-8 rounded-full object-cover border border-slate-200 shrink-0 shadow-2xs">` 
                  : `<div class="w-8 h-8 rounded-full bg-purple-100 text-purple-800 font-bold text-xs flex items-center justify-center shrink-0">${obtenerIniciales(m.nombre)}</div>`}
                <div class="min-w-0">
                  <strong class="font-bold text-[#0a192f] block truncate">${escapeHtml(m.nombre)}</strong>
                  <span class="font-mono text-[11px] text-slate-500 block truncate">${escapeHtml(m.correo)}</span>
                </div>
              </div>
            </td>
            <td class="py-3 font-semibold text-slate-700">${m.aprendices_a_cargo || 0} estudiantes</td>
            <td class="py-3">
              <div class="flex items-center space-x-2">
                <div class="progress-track-cyan w-20">
                  <div class="progress-bar-cyan" style="width: ${pct}%;"></div>
                </div>
                <span class="font-bold text-xs text-[#0a192f]">${pct}%</span>
              </div>
            </td>
            <td class="py-3 font-medium text-slate-600">${m.cursos_completados || 0} de ${m.total_cursos_docentes || 0}</td>
            <td class="py-3 font-semibold text-[#0a192f]">⏱️ ${m.horas_formacion || 0} hrs (${m.minutos_formacion || 0} min)</td>
            <td class="py-3">
              <span class="px-2.5 py-1 rounded-full text-[11px] font-bold ${m.badge_color === 'emerald' ? 'bg-emerald-100 text-emerald-800' : (m.badge_color === 'amber' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700')}">
                ${m.rendimiento}
              </span>
            </td>
            <td class="py-3 text-right">
              <div class="flex items-center justify-end gap-1.5 flex-wrap">
                <button onclick="abrirModalDetalleMentorAdmin(${m.id})" class="px-2.5 py-1.5 rounded-xl bg-[#091b2c] hover:bg-[#0f273f] text-cyan-300 hover:text-white text-xs font-bold inline-flex items-center gap-1 transition-colors shadow-2xs" title="Ver formación, cursos y alumnos del mentor">
                  <i data-lucide="eye" class="w-3.5 h-3.5 text-cyan-400"></i>
                  <span>Ver Cursos</span>
                </button>
                <button onclick="abrirModalEditarUsuario(${m.id}, '${escapeHtml(m.nombre)}', '${m.correo}', 'Mentor', ${m.organizacion_id || (adminConvenioData?.organizacion?.id || 'null')}, null)" class="px-2.5 py-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-bold inline-flex items-center gap-1 transition-colors border border-amber-200" title="Editar mentor">
                  <i data-lucide="edit-3" class="w-3.5 h-3.5 text-amber-600"></i>
                  <span>Editar</span>
                </button>
                <button onclick="abrirModalEliminarUsuario(${m.id}, '${escapeHtml(m.nombre)}', '${m.correo}')" class="px-2.5 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold inline-flex items-center gap-1 transition-colors border border-rose-200" title="Eliminar mentor con respaldo en papelera">
                  <i data-lucide="trash-2" class="w-3.5 h-3.5 text-rose-600"></i>
                  <span>Eliminar</span>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }
    refrescarIconos();
  } catch (err) {
    console.error('Error cargando formación de mentores:', err);
  }
}

function abrirModalDetalleMentorAdmin(mentorId) {
  if (!adminMentoresFormacionData) return;
  const m = adminMentoresFormacionData.find(item => item.id === mentorId);
  if (!m) return;

  document.getElementById('detalle-men-nombre').innerText = m.nombre;
  document.getElementById('detalle-men-correo').innerText = m.correo;
  document.getElementById('detalle-men-meta').innerText = `${adminConvenioData?.organizacion?.nombre || 'Institución'} · Programa de Capacitación Docente`;
  document.getElementById('detalle-men-promedio').innerText = `${Math.round(m.promedio_formacion_pct || 0)}%`;
  document.getElementById('detalle-men-cursos-completados').innerText = `${m.cursos_completados || 0} de ${m.total_cursos_docentes || 0}`;
  document.getElementById('detalle-men-tiempo').innerText = `${m.horas_formacion || 0} hrs`;
  document.getElementById('detalle-men-alumnos-count').innerText = `${m.aprendices_a_cargo || 0}`;

  const avEl = document.getElementById('detalle-men-avatar');
  if (avEl) {
    if (m.foto_perfil) {
      avEl.innerHTML = `<img src="${m.foto_perfil}" alt="${escapeHtml(m.nombre)}" class="w-full h-full object-cover rounded-2xl">`;
    } else {
      avEl.innerText = obtenerIniciales(m.nombre);
    }
  }

  const badgeEl = document.getElementById('detalle-men-badge-rendimiento');
  if (badgeEl) badgeEl.innerText = m.rendimiento;

  const lista = document.getElementById('detalle-men-lista-capacitaciones');
  const cursos = m.cursos_detalle || [];
  if (lista) {
    if (cursos.length === 0) {
      lista.innerHTML = `<div class="p-6 text-center text-slate-400 text-xs">No hay cursos pedagógicos asignados.</div>`;
    } else {
      lista.innerHTML = cursos.map(c => {
        const avance = Math.round(c.porcentaje_avance || 0);
        const comp = avance >= 80;
        return `
          <div class="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex flex-col justify-between">
            <div class="flex items-start justify-between gap-2">
              <div>
                <span class="text-[10px] font-bold uppercase tracking-wider text-purple-700">Trayectoria Docente</span>
                <h5 class="text-xs font-bold text-[#0a192f] mt-0.5">${escapeHtml(c.titulo)}</h5>
              </div>
              <span class="text-[10px] font-bold px-2 py-0.5 rounded ${comp ? 'bg-emerald-100 text-emerald-800' : (avance > 0 ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-600')}">
                ${comp ? '🏆 Completado' : (avance > 0 ? 'En Progreso' : 'Sin Iniciar')}
              </span>
            </div>
            <div class="mt-2.5">
              <div class="flex items-center justify-between text-[11px] mb-1">
                <span class="text-slate-500 font-medium">Módulos: ${c.modulos_completados} de ${c.total_modulos}</span>
                <span class="font-extrabold text-[#0a192f]">${avance}%</span>
              </div>
              <div class="progress-track-cyan">
                <div class="progress-bar-cyan" style="width: ${avance}%;"></div>
              </div>
              <p class="text-[10px] text-slate-400 mt-1 font-medium">${c.tiempo_minutos || 0} minutos dedicados</p>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  document.getElementById('modal-detalle-mentor-capacitaciones')?.classList.remove('hidden');
  refrescarIconos();
}

function descargarInformeExcelMentoresAdmin() {
  if (!adminConvenioData || !adminConvenioData.organizacion) return;
  const orgId = adminConvenioData.organizacion.id;
  mostrarToast('Generando reporte oficial de mentores y formación en Excel (.xlsx)...', 'info');
  window.location.href = `${API_BASE}/api/admin/convenio/${orgId}/reporte-excel-mentores`;
}

async function cargarCapacitacionesMentor(mentorId) {
  const grid = document.getElementById('grid-mentor-capacitaciones');
  if (!grid) return;

  try {
    const res = await fetch(`${API_BASE}/api/mentores/mis-capacitaciones/${mentorId}`);
    const json = await res.json();
    const materiales = json.data || [];

    if (materiales.length === 0) {
      grid.innerHTML = `<div class="p-6 text-center text-slate-400 col-span-full text-xs">No hay capacitaciones para mentores asignadas en este momento.</div>`;
      return;
    }

    grid.innerHTML = materiales.map(m => `
      <div class="corp-card p-5 flex flex-col justify-between border-t-4 border-purple-500 hover:shadow-md transition-shadow">
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-[10px] font-bold text-purple-700 uppercase tracking-wider">${m.tipo_material || 'Docente'}</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800">Para Mentores</span>
          </div>
          <h4 class="text-sm font-bold text-[#0a192f] mb-2 leading-snug">${m.titulo}</h4>
        </div>
        <div class="pt-3 border-t border-slate-100 mt-3">
          <a href="${m.enlace_url}" target="_blank" class="w-full py-2 rounded-xl bg-[#091b2c] hover:bg-[#0f273f] text-white text-xs font-bold flex items-center justify-center gap-1.5 transition-colors">
            <span>Iniciar Capacitación</span>
            <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
          </a>
        </div>
      </div>
    `).join('');
    refrescarIconos();
  } catch (e) {
    console.error('Error cargando capacitaciones de mentor:', e);
  }
}

// =====================================================================
// 10. MÉTRICAS VISUALES & GRÁFICAS INTERACTIVAS (CHART.JS)
// =====================================================================
async function actualizarMetricas() {
  try {
    const res = await fetch(`${API_BASE}/api/metricas/graficas-progreso`);
    const json = await res.json();

    const dist = json.distribucion || {};
    const cursosStats = json.cursos_estadisticas || [];
    const topAprendices = json.top_aprendices || [];

    // Actualizar contadores
    const statOrgs = document.getElementById('stat-total-orgs');
    if (statOrgs) statOrgs.innerText = allOrganizations.length || 0;

    const statUsers = document.getElementById('stat-total-usuarios');
    if (statUsers) statUsers.innerText = json.total_aprendices || 0;

    const statMentores = document.getElementById('stat-total-mentores');
    if (statMentores) statMentores.innerText = (allHierarchyData.mentores || []).length || 0;

    const resAudit = await fetch(`${API_BASE}/api/auditoria/listar`);
    const dataAudit = await resAudit.json();
    const statAudit = document.getElementById('stat-total-auditoria');
    if (statAudit) statAudit.innerText = dataAudit.total || 0;

    // Renderizar Gráfica 1: Dona de Distribución de Avance
    renderizarGraficaDona(dist);

    // Renderizar Gráfica 2: Barras de Progreso por Curso
    renderizarGraficaBarras(cursosStats);

    // Renderizar Tabla Top Aprendices
    renderizarTopAprendices(topAprendices);
  } catch (e) {
    console.error('Error cargando métricas:', e);
  }
}

function renderizarGraficaDona(dist) {
  const canvas = document.getElementById('chartProgresoDona');
  if (!canvas || !window.Chart) return;

  if (chartDonaInstance) {
    chartDonaInstance.destroy();
  }

  const ctx = canvas.getContext('2d');
  chartDonaInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Completado (≥90%)', 'Avanzado (60-89%)', 'En Progreso (25-59%)', 'Inicial (<25%)'],
      datasets: [{
        data: [
          dist.completados || 0,
          dist.avanzados || 0,
          dist.en_progreso || 0,
          dist.iniciales || 0
        ],
        backgroundColor: ['#00b4d8', '#38bdf8', '#f59e0b', '#cbd5e1'],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            boxWidth: 12,
            font: { size: 11, family: 'Plus Jakarta Sans' }
          }
        }
      }
    }
  });
}

function renderizarGraficaBarras(cursosStats) {
  const canvas = document.getElementById('chartProgresoBarras');
  if (!canvas || !window.Chart) return;

  if (chartBarrasInstance) {
    chartBarrasInstance.destroy();
  }

  const titulos = cursosStats.map(c => c.titulo.length > 25 ? c.titulo.substring(0, 25) + '...' : c.titulo);
  const avances = cursosStats.map(c => Math.round(c.promedio_curso || 0));

  const ctx = canvas.getContext('2d');
  chartBarrasInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: titulos.length > 0 ? titulos : ['Sin cursos con avance'],
      datasets: [{
        label: '% Avance Promedio',
        data: avances.length > 0 ? avances : [0],
        backgroundColor: '#00b4d8',
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      scales: {
        x: {
          beginAtZero: true,
          max: 100,
          ticks: { font: { size: 10 } }
        },
        y: {
          ticks: { font: { size: 10, family: 'Plus Jakarta Sans' } }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderizarTopAprendices(top) {
  const tbody = document.getElementById('tabla-top-aprendices-body');
  if (!tbody) return;

  if (top.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-slate-400">No hay registros de aprendices activos.</td></tr>`;
    return;
  }

  tbody.innerHTML = top.map(a => {
    const avance = Math.round(a.promedio_avance || 0);
    return `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-2.5 font-bold text-[#0a192f]">${a.nombre}</td>
        <td class="py-2.5 text-slate-600">${a.organizacion_nombre || 'N/A'}</td>
        <td class="py-2.5">
          <div class="flex items-center space-x-2">
            <div class="progress-track-cyan w-20">
              <div class="progress-bar-cyan" style="width: ${avance}%;"></div>
            </div>
            <span class="font-bold text-xs text-[#0a192f]">${avance}%</span>
          </div>
        </td>
        <td class="py-2.5 text-slate-600 font-medium">${a.total_minutos || 0} min</td>
      </tr>
    `;
  }).join('');
}

// =====================================================================
// 11. CATÁLOGO DE CONTENIDOS & CREACIÓN
// =====================================================================
async function cargarMateriales() {
  try {
    const res = await fetch(`${API_BASE}/api/material/catalogo`);
    const json = await res.json();
    const grid = document.getElementById('grid-materiales-corp');
    if (!grid) return;

    const mats = json.data || [];
    catalogoColeccionesActuales = mats;
    if (mats.length === 0) {
      grid.innerHTML = `<div class="p-8 text-center text-slate-400 col-span-full font-medium">No hay contenidos en el catálogo.</div>`;
      return;
    }

    const puedeEliminar = currentUser && (currentUser.rol === 'Super Administrador' || currentUser.rol === 'Administrador');
    const esAprendiz = currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante');
    const puedeEnviarOrg = currentUser && (currentUser.rol === 'Super Administrador' || currentUser.rol === 'Administrador' || currentUser.rol === 'Mentor');

    const contAccionesCatalogo = document.getElementById('contenedor-acciones-catalogo');
    if (contAccionesCatalogo) {
      if (esAprendiz) {
        contAccionesCatalogo.classList.add('hidden');
      } else {
        contAccionesCatalogo.classList.remove('hidden');
      }
    }

    grid.innerHTML = mats.map(m => {
      const botonEliminar = puedeEliminar ? `
        <button onclick="confirmarEliminarMaterial(${m.id}, '${escapeHtml(m.titulo)}')" title="Eliminar colección del catálogo" class="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors">
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
        </button>
      ` : '';

      const botonEnviarOrg = (puedeEnviarOrg && !esAprendiz) ? `
        <button onclick="abrirModalEnviarColeccion(${m.id})" class="btn-catalogo-enviar" title="${t('cat_btn_enviar_org_title', 'Enviar / Asignar esta colección a una institución')}">
          <i data-lucide="send" class="w-3.5 h-3.5"></i>
          <span>${t('cat_btn_enviar_org', 'Enviar a Org')}</span>
        </button>
      ` : '';

      const rolDestinoTexto = m.rol_destino === 'Mentor' 
        ? ('👨‍🏫 ' + t('cat_para_mentores', 'Para Mentores')) 
        : (m.rol_destino === 'Todos' ? ('🌐 ' + t('cat_global', 'Global')) : ('🎓 ' + t('cat_para_aprendices', 'Para Aprendices')));

      return `
        <div class="corp-card p-5 flex flex-col justify-between hover:shadow-md transition-shadow relative">
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-[10px] font-bold text-cyan-600 uppercase tracking-wider">${m.tipo_material || 'Curso'}</span>
              <div class="flex items-center space-x-1">
                <span class="px-2 py-0.5 rounded text-[10px] font-extrabold badge-catalogo-modulos">
                  ${m.total_modulos || 3} ${t('cat_modulos', 'Módulos')}
                </span>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded badge-catalogo-rol">
                  ${rolDestinoTexto}
                </span>
                ${botonEliminar}
              </div>
            </div>
            <h4 class="text-sm font-bold text-[#0a192f] mt-1 mb-2 leading-snug">${m.titulo}</h4>
            ${m.organizacion_nombre ? `<p class="text-[11px] text-slate-400 mb-2 font-medium">${t('cat_institucion', 'Institución')}: <span class="text-slate-600 font-semibold">${m.organizacion_nombre}</span></p>` : `<p class="text-[11px] text-cyan-600 mb-2 font-medium">${t('cat_acceso_global', 'Acceso Global (Todas)')}</p>`}
          </div>
          <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2 flex-wrap">
            <a href="${m.enlace_url}" target="_blank" class="btn-catalogo-explorar flex-1">
              <span>${t('cat_explorar_material', 'Explorar Material')}</span>
              <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
            </a>
            ${botonEnviarOrg}
          </div>
        </div>
      `;
    }).join('');
    refrescarIconos();
  } catch (e) {
    console.error('Error cargando catálogo:', e);
  }
}

function abrirModalCrearMaterial() {
  if (currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante')) {
    mostrarToast('Los aprendices no tienen permisos para subir material.', 'error');
    return;
  }
  document.getElementById('modal-crear-material').classList.remove('hidden');
}

async function guardarNuevoMaterial(event) {
  event.preventDefault();
  if (currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante')) {
    mostrarToast('Los aprendices no tienen permisos para subir material.', 'error');
    return;
  }
  const titulo = document.getElementById('mat-titulo').value.trim();
  const tipo_material = document.getElementById('mat-tipo').value;
  const enlace_url = document.getElementById('mat-url').value.trim();
  const rol_destino = document.getElementById('mat-rol-destino').value;
  const total_modulos = parseInt(document.getElementById('mat-modulos')?.value || 3);
  const orgVal = document.getElementById('mat-asignar-org').value;
  const organizacion_id = orgVal ? parseInt(orgVal) : null;

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/material/crear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ titulo, tipo_material, enlace_url, rol_destino, total_modulos, organizacion_id })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al subir material');

    mostrarToast('✓ Material o colección agregada al catálogo con éxito.', 'exito');
    cerrarModal('modal-crear-material');
    document.getElementById('mat-titulo').value = '';
    document.getElementById('mat-url').value = '';
    cargarMateriales();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------------------------------------------------------------------
// ENVIAR / ASIGNAR COLECCIÓN CON FLUJO JERÁRQUICO Y ALERTA ANTI-DUPLICADOS
// Flujo: Super Admin -> Institución (Admins) -> Mentores -> Aprendices
// ---------------------------------------------------------------------
let integrantesOrgCache = {};

async function abrirModalEnviarColeccion(materialId = null) {
  if (currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante')) {
    mostrarToast('Los aprendices no tienen permisos para enviar o asignar colecciones.', 'error');
    return;
  }
  try {
    const rolUsuario = currentUser?.rol || 'Super Administrador';
    const orgUsuarioId = currentUser?.organizacion_id;

    // Configurar visibilidad de opciones jerárquicas según el rol
    const lblInst = document.getElementById('lbl-dest-institucion');
    const lblMent = document.getElementById('lbl-dest-mentores');
    const lblApren = document.getElementById('lbl-dest-aprendices');
    const badgeRolInfo = document.getElementById('badge-enviar-org-rol-info');

    let nivelPorDefecto = 'Institución';

    if (rolUsuario === 'Super Administrador') {
      if (lblInst) lblInst.classList.remove('hidden');
      if (lblMent) lblMent.classList.remove('hidden');
      if (lblApren) lblApren.classList.remove('hidden');
      if (badgeRolInfo) badgeRolInfo.innerText = 'Rol: Super Administrador (Global)';
      nivelPorDefecto = 'Institución';
    } else if (rolUsuario === 'Administrador') {
      // El Administrador Institucional distribuye a sus Mentores o a sus Aprendices
      if (lblInst) lblInst.classList.add('hidden');
      if (lblMent) lblMent.classList.remove('hidden');
      if (lblApren) lblApren.classList.remove('hidden');
      if (badgeRolInfo) badgeRolInfo.innerText = 'Rol: Administrador Institucional';
      nivelPorDefecto = 'Mentores';
    } else if (rolUsuario === 'Mentor') {
      // El Mentor distribuye directamente a sus Aprendices
      if (lblInst) lblInst.classList.add('hidden');
      if (lblMent) lblMent.classList.add('hidden');
      if (lblApren) lblApren.classList.remove('hidden');
      if (badgeRolInfo) badgeRolInfo.innerText = 'Rol: Mentor / Tutor';
      nivelPorDefecto = 'Aprendices';
    }

    // Configurar organizaciones
    const selectOrg = document.getElementById('select-enviar-org');
    if (selectOrg) {
      if (allOrganizations.length === 0) {
        const resOrg = await fetch(`${API_BASE}/api/organizaciones/listar`);
        const jsonOrg = await resOrg.json();
        allOrganizations = jsonOrg.data || [];
      }
      selectOrg.innerHTML = '<option value="">Elegir colegio, empresa o institución...</option>' +
        allOrganizations.map(o => `<option value="${o.id}">🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`).join('');

      if (rolUsuario === 'Super Administrador') {
        selectOrg.disabled = false;
        const orgActual = document.getElementById('select-analitica-org')?.value;
        if (orgActual) {
          selectOrg.value = orgActual;
        } else if (allOrganizations.length > 0) {
          selectOrg.value = allOrganizations[0].id;
        }
      } else {
        // Para administradores y mentores, la organización queda fijada a su institución
        if (orgUsuarioId) {
          selectOrg.value = orgUsuarioId;
          selectOrg.disabled = true;
        }
      }
    }

    // Configurar catálogo de colecciones
    const selectCol = document.getElementById('select-enviar-coleccion');
    if (selectCol) {
      if (catalogoColeccionesActuales.length === 0) {
        const resMat = await fetch(`${API_BASE}/api/material/catalogo`);
        const jsonMat = await resMat.json();
        catalogoColeccionesActuales = jsonMat.data || [];
      }
      selectCol.innerHTML = '<option value="">Elegir colección de Microsoft Learn...</option>' +
        catalogoColeccionesActuales.map(m => `<option value="${m.id}">📚 ${m.titulo} (${m.total_modulos || 3} Módulos)</option>`).join('');

      if (materialId) selectCol.value = materialId;
    }

    // Cargar todas las asignaciones existentes para alerta anti-duplicados
    const resAsig = await fetch(`${API_BASE}/api/superadmin/colecciones/asignaciones-todas`);
    const jsonAsig = await resAsig.json();
    todasAsignacionesColecciones = jsonAsig.data || [];

    // Marcar nivel por defecto en radio buttons
    const radios = document.getElementsByName('radio-destinatario-nivel');
    radios.forEach(r => {
      r.checked = (r.value === nivelPorDefecto);
    });

    await cambioOrganizacionEnvioColeccion();
    cambiarNivelDestinoColeccion(nivelPorDefecto);

    const modal = document.getElementById('modal-enviar-coleccion-org');
    if (modal) modal.classList.remove('hidden');
    refrescarIconos();
  } catch (e) {
    console.error('Error preparando envío de colección:', e);
    mostrarToast('Error al preparar el envío de la colección.', 'error');
  }
}

async function cambioOrganizacionEnvioColeccion() {
  const selectOrg = document.getElementById('select-enviar-org');
  const orgId = selectOrg ? parseInt(selectOrg.value) : null;
  if (!orgId) return;

  if (!integrantesOrgCache[orgId]) {
    try {
      const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/integrantes-por-rol`);
      if (res.ok) {
        const data = await res.json();
        integrantesOrgCache[orgId] = data;
      }
    } catch (err) {
      console.warn('No se pudieron obtener integrantes por rol:', err);
    }
  }

  const nivelActual = document.querySelector('input[name="radio-destinatario-nivel"]:checked')?.value || 'Institución';
  actualizarOpcionesDestinatarioEspecifico(orgId, nivelActual);
  verificarDuplicadoColeccionEnvio();
}

function cambiarNivelDestinoColeccion(nivel) {
  // Actualizar estilos visuales de las tarjetas de selección
  const tarjetas = document.querySelectorAll('.opcion-destino-card');
  tarjetas.forEach(t => {
    const input = t.querySelector('input[type="radio"]');
    if (input && input.value === nivel) {
      t.classList.add('seleccionado', 'border-cyan-600', 'bg-cyan-50/60');
      t.classList.remove('border-slate-200', 'bg-white');
    } else {
      t.classList.remove('seleccionado', 'border-cyan-600', 'bg-cyan-50/60');
      t.classList.add('border-slate-200', 'bg-white');
    }
  });

  const selectOrg = document.getElementById('select-enviar-org');
  const orgId = selectOrg ? parseInt(selectOrg.value) : null;
  actualizarOpcionesDestinatarioEspecifico(orgId, nivel);
  verificarDuplicadoColeccionEnvio();
}

function actualizarOpcionesDestinatarioEspecifico(orgId, nivel) {
  const contEspecifico = document.getElementById('contenedor-destinatario-especifico');
  const selectEspecifico = document.getElementById('select-destinatario-especifico');
  const lblEspecifico = document.getElementById('lbl-select-destinatario-especifico');
  const badgeTotal = document.getElementById('badge-total-destinatarios-especificos');
  const txtExplicacion = document.getElementById('txt-explicacion-jerarquia');

  const cache = orgId ? integrantesOrgCache[orgId] : null;

  if (nivel === 'Institución') {
    if (contEspecifico) contEspecifico.classList.add('hidden');
    if (txtExplicacion) {
      txtExplicacion.innerHTML = `
        <span class="text-sm shrink-0">💡</span>
        <span><strong>Institución (Administradores):</strong> La colección se asigna al catálogo institucional. Sus administradores la recibirán con privilegios para distribuirla luego a sus mentores.</span>
      `;
    }
    return;
  }

  if (contEspecifico) contEspecifico.classList.remove('hidden');

  if (nivel === 'Mentores') {
    const mentores = cache?.mentores || [];
    if (lblEspecifico) lblEspecifico.innerText = 'Seleccionar mentor destino:';
    if (badgeTotal) badgeTotal.innerText = `${mentores.length} mentor(es) disponible(s)`;
    if (selectEspecifico) {
      selectEspecifico.innerHTML = `<option value="todos">🌟 Todos los Mentores de la Institución (${mentores.length})</option>` +
        mentores.map(m => `<option value="${m.id}">👨‍🏫 ${escapeHtml(m.nombre)} (${escapeHtml(m.correo)})</option>`).join('');
    }
    if (txtExplicacion) {
      txtExplicacion.innerHTML = `
        <span class="text-sm shrink-0">💡</span>
        <span><strong>Mentores (Docentes):</strong> La colección se asigna a los mentores para que preparen su plan de formación y la asignen posteriormente a sus estudiantes.</span>
      `;
    }
  } else if (nivel === 'Aprendices') {
    const aprendices = cache?.aprendices || [];
    if (lblEspecifico) lblEspecifico.innerText = 'Seleccionar estudiante destino:';
    if (badgeTotal) badgeTotal.innerText = `${aprendices.length} aprendiz(es) disponible(s)`;
    if (selectEspecifico) {
      selectEspecifico.innerHTML = `<option value="todos">🌟 Todos los Aprendices de la Institución (${aprendices.length})</option>` +
        aprendices.map(a => `<option value="${a.id}">🎓 ${escapeHtml(a.nombre)} (${escapeHtml(a.correo)})</option>`).join('');
    }
    if (txtExplicacion) {
      txtExplicacion.innerHTML = `
        <span class="text-sm shrink-0">💡</span>
        <span><strong>Aprendices (Estudiantes):</strong> Los estudiantes son matriculados directamente en la colección con seguimiento activo de módulos, tiempos y avances.</span>
      `;
    }
  }
}

function verificarDuplicadoColeccionEnvio() {
  const selectOrg = document.getElementById('select-enviar-org');
  const selectCol = document.getElementById('select-enviar-coleccion');
  const previewCard = document.getElementById('preview-coleccion-envio');
  const alertaBox = document.getElementById('alerta-duplicado-coleccion');
  const btnSubmit = document.getElementById('btn-confirmar-enviar-coleccion');

  const orgId = selectOrg ? parseInt(selectOrg.value) : null;
  const colId = selectCol ? parseInt(selectCol.value) : null;
  const nivel = document.querySelector('input[name="radio-destinatario-nivel"]:checked')?.value || 'Institución';
  const destEspVal = document.getElementById('select-destinatario-especifico')?.value;
  const destId = (destEspVal && destEspVal !== 'todos') ? parseInt(destEspVal) : null;

  if (colId && catalogoColeccionesActuales.length > 0) {
    const col = catalogoColeccionesActuales.find(c => c.id === colId);
    if (col && previewCard) {
      previewCard.classList.remove('hidden');
      const tipoEl = document.getElementById('preview-col-tipo');
      const modEl = document.getElementById('preview-col-modulos');
      const titEl = document.getElementById('preview-col-titulo');
      const urlEl = document.getElementById('preview-col-url');
      if (tipoEl) tipoEl.innerText = col.tipo_material || 'Colección Microsoft';
      if (modEl) modEl.innerText = `${col.total_modulos || 3} Módulos de Formación`;
      if (titEl) titEl.innerText = col.titulo;
      if (urlEl) urlEl.href = col.enlace_url;
    }
  } else if (previewCard) {
    previewCard.classList.add('hidden');
  }

  if (!alertaBox) return;

  if (!orgId || !colId) {
    alertaBox.className = 'hidden';
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.classList.remove('opacity-50', 'cursor-not-allowed');
    }
    return;
  }

  const orgNombre = selectOrg.options[selectOrg.selectedIndex]?.text || 'esta institución';

  // Verificar si ya fue asignada según el nivel y destinatario
  let yaEnviada = false;
  let motivoDuplicado = '';

  if (nivel === 'Institución') {
    yaEnviada = todasAsignacionesColecciones.some(a => 
      a.material_id === colId && a.organizacion_id === orgId && 
      (a.destinatario_tipo === 'Institución' || !a.destinatario_tipo)
    );
    motivoDuplicado = `La colección ya fue asignada previamente a la directiva/administradores de <strong>${orgNombre}</strong>. Ya está disponible en su catálogo institucional.`;
  } else if (nivel === 'Mentores') {
    if (destId) {
      yaEnviada = todasAsignacionesColecciones.some(a => 
        a.material_id === colId && a.organizacion_id === orgId && 
        a.destinatario_tipo === 'Mentores' && a.destinatario_id == destId
      );
      motivoDuplicado = `Esta colección ya fue asignada específicamente a este mentor seleccionado.`;
    } else {
      yaEnviada = todasAsignacionesColecciones.some(a => 
        a.material_id === colId && a.organizacion_id === orgId && 
        a.destinatario_tipo === 'Mentores' && (!a.destinatario_id || a.destinatario_id == 0)
      );
      motivoDuplicado = `Esta colección ya fue enviada previamente a todos los mentores de <strong>${orgNombre}</strong>.`;
    }
  } else if (nivel === 'Aprendices') {
    if (destId) {
      yaEnviada = todasAsignacionesColecciones.some(a => 
        a.material_id === colId && a.organizacion_id === orgId && 
        a.destinatario_tipo === 'Aprendices' && a.destinatario_id == destId
      );
      motivoDuplicado = `Este estudiante ya se encuentra matriculado en esta colección.`;
    } else {
      yaEnviada = todasAsignacionesColecciones.some(a => 
        a.material_id === colId && a.organizacion_id === orgId && 
        a.destinatario_tipo === 'Aprendices' && (!a.destinatario_id || a.destinatario_id == 0)
      );
      motivoDuplicado = `Esta colección ya fue enviada y matriculada a todos los aprendices de <strong>${orgNombre}</strong>.`;
    }
  }

  if (yaEnviada) {
    alertaBox.className = 'alerta-caja-error p-3.5 rounded-xl border text-xs flex items-start gap-2 shadow-sm animate-pulse';
    alertaBox.innerHTML = `
      <i data-lucide="alert-triangle" class="w-4 h-4 text-rose-500 shrink-0 mt-0.5"></i>
      <div>
        <strong class="font-extrabold block">⚠️ ¡Alerta! Esta colección ya fue enviada a este destino</strong>
        <p class="text-[11px] mt-0.5 opacity-90">${motivoDuplicado}</p>
      </div>
    `;
    if (btnSubmit) {
      btnSubmit.disabled = true;
      btnSubmit.classList.add('opacity-50', 'cursor-not-allowed');
    }
  } else {
    alertaBox.className = 'alerta-caja-exito p-3.5 rounded-xl border text-xs flex items-start gap-2 shadow-sm';
    let detalleExito = '';
    if (nivel === 'Institución') {
      detalleExito = `Se asignará al catálogo de <strong>${orgNombre}</strong> para que sus administradores la reciban.`;
    } else if (nivel === 'Mentores') {
      detalleExito = destId ? `Se asignará al mentor seleccionado para preparación docente.` : `Se asignará a todos los mentores de <strong>${orgNombre}</strong>.`;
    } else {
      detalleExito = destId ? `El estudiante quedará matriculado con seguimiento formativo activo.` : `Todos los aprendices de <strong>${orgNombre}</strong> serán matriculados con seguimiento formativo.`;
    }

    alertaBox.innerHTML = `
      <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-500 shrink-0 mt-0.5"></i>
      <div>
        <strong class="font-bold block">✓ Colección disponible para enviar (${nivel})</strong>
        <p class="text-[11px] mt-0.5 opacity-90">${detalleExito}</p>
      </div>
    `;
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  }
  refrescarIconos();
}

async function ejecutarEnviarColeccionOrganizacion(event) {
  event.preventDefault();
  const selectOrg = document.getElementById('select-enviar-org');
  const selectCol = document.getElementById('select-enviar-coleccion');
  const btnSubmit = document.getElementById('btn-confirmar-enviar-coleccion');

  const orgId = parseInt(selectOrg.value);
  const colId = parseInt(selectCol.value);
  const nivel = document.querySelector('input[name="radio-destinatario-nivel"]:checked')?.value || 'Institución';
  const destEspVal = document.getElementById('select-destinatario-especifico')?.value;
  const destId = (destEspVal && destEspVal !== 'todos') ? parseInt(destEspVal) : null;

  if (!orgId || !colId) {
    mostrarToast('Por favor selecciona la institución y la colección.', 'error');
    return;
  }

  try {
    if (btnSubmit) {
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = 'Enviando colección...';
    }

    const payload = {
      material_id: colId,
      organizacion_id: orgId,
      destinatario_tipo: nivel,
      destinatario_id: destId,
      remitente_id: currentUser?.id || null,
      remitente_rol: currentUser?.rol || 'Administración'
    };

    const res = await fetch(`${API_BASE}/api/superadmin/colecciones/enviar-a-organizacion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al enviar colección');

    mostrarToast(data.mensaje || '✓ Colección enviada con éxito.', 'exito');
    cerrarModal('modal-enviar-coleccion-org');
    
    // Recargar catálogo y asignaciones
    cargarMateriales();
    const selectAnalitica = document.getElementById('select-analitica-org');
    if (selectAnalitica) {
      selectAnalitica.value = orgId;
      cargarAnaliticaPorOrganizacion(orgId);
    }
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = '<i data-lucide="send" class="w-4 h-4"></i><span>Confirmar y Enviar Colección</span>';
      refrescarIconos();
    }
  }
}

// ---------------------------------------------------------------------
// REFRESCO CENTRALIZADO DE SELECTORES DE ORGANIZACIONES
// ---------------------------------------------------------------------
async function refrescarTodosSelectoresOrganizaciones(selectedId = null) {
  try {
    const resOrg = await fetch(`${API_BASE}/api/organizaciones/listar`);
    const jsonOrg = await resOrg.json();
    allOrganizations = jsonOrg.data || [];

    // 1. Selector de Analítica en Métricas
    const selectAnalitica = document.getElementById('select-analitica-org');
    if (selectAnalitica) {
      const cur = selectedId || parseInt(selectAnalitica.value) || (allOrganizations[0]?.id || '');
      selectAnalitica.innerHTML = allOrganizations.map(o => 
        `<option value="${o.id}" ${o.id === cur ? 'selected' : ''}>🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`
      ).join('');
      if (cur) selectAnalitica.value = cur;
    }

    // 2. Selector de Grupos de Trabajo
    const selectGrupos = document.getElementById('select-org-grupos');
    if (selectGrupos) {
      const curG = selectedId || parseInt(selectGrupos.value) || (allOrganizations[0]?.id || '');
      selectGrupos.innerHTML = allOrganizations.map(o => 
        `<option value="${o.id}" ${o.id === curG ? 'selected' : ''}>🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`
      ).join('');
      if (curG) selectGrupos.value = curG;
    }

    // 3. Selector de El Celador - Nuevos Integrantes
    const contFiltroIntegrantes = document.getElementById('contenedor-filtro-org-integrantes');
    const selectCelador = document.getElementById('select-filtro-org-integrantes');
    if (currentUser && currentUser.rol !== 'Super Administrador') {
      if (contFiltroIntegrantes) contFiltroIntegrantes.classList.add('hidden');
    } else {
      if (contFiltroIntegrantes) contFiltroIntegrantes.classList.remove('hidden');
      if (selectCelador) {
        const curC = selectCelador.value || 'TODOS';
        let htmlC = '<option value="TODOS">Todas las organizaciones</option>';
        allOrganizations.forEach(o => {
          htmlC += `<option value="${o.id}" ${o.id == curC ? 'selected' : ''}>🏛️ ${o.nombre}</option>`;
        });
        selectCelador.innerHTML = htmlC;
      }
    }

    // 4. Selector de El Celador - Auditoría
    const contFiltroAudit = document.getElementById('contenedor-filtro-org-auditoria');
    const selectAuditOrg = document.getElementById('select-audit-org');
    if (currentUser && currentUser.rol !== 'Super Administrador') {
      if (contFiltroAudit) contFiltroAudit.classList.add('hidden');
    } else {
      if (contFiltroAudit) contFiltroAudit.classList.remove('hidden');
      if (selectAuditOrg) {
        const curA = selectAuditOrg.value || 'TODOS';
        let htmlA = '<option value="TODOS">Todas las organizaciones</option>';
        allOrganizations.forEach(o => {
          htmlA += `<option value="${o.nombre}" ${o.nombre === curA ? 'selected' : ''}>🏛️ ${o.nombre}</option>`;
        });
        selectAuditOrg.innerHTML = htmlA;
      }
    }

    // 5. Selector de Modal Crear Manual
    const selectManualOrg = document.getElementById('modal-crear-manual-org');
    if (selectManualOrg) {
      const curM = selectedId || parseInt(selectManualOrg.value) || (allOrganizations[0]?.id || '');
      selectManualOrg.innerHTML = allOrganizations.map(o => 
        `<option value="${o.id}" ${o.id === curM ? 'selected' : ''}>🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`
      ).join('');
      if (curM) selectManualOrg.value = curM;
    }

    // 6. Selector de Modal Enviar Colección
    const selectEnviarCol = document.getElementById('modal-enviar-col-org');
    if (selectEnviarCol) {
      const curE = selectedId || parseInt(selectEnviarCol.value) || (allOrganizations[0]?.id || '');
      selectEnviarCol.innerHTML = allOrganizations.map(o => 
        `<option value="${o.id}" ${o.id === curE ? 'selected' : ''}>🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`
      ).join('');
      if (curE) selectEnviarCol.value = curE;
    }

    // 7. Selector de Carga Excel general
    const selectSubirExcel = document.getElementById('subir-excel-org-id');
    if (selectSubirExcel) {
      const curS = selectedId || parseInt(selectSubirExcel.value) || (allOrganizations[0]?.id || '');
      selectSubirExcel.innerHTML = allOrganizations.map(o => 
        `<option value="${o.id}" ${o.id === curS ? 'selected' : ''}>🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`
      ).join('');
      if (curS) selectSubirExcel.value = curS;
    }
  } catch (err) {
    console.warn('Error refrescando selectores de organizaciones:', err);
  }
}

// ---------------------------------------------------------------------
// ANALÍTICA INSTITUCIONAL POR ORGANIZACIÓN (MÉTRICAS & MÓDULOS)
let chartAprendizPrivAvanceInstance = null;
let chartAprendizPrivQuizzesInstance = null;

async function cargarMetricasPrivadasAprendiz() {
  const contPriv = document.getElementById('contenedor-metricas-aprendiz-privadas');
  const barOrg = document.getElementById('barra-selector-metricas-org');
  const tabsInst = document.getElementById('tabs-metricas-institucionales');
  const tabRend = document.getElementById('tab-content-metricas-rendimiento');
  const tabApr = document.getElementById('tab-content-metricas-aprendices');
  const tabCat = document.getElementById('tab-content-metricas-catalogo');
  const titMet = document.getElementById('titulo-vista-metricas');
  const subMet = document.getElementById('subtitulo-vista-metricas');

  if (titMet) titMet.innerText = 'Mis Métricas & Gráficas';
  if (subMet) subMet.innerText = 'Expediente privado de avance, calificaciones en quizzes y dedicación en la plataforma.';
  if (barOrg) barOrg.classList.add('hidden');
  if (tabsInst) tabsInst.classList.add('hidden');
  if (tabRend) tabRend.classList.add('hidden');
  if (tabApr) tabApr.classList.add('hidden');
  if (tabCat) tabCat.classList.add('hidden');
  if (contPriv) contPriv.classList.remove('hidden');

  if (!currentUser) return;

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/aprendiz/${currentUser.id}/desglose-cursos`);
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al cargar métricas privadas');

    const u = json.aprendiz || {};
    const cursos = json.cursos || [];
    const quizzes = json.quizzes || [];
    const kpis = json.kpis || {};

    const elNom = document.getElementById('aprendiz-priv-nombre');
    const elRa = document.getElementById('aprendiz-priv-racha');
    const elTi = document.getElementById('aprendiz-priv-tiempo');
    const elAv = document.getElementById('aprendiz-priv-avatar');

    if (elNom) elNom.innerText = u.nombre || currentUser.nombre || 'Mi Perfil';
    if (elRa) elRa.innerText = `🔥 ${u.racha_semanal || currentUser.racha_semanal || 1}`;
    const totalMins = kpis.total_minutos || u.total_minutos || currentUser.total_minutos || 0;
    if (elTi) elTi.innerText = `${totalMins} min`;
    if (elAv) {
      if (u.foto_perfil || currentUser.foto_perfil) {
        elAv.innerHTML = `<img src="${u.foto_perfil || currentUser.foto_perfil}" class="w-full h-full object-cover">`;
      } else {
        elAv.innerHTML = `<span>${obtenerIniciales(u.nombre || currentUser.nombre)}</span>`;
      }
    }

    const kpiCur = document.getElementById('kpi-aprendiz-priv-cursos');
    const kpiAvPct = document.getElementById('kpi-aprendiz-priv-avance');
    const kpiQzH = document.getElementById('kpi-aprendiz-priv-quizzes-hechos');
    const kpiQzNota = document.getElementById('kpi-aprendiz-priv-quizzes-nota');

    if (kpiCur) kpiCur.innerText = kpis.total_cursos || cursos.length || 0;
    if (kpiAvPct) kpiAvPct.innerText = `${Math.round(kpis.promedio_general || 0)}%`;
    if (kpiQzH) kpiQzH.innerText = kpis.total_quizzes || quizzes.length || 0;
    if (kpiQzNota) kpiQzNota.innerText = `${Math.round(kpis.promedio_quizzes || 0)}%`;

    // Gráfica 1: Avance por Curso
    const canvasAv = document.getElementById('chartAprendizPrivAvance');
    if (canvasAv && window.Chart) {
      if (chartAprendizPrivAvanceInstance) chartAprendizPrivAvanceInstance.destroy();
      const ctxAv = canvasAv.getContext('2d');
      const labels = cursos.length > 0 ? cursos.map(c => (c.titulo.length > 20 ? c.titulo.substring(0, 20) + '...' : c.titulo)) : ['Sin cursos'];
      const valores = cursos.length > 0 ? cursos.map(c => Math.round(c.porcentaje_completado || 0)) : [0];

      chartAprendizPrivAvanceInstance = new Chart(ctxAv, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Mi Avance (%)',
            data: valores,
            backgroundColor: 'rgba(0, 180, 216, 0.75)',
            borderColor: '#00b4d8',
            borderWidth: 2,
            borderRadius: 8
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { min: 0, max: 100, ticks: { callback: v => v + '%' } }
          },
          plugins: {
            legend: { display: false }
          }
        }
      });
    }

    // Gráfica 2: Historial de Quizzes
    const canvasQz = document.getElementById('chartAprendizPrivQuizzes');
    if (canvasQz && window.Chart) {
      if (chartAprendizPrivQuizzesInstance) chartAprendizPrivQuizzesInstance.destroy();
      const ctxQz = canvasQz.getContext('2d');
      const labelsQz = quizzes.length > 0 ? quizzes.map(q => (q.quiz_titulo.length > 18 ? q.quiz_titulo.substring(0, 18) + '...' : q.quiz_titulo)) : ['Sin evaluaciones'];
      const valoresQz = quizzes.length > 0 ? quizzes.map(q => Math.round(q.puntaje_obtenido || 0)) : [0];

      chartAprendizPrivQuizzesInstance = new Chart(ctxQz, {
        type: 'line',
        data: {
          labels: labelsQz,
          datasets: [{
            label: 'Calificación (%)',
            data: valoresQz,
            borderColor: '#9333ea',
            backgroundColor: 'rgba(147, 51, 234, 0.15)',
            fill: true,
            tension: 0.35,
            pointRadius: 6,
            pointBackgroundColor: '#9333ea'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { min: 0, max: 100, ticks: { callback: v => v + '%' } }
          },
          plugins: {
            legend: { display: false }
          }
        }
      });
    }

    // Tabla de Quizzes Privada
    const tbodyQz = document.getElementById('tabla-aprendiz-priv-quizzes-body');
    const badgeTotQz = document.getElementById('badge-aprendiz-priv-total-quizzes');
    if (badgeTotQz) badgeTotQz.innerText = `${quizzes.length} evaluaciones`;

    if (tbodyQz) {
      if (quizzes.length === 0) {
        tbodyQz.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400">Aún no has presentado evaluaciones o quizzes en tus clases.</td></tr>`;
      } else {
        tbodyQz.innerHTML = quizzes.map(q => {
          const aprobado = (q.puntaje_obtenido || 0) >= 60;
          return `
            <tr class="hover:bg-slate-50 transition-colors">
              <td class="py-3 font-bold text-[#0a192f]">${escapeHtml(q.quiz_titulo || 'Evaluación')}</td>
              <td class="py-3 text-slate-600">${escapeHtml(q.mentor_nombre || 'Docente')}</td>
              <td class="py-3 font-extrabold text-sm ${aprobado ? 'text-emerald-600' : 'text-rose-600'}">${Math.round(q.puntaje_obtenido || 0)}%</td>
              <td class="py-3">
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${aprobado ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}">
                  ${aprobado ? 'Aprobado' : 'Reprobado'}
                </span>
              </td>
              <td class="py-3 text-slate-400 font-mono text-[11px]">${q.fecha_realizacion || '--'}</td>
            </tr>
          `;
        }).join('');
      }
    }

    refrescarIconos();
  } catch (err) {
    console.error('Error cargando métricas privadas del estudiante:', err);
  }
}

// ---------------------------------------------------------------------
async function cargarAnaliticaPorOrganizacion(orgId = null) {
  try {
    if (currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante')) {
      await cargarMetricasPrivadasAprendiz();
      return;
    }

    // Restaurar contenedores institucionales para otros roles
    const contPriv = document.getElementById('contenedor-metricas-aprendiz-privadas');
    const barOrg = document.getElementById('barra-selector-metricas-org');
    const tabsInst = document.getElementById('tabs-metricas-institucionales');
    const tabRend = document.getElementById('tab-content-metricas-rendimiento');
    if (contPriv) contPriv.classList.add('hidden');
    if (barOrg) barOrg.classList.remove('hidden');
    if (tabsInst) tabsInst.classList.remove('hidden');
    if (tabRend) tabRend.classList.remove('hidden');

    const titMet = document.getElementById('titulo-vista-metricas');
    const subMet = document.getElementById('subtitulo-vista-metricas');
    if (currentUser && currentUser.rol === 'Mentor') {
      if (titMet) titMet.innerText = 'Métricas & Gráficas de Mis Estudiantes';
      if (subMet) subMet.innerText = 'Seguimiento del rendimiento y avance en colecciones de los alumnos a tu cargo.';
    } else if (currentUser && currentUser.rol === 'Super Administrador') {
      if (titMet) titMet.innerText = 'Métricas y Desempeño Global';
      if (subMet) subMet.innerText = 'Supervisión integral de progreso, avance por módulos y rendimientos de todas las instituciones.';
    } else {
      if (titMet) titMet.innerText = 'Métricas y Desempeño Institucional';
      if (subMet) subMet.innerText = 'Supervisión integral de progreso y rendimientos académicos de la institución.';
    }

    const selectOrg = document.getElementById('select-analitica-org');
    if (!selectOrg) return;

    // Consultar SIEMPRE organizaciones frescas para que cualquier nueva aparezca al instante
    const resOrg = await fetch(`${API_BASE}/api/organizaciones/listar`);
    const jsonOrg = await resOrg.json();
    allOrganizations = jsonOrg.data || [];

    if (allOrganizations.length === 0) {
      selectOrg.innerHTML = '<option value="">No hay organizaciones registradas</option>';
      return;
    }

    let targetOrgId = orgId;
    const contSelect = document.getElementById('contenedor-select-analitica-org');
    const contBadge = document.getElementById('contenedor-badge-analitica-org');
    const badgeNombre = document.getElementById('badge-analitica-org-nombre');

    if (currentUser && currentUser.rol !== 'Super Administrador') {
      targetOrgId = currentUser.organizacion_id || allOrganizations[0].id;
      if (contSelect) contSelect.classList.add('hidden');
      if (contBadge) contBadge.classList.remove('hidden');
      if (badgeNombre) badgeNombre.innerText = currentUser.organizacion_nombre || 'Mi Institución';
    } else {
      if (contSelect) contSelect.classList.remove('hidden');
      if (contBadge) contBadge.classList.add('hidden');
      if (!targetOrgId) targetOrgId = parseInt(selectOrg.value) || allOrganizations[0].id;
      selectOrg.innerHTML = allOrganizations.map(o => 
        `<option value="${o.id}" ${o.id === targetOrgId ? 'selected' : ''}>🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`
      ).join('');
      selectOrg.value = targetOrgId;
    }

    const res = await fetch(`${API_BASE}/api/superadmin/organizaciones/${targetOrgId}/analitica-colecciones`);
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al cargar analítica');

    analiticaOrgActual = json;
    let estudiantes = json.estudiantes || [];
    if (currentUser && currentUser.rol === 'Mentor') {
      estudiantes = estudiantes.filter(e => e.mentor_id === currentUser.id || e.mentor_nombre === currentUser.nombre);
    }
    analiticaEstudiantesActuales = estudiantes;

    const totalEst = estudiantes.length;
    let promAvance = 0;
    let modCompletados = 0;
    let modTotales = 0;
    let finalizados = 0;

    if (totalEst > 0) {
      const sumAvance = estudiantes.reduce((acc, curr) => acc + (curr.promedio_avance || 0), 0);
      promAvance = Math.round(sumAvance / totalEst);
      modCompletados = estudiantes.reduce((acc, curr) => acc + (curr.modulos_completados || 0), 0);
      modTotales = estudiantes.reduce((acc, curr) => acc + (curr.modulos_asignados || 0), 0);
      finalizados = estudiantes.filter(e => (e.promedio_avance || 0) >= 100).length;
    }

    const kpiCol = document.getElementById('kpi-org-colecciones');
    const kpiApr = document.getElementById('kpi-org-aprendices');
    const kpiAvance = document.getElementById('kpi-org-avance-promedio');
    const kpiMod = document.getElementById('kpi-org-modulos');
    const kpiComp = document.getElementById('kpi-org-completados');
    const badgeTotal = document.getElementById('badge-org-total-col');

    if (kpiCol) kpiCol.innerText = json.kpis?.total_colecciones || 0;
    if (kpiApr) kpiApr.innerText = (currentUser && currentUser.rol === 'Mentor') ? totalEst : (json.kpis?.total_aprendices || 0);
    if (kpiAvance) kpiAvance.innerText = `${(currentUser && currentUser.rol === 'Mentor') ? promAvance : (json.kpis?.promedio_general_org || 0)}%`;
    if (kpiMod) kpiMod.innerText = (currentUser && currentUser.rol === 'Mentor') ? `${modCompletados} / ${modTotales}` : `${json.kpis?.modulos_completados_totales || 0} / ${json.kpis?.modulos_asignados_totales || 0}`;
    if (kpiComp) kpiComp.innerText = `${(currentUser && currentUser.rol === 'Mentor') ? (totalEst > 0 ? Math.round((finalizados / totalEst) * 100) : 0) : (json.kpis?.tasa_finalizacion_org || 0)}%`;
    if (badgeTotal) badgeTotal.innerText = `${(json.colecciones || []).length} colecciones asignadas`;

    renderizarColeccionesOrganizacion(json.colecciones || []);
    cargarColeccionesEstadoOrganizacion(targetOrgId);
    renderizarGraficasOrganizacion(json);
    renderizarTablaEstudiantesAnalitica();

    refrescarIconos();
  } catch (e) {
    console.error('Error cargando analítica por organización:', e);
  }
}

function cambiarOrganizacionAnalitica(orgId) {
  if (orgId) {
    cargarAnaliticaPorOrganizacion(parseInt(orgId));
  }
}

function renderizarColeccionesOrganizacion(colecciones) {
  const grid = document.getElementById('grid-org-colecciones-analitica');
  if (!grid) return;

  if (colecciones.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full p-8 text-center bg-slate-50 border border-slate-200 rounded-2xl">
        <div class="w-12 h-12 rounded-xl bg-cyan-50 text-cyan-700 flex items-center justify-center mx-auto mb-2">
          <i data-lucide="layers" class="w-6 h-6"></i>
        </div>
        <h4 class="text-sm font-bold text-slate-700">Esta organización no tiene colecciones asignadas</h4>
        <p class="text-xs text-slate-400 mt-1 max-w-sm mx-auto">Utiliza el botón "Enviar Colección a esta Institución" para comenzar el seguimiento de sus aprendices.</p>
        <button onclick="abrirModalEnviarColeccion()" class="mt-3 px-3.5 py-1.5 rounded-xl bg-cyan-700 hover:bg-cyan-800 text-white text-xs font-bold shadow-sm inline-flex items-center gap-1.5">
          <i data-lucide="send" class="w-3.5 h-3.5"></i>
          <span>Enviar Primera Colección</span>
        </button>
      </div>
    `;
    refrescarIconos();
    return;
  }

  const orgId = analiticaOrgActual?.organizacion?.id;

  grid.innerHTML = colecciones.map(c => {
    const totalMod = c.total_modulos || 3;
    const prom = Math.round(c.promedio_avance || 0);

    const dist = c.distribucion_modulos || {};
    const chipsModulos = [];
    for (let i = 0; i <= totalMod; i++) {
      const cant = dist[`${i}_modulos`] || 0;
      chipsModulos.push(`<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">${cant} con ${i} mód.</span>`);
    }

    return `
      <div class="corp-card p-5 flex flex-col justify-between hover:shadow-md transition-shadow border border-slate-200">
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-[10px] font-bold text-cyan-600 uppercase tracking-wider">${c.tipo_material || 'Colección Microsoft'}</span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-purple-100 text-purple-800 border border-purple-200">
              ${totalMod} Módulos
            </span>
          </div>

          <h4 class="text-sm font-bold text-[#0a192f] leading-snug mb-1.5">${c.titulo}</h4>
          
          <a href="${c.enlace_url}" target="_blank" class="text-[11px] text-cyan-600 hover:text-cyan-800 font-semibold underline flex items-center gap-1 mb-3">
            <span>Ruta en Microsoft Learn</span>
            <i data-lucide="external-link" class="w-3 h-3"></i>
          </a>

          <!-- Barra de Progreso del Avance Promedio -->
          <div class="space-y-1 mb-3">
            <div class="flex items-center justify-between text-[11px] font-bold">
              <span class="text-slate-600">Avance Promedio:</span>
              <span class="${prom >= 80 ? 'text-emerald-700' : (prom >= 40 ? 'text-cyan-700' : 'text-amber-700')}">${prom}%</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
              <div class="h-2 rounded-full ${prom >= 80 ? 'bg-emerald-500' : (prom >= 40 ? 'bg-cyan-600' : 'bg-amber-500')} transition-all" style="width: ${prom}%"></div>
            </div>
          </div>

          <!-- Métricas Resumen -->
          <div class="grid grid-cols-3 gap-2 py-2 border-y border-slate-100 text-center mb-3">
            <div>
              <span class="text-[10px] text-slate-400 font-bold block uppercase">Matriculados</span>
              <strong class="text-xs text-slate-800 font-black">${c.total_aprendices_matriculados || 0}</strong>
            </div>
            <div>
              <span class="text-[10px] text-slate-400 font-bold block uppercase">En Progreso</span>
              <strong class="text-xs text-cyan-700 font-black">${c.estudiantes_en_progreso || 0}</strong>
            </div>
            <div>
              <span class="text-[10px] text-slate-400 font-bold block uppercase">Certificados</span>
              <strong class="text-xs text-emerald-700 font-black">${c.estudiantes_completados || 0}</strong>
            </div>
          </div>

          <!-- Distribución de módulos -->
          <div class="flex items-center gap-1 flex-wrap mb-2">
            ${chipsModulos.join('')}
          </div>
        </div>

        <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
          <span class="text-[10px] text-slate-400 font-mono">ID Colección #${c.id}</span>
          <button onclick="desvincularColeccionOrganizacion(${c.id}, ${orgId})" class="text-[11px] text-rose-600 hover:text-rose-800 font-bold hover:underline" title="Desvincular colección de esta organización">
            Desvincular
          </button>
        </div>
      </div>
    `;
  }).join('');
  refrescarIconos();
}

function renderizarGraficasOrganizacion(data) {
  const colecciones = data.colecciones || [];
  const estudiantes = data.estudiantes || [];

  const canvasBarras = document.getElementById('chartOrgColeccionesBarras');
  if (canvasBarras && window.Chart) {
    if (chartOrgColeccionesInstance) chartOrgColeccionesInstance.destroy();

    const labels = colecciones.map(c => c.titulo.length > 20 ? c.titulo.substring(0, 20) + '...' : c.titulo);
    const valores = colecciones.map(c => Math.round(c.promedio_avance || 0));

    const ctx = canvasBarras.getContext('2d');
    chartOrgColeccionesInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels.length > 0 ? labels : ['Sin colecciones'],
        datasets: [{
          label: '% Avance Promedio',
          data: valores.length > 0 ? valores : [0],
          backgroundColor: '#0284c7',
          borderRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true, max: 100, ticks: { font: { size: 10 } } },
          x: { ticks: { font: { size: 10, family: 'Plus Jakarta Sans' } } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  const canvasDona = document.getElementById('chartOrgModulosDona');
  if (canvasDona && window.Chart) {
    if (chartOrgModulosInstance) chartOrgModulosInstance.destroy();

    let c0 = 0, c1 = 0, c2 = 0, c3 = 0;
    estudiantes.forEach(e => {
      const m = e.total_modulos_completados || 0;
      if (m === 0) c0++;
      else if (m === 1) c1++;
      else if (m === 2) c2++;
      else c3++;
    });

    const ctx = canvasDona.getContext('2d');
    chartOrgModulosInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['0 Módulos (Sin iniciar)', '1 Módulo cursado', '2 Módulos cursados', '3+ Módulos (Certificados)'],
        datasets: [{
          data: [c0, c1, c2, c3],
          backgroundColor: ['#cbd5e1', '#38bdf8', '#0284c7', '#059669'],
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 12, font: { size: 10, family: 'Plus Jakarta Sans' } }
          }
        }
      }
    });
  }
}

function renderizarTablaEstudiantesAnalitica() {
  const tbody = document.getElementById('tabla-org-estudiantes-body');
  if (!tbody) return;

  const query = document.getElementById('input-buscar-aprendiz-analitica')?.value.toLowerCase().trim() || '';
  let lista = analiticaEstudiantesActuales;
  if (currentUser && currentUser.rol === 'Mentor') {
    lista = lista.filter(e => e.mentor_id === currentUser.id || e.mentor_correo === currentUser.correo || (e.mentor_nombre && e.mentor_nombre === currentUser.nombre));
  }

  const filtrados = lista.filter(e => {
    return !query ||
      e.nombre.toLowerCase().includes(query) ||
      e.correo.toLowerCase().includes(query) ||
      (e.mentor_nombre && e.mentor_nombre.toLowerCase().includes(query));
  });

  if (filtrados.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="p-8 text-center text-slate-400">No se encontraron estudiantes para la búsqueda realizada.</td></tr>`;
    return;
  }

  const filas = [];
  filtrados.forEach(e => {
    const cursos = e.cursos || [];
    if (cursos.length === 0) {
      filas.push(`
        <tr class="hover:bg-slate-50 transition-colors">
          <td class="py-2.5 px-3">
            <strong class="text-xs text-[#0a192f] block font-bold">${e.nombre}</strong>
            <span class="text-[11px] text-slate-400 font-mono">${e.correo}</span>
          </td>
          <td class="py-2.5 px-3 text-xs text-purple-800 font-semibold">${e.mentor_nombre || 'Sin Mentor'}</td>
          <td colspan="6" class="py-2.5 px-3 text-xs text-slate-400 italic">No tiene colecciones asignadas en esta entidad</td>
        </tr>
      `);
      return;
    }

    cursos.forEach((c, idx) => {
      const totalMod = c.total_modulos || 3;
      const modComp = c.modulos_completados || 0;
      const pct = Math.round(c.porcentaje_avance || 0);

      const dots = [];
      for (let i = 1; i <= totalMod; i++) {
        if (i <= modComp) {
          dots.push('<span class="inline-block w-2.5 h-2.5 rounded-full bg-cyan-600" title="Módulo ' + i + ' completado"></span>');
        } else {
          dots.push('<span class="inline-block w-2.5 h-2.5 rounded-full bg-slate-200 border border-slate-300" title="Módulo ' + i + ' pendiente"></span>');
        }
      }

      let badgeEstado = 'bg-slate-100 text-slate-700 border-slate-200';
      if (c.estado === 'Completado' || pct >= 100) badgeEstado = 'bg-emerald-100 text-emerald-800 border-emerald-200';
      else if (c.estado === 'En Progreso' || pct > 0) badgeEstado = 'bg-cyan-100 text-cyan-800 border-cyan-200';

      filas.push(`
        <tr class="hover:bg-slate-50 transition-colors">
          ${idx === 0 ? `
            <td rowspan="${cursos.length}" class="py-2.5 px-3 border-r border-slate-100 bg-white align-top">
              <strong class="text-xs text-[#0a192f] block font-bold">${e.nombre}</strong>
              <span class="text-[11px] text-slate-400 font-mono">${e.correo}</span>
              <span class="text-[10px] font-bold text-slate-500 mt-1 block">Avance Global: <span class="text-cyan-700">${Math.round(e.promedio_avance || 0)}%</span></span>
            </td>
            <td rowspan="${cursos.length}" class="py-2.5 px-3 border-r border-slate-100 bg-white align-top text-xs text-purple-900 font-semibold">
              <div class="flex items-center gap-1.5">
                <i data-lucide="graduation-cap" class="w-3.5 h-3.5 text-purple-600 shrink-0"></i>
                <span>${e.mentor_nombre || 'Sin Mentor'}</span>
              </div>
            </td>
          ` : ''}
          <td class="py-2 px-3 text-xs font-bold text-[#0a192f] max-w-[200px] truncate" title="${c.titulo}">
            ${c.titulo}
          </td>
          <td class="py-2 px-3 whitespace-nowrap">
            <div class="flex items-center gap-1.5">
              <div class="flex items-center gap-1">${dots.join('')}</div>
              <span class="text-[11px] font-bold text-slate-700 font-mono ml-1">${modComp} / ${totalMod}</span>
            </div>
          </td>
          <td class="py-2 px-3 whitespace-nowrap">
            <div class="flex items-center gap-2">
              <div class="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div class="h-1.5 rounded-full ${pct >= 80 ? 'bg-emerald-500' : 'bg-cyan-600'}" style="width: ${pct}%"></div>
              </div>
              <span class="text-xs font-bold ${pct >= 80 ? 'text-emerald-700' : 'text-cyan-800'} font-mono">${pct}%</span>
            </div>
          </td>
          <td class="py-2 px-3 text-[11px] font-mono text-slate-500 whitespace-nowrap">
            ${c.tiempo_dedicado_minutos || 0} min
          </td>
          <td class="py-2 px-3 whitespace-nowrap">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeEstado}">${c.estado || 'No Iniciado'}</span>
          </td>
          <td class="py-2 px-3 text-right whitespace-nowrap">
            <button onclick="abrirModalSimularProgreso(${e.usuario_id}, '${escapeHtml(e.nombre)}', ${c.curso_id}, '${escapeHtml(c.titulo)}', ${modComp}, ${totalMod})" class="px-2.5 py-1 rounded-lg bg-cyan-50 hover:bg-cyan-100 text-cyan-800 border border-cyan-200 text-[11px] font-bold transition-all shadow-2xs inline-flex items-center gap-1" title="Ajustar o simular avance de módulos">
              <i data-lucide="sliders" class="w-3 h-3 text-cyan-600"></i>
              <span>Simular Módulos</span>
            </button>
          </td>
        </tr>
      `);
    });
  });

  tbody.innerHTML = filas.join('');
  refrescarIconos();
}

function filtrarTablaEstudiantesAnalitica() {
  renderizarTablaEstudiantesAnalitica();
}

function abrirModalSimularProgreso(usuarioId, nombre, cursoId, cursoTitulo, modulosActuales, totalModulos) {
  document.getElementById('input-simular-usuario-id').value = usuarioId;
  document.getElementById('input-simular-curso-id').value = cursoId;
  document.getElementById('input-simular-total-modulos').value = totalModulos;

  document.getElementById('lbl-simular-nombre').innerText = nombre;
  document.getElementById('lbl-simular-curso').innerText = `${cursoTitulo} (${totalModulos} Módulos)`;

  const range = document.getElementById('range-simular-modulos');
  if (range) {
    range.max = totalModulos;
    range.value = modulosActuales;
  }

  cambiarRangeModulos(modulosActuales);

  const modal = document.getElementById('modal-simular-modulos');
  if (modal) modal.classList.remove('hidden');
}

function cambiarRangeModulos(val) {
  const totalMod = parseInt(document.getElementById('input-simular-total-modulos')?.value || 3);
  const mComp = parseInt(val);
  const pct = Math.round((mComp / Math.max(1, totalMod)) * 100);

  const badgeVal = document.getElementById('badge-simular-modulos-val');
  if (badgeVal) badgeVal.innerText = `${mComp} / ${totalMod}`;

  const lblPct = document.getElementById('lbl-simular-pct');
  if (lblPct) lblPct.innerText = `${pct}%`;

  const badgeEst = document.getElementById('badge-simular-estado');
  if (badgeEst) {
    if (mComp === 0) {
      badgeEst.className = 'inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-700';
      badgeEst.innerText = 'No Iniciado';
    } else if (mComp >= totalMod) {
      badgeEst.className = 'inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800';
      badgeEst.innerText = 'Completado (100%)';
    } else {
      badgeEst.className = 'inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-100 text-cyan-800';
      badgeEst.innerText = 'En Progreso';
    }
  }
}

async function ejecutarActualizarProgresoModulos(event) {
  event.preventDefault();
  const usuario_id = parseInt(document.getElementById('input-simular-usuario-id').value);
  const curso_id = parseInt(document.getElementById('input-simular-curso-id').value);
  const modulos_completados = parseInt(document.getElementById('range-simular-modulos').value);

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/progreso/actualizar-modulos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario_id, curso_id, modulos_completados })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al actualizar progreso');

    mostrarToast(data.mensaje || '✓ Avance de módulos actualizado.', 'exito');
    cerrarModal('modal-simular-modulos');

    const orgId = analiticaOrgActual?.organizacion?.id;
    if (orgId) {
      cargarAnaliticaPorOrganizacion(orgId);
    }
    actualizarMetricas();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

async function desvincularColeccionOrganizacion(materialId, orgId) {
  if (!confirm('¿Estás seguro de que deseas desvincular esta colección de la organización seleccionada?')) return;
  try {
    const res = await fetch(`${API_BASE}/api/superadmin/colecciones/desvincular-organizacion/${materialId}/${orgId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al desvincular');

    mostrarToast('✓ Colección desvinculada de la organización.', 'exito');
    cargarAnaliticaPorOrganizacion(orgId);
    cargarMateriales();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function descargarDatasetPowerBI() {
  const orgId = document.getElementById('select-analitica-org')?.value;
  const url = orgId 
    ? `${API_BASE}/api/powerbi/exportar-metricas-colecciones.csv?organizacion_id=${orgId}`
    : `${API_BASE}/api/powerbi/exportar-metricas-colecciones.csv`;

  window.open(url, '_blank');
  mostrarToast('📥 Descargando dataset CSV compatible con Microsoft Power BI...', 'info');
}

function descargarInformeExcelMetricas() {
  const orgId = document.getElementById('select-analitica-org')?.value || (currentUser?.organizacion_id || '');
  const url = orgId 
    ? `${API_BASE}/api/metricas/exportar-excel?organizacion_id=${orgId}`
    : `${API_BASE}/api/metricas/exportar-excel`;

  mostrarToast('📊 Descargando informe profesional en Excel (.xlsx) con métricas y gráficas nativas...', 'info');
  const link = document.createElement('a');
  link.href = url;
  link.download = `metricas_desempeno_${new Date().toISOString().slice(0, 10)}.xlsx`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function copiarUrlLivePowerBI() {
  const orgId = document.getElementById('select-analitica-org')?.value;
  const baseUrl = (window.location.protocol === 'file:') ? 'http://localhost:8080' : window.location.origin;
  const url = orgId 
    ? `${baseUrl}/api/powerbi/metricas-organizaciones-json?organizacion_id=${orgId}`
    : `${baseUrl}/api/powerbi/metricas-organizaciones-json`;

  copiarAlPortapapelesSeguro(url);
  mostrarToast(`✓ URL de datos en vivo para Power BI copiada al portapapeles: ${url}`, 'exito');
}

function abrirModalGuiaPowerBI() {
  const orgId = document.getElementById('select-analitica-org')?.value;
  const baseUrl = (window.location.protocol === 'file:') ? 'http://localhost:8080' : window.location.origin;
  const url = orgId 
    ? `${baseUrl}/api/powerbi/metricas-organizaciones-json?organizacion_id=${orgId}`
    : `${baseUrl}/api/powerbi/metricas-organizaciones-json`;

  const inputDisplay = document.getElementById('input-powerbi-url-display');
  if (inputDisplay) inputDisplay.value = url;

  const modal = document.getElementById('modal-guia-powerbi');
  if (modal) modal.classList.remove('hidden');
}

// =====================================================================
// 12. AUDITORÍA EL CELADOR & HISTORIAL DE NUEVOS INTEGRANTES (POR DÍAS)
// =====================================================================
let integranteAEliminar = { id: null, nombre: '', email: '' };
let historialIntegrantesData = { registros_por_dia: {}, resumen_dias: [] };

let auditSeleccionados = new Set();

async function cargarAuditoria() {
  try {
    const isSuperAdmin = currentUser?.rol === 'Super Administrador';
    const isAprendiz = currentUser?.rol === 'Aprendiz' || currentUser?.rol === 'Estudiante';
    const isMentor = currentUser?.rol === 'Mentor';
    const isAdmin = currentUser?.rol === 'Administrador';

    const orgFiltro = isSuperAdmin ? (document.getElementById('select-audit-org')?.value || 'TODOS') : 'TODOS';
    const fechaFiltro = document.getElementById('input-audit-fecha')?.value || '';
    const params = new URLSearchParams();
    if (fechaFiltro) params.append('fecha', fechaFiltro);

    if (isAprendiz && currentUser?.correo) {
      params.append('correo', currentUser.correo);
    } else if (isAdmin && currentUser?.organizacion_id) {
      params.append('organizacion_id', currentUser.organizacion_id);
    } else if (orgFiltro && orgFiltro !== 'TODOS') {
      params.append('organizacion_nombre', orgFiltro);
    }

    // Si es mentor y aún no ha precargado sus alumnos, consultar sus aprendices
    if (isMentor && (!window.mentorAlumnosActuales || window.mentorAlumnosActuales.length === 0)) {
      try {
        const resAlu = await fetch(`${API_BASE}/api/mentor/${currentUser.id}/alumnos-detalle`);
        const jsonAlu = await resAlu.json();
        if (jsonAlu.data) window.mentorAlumnosActuales = jsonAlu.data;
      } catch (err) {}
    }

    const res = await fetch(`${API_BASE}/api/auditoria/listar?${params.toString()}`);
    const json = await res.json();
    allAuditLogs = json.data || [];
    filtrarAuditoria();
  } catch (e) {
    console.error('Error cargando auditoria:', e);
  }
}

function obtenerCorreosAlumnosMentor() {
  const set = new Set();
  if (!currentUser) return set;
  set.add(currentUser.correo.toLowerCase().trim());
  if (window.mentorAlumnosActuales && Array.isArray(window.mentorAlumnosActuales)) {
    window.mentorAlumnosActuales.forEach(a => {
      if (a.correo) set.add(a.correo.toLowerCase().trim());
    });
  }
  if (window.adminAprendicesFiltrados && Array.isArray(window.adminAprendicesFiltrados)) {
    window.adminAprendicesFiltrados.forEach(a => {
      if (a.mentor_id === currentUser.id || a.mentor_correo === currentUser.correo || a.mentor_nombre === currentUser.nombre) {
        if (a.correo) set.add(a.correo.toLowerCase().trim());
      }
    });
  }
  if (allHierarchyData && allHierarchyData.aprendices && Array.isArray(allHierarchyData.aprendices)) {
    allHierarchyData.aprendices.forEach(a => {
      if (a.mentor_id === currentUser.id || a.mentor_correo === currentUser.correo || a.mentor_nombre === currentUser.nombre) {
        if (a.correo) set.add(a.correo.toLowerCase().trim());
      }
    });
  }
  return set;
}

function filtrarAuditoria() {
  const isSuperAdmin = currentUser?.rol === 'Super Administrador';
  const isAprendiz = currentUser?.rol === 'Aprendiz' || currentUser?.rol === 'Estudiante';
  const isMentor = currentUser?.rol === 'Mentor';
  const isAdmin = currentUser?.rol === 'Administrador';

  // Ajustes de títulos y selectores según rol
  const titCelador = document.getElementById('titulo-vista-celador');
  const subCelador = document.getElementById('subtitulo-vista-celador');
  const selOrg = document.getElementById('contenedor-filtro-org-auditoria');
  const btnTabIntegrantes = document.getElementById('btn-tab-celador-integrantes');
  const btnTabWaf = document.getElementById('btn-tab-celador-ciberseguridad');

  if (isAprendiz) {
    if (titCelador) titCelador.innerText = 'Mi Registro de Actividad';
    if (subCelador) subCelador.innerText = 'Historial exclusivo de tus accesos y actividades académicas en la plataforma.';
    if (selOrg) selOrg.classList.add('hidden');
    if (btnTabIntegrantes) btnTabIntegrantes.classList.add('hidden');
    if (btnTabWaf) btnTabWaf.classList.add('hidden');
  } else if (isMentor) {
    if (titCelador) titCelador.innerText = 'Registro de Actividad de Mis Estudiantes';
    if (subCelador) subCelador.innerText = 'Bitácora de actividad y sesiones de los aprendices a tu cargo y tus tutorías.';
    if (selOrg) selOrg.classList.add('hidden');
    if (btnTabIntegrantes) btnTabIntegrantes.classList.add('hidden');
    if (btnTabWaf) btnTabWaf.classList.add('hidden');
  } else if (isSuperAdmin) {
    if (titCelador) titCelador.innerText = 'Registro de Actividad Global';
    if (subCelador) subCelador.innerText = 'Control diario de integrantes y bitácora de auditoría en tiempo real de administradores, mentores y aprendices.';
    if (selOrg) selOrg.classList.remove('hidden');
    if (btnTabIntegrantes) btnTabIntegrantes.classList.remove('hidden');
    if (btnTabWaf) btnTabWaf.classList.remove('hidden');
  } else {
    // Administrador Institucional
    if (titCelador) titCelador.innerText = 'Registro de Actividad Institucional (Mentores y Aprendices)';
    if (subCelador) subCelador.innerText = 'Bitácora de auditoría y movimientos de los mentores y aprendices de tu institución.';
    if (selOrg) selOrg.classList.add('hidden');
    if (btnTabIntegrantes) btnTabIntegrantes.classList.remove('hidden');
    if (btnTabWaf) btnTabWaf.classList.add('hidden');
  }

  const query = document.getElementById('input-audit-search')?.value.toLowerCase().trim() || '';
  const estadoFiltro = document.getElementById('select-audit-estado')?.value || 'TODOS';
  const fechaFiltro = document.getElementById('input-audit-fecha')?.value || '';
  const orgFiltro = isSuperAdmin ? (document.getElementById('select-audit-org')?.value || 'TODOS') : 'TODOS';
  const tbody = document.getElementById('tabla-auditoria-body');
  if (!tbody) return;

  const mentorCorreos = isMentor ? obtenerCorreosAlumnosMentor() : null;

  const filtrados = allAuditLogs.filter(row => {
    const rowEmail = (row.Correo_Usuario || '').toLowerCase().trim();
    const rowRol = (row.usuario_rol || '').trim();

    if (isAprendiz) {
      if (!rowEmail || rowEmail !== (currentUser?.correo || '').toLowerCase().trim()) {
        return false;
      }
    } else if (isMentor) {
      if (!rowEmail || !mentorCorreos || !mentorCorreos.has(rowEmail)) {
        return false;
      }
    } else if (isAdmin) {
      // El Administrador solo ve a los mentores y aprendices de su institución
      if (rowRol === 'Super Administrador') {
        return false;
      }
      if (rowRol && rowRol !== 'Mentor' && rowRol !== 'Aprendiz' && rowRol !== 'Estudiante' && rowEmail !== (currentUser?.correo || '').toLowerCase().trim()) {
        return false;
      }
    }

    const matchEstado = (estadoFiltro === 'TODOS') || (row.Estado === estadoFiltro);
    const matchFecha = !fechaFiltro || (row.Fecha_Hora && row.Fecha_Hora.startsWith(fechaFiltro));
    const matchOrg = (orgFiltro === 'TODOS') || 
      (row.organizacion_nombre && row.organizacion_nombre.toLowerCase().includes(orgFiltro.toLowerCase())) ||
      (row.Detalles_Error && row.Detalles_Error.toLowerCase().includes(orgFiltro.toLowerCase()));
    const matchQuery = !query ||
      (row.Correo_Usuario && row.Correo_Usuario.toLowerCase().includes(query)) ||
      (row.organizacion_nombre && row.organizacion_nombre.toLowerCase().includes(query)) ||
      (row.Modulo && row.Modulo.toLowerCase().includes(query)) ||
      (row.Operacion && row.Operacion.toLowerCase().includes(query)) ||
      (row.Detalles_Error && row.Detalles_Error.toLowerCase().includes(query));
    return matchEstado && matchFecha && matchOrg && matchQuery;
  });

  if (filtrados.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="p-6 text-center text-slate-400">No se encontraron eventos de auditoría registrados para esta institución o filtro.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtrados.map(r => {
    const esExito = (r.Estado === 'EXITO');
    const badgeClase = esExito 
      ? 'bg-emerald-100 text-emerald-800 border-emerald-200' 
      : 'bg-rose-100 text-rose-800 border-rose-200';

    const isChecked = auditSeleccionados.has(r.id);

    return `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-2.5 px-3 w-8">
          <input type="checkbox" class="check-audit-item rounded text-purple-600 focus:ring-purple-500" value="${r.id}" ${isChecked ? 'checked' : ''} onchange="toggleSeleccionAudit(${r.id}, this.checked)">
        </td>
        <td class="py-2.5 px-3 text-slate-500 whitespace-nowrap">${r.Fecha_Hora}</td>
        <td class="py-2.5 px-3 font-semibold text-slate-700 whitespace-nowrap">
          <span class="inline-flex items-center gap-1.5">
            <i data-lucide="building-2" class="w-3.5 h-3.5 text-slate-400"></i>
            ${escapeHtml(r.organizacion_nombre || 'Plataforma Global')}
          </span>
        </td>
        <td class="py-2.5 px-3 font-bold text-slate-800">${escapeHtml(r.Correo_Usuario || '')}</td>
        <td class="py-2.5 px-3 text-cyan-800 font-semibold">${escapeHtml(r.Modulo || '')}</td>
        <td class="py-2.5 px-3 text-slate-600">${escapeHtml(r.Operacion || '')}</td>
        <td class="py-2.5 px-3">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${badgeClase}">${r.Estado}</span>
        </td>
        <td class="py-2.5 px-3 text-slate-500 max-w-xs truncate" title="${escapeHtml(r.Detalles_Error || '')}">${escapeHtml(r.Detalles_Error || 'Ninguno')}</td>
        <td class="py-2.5 px-3 text-right whitespace-nowrap">
          <button onclick="eliminarEventoAuditoria(${r.id}, '${escapeHtml(r.Operacion || '')}')" class="p-1.5 rounded-lg text-rose-500 hover:text-rose-700 hover:bg-rose-50 transition-colors inline-flex items-center gap-1" title="Eliminar este evento de la bitácora">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');
  refrescarIconos();
  actualizarBarraSeleccionAudit();
}

function toggleSeleccionAudit(id, checked) {
  if (checked) {
    auditSeleccionados.add(id);
  } else {
    auditSeleccionados.delete(id);
  }
  actualizarBarraSeleccionAudit();
}

function toggleSeleccionarTodosAudit(checked) {
  document.querySelectorAll('.check-audit-item').forEach(cb => {
    cb.checked = checked;
    const id = parseInt(cb.value);
    if (checked) auditSeleccionados.add(id);
    else auditSeleccionados.delete(id);
  });
  actualizarBarraSeleccionAudit();
}

function seleccionarTodosAudit() {
  toggleSeleccionarTodosAudit(true);
  const checkAll = document.getElementById('check-all-audit');
  if (checkAll) checkAll.checked = true;
}

function cancelarSeleccionAudit() {
  auditSeleccionados.clear();
  document.querySelectorAll('.check-audit-item').forEach(cb => cb.checked = false);
  const checkAll = document.getElementById('check-all-audit');
  if (checkAll) checkAll.checked = false;
  const barra = document.getElementById('barra-seleccion-audit');
  if (barra) barra.classList.add('hidden');
}

function actualizarBarraSeleccionAudit() {
  const barra = document.getElementById('barra-seleccion-audit');
  const label = document.getElementById('label-conteo-seleccionados-audit');
  if (!barra || !label) return;

  const cantidad = auditSeleccionados.size;
  if (cantidad > 0) {
    label.innerText = `${cantidad} evento${cantidad === 1 ? '' : 's'} seleccionado${cantidad === 1 ? '' : 's'}`;
    barra.classList.remove('hidden');
  } else {
    barra.classList.add('hidden');
  }
}

async function confirmarEliminarSeleccionadosAudit() {
  const ids = Array.from(auditSeleccionados);
  if (ids.length === 0) return;

  if (!confirm(`⚠️ ¿Deseas eliminar permanentemente los ${ids.length} eventos seleccionados de la bitácora de auditoría?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/auditoria/eliminar-lote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: ids })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al eliminar eventos de auditoría');

    mostrarToast(`✓ ${data.mensaje || `${ids.length} eventos eliminados de auditoría.`}`, 'exito');
    cancelarSeleccionAudit();
    cargarAuditoria();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function limpiarFechaAuditoria() {
  const input = document.getElementById('input-audit-fecha');
  if (input) input.value = '';
  filtrarAuditoria();
}

async function eliminarEventoAuditoria(logId, accion) {
  if (!logId) return;
  if (!confirm(`¿Deseas eliminar este registro de auditoría ("${accion || 'Operación'}") de la bitácora del Registro de Actividad?`)) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/auditoria/${logId}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al eliminar registro de auditoría');
    mostrarToast('✓ Evento eliminado de la bitácora de auditoría.', 'exito');
    cargarAuditoria();
  } catch (e) {
    mostrarToast(e.message, 'error');
  }
}

async function confirmarLimpiarAuditoriaDia() {
  const fecha = document.getElementById('input-audit-fecha')?.value;
  if (!fecha) {
    return mostrarToast('Por favor selecciona primero una fecha en el filtro "Día" para eliminar sus eventos.', 'advertencia');
  }
  if (!confirm(`¿Eliminar TODOS los eventos de auditoría registrados en la fecha ${fecha}? Esta acción no se puede deshacer.`)) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/auditoria/por-dia/${fecha}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al limpiar eventos del día');
    mostrarToast(data.mensaje || `✓ Eventos del día ${fecha} eliminados.`, 'exito');
    cargarAuditoria();
  } catch (e) {
    mostrarToast(e.message, 'error');
  }
}

async function confirmarVaciarTodaAuditoria() {
  if (!confirm('⚠️ ¿Estás completamente seguro de VACIAR TODA la bitácora del Registro de Actividad? Esta acción es irreversible.')) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/auditoria/limpiar-todo`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al vaciar bitácora de auditoría');
    mostrarToast('✓ Bitácora del Registro de Actividad vaciada con éxito.', 'exito');
    cargarAuditoria();
  } catch (e) {
    mostrarToast(e.message, 'error');
  }
}

function cambiarTabCelador(tab) {
  const isAprendiz = currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante');
  const isMentor = currentUser && currentUser.rol === 'Mentor';

  const btnIntegrantes = document.getElementById('btn-tab-celador-integrantes');
  const btnEventos = document.getElementById('btn-tab-celador-eventos');
  const btnCiber = document.getElementById('btn-tab-celador-ciberseguridad');

  const panelIntegrantes = document.getElementById('panel-celador-integrantes');
  const panelEventos = document.getElementById('panel-celador-eventos');
  const panelCiber = document.getElementById('panel-celador-ciberseguridad');

  if (isAprendiz || isMentor) {
    if (btnIntegrantes) btnIntegrantes.classList.add('hidden');
    if (btnCiber) btnCiber.classList.add('hidden');
    tab = 'eventos';
  } else {
    if (btnIntegrantes) btnIntegrantes.classList.remove('hidden');
    if (currentUser?.rol === 'Super Administrador' && btnCiber) {
      btnCiber.classList.remove('hidden');
    } else if (btnCiber) {
      btnCiber.classList.add('hidden');
    }
  }

  // Reset classes
  const inactivoCls = "px-3.5 py-1.5 rounded-lg font-medium text-slate-600 hover:text-slate-900 transition-all flex items-center gap-1.5";
  const activoCls = "px-3.5 py-1.5 rounded-lg font-bold bg-white text-[#0a192f] shadow-sm transition-all flex items-center gap-1.5";

  if (btnIntegrantes) btnIntegrantes.className = inactivoCls;
  if (btnEventos) btnEventos.className = inactivoCls;
  if (btnCiber) btnCiber.className = inactivoCls;

  if (panelIntegrantes) panelIntegrantes.classList.add('hidden');
  if (panelEventos) panelEventos.classList.add('hidden');
  if (panelCiber) panelCiber.classList.add('hidden');

  if (tab === 'integrantes' && !isAprendiz && !isMentor) {
    if (btnIntegrantes) btnIntegrantes.className = activoCls;
    if (panelIntegrantes) panelIntegrantes.classList.remove('hidden');
    cargarHistorialIntegrantes();
  } else if (tab === 'ciberseguridad' && !isAprendiz && !isMentor) {
    if (btnCiber) btnCiber.className = activoCls;
    if (panelCiber) panelCiber.classList.remove('hidden');
    cargarPanelCiberseguridad();
  } else {
    if (btnEventos) btnEventos.className = activoCls;
    if (panelEventos) panelEventos.classList.remove('hidden');
    cargarAuditoria();
  }
  refrescarIconos();
}

// ---------------------------------------------------------------------
// HISTORIAL DE NUEVOS INTEGRANTES (ORGANIZADO POR DÍAS Y ELIMINACIÓN)
// ---------------------------------------------------------------------
let historialDebounceTimer = null;
function filtrarHistorialIntegrantes() {
  clearTimeout(historialDebounceTimer);
  historialDebounceTimer = setTimeout(() => {
    cargarHistorialIntegrantes();
  }, 250);
}

function cambiarFechaPickerIntegrantes(val) {
  const selectDia = document.getElementById('select-filtro-dia-integrantes');
  if (selectDia && val) {
    selectDia.value = 'TODOS';
  }
  cargarHistorialIntegrantes();
}

function limpiarFechaPickerIntegrantes() {
  const picker = document.getElementById('input-fecha-picker-integrantes');
  if (picker) picker.value = '';
  cargarHistorialIntegrantes();
}

function formatearFechaDiaTexto(fechaStr) {
  if (!fechaStr) return 'Fecha sin registrar';
  const hoyStr = new Date().toISOString().slice(0, 10);
  const dHoy = new Date();
  dHoy.setDate(dHoy.getDate() - 1);
  const ayerStr = dHoy.toISOString().slice(0, 10);

  const partes = fechaStr.split('-');
  const fechaBonita = (partes.length === 3) ? `${partes[2]}/${partes[1]}/${partes[0]}` : fechaStr;

  if (fechaStr === hoyStr) {
    return `Hoy (${fechaBonita})`;
  } else if (fechaStr === ayerStr) {
    return `Ayer (${fechaBonita})`;
  } else {
    return `Jornada ${fechaBonita}`;
  }
}

let historialSeleccionados = new Set();

async function cargarHistorialIntegrantes() {
  try {
    const busqueda = document.getElementById('input-buscar-historial-integrantes')?.value.trim() || '';
    const selectDia = document.getElementById('select-filtro-dia-integrantes')?.value || 'TODOS';
    const pickerDia = document.getElementById('input-fecha-picker-integrantes')?.value || '';
    const rol = document.getElementById('select-filtro-rol-integrantes')?.value || 'TODOS';
    const isSuperAdmin = currentUser?.rol === 'Super Administrador';
    const orgId = isSuperAdmin
      ? (document.getElementById('select-filtro-org-integrantes')?.value || 'TODOS')
      : (currentUser?.organizacion_id ? String(currentUser.organizacion_id) : 'TODOS');

    const fechaFiltro = pickerDia || (selectDia !== 'TODOS' ? selectDia : '');

    const params = new URLSearchParams();
    if (fechaFiltro) params.append('fecha', fechaFiltro);
    if (rol && rol !== 'TODOS') params.append('rol', rol);
    if (orgId && orgId !== 'TODOS') params.append('organizacion_id', orgId);
    if (busqueda) params.append('busqueda', busqueda);

    const res = await fetch(`${API_BASE}/api/historial-integrantes/listar?${params.toString()}`);
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al obtener historial de integrantes');

    historialIntegrantesData = json;

    // Actualizar KPIs
    const kpiHoy = document.getElementById('kpi-historial-hoy');
    const kpiAyer = document.getElementById('kpi-historial-ayer');
    const kpiTotal = document.getElementById('kpi-historial-total');
    const kpiDias = document.getElementById('kpi-historial-dias');

    if (kpiHoy) kpiHoy.textContent = json.metricas?.hoy ?? 0;
    if (kpiAyer) kpiAyer.textContent = json.metricas?.ayer ?? 0;
    if (kpiTotal) kpiTotal.textContent = json.metricas?.total_general ?? 0;
    if (kpiDias) kpiDias.textContent = json.metricas?.dias_activos ?? 0;

    // Poblar Selector de Días disponibles si existe
    if (selectDia !== 'TODOS' && !pickerDia) {
      // conservar selección actual
    } else if (json.resumen_dias && Array.isArray(json.resumen_dias)) {
      actualizarSelectorDiasIntegrantes(json.resumen_dias, selectDia);
    }

    renderizarHistorialIntegrantes(json.registros_por_dia || {}, 'contenedor-historial-dias');
    renderizarHistorialIntegrantes(json.registros_por_dia || {}, 'contenedor-celador-integrantes-dias');

  } catch (e) {
    console.error('Error cargando historial de integrantes:', e);
    const cont = document.getElementById('contenedor-historial-dias');
    if (cont) cont.innerHTML = `<div class="p-6 text-center text-rose-500 font-semibold text-xs">Error al cargar el historial: ${e.message}</div>`;
  }
}

function actualizarSelectorDiasIntegrantes(resumenDias, valorSeleccionado) {
  const select = document.getElementById('select-filtro-dia-integrantes');
  if (!select) return;

  let optionsHtml = '<option value="TODOS">Todos los días</option>';
  resumenDias.forEach(d => {
    const label = `${formatearFechaDiaTexto(d.fecha_dia)} (${d.total_integrantes} reg.)`;
    const sel = (valorSeleccionado === d.fecha_dia) ? 'selected' : '';
    optionsHtml += `<option value="${d.fecha_dia}" ${sel}>${label}</option>`;
  });
  select.innerHTML = optionsHtml;
}

function renderizarHistorialIntegrantes(registrosPorDia, contenedorId) {
  const contenedor = document.getElementById(contenedorId);
  if (!contenedor) return;

  const diasClaves = Object.keys(registrosPorDia);
  if (diasClaves.length === 0) {
    contenedor.innerHTML = `
      <div class="corp-card p-12 text-center border border-slate-200">
        <div class="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-3 text-slate-400">
          <i data-lucide="user-x" class="w-7 h-7"></i>
        </div>
        <h4 class="text-sm font-bold text-slate-700">No se encontraron nuevos integrantes</h4>
        <p class="text-xs text-slate-400 max-w-sm mx-auto mt-1">No hay registros que coincidan con la institución, fecha o filtro seleccionado.</p>
      </div>
    `;
    refrescarIconos();
    actualizarBarraSeleccionHistorial();
    return;
  }

  // Ordenar días descendente (más recientes primero)
  diasClaves.sort((a, b) => b.localeCompare(a));

  const bloquesHtml = diasClaves.map(dia => {
    const integrantes = registrosPorDia[dia] || [];
    const tituloDia = formatearFechaDiaTexto(dia);
    const totalDia = integrantes.length;

    const filasHtml = integrantes.map(item => {
      const hora = (item.fecha_registro && item.fecha_registro.includes(' '))
        ? item.fecha_registro.split(' ')[1]
        : (item.fecha_registro || '--:--');

      let badgeRol = 'badge-corp ' + obtenerClaseBadgeRol(item.rol);

      const esExcel = item.origen_registro && item.origen_registro.includes('Excel');
      const badgeOrigen = esExcel 
        ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">📊 Excel</span>'
        : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">✍️ Manual</span>';

      const isChecked = historialSeleccionados.has(item.id);

      return `
        <tr class="hover:bg-slate-50/80 transition-colors">
          <td class="py-2.5 px-3 w-8">
            <input type="checkbox" class="check-integrante-item rounded text-cyan-600 focus:ring-cyan-500" value="${item.id}" ${isChecked ? 'checked' : ''} onchange="toggleSeleccionIntegrante(${item.id}, this.checked)">
          </td>
          <td class="py-2.5 px-4 font-mono text-[11px] text-slate-500 whitespace-nowrap">
            <span class="inline-flex items-center gap-1">
              <i data-lucide="clock" class="w-3 h-3 text-slate-400"></i>
              ${hora}
            </span>
          </td>
          <td class="py-2.5 px-4 font-bold text-slate-800 whitespace-nowrap">${escapeHtml(item.nombre)}</td>
          <td class="py-2.5 px-4 font-mono text-xs text-slate-600">${escapeHtml(item.correo)}</td>
          <td class="py-2.5 px-4 whitespace-nowrap">
            <span class="${badgeRol}">${item.rol}</span>
          </td>
          <td class="py-2.5 px-4 text-slate-600 whitespace-nowrap font-medium">
            <span class="inline-flex items-center gap-1.5">
              <i data-lucide="building-2" class="w-3.5 h-3.5 text-slate-400"></i>
              ${escapeHtml(item.organizacion_nombre || 'Plataforma Global')}
            </span>
          </td>
          <td class="py-2.5 px-4 whitespace-nowrap">${badgeOrigen}</td>
          <td class="py-2.5 px-4 text-right whitespace-nowrap">
            <button onclick="abrirModalEliminarIntegrante(${item.id}, '${escapeHtml(item.nombre)}', '${escapeHtml(item.correo)}')" 
                    class="px-2.5 py-1 rounded-lg text-rose-600 hover:text-white hover:bg-rose-600 border border-rose-200 text-[11px] font-bold transition-all inline-flex items-center gap-1 shadow-sm" 
                    title="Eliminar este integrante del historial">
              <i data-lucide="trash-2" class="w-3 h-3"></i>
              <span>Eliminar</span>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    return `
      <div id="bloque-dia-${dia}" class="corp-card overflow-hidden shadow-sm border border-slate-200">
        <!-- Encabezado del Día -->
        <div class="p-4 bg-slate-50 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-cyan-100 text-cyan-800 flex items-center justify-center font-bold text-sm shadow-xs">
              <i data-lucide="calendar" class="w-4 h-4 text-cyan-700"></i>
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h3 class="text-sm font-bold text-[#0a192f]">${tituloDia}</h3>
                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-cyan-50 text-cyan-800 border border-cyan-200">
                  ${totalDia} ${totalDia === 1 ? 'nuevo integrante' : 'nuevos integrantes'}
                </span>
              </div>
              <p class="text-[11px] text-slate-500 font-mono mt-0.5">Fecha: ${dia}</p>
            </div>
          </div>
          
          <!-- Acciones del Día (Marcar día y Limpiar día) -->
          <div class="flex items-center gap-2 self-end sm:self-auto flex-wrap">
            <label class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold cursor-pointer transition-colors select-none border border-slate-200">
              <input type="checkbox" onchange="toggleSeleccionarDiaHistorial('${dia}', this.checked)" class="rounded text-cyan-600 focus:ring-cyan-500">
              <span>Marcar día</span>
            </label>
            <button onclick="confirmarLimpiarHistorialDia('${dia}')" 
                    class="btn-alerta-rose" 
                    title="Eliminar del historial todos los registros correspondientes a esta fecha">
              <i data-lucide="calendar-x" class="w-3.5 h-3.5"></i>
              <span>Limpiar este día</span>
            </button>
          </div>
        </div>

        <!-- Tabla de Integrantes del Día -->
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="text-slate-400 font-semibold uppercase text-[10px] tracking-wider border-b border-slate-100 bg-white">
              <tr>
                <th class="py-2.5 px-3 w-8">
                  <input type="checkbox" onchange="toggleSeleccionarDiaHistorial('${dia}', this.checked)" class="rounded text-cyan-600 focus:ring-cyan-500" title="Seleccionar todos los de este día">
                </th>
                <th class="py-2.5 px-4">Hora</th>
                <th class="py-2.5 px-4">Nombre Completo</th>
                <th class="py-2.5 px-4">Correo Electrónico</th>
                <th class="py-2.5 px-4">Rol / Cargo</th>
                <th class="py-2.5 px-4">Institución</th>
                <th class="py-2.5 px-4">Origen</th>
                <th class="py-2.5 px-4 text-right">Acción</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 text-slate-700 font-medium bg-white">
              ${filasHtml}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }).join('');

  contenedor.innerHTML = bloquesHtml;
  refrescarIconos();
  actualizarBarraSeleccionHistorial();
}

function toggleSeleccionIntegrante(id, checked) {
  if (checked) {
    historialSeleccionados.add(id);
  } else {
    historialSeleccionados.delete(id);
  }
  actualizarBarraSeleccionHistorial();
}

function toggleSeleccionarDiaHistorial(dia, checked) {
  const diaBloque = document.getElementById(`bloque-dia-${dia}`);
  if (!diaBloque) return;
  const checkboxes = diaBloque.querySelectorAll('.check-integrante-item');
  checkboxes.forEach(cb => {
    cb.checked = checked;
    const id = parseInt(cb.value);
    if (checked) historialSeleccionados.add(id);
    else historialSeleccionados.delete(id);
  });
  actualizarBarraSeleccionHistorial();
}

function seleccionarTodosHistorial() {
  document.querySelectorAll('.check-integrante-item').forEach(cb => {
    cb.checked = true;
    historialSeleccionados.add(parseInt(cb.value));
  });
  actualizarBarraSeleccionHistorial();
}

function cancelarSeleccionHistorial() {
  historialSeleccionados.clear();
  document.querySelectorAll('.check-integrante-item').forEach(cb => cb.checked = false);
  const barra = document.getElementById('barra-seleccion-historial');
  if (barra) barra.classList.add('hidden');
}

function actualizarBarraSeleccionHistorial() {
  const barra = document.getElementById('barra-seleccion-historial');
  const label = document.getElementById('label-conteo-seleccionados-historial');
  if (!barra || !label) return;

  const cantidad = historialSeleccionados.size;
  if (cantidad > 0) {
    label.innerText = `${cantidad} elemento${cantidad === 1 ? '' : 's'} seleccionado${cantidad === 1 ? '' : 's'}`;
    barra.classList.remove('hidden');
  } else {
    barra.classList.add('hidden');
  }
}

async function confirmarEliminarSeleccionadosHistorial() {
  const ids = Array.from(historialSeleccionados);
  if (ids.length === 0) return;

  const eliminarUsuarios = confirm(`¿Deseas dar de baja también las cuentas de los usuarios seleccionados (${ids.length} usuarios)?\n\nPresiona ACEPTAR para eliminar los registros del historial Y las cuentas de usuario.\nPresiona CANCELAR para eliminar SOLAMENTE del historial.`);

  if (!confirm(`⚠️ ¿Confirmas eliminar ${ids.length} elementos seleccionados del historial?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/historial-integrantes/eliminar-lote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: ids, eliminar_usuarios: eliminarUsuarios })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al eliminar selección');

    mostrarToast(`✓ ${data.mensaje || `${ids.length} registros eliminados con éxito.`}`, 'exito');
    cancelarSeleccionHistorial();
    cargarHistorialIntegrantes();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function abrirModalEliminarIntegrante(registroId, nombre, email) {
  integranteAEliminar = { id: registroId, nombre: nombre, email: email };
  const labelDesc = document.getElementById('label-eliminar-integrante-desc');
  if (labelDesc) {
    labelDesc.innerHTML = `Estás a punto de eliminar a <strong>${nombre}</strong> (<code>${email}</code>) del historial cronológico.`;
  }
  const checkDel = document.getElementById('check-eliminar-usuario-bd');
  if (checkDel) checkDel.checked = false;

  const modal = document.getElementById('modal-confirmar-eliminar-integrante');
  if (modal) modal.classList.remove('hidden');
}

async function ejecutarEliminarIntegrante() {
  if (!integranteAEliminar.id) return;
  const delUsuario = document.getElementById('check-eliminar-usuario-bd')?.checked || false;

  try {
    const res = await fetch(`${API_BASE}/api/historial-integrantes/${integranteAEliminar.id}?eliminar_usuario=${delUsuario}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al eliminar integrante');

    mostrarToast(data.mensaje || '✓ Integrante eliminado del historial.', 'exito');
    cerrarModal('modal-confirmar-eliminar-integrante');
    integranteAEliminar = { id: null, nombre: '', email: '' };
    
    // Recargar historial y jerarquías si se eliminó el usuario
    cargarHistorialIntegrantes();
    if (delUsuario) {
      cargarJerarquia3Columnas();
      actualizarMetricas();
    }
  } catch (e) {
    mostrarToast(e.message, 'error');
  }
}

async function confirmarLimpiarHistorialDia(fechaDia) {
  if (!confirm(`¿Estás seguro de que deseas eliminar TODOS los registros de nuevos integrantes del día ${fechaDia}? Esta acción limpiará la lista de esa fecha del historial.`)) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/historial-integrantes/por-dia/${fechaDia}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al limpiar día del historial');
    mostrarToast(data.mensaje || `✓ Registros del día ${fechaDia} eliminados del historial.`, 'exito');
    cargarHistorialIntegrantes();
  } catch (e) {
    mostrarToast(e.message, 'error');
  }
}

async function confirmarVaciarHistorialCompleto() {
  if (!confirm('⚠️ ¿Estás completamente seguro de que deseas VACIAR TODO el historial de nuevos integrantes? Esta acción eliminará permanentemente todos los registros históricos acumulados.')) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/historial-integrantes/limpiar-todo`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al vaciar historial');
    mostrarToast(data.mensaje || '✓ Historial de nuevos integrantes vaciado con éxito.', 'exito');
    cargarHistorialIntegrantes();
  } catch (e) {
    mostrarToast(e.message, 'error');
  }
}

// =====================================================================
// LIMPIEZA INTEGRAL DE BASE DE DATOS Y OPTIMIZACIÓN DE TRÁFICO
// =====================================================================
async function abrirModalLimpiarBD() {
  const modal = document.getElementById('modal-limpiar-base-datos');
  if (modal) modal.classList.remove('hidden');
  refrescarIconos();

  const cntAudit = document.getElementById('diag-cnt-auditoria');
  const cntHist = document.getElementById('diag-cnt-historial');
  const cntPap = document.getElementById('diag-cnt-papelera');
  const cntDb = document.getElementById('diag-cnt-db');

  if (cntAudit) cntAudit.innerText = 'Calculando...';
  if (cntHist) cntHist.innerText = 'Calculando...';
  if (cntPap) cntPap.innerText = 'Calculando...';
  if (cntDb) cntDb.innerText = 'Calculando...';

  try {
    const res = await fetch(`${API_BASE}/api/sistema/diagnostico-limpieza`);
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error obteniendo diagnóstico');

    const tot = json.datos || json.totales || {};
    const cAudit = tot.auditoria?.conteo ?? tot.auditoria ?? 0;
    const cHist = tot.historial_integrantes?.conteo ?? tot.historial_integrantes ?? 0;
    const cPap = tot.papelera?.conteo ?? tot.papelera_usuarios ?? 0;
    const cDb = tot.tamano_base_datos ?? `${tot.espacio_estimado_kb ?? 0} KB`;

    if (cntAudit) cntAudit.innerText = `${cAudit} evts`;
    if (cntHist) cntHist.innerText = `${cHist} reg`;
    if (cntPap) cntPap.innerText = `${cPap} usuarios`;
    if (cntDb) cntDb.innerText = `${cDb}`;
  } catch (err) {
    console.error('Error en diagnóstico:', err);
    if (cntAudit) cntAudit.innerText = '--';
    if (cntHist) cntHist.innerText = '--';
    if (cntPap) cntPap.innerText = '--';
    if (cntDb) cntDb.innerText = '--';
  }
}

async function ejecutarLimpiezaGranular(event) {
  if (event) event.preventDefault();

  const audit = document.getElementById('check-limpiar-auditoria')?.checked || false;
  const hist = document.getElementById('check-limpiar-historial')?.checked || false;
  const pap = document.getElementById('check-limpiar-papelera')?.checked || false;
  const users = document.getElementById('check-limpiar-usuarios')?.checked || false;
  const vac = document.getElementById('check-limpiar-vacuum')?.checked || false;

  if (!audit && !hist && !pap && !users && !vac) {
    mostrarToast('Selecciona al menos una casilla para realizar la optimización.', 'error');
    return;
  }

  let advertencia = '¿Confirmas la limpieza y optimización del sistema según las opciones seleccionadas?';
  if (users) {
    advertencia = '⚠️ Has seleccionado reiniciar usuarios y avances de prueba. Tu usuario de Super Administrador (Diego Niño) permanecerá 100% blindado. ¿Deseas continuar?';
  }

  if (!confirm(advertencia)) return;

  try {
    mostrarToast('⏳ Ejecutando optimización granular...', 'info');
    const res = await fetch(`${API_BASE}/api/sistema/limpiar-granular`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        limpiar_auditoria: audit,
        limpiar_historial_integrantes: hist,
        limpiar_papelera: pap,
        limpiar_usuarios_prueba: users,
        ejecutar_vacuum: vac
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error en limpieza granular');

    cerrarModal('modal-limpiar-base-datos');
    mostrarToast(json.mensaje || '¡Limpieza granular completada con éxito!', 'exito');

    // Refrescar todas las vistas en vivo
    if (typeof refrescarTodosSelectoresOrganizaciones === 'function') await refrescarTodosSelectoresOrganizaciones();
    if (typeof cargarDatosConectividadConfiguracion === 'function') cargarDatosConectividadConfiguracion();
    if (typeof cargarAuditoria === 'function') cargarAuditoria();
    if (typeof cargarHistorialIntegrantes === 'function') cargarHistorialIntegrantes();
    if (typeof cargarPapeleraUsuarios === 'function') cargarPapeleraUsuarios();
    if (typeof cargarNodosInstitucionales === 'function') cargarNodosInstitucionales();
    if (typeof cargarJerarquia3Columnas === 'function') cargarJerarquia3Columnas();
    if (typeof actualizarMetricas === 'function') actualizarMetricas();
  } catch (err) {
    console.error('Error en limpieza:', err);
    mostrarToast(err.message, 'error');
  }
}

async function ejecutarLimpiezaBD(tipo) {
  let mensajeConfirm = '';
  if (tipo === 'todo') {
    mensajeConfirm = '⚠️ ATENCIÓN: ¿Deseas ejecutar un RESET TOTAL LIMPIO?\n\n• Se eliminarán los usuarios de prueba acumulados.\n• Se limpiará el historial y la auditoría.\n• Se compactará la base de datos con VACUUM.\n• Tu cuenta de Super Administrador permanece 100% protegida.\n\n¿Deseas continuar?';
  } else if (tipo === 'historial_auditoria') {
    mensajeConfirm = '¿Deseas vaciar todos los registros de historial y la bitácora de auditoría para restablecer el tráfico a cero?';
  } else if (tipo === 'optimizar') {
    mensajeConfirm = '¿Deseas ejecutar la optimización y compactación profunda (VACUUM) de la base de datos?';
  }

  if (mensajeConfirm && !confirm(mensajeConfirm)) return;

  try {
    mostrarToast('⏳ Ejecutando limpieza y optimización...', 'info');
    const res = await fetch(`${API_BASE}/api/sistema/limpiar-base-datos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo: tipo, preservar_superadmin: true })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al ejecutar limpieza de base de datos');

    cerrarModal('modal-limpiar-base-datos');
    mostrarToast(json.mensaje || 'Base de datos optimizada y limpia.', 'exito');

    // Refrescar todas las vistas en vivo
    await refrescarTodosSelectoresOrganizaciones();
    if (typeof cargarHistorialIntegrantes === 'function') cargarHistorialIntegrantes();
    if (typeof cargarAuditoria === 'function') cargarAuditoria();
    if (typeof cargarNodosInstitucionales === 'function') cargarNodosInstitucionales();
    if (typeof cargarJerarquia3Columnas === 'function') cargarJerarquia3Columnas();
    if (typeof actualizarMetricas === 'function') actualizarMetricas();
  } catch (err) {
    console.error('Error en limpieza BD:', err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// 13. RED LOCAL, INTERNET GLOBAL, UTILIDADES & NOTIFICACIONES
// =====================================================================
// Función universal de copiado al portapapeles compatible con HTTP y HTTPS
function copiarAlPortapapelesSeguro(texto) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(texto).catch(() => {
      fallbackCopiarTexto(texto);
    });
  }
  fallbackCopiarTexto(texto);
}

function fallbackCopiarTexto(texto) {
  try {
    const textArea = document.createElement("textarea");
    textArea.value = texto;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    textArea.style.top = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
  } catch (err) {
    console.warn("Fallback de copiado al portapapeles:", err);
  }
}

function copiarUrlRed() {
  if (!networkUrl) return;
  copiarAlPortapapelesSeguro(networkUrl);
  mostrarToast(`Enlace de red local copiado: ${networkUrl}`, 'info');
}

function copiarUrlInternet() {
  if (!globalInternetUrl) {
    return mostrarToast('El enlace de Internet se está sincronizando con Cloudflare. Aguarda un segundo...', 'advertencia');
  }
  copiarAlPortapapelesSeguro(globalInternetUrl);
  mostrarToast(`¡Enlace global de Internet copiado! Compártelo con quien quieras: ${globalInternetUrl}`, 'exito');
}

function escapeHtml(text) {
  if (!text) return '';
  return text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function cerrarModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}

function mostrarToast(mensaje, tipo = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const estilos = {
    exito: 'bg-emerald-50 border-emerald-300 text-emerald-900',
    error: 'bg-rose-50 border-rose-300 text-rose-900',
    advertencia: 'bg-amber-50 border-amber-300 text-amber-900',
    info: 'bg-[#091b2c] border-slate-700 text-white',
  };

  const iconos = {
    exito: 'check-circle-2',
    error: 'alert-circle',
    advertencia: 'alert-triangle',
    info: 'info',
  };

  toast.className = `p-3.5 rounded-xl border shadow-xl flex items-start gap-2.5 text-xs pointer-events-auto transition-all duration-300 transform translate-y-2 opacity-0 ${estilos[tipo] || estilos.info}`;
  toast.innerHTML = `
    <i data-lucide="${iconos[tipo] || 'info'}" class="w-4 h-4 shrink-0 mt-0.5"></i>
    <div class="flex-1 font-semibold">${mensaje}</div>
  `;

  container.appendChild(toast);
  refrescarIconos();

  setTimeout(() => toast.classList.remove('translate-y-2', 'opacity-0'), 10);
  setTimeout(() => {
    toast.classList.add('translate-y-2', 'opacity-0');
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

async function verificarEstadoServidor() {
  try {
    const res = await fetch(`${API_BASE}/api/estado-servidor`);
    if (!res.ok) throw new Error('Servidor offline');
    const data = await res.json();
    
    // Configurar URL de red local
    networkUrl = data.url_red || '';
    const labelRed = document.getElementById('label-network-url');
    const badgeRed = document.getElementById('badge-red-local');
    if (labelRed && networkUrl) {
      labelRed.innerText = networkUrl;
      if (badgeRed) badgeRed.classList.remove('hidden');
    }

    // Configurar URL global de Internet (Cloudflare Tunnel)
    globalInternetUrl = data.url_internet || '';
    const badgeInternet = document.getElementById('badge-internet-global');
    const labelInternet = document.getElementById('label-internet-url');
    if (badgeInternet) {
      badgeInternet.classList.remove('hidden');
      if (labelInternet) {
        if (globalInternetUrl) {
          labelInternet.innerText = 'En Línea';
          badgeInternet.title = `Enlace público mundial: ${globalInternetUrl}`;
        } else {
          labelInternet.innerText = 'Conectando...';
          // Reintentar en 2.5s si el túnel aún está estableciendo la conexión
          setTimeout(verificarEstadoServidor, 2500);
        }
      }
    }

    const badge = document.getElementById('badge-db-status');
    const text = document.getElementById('text-db-status');
    if (badge && text) {
      text.innerText = data.modo_bd;
      if (data.modo_bd.includes('Azure')) {
        badge.className = 'flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800';
      } else {
        badge.className = 'flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-50 border border-cyan-200 text-xs font-semibold text-cyan-800';
      }
    }
    refrescarIconos();
  } catch (e) {
    const badge = document.getElementById('badge-db-status');
    const text = document.getElementById('text-db-status');
    if (badge && text) {
      badge.className = 'flex items-center space-x-2 px-3 py-1 rounded-full bg-rose-50 border border-rose-200 text-xs font-semibold text-rose-800';
      text.innerText = 'Servidor Offline';
    }
  }
}

// =====================================================================
// 8.6. GESTIÓN Y ORGANIZACIÓN DE GRUPOS DE TRABAJO (SUPERADMIN)
// =====================================================================
let gruposActualesData = null;
let organizacionGruposId = null;

async function abrirModalOrganizarGrupos(orgId = null, mentorIdFoco = null) {
  const selectOrg = document.getElementById('select-org-grupos');
  if (!selectOrg) return;

  // Cargar lista de organizaciones en el select
  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/listar`);
    const raw = await res.json();
    const orgs = Array.isArray(raw) ? raw : (raw.data || []);
    if (orgs && orgs.length > 0) {
      selectOrg.innerHTML = orgs.map(o => `
        <option value="${o.id}">${escapeHtml(o.nombre)} (${o.tipo_organizacion})</option>
      `).join('');
    }
  } catch (e) {
    console.error("Error cargando organizaciones para grupos:", e);
  }

  // Determinar organización inicial
  if (orgId) {
    organizacionGruposId = parseInt(orgId);
    selectOrg.value = String(orgId);
  } else {
    const filtroVal = document.getElementById('select-filtro-org-jerarquia')?.value;
    if (filtroVal) {
      organizacionGruposId = parseInt(filtroVal);
      selectOrg.value = String(filtroVal);
    } else if (selectOrg.value) {
      organizacionGruposId = parseInt(selectOrg.value);
    } else if (currentUser?.organizacion_id) {
      organizacionGruposId = currentUser.organizacion_id;
      selectOrg.value = String(currentUser.organizacion_id);
    }
  }

  document.getElementById('modal-organizar-grupos').classList.remove('hidden');
  refrescarIconos();

  if (organizacionGruposId) {
    await cargarDetalleGrupos(organizacionGruposId, mentorIdFoco);
  }
}

function cambiarOrgGrupos(nuevaOrgId) {
  if (!nuevaOrgId) return;
  organizacionGruposId = parseInt(nuevaOrgId);
  cargarDetalleGrupos(organizacionGruposId);
}

async function cargarDetalleGrupos(orgId = null, mentorIdFoco = null) {
  const targetOrgId = orgId || organizacionGruposId;
  if (!targetOrgId) return;
  organizacionGruposId = targetOrgId;

  const contSinMentor = document.getElementById('lista-aprendices-sin-mentor');
  const contMentores = document.getElementById('grid-grupos-mentores');
  
  if (contSinMentor) contSinMentor.innerHTML = `<div class="p-6 text-center text-slate-400 text-xs">Cargando aprendices...</div>`;
  if (contMentores) contMentores.innerHTML = `<div class="col-span-2 p-8 text-center text-slate-400 text-xs">Cargando grupos...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/grupos/detalle/${targetOrgId}`);
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al obtener detalle de grupos');

    gruposActualesData = json.data;
    renderizarInterfazGrupos(json.data, mentorIdFoco);
  } catch (err) {
    mostrarToast(err.message, 'error');
    if (contSinMentor) contSinMentor.innerHTML = `<div class="p-6 text-center text-rose-500 text-xs">${err.message}</div>`;
    if (contMentores) contMentores.innerHTML = `<div class="col-span-2 p-8 text-center text-rose-500 text-xs">${err.message}</div>`;
  }
}

function renderizarInterfazGrupos(data, mentorIdFoco = null) {
  const { mentores, sin_mentor, metricas, organizacion } = data;

  // Actualizar KPIs
  const mMentores = document.getElementById('metric-grupos-mentores');
  const mAprendices = document.getElementById('metric-grupos-aprendices');
  const mAsignados = document.getElementById('metric-grupos-asignados');
  const mSinMentor = document.getElementById('metric-grupos-sin-mentor');
  const badgeContador = document.getElementById('badge-contador-sin-mentor');

  if (mMentores) mMentores.innerText = metricas.total_mentores || 0;
  if (mAprendices) mAprendices.innerText = metricas.total_aprendices || 0;
  if (mAsignados) mAsignados.innerText = metricas.aprendices_asignados || 0;
  if (mSinMentor) mSinMentor.innerText = metricas.aprendices_sin_mentor || 0;
  if (badgeContador) badgeContador.innerText = sin_mentor.length;

  // Poblar select de mentores para asignación por lote
  const selectLote = document.getElementById('select-mentor-destino-lote');
  if (selectLote) {
    selectLote.innerHTML = `<option value="">Elegir mentor destino...</option>` +
      mentores.map(m => `<option value="${m.id}">${escapeHtml(m.nombre)} (${m.aprendices.length} alumnos)</option>`).join('');
  }

  // Panel de lote
  const panelLote = document.getElementById('panel-asignacion-lote');
  if (panelLote) {
    if (sin_mentor.length > 0 && mentores.length > 0) {
      panelLote.classList.remove('hidden');
    } else {
      panelLote.classList.add('hidden');
    }
  }

  // Reset checkbox lote
  const checkTodos = document.getElementById('check-seleccionar-todos-sin-mentor');
  if (checkTodos) checkTodos.checked = false;
  const txtSel = document.getElementById('texto-seleccionados-lote');
  if (txtSel) txtSel.innerText = '0 sel.';

  // 1. Renderizar Bandeja de Aprendices Sin Mentor
  const contSinMentor = document.getElementById('lista-aprendices-sin-mentor');
  if (contSinMentor) {
    if (sin_mentor.length === 0) {
      contSinMentor.innerHTML = `
        <div class="p-6 text-center text-slate-400">
          <i data-lucide="check-circle-2" class="w-8 h-8 text-emerald-500 mx-auto mb-2"></i>
          <p class="text-xs font-bold text-slate-700">¡Bandeja despejada!</p>
          <p class="text-[11px] text-slate-500 mt-1">Todos los aprendices de ${escapeHtml(organizacion.nombre)} tienen un mentor asignado.</p>
        </div>
      `;
    } else {
      contSinMentor.innerHTML = sin_mentor.map(a => {
        const avance = Math.round(a.promedio_avance || 0);
        return `
          <div class="p-2.5 bg-slate-50 hover:bg-white border border-slate-200 hover:border-amber-300 rounded-xl transition-all shadow-sm">
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-2 min-w-0">
                <input type="checkbox" value="${a.id}" class="check-sin-mentor rounded text-cyan-600 focus:ring-cyan-500 shrink-0" onchange="actualizarConteoSeleccionadosLote()">
                <div class="min-w-0">
                  <h5 class="text-xs font-bold text-[#0a192f] leading-tight truncate">${escapeHtml(a.nombre)}</h5>
                  <p class="text-[11px] text-slate-500 font-mono truncate">${escapeHtml(a.correo)}</p>
                </div>
              </div>
              <span class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold text-[10px] shrink-0">
                ${avance}%
              </span>
            </div>
            
            <div class="mt-2 pt-2 border-t border-slate-200/60 flex items-center justify-between gap-2">
              <span class="text-[10px] text-slate-400 font-medium shrink-0">Asignar a:</span>
              <select onchange="if(this.value) reasignarAprendizGrupo(${a.id}, this.value)" class="corp-input px-2 py-1 rounded-lg text-[10px] font-semibold text-purple-900 bg-purple-50/70 border-purple-200 flex-1 max-w-[170px]">
                <option value="">Seleccionar mentor...</option>
                ${mentores.map(m => `<option value="${m.id}">${escapeHtml(m.nombre)}</option>`).join('')}
              </select>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // 2. Renderizar Grupos por Mentor
  const contMentores = document.getElementById('grid-grupos-mentores');
  if (contMentores) {
    if (mentores.length === 0) {
      contMentores.innerHTML = `
        <div class="col-span-2 p-8 text-center text-slate-400">
          <i data-lucide="alert-circle" class="w-10 h-10 text-amber-500 mx-auto mb-2"></i>
          <p class="text-sm font-bold text-slate-700">No hay mentores registrados en esta institución.</p>
          <p class="text-xs text-slate-500 mt-1">Registra o importa mentores con el archivo Excel para poder organizar los grupos de trabajo.</p>
        </div>
      `;
    } else {
      contMentores.innerHTML = mentores.map(m => {
        const esFoco = mentorIdFoco && m.id === parseInt(mentorIdFoco);
        const otrosMentores = mentores.filter(otro => otro.id !== m.id);
        const nombreEscapado = (m.nombre || '').replace(/'/g, "\\'");
        const correoEscapado = (m.correo || '').replace(/'/g, "\\'");

        return `
          <div id="card-grupo-mentor-${m.id}" class="bg-white rounded-xl border ${esFoco ? 'border-purple-500 ring-2 ring-purple-200' : 'border-slate-200'} shadow-sm flex flex-col overflow-hidden transition-all">
            
            <!-- Encabezado del Mentor -->
            <div class="p-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div class="flex items-center space-x-2.5 min-w-0">
                <div class="w-8 h-8 rounded-full bg-purple-100 text-purple-800 font-bold flex items-center justify-center text-xs shadow-xs shrink-0">
                  ${m.nombre.charAt(0).toUpperCase()}
                </div>
                <div class="min-w-0">
                  <h5 class="text-xs font-bold text-[#0a192f] leading-snug truncate">${escapeHtml(m.nombre)}</h5>
                  <p class="text-[10px] text-purple-700 font-mono truncate">${escapeHtml(m.correo)}</p>
                </div>
              </div>
              <span class="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 font-bold text-[10px] shrink-0 border border-purple-200 ml-2">
                👥 ${m.aprendices.length} aprendices
              </span>
            </div>

            <!-- Casillita de Carga Excel para el Mentor -->
            <div class="px-3 py-2 bg-emerald-50/70 border-b border-emerald-100/80 flex items-center justify-between gap-2">
              <div class="flex items-center gap-1.5 min-w-0">
                <i data-lucide="file-spreadsheet" class="w-4 h-4 text-emerald-600 shrink-0"></i>
                <div class="min-w-0">
                  <span class="text-[11px] font-bold text-emerald-900 block leading-tight">Carga Excel del Mentor</span>
                  <span class="text-[9px] text-emerald-700/80 block leading-none">Subir lista de estudiantes</span>
                </div>
              </div>
              <button onclick="abrirModalSubirExcelMentor(${m.id}, '${nombreEscapado}', '${correoEscapado}')" 
                class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[11px] flex items-center gap-1.5 shadow-xs transition-colors shrink-0"
                title="Cargar archivo Excel con los estudiantes para este mentor">
                <i data-lucide="upload" class="w-3 h-3"></i>
                <span>Subir Aprendices</span>
              </button>
            </div>

            <!-- Lista de Aprendices de este Mentor -->
            <div class="p-3 space-y-2 flex-1 max-h-[320px] overflow-y-auto bg-white">
              ${m.aprendices.length === 0 ? `
                <div class="py-6 text-center text-slate-400 text-xs flex flex-col items-center">
                  <i data-lucide="users" class="w-7 h-7 text-slate-300 mb-1"></i>
                  <p class="text-slate-600 font-bold text-xs">Sin aprendices asignados</p>
                  <p class="text-[11px] text-slate-400 mt-0.5 max-w-[220px]">Sube el archivo Excel con los estudiantes de este mentor o asigna desde la izquierda.</p>
                  <button onclick="abrirModalSubirExcelMentor(${m.id}, '${nombreEscapado}', '${correoEscapado}')" 
                    class="mt-3 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition-all">
                    <i data-lucide="file-spreadsheet" class="w-3.5 h-3.5"></i>
                    <span>Subir Excel de Aprendices</span>
                  </button>
                </div>
              ` : m.aprendices.map(a => {
                const avance = Math.round(a.promedio_avance || 0);
                return `
                  <div class="p-2 rounded-lg bg-slate-50/80 hover:bg-slate-50 border border-slate-100 hover:border-slate-300 flex items-center justify-between gap-2 text-xs transition-colors">
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-1.5">
                        <span class="font-bold text-[#0a192f] text-[11px] truncate block">${escapeHtml(a.nombre)}</span>
                        <span class="text-[10px] font-semibold text-cyan-800 shrink-0">(${avance}%)</span>
                      </div>
                      <p class="text-[10px] text-slate-400 font-mono truncate">${escapeHtml(a.correo)}</p>
                    </div>

                    <div class="flex items-center gap-1 shrink-0">
                      <!-- Dropdown Mover de Mentor -->
                      <select onchange="manejarAccionAprendizGrupo(${a.id}, this.value, ${m.id})" class="corp-input px-1.5 py-0.5 rounded text-[10px] bg-white text-slate-600 border-slate-200" title="Mover a otro mentor o desvincular">
                        <option value="">Acción...</option>
                        <optgroup label="Mover a otro mentor">
                          ${otrosMentores.map(om => `<option value="mover_${om.id}">➡️ ${escapeHtml(om.nombre)}</option>`).join('')}
                        </optgroup>
                        <option value="desvincular">❌ Desvincular (Sin mentor)</option>
                      </select>

                      <button onclick="desvincularAprendizGrupo(${a.id})" class="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors" title="Desvincular del mentor">
                        <i data-lucide="user-minus" class="w-3.5 h-3.5"></i>
                      </button>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>

            <!-- Footer rápido del mentor -->
            <div class="p-2 bg-slate-50/60 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500">
              <span>Carga actual: <strong>${m.aprendices.length}</strong></span>
              <button onclick="abrirModalSubirExcelMentor(${m.id}, '${nombreEscapado}', '${correoEscapado}')" class="text-emerald-700 hover:text-emerald-900 font-bold flex items-center gap-1">
                <i data-lucide="file-spreadsheet" class="w-3 h-3"></i>
                <span>Cargar Excel</span>
              </button>
            </div>

          </div>
        `;
      }).join('');
    }
  }

  refrescarIconos();

  if (mentorIdFoco) {
    const elFoco = document.getElementById(`card-grupo-mentor-${mentorIdFoco}`);
    if (elFoco) {
      elFoco.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
}

async function manejarAccionAprendizGrupo(aprendizId, accion, mentorActualId) {
  if (!accion) return;
  if (accion === 'desvincular') {
    await desvincularAprendizGrupo(aprendizId);
  } else if (accion.startsWith('mover_')) {
    const nuevoMentorId = parseInt(accion.replace('mover_', ''));
    await reasignarAprendizGrupo(aprendizId, nuevoMentorId);
  }
}

async function reasignarAprendizGrupo(aprendizId, nuevoMentorId) {
  try {
    const res = await fetch(`${API_BASE}/api/superadmin/grupos/reasignar`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        aprendiz_id: parseInt(aprendizId),
        mentor_id: nuevoMentorId ? parseInt(nuevoMentorId) : null
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al reasignar aprendiz');

    mostrarToast(json.mensaje || 'Asignación actualizada con éxito.', 'exito');
    await cargarDetalleGrupos(organizacionGruposId);
    if (typeof cargarJerarquiaVisual === 'function') cargarJerarquiaVisual();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

async function desvincularAprendizGrupo(aprendizId) {
  try {
    const res = await fetch(`${API_BASE}/api/superadmin/grupos/desvincular/${aprendizId}`, {
      method: 'PUT'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al desvincular aprendiz');

    mostrarToast(json.mensaje || 'Aprendiz desvinculado a la bandeja sin mentor.', 'info');
    await cargarDetalleGrupos(organizacionGruposId);
    if (typeof cargarJerarquiaVisual === 'function') cargarJerarquiaVisual();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

async function ejecutarAutoRepartoGrupos(repartirTodos = false) {
  if (!organizacionGruposId) {
    mostrarToast('Por favor selecciona una institución primero.', 'advertencia');
    return;
  }

  const mensajeConfirm = repartirTodos 
    ? '¿Deseas reiniciar todas las asignaciones y repartir EQUITATIVAMENTE a TODOS los aprendices entre los mentores?'
    : '¿Deseas repartir equitativamente los aprendices pendientes (sin mentor) entre los mentores activos?';

  if (!confirm(mensajeConfirm)) return;

  const btnId = repartirTodos ? 'btn-rebalancear-todos' : 'btn-repartir-pendientes';
  const btn = document.getElementById(btnId);
  const textoOriginal = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Repartiendo...`;
    refrescarIconos();
  }

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${organizacionGruposId}/auto-repartir?repartir_todos=${repartirTodos}`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al ejecutar reparto automático');

    mostrarToast(json.mensaje || 'Reparto realizado exitosamente.', 'exito');
    await cargarDetalleGrupos(organizacionGruposId);
    if (typeof cargarJerarquiaVisual === 'function') cargarJerarquiaVisual();
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = textoOriginal;
      refrescarIconos();
    }
  }
}

function toggleSeleccionarTodosSinMentor(seleccionado) {
  const checks = document.querySelectorAll('.check-sin-mentor');
  checks.forEach(c => c.checked = seleccionado);
  actualizarConteoSeleccionadosLote();
}

function actualizarConteoSeleccionadosLote() {
  const checks = document.querySelectorAll('.check-sin-mentor:checked');
  const txt = document.getElementById('texto-seleccionados-lote');
  if (txt) {
    txt.innerText = `${checks.length} sel.`;
  }
}

async function ejecutarAsignacionLote() {
  const mentorId = document.getElementById('select-mentor-destino-lote')?.value;
  if (!mentorId) {
    mostrarToast('Selecciona un mentor destino para asignar los aprendices.', 'advertencia');
    return;
  }

  const checks = Array.from(document.querySelectorAll('.check-sin-mentor:checked'));
  const ids = checks.map(c => parseInt(c.value));
  if (ids.length === 0) {
    mostrarToast('Marca al menos un aprendiz de la lista para asignar.', 'advertencia');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/grupos/asignar-lote`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mentor_id: parseInt(mentorId),
        aprendices_ids: ids
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al asignar lote');

    mostrarToast(json.mensaje || 'Aprendices asignados exitosamente.', 'exito');
    await cargarDetalleGrupos(organizacionGruposId);
    if (typeof cargarJerarquiaVisual === 'function') cargarJerarquiaVisual();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// CARGA DE APRENDICES POR EXCEL PARA UN MENTOR ESPECÍFICO
// =====================================================================
function abrirModalSubirExcelMentor(mentorId, mentorNombre, mentorCorreo) {
  const inputId = document.getElementById('input-subir-excel-mentor-id');
  const labelSub = document.getElementById('label-subir-excel-mentor-subtitulo');
  const inputArchivo = document.getElementById('input-archivo-excel-mentor');
  const labelArchivo = document.getElementById('label-archivo-excel-mentor-nombre');

  if (inputId) inputId.value = mentorId;
  if (labelSub) labelSub.innerText = `Mentor: ${mentorNombre} (${mentorCorreo})`;
  if (inputArchivo) inputArchivo.value = '';
  if (labelArchivo) {
    labelArchivo.innerText = 'Haz clic aquí para seleccionar el archivo Excel';
    labelArchivo.className = 'text-xs font-bold text-slate-700';
  }

  const modal = document.getElementById('modal-subir-excel-mentor');
  if (modal) modal.classList.remove('hidden');
  refrescarIconos();
}

function descargarPlantillaExcelMentorActual() {
  const mentorId = document.getElementById('input-subir-excel-mentor-id')?.value;
  if (!mentorId) {
    mostrarToast('No se ha detectado el mentor seleccionado.', 'advertencia');
    return;
  }
  window.location.href = `${API_BASE}/api/superadmin/mentores/${mentorId}/descargar-plantilla-excel`;
}

function actualizarInfoArchivoExcelMentor(input) {
  const labelArchivo = document.getElementById('label-archivo-excel-mentor-nombre');
  if (!labelArchivo) return;

  if (input.files && input.files[0]) {
    const file = input.files[0];
    const tamanoKb = (file.size / 1024).toFixed(1);
    labelArchivo.innerHTML = `<span class="text-emerald-700 font-bold">📄 ${escapeHtml(file.name)}</span> <span class="text-slate-400 font-normal">(${tamanoKb} KB)</span>`;
  } else {
    labelArchivo.innerText = 'Haz clic aquí para seleccionar el archivo Excel';
    labelArchivo.className = 'text-xs font-bold text-slate-700';
  }
}

async function ejecutarCargarAprendicesExcelMentor() {
  const mentorId = document.getElementById('input-subir-excel-mentor-id')?.value;
  if (!mentorId) {
    mostrarToast('No se identificó el mentor objetivo.', 'error');
    return;
  }

  const inputArchivo = document.getElementById('input-archivo-excel-mentor');
  if (!inputArchivo || !inputArchivo.files || inputArchivo.files.length === 0) {
    mostrarToast('Por favor selecciona un archivo Excel (.xlsx, .xls o .csv).', 'advertencia');
    return;
  }

  const btn = document.getElementById('btn-submit-excel-mentor');
  const textoOriginal = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Procesando archivo...</span>`;
    refrescarIconos();
  }

  try {
    const formData = new FormData();
    formData.append('archivo', inputArchivo.files[0]);

    const res = await fetch(`${API_BASE}/api/superadmin/mentores/${mentorId}/cargar-aprendices-excel`, {
      method: 'POST',
      body: formData
    });

    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al procesar el archivo Excel del mentor');

    cerrarModal('modal-subir-excel-mentor');
    mostrarToast(json.mensaje || 'Aprendices importados y asignados exitosamente.', 'exito');

    // Refrescar vistas
    if (organizacionGruposId) {
      await cargarDetalleGrupos(organizacionGruposId, parseInt(mentorId));
    }
    if (typeof cargarJerarquiaVisual === 'function') cargarJerarquiaVisual();
    if (typeof cargarHistorialIntegrantes === 'function') cargarHistorialIntegrantes();
  } catch (err) {
    console.error('Error cargando Excel para mentor:', err);
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = textoOriginal;
      refrescarIconos();
    }
  }
}

// =====================================================================
// INCORPORACIÓN MANUAL DE INTEGRANTES POR ORGANIZACIÓN (ESTUDIANTE/MENTOR/ADMIN)
// =====================================================================
let mentoresOrgManualCache = [];

async function abrirModalCrearIntegranteManual(orgId = null) {
  try {
    const selectOrg = document.getElementById('manual-usr-org');
    if (!selectOrg) return;

    if (!allOrganizations || allOrganizations.length === 0) {
      const resOrg = await fetch(`${API_BASE}/api/organizaciones/listar`);
      const jsonOrg = await resOrg.json();
      allOrganizations = jsonOrg.data || [];
    }

    if (allOrganizations.length === 0) {
      mostrarToast('No hay organizaciones creadas para vincular integrantes.', 'advertencia');
      return;
    }

    selectOrg.innerHTML = allOrganizations.map(o => 
      `<option value="${o.id}">🏛️ ${o.nombre} (${o.tipo_organizacion || 'Institución'})</option>`
    ).join('');

    const targetOrgId = orgId || (analiticaOrgActual?.organizacion?.id) || (currentUser?.organizacion_id) || allOrganizations[0].id;
    selectOrg.value = targetOrgId;

    const inpNombre = document.getElementById('manual-usr-nombre');
    const inpCorreo = document.getElementById('manual-usr-correo');
    const inpPwd = document.getElementById('manual-usr-password');
    if (inpNombre) inpNombre.value = '';
    if (inpCorreo) inpCorreo.value = '';
    if (inpPwd) {
      inpPwd.value = '123456';
      inpPwd.type = 'password';
    }

    const radioAprendiz = document.querySelector('input[name="manual-usr-rol"][value="Aprendiz"]');
    if (radioAprendiz) {
      radioAprendiz.checked = true;
      cambiarRolModalManual('Aprendiz');
    }

    await actualizarMentoresModalManual(targetOrgId);

    const modal = document.getElementById('modal-crear-integrante-manual');
    if (modal) modal.classList.remove('hidden');

    if (inpNombre) inpNombre.focus();
    refrescarIconos();
  } catch (err) {
    console.error('Error abriendo modal de nuevo integrante manual:', err);
    mostrarToast('No fue posible abrir el formulario de alta manual.', 'error');
  }
}

function cambiarRolModalManual(rol) {
  const contMentor = document.getElementById('contenedor-manual-mentor');
  if (contMentor) {
    if (rol === 'Aprendiz') {
      contMentor.classList.remove('hidden');
    } else {
      contMentor.classList.add('hidden');
    }
  }

  ['aprendiz', 'mentor', 'admin'].forEach(r => {
    const lbl = document.getElementById(`lbl-rol-${r}`);
    if (lbl) {
      lbl.className = "flex flex-col items-center p-2.5 rounded-xl border border-slate-200 bg-white cursor-pointer text-center transition-all hover:border-slate-300";
    }
  });

  if (rol === 'Aprendiz') {
    const lbl = document.getElementById('lbl-rol-aprendiz');
    if (lbl) lbl.className = "flex flex-col items-center p-2.5 rounded-xl border-2 border-cyan-500 bg-cyan-50/50 cursor-pointer text-center transition-all hover:bg-cyan-50";
  } else if (rol === 'Mentor') {
    const lbl = document.getElementById('lbl-rol-mentor');
    if (lbl) lbl.className = "flex flex-col items-center p-2.5 rounded-xl border-2 border-purple-500 bg-purple-50/50 cursor-pointer text-center transition-all hover:bg-purple-50";
  } else if (rol === 'Administrador') {
    const lbl = document.getElementById('lbl-rol-admin');
    if (lbl) lbl.className = "flex flex-col items-center p-2.5 rounded-xl border-2 border-amber-500 bg-amber-50/50 cursor-pointer text-center transition-all hover:bg-amber-50";
  }
}

async function actualizarMentoresModalManual(orgId) {
  const selectMentor = document.getElementById('manual-usr-mentor');
  if (!selectMentor || !orgId) return;

  selectMentor.innerHTML = '<option value="">Sin mentor asignado (General)</option>';

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/mentores`);
    const json = await res.json();
    const mentores = json.data || [];
    mentoresOrgManualCache = mentores;

    mentores.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.innerText = `👨‍🏫 ${m.nombre} (${m.correo})`;
      selectMentor.appendChild(opt);
    });
  } catch (e) {
    console.warn('No se pudieron consultar los mentores de la organización:', e);
  }
}

async function ejecutarCrearIntegranteManual(event) {
  event.preventDefault();
  const orgId = parseInt(document.getElementById('manual-usr-org')?.value);
  const nombre = document.getElementById('manual-usr-nombre')?.value.trim();
  const correo = document.getElementById('manual-usr-correo')?.value.trim().toLowerCase();
  const rolRadio = document.querySelector('input[name="manual-usr-rol"]:checked');
  const rol = rolRadio ? rolRadio.value : 'Aprendiz';
  const mentorIdVal = document.getElementById('manual-usr-mentor')?.value;
  const mentorId = (rol === 'Aprendiz' && mentorIdVal) ? parseInt(mentorIdVal) : null;
  const password = document.getElementById('manual-usr-password')?.value.trim() || '123456';

  if (!orgId || !nombre || !correo) {
    mostrarToast('Por favor completa los campos obligatorios.', 'advertencia');
    return;
  }

  if (password.length < 6) {
    mostrarToast('La contraseña debe tener al menos 6 dígitos.', 'advertencia');
    return;
  }

  const btnSubmit = document.getElementById('btn-submit-crear-manual');
  if (btnSubmit) {
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Guardando integrante...</span>`;
    refrescarIconos();
  }

  try {
    const res = await fetch(`${API_BASE}/api/superadmin/usuarios/crear-manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        organizacion_id: orgId,
        nombre,
        correo,
        rol,
        mentor_id: mentorId,
        password
      })
    });

    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al guardar integrante');

    mostrarToast(json.mensaje || `✓ Integrante guardado con éxito.`, 'exito');
    cerrarModal('modal-crear-integrante-manual');

    // Refrescar analítica de colecciones si estamos en la vista de métricas de esta organización
    if (typeof cargarAnaliticaPorOrganizacion === 'function') {
      const selectAnalitica = document.getElementById('select-analitica-org');
      if (selectAnalitica && parseInt(selectAnalitica.value) === orgId) {
        cargarAnaliticaPorOrganizacion(orgId);
      }
    }

    if (typeof cargarJerarquia3Columnas === 'function') {
      cargarJerarquia3Columnas();
    }

    if (typeof cargarHistorialIntegrantes === 'function') {
      cargarHistorialIntegrantes();
    }

    if (typeof cargarDatosAdminConvenio === 'function' && currentUser?.rol === 'Administrador') {
      cargarDatosAdminConvenio();
    }
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btnSubmit) {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i><span>Guardar</span>`;
      refrescarIconos();
    }
  }
}

// =====================================================================
// CAMBIO DE CONTRASEÑA EN SESIÓN ACTIVA (PARA TODOS LOS USUARIOS)
// =====================================================================
function abrirModalCambiarPasswordInterno() {
  const act = document.getElementById('pwd-interno-actual');
  const n1 = document.getElementById('pwd-interno-nueva');
  const n2 = document.getElementById('pwd-interno-confirm');
  const msg = document.getElementById('msg-pwd-interno-match');

  if (act) { act.value = ''; act.type = 'password'; }
  if (n1) { n1.value = ''; n1.type = 'password'; }
  if (n2) { n2.value = ''; n2.type = 'password'; }
  if (msg) msg.classList.add('hidden');

  const modal = document.getElementById('modal-cambiar-password-interno');
  if (modal) modal.classList.remove('hidden');
  if (act) act.focus();
  refrescarIconos();
}

function validarCoincidenciaPasswordInterno() {
  const p1 = document.getElementById('pwd-interno-nueva')?.value || '';
  const p2 = document.getElementById('pwd-interno-confirm')?.value || '';
  const msg = document.getElementById('msg-pwd-interno-match');
  if (!msg) return;

  if (!p2) {
    msg.classList.add('hidden');
    return;
  }

  msg.classList.remove('hidden');
  if (p1 === p2) {
    msg.innerText = '✓ Las contraseñas coinciden';
    msg.className = 'text-[11px] font-semibold mt-1 text-emerald-600';
  } else {
    msg.innerText = '✕ Las contraseñas no coinciden';
    msg.className = 'text-[11px] font-semibold mt-1 text-rose-600';
  }
}

async function ejecutarCambiarPasswordInterno(event) {
  event.preventDefault();
  if (!currentUser || !currentUser.id) {
    mostrarToast('Debes tener una sesión activa para cambiar tu contraseña.', 'advertencia');
    return;
  }

  const pwdAct = document.getElementById('pwd-interno-actual')?.value.trim();
  const pwdNue = document.getElementById('pwd-interno-nueva')?.value.trim();
  const pwdConf = document.getElementById('pwd-interno-confirm')?.value.trim();

  if (!pwdAct || !pwdNue || !pwdConf) {
    mostrarToast('Por favor completa todos los campos de contraseña.', 'advertencia');
    return;
  }

  if (pwdNue.length < 6) {
    mostrarToast('La nueva contraseña debe tener al menos 6 caracteres o dígitos.', 'advertencia');
    return;
  }

  if (pwdNue !== pwdConf) {
    mostrarToast('Las contraseñas no coinciden. Por favor verifícalas.', 'error');
    return;
  }

  const btn = document.getElementById('btn-submit-pwd-interno');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Actualizando clave...</span>`;
    refrescarIconos();
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/cambiar-password-sesion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        usuario_id: currentUser.id,
        password_actual: pwdAct,
        password_nueva: pwdNue
      })
    });

    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al actualizar contraseña');

    mostrarToast(json.mensaje || '¡Contraseña actualizada exitosamente!', 'exito');
    cerrarModal('modal-cambiar-password-interno');
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i><span>Guardar Nueva Clave</span>`;
      refrescarIconos();
    }
  }
}

// =====================================================================
// PESTAÑAS EN MÉTRICAS & RENDIMIENTO
// =====================================================================
function cambiarTabMetricas(tabId) {
  const tabs = ['rendimiento', 'aprendices', 'catalogo'];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-btn-metricas-${t}`);
    const content = document.getElementById(`tab-content-metricas-${t}`);
    if (btn) {
      if (t === tabId) {
        btn.className = 'px-4 py-2.5 text-xs font-bold border-b-2 border-cyan-600 text-cyan-700 flex items-center gap-2 transition-all';
      } else {
        btn.className = 'px-4 py-2.5 text-xs font-bold border-b-2 border-transparent text-slate-500 hover:text-slate-800 flex items-center gap-2 transition-all';
      }
    }
    if (content) {
      if (t === tabId) content.classList.remove('hidden');
      else content.classList.add('hidden');
    }
  });
  refrescarIconos();
}

// =====================================================================
// PESTAÑAS EN CONFIGURACIÓN & CUENTA
// =====================================================================
function cambiarTabConfiguracion(tabId) {
  // Vista unificada: siempre abre la pestaña principal de Configuración de Perfil
  tabId = 'cuenta';
  const tabsOcultas = ['personalizacion', 'conectividad', 'backups', 'papelera', 'powerbi'];

  const btnCuenta = document.getElementById('tab-btn-cfg-cuenta');
  const contCuenta = document.getElementById('tab-content-cfg-cuenta');
  if (btnCuenta) {
    btnCuenta.className = 'px-4 py-2.5 text-xs font-bold border-b-2 border-cyan-600 text-cyan-700 flex items-center gap-2 whitespace-nowrap transition-all cursor-pointer';
  }
  if (contCuenta) {
    contCuenta.classList.remove('hidden');
  }

  tabsOcultas.forEach(t => {
    const btn = document.getElementById(`tab-btn-cfg-${t}`);
    const content = document.getElementById(`tab-content-cfg-${t}`);
    if (btn) btn.classList.add('hidden');
    if (content) content.classList.add('hidden');
  });

  actualizarVisibilidadTemasSegunRol();
  refrescarIconos();
}

function cambiarSubTabPersonalizacion(subtab) {
  refrescarIconos();
}

function inicializarVistaConfiguraciones(subTabApertura = null) {
  if (!currentUser) return;

  const inNombre = document.getElementById('cfg-input-nombre');
  const inCorreo = document.getElementById('cfg-input-correo');
  const inRol = document.getElementById('cfg-input-rol');
  const inOrg = document.getElementById('cfg-input-organizacion');
  const dispNombre = document.getElementById('cfg-perfil-nombre-display');
  const dispCorreo = document.getElementById('cfg-perfil-correo-display');
  const dispRol = document.getElementById('cfg-perfil-rol-badge');
  const dispOrg = document.getElementById('cfg-perfil-org-display');
  const avatarPrev = document.getElementById('cfg-perfil-avatar-preview');

  if (inNombre) {
    inNombre.value = currentUser.nombre;
    inNombre.disabled = true;
    inNombre.readOnly = true;
  }
  if (inCorreo) {
    inCorreo.value = currentUser.correo;
    inCorreo.disabled = true;
    inCorreo.readOnly = true;
  }
  if (inRol) {
    inRol.value = currentUser.rol;
    inRol.disabled = true;
    inRol.readOnly = true;
  }

  const orgNombre = currentUser.organizacion?.nombre || (allOrganizations.find(o => o.id === currentUser.organizacion_id)?.nombre) || 'Corporación Universitaria Minuto de Dios';
  if (inOrg) {
    inOrg.value = orgNombre;
    inOrg.disabled = true;
    inOrg.readOnly = true;
  }
  if (dispOrg) {
    dispOrg.innerText = `🏛️ ${orgNombre}`;
  }

  if (dispNombre) dispNombre.innerText = currentUser.nombre;
  if (dispCorreo) dispCorreo.innerText = currentUser.correo;
  if (dispRol) {
    dispRol.innerText = currentUser.rol;
    dispRol.className = 'badge-corp font-bold mt-2 inline-block ' + obtenerClaseBadgeRol(currentUser.rol);
  }

  const partes = currentUser.nombre.split(' ');
  const iniciales = partes.length >= 2 ? (partes[0][0] + partes[1][0]).toUpperCase() : currentUser.nombre.substring(0, 2).toUpperCase();
  if (avatarPrev) {
    if (currentUser.foto_perfil) {
      avatarPrev.innerHTML = `<img src="${currentUser.foto_perfil}" class="w-full h-full object-cover rounded-full">`;
    } else {
      avatarPrev.innerHTML = `<span id="cfg-perfil-avatar-iniciales">${iniciales}</span>`;
    }
  }

  // Ocultar siempre Conectividad, Papelera, Power BI y pestañas extra
  const tabsOcultas = ['personalizacion', 'conectividad', 'backups', 'papelera', 'powerbi'];
  tabsOcultas.forEach(t => {
    const btn = document.getElementById(`tab-btn-cfg-${t}`);
    const content = document.getElementById(`tab-content-cfg-${t}`);
    if (btn) btn.classList.add('hidden');
    if (content) content.classList.add('hidden');
  });

  // Copia de seguridad de la institución: EXCLUSIVA para Administradores (oculta para Mentores y Aprendices)
  const seccionBackupAdmin = document.getElementById('seccion-backup-institucional-admin');
  const esAdmin = (currentUser.rol === 'Administrador' || currentUser.rol === 'Super Administrador');
  if (seccionBackupAdmin) {
    if (esAdmin) {
      seccionBackupAdmin.classList.remove('hidden');
    } else {
      seccionBackupAdmin.classList.add('hidden');
    }
  }

  cambiarTabConfiguracion('cuenta');
  refrescarIconos();
}

async function descargarCopiaSeguridadInstitucional() {
  if (!currentUser) return;
  const esAdmin = (currentUser.rol === 'Administrador' || currentUser.rol === 'Super Administrador');
  if (!esAdmin) {
    return mostrarToast('Solo los Administradores pueden descargar la copia de seguridad institucional.', 'advertencia');
  }

  const orgId = currentUser.organizacion_id || 13;
  const btn = document.getElementById('btn-descargar-backup-institucion');
  const textoOriginal = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Generando Copia de Seguridad...</span>`;
    refrescarIconos();
  }

  try {
    const res = await fetch(`${API_BASE}/api/sistema/backups/exportar-excel?organizacion_id=${orgId}`, {
      method: 'POST'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error al generar la copia de seguridad');

    mostrarToast(`✓ ${data.mensaje}`, 'exito');
    if (data.url_descarga) {
      const link = document.createElement('a');
      link.href = `${API_BASE}${data.url_descarga}`;
      link.download = data.backup?.archivo || 'backup_institucion.xlsx';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = textoOriginal;
      refrescarIconos();
    }
  }
}

async function procesarSubidaFotoPerfil(event) {
  const archivo = event.target.files[0];
  if (!archivo) return;

  if (!archivo.type.startsWith('image/')) {
    mostrarToast('Por favor selecciona una imagen válida (JPG, PNG, WebP).', 'advertencia');
    return;
  }

  if (archivo.size > 3 * 1024 * 1024) {
    mostrarToast('La imagen debe pesar menos de 3 MB.', 'advertencia');
    return;
  }

  const reader = new FileReader();
  reader.onload = async function(e) {
    const dataUrl = e.target.result;
    try {
      const res = await fetch(`${API_BASE}/api/usuarios/perfil/foto`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario_id: currentUser.id, foto_perfil: dataUrl })
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Error al guardar foto');

      currentUser.foto_perfil = dataUrl;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      actualizarPerfilSidebar();
      inicializarVistaConfiguraciones();
      mostrarToast('¡Foto de perfil actualizada correctamente!', 'exito');
    } catch (err) {
      console.error(err);
      mostrarToast(err.message, 'error');
    }
  };
  reader.readAsDataURL(archivo);
}

async function eliminarFotoPerfil() {
  if (!currentUser.foto_perfil) {
    mostrarToast('No tienes foto de perfil asignada.', 'info');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/perfil/foto/${currentUser.id}`, {
      method: 'DELETE'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al eliminar foto');

    currentUser.foto_perfil = null;
    localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    actualizarPerfilSidebar();
    inicializarVistaConfiguraciones();
    mostrarToast('Foto eliminada. Se mostrarán tus iniciales.', 'info');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function guardarCambioPasswordPerfil(event) {
  event.preventDefault();
  const pwdNueva = document.getElementById('cfg-input-pwd-nueva').value;
  const pwdConf = document.getElementById('cfg-input-pwd-conf').value;

  if (pwdNueva.length < 6) {
    mostrarToast('La nueva contraseña debe tener al menos 6 caracteres.', 'advertencia');
    return;
  }
  if (pwdNueva !== pwdConf) {
    mostrarToast('Las contraseñas no coinciden. Por favor verifica.', 'error');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/perfil/password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        usuario_id: currentUser.id,
        password_nueva: pwdNueva
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al actualizar contraseña');

    document.getElementById('cfg-input-pwd-nueva').value = '';
    document.getElementById('cfg-input-pwd-conf').value = '';
    mostrarToast(json.mensaje || '¡Contraseña actualizada con éxito!', 'exito');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// COLORIMETRÍA INSTITUCIONAL
// =====================================================================
let orgSeleccionadaColorimetriaId = null;

async function cargarSelectorOrgsColorimetria() {
  const selectOrg = document.getElementById('select-color-org');
  const contenedor = document.getElementById('contenedor-select-color-org');
  if (!selectOrg) return;

  if (currentUser && currentUser.rol !== 'Super Administrador') {
    if (contenedor) contenedor.classList.add('hidden');
    orgSeleccionadaColorimetriaId = currentUser.organizacion_id;
    if (orgSeleccionadaColorimetriaId) {
      cargarColorimetriaOrg(orgSeleccionadaColorimetriaId);
    }
    return;
  }

  if (contenedor) contenedor.classList.remove('hidden');

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/listar`);
    const json = await res.json();
    const orgs = json.data || [];

    if (orgs.length === 0) {
      selectOrg.innerHTML = '<option value="">No hay organizaciones</option>';
      return;
    }

    const targetId = orgSeleccionadaColorimetriaId || orgs[0].id;
    selectOrg.innerHTML = orgs.map(o => 
      `<option value="${o.id}" ${o.id === targetId ? 'selected' : ''}>🏛️ ${o.nombre}</option>`
    ).join('');

    orgSeleccionadaColorimetriaId = targetId;
    cargarColorimetriaOrg(targetId);
  } catch (err) {
    console.error(err);
  }
}

async function cargarColorimetriaOrg(orgId) {
  if (!orgId) return;
  orgSeleccionadaColorimetriaId = parseInt(orgId);

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgSeleccionadaColorimetriaId}/colores`);
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al cargar colores');

    const data = json.data || {};
    const p = data.color_primario || '#0a192f';
    const s = data.color_secundario || '#0f273f';
    const a = data.color_acento || '#00b4d8';
    const personalizado = Boolean(data.color_personalizado);

    const pickP = document.getElementById('picker-color-primario');
    const hexP = document.getElementById('hex-color-primario');
    const pickS = document.getElementById('picker-color-secundario');
    const hexS = document.getElementById('hex-color-secundario');
    const pickA = document.getElementById('picker-color-acento');
    const hexA = document.getElementById('hex-color-acento');

    if (pickP) pickP.value = p;
    if (hexP) hexP.value = p;
    if (pickS) pickS.value = s;
    if (hexS) hexS.value = s;
    if (pickA) pickA.value = a;
    if (hexA) hexA.value = a;

    actualizarPreviewColorimetria(p, s, a, personalizado, data.nombre);
    cargarTemasGuardadosOrg(orgSeleccionadaColorimetriaId);
  } catch (err) {
    console.error(err);
  }
}

function seleccionarPresetColor(p, s, a, personalizado) {
  const pickP = document.getElementById('picker-color-primario');
  const hexP = document.getElementById('hex-color-primario');
  const pickS = document.getElementById('picker-color-secundario');
  const hexS = document.getElementById('hex-color-secundario');
  const pickA = document.getElementById('picker-color-acento');
  const hexA = document.getElementById('hex-color-acento');

  if (pickP) pickP.value = p;
  if (hexP) hexP.value = p;
  if (pickS) pickS.value = s;
  if (hexS) hexS.value = s;
  if (pickA) pickA.value = a;
  if (hexA) hexA.value = a;

  actualizarPreviewColorimetria(p, s, a, personalizado);
}

function actualizarHexColor(tipo) {
  const picker = document.getElementById(`picker-color-${tipo}`);
  const hex = document.getElementById(`hex-color-${tipo}`);
  if (picker && hex) hex.value = picker.value.toUpperCase();
  actualizarPreviewDesdeInputs();
}

function actualizarPickerColor(tipo) {
  const picker = document.getElementById(`picker-color-${tipo}`);
  const hex = document.getElementById(`hex-color-${tipo}`);
  if (picker && hex && /^#[0-9A-Fa-f]{6}$/.test(hex.value.trim())) {
    picker.value = hex.value.trim();
    actualizarPreviewDesdeInputs();
  }
}

function actualizarPreviewDesdeInputs() {
  const p = document.getElementById('hex-color-primario')?.value || '#0a192f';
  const s = document.getElementById('hex-color-secundario')?.value || '#0f273f';
  const a = document.getElementById('hex-color-acento')?.value || '#00b4d8';
  actualizarPreviewColorimetria(p, s, a, true);
}

function actualizarPreviewColorimetria(p, s, a, personalizado, nombreOrg) {
  const box = document.getElementById('preview-box');
  const icon = document.getElementById('preview-box-icon');
  const btn = document.getElementById('preview-box-btn');
  const title = document.getElementById('preview-box-title');
  const status = document.getElementById('preview-badge-status');

  if (box) box.style.backgroundColor = p;
  if (icon) {
    icon.style.backgroundColor = s;
    icon.style.color = a;
  }
  if (btn) {
    btn.style.backgroundColor = a;
    btn.style.color = '#ffffff';
  }
  if (title && nombreOrg) title.innerText = nombreOrg;
  if (status) {
    if (personalizado) {
      status.innerText = 'Personalizado';
      status.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-100 text-cyan-800';
    } else {
      status.innerText = 'Predeterminado';
      status.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700';
    }
  }
}

async function guardarColoresOrg() {
  const orgId = orgSeleccionadaColorimetriaId || (currentUser?.organizacion_id) || (currentUser?.organizacion?.id);
  if (!orgId) {
    mostrarToast('Selecciona una organización para guardar sus colores.', 'error');
    return;
  }

  const p = document.getElementById('hex-color-primario')?.value.trim() || '#0a192f';
  const s = document.getElementById('hex-color-secundario')?.value.trim() || '#0f273f';
  const a = document.getElementById('hex-color-acento')?.value.trim() || '#00b4d8';

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/colores`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        color_primario: p,
        color_secundario: s,
        color_acento: a,
        color_personalizado: true
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error guardando colores');

    if (currentUser) {
      if (!currentUser.organizacion) currentUser.organizacion = {};
      currentUser.organizacion.color_primario = p;
      currentUser.organizacion.color_secundario = s;
      currentUser.organizacion.color_acento = a;
      currentUser.organizacion.color_personalizado = 1;
      currentUser.org_color_primario = p;
      currentUser.org_color_secundario = s;
      currentUser.org_color_acento = a;
      currentUser.org_color_personalizado = 1;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    }

    aplicarColoresInstitucion({ color_primario: p, color_secundario: s, color_acento: a, color_personalizado: 1 });
    actualizarPreviewColorimetria(p, s, a, true);

    const actual = localStorage.getItem('edtech_tema_visual');
    if (actual === 'institucional') {
      seleccionarTemaVisual('institucional');
    }

    mostrarToast('✅ ¡Colores institucionales aplicados y publicados con éxito!', 'exito');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function restablecerColoresOrg() {
  const orgId = orgSeleccionadaColorimetriaId || (currentUser?.organizacion_id) || (currentUser?.organizacion?.id);
  if (!orgId) return;

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/colores/restablecer`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error restableciendo colores');

    seleccionarPresetColor('#0a192f', '#0f273f', '#00b4d8', false);

    if (currentUser) {
      if (!currentUser.organizacion) currentUser.organizacion = {};
      currentUser.organizacion.color_primario = '#0a192f';
      currentUser.organizacion.color_secundario = '#0f273f';
      currentUser.organizacion.color_acento = '#00b4d8';
      currentUser.organizacion.color_personalizado = 0;
      currentUser.org_color_primario = '#0a192f';
      currentUser.org_color_secundario = '#0f273f';
      currentUser.org_color_acento = '#00b4d8';
      currentUser.org_color_personalizado = 0;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    }

    aplicarColoresInstitucion({ color_primario: '#0a192f', color_secundario: '#0f273f', color_acento: '#00b4d8', color_personalizado: 0 });
    actualizarPreviewColorimetria('#0a192f', '#0f273f', '#00b4d8', false);

    const actual = localStorage.getItem('edtech_tema_visual');
    if (actual === 'institucional') {
      seleccionarTemaVisual('institucional');
    }

    mostrarToast('Diseño institucional restablecido a valores oficiales.', 'info');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

function aplicarColoresInstitucion(org) {
  if (!org) return;
  const p = org.color_primario || '#0a192f';
  const s = org.color_secundario || '#0f273f';
  const a = org.color_acento || '#00b4d8';

  document.documentElement.style.setProperty('--navy-sidebar', p);
  document.documentElement.style.setProperty('--navy-hover', s);
  document.documentElement.style.setProperty('--cyan-accent', a);
}

// =====================================================================
// CONECTIVIDAD & ESTADO DEL SISTEMA
// =====================================================================
async function cargarDatosConectividadConfiguracion() {
  try {
    const res = await fetch(`${API_BASE}/api/estado-servidor`);
    const json = await res.json();

    const tLocal = document.getElementById('cfg-url-local-text');
    const tRed = document.getElementById('cfg-url-red-text');
    const tInternet = document.getElementById('cfg-url-internet-text');
    const linkAbrir = document.getElementById('cfg-link-abrir-internet');

    if (tLocal) tLocal.innerText = json.url_local || 'http://localhost:8080';
    if (tRed) tRed.innerText = json.url_red || '--';
    if (tInternet) tInternet.innerText = json.url_internet || 'Conectando túnel seguro...';
    if (linkAbrir && json.url_internet && json.url_internet.startsWith('http')) {
      linkAbrir.href = json.url_internet;
      linkAbrir.classList.remove('pointer-events-none', 'opacity-50');
    }
  } catch (err) {
    console.error(err);
  }
}

// =====================================================================
// COPIAS DE SEGURIDAD (BACKUPS DIARIOS Y MENSUALES)
// =====================================================================
async function crearCopiaSeguridadManual() {
  mostrarToast('Generando copia de seguridad de la base de datos...', 'info');
  try {
    const res = await fetch(`${API_BASE}/api/sistema/backups/crear`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error creando respaldo');

    mostrarToast(json.mensaje || '¡Copia de seguridad física generada con éxito!', 'exito');
    cargarHistorialBackups();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function cargarHistorialBackups() {
  const tbody = document.getElementById('tabla-backups-body');
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/sistema/backups/listar`);
    const json = await res.json();
    const backups = json.data || [];

    if (backups.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-400 text-xs">No hay copias de seguridad guardadas aún. Haz clic en "Generar Copia de Seguridad Ahora".</td></tr>';
      return;
    }

    tbody.innerHTML = backups.map(b => `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-2.5 px-3">
          <div class="flex items-center gap-2">
            <i data-lucide="${b.archivo.endsWith('.xlsx') ? 'file-spreadsheet' : 'database'}" class="w-4 h-4 ${b.archivo.endsWith('.xlsx') ? 'text-emerald-600' : 'text-cyan-600'} shrink-0"></i>
            <span class="font-mono text-xs font-bold text-slate-800">${b.archivo}</span>
          </div>
        </td>
        <td class="py-2.5 px-3 text-xs text-slate-600 font-mono">${b.fecha}</td>
        <td class="py-2.5 px-3">
          ${b.archivo.endsWith('.xlsx')
            ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">📊 Excel con Gráficos</span>'
            : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200">${b.mes}</span>`
          }
        </td>
        <td class="py-2.5 px-3 text-xs font-bold text-slate-700">${b.tamano}</td>
        <td class="py-2.5 px-3 text-right">
          <a href="${API_BASE}/api/sistema/backups/descargar/${b.archivo}" class="px-3 py-1 rounded-lg ${b.archivo.endsWith('.xlsx') ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200'} text-xs font-bold inline-flex items-center gap-1 transition-all shadow-2xs" download title="Descargar archivo">
            <i data-lucide="download" class="w-3.5 h-3.5"></i>
            <span>${b.archivo.endsWith('.xlsx') ? 'Descargar Excel' : 'Descargar .db'}</span>
          </a>
        </td>
      </tr>
    `).join('');
    refrescarIconos();
  } catch (err) {
    console.error(err);
    tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-rose-500 text-xs">Error al cargar copias de seguridad.</td></tr>';
  }
}

// =====================================================================
// PAPELERA DE INTEGRANTES & RECUPERACIÓN SEGURA
// =====================================================================
async function cargarPapeleraUsuarios() {
  const tbody = document.getElementById('tabla-papelera-body');
  if (!tbody) return;

  try {
    const orgId = (currentUser?.rol !== 'Super Administrador') ? currentUser?.organizacion_id : null;
    const url = orgId ? `${API_BASE}/api/papelera/usuarios?organizacion_id=${orgId}` : `${API_BASE}/api/papelera/usuarios`;

    const res = await fetch(url);
    const json = await res.json();
    const items = json.data || [];

    if (items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-slate-400 text-xs">La papelera está vacía. No hay integrantes eliminados pendientes de recuperación.</td></tr>';
      return;
    }

    tbody.innerHTML = items.map(p => `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-2.5 px-3">
          <strong class="text-xs text-[#0a192f] block font-bold">${p.nombre}</strong>
          <span class="text-[11px] text-slate-400 font-mono">${p.correo}</span>
        </td>
        <td class="py-2.5 px-3">
          <span class="badge-corp ${obtenerClaseBadgeRol(p.rol)} font-bold text-[10px]">${p.rol}</span>
        </td>
        <td class="py-2.5 px-3 text-xs text-slate-600 font-semibold">${p.organizacion_nombre || 'Sin Organización'}</td>
        <td class="py-2.5 px-3 text-xs font-mono text-slate-500">${p.fecha_eliminacion || '--'}</td>
        <td class="py-2.5 px-3 text-right whitespace-nowrap space-x-1.5">
          <button onclick="restaurarUsuarioPapelera(${p.id}, '${escapeHtml(p.nombre)}')" class="px-2.5 py-1 rounded-lg bg-cyan-50 hover:bg-cyan-100 text-cyan-800 border border-cyan-200 text-xs font-bold inline-flex items-center gap-1 transition-all" title="Restaurar este integrante a la institución con su avance previo">
            <i data-lucide="rotate-ccw" class="w-3 h-3 text-cyan-600"></i>
            <span>Restaurar</span>
          </button>
          <button onclick="purgarUsuarioPapelera(${p.id}, '${escapeHtml(p.nombre)}')" class="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold inline-flex items-center gap-1 transition-all" title="Eliminar definitivamente sin posibilidad de recuperación">
            <i data-lucide="trash-2" class="w-3 h-3"></i>
            <span>Purgar</span>
          </button>
        </td>
      </tr>
    `).join('');
    refrescarIconos();
  } catch (err) {
    console.error(err);
    tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-rose-500 text-xs">Error cargando papelera.</td></tr>';
  }
}

async function restaurarUsuarioPapelera(papeleraId, nombre) {
  if (!confirm(`¿Deseas restaurar a '${nombre}'? El usuario recuperará su acceso y todo su avance previo en los cursos.`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/papelera/usuarios/restaurar/${papeleraId}`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error restaurando integrante');

    mostrarToast(json.mensaje || `¡'${nombre}' ha sido restaurado exitosamente!`, 'exito');
    cargarPapeleraUsuarios();
    if (typeof cargarJerarquia3Columnas === 'function') cargarJerarquia3Columnas();
    if (typeof cargarVistaAdminConvenio === 'function') cargarVistaAdminConvenio();
    if (typeof cargarAnaliticaPorOrganizacion === 'function') cargarAnaliticaPorOrganizacion();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function purgarUsuarioPapelera(papeleraId, nombre) {
  if (!confirm(`¿Eliminar definitivamente a '${nombre}'? Esta acción es irreversible.`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/papelera/usuarios/purgar/${papeleraId}`, {
      method: 'DELETE'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error purgando registro');

    mostrarToast(`'${nombre}' eliminado definitivamente.`, 'info');
    cargarPapeleraUsuarios();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function vaciarTodaPapelera() {
  if (!confirm('¿Estás seguro de vaciar toda la papelera? Todos los integrantes eliminados se borrarán de forma irreversible.')) return;

  try {
    const orgId = (currentUser?.rol !== 'Super Administrador') ? currentUser?.organizacion_id : null;
    const url = orgId ? `${API_BASE}/api/papelera/usuarios/vaciar?organizacion_id=${orgId}` : `${API_BASE}/api/papelera/usuarios/vaciar`;
    const res = await fetch(url, { method: 'DELETE' });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error vaciando papelera');

    mostrarToast('Papelera vaciada correctamente.', 'info');
    cargarPapeleraUsuarios();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// TEMAS PERSONALIZADOS POR ORGANIZACIÓN (SIN LÍMITES)
// =====================================================================
async function cargarTemasGuardadosOrg(orgId) {
  const targetId = orgId || orgSeleccionadaColorimetriaId || currentUser?.organizacion_id;
  const grid = document.getElementById('grid-temas-guardados');
  if (!grid || !targetId) return;

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${targetId}/temas`);
    const json = await res.json();
    const temas = json.data || [];

    if (temas.length === 0) {
      grid.innerHTML = `
        <div class="col-span-full p-6 text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
          <i data-lucide="palette" class="w-6 h-6 mx-auto mb-2 text-slate-300"></i>
          <p class="font-bold text-slate-600">Aún no hay temas personalizados guardados para esta institución.</p>
          <p class="text-[11px] text-slate-400 mt-0.5">Puedes crear combinaciones para diferentes temporadas del año y guardarlas arriba.</p>
        </div>
      `;
      refrescarIconos();
      return;
    }

    grid.innerHTML = temas.map(t => `
      <div class="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs hover:shadow-md transition-all space-y-3 ${t.activo ? 'ring-2 ring-cyan-500 border-cyan-400' : ''}">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full shrink-0" style="background-color: ${t.color_acento};"></span>
            <strong class="text-xs font-bold text-slate-800 truncate max-w-[130px]">${escapeHtml(t.nombre)}</strong>
          </div>
          ${t.activo ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-100 text-cyan-800">Activo</span>' : ''}
        </div>

        <div class="flex items-center gap-1.5 h-6 rounded-lg overflow-hidden border border-slate-200">
          <div class="h-full flex-1" style="background-color: ${t.color_primario};" title="Primario: ${t.color_primario}"></div>
          <div class="h-full flex-1" style="background-color: ${t.color_secundario};" title="Secundario: ${t.color_secundario}"></div>
          <div class="h-full flex-1" style="background-color: ${t.color_acento};" title="Acento: ${t.color_acento}"></div>
        </div>

        <div class="flex items-center justify-between gap-1.5 pt-1">
          <button type="button" onclick="aplicarTemaGuardado(${t.id}, '${t.color_primario}', '${t.color_secundario}', '${t.color_acento}', '${escapeHtml(t.nombre)}')" class="flex-1 py-1 px-2 rounded-lg bg-slate-900 hover:bg-black text-white text-[11px] font-bold transition-all flex items-center justify-center gap-1">
            <i data-lucide="check" class="w-3 h-3 text-cyan-400"></i>
            <span>Usar</span>
          </button>
          <button type="button" onclick="seleccionarPresetColor('${t.color_primario}', '${t.color_secundario}', '${t.color_acento}', true)" class="p-1 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 text-[11px]" title="Cargar en editor para modificar">
            <i data-lucide="edit-3" class="w-3 h-3"></i>
          </button>
          <button type="button" onclick="eliminarTemaGuardado(${t.id}, '${escapeHtml(t.nombre)}')" class="p-1 rounded-lg border border-rose-200 hover:bg-rose-50 text-rose-600 text-[11px]" title="Eliminar tema">
            <i data-lucide="trash-2" class="w-3 h-3"></i>
          </button>
        </div>
      </div>
    `).join('');
    refrescarIconos();
  } catch (err) {
    console.error('Error cargando temas:', err);
    grid.innerHTML = '<div class="col-span-full p-4 text-center text-rose-500 text-xs">Error cargando temas.</div>';
  }
}

async function guardarNuevoTemaPersonalizado() {
  const orgId = orgSeleccionadaColorimetriaId || currentUser?.organizacion_id;
  if (!orgId) {
    mostrarToast('Selecciona una organización para guardar el tema.', 'error');
    return;
  }

  const inNombre = document.getElementById('input-nombre-nuevo-tema');
  const nombre = inNombre?.value.trim() || `Tema ${new Date().toLocaleDateString('es-CO')}`;
  const p = document.getElementById('hex-color-primario')?.value.trim() || '#0a192f';
  const s = document.getElementById('hex-color-secundario')?.value.trim() || '#0f273f';
  const a = document.getElementById('hex-color-acento')?.value.trim() || '#06b6d4';

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/temas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nombre: nombre,
        color_primario: p,
        color_secundario: s,
        color_acento: a,
        temporada: nombre
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error guardando tema');

    mostrarToast(`¡Tema '${nombre}' guardado exitosamente en tu colección!`, 'exito');
    if (inNombre) inNombre.value = '';
    cargarTemasGuardadosOrg(orgId);
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function aplicarTemaGuardado(temaId, p, s, a, nombre) {
  const orgId = orgSeleccionadaColorimetriaId || currentUser?.organizacion_id;
  if (!orgId) return;

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/temas/${temaId}/aplicar`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error aplicando tema');

    seleccionarPresetColor(p, s, a, true);
    aplicarColoresInstitucion({ color_primario: p, color_secundario: s, color_acento: a, color_personalizado: 1 });
    mostrarToast(`¡Tema '${nombre}' activado para la institución!`, 'exito');
    cargarTemasGuardadosOrg(orgId);
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function eliminarTemaGuardado(temaId, nombre) {
  const orgId = orgSeleccionadaColorimetriaId || currentUser?.organizacion_id;
  if (!orgId) return;
  if (!confirm(`¿Deseas eliminar el tema '${nombre}' de tu colección?`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/temas/${temaId}`, {
      method: 'DELETE'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error eliminando tema');

    mostrarToast(`Tema '${nombre}' eliminado.`, 'info');
    cargarTemasGuardadosOrg(orgId);
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// EXPORTACIÓN DE COPIA EN EXCEL CON GRÁFICAS NATIVAS
// =====================================================================
async function generarBackupExcelConGraficos() {
  mostrarToast('📊 Generando copia completa en Excel con gráficos nativos...', 'info');

  try {
    const res = await fetch(`${API_BASE}/api/sistema/backups/exportar-excel`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al exportar Excel');

    mostrarToast(`¡Archivo '${json.archivo}' generado con éxito! Iniciando descarga...`, 'exito');

    const link = document.createElement('a');
    link.href = `${API_BASE}${json.url_descarga}`;
    link.download = json.archivo;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    cargarHistorialBackups();
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// ESTADO DE COLECCIONES (ASIGNADAS Y DISPONIBLES POR ASIGNAR)
// =====================================================================
async function cargarColeccionesEstadoOrganizacion(orgId) {
  if (!orgId) return;
  const gridAsig = document.getElementById('grid-org-colecciones-analitica');
  const gridDisp = document.getElementById('grid-org-colecciones-disponibles-analitica');
  const badgeDisp = document.getElementById('badge-org-total-disponibles');
  const badgeTotal = document.getElementById('badge-org-total-col');

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/colecciones-estado`);
    const json = await res.json();
    if (!res.ok) return;

    const asignadas = json.asignadas || [];
    const disponibles = json.disponibles || [];

    if (badgeTotal) badgeTotal.innerText = `${asignadas.length} asignadas`;
    if (badgeDisp) badgeDisp.innerText = `${disponibles.length} disponibles`;

    // Renderizar Asignadas
    if (gridAsig) {
      if (asignadas.length === 0) {
        gridAsig.innerHTML = `
          <div class="col-span-full p-6 text-center bg-white border border-slate-200 rounded-xl">
            <span class="text-2xl mb-1 block">📦</span>
            <h4 class="text-xs font-bold text-slate-700">Esta institución no tiene colecciones asignadas aún</h4>
            <p class="text-[11px] text-slate-400 mt-1">Revisa la lista de colecciones disponibles abajo para asignarle su primer material.</p>
          </div>
        `;
      } else {
        gridAsig.innerHTML = asignadas.map(c => `
          <div class="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-3 hover:shadow-md transition-all">
            <div class="flex items-start justify-between gap-2">
              <div>
                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 inline-block mb-1">
                  ✓ Asignada
                </span>
                <h5 class="text-xs font-bold text-slate-800 leading-snug">${escapeHtml(c.titulo)}</h5>
                <span class="text-[10px] text-slate-400 font-medium">Asignada: ${c.fecha_asignacion ? c.fecha_asignacion.substring(0, 10) : '--'}</span>
              </div>
              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-50 text-cyan-800 border border-cyan-200 shrink-0">
                ${c.total_modulos} Módulos
              </span>
            </div>

            <div class="space-y-1.5 pt-1">
              <div class="flex justify-between text-[11px] font-semibold text-slate-600">
                <span>Avance Promedio:</span>
                <span class="text-cyan-700 font-bold">${c.avance_promedio || 0}%</span>
              </div>
              <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div class="bg-cyan-600 h-2 rounded-full transition-all" style="width: ${Math.min(100, Math.max(0, c.avance_promedio || 0))}%"></div>
              </div>
              <div class="flex justify-between text-[10px] text-slate-400">
                <span>${c.total_estudiantes_cursando || 0} aprendices cursando</span>
                <span>${c.rol_destino || 'General'}</span>
              </div>
            </div>

            ${c.enlace_url ? `
              <div class="pt-1">
                <a href="${c.enlace_url}" target="_blank" rel="noopener noreferrer" class="w-full py-1.5 px-2.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 text-center text-[11px] font-bold border border-slate-200 flex items-center justify-center gap-1.5 transition-colors">
                  <i data-lucide="external-link" class="w-3 h-3 text-cyan-600"></i>
                  <span>Ver Contenido Oficial</span>
                </a>
              </div>
            ` : ''}
          </div>
        `).join('');
      }
    }

    // Renderizar Disponibles por Asignar
    if (gridDisp) {
      if (disponibles.length === 0) {
        gridDisp.innerHTML = `
          <div class="col-span-full p-6 text-center bg-white border border-slate-200 rounded-xl">
            <span class="text-2xl mb-1 block">🎉</span>
            <h4 class="text-xs font-bold text-slate-700">¡Todas las colecciones de la plataforma están asignadas a esta institución!</h4>
            <p class="text-[11px] text-slate-400 mt-1">Puedes agregar nuevo material desde la pestaña de Catálogo de Contenidos.</p>
          </div>
        `;
      } else {
        gridDisp.innerHTML = disponibles.map(c => `
          <div class="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-3 hover:shadow-md transition-all flex flex-col justify-between">
            <div class="space-y-1.5">
              <div class="flex items-start justify-between gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                  ⚡ Disponible por Asignar
                </span>
                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">
                  ${c.total_modulos} Módulos
                </span>
              </div>
              <h5 class="text-xs font-bold text-slate-800 leading-snug">${escapeHtml(c.titulo)}</h5>
              <div class="text-[10px] text-slate-400">Tipo: <span class="font-medium text-slate-600">${c.tipo_material || 'Curso'}</span> | Destino: <span class="font-medium text-slate-600">${c.rol_destino || 'General'}</span></div>
            </div>

            <div class="pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
              ${c.enlace_url ? `
                <a href="${c.enlace_url}" target="_blank" rel="noopener noreferrer" class="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100" title="Previsualizar enlace">
                  <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                </a>
              ` : '<span></span>'}
              <button onclick="asignarColeccionRapida(${orgId}, ${c.id}, '${escapeHtml(c.titulo)}')" class="px-3 py-1.5 rounded-lg bg-cyan-700 hover:bg-cyan-800 text-white text-xs font-bold shadow-2xs flex items-center gap-1.5 transition-all">
                <i data-lucide="plus-circle" class="w-3.5 h-3.5"></i>
                <span>Asignar a esta Institución</span>
              </button>
            </div>
          </div>
        `).join('');
      }
    }

    refrescarIconos();
  } catch (err) {
    console.error('Error cargando estado de colecciones:', err);
  }
}

async function asignarColeccionRapida(orgId, materialId, titulo) {
  if (!confirm(`¿Deseas asignar la colección '${titulo}' a esta institución? Sus aprendices tendrán acceso de inmediato.`)) return;

  try {
    const res = await fetch(`${API_BASE}/api/organizaciones/${orgId}/asignar-coleccion/${materialId}`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al asignar colección');

    mostrarToast(json.mensaje || `¡Colección '${titulo}' asignada correctamente!`, 'exito');
    cargarAnaliticaPorOrganizacion(orgId);
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

// =====================================================================
// PERSONALIZACIÓN DEL ESPACIO DE TRABAJO (TEMAS FESTIVOS & FONDOS)
// =====================================================================
function abrirConfiguracionEspacioDesdeAprendiz() {
  navegarVista('configuraciones');
  cambiarTabConfiguracion('espacio');
}

async function cargarEstadoEspacioTrabajo() {
  if (!currentUser) return;

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/espacio-trabajo`);
    const json = await res.json();
    if (res.ok && json.data) {
      currentUser.tema_decorativo = json.data.tema_decorativo || 'estandar';
      currentUser.fondo_personalizado = json.data.fondo_personalizado || null;
      currentUser.racha_semanas = json.data.racha_semanas !== undefined ? json.data.racha_semanas : 5;
      if (json.data.foto_perfil) currentUser.foto_perfil = json.data.foto_perfil;
      if (json.data.colores_personalizados) {
        currentUser.colores_personalizados = typeof json.data.colores_personalizados === 'string'
          ? JSON.parse(json.data.colores_personalizados)
          : json.data.colores_personalizados;
      }
      if (json.data.disenos_personalizados_json) {
        currentUser.disenos_personalizados = typeof json.data.disenos_personalizados_json === 'string'
          ? JSON.parse(json.data.disenos_personalizados_json)
          : json.data.disenos_personalizados_json;
      }
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    }
  } catch (e) {
    console.warn('Error cargando espacio de trabajo:', e);
  }

  const esAprendiz = (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante');
  const badgeRachaCont = document.getElementById('badge-espacio-racha-status');
  const btnAvanzar = document.getElementById('btn-avanzar-racha-semanal');
  const bannerRacha = document.getElementById('banner-espacio-racha-info');
  const badgeRacha = document.getElementById('cfg-espacio-racha-num');
  const bannerTitulo = document.getElementById('banner-espacio-racha-titulo');
  const bannerDesc = document.getElementById('banner-espacio-racha-desc');

  if (!esAprendiz) {
    if (badgeRachaCont) badgeRachaCont.classList.add('hidden');
    if (btnAvanzar) btnAvanzar.classList.add('hidden');
    if (bannerRacha) bannerRacha.classList.add('hidden');
  } else {
    if (badgeRachaCont) badgeRachaCont.classList.remove('hidden');
    if (btnAvanzar) btnAvanzar.classList.remove('hidden');
    if (bannerRacha) bannerRacha.classList.remove('hidden');

    const rachaNum = currentUser.racha_semanas !== undefined ? currentUser.racha_semanas : 5;
    if (badgeRacha) badgeRacha.innerText = `${rachaNum} semanas`;

    if (bannerTitulo && bannerDesc) {
      if (rachaNum >= 5) {
        bannerTitulo.innerText = '🎉 ¡Nivel de Racha Alcanzado (5 Semanas)! Acceso Desbloqueado';
        bannerDesc.innerText = 'Felicitaciones por tu constancia académica. Tienes habilitados todos los fondos festivos (Navideño, Halloween, Pascuas, Superhéroes, Galaxia, Cyberpunk) y la subida de fotos personalizadas.';
      } else {
        bannerTitulo.innerText = `🔒 Desbloqueo por Racha Semanal (${rachaNum}/5 semanas)`;
        bannerDesc.innerText = `Para desbloquear los temas festivos especiales y subir fotos personalizadas, continúa completando tus rutas y quizzes para alcanzar 5 semanas consecutivas de estudio.`;
      }
    }
  }

  // Previsualización de fondo si tiene uno
  const contPreview = document.getElementById('contenedor-preview-fondo');
  const imgPreview = document.getElementById('img-preview-fondo');
  if (contPreview && imgPreview) {
    if (currentUser.fondo_personalizado) {
      imgPreview.src = currentUser.fondo_personalizado;
      contPreview.classList.remove('hidden');
    } else {
      contPreview.classList.add('hidden');
    }
  }

  // Cargar paleta personalizada guardada en los inputs
  let paletaGuardada = currentUser.colores_personalizados || JSON.parse(localStorage.getItem('edtech_colores_personalizados') || 'null');
  if (typeof paletaGuardada === 'string') {
    try { paletaGuardada = JSON.parse(paletaGuardada); } catch (e) {}
  }
  if (paletaGuardada) {
    if (paletaGuardada.primario) {
      const pPick = document.getElementById('picker-personal-primario');
      const pHex = document.getElementById('hex-personal-primario');
      if (pPick) pPick.value = paletaGuardada.primario;
      if (pHex) pHex.value = paletaGuardada.primario;
    }
    if (paletaGuardada.acento) {
      const aPick = document.getElementById('picker-personal-acento');
      const aHex = document.getElementById('hex-personal-acento');
      if (aPick) aPick.value = paletaGuardada.acento;
      if (aHex) aHex.value = paletaGuardada.acento;
    }
    if (paletaGuardada.fondo) {
      const fPick = document.getElementById('picker-personal-fondo');
      const fHex = document.getElementById('hex-personal-fondo');
      if (fPick) fPick.value = paletaGuardada.fondo;
      if (fHex) fHex.value = paletaGuardada.fondo;
    }
  }

  // Cargar galería dinámica de sugerencias y opciones de diseño
  cargarOpcionesDisenosTemas();

  // Mantener oculto el panel complejo de colorimetría para dejar solo Idioma y Modo Claro (Blanco) / Modo Oscuro (Negro)
  const panelEntornoAdmin = document.getElementById('panel-personalizacion-entorno-admin');
  if (panelEntornoAdmin) {
    panelEntornoAdmin.classList.add('hidden');
  }

  aplicarEstilosTemaWeb(currentUser.tema_decorativo || 'estandar', currentUser.fondo_personalizado);
}

async function aplicarTemaDecorativoWeb(tema) {
  if (!currentUser) return;
  const esAprendiz = (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante');
  const racha = currentUser.racha_semanas !== undefined ? currentUser.racha_semanas : 5;

  if (esAprendiz && racha < 5 && tema !== 'estandar' && tema !== 'minimalista' && tema !== 'personalizado') {
    return mostrarToast('🔒 Este tema festivo requiere 5 semanas consecutivas de racha. ¡Sigue aprendiendo para desbloquearlo!', 'advertencia');
  }

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/tema-decorativo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tema_decorativo: tema,
        fondo_personalizado: currentUser.fondo_personalizado
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al guardar tema');

    currentUser.tema_decorativo = tema;
    localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    aplicarEstilosTemaWeb(tema, currentUser.fondo_personalizado);
    renderizarOpcionesDisenosTemas();
    mostrarToast(`¡Estilo '${tema.toUpperCase()}' activado con éxito!`, 'exito');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function procesarSubidaFondoPersonalizado(event) {
  const archivo = event.target.files[0];
  if (!archivo) return;

  const esAprendiz = (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante');
  const racha = currentUser.racha_semanas !== undefined ? currentUser.racha_semanas : 5;
  if (esAprendiz && racha < 5) {
    return mostrarToast('🔒 Subir fotos o fondos personalizados requiere una racha semanal de 5 semanas.', 'advertencia');
  }

  if (!archivo.type.startsWith('image/')) {
    return mostrarToast('Selecciona un archivo de imagen válido (JPG, PNG, WebP).', 'advertencia');
  }

  const reader = new FileReader();
  reader.onload = async (e) => {
    const base64 = e.target.result;
    try {
      mostrarToast('Guardando foto personalizada de fondo...', 'info');
      const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/tema-decorativo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tema_decorativo: currentUser.tema_decorativo || 'estandar',
          fondo_personalizado: base64
        })
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Error al guardar fondo');

      currentUser.fondo_personalizado = base64;
      localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
      aplicarEstilosTemaWeb(currentUser.tema_decorativo, base64);

      const contPreview = document.getElementById('contenedor-preview-fondo');
      const imgPreview = document.getElementById('img-preview-fondo');
      if (contPreview && imgPreview) {
        imgPreview.src = base64;
        contPreview.classList.remove('hidden');
      }

      mostrarToast('¡Fondo de pantalla personalizado aplicado con éxito!', 'exito');
    } catch (err) {
      console.error(err);
      mostrarToast(err.message, 'error');
    }
  };
  reader.readAsDataURL(archivo);
}

async function eliminarFondoPersonalizado() {
  if (!currentUser) return;
  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/tema-decorativo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tema_decorativo: currentUser.tema_decorativo || 'estandar',
        fondo_personalizado: null
      })
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al eliminar');

    currentUser.fondo_personalizado = null;
    localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    aplicarEstilosTemaWeb(currentUser.tema_decorativo || 'estandar', null);

    const contPreview = document.getElementById('contenedor-preview-fondo');
    if (contPreview) contPreview.classList.add('hidden');

    mostrarToast('Fondo personalizado retirado.', 'info');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

function sincronizarPickerPersonal(tipo) {
  const picker = document.getElementById(`picker-personal-${tipo}`);
  const hex = document.getElementById(`hex-personal-${tipo}`);
  if (picker && hex) {
    hex.value = picker.value;
  }
}

function sincronizarHexPersonal(tipo) {
  const picker = document.getElementById(`picker-personal-${tipo}`);
  const hex = document.getElementById(`hex-personal-${tipo}`);
  if (picker && hex && /^#[0-9A-Fa-f]{6}$/.test(hex.value)) {
    picker.value = hex.value;
  }
}

async function guardarEstiloPersonalizadoColores() {
  if (!currentUser) return;
  const primario = document.getElementById('hex-personal-primario')?.value || '#0a192f';
  const acento = document.getElementById('hex-personal-acento')?.value || '#06b6d4';
  const fondo = document.getElementById('hex-personal-fondo')?.value || '#0f273f';

  const paleta = { primario, acento, fondo };
  currentUser.colores_personalizados = paleta;
  currentUser.tema_decorativo = 'personalizado';
  localStorage.setItem('edtech_colores_personalizados', JSON.stringify(paleta));
  sessionStorage.setItem('edtech_colores_personalizados', JSON.stringify(paleta));
  localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
  sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));

  aplicarEstilosTemaWeb('personalizado', currentUser.fondo_personalizado);
  renderizarOpcionesDisenosTemas();

  try {
    await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/colores-personalizados`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(paleta)
    });
    await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/tema-decorativo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tema_decorativo: 'personalizado',
        fondo_personalizado: currentUser.fondo_personalizado
      })
    });
  } catch (e) {
    console.warn('Error sincronizando estilo con servidor:', e);
  }

  mostrarToast('🎨 ¡Tu estilo personalizado de colores ha sido aplicado y guardado permanentemente!', 'exito');
}

async function avanzarRachaAprendiz() {
  if (!currentUser) return;
  const btn = document.getElementById('btn-avanzar-racha-semanal');
  if (btn) btn.disabled = true;

  try {
    mostrarToast('⚡ Verificando actividad continua de esta semana...', 'info');
    const res = await fetch(`${API_BASE}/api/aprendiz/${currentUser.id}/actualizar-racha`, {
      method: 'POST'
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.detail || 'Error al actualizar racha');

    currentUser.racha_semanas = json.racha_semanas;
    localStorage.setItem('edtech_usuario', JSON.stringify(currentUser));
    sessionStorage.setItem('edtech_usuario', JSON.stringify(currentUser));

    const badgeRacha = document.getElementById('cfg-espacio-racha-num');
    if (badgeRacha) badgeRacha.innerText = `${json.racha_semanas} semanas`;

    cargarEstadoEspacioTrabajo();

    if (json.desbloqueado) {
      mostrarToast(`🔥 ${json.mensaje} ¡Todos los temas festivos y fotos están desbloqueados!`, 'exito');
    } else {
      mostrarToast(`🔥 ${json.mensaje}`, 'exito');
    }
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

// =====================================================================
// OPCIONES Y SUGERENCIAS DE DISEÑOS TEMÁTICOS EDITABLES & ELIMINABLES
// =====================================================================
const DISENOS_SUGERENCIAS_PREDETERMINADOS = [];

let listaDisenosSugerencias = [];

async function cargarOpcionesDisenosTemas() {
  if (!currentUser) return;
  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/disenos-sugerencias`);
    if (res.ok) {
      const json = await res.json();
      if (json.disenos && Array.isArray(json.disenos)) {
        listaDisenosSugerencias = json.disenos;
      }
    }
  } catch (err) {
    console.warn('Error cargando sugerencias de diseños:', err);
  }
  renderizarOpcionesDisenosTemas();
}

function renderizarOpcionesDisenosTemas() {
  const grid = document.getElementById('grid-tarjetas-temas-decorativos');
  if (!grid) return;

  const esAprendiz = (currentUser && (currentUser.rol === 'Aprendiz' || currentUser.rol === 'Estudiante'));
  const racha = currentUser && currentUser.racha_semanas !== undefined ? currentUser.racha_semanas : 5;
  const temaActual = currentUser ? (currentUser.tema_decorativo || 'estandar') : 'estandar';

  if (!listaDisenosSugerencias || listaDisenosSugerencias.length === 0) {
    grid.innerHTML = `<div class="p-8 text-center text-slate-400 text-xs col-span-full border border-dashed border-slate-300 rounded-2xl bg-white"><p class="font-bold text-slate-700 mb-1">No tienes temas personalizados creados</p><p class="text-slate-500">Pulsa "+ Crear Tema" arriba para crear tus propios estilos con los colores y nombres que prefieras.</p></div>`;
    return;
  }

  grid.innerHTML = listaDisenosSugerencias.map(d => {
    const tipo = d.tipo_base || d.id;
    const esActivo = (temaActual === tipo || temaActual === d.id);
    const bloqueadoPorRacha = esAprendiz && racha < 5 && tipo !== 'estandar' && tipo !== 'minimalista' && tipo !== 'personalizado';
    const gradiente = d.color_gradiente || 'from-[#0a192f] via-[#0f273f] to-[#00b4d8]';

    return `
      <div class="relative rounded-2xl border transition-all duration-200 overflow-hidden bg-white flex flex-col justify-between ${esActivo ? 'border-cyan-500 shadow-md ring-2 ring-cyan-400/40' : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'}">
        <!-- Banner Superior Gradiente -->
        <div class="h-20 bg-gradient-to-br ${gradiente} p-3 flex items-start justify-between relative overflow-hidden">
          <div class="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-md flex items-center justify-center text-xl shadow-xs border border-white/30">
            <span>${d.icono || '✨'}</span>
          </div>
          <div class="flex items-center gap-1 z-10">
            ${esActivo ? `
              <span class="px-2 py-0.5 rounded-full bg-cyan-400 text-[#0a192f] font-extrabold text-[10px] shadow-xs tracking-wider">
                ACTIVO
              </span>
            ` : ''}
            <button type="button" onclick="abrirModalCrearEditarDiseno('${d.id}')" class="w-6 h-6 rounded-lg bg-black/30 hover:bg-black/50 text-white flex items-center justify-center text-xs transition-colors backdrop-blur-xs" title="Editar Nombre y Opciones de este Diseño">
              <i data-lucide="edit-3" class="w-3 h-3"></i>
            </button>
            <button type="button" onclick="eliminarOpcionDiseno('${d.id}')" class="w-6 h-6 rounded-lg bg-rose-600/70 hover:bg-rose-700 text-white flex items-center justify-center text-xs transition-colors backdrop-blur-xs" title="Eliminar Sugerencia">
              <i data-lucide="trash-2" class="w-3 h-3"></i>
            </button>
          </div>
        </div>

        <!-- Contenido y Metadatos -->
        <div class="p-4 flex-1 flex flex-col justify-between space-y-3">
          <div>
            <div class="flex items-center justify-between gap-1 mb-1">
              <h4 class="text-xs font-bold text-[#0a192f] leading-snug line-clamp-1" title="${escapeHtml(d.nombre)}">${escapeHtml(d.nombre)}</h4>
              <span class="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-semibold shrink-0">${d.tipo_base || 'tema'}</span>
            </div>
            <p class="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">${escapeHtml(d.descripcion || 'Estilo visual para tu espacio de trabajo.')}</p>
          </div>

          <!-- Botón de Acción -->
          <div>
            ${bloqueadoPorRacha ? `
              <button type="button" disabled class="w-full py-2 px-3 rounded-xl bg-slate-100 border border-slate-200 text-slate-400 text-xs font-bold cursor-not-allowed flex items-center justify-center gap-1.5">
                <i data-lucide="lock" class="w-3.5 h-3.5"></i>
                <span>Requiere 5 sem. racha</span>
              </button>
            ` : (esActivo ? `
              <button type="button" onclick="aplicarTemaDecorativoWeb('${tipo}')" class="w-full py-2 px-3 rounded-xl bg-cyan-50 border border-cyan-300 text-cyan-800 text-xs font-bold flex items-center justify-center gap-1.5 shadow-2xs">
                <i data-lucide="check" class="w-3.5 h-3.5"></i>
                <span>Diseño Activo</span>
              </button>
            ` : `
              <button type="button" onclick="aplicarTemaDecorativoWeb('${tipo}')" class="w-full py-2 px-3 rounded-xl bg-slate-900 hover:bg-[#0f273f] text-white text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-2xs">
                <i data-lucide="sparkles" class="w-3.5 h-3.5 text-cyan-400"></i>
                <span>Aplicar Diseño</span>
              </button>
            `)}
          </div>
        </div>
      </div>
    `;
  }).join('');

  refrescarIconos();
}

function abrirModalCrearEditarDiseno(disenoId) {
  const modal = document.getElementById('modal-editar-diseno-tema');
  if (!modal) return;

  const idInput = document.getElementById('modal-diseno-id');
  const tituloEl = document.getElementById('modal-diseno-titulo');
  const nombreInput = document.getElementById('modal-diseno-nombre');
  const iconoInput = document.getElementById('modal-diseno-icono');
  const tipoInput = document.getElementById('modal-diseno-tipo-base');
  const descInput = document.getElementById('modal-diseno-desc');

  if (disenoId) {
    const d = listaDisenosSugerencias.find(item => item.id === disenoId);
    if (d) {
      if (idInput) idInput.value = d.id;
      if (tituloEl) tituloEl.innerText = 'Editar Opción de Diseño / Sugerencia';
      if (nombreInput) nombreInput.value = d.nombre || '';
      if (iconoInput) iconoInput.value = d.icono || '✨';
      if (tipoInput) tipoInput.value = d.tipo_base || 'estandar';
      if (descInput) descInput.value = d.descripcion || '';
    }
  } else {
    if (idInput) idInput.value = '';
    if (tituloEl) tituloEl.innerText = 'Nueva Opción de Diseño / Sugerencia';
    if (nombreInput) nombreInput.value = '';
    if (iconoInput) iconoInput.value = '✨';
    if (tipoInput) tipoInput.value = 'estandar';
    if (descInput) descInput.value = '';
  }

  modal.classList.remove('hidden');
}

async function guardarModalDisenoTema(event) {
  event.preventDefault();
  if (!currentUser) return;

  const idInput = document.getElementById('modal-diseno-id');
  const nombreInput = document.getElementById('modal-diseno-nombre');
  const iconoInput = document.getElementById('modal-diseno-icono');
  const tipoInput = document.getElementById('modal-diseno-tipo-base');
  const descInput = document.getElementById('modal-diseno-desc');

  const id = idInput?.value?.trim() || '';
  const nombre = nombreInput?.value?.trim();
  const icono = iconoInput?.value?.trim() || '✨';
  const tipo_base = tipoInput?.value || 'estandar';
  const desc = descInput?.value?.trim() || '';

  if (!nombre) {
    return mostrarToast('Ingresa un nombre para el diseño.', 'advertencia');
  }

  const gradientesPorTipo = {
    estandar: 'from-[#0a192f] via-[#0f273f] to-[#00b4d8]',
    minimalista: 'from-slate-100 via-slate-200 to-slate-300',
    navidad: 'from-red-900 via-emerald-950 to-slate-900',
    halloween: 'from-amber-950 via-purple-950 to-slate-950',
    pascua: 'from-amber-200 via-teal-100 to-rose-200',
    superheroes: 'from-rose-900 via-blue-900 to-amber-700',
    galaxia: 'from-[#020617] via-indigo-950 to-purple-950',
    cyberpunk: 'from-fuchsia-950 via-cyan-950 to-slate-950'
  };

  const nuevoGradiente = gradientesPorTipo[tipo_base] || 'from-[#0a192f] via-[#0f273f] to-[#00b4d8]';

  if (id) {
    const idx = listaDisenosSugerencias.findIndex(d => d.id === id);
    if (idx !== -1) {
      listaDisenosSugerencias[idx] = {
        ...listaDisenosSugerencias[idx],
        nombre,
        icono,
        tipo_base,
        descripcion: desc,
        color_gradiente: nuevoGradiente
      };
    }
  } else {
    const nuevoId = 'sug_' + Date.now();
    listaDisenosSugerencias.push({
      id: nuevoId,
      nombre,
      icono,
      tipo_base,
      descripcion: desc,
      color_gradiente: nuevoGradiente
    });
  }

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/disenos-sugerencias`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ disenos: listaDisenosSugerencias })
    });
    if (!res.ok) {
      const errJson = await res.json();
      throw new Error(errJson.detail || 'Error al guardar diseño');
    }
    cerrarModal('modal-editar-diseno-tema');
    renderizarOpcionesDisenosTemas();
    mostrarToast('¡Opción de diseño guardada con éxito!', 'exito');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function eliminarOpcionDiseno(disenoId) {
  if (!currentUser) return;
  if (!confirm('¿Deseas eliminar esta sugerencia / opción de diseño?')) return;

  listaDisenosSugerencias = listaDisenosSugerencias.filter(d => d.id !== disenoId);

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/disenos-sugerencias`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ disenos: listaDisenosSugerencias })
    });
    if (!res.ok) {
      const errJson = await res.json();
      throw new Error(errJson.detail || 'Error al eliminar diseño');
    }
    renderizarOpcionesDisenosTemas();
    mostrarToast('Opción de diseño eliminada correctamente.', 'info');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

async function restablecerSugerenciasDisenos() {
  if (!currentUser) return;
  if (!confirm('¿Deseas restablecer las opciones de diseño a los estilos iniciales del sistema?')) return;

  listaDisenosSugerencias = JSON.parse(JSON.stringify(DISENOS_SUGERENCIAS_PREDETERMINADOS));

  try {
    const res = await fetch(`${API_BASE}/api/usuarios/${currentUser.id}/disenos-sugerencias`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ disenos: listaDisenosSugerencias })
    });
    if (!res.ok) {
      const errJson = await res.json();
      throw new Error(errJson.detail || 'Error al restablecer diseños');
    }
    renderizarOpcionesDisenosTemas();
    mostrarToast('Diseños restablecidos al catálogo base.', 'exito');
  } catch (err) {
    console.error(err);
    mostrarToast(err.message, 'error');
  }
}

function aplicarEstilosTemaWeb(tema, fondoPersonalizado) {
  document.body.classList.remove('tema-navidad', 'tema-halloween', 'tema-pascua', 'tema-superheroes', 'tema-galaxia', 'tema-cyberpunk', 'tema-minimalista');
  const mainLayout = document.getElementById('app-layout') || document.body;

  // Manejo de paleta de colores
  if (tema === 'personalizado') {
    const paleta = currentUser?.colores_personalizados || JSON.parse(localStorage.getItem('edtech_colores_personalizados') || 'null');
    if (paleta) {
      if (paleta.primario) document.documentElement.style.setProperty('--navy-sidebar', paleta.primario);
      if (paleta.fondo) document.documentElement.style.setProperty('--navy-hover', paleta.fondo);
      if (paleta.acento) document.documentElement.style.setProperty('--cyan-accent', paleta.acento);
    }
  } else {
    // Si la organización tiene colores propios, aplicarlos; si no, resetear a los de por defecto
    if (currentUser?.organizacion?.color_personalizado) {
      aplicarColoresInstitucion(currentUser.organizacion);
    } else {
      document.documentElement.style.removeProperty('--navy-sidebar');
      document.documentElement.style.removeProperty('--navy-hover');
      document.documentElement.style.removeProperty('--cyan-accent');
    }
  }

  // Manejo de fondos y temas visuales
  if (fondoPersonalizado) {
    mainLayout.style.backgroundImage = `linear-gradient(rgba(10, 25, 47, 0.84), rgba(15, 39, 63, 0.90)), url('${fondoPersonalizado}')`;
    mainLayout.style.backgroundSize = 'cover';
    mainLayout.style.backgroundAttachment = 'fixed';
    mainLayout.style.backgroundPosition = 'center';
  } else {
    mainLayout.style.removeProperty('background-image');
    mainLayout.style.removeProperty('background-size');
    mainLayout.style.removeProperty('background-attachment');
    mainLayout.style.removeProperty('background-position');

    if (tema === 'minimalista') {
      document.body.classList.add('tema-minimalista');
    } else if (tema === 'navidad') {
      document.body.classList.add('tema-navidad');
      mainLayout.style.backgroundImage = 'radial-gradient(circle at 10% 20%, rgba(6, 78, 59, 0.15) 0%, transparent 40%), radial-gradient(circle at 90% 80%, rgba(159, 18, 57, 0.15) 0%, transparent 40%)';
    } else if (tema === 'halloween') {
      document.body.classList.add('tema-halloween');
      mainLayout.style.backgroundImage = 'radial-gradient(circle at 15% 15%, rgba(124, 45, 18, 0.18) 0%, transparent 45%), radial-gradient(circle at 85% 85%, rgba(88, 28, 135, 0.18) 0%, transparent 45%)';
    } else if (tema === 'pascua') {
      document.body.classList.add('tema-pascua');
      mainLayout.style.backgroundImage = 'radial-gradient(circle at 20% 30%, rgba(251, 191, 36, 0.14) 0%, transparent 40%), radial-gradient(circle at 80% 70%, rgba(244, 114, 182, 0.14) 0%, transparent 40%)';
    } else if (tema === 'superheroes') {
      document.body.classList.add('tema-superheroes');
      mainLayout.style.backgroundImage = 'radial-gradient(circle at 20% 20%, rgba(225, 29, 72, 0.16) 0%, transparent 45%), radial-gradient(circle at 80% 80%, rgba(30, 58, 138, 0.18) 0%, transparent 45%)';
    } else if (tema === 'galaxia') {
      document.body.classList.add('tema-galaxia');
      mainLayout.style.backgroundImage = 'radial-gradient(circle at 50% 20%, rgba(99, 102, 241, 0.18) 0%, transparent 50%), radial-gradient(circle at 80% 80%, rgba(147, 51, 234, 0.18) 0%, transparent 50%)';
    } else if (tema === 'cyberpunk') {
      document.body.classList.add('tema-cyberpunk');
      mainLayout.style.backgroundImage = 'radial-gradient(circle at 30% 20%, rgba(217, 70, 239, 0.16) 0%, transparent 45%), radial-gradient(circle at 70% 80%, rgba(6, 182, 212, 0.16) 0%, transparent 45%)';
    }
  }

  const temaCorp = localStorage.getItem('edtech_tema_visual') || 'claro';
  if (!document.body.classList.contains('tema-oscuro') && !document.body.classList.contains('tema-claro')) {
    document.body.classList.add(`tema-${temaCorp}`);
  }
}

// =====================================================================
// MÓDULO DE CIBERSEGURIDAD, FIREWALL WAF Y ESCÁNER OWASP
// =====================================================================
const escaparHTML = typeof escapeHtml === 'function' ? escapeHtml : (str => String(str || '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[m]));

async function cargarPanelCiberseguridad() {
  try {
    const res = await fetch(`${API_BASE}/api/seguridad/estado`);
    if (!res.ok) throw new Error("No se pudo obtener el estado del Firewall");
    const data = await res.json();

    const elWaf = document.getElementById('sec-kpi-waf-status');
    const elTunel = document.getElementById('sec-kpi-tunnel-url');
    const elBloq = document.getElementById('sec-kpi-ips-bloqueadas');
    const elAmenazas = document.getElementById('sec-kpi-amenazas-total');
    const elLabelBloq = document.getElementById('label-total-ips-bloqueadas');
    const elLabelInc = document.getElementById('label-total-incidentes');

    if (elWaf) elWaf.innerText = data.waf_activo ? "100% ACTIVO" : "INACTIVO";
    if (elTunel) {
      const urlClean = data.enlace_publico ? data.enlace_publico.replace('https://', '') : 'trycloudflare.com';
      elTunel.innerText = urlClean;
      elTunel.title = data.enlace_publico || '';
    }
    if (elBloq) elBloq.innerText = data.total_ips_bloqueadas || 0;
    if (elAmenazas) elAmenazas.innerText = data.total_amenazas_neutralizadas || 0;
    if (elLabelBloq) elLabelBloq.innerText = `${data.total_ips_bloqueadas || 0} IPs en lista negra`;
    if (elLabelInc) elLabelInc.innerText = `${data.total_amenazas_neutralizadas || 0} interceptados`;

    await cargarIpsBloqueadasUI();
    await cargarIncidentesSeguridadUI();
    await cargarResumenEscaneoPrevioUI();
    refrescarIconos();
  } catch (err) {
    console.error("Error al cargar panel de ciberseguridad:", err);
  }
}

async function cargarIpsBloqueadasUI() {
  const tbody = document.getElementById('tabla-ips-bloqueadas-body');
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/seguridad/ips-bloqueadas`);
    const data = await res.json();
    const ips = (data.ips || []).filter(i => i.bloqueo_activo === 1);

    if (!ips || ips.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" class="text-center py-4 text-slate-400 font-medium">No hay IPs restringidas actualmente</td></tr>`;
      return;
    }

    tbody.innerHTML = ips.map(i => `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-2 px-2.5 font-mono font-bold text-rose-700">${escaparHTML(i.ip)}</td>
        <td class="py-2 px-2.5 text-slate-600 truncate max-w-[140px]" title="${escaparHTML(i.motivo)}">${escaparHTML(i.motivo)}</td>
        <td class="py-2 px-2.5 text-right">
          <button onclick="desbloquearIpUI('${i.ip}')" class="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-cyan-50 hover:bg-cyan-100 text-cyan-800 border border-cyan-200 transition-all">
            Desbloquear
          </button>
        </td>
      </tr>
    `).join('');
    refrescarIconos();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="3" class="text-center py-3 text-rose-500">Error cargando lista de IPs</td></tr>`;
  }
}

async function desbloquearIpUI(ip) {
  if (!confirm(`¿Deseas desbloquear y restaurar el acceso para la IP ${ip}?`)) return;
  try {
    const res = await fetch(`${API_BASE}/api/seguridad/desbloquear-ip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error desbloqueando IP");
    mostrarToast(data.mensaje || `IP ${ip} desbloqueada`, 'exito');
    cargarPanelCiberseguridad();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

async function bloquearIpManualUI(event) {
  event.preventDefault();
  const inputIp = document.getElementById('input-ip-bloquear');
  const inputMotivo = document.getElementById('input-motivo-bloquear');
  const ip = inputIp ? inputIp.value.trim() : '';
  const motivo = inputMotivo ? inputMotivo.value.trim() : 'Bloqueo manual preventivo';

  if (!ip) return;
  try {
    const res = await fetch(`${API_BASE}/api/seguridad/bloquear-ip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip, motivo })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error bloqueando IP");
    mostrarToast(data.mensaje || `IP ${ip} agregada a lista negra`, 'exito');
    if (inputIp) inputIp.value = '';
    if (inputMotivo) inputMotivo.value = '';
    cargarPanelCiberseguridad();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

async function cargarIncidentesSeguridadUI() {
  const tbody = document.getElementById('tabla-incidentes-body');
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/seguridad/incidentes-recientes`);
    const data = await res.json();
    const incs = data.incidentes || [];

    if (incs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-slate-400 font-medium">Sin incidentes registrados recientemente. El perímetro está seguro.</td></tr>`;
      return;
    }

    tbody.innerHTML = incs.map(inc => {
      let badgeCls = "bg-rose-100 text-rose-800 border-rose-200";
      if (inc.tipo_amenaza.includes("BOT")) badgeCls = "bg-purple-100 text-purple-800 border-purple-200";
      if (inc.tipo_amenaza.includes("FUERZA")) badgeCls = "bg-amber-100 text-amber-800 border-amber-200";

      return `
        <tr class="hover:bg-slate-50 transition-colors">
          <td class="py-2 px-2.5 text-slate-500 whitespace-nowrap text-[11px]">${escaparHTML(inc.fecha_hora || '')}</td>
          <td class="py-2 px-2.5 font-mono font-bold text-slate-800 text-[11px]">${escaparHTML(inc.ip)}</td>
          <td class="py-2 px-2.5 whitespace-nowrap">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeCls}">
              ${escaparHTML(inc.tipo_amenaza)}
            </span>
          </td>
          <td class="py-2 px-2.5 text-slate-600 text-[11px] max-w-xs truncate" title="${escaparHTML(inc.detalles)}">
            ${escaparHTML(inc.detalles)}
          </td>
          <td class="py-2 px-2.5 text-right whitespace-nowrap">
            <span class="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
              <i data-lucide="mail-check" class="w-3 h-3 text-emerald-600"></i>
              <span>Alerta Despachada</span>
            </span>
          </td>
        </tr>
      `;
    }).join('');
    refrescarIconos();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-rose-500">Error cargando incidentes</td></tr>`;
  }
}

async function cargarResumenEscaneoPrevioUI() {
  const cont = document.getElementById('lista-pruebas-escaneo');
  if (!cont || cont.children.length > 0) return;
  await ejecutarEscaneoVulnerabilidadesUI(false);
}

async function ejecutarEscaneoVulnerabilidadesUI(mostrarToastMsg = true) {
  const btn = document.getElementById('btn-iniciar-escaneo');
  const cont = document.getElementById('lista-pruebas-escaneo');
  const labelScore = document.getElementById('escaneo-score-label');
  const badgeScore = document.getElementById('escaneo-badge-score');
  const labelFecha = document.getElementById('escaneo-fecha-label');

  if (btn && mostrarToastMsg) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Analizando OWASP Top 10...</span>`;
    refrescarIconos();
  }

  try {
    const res = await fetch(`${API_BASE}/api/seguridad/escaneo-vulnerabilidades`);
    if (!res.ok) throw new Error("Fallo al ejecutar el escaneo de seguridad");
    const data = await res.json();

    if (labelScore) labelScore.innerText = `${data.score_seguridad} / 100`;
    if (badgeScore) badgeScore.innerText = `${data.score_seguridad}%`;
    if (labelFecha) labelFecha.innerText = `Último escaneo ejecutado: ${data.fecha_escaneo}`;

    if (cont && data.pruebas) {
      cont.innerHTML = data.pruebas.map(p => `
        <div class="owasp-prueba-card p-3.5 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-white transition-all flex items-start gap-3 shadow-xs">
          <div class="owasp-check-icon w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-black text-xs shrink-0 mt-0.5">
            <i data-lucide="check" class="w-4 h-4"></i>
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-2">
              <span class="owasp-prueba-titulo text-xs font-bold text-[#0a192f] truncate">${escaparHTML(p.nombre)}</span>
              <span class="owasp-badge-aprobado px-2 py-0.5 rounded text-[10px] font-extrabold bg-emerald-100 text-emerald-800">
                ${p.estado}
              </span>
            </div>
            <p class="owasp-prueba-meta text-[10px] font-bold text-cyan-700 uppercase tracking-wider mt-0.5">${escaparHTML(p.categoria)} · ${p.id}</p>
            <p class="owasp-prueba-evidencia text-[11px] text-slate-600 mt-1 leading-snug">${escaparHTML(p.evidencia)}</p>
          </div>
        </div>
      `).join('');
    }

    if (mostrarToastMsg) {
      mostrarToast(`🛡️ Escaneo completado: ${data.score_seguridad}% de seguridad. Sistema 100% blindado.`, 'exito');
    }
  } catch (err) {
    if (mostrarToastMsg) mostrarToast(err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="scan" class="w-4 h-4"></i><span>🔍 Ejecutar Escáner OWASP</span>`;
      refrescarIconos();
    }
  }
}

