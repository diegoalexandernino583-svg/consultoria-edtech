-- 1. Limpieza de tablas (Orden estricto por llaves foráneas)
DROP TABLE IF EXISTS asignacion_material;
DROP TABLE IF EXISTS material_capacitacion;
DROP TABLE IF EXISTS progreso_cursos;
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS catalogo_cursos;
DROP TABLE IF EXISTS organizaciones;
GO

-- 2. Organizaciones (Ahora con control de cupos dictados por el Super Administrador)
CREATE TABLE organizaciones (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tipo_organizacion VARCHAR(50) NOT NULL, 
    dominio_permitido VARCHAR(100) NOT NULL, 
    licencias_asignadas INT DEFAULT 0, 
    max_administradores INT DEFAULT 1, -- Tú controlas cuántos admins pueden tener
    max_mentores INT DEFAULT 5,        -- Tú controlas cuántos mentores
    fecha_creacion DATETIME DEFAULT GETDATE(),
    estado_activo BIT DEFAULT 1
);
GO

-- 3. Catálogo de Cursos Base
CREATE TABLE catalogo_cursos (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nombre_curso VARCHAR(150) NOT NULL,
    descripcion TEXT
);
GO

-- 4. Usuarios (Jerarquía Oficial + Conexión Aprendiz/Mentor)
CREATE TABLE usuarios (
    id INT IDENTITY(1,1) PRIMARY KEY,
    organizacion_id INT,
    mentor_id INT NULL, -- Enlaza al Aprendiz directamente con su Mentor
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(100) UNIQUE NOT NULL,
    rol VARCHAR(50) NOT NULL, -- 'Super Administrador', 'Administrador', 'Mentor', 'Aprendiz'
    password_hash VARCHAR(255),
    FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id),
    FOREIGN KEY (mentor_id) REFERENCES usuarios(id)
);
GO

-- 5. Progreso para reportes y Power BI
CREATE TABLE progreso_cursos (
    id INT IDENTITY(1,1) PRIMARY KEY,
    usuario_id INT,
    curso_id INT,
    porcentaje_avance DECIMAL(5,2) DEFAULT 0.00,
    tiempo_dedicado_minutos INT DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (curso_id) REFERENCES catalogo_cursos(id)
);
GO

-- =========================================================
-- NUEVO: SISTEMA DE DISTRIBUCIÓN DE CONTENIDO
-- =========================================================

-- Tabla para que el Super Administrador suba las capacitaciones
CREATE TABLE material_capacitacion (
    id INT IDENTITY(1,1) PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    tipo_material VARCHAR(50), -- Ej: 'Colección Microsoft', 'Módulo SENA', 'Video'
    enlace_url VARCHAR(500) NOT NULL,
    fecha_publicacion DATETIME DEFAULT GETDATE()
);
GO

-- Tabla que decide a qué organizaciones se les envía el material (Tu panel de control)
CREATE TABLE asignacion_material (
    id INT IDENTITY(1,1) PRIMARY KEY,
    material_id INT,
    organizacion_id INT NULL, -- Si es NULL, le llega a todas. Si tiene un ID, le llega solo a esa.
    FOREIGN KEY (material_id) REFERENCES material_capacitacion(id),
    FOREIGN KEY (organizacion_id) REFERENCES organizaciones(id)
);
GO

-- =========================================================
-- 6. INYECCIÓN DE DATOS DE PRUEBA (Arquitectura Definitiva)
-- =========================================================

INSERT INTO organizaciones (nombre, tipo_organizacion, dominio_permitido, licencias_asignadas, max_administradores, max_mentores) VALUES 
('UNIMINUTO', 'Educativa', 'uniminuto.edu.co', 500, 2, 20),
('Hotmart', 'Empresa', 'hotmart.com', 100, 1, 5);
GO

-- Tú eres el Super Administrador (No necesitas organización, pero te asociamos a la master si quieres)
INSERT INTO usuarios (organizacion_id, mentor_id, nombre, correo, rol, password_hash) VALUES 
(1, NULL, 'Diego Alexander Niño Niño', 'alexander.nino.583@gmail.com', 'Super Administrador', NULL),
(1, NULL, 'Mentor UNIMINUTO', 'mentor@uniminuto.edu.co', 'Mentor', NULL);
GO

-- El aprendiz amarrado a su mentor (ID 2)
INSERT INTO usuarios (organizacion_id, mentor_id, nombre, correo, rol, password_hash) VALUES 
(1, 2, 'Aprendiz Prueba', 'aprendiz@uniminuto.edu.co', 'Aprendiz', NULL);
GO