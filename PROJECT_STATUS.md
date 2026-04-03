# Project Status

## Estado
- fase_actual: `Implementacion`
- checkpoint_actual: `busqueda multi-provider activa (Adzuna RapidAPI + Remotive + Tavily)`
- repo_status: `implementacion activa con login, chat OpenAI, busqueda multi-provider, importacion manual, CV activo por persona y ciclo base de postulacion`
- ultima_actualizacion: `2026-04-03`

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

## Bloqueadores
- no hay bloqueadores funcionales de alcance V1
- no hay bloqueadores tecnicos activos reportados en este checkpoint

## Siguiente Actividad
- ampliar analisis de fit cultural con trazabilidad de evidencia por fuente
- preparar integracion de indexacion vectorial del CV en Pinecone
- incorporar embeddings reales con `text-embedding-3-small` sobre CV activo
