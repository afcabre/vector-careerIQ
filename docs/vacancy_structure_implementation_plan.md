# Vacancy Structure V2 Implementation Plan

## Proposito
Traducir el contrato acordado para Paso 2 y Paso 3 a un plan de implementacion ejecutable, incremental y seguro sobre el baseline estable actual.

## Restriccion principal
- no romper el extractor legacy actual ni el flujo analitico estable mientras se implementa `v2`
- `v2` debe entrar en paralelo, con persistencia separada y activacion controlada

## Supuestos operativos
- el `raw_text` de vacante ya existe en `opportunities.snapshot_raw_text`
- `vacancy_profile` legacy sigue vivo mientras `v2` madura
- Paso 2 y Paso 3 se implementan primero como artefactos paralelos
- la integracion con `analyze_profile_match` ocurre solo al final, despues de validar calidad

## Artefactos objetivo
### Paso 2
```json
{
  "contract_version": "vacancy_blocks.v2",
  "vacancy_id": "VAL-123",
  "generated_at": "2026-04-21T10:30:00-05:00",
  "vacancy_blocks": {
    "work_conditions": [],
    "responsibilities": [],
    "required_criteria": [],
    "desirable_criteria": [],
    "benefits": [],
    "about_the_company": [],
    "unclassified": []
  },
  "warnings": [],
  "coverage_notes": []
}
```

### Paso 3
```json
{
  "contract_version": "vacancy_dimensions.v2",
  "vacancy_id": "VAL-123",
  "generated_at": "2026-04-21T10:31:05-05:00",
  "vacancy_dimensions": {
    "work_conditions": {
      "salary": {
        "raw_text": ""
      },
      "modality": {
        "value": "",
        "raw_text": ""
      },
      "location": {
        "places": [],
        "raw_text": ""
      },
      "contract_type": {
        "value": "",
        "raw_text": ""
      },
      "other_conditions": [
        {
          "raw_text": ""
        }
      ]
    },
    "responsibilities": [
      {
        "raw_text": ""
      }
    ],
    "required_criteria": [
      {
        "raw_text": ""
      }
    ],
    "desirable_criteria": [
      {
        "raw_text": ""
      }
    ],
    "benefits": [
      {
        "raw_text": ""
      }
    ],
    "about_the_company": [
      {
        "raw_text": ""
      }
    ]
  }
}
```

## Decision de persistencia recomendada
No reutilizar `vacancy_profile` como contenedor final de `v2`.

Recomendacion:
- mantener `vacancy_profile` y `vacancy_profile_status` para el legado
- agregar en `OpportunityRecord`:
  - `vacancy_blocks_artifact`
  - `vacancy_blocks_status`
  - `vacancy_blocks_generated_at`
  - `vacancy_dimensions_artifact`
  - `vacancy_dimensions_status`
  - `vacancy_dimensions_generated_at`

Razon:
- evita contaminar el baseline estable
- permite comparar `legacy` vs `vacancy_blocks` vs `vacancy_dimensions`
- permite rollout controlado sin migracion destructiva

Estados sugeridos:
- `none`
- `draft`
- `approved`
- `error`

## Orden de implementacion
1. Persistencia paralela y contratos
2. Servicio Paso 2
3. Servicio Paso 3
4. Endpoints y SSE
5. UI de inspeccion y aprobacion
6. Tests de contrato y regresion
7. Integracion opcional con analisis

## Fase 1. Base de datos y contratos
### Objetivo
Agregar soporte de persistencia paralela para `vacancy_blocks` y `vacancy_dimensions` sin tocar el comportamiento legacy.

### Cambios
- extender `OpportunityRecord` en `apps/backend/app/services/opportunity_store.py`
- extender serializacion Pydantic en `apps/backend/app/api/opportunities.py`
- exponer los nuevos artefactos en API

### Archivos
- `apps/backend/app/services/opportunity_store.py`
- `apps/backend/app/api/opportunities.py`
- `apps/frontend/src/api.ts`

### Entregable
- opportunity puede almacenar ambos artefactos sin afectar `vacancy_profile`

### Criterio de aceptacion
- crear/listar/consultar oportunidad sigue funcionando igual
- nuevos campos aparecen vacios por defecto
- no hay regresion en endpoints legacy

## Fase 2. Contratos ejecutables y validadores
### Objetivo
Formalizar normalizacion y defaults de `vacancy_blocks` y `vacancy_dimensions`.

### Cambios
- crear modulo `vacancy_blocks_contract.py`
- crear modulo `vacancy_dimensions_contract.py`
- incluir helpers:
  - `empty_*`
  - `normalize_*`
  - `is_*`

### Archivos
- `apps/backend/app/services/vacancy_blocks_contract.py`
- `apps/backend/app/services/vacancy_dimensions_contract.py`
- tests dedicados

### Criterio de aceptacion
- contratos devuelven shape fijo
- defaults acordados:
  - strings `""`
  - numericos/booleanos `null`
  - arrays `[]`

## Fase 3. Servicio de Paso 2
### Objetivo
Implementar segmentacion contextual sobre `raw_text`.

### Comportamiento
- input: oportunidad con `snapshot_raw_text`
- output: artefacto `vacancy_blocks.v2`
- prompt enfocado en:
  - clasificar
  - limpiar
  - fragmentar fino
  - no resumir
  - no atomizar

### Cambios
- crear servicio `vacancy_blocks_service.py`
- nuevo flow de prompt:
  - `task_vacancy_blocks_extract`
- no reemplaza `task_vacancy_profile_extract`

### Archivos
- `apps/backend/app/services/vacancy_blocks_service.py`
- `apps/backend/app/services/prompt_config_store.py`
- tests dedicados

### Criterio de aceptacion
- genera `vacancy_blocks` con listas de strings
- genera `warnings` y `coverage_notes` globales
- no inventa claves fuera del set fijo
- incluye `about_the_company` como bloque explicito para contexto de empresa

## Fase 4. Servicio de Paso 3
### Objetivo
Tomar Paso 2 y producir la estructura atomizada final.

### Comportamiento
- input: artefacto Paso 2 aprobado o vigente
- output: artefacto `vacancy_dimensions.v2`
- separar responsabilidades:
  - `S3` atomizacion minima homogena
  - `S3.1` normalizacion salarial
  - `S3.9` enriquecimiento deterministico previo a retrieval si se aprueba

### Cambios
- crear servicio `vacancy_dimensions_service.py`
- nuevo flow de prompt:
  - `task_vacancy_dimensions_extract`
- excluir en `S3`:
  - `semantic_queries`
  - `category`
  - ids por item

### Archivos
- `apps/backend/app/services/vacancy_dimensions_service.py`
- `apps/backend/app/services/prompt_config_store.py`
- tests dedicados

### Criterio de aceptacion
- produce `vacancy_dimensions`
- `work_conditions` usa el set reducido aprobado
- `about_the_company` sobrevive en `S3`
- no arrastra `vacancy_blocks` dentro del artefacto final

## TODO de revision posterior al gate
Estos puntos no cambian el contrato ejecutable actual, pero quedan documentados como backlog de diseno antes de una siguiente iteracion de contrato:

- evaluar una futura variante `vacancy_blocks.v2` con naming alineado a Step 3 sin renombrar la raiz de Paso 2 a `vacancy_dimensions`
- usar en Paso 2 `required_criteria` / `desirable_criteria` como naming objetivo
- incorporar `about_the_company` en Paso 2 para capturar senales de empresa y contexto corporativo
- revisar simplificacion del contrato de Paso 3 para reducir ruido y redundancia en items atomicos
- revisar si la generacion de `semantic_queries` debe permanecer en Paso 3 o moverse a una fase posterior dedicada

## Plan explicito propuesto para iteracion siguiente
Objetivo:
- simplificar la pipeline para que cada paso haga una sola cosa
- eliminar de Paso 3 los campos que hoy introducen ruido sin aportar valor observable
- volver explicitas las transformaciones y validaciones por paso antes de tocar codigo

Regla operativa:
- no introducir heuristicas silenciosas ni validaciones nuevas no documentadas
- cada paso debe declarar antes de implementarse: objetivo, input, output, transformaciones permitidas, transformaciones prohibidas, validaciones explicitas y criterio de error

### S2. Segmentacion contextual
Objetivo:
- clasificar el `raw_text` de vacante en bloques contextuales amplios y consultables

Output esperado:
- artefacto `vacancy_blocks`
- listas de strings limpias por clave
- `warnings` y `coverage_notes` globales

Direccion propuesta:
- mantener `work_conditions`, `responsibilities`, `benefits`, `about_the_company` y `unclassified`
- usar `required_criteria` / `desirable_criteria` como naming objetivo de S2

Transformaciones prohibidas:
- no resumir
- no atomizar
- no generar `semantic_queries`
- no asignar `id`
- no asignar `category`

### S3. Atomizacion minima
Objetivo:
- convertir los bloques de S2 en items atomicos utilizables sin agregar semantica extra

Output esperado:
- `work_conditions` reducido a `salary`, `modality`, `location`, `contract_type`, `other_conditions`
- listas atomicas homogeneas para responsabilidades, criterios requeridos, criterios deseables, beneficios y `about_the_company`
- cada item con `raw_text` como unica carga textual
- `salary` conserva solo `raw_text` en este paso

Direccion propuesta:
- quitar `id`
- quitar `category`
- quitar campo resumido por item (`task`, `requirement`, `benefit`)
- quitar `semantic_queries` de este paso

Transformaciones prohibidas:
- no generar taxonomias
- no resumir ni parafrasear por defecto
- no intentar disenar consultas de retrieval

### S3.1. Normalizacion de salario
Objetivo:
- resolver salario como subproblema separado por su estructura diferente al resto del artefacto

Output esperado:
- artefacto `vacancy_salary_normalization.v1`
- objeto `salary` con `min`, `max`, `currency`, `period`, `raw_text`

Regla:
- este paso no reclasifica ni reatomiza la vacante
- este paso no genera queries
- este paso solo normaliza salario a partir de senales de `work_conditions`
- este paso toma como input `vacancy_dimensions.v2.work_conditions.salary.raw_text`

### S3.9. Enriquecimiento deterministico
Objetivo:
- asignar referencias tecnicas estables y operativas a cada item atomico antes de `S4`

Output esperado:
- artefacto `vacancy_dimensions_enriched.v1`
- cada item atomico enriquecido con:
  - `item_id`
  - `item_index`
  - `group_code`

Regla:
- este paso es programatico y no usa LLM
- `item_id` representa un fingerprint estable del contenido
- `item_index` representa la posicion del item dentro de su lista padre
- `group_code` representa el grupo corto del item (`resp`, `req`, `des`, `ben`, `comp`, `cond`)
- `item_id` usa `sha256` truncado a `10` hex sobre `vacancy_id|group_code|normalized_raw_text`
- `normalized_raw_text` se construye con `trim`, minusculas y colapso de espacios internos
- este paso no modifica `raw_text`
- este paso no reclasifica ni resume
- este paso no genera queries

### S4. Generacion de queries de retrieval
Objetivo:
- generar consultas semanticas por item atomizado ya estable

Output esperado:
- artefacto separado de queries por item y por grupo padre
- una o mas queries por item segun regla que se apruebe

Regla:
- este paso no reclasifica ni reatomiza la vacante
- toma items estabilizados de `S3` y, si aplica, enriquecidos por `S3.9`
- input operativo preferido: `vacancy_dimensions_enriched.v1`
- input complementario opcional: `vacancy_salary_normalization.v1`
- formula queries orientadas a recuperacion de evidencia
- este paso puede devolver `queries: []` cuando no exista una formulacion util
- mientras no exista schema runtime dedicado para `S4`, la implementacion inicial puede reutilizar `step3.llm_temperature`
- decision operativa vigente:
  - mantener por ahora el control dentro del prompt
  - no introducir aun filtro programatico por tipologia
  - observar primero el comportamiento real de `S4` sobre todas las tipologias habilitadas en el contrato

### TODO posterior a observacion de S4
- si `S4` genera ruido en corridas reales, evaluar control administrable de tipologias dentro del prompt
- no mover esa mejora a logica programatica mientras no exista evidencia de necesidad
- si se adopta despues, empezar por `responsibilities`, `required_criteria` y `desirable_criteria`

### S5. Retrieval de evidencia
Objetivo:
- ejecutar busqueda semantica en Pinecone por item/query y persistir evidencia recuperada

Output esperado:
- matches recuperados
- score
- fragmentos de CV
- metadata de origen

Regla:
- este paso no concluye alineacion final
- solo recupera y ordena evidencia
- la interpretacion de scores queda separada del retrieval mismo
- implementacion actual recomendada:
  - paso programatico, sin LLM
  - reutilizar `query_cv_matches`
  - exigir CV activo e indexado antes de correr
  - tomar `top_k_semantic_per_criterion` desde Runtime IA
  - permitir evidencia vacia por item sin tratarlo como error del paso

### Criterio operativo acordado para clasificacion en S6
- `score >= 0.75`: evidencia fuerte
- `score >= 0.45 y < 0.75`: evidencia util
- `score >= 0.30 y < 0.45`: evidencia debil o para revision
- `score < 0.30`: probable ruido

Nota:
- estos umbrales no filtran `S5`
- `S5` persiste toda la evidencia recuperada
- `S6` clasifica y decide que entra a analisis principal
- lo descartado no se borra; se conserva con razon explicita
- Runtime IA debe exponer estos umbrales para ajuste operativo

### S6. Analisis y presentacion
Objetivo:
- consolidar evidencia de `S5` de forma deterministica antes de cualquier presentacion final

Output esperado:
- `accepted_matches`
- `discarded_matches`
- `best_evidence`
- `item_status`
- score consolidado por item

Regla:
- sin LLM en esta primera iteracion
- deduplicar por fragmento recuperado, no por query
- conservar trazabilidad de queries que dispararon cada match
- usar los umbrales configurados en Runtime IA para clasificacion
- implementacion actual:
  - artefacto separado `vacancy_evidence_analysis.v1`
  - input: `vacancy_retrieval_evidence.v1`
  - output: `accepted_matches`, `discarded_matches`, `best_evidence`, `item_status`
  - `best_evidence` queda como lista corta y no como item unico
  - `snippet` se entiende como fragmento recuperado del retrieval, no como texto completo del CV

### S7. Analisis y presentacion
Objetivo:
- derivar desde `S6` un resumen estructurado complementario para facilitar el consumo posterior de `S8`

Output esperado:
- conteos globales por bucket
- conteos por grupo primario
- listas compactas de `strengths`, `gaps` y `review_items`

Regla:
- `S7` no reemplaza `S6`
- `S7` debe resumir solo `responsibilities`, `required_criteria` y `desirable_criteria`
- `S8` consumira `S7` como resumen y `S6` como respaldo detallado
- implementacion actual:
  - artefacto separado `vacancy_alignment_summary.v1`
  - input: `vacancy_evidence_analysis.v1`
  - output: `overall`, `groups`, `strengths`, `gaps`, `review_items`

## Orden recomendado de ejecucion inmediata
1. cerrar por documento el contrato minimo de S3
2. decidir que subclaves de `work_conditions` sobreviven en S3
3. decidir naming final de criterios en S2
4. cerrar forma canonica de `about_the_company` en el contrato objetivo de S2
5. documentar contrato e interfaz de `S3.1` para salario
6. documentar contrato e interfaz de `S3.9` para referencias tecnicas
7. documentar contrato e interfaz de S4
8. documentar interfaz de S5 y criterio de lectura de scores
9. solo despues implementar cambios de codigo

## Fase 5. Endpoints backend
### Objetivo
Exponer la nueva pipeline sin romper la actual.

### Endpoints recomendados
- `POST /persons/{person_id}/opportunities/{opportunity_id}/vacancy-blocks/recompute`
- `POST /persons/{person_id}/opportunities/{opportunity_id}/vacancy-blocks/recompute/stream`
- `POST /persons/{person_id}/opportunities/{opportunity_id}/vacancy-dimensions/recompute`
- `POST /persons/{person_id}/opportunities/{opportunity_id}/vacancy-dimensions/recompute/stream`
- `PATCH /persons/{person_id}/opportunities/{opportunity_id}`
  - permitir guardar/aprobar artefactos Paso 2 y Paso 3

### Criterio de aceptacion
- se pueden regenerar Paso 2 y Paso 3 por separado
- Paso 3 falla controladamente si Paso 2 no existe o es invalido
- SSE reporta etapas claras

## Fase 6. UI de Vacantes
### Objetivo
Inspeccionar y aprobar Paso 2 y Paso 3 desde frontend.

### Comportamiento recomendado
- mantener el panel legacy actual sin romperlo
- agregar panel experimental `Vacancy V2`
- subpaneles:
  - `Vacancy Blocks`
  - `Vacancy Dimensions`
- mostrar:
  - estado
  - `generated_at`
  - JSON
  - modo lectura
  - aprobacion manual

### Archivos
- `apps/frontend/src/App.tsx`
- `apps/frontend/src/api.ts`
- `apps/frontend/src/styles.css`

### Criterio de aceptacion
- el usuario puede recalcular Paso 2
- luego recalcular Paso 3
- luego revisar ambos artefactos sin tocar el legacy

## Fase 7. Testing
### Backend
- contratos de Paso 2
- contratos de Paso 3
- persistencia de nuevos campos
- endpoints de recomputo
- SSE de Paso 2
- SSE de Paso 3
- regresion de endpoints legacy

### Frontend
- parsing de nuevos artefactos
- rendering de arrays vacios
- estados de recálculo
- fallback si un artefacto no existe

## Fase 8. Integracion con analisis
### Objetivo
Usar Paso 3 como nueva fuente de verdad analitica.

### Regla
- no empezar esta fase hasta validar calidad de Paso 2 y Paso 3 con datos reales

### Estrategia recomendada
- introducir feature flag backend:
  - `USE_VACANCY_STRUCTURE_STEP3_FOR_ANALYSIS`
- adaptar `opportunity_ai_service.py`
- retirar dependencias de `JobCriteriaMapper` solo cuando la nueva lectura sea estable

### Criterio de aceptacion
- el analisis puede correr sobre Paso 3 bajo flag
- el baseline legacy sigue disponible como fallback

## Slices ideales para modelo pequeno
### Slice 1
Agregar campos de persistencia paralela en backend y frontend.

Write scope:
- `apps/backend/app/services/opportunity_store.py`
- `apps/backend/app/api/opportunities.py`
- `apps/frontend/src/api.ts`

### Slice 2
Crear contratos ejecutables y tests unitarios de Paso 2 y Paso 3.

Write scope:
- `apps/backend/app/services/vacancy_blocks_contract.py`
- `apps/backend/app/services/vacancy_dimensions_contract.py`
- `apps/backend/tests/test_vacancy_blocks_contract.py`
- `apps/backend/tests/test_vacancy_dimensions_contract.py`

### Slice 3
Crear `vacancy_blocks_service.py` y su test.

Write scope:
- `apps/backend/app/services/vacancy_blocks_service.py`
- `apps/backend/tests/test_vacancy_blocks_service.py`
- `apps/backend/app/services/prompt_config_store.py`

### Slice 4
Crear `vacancy_dimensions_service.py` y su test.

Write scope:
- `apps/backend/app/services/vacancy_dimensions_service.py`
- `apps/backend/tests/test_vacancy_dimensions_service.py`
- `apps/backend/app/services/prompt_config_store.py`

### Slice 5
Crear endpoints backend de recomputo y SSE.

Write scope:
- `apps/backend/app/api/opportunities.py`
- tests asociados

### Slice 6
Agregar panel experimental frontend.

Write scope:
- `apps/frontend/src/App.tsx`
- `apps/frontend/src/styles.css`

### Slice 7
Feature flag de integracion analitica.

Write scope:
- `apps/backend/app/services/opportunity_ai_service.py`
- tests de regresion

## Riesgos a controlar
- mezclar `v2` con el legacy demasiado pronto
- pedir demasiado a `4o-mini` en Paso 2 o Paso 3
- sobrecargar `category`
- generar `semantic_queries` redundantes o demasiado largas
- confundir condiciones operativas con competencias

## Recomendaciones de prompting para modelo pequeno
- un prompt por fase, no multiproposito
- ejemplos positivos y negativos cortos
- forzar claves exactas
- limitar a una `semantic_queries[0]` por item al inicio
- prohibir explicitamente:
  - resumir
  - inventar claves
  - fusionar items no equivalentes

## Lo que aun queda fuera
- historial formal de artefactos con `artifact_id`
- aprobacion multi-version
- migracion de oportunidades ya estructuradas al nuevo contrato
- reemplazo final del legado en analisis
