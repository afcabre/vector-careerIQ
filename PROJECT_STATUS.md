# Project Status

## Estado
- fase_actual: `Implementacion`
- checkpoint_actual: `prompt layering global + historico IA en UI + paridad SSE con persistencia en chat/analyze/prepare`
- repo_status: `implementacion activa con login, gestion de personas, chat OpenAI, busqueda multi-provider, importacion manual, CV activo y capa semantica basica`
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
- UI permite abrir detalle efimero de resultados de busqueda sin persistir; el guardado sigue como accion separada `Guardar como oportunidad`
- UX de `Abrir detalle` ajustada para mostrar/ocultar detalle inline en la misma tarjeta de resultado (feedback inmediato visible)
- requerimientos normativos actualizados para incluir modulo/seccion de administracion de prompts en V1
- arquitectura actualizada con `Prompt Admin`, `Prompt Config Router/Service` y endpoints admin de configuracion
- backend incorpora `prompt_config_store` con defaults V1, validacion y persistencia `memory/firestore`
- backend expone endpoints admin `GET /api/admin/prompt-configs`, `GET /api/admin/prompt-configs/{flow_key}` y `PATCH /api/admin/prompt-configs/{flow_key}`
- busqueda Tavily de vacantes usa construccion de query configurable via `prompt_configs` (`search_jobs_tavily`)
- fit cultural Tavily usa construccion de query configurable via `prompt_configs` (`search_culture_tavily`)
- pruebas de contrato/admin de prompt configs agregadas en `apps/backend/tests/test_prompt_config_admin.py` (`5 tests` en `OK`)
- frontend incorpora seccion `Administracion de prompts (global V1)` para listar/editar `template_text`, `target_sources` e `is_active`
- frontend consume endpoints admin de prompt configs y aplica validaciones basicas antes de guardar
- build frontend verificado localmente tras integracion UI admin: `npm run build` en `OK`
- prompt configs ampliados para V1 con capas editables: `guardrails_core` (global), `system_identity` (global) y `task_*` por accion (`chat`, `analyze`, `prepare`)
- arquitectura normativa actualizada con matriz operativa de prompts/parametros V1 (destino, objetivo, placeholders, alcance, riesgo y control de consumo)
- arquitectura normativa extendida con trazabilidad endpoint->composicion->variables y reglas de fallback por flow
- backend incorpora store `ai_action_runs` para persistir resultado vigente + historico por accion IA
- backend expone consulta de historico por accion IA: `GET /api/persons/{person_id}/opportunities/{opportunity_id}/ai-runs` con filtro opcional `action_key`
- frontend incorpora consulta explicita de historico IA persistido por oportunidad con filtro opcional por accion y refresco manual
- API agrega acciones separadas de analisis: `POST .../analyze/profile-match` y `POST .../analyze/cultural-fit`
- API `prepare` permite `targets` seleccionables (`guidance_text`, `cover_letter`, `experience_summary`) y `force_recompute`
- comportamiento por defecto de acciones IA: leer ultimo resultado persistido; regenerar solo con `force_recompute=true`
- rate limiting de login implementado con ventana temporal, max intentos y bloqueo temporal configurable por variables seguras
- frontend agrega switch global `Forzar recalculo IA` y botones separados para `Analyze perfil` y `Analyze cultura`
- frontend agrega seleccion de materiales para `prepare seleccionado` y consume respuesta vigente por cache cuando aplica
- capa de prompt en chat/analyze/prepare alineada a composicion: `guardrails_core + system_identity + task_prompt`
- hardening de guardrails implementado: piso no editable, deteccion basica de prompt injection y saneo de salida ante intento de divulgacion de prompt interno
- pruebas de hardening de guardrails agregadas (`apps/backend/tests/test_guardrails.py`)
- flujos streaming ajustados para paridad operativa: lo emitido por `message_delta` coincide con `message_complete` y con contenido persistido en `chat`, `analyze/stream` y `prepare/stream`
- pruebas edge de seguridad en SSE agregadas para prompt leak/prompt injection en `chat`, `analyze` y `prepare` (`apps/backend/tests/test_sse_flows.py`, `apps/backend/tests/test_guardrails.py`)
- pruebas de rate limiting de login agregadas (`apps/backend/tests/test_auth_rate_limit.py`)
- README actualizado con seccion de placeholders validos (`{placeholder}`) y variables disponibles por flujo de prompt
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
- UI permite crear nuevas personas consultadas con baseline V1 (`full_name`, `target_roles`, `location`, `years_experience`, `skills`) consumiendo `POST /api/persons`
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
- pruebas de contratos API para errores (`422` status invalido, `409` transicion invalida) y aislamiento por `person_id` en `artifacts`/`analyze_stream`/`prepare_stream` agregadas en `apps/backend/tests/test_api_error_and_fallbacks.py`
- pruebas de fallback para proveedores de busqueda y fallback LLM (`analyze`/`prepare`) agregadas en `apps/backend/tests/test_api_error_and_fallbacks.py`
- cobertura de contratos API reforzada para degradacion parcial y fallback controlado en `search`, incluyendo warnings esperados, dedupe y limite de resultados en `apps/backend/tests/test_api_error_and_fallbacks.py`
- cobertura de contratos API reforzada para fallback controlado en endpoints `analyze_profile_match` y `prepare` cuando LLM cae en fallback en `apps/backend/tests/test_api_error_and_fallbacks.py`
- prueba SSE adicional de evento `error` en `prepare/stream` agregada en `apps/backend/tests/test_sse_flows.py`
- suite backend actualizada y verificada localmente: `19 tests` en `OK`
- prueba de paridad minima `memory` vs `firestore` mocked para stores de oportunidades/artefactos agregada en `apps/backend/tests/test_firestore_mock_parity.py`
- prueba HTTP de aislamiento por `person_id` en endpoint de artifacts agregada en `apps/backend/tests/test_http_artifacts_isolation.py` (marcada `skip` por bloqueo del harness ASGI en entorno local)
- suite backend actualizada y verificada localmente: `21 tests` en `OK` (`skipped=1`)
- pruebas adicionales de contratos de error para oportunidad inexistente en `analyze`/`prepare` y sus endpoints SSE agregadas en `apps/backend/tests/test_api_error_and_fallbacks.py`
- suite backend actualizada y verificada localmente: `23 tests` en `OK` (`skipped=1`)
- pruebas de contratos de validacion para payloads incompletos/invalidos en modelos API agregadas en `apps/backend/tests/test_request_validation_contracts.py`
- suite backend actualizada y verificada localmente: `28 tests` en `OK` (`skipped=1`)
- hardening de degradacion parcial en busqueda agregado en `apps/backend/tests/test_api_error_and_fallbacks.py` (fallo de un proveedor con resultados parciales de otros y warnings por proveedores no configurados)
- contrato API agregado para `search` con `person_id` inexistente (`404`) en `apps/backend/tests/test_api_error_and_fallbacks.py`
- contrato API agregado para validar que `search` no persiste oportunidades y solo `from-search` las crea en `apps/backend/tests/test_api_error_and_fallbacks.py`
- suite backend actualizada y verificada localmente: `31 tests` en `OK` (`skipped=1`)
- verificacion incremental backend ejecutada localmente: `tests/test_api_error_and_fallbacks.py` en `OK` (`12 tests`)
- build frontend verificado localmente tras ajuste UI: `npm run build` en `OK`
- decision operativa registrada en memoria: mantener `skip` temporal del test HTTP ASGI y criterio de salida definido para reactivarlo
- diagnostico tecnico registrado: bloqueo reproducido en inicializacion de portal AnyIO de `TestClient` (antes del procesamiento de request)
- bloqueo ASGI validado tambien en app FastAPI minima (`/ping`), confirmando limitacion del harness local y no regresion del codigo de negocio
- intento de mitigacion local ejecutado: downgrade de `anyio` de `4.13.0` a `4.4.0` en `.venv`; el bloqueo de `TestClient` persiste
- suite backend revalidada tras hardening SSE: `51 tests` en `OK` (`skipped=1`)
- suite backend revalidada tras refuerzo de contratos HTTP fallback/degradacion: `55 tests` en `OK` (`skipped=1`)

## Mejoras Identificadas (Diferidas)
- extraccion estructurada de CV a Markdown (PyMuPDF/LlamaIndex) para mejorar jerarquia semantica
- vector `profile_summary` por persona (`type=profile_summary`) para match ejecutivo de alto nivel

## Bloqueadores
- no hay bloqueadores funcionales de alcance V1
- limitacion tecnica local: clientes ASGI de prueba (`TestClient`/`ASGITransport`) se bloquean en requests; se mantiene cobertura equivalente por handler/store y un test HTTP en `skip` hasta resolver harness
- riesgo operativo local: entorno de desarrollo modificado para diagnostico (`anyio` downgraded en `.venv`) sin solucion aun para el bloqueo ASGI

## Siguiente Actividad
- investigar y cerrar el bloqueo del harness ASGI para reactivar el test HTTP hoy marcado `skip`
- evaluar mejora futura de saneo incremental por deltas SSE sin romper paridad ni latencia
