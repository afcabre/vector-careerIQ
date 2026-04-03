# Reglas de trabajo del agente

Antes de actuar:
1. Lee `PROJECT_STATUS.md`
2. Lee `.specify/instructions/SDD-Prompt-Maestro.md`
3. Usa como documentos normativos principales `.specify/00.Caso-de-Uso-y-Alcance.md`, `.specify/01.Constitucion.md`, `.specify/02.Spec.md` y `.specify/03.Arquitectura-y-Plan.md`

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
