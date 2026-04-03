# Project Status

## Estado
- fase_actual: `Implementacion`
- checkpoint_actual: `importacion manual de vacantes por URL/texto desde UI`
- repo_status: `implementacion activa con login, chat OpenAI, busqueda, importacion manual y ciclo base de postulacion`
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

## Bloqueadores
- no hay bloqueadores funcionales para comenzar implementacion
- falta materializar configuracion local minima antes de desarrollar el primer flujo vertical

## Siguiente Actividad
- completar ingesta de CV (carga, extraccion base y un CV activo por persona)
- incorporar `Adzuna` y `Remotive API` en capa multi-provider de busqueda
- ampliar analisis de fit cultural con trazabilidad de evidencia por fuente
