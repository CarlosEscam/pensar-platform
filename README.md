# PENSAR

Plataforma web para diagnosticar, desarrollar y dar seguimiento al **pensamiento computacional** (abstracción, descomposición, patrones y algoritmos) en estudiantes de nuevo ingreso de la Universidad de Pamplona. Proyecto integrador de Ingeniería de Software I.

**Autores:** Carlos Alberto Escamilla Mariño · Yarly Melitza Guerrero Berbesi

## Estado (v1.0.0 — backend del MVP)

| Módulo | Estado |
|---|---|
| Autenticación JWT con roles (estudiante, docente, administrador) | Implementado |
| Diagnóstico TPC de 28 ítems calificado por dimensión (RN-01 → 409) | Implementado |
| Retos cerrados y semi-estructurados con patrón Strategy (RN-02, RN-04) | Implementado |
| Gamificación: nivel = puntos // 50 + 1 (RN-03) | Implementado |
| Interfaz web (React) y dashboard del docente | Pendiente (siguiente release) |

## Estructura

```
backend/            API FastAPI (app/, tests/, Dockerfile)
docker-compose.yml  PostgreSQL 15 + API
.github/workflows/  CI: higiene, build, lint (ruff) y pruebas con cobertura >= 90 %
```

## Ejecutar con Docker

```bash
cp .env.example .env                    # raíz: cambiar POSTGRES_PASSWORD por una contraseña aleatoria
cp backend/.env.example backend/.env   # cambiar SECRET_KEY (y la misma contraseña en DATABASE_URL)
docker compose up --build
# API:  http://localhost:8000      Documentación interactiva: http://localhost:8000/docs
```

## Ejecutar en local (sin Docker)

```bash
cd backend
python -m venv venv && source venv/bin/activate      # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # ajustar SECRET_KEY y DATABASE_URL (misma contraseña que POSTGRES_PASSWORD)
uvicorn app.main:app --reload
```

`SECRET_KEY` es obligatoria: la aplicación no arranca sin ella.

## Retos de imagen (DFD, PSeInt, Arduino, Scratch)

El estudiante sube una captura (PNG, JPG o WEBP, máx. 5 MB) a `POST /challenges/{id}/attempt-image`. Un modelo de visión evalúa cada criterio de la **rúbrica** del reto (la define el docente en `content.rubric`) y PENSAR calcula la nota como el porcentaje de criterios cumplidos; aprueba con `content.pass_score` (70 por defecto). La rúbrica no se muestra al estudiante.

- Requiere `ANTHROPIC_API_KEY` en `backend/.env`. Sin ella el endpoint responde 503 y el resto de la API funciona igual.
- Cada intento calificado tiene costo: el límite es de 5 por estudiante, reto y día.
- No se guarda la imagen, solo su huella (SHA-256), la nota y el detalle por criterio.
- Ejemplo de reto (`challenge_type: "image"`): `content = {"language": "dfd", "statement": "...", "rubric": ["Tiene inicio y fin", "Usa una decisión", "Muestra el resultado"]}`. Lenguajes: `dfd`, `pseint`, `arduino`, `scratch`.
- Bases de datos ya creadas (sin migraciones): ejecutar una vez `ALTER TYPE challengetype ADD VALUE 'image';` en PostgreSQL. En una base nueva no hace falta.

## Pruebas y calidad

```bash
cd backend
pip install -r requirements-dev.txt
pytest --cov=app --cov-fail-under=90     # SQLite temporal; no requiere PostgreSQL
ruff check app tests
```

## Flujo de trabajo

GitHub Flow: ramas de corta vida (`feature/`, `refactor/`, `chore/`), integración a `main` solo mediante Pull Request con el CI en verde. Los defectos se registran como issues (`BUG-xx`).

## Reglas de negocio

RN-01 un diagnóstico por periodo (409) · RN-02 coincidencia semántica de estructuras · RN-03 nivel por puntos · RN-04 puntos una sola vez por reto · RN-05 endpoints con JWT y roles · RN-06 28 preguntas, 7 por dimensión, sin exponer respuestas correctas.
