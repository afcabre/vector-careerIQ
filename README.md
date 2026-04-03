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
- flujo vertical inicial implementado: login tutor + seleccion de persona consultada
- persistencia conmutada para `persons` y validacion de operador: `memory` o `firestore`
- persistencia conmutada para sesion backend: `memory` o `firestore`
- conversacion persistente por `person_id` implementada en backend y frontend
- `/chat` y `/chat/stream` conectados a OpenAI (`OPENAI_API_KEY`) con fallback seguro
- `/search` y guardado explicito de oportunidades implementados por `person_id`
- `analyze` y `prepare` por oportunidad implementados con artefactos persistidos
- importacion manual de vacantes por URL y texto pegado desde frontend

## Siguiente paso
- completar ingesta de CV con un solo CV activo por persona
- integrar `Adzuna` y `Remotive API` en busqueda multi-provider
- ampliar trazabilidad de evidencia para fit cultural

## Arranque Local Minimo
### Backend
- copiar `apps/backend/.env.example` a `apps/backend/.env`
- seleccionar backend de persistencia:
  - local rapido: `PERSISTENCE_BACKEND=memory`
  - persistente: `PERSISTENCE_BACKEND=firestore`
- instalar dependencias:
  - `cd apps/backend`
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -r requirements.txt`
- ejecutar API:
  - `uvicorn app.main:app --reload --port 8000`

Si usas `firestore`, define en `.env`:
- `FIREBASE_CREDENTIALS_FILE` apuntando al JSON de servicio
o
- `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY`

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
