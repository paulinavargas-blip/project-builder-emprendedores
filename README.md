# Project Builder – Desarrollo de Emprendedores | WEB v1

Esta versión está pensada para publicarse una sola vez en Internet y compartirse mediante una liga en Blackboard.

## Arquitectura

- Interfaz: Streamlit
- Base de datos: Supabase
- Despliegue sugerido: Streamlit Community Cloud
- Código: GitHub
- Acceso del alumno: navegador web, sin instalar Python

## Cómo funciona para el alumno

1. Entra a la liga del Project Builder.
2. Crea su proyecto con:
   - código único de equipo
   - nombre del proyecto
   - PIN
3. Trabaja los módulos.
4. Pulsa Guardar.
5. Otro día vuelve a la misma liga, captura código + PIN y recupera su avance.
6. Puede descargar el Plan de Negocios acumulado en Word.

## Archivos principales

- `streamlit_app.py`: aplicación web.
- `data/modulos.json`: contenido académico del curso.
- `sql/01_crear_base_de_datos.sql`: crea la tabla de proyectos.
- `.streamlit/secrets.toml.example`: ejemplo de secretos.
- `requirements.txt`: dependencias para el servidor.

## PASO 1 — Crear Supabase

1. Crear un proyecto en Supabase.
2. Abrir SQL Editor.
3. Copiar y ejecutar `sql/01_crear_base_de_datos.sql`.
4. En Project Settings > API copiar:
   - Project URL
   - service_role key

IMPORTANTE: la service_role key es secreta. Nunca debe subirse a GitHub.

## PASO 2 — Subir el código a GitHub

Crear un repositorio y subir esta carpeta.
Puede ser privado.

No subir un archivo real `.streamlit/secrets.toml`.
El `.gitignore` ya lo excluye.

## PASO 3 — Publicar en Streamlit Community Cloud

1. Entrar a Streamlit Community Cloud con GitHub.
2. Crear una app nueva desde el repositorio.
3. Indicar como archivo principal:
   `streamlit_app.py`
4. Abrir Advanced settings / Secrets.
5. Agregar:

SUPABASE_URL = "..."
SUPABASE_SERVICE_KEY = "..."

6. Publicar.

Al finalizar, Streamlit genera una URL `*.streamlit.app`.

## PASO 4 — Blackboard

Agregar en Blackboard un enlace web con un nombre como:

**Project Builder – Desarrollo de Emprendedores**

Los alumnos solo necesitarán abrir la liga.

## Seguridad de acceso

Cada proyecto utiliza:
- código único de equipo
- PIN
- hash PBKDF2 con salt individual

El PIN no se almacena en texto visible.

## Recomendación operativa

Antes de liberar la liga:
- crear 2 o 3 proyectos de prueba;
- probar guardar/cerrar/volver a entrar;
- probar dos navegadores distintos;
- generar el Word final;
- confirmar que los costos de Mercadotecnia, Operaciones, Talento y Legal se integran correctamente con Finanzas.

## Futuras mejoras posibles

- panel de profesora/administradora;
- restablecimiento de PIN;
- carga de anexos/evidencias;
- rúbricas y semáforo de calidad;
- historial de versiones;
- exportación final con portada institucional;
- acceso mediante correo institucional.
