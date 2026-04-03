# Project Status

## Estado
- fase_actual: `Implementacion`
- checkpoint_actual: `flujo vertical base con persistencia conmutable`
- repo_status: `implementacion activa con login, sesion backend y seleccion de persona consultada`
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
- sesion backend aun en memoria temporal

## Bloqueadores
- no hay bloqueadores funcionales para comenzar implementacion
- falta materializar configuracion local minima antes de desarrollar el primer flujo vertical

## Siguiente Actividad
- instalar dependencias y validar arranque local
- validar modo `firestore` con credenciales reales de entorno
- decidir y aplicar estrategia de sesion persistente para despliegue
- continuar con capa conversacional persistente por `person_id`
