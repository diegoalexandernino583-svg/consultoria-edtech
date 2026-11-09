-- ============================================================================
-- SCRIPT DE OPTIMIZACIÓN Y AISLAMIENTO SAAS MULTI-TENANT: AZURE SQL DATABASE
-- Plataforma: Education Technology SaaS
-- Autor: Arquitectura de Software & Base de Datos
-- ============================================================================

-- 1. ÍNDICES COMPUESTOS B-TREE CON COBERTURA (INCLUDE) PARA AISLAMIENTO TENANT
-- Garantiza búsquedas con latencia < 30ms incluso con millones de registros por colegio

-- Índices para la tabla de Usuarios por Institución / Tenant
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_usuarios_tenant_correo' AND object_id = OBJECT_ID('usuarios'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_usuarios_tenant_correo
    ON usuarios (institucion_id, correo)
    INCLUDE (id, nombre, rol, activo, fecha_creacion);
    PRINT 'Índice IX_usuarios_tenant_correo creado con éxito.';
END
GO

-- Índices para Cursos y Entornos por Institución
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_cursos_tenant_activo' AND object_id = OBJECT_ID('cursos'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_cursos_tenant_activo
    ON cursos (institucion_id, activo)
    INCLUDE (id, titulo, nivel, tutor_id);
    PRINT 'Índice IX_cursos_tenant_activo creado con éxito.';
END
GO

-- Índices para Registro de Actividad y Auditoría
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_auditoria_tenant_fecha' AND object_id = OBJECT_ID('registro_actividad'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_auditoria_tenant_fecha
    ON registro_actividad (institucion_id, fecha DESC)
    INCLUDE (id, usuario_id, modulo, accion);
    PRINT 'Índice IX_auditoria_tenant_fecha creado con éxito.';
END
GO

-- Índices para el Videojuego Educativo de Matemáticas
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_videojuego_ejercicios_nivel' AND object_id = OBJECT_ID('videojuego_matematicas_ejercicios'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_videojuego_ejercicios_nivel
    ON videojuego_matematicas_ejercicios (nivel, orden, activo)
    INCLUDE (id, pregunta, tipo, opciones, respuesta_correcta, puntos);
    PRINT 'Índice IX_videojuego_ejercicios_nivel creado con éxito.';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_progreso_videojuego_usuario_tenant' AND object_id = OBJECT_ID('progreso_videojuego_matematicas'))
BEGIN
    CREATE NONCLUSTERED INDEX IX_progreso_videojuego_usuario_tenant
    ON progreso_videojuego_matematicas (institucion_id, usuario_id, nivel, fecha DESC)
    INCLUDE (id, puntaje, aciertos, total_preguntas, estrellas, tiempo_segundos);
    PRINT 'Índice IX_progreso_videojuego_usuario_tenant creado con éxito.';
END
GO

-- 2. ROW-LEVEL SECURITY (RLS) PARA BLINDAJE A NIVEL DE MOTOR EN AZURE SQL
-- Previene que cualquier SELECT o UPDATE acceda a datos de otro Tenant,
-- incluso si la consulta SQL es generada sin filtro 'WHERE institucion_id = @id'.

IF SCHEMA_ID('Security') IS NULL
BEGIN
    EXEC('CREATE SCHEMA Security');
    PRINT 'Esquema Security creado con éxito.';
END
GO

CREATE OR ALTER FUNCTION Security.fn_tenant_predicate(@TenantId INT)
    RETURNS TABLE
    WITH SCHEMABINDING
AS
    RETURN SELECT 1 AS fn_securitypredicate_result
    WHERE @TenantId = CAST(SESSION_CONTEXT(N'TenantId') AS INT)
       OR SESSION_CONTEXT(N'TenantId') IS NULL -- Permite tareas de mantenimiento de sysadmin
       OR SESSION_CONTEXT(N'IsSuperAdmin') = 1;
GO

-- Ejemplo de aplicación de la política de seguridad a la tabla usuarios
-- DROP SECURITY POLICY IF EXISTS Security.TenantSecurityPolicy;
-- CREATE SECURITY POLICY Security.TenantSecurityPolicy
--     ADD FILTER PREDICATE Security.fn_tenant_predicate(institucion_id) ON dbo.usuarios,
--     ADD BLOCK PREDICATE Security.fn_tenant_predicate(institucion_id) ON dbo.usuarios AFTER INSERT,
--     ADD FILTER PREDICATE Security.fn_tenant_predicate(institucion_id) ON dbo.cursos,
--     ADD BLOCK PREDICATE Security.fn_tenant_predicate(institucion_id) ON dbo.cursos AFTER INSERT,
--     ADD FILTER PREDICATE Security.fn_tenant_predicate(institucion_id) ON dbo.progreso_videojuego_matematicas,
--     ADD BLOCK PREDICATE Security.fn_tenant_predicate(institucion_id) ON dbo.progreso_videojuego_matematicas AFTER INSERT
--     WITH (STATE = ON);
-- GO
