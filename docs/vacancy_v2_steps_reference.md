# Vacancy V2 Steps Reference

## Proposito
Consolidar en un solo documento la definicion operativa de los Steps de `vacancy_v2`, su objetivo, input, output, tipo de ejecucion y la llave de prompt asociada cuando aplica.

## Alcance
- este documento consolida `S1` a `S8`
- `S2` a `S8` ya estaban documentados de forma distribuida
- `S1` se incluye aqui como precondicion operativa para cerrar la lectura end-to-end
- cuando exista conflicto, prevalecen:
  - `docs/vacancy_structure_implementation_plan.md`
  - `docs/vacancy_structure_contract_v2.md`
  - contratos ejecutables en `apps/backend/app/services`

## Resumen ejecutivo
- `vacancy_v2` arranca formalmente en `S2`
- `S1` no es hoy un artefacto formal de `vacancy_v2`; es la etapa previa de captura del `snapshot_raw_text`
- los Steps con prompt configurable son: `S2`, `S3`, `S3.1`, `S4`, `S8`
- los Steps deterministas, sin prompt propio, son: `S3.9`, `S5`, `S6`, `S7`

## Mapa rapido
| Step | Nombre | Tipo | Output principal | Prompt key |
| --- | --- | --- | --- | --- |
| `S1` | Pre-ingesta de vacante | captura/persistencia | `snapshot_raw_text` en oportunidad | `ninguna` |
| `S2` | Segmentacion contextual | `LLM-first` | `vacancy_blocks.v2` | `task_vacancy_blocks_extract` |
| `S3` | Atomizacion minima | `LLM-first` | `vacancy_dimensions.v2` | `task_vacancy_dimensions_extract` |
| `S3.1` | Normalizacion salarial | `LLM-first` | `vacancy_salary_normalization.v1` | `task_vacancy_salary_normalize` |
| `S3.9` | Enriquecimiento deterministico | programatico | `vacancy_dimensions_enriched.v1` | `ninguna` |
| `S4` | Generacion de queries de retrieval | `LLM-first` | `vacancy_retrieval_queries.v1` | `task_vacancy_retrieval_queries_extract` |
| `S5` | Retrieval de evidencia | programatico | `vacancy_retrieval_evidence.v1` | `ninguna` |
| `S6` | Analisis de evidencia | programatico | `vacancy_evidence_analysis.v1` | `ninguna` |
| `S7` | Resumen de alineacion | programatico | `vacancy_alignment_summary.v1` | `ninguna` |
| `S8` | Reporte final grounded | `LLM-first` | `vacancy_alignment_report.v1` | `task_vacancy_alignment_report` |

## S1. Pre-ingesta de vacante
### Objetivo
Capturar y persistir la descripcion bruta de la vacante para dejar una entrada estable antes de cualquier estructuracion `v2`.

### Rol dentro de la pipeline
`S1` no es hoy un artefacto formal de `vacancy_v2`. Funciona como precondicion de entrada: la oportunidad ya debe tener `snapshot_raw_text`.

### Input
- URL importada
- texto manual
- descripcion copiada desde WhatsApp u otra fuente

### Output
- `opportunities.snapshot_raw_text`
- campos basicos de oportunidad como titulo, empresa, URL o metadata de origen cuando existan

### Transformaciones permitidas
- limpieza minima de captura
- persistencia de texto fuente

### Transformaciones prohibidas
- no estructurar en bloques
- no normalizar salario
- no generar queries
- no inferir alineacion candidato-vacante

### Prompt key
- `ninguna` para `vacancy_v2`
- flujo legacy relacionado, pero aparte: `task_vacancy_profile_extract`

## S2. Segmentacion contextual
### Objetivo
Clasificar el `snapshot_raw_text` en bloques contextuales amplios y consultables, preservando la mayor fidelidad posible del contenido.

### Tipo de ejecucion
`LLM-first`

### Input
- `snapshot_raw_text`
- metadata de oportunidad usada como contexto auxiliar: titulo, empresa, ubicacion, URL

### Output
- contrato `vacancy_blocks.v2`
- bloque `vacancy_blocks` con:
  - `about_the_company`
  - `work_conditions`
  - `responsibilities`
  - `required_requirements`
  - `desirable_requirements`
  - `benefits`
  - `unclassified`
- metadata global:
  - `warnings`
  - `coverage_notes`
  - `flow`
  - `vacancy_id`
  - `generated_at`

### Regla operativa
Este paso clasifica y limpia, pero no resume ni atomiza. Si el texto es ambiguo, debe hacerlo visible mediante `warnings` o `coverage_notes`.

### Transformaciones permitidas
- separar fragmentos semanticamente distinguibles
- clasificar el texto en bloques fijos
- conservar fragmentos limpios como listas de strings

### Transformaciones prohibidas
- no resumir
- no atomizar
- no generar `semantic_queries`
- no generar `item_id`
- no generar `category`
- no inventar claves nuevas

### Prompt key
- `task_vacancy_blocks_extract`

### Contrato principal
- `vacancy_blocks.v2`

## S3. Atomizacion minima
### Objetivo
Convertir los bloques de `S2` en items atomicos homogeneos y consumibles por los siguientes pasos, sin introducir semantica adicional.

### Tipo de ejecucion
`LLM-first`

### Input
- `vacancy_blocks.v2`

### Output
- contrato `vacancy_dimensions.v2`
- raiz `vacancy_dimensions` con:
  - `work_conditions`
  - `responsibilities`
  - `required_criteria`
  - `desirable_criteria`
  - `benefits`
  - `about_the_company`
  - `unclassified`
- cada item se expresa con `raw_text`
- metadata raiz:
  - `warnings`
  - `coverage_notes`
  - `contract_version`
  - `vacancy_id`
  - `generated_at`

### Regla operativa
Este paso atomiza lo minimo necesario para dejar items utilizables. No agrega IDs, queries ni taxonomias. La señal salarial debe permanecer como `raw_text` para que `S3.1` la procese aparte.

### Transformaciones permitidas
- dividir bloques en items atomicos
- deduplicar por texto normalizado
- preservar `warnings` y `coverage_notes`

### Transformaciones prohibidas
- no generar taxonomias
- no resumir ni parafrasear por defecto
- no disenar queries de retrieval
- no agregar `item_id`, `item_index`, `group_code`

### Prompt key
- `task_vacancy_dimensions_extract`

### Contrato principal
- `vacancy_dimensions.v2`

## S3.1. Normalizacion salarial
### Objetivo
Resolver el salario como subproblema independiente, porque requiere estructura distinta del resto de criterios.

### Tipo de ejecucion
`LLM-first`

### Input
- `vacancy_dimensions.v2`
- en especial señales salariales dentro de `vacancy_dimensions.work_conditions[].raw_text`

### Output
- contrato `vacancy_salary_normalization.v1`
- objeto `salary` con:
  - `min`
  - `max`
  - `currency`
  - `period`
  - `raw_text`

### Regla operativa
No reclasifica la vacante ni modifica `S3`. Solo normaliza salario cuando existe señal suficiente.

### Transformaciones permitidas
- extraer rango, moneda y periodo cuando haya evidencia
- conservar `raw_text` cuando falte certeza

### Transformaciones prohibidas
- no generar queries
- no reatomizar
- no reescribir el artefacto `vacancy_dimensions.v2`

### Prompt key
- `task_vacancy_salary_normalize`

### Contrato principal
- `vacancy_salary_normalization.v1`

## S3.9. Enriquecimiento deterministico
### Objetivo
Agregar referencias tecnicas estables por item antes de retrieval.

### Tipo de ejecucion
Programatico

### Input
- `vacancy_dimensions.v2`

### Output
- contrato `vacancy_dimensions_enriched.v1`
- cada item enriquecido con:
  - `item_id`
  - `item_index`
  - `group_code`

### Regla operativa
No usa LLM. Es un paso de trazabilidad y estabilizacion tecnica. `item_id` se calcula como fingerprint estable del contenido.

### Transformaciones permitidas
- generar `item_id`
- asignar `item_index`
- asignar `group_code`

### Transformaciones prohibidas
- no modificar `raw_text`
- no reclasificar
- no resumir
- no generar queries

### Prompt key
- `ninguna`

### Contrato principal
- `vacancy_dimensions_enriched.v1`

## S4. Generacion de queries de retrieval
### Objetivo
Traducir criterios atomizados a queries utiles para recuperar evidencia en el CV.

### Tipo de ejecucion
`LLM-first`

### Input
- principal: `vacancy_dimensions_enriched.v1`
- complementario opcional: `vacancy_salary_normalization.v1`

### Output
- contrato `vacancy_retrieval_queries.v1`
- grupos:
  - `responsibilities`
  - `required_criteria`
  - `desirable_criteria`
  - `benefits`
  - `about_the_company`
  - `work_conditions`
- cada item con:
  - `item_id`
  - `item_index`
  - `group_code`
  - `raw_text`
  - `queries`

### Regla operativa
Debe formular queries orientadas a buscar evidencia del candidato. En la configuracion actual, el retrieval semantico se limita por defecto a `responsibilities`, `required_criteria` y `desirable_criteria`; los otros grupos permanecen presentes en contrato, pero vacios por defecto.

### Transformaciones permitidas
- generar varias queries por item
- dejar `queries: []` cuando no haya formulacion util

### Transformaciones prohibidas
- no reclasificar la vacante
- no resumir la vacante
- no modificar la estructura base de items

### Prompt key
- `task_vacancy_retrieval_queries_extract`

### Contrato principal
- `vacancy_retrieval_queries.v1`

## S5. Retrieval de evidencia
### Objetivo
Ejecutar la busqueda semantica contra el CV indexado y persistir toda la evidencia recuperada.

### Tipo de ejecucion
Programatico

### Input
- `vacancy_retrieval_queries.v1`
- CV activo e indexado
- configuracion operativa de retrieval

### Output
- contrato `vacancy_retrieval_evidence.v1`
- matches por item con:
  - `query_index`
  - `query_text`
  - `score`
  - `snippet`
  - `source_ref`
  - `section`
  - `block_type`
  - `block_title`

### Regla operativa
Este paso no decide alineacion ni descarta por score. Solo recupera y ordena evidencia.

### Transformaciones permitidas
- consultar retrieval semantico
- persistir evidencia vacia por item sin tratarlo como error

### Transformaciones prohibidas
- no clasificar la fuerza de evidencia
- no concluir ajuste candidato-vacante

### Prompt key
- `ninguna`

### Contrato principal
- `vacancy_retrieval_evidence.v1`

## S6. Analisis de evidencia
### Objetivo
Consolidar de forma deterministica la evidencia recuperada por `S5` antes de cualquier salida final.

### Tipo de ejecucion
Programatico

### Input
- `vacancy_retrieval_evidence.v1`
- umbrales operativos de score

### Output
- contrato `vacancy_evidence_analysis.v1`
- por item:
  - `accepted_matches`
  - `discarded_matches`
  - `best_evidence`
  - `item_status`
  - `best_score`

### Regla operativa
Deduplica por fragmento recuperado y clasifica usando umbrales configurables. Mantiene trazabilidad de qué queries dispararon cada match.

### Transformaciones permitidas
- consolidar matches duplicados
- clasificar evidencia en buckets operativos
- conservar razones de descarte

### Transformaciones prohibidas
- no usar LLM en la iteracion actual
- no redactar aun el reporte final

### Prompt key
- `ninguna`

### Contrato principal
- `vacancy_evidence_analysis.v1`

## S7. Resumen de alineacion
### Objetivo
Sintetizar `S6` en un resumen estructurado de consumo rapido para el paso final.

### Tipo de ejecucion
Programatico

### Input
- `vacancy_evidence_analysis.v1`

### Output
- contrato `vacancy_alignment_summary.v1`
- `overall`
- `groups`
- `strengths`
- `gaps`
- `review_items`

### Regla operativa
No reemplaza `S6`; lo resume. Solo resume grupos primarios: `responsibilities`, `required_criteria`, `desirable_criteria`.

### Transformaciones permitidas
- agregar conteos globales
- derivar listas compactas de fortalezas, brechas y puntos a revisar

### Transformaciones prohibidas
- no rehacer retrieval
- no recalcular el significado de la evidencia fuera de los buckets definidos en `S6`

### Prompt key
- `ninguna`

### Contrato principal
- `vacancy_alignment_summary.v1`

## S8. Reporte final grounded
### Objetivo
Producir el analisis final candidato-vacante en formato estructurado y legible para usuario final.

### Tipo de ejecucion
`LLM-first`

### Input
- `person_context`
- `opportunity_context`
- `vacancy_alignment_summary.v1`
- `vacancy_evidence_analysis.v1`

### Output
- contrato `vacancy_alignment_report.v1`
- dos claves raiz obligatorias:
  - `report`
  - `rendered_markdown`

### Contenido esperado del reporte
- `executive_summary`
- `decision_table`
- `vacancy_fit_matrix`
- `candidate_preference_matrix`
- `fit_answer`
- `strengths`
- `gaps`
- `preference_conflicts`
- `improvement_actions`
- `alerts_and_conflicts`
- `actionable_conclusion`

### Regla operativa
Debe usar `S7` como resumen y `S6` como respaldo detallado. No recalcula scores ni buckets. Su trabajo es interpretar grounded en evidencia y producir una recomendacion accionable para el candidato o su tutor.

### Transformaciones permitidas
- redactar conclusion ejecutiva
- organizar matrices legibles
- producir version dual `JSON + rendered_markdown`

### Transformaciones prohibidas
- no inventar informacion
- no omitir criterios relevantes
- no convertir ausencia de evidencia en contradiccion
- no recalcular scores de retrieval

### Prompt key
- `task_vacancy_alignment_report`

### Contrato principal
- `vacancy_alignment_report.v1`

## Llaves de prompt por Step
- `S1`: `ninguna` en `vacancy_v2`
- `S2`: `task_vacancy_blocks_extract`
- `S3`: `task_vacancy_dimensions_extract`
- `S3.1`: `task_vacancy_salary_normalize`
- `S3.9`: `ninguna`
- `S4`: `task_vacancy_retrieval_queries_extract`
- `S5`: `ninguna`
- `S6`: `ninguna`
- `S7`: `ninguna`
- `S8`: `task_vacancy_alignment_report`

## Estado de documentacion
- `S2` a `S8` ya existian documentados de forma distribuida
- este documento los consolida en una sola referencia operativa
- `S1` queda explicitado aqui como precondicion operativa, aunque todavia no exista como contrato formal de `vacancy_v2`

## Fuentes principales
- `docs/vacancy_structure_implementation_plan.md`
- `docs/vacancy_structure_contract_v2.md`
- `apps/backend/app/services/prompt_config_store.py`
- contratos ejecutables `apps/backend/app/services/vacancy_*_contract.py`
