# 🏛️ Arquitectura de Base de Datos - Consultoría EdTech
**Documentación Técnica - Diagrama de Entidad-Relación (UML)**

---

## 1. Diagrama Estructural
 llave primaria
+-----------------------+       +------------------------+
|    INSTITUCIONES      |       |      USUARIOS          |
+-----------------------+       +------------------------+
| PK  id                | 1   * | PK  id                 |
|     nombre_institucion|-------| FK  institucion_id     |
|     (otros datos...)  |       |     nombre             |
+-----------------------+       |     correo             |
                                |     rol                |
                                |     password_hash      |
+-----------------------+       +------------------------+
|  CATALOGO_CURSOS      |                   | 1
+-----------------------+                   |
| PK  id                | 1                 | *
|     nombre_curso      |       +------------------------+
|     descripcion       |-------|    PROGRESO_CURSOS     |
|     (otros datos...)  | *     +------------------------+
|                       |       | PK  id                 |
+-----------------------+       | FK  usuario_id         |
                                | FK  curso_id           |
                                |     estado_progreso    |
                                +------------------------+
                            