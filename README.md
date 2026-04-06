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
- `/search` multi-provider y guardado explicito de oportunidades implementados por `person_id`
- `analyze` y `prepare` por oportunidad implementados con artefactos persistidos
- importacion manual de vacantes por URL y texto pegado desde frontend
- carga de CV por persona (`/cv`) con un CV activo por perfil y extraccion base de texto
- indexacion vectorial del CV activo habilitada (embeddings OpenAI + upsert/query en Pinecone cuando hay configuracion)
- chunking token-aware con solapamiento aplicado al pipeline de CV para embeddings
- fit cultural en `analyze` con señales publicas trazables por fuente y advertencias de evidencia
- `analyze` y `prepare` incorporan retrieval semantico de CV y exponen evidencia usada
- notas operativas editables por oportunidad habilitadas en frontend (persistencia via `PATCH`)
- edicion de estado de oportunidad habilitada en frontend con estados V1 y persistencia via `PATCH`
- perfil de persona con preferencias culturales/condiciones de trabajo estructuradas por campo (`enabled`, `selected_values`, `criticality`) y notas abiertas
- en fit cultural, ausencia de evidencia para campos criticos se reporta como `indeterminado` + red flag (sin descarte automatico)
- observabilidad basica agregada en backend para errores/fallbacks de proveedores y retrieval semantico

## Siguiente paso
- agregar pruebas de integracion para aislamiento por `person_id` en analisis/oportunidades
- evaluar soporte de streaming SSE real en frontend usando `/chat/stream`
- agregar pruebas unitarias para transiciones de estado y manejo de `cultural_fit_preferences`

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

Modelos OpenAI recomendados en V1:
- `OPENAI_CHAT_MODEL=gpt-4o-mini`
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`

Variables de busqueda para Adzuna via RapidAPI:
- `RAPIDAPI_KEY`
- `RAPIDAPI_ADZUNA_HOST`

Remotive API en V1:
- uso publico sin API key obligatoria
- `REMOTIVE_API_KEY` se mantiene como variable opcional

Variables Pinecone para indexacion CV:
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- `PINECONE_INDEX_HOST`

Mejoras diferidas (no implementadas en V1 actual):
- extraccion estructurada CV a Markdown para enriquecer jerarquia semantica
- vector de `profile_summary` por persona para matching ejecutivo rapido

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
