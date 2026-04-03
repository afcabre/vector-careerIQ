# Project Status

## Estado
- fase_actual: `Implementacion`
- checkpoint_actual: `conversacion persistente por person_id en progreso`
- repo_status: `implementacion activa con login, sesion backend, seleccion de persona y chat persistente`
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

## Bloqueadores
- no hay bloqueadores funcionales para comenzar implementacion
- falta materializar configuracion local minima antes de desarrollar el primer flujo vertical

## Siguiente Actividad
- instalar dependencias y validar arranque local
- validar modo `firestore` con credenciales reales de entorno
- estabilizar endpoint `/chat/stream` con proveedor LLM real
- continuar con busqueda y oportunidades en contexto conversacional
