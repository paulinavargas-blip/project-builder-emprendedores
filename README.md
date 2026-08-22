# Project Builder – Desarrollo de Emprendedores | MULTI v1

Arquitectura para una administradora que también puede ser profesora, tres profesores adicionales, grupos, 5–6 equipos por profesor y un proyecto por equipo.

## Roles

**Administradora + Profesora:** alterna entre `Panel administrador` y `Mis grupos`.

**Profesor:** ve solo sus grupos, crea equipos/proyectos, consulta avance y puede restablecer PIN de equipo.

**Equipo:** entra con código único + PIN, trabaja el Builder, guarda en línea y descarga su Plan de Negocios.

## Base de datos

`app_users → groups → teams → projects`

## Antes de publicar

Como la tabla actual todavía no contiene proyectos reales, ejecutar en Supabase SQL Editor:

`sql/01_REEMPLAZAR_ESQUEMA_MULTI.sql`

## Secrets en Streamlit

```toml
SUPABASE_URL = "..."
SUPABASE_SERVICE_KEY = "..."
INITIAL_ADMIN_NAME = "..."
INITIAL_ADMIN_EMAIL = "..."
INITIAL_ADMIN_PASSWORD = "..."
```

Cuando `app_users` está vacío, la aplicación crea automáticamente la primera cuenta con `is_admin=true` e `is_teacher=true`.

## Flujo de configuración

1. Ejecutar el nuevo SQL en Supabase.
2. Reemplazar los archivos del repositorio GitHub con esta versión.
3. Configurar Secrets en Streamlit.
4. Publicar una sola app.
5. Iniciar sesión como administradora/profesora.
6. Crear a los otros 3 profesores.
7. Crear y asignar grupos.
8. Cada profesor crea sus 5–6 equipos.
9. Entregar código + PIN a cada equipo.
10. Publicar una sola URL en Blackboard.

## Seguridad

Contraseñas y PIN se almacenan como PBKDF2 + salt. La clave privada de Supabase nunca debe subirse a GitHub. RLS queda activado y la aplicación accede desde el servidor usando `SUPABASE_SERVICE_KEY`.
