# 🚀 Centro de Comando EdTech - Versión Visual e Interactiva

Esta es la **versión visual e interactiva** del sistema Consultoría EdTech. Fue creada como una evolución completa de los scripts CLI originales, proporcionando una interfaz web moderna tipo SaaS para administrar la plataforma.

---

## ⚡ ¿Cómo Ejecutar la Interfaz?

Tienes dos formas súper sencillas:

### Opción 1: Con doble clic (Recomendado)
Haz doble clic sobre el archivo:
```text
iniciar_interfaz.bat
```

### Opción 2: Desde la terminal de comandos
Abre una terminal en esta carpeta y ejecuta:
```bash
python app_visual.py
```

La aplicación abrirá automáticamente tu navegador en:
👉 **`http://localhost:8000`**

---

## 🛡️ Funcionalidades Visuales Incluidas

1. **Portal de Autenticación con 2FA:**
   - Inicio de sesión con verificación de contraseña segura con `bcrypt`.
   - Generación de código OTP de 6 dígitos enviado por Gmail SMTP y visualización rápida en pantalla para pruebas instantáneas.
   - Recuperación de contraseña por código.
   - Pestaña para registro de nuevos usuarios con rol y organización asignada.
   - Botones de **1 Clic para Demostración** con perfiles pre-cargados (Super Admin, Mentor, Aprendiz, Administrador).

2. **Panel de Organizaciones & Sedes (Super Admin / Admin):**
   - Vista de tarjetas de cada institución (UNIMINUTO, Hotmart, etc.) con sus cupos, dominios oficiales y métricas de usuarios activos.
   - Modal para dar de alta nuevas organizaciones.

3. **Directorio de Usuarios y Carga Masiva Inteligente:**
   - Tabla completa de usuarios registrados.
   - Herramienta de **Carga Masiva con Escudo de Dominio**: valida automáticamente que los correos importados pertenezcan al dominio autorizado de la organización (ej: `@uniminuto.edu.co`).
   - Envío de correos de bienvenida en segundo plano sin congelar la interfaz.

4. **Mentores & Reparto Automático Balanceado:**
   - **Superpoder de Auto-Reparto**: algoritmo que asigna de forma equitativa todos los aprendices huérfanos a los mentores de su institución.
   - Vista individual de aprendices para mentores.

5. **Catálogo de Materiales y Capacitaciones:**
   - Publicación y asignación de cursos a organizaciones específicas o de forma global.
   - Integración directa con las rutas de aprendizaje de **Microsoft Learn** y tableros de **Power BI**.

6. **"El Celador" - Módulo de Auditoría en Tiempo Real:**
   - Visualización de la bitácora `auditoria_transacciones.csv`.
   - Búsqueda en vivo por usuario, módulo o detalle de error.
   - Filtros instantáneos por estado (`EXITO` / `FALLO`).
   - Métricas de salud del sistema.

7. **Arquitectura Híbrida y Resiliente:**
   - Detecta si el servidor **Azure SQL Database** está disponible a través de `pyodbc`.
   - Si la red o firewall de Azure no responde, conmuta automáticamente a **SQLite Local** sin interrumpir la experiencia de usuario ni generar pantallas de error.
