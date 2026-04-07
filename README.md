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
- `analyze` separado por accion (`perfil-vacante` y `fit cultural`) con cache por defecto, `forzar recalculo` y historico backend por accion
- `prepare` con seleccion de materiales (`guidance`, `cover_letter`, `experience_summary`), cache por defecto y historico backend por accion
- frontend permite consulta explicita de historico IA persistido por oportunidad (filtro opcional por `action_key`)
- backend persiste trazas de request exacto enviado a `OpenAI`, `Tavily`, `Adzuna` y `Remotive` (sin secretos)
- frontend muestra trazas de request por persona con filtros de destino y oportunidad activa
- importacion manual de vacantes por URL y texto pegado desde frontend
- carga de CV por persona (`/cv`) con un CV activo por perfil y extraccion base de texto
- indexacion vectorial del CV activo habilitada (embeddings OpenAI + upsert/query en Pinecone cuando hay configuracion)
- chunking token-aware con solapamiento aplicado al pipeline de CV para embeddings
- fit cultural en `analyze` con señales publicas trazables por fuente y advertencias de evidencia
- `analyze perfil-vacante` y `prepare` incorporan retrieval semantico de CV y exponen evidencia usada
- notas operativas editables por oportunidad habilitadas en frontend (persistencia via `PATCH`)
- edicion de estado de oportunidad habilitada en frontend con estados V1 y persistencia via `PATCH`
- edicion de perfil base por persona en UI (`full_name`, `target_roles`, `location`, `years_experience`, `skills`) via `PATCH /persons/{person_id}`
- perfil de persona con preferencias culturales/condiciones de trabajo estructuradas por campo (`enabled`, `selected_values`, `criticality`) y notas abiertas
- en fit cultural, ausencia de evidencia para campos criticos se reporta como `indeterminado` + red flag (sin descarte automatico)
- chat frontend usa streaming SSE real sobre `/chat/stream` con render incremental y fallback a `/chat` no-stream
- criterio de producto: el streaming SSE no debe quedar restringido a chat; debe aplicarse tambien a salidas IA de `analyze` y `prepare`
- `analyze` en frontend usa SSE separado por accion: `profile-match/stream` y `cultural-fit/stream` (fallback a no-stream)
- observabilidad basica agregada en backend para errores/fallbacks de proveedores y retrieval semantico

## Siguiente paso
- ampliar pruebas de seguridad para casos edge de prompt injection en flujos streaming
- reforzar cobertura de contratos HTTP sobre degradacion parcial de proveedores
- revisar y cerrar el `skip` del test HTTP ASGI cuando se resuelva limitacion del harness local

## Testing Backend
- ejecutar aislamiento por `person_id` (API+store):
  - `cd apps/backend`
  - `.venv/bin/python -m unittest discover -s tests -p "test_*.py" -q`

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

Variables de rate limiting en login (V1):
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS` (default `300`)
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` (default `5`)
- `LOGIN_RATE_LIMIT_BLOCK_SECONDS` (default `900`)

## Administracion de Prompts (Placeholders)
Sintaxis valida de placeholders en plantillas:
- usar siempre llaves: `{placeholder}`
- no usar parentesis: `(placeholder)`

Flujo `search_jobs_tavily`:
- requerido:
  - `{query}`
- disponibles:
  - `{person_full_name}`
  - `{target_roles}`
  - `{skills}`
  - `{person_location}`
  - `{target_sources}` (inyectado desde lista de fuentes objetivo configuradas)

Flujo `search_culture_tavily`:
- requerido:
  - `{company}`
- disponibles:
  - `{roles}`
  - `{target_roles}`
  - `{person_location}`
  - `{target_sources}` (inyectado desde lista de fuentes objetivo configuradas)

Flujo `system_identity`:
- requerido:
  - `{person_name}`
- disponibles:
  - `{person_location}`
  - `{target_roles}`

Flujo `task_chat`:
- requerido:
  - `{person_context}`
- disponibles:
  - `{cv_context_source}`
  - `{cv_context}`

Flujos `task_analyze_profile_match`, `task_analyze_cultural_fit`, `task_prepare_guidance`, `task_prepare_cover_letter`, `task_prepare_experience_summary`:
- requeridos:
  - `{person_context}`
  - `{opportunity_context}`
- disponibles segun flujo:
  - `{semantic_evidence_context}`
  - `{cultural_evidence_context}`
  - `{confidence_hint}`

Referencia tecnica de esta definicion:
- `apps/backend/app/services/prompt_config_store.py`
- `apps/backend/app/services/search_service.py`
- `apps/backend/app/services/opportunity_ai_service.py`

Mapa rapido endpoint -> flow:
- `POST /api/persons/{person_id}/chat` y `.../chat/stream`: `guardrails_core + system_identity + task_chat`
- `POST /api/persons/{person_id}/opportunities/{opportunity_id}/analyze/profile-match`: `guardrails_core + system_identity + task_analyze_profile_match`
- `POST /api/persons/{person_id}/opportunities/{opportunity_id}/analyze/cultural-fit`: `guardrails_core + system_identity + task_analyze_cultural_fit`
- `POST /api/persons/{person_id}/opportunities/{opportunity_id}/analyze/profile-match/stream`: SSE especifico de `analyze profile-match`
- `POST /api/persons/{person_id}/opportunities/{opportunity_id}/analyze/cultural-fit/stream`: SSE especifico de `analyze cultural-fit`
- `POST /api/persons/{person_id}/opportunities/{opportunity_id}/prepare`: `guardrails_core + system_identity + task_prepare_*` segun `targets`
- `POST /api/persons/{person_id}/opportunities/{opportunity_id}/prepare/stream`: misma composicion de `prepare` con SSE por canal y soporte de `targets` + `force_recompute`
- `GET /api/persons/{person_id}/opportunities/{opportunity_id}/ai-runs`: historico backend por accion IA (`action_key` opcional)
- `GET /api/persons/{person_id}/request-traces`: historial de request payload exacto por destino (`destination`, `opportunity_id`, `run_id`, `limit` opcionales)
- `POST /api/persons/{person_id}/search`: `search_jobs_tavily`
- senales culturales en `analyze_cultural_fit`: `search_culture_tavily`

Detalle normativo completo (endpoint -> composicion -> variables):
- `.specify/03.Arquitectura-y-Plan.md`

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
