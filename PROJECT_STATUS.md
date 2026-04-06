# Project Status

## Estado
- fase_actual: `Implementacion`
- checkpoint_actual: `SSE extendido a chat, analyze y prepare con fallback no-stream`
- repo_status: `implementacion activa con login, chat OpenAI, busqueda multi-provider, importacion manual, CV activo y capa semantica basica`
- ultima_actualizacion: `2026-04-06`

## Progreso Por Fase
- `Fase 0`: completada
- `Fase 1`: completada
- `Fase 2`: completada
- `Fase 3`: completada
- `Fase 4`: completada
- `Reorganizacion documental`: completada
- `Implementacion`: iniciada

## Artefactos Normativos
- `.specify/00.Caso-de-Uso-y-Alcance.md`
- `.specify/01.Constitucion.md`
- `.specify/02.Spec.md`
- `.specify/03.Arquitectura-y-Plan.md`

## Estado Tecnico
- scaffold base existente en `apps/frontend` y `apps/backend`
- documentos normativos activos en `.specify/`
- contratos minimos de `auth` y `persons` implementados en backend
- flujo vertical inicial implementado en modo local: login tutor + seleccion de persona consultada
- `persons` y validacion de operador soportan backend `memory` o `firestore`
- sesion backend soporta backend `memory` o `firestore`
- conversacion por `person_id` implementada en backend y conectada en frontend
- `/chat` y `/chat/stream` integrados con OpenAI (fallback seguro si falta key/dependencia)
- `/search` implementado con Tavily (fallback seguro)
- guardado explicito desde busqueda a oportunidades persistidas por `person_id`
- `analyze` por oportunidad implementado
- `prepare` implementado con artefactos persistidos (`cover_letter`, `experience_summary`)
- importacion manual de vacantes por `URL` y por `texto pegado` habilitada en frontend
- toolchain frontend local operativo (`npm install` + `npm run build` exitoso)
- carga de CV por persona implementada (`POST /api/persons/{person_id}/cv`)
- consulta de CV activo por persona implementada (`GET /api/persons/{person_id}/cv/active`)
- regla V1 de un solo CV activo por persona aplicada en store (`memory` y `firestore`)
- extraccion base de texto de CV habilitada con soporte PDF/texto y preview en UI
- configuracion OpenAI alineada para V1: `gpt-4o-mini` (inferencia) y `text-embedding-3-small` (embeddings)
- decision de proveedor: `Adzuna` se integrara via `RapidAPI` (`RAPIDAPI_KEY` + `RAPIDAPI_ADZUNA_HOST`)
- busqueda multi-provider implementada en backend (`Adzuna via RapidAPI`, `Remotive`, `Tavily`)
- degradacion parcial por proveedor implementada con warnings por fuente
- deduplicacion de resultados implementada con clave principal por `source_url`
- `Remotive API` operando en modo publico V1; `REMOTIVE_API_KEY` queda opcional
- indexacion vectorial de CV activo implementada con `text-embedding-3-small` y upsert a Pinecone
- estado de indexacion CV expuesto en API/UI (`vector_index_status`, `vector_chunks_indexed`)
- chat enriquecido con retrieval semantico de Pinecone con fallback a preview de CV
- chunking CV mejorado a estrategia token-aware con solapamiento (~700 tokens, overlap ~12%)
- recuperacion semantica ajustada a `top_k` alto para analisis mas exhaustivo en namespace por persona
- `analyze` ampliado con fit cultural y evidencia publica por fuente (`Tavily`)
- respuesta de analisis expone `cultural_confidence`, `cultural_warnings` y `cultural_signals`
- UI muestra trazabilidad de señales culturales y advertencias de evidencia debil
- `analyze` y `prepare` reutilizan retrieval semantico CV desde Pinecone con fallback a preview
- API/UI exponen evidencia semantica utilizada (`semantic_evidence`) para trazabilidad del resultado
- UI permite editar y guardar notas operativas por oportunidad desde el detalle activo
- UI permite editar y guardar estado de oportunidad con estados V1 (`detected`, `analyzed`, `prioritized`, `application_prepared`, `applied`, `discarded`)
- UI permite editar perfil base por persona (`full_name`, `target_roles`, `location`, `years_experience`, `skills`) desde `Contexto activo`
- perfil de persona permite configurar preferencias culturales/condiciones de trabajo por campo (`enabled`, `selected_values`, `criticality`) y notas abiertas
- el analisis cultural trata falta de evidencia en campos criticos como `indeterminado` con red flag (no exclusion automatica)
- backend incorpora logs basicos de fallos por proveedor y fallback semantico (`search`, `cv_vector`, `opportunity_ai`)
- pruebas de integracion API+store para aislamiento por `person_id` en oportunidades y `analyze` agregadas en `apps/backend/tests/test_person_isolation.py`
- pruebas unitarias de transiciones de estado (`is_valid_transition`, `update_opportunity`) agregadas en `apps/backend/tests/test_opportunity_transitions.py`
- pruebas unitarias de saneamiento/normalizacion de `cultural_fit_preferences` agregadas en `apps/backend/tests/test_cultural_fit_validation.py`
- frontend envia chat por `/chat/stream` con render incremental de deltas SSE y fallback automatico a `/chat` si streaming no disponible
- criterio de arquitectura confirmado: el streaming SSE debe cubrir todas las salidas IA relevantes (`chat`, `analyze`, `prepare`), no solo conversacion
- backend expone `POST /api/persons/{person_id}/opportunities/{opportunity_id}/analyze/stream` con eventos SSE y payload final estructurado
- backend expone `POST /api/persons/{person_id}/opportunities/{opportunity_id}/prepare/stream` con eventos SSE por canal (`guidance_text`, `cover_letter`, `experience_summary`)
- frontend consume SSE de `analyze/prepare` con render incremental y fallback automatico a endpoints no-stream
- suite backend verificada localmente: `8 tests` en `OK`
- build frontend verificado localmente: `npm run build` en `OK`
- pruebas de integracion de `prepare` y persistencia/reemplazo de artefactos agregadas en `apps/backend/tests/test_prepare_artifacts.py`
- pruebas de flujo SSE para `chat`, `analyze` y `prepare` agregadas en `apps/backend/tests/test_sse_flows.py`
- suite backend actualizada y verificada localmente: `12 tests` en `OK`

## Mejoras Identificadas (Diferidas)
- extraccion estructurada de CV a Markdown (PyMuPDF/LlamaIndex) para mejorar jerarquia semantica
- vector `profile_summary` por persona (`type=profile_summary`) para match ejecutivo de alto nivel

## Bloqueadores
- no hay bloqueadores funcionales de alcance V1
- no hay bloqueadores tecnicos activos reportados en este checkpoint

## Siguiente Actividad
- ampliar pruebas de contratos API para errores y fallback (proveedores externos y LLM)
- reforzar cobertura de aislamiento por `person_id` en artefactos y endpoints de streaming
