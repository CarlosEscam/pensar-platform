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
cp backend/.env.example backend/.env   # y cambiar SECRET_KEY por un valor largo y aleatorio
docker compose up --build
# API:  http://localhost:8000      Documentación interactiva: http://localhost:8000/docs
```

## Ejecutar en local (sin Docker)

```bash
cd backend
python -m venv venv && source venv/bin/activate      # en Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # ajustar SECRET_KEY y DATABASE_URL
uvicorn app.main:app --reload
```

`SECRET_KEY` es obligatoria: la aplicación no arranca sin ella.

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
