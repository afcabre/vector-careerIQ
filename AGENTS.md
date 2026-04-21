# Reglas de trabajo del agente

Antes de actuar:
1. Lee `PROJECT_STATUS.md`
2. Lee `.specify/instructions/SDD-Prompt-Maestro.md`
3. Lee `.specify/instructions/Implementation-Worker-Protocol.md` para ejecucion iterativa de implementacion
4. Usa como documentos normativos principales `.specify/00.Caso-de-Uso-y-Alcance.md`, `.specify/01.Constitucion.md`, `.specify/02.Spec.md` y `.specify/03.Arquitectura-y-Plan.md`

## Estado
Mantén un archivo `PROJECT_STATUS.md` en la raíz del repositorio.

Si no existe, créalo.
Si existe, actualízalo después de avances relevantes.

`PROJECT_STATUS.md` debe resumir el estado vigente del proyecto sin duplicar la documentación normativa.

Si el usuario pide `status` o `\s`, entrega un resumen Markdown con:
- progreso por fase (`█/░`)
- archivos clave (`existente/generado/pendiente`)
- contador Q/A
- bloqueadores
- faltantes generales
- siguiente actividad

Usa `PROJECT_STATUS.md` como fuente principal si existe.
Si está desactualizado, actualízalo antes de responder.

## Reglas
- Sigue el proceso SDD definido en los documentos referenciados.
- Haz una sola pregunta a la vez cuando exista ambigüedad.
- No inventes requisitos.
- Minimiza la duplicación documental.
- Mantén V1 acotado.
- Actualiza `PROJECT_STATUS.md` después de avances relevantes.

## Mecanica Operativa
- El repositorio y la documentacion local son la fuente principal de verdad tecnica.
- `Notion` se usa para plan de implementacion, seguimiento operativo, tareas y estado de ejecucion.
- Un modelo pequeno puede ejecutar slices de implementacion desde este entorno siguiendo el plan vigente.
- La configuracion del entorno y permisos especiales la controla el usuario cuando haga falta.
- En branch experimental o `spike/*`, el avance es iterativo dentro del slice activo pero con checkpoint con el usuario antes de commit o antes de pasar al siguiente slice.
- Los mensajes de commit se redactan en ingles.
- Antes de proponer un commit, el worker debe explicar el slice, indicar que se puede probar y esperar validacion operativa del usuario cuando aplique.

## Regla De Fuente De Verdad
- Si durante la ejecucion aparece un cambio de contrato, alcance o decision tecnica, primero se registra en documentacion local y/o `PROJECT_STATUS.md`.
- Solo despues de actualizar la fuente local de verdad se refleja el cambio en `Notion`.
- No deben existir decisiones nuevas importantes que vivan unicamente en `Notion`.

## Runtime Config V2
- La configuracion de corrida de `Step 2` y `Step 3` para `vacancy_v2` comienza como schema interno con defaults en backend.
- No se expone en administracion del sistema en esta fase inicial.
- Controles operativos como retries, timeout, output token limits y validation retry controls quedan internos hasta validar corridas reales.
