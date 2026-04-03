# Pr Infra Escalable

Base inicial del proyecto SDD para un asistente conversacional orientado a oportunidades laborales.

## Estructura
- `apps/frontend`: frontend `React + Vite`
- `apps/backend`: backend `FastAPI`
- `.specify/`: artefactos SDD y memoria operativa
- `.specify/00.Caso-de-Uso-y-Alcance.md`: caso de uso y alcance
- `.specify/01.Constitucion.md`: constitucion del proyecto
- `.specify/02.Spec.md`: especificacion funcional
- `.specify/03.Arquitectura-y-Plan.md`: arquitectura y plan tecnico

## Estado
- documentacion normativa base creada
- scaffolding tecnico minimo creado
- dependencias no instaladas aun

## Siguiente paso
- instalar dependencias
- validar arranque local de backend y frontend
- implementar persistencia real en Firestore para auth/personas

## Arranque Local Minimo
### Backend
- copiar `apps/backend/.env.example` a `apps/backend/.env`
- instalar dependencias:
  - `cd apps/backend`
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -r requirements.txt`
- ejecutar API:
  - `uvicorn app.main:app --reload --port 8000`

Credenciales demo por defecto:
- `username`: `tutor`
- `password`: `change_me`

### Frontend
- copiar `apps/frontend/.env.example` a `apps/frontend/.env`
- instalar dependencias:
  - `cd apps/frontend`
  - `npm install`
- ejecutar app:
  - `npm run dev`
