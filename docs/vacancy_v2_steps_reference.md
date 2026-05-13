# Vacancy V2 Steps Reference

## Proposito
Consolidar en un solo documento la definicion operativa de los Steps de `vacancy_v2`, su objetivo, input, output, tipo de ejecucion y la llave de prompt asociada cuando aplica.

## Alcance
- este documento consolida `S1` a `S8`
- adicionalmente documenta las capas posteriores de presentacion/comparacion planeadas para el rediseño de match
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
- evolucion recomendada nueva: `S4` sigue como candidate generation `LLM-first`, pero `S6` debe evolucionar hacia rerank real con `Cohere`, manteniendo `S6.5` como adjudicacion grounded posterior
- para el rediseño de presentacion final se propone una capa adicional posterior a `S7 v2`: limpieza de perfil comparable, normalizacion de condiciones comparables de vacante, checks deterministas y matriz de presentacion antes del relato final

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
| `S6.5` | Adjudicacion grounded de evidencia | `LLM-first` | `vacancy_evidence_adjudication.v1` | `task_vacancy_evidence_adjudication` |
| `S7` | Resumen de alineacion | programatico | `vacancy_alignment_summary.v1` | `ninguna` |
| `S8` | Reporte final grounded | `LLM-first` | `vacancy_alignment_report.v1` | `task_vacancy_alignment_report` |

## Capas planeadas posteriores a `S7 v2`
| Capa | Nombre | Tipo | Output principal | Prompt key |
| --- | --- | --- | --- | --- |
| `P0` | Limpieza de perfil comparable del candidato | programatico | `candidate_preference_profile.v1` | `ninguna` |
| `C1` | Normalizacion de condiciones comparables de vacante | programatico/controlado | `vacancy_comparable_conditions.v1` | `ninguna` |
| `C2` | Checks deterministas vacante-perfil | programatico | `candidate_preference_checks.v1` | `ninguna` |
| `P1` | Matriz deterministica de presentacion profesional | programatico | `vacancy_fit_presentation.v1` | `ninguna` |
| `S8 v2` | Relato final centrado en la persona candidata | `LLM-first` | `vacancy_alignment_report.v2` | `task_vacancy_alignment_report_v2` |

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

### Evolucion planeada
Para comparaciones de compensacion mas utiles, se propone una extension minima del contrato de `S3.1` cuando la vacante combine fijo + variable:
- `has_variable_component`
- `variable_component_type`
- `variable_component_note`

Regla planeada:
- `min/max/currency/period` siguen representando solo la base fija comparable
- el componente variable se preserva explicitamente y no solo dentro de `raw_text`

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

## P0. Limpieza de perfil comparable del candidato
### Objetivo
Reducir la superficie de preferencias del candidato a senales realmente comparables o contrastables, eliminando ruido blando o ambiguo antes de los checks deterministas.

### Tipo de ejecucion
Programatico

### Input
- perfil estructurado persistido del candidato

### Output
- contrato propuesto `candidate_preference_profile.v1`

### Senales comparables objetivo
- ubicacion actual
- ubicaciones aceptadas
- modalidades aceptadas
- expectativa salarial
- tipos de contrato aceptados
- disponibilidad para relocalizacion
- disponibilidad para viaje
- restricciones duras explicitas

### Aclaracion importante
`P0` no debe absorber capacidades profesionales como:
- idiomas y nivel
- certificaciones
- herramientas o tecnologias

Esas senales pertenecen al fit profesional principal. En especial:
- `idiomas + nivel` deben agregarse al perfil estructurado del candidato como captura explicita;
- luego deben alimentar el flujo principal de alineacion profesional, no los preference checks deterministas.

### Transformaciones prohibidas
- no inventar preferencias
- no mantener preferencias narrativas sin regla de comparacion o contraste
- no incluir en `P0` senales de company/culture fit que dependen de investigacion externa

### Regla de simplificacion
`P0` no debe incluir:
- `company_scale`
- `organizational_moment`
- `cultural_formality`
- `work_intensity`
- `environment_predictability`
- `organization_structure_level`
- `schedule_flexibility`

Esas senales quedan fuera del artefacto comparable y, si se usan, pertenecen al modulo `cultural/company fit`.

### Prompt key
- `ninguna`

## C1. Normalizacion de condiciones comparables de vacante
### Objetivo
Convertir las condiciones observables de la vacante en senales comparables estables antes de cruzarlas con el perfil del candidato.

### Tipo de ejecucion
Programatico o controlado

### Input
- `vacancy_dimensions.v2.work_conditions`
- `vacancy_salary_normalization.v1`
- `snapshot_raw_text` como apoyo

### Output
- contrato propuesto `vacancy_comparable_conditions.v1`

### Senales comparables objetivo
- ubicacion normalizada
- modalidad normalizada
- compensacion comparable
- tipo de contrato cuando exista

### Regla operativa
La interpretacion puede existir al normalizar, pero el output debe quedar estable. Si la vacante no especifica una condicion con suficiente claridad, debe persistirse como desconocida.

### Caso especial planeado
Si la vacante expresa `salario fijo + comisiones` o `salario fijo + variable`, la base fija debe quedar comparable y el componente variable debe quedar explicitado, no solo escondido en `raw_text`.

### Regla de valores
- `contract_type.value` debe alinearse con el set reducido comparable:
  - `indefinite`
  - `fixed_term`
  - `service_contract`
  - `unknown`
- `modality.mode` debe alinearse con:
  - `onsite`
  - `hybrid`
  - `remote`
  - `unknown`

### Prompt key
- `ninguna`

## C2. Checks deterministas vacante-perfil
### Objetivo
Comparar condiciones comparables de vacante contra preferencias/restricciones comparables del candidato sin volver a usar LLM para decidir el estado final de cada fila.

### Tipo de ejecucion
Programatico

### Input
- `candidate_preference_profile.v1`
- `vacancy_comparable_conditions.v1`

### Output
- contrato propuesto `candidate_preference_checks.v1`

### Regla operativa
La comparacion debe operar sobre valores ya normalizados.

Ejemplos:
- `Bogota D.C.` vacante y `Bogota, Colombia` candidato -> compatible
- vacante `remote` -> no exigir match de ciudad
- vacante `onsite` + candidato `remote only` -> conflicto
- falta de senal suficiente en vacante o perfil -> `Sin informacion`

### Prompt key
- `ninguna`

## P1. Matriz deterministica de presentacion profesional
### Objetivo
Construir la matriz principal de lectura del fit profesional a partir de `S6.5`, sin delegar a `S8` la reconstruccion de filas.

### Tipo de ejecucion
Programatico

### Input
- `vacancy_evidence_adjudication.v1`

### Output
- contrato propuesto `vacancy_fit_presentation.v1`

### Regla operativa
Debe agrupar como minimo:
- `Requisitos obligatorios`
- `Responsabilidades`
- `Deseables`

Columnas objetivo:
- `Tipo u origen`
- `Criterio`
- `Estado`
- `Por que`

La evidencia se muestra como detalle desplegable dentro de `Por que`, no como columna ancha separada.

### Prompt key
- `ninguna`

## S8 v2. Relato final centrado en la persona candidata
### Objetivo
Generar el relato final y la recomendacion accionable usando como insumos principales la adjudicacion, la matriz profesional ya ensamblada y los checks de preferencias ya resueltos.

### Tipo de ejecucion
`LLM-first`

### Input
- `vacancy_evidence_adjudication.v1`
- `vacancy_alignment_summary.v2`
- `vacancy_fit_presentation.v1`
- `candidate_preference_checks.v1`

### Output
- `vacancy_alignment_report.v2`

### Regla operativa
`S8 v2` debe explicar y recomendar. No debe volver a decidir ni reconstruir filas de tablas que ya fueron derivadas previamente.

### Prompt key
- `task_vacancy_alignment_report_v2`

## Nota de perfil candidato
Como decision de diseno vigente para el rediseño:
- `idioma + nivel` debe incorporarse al perfil estructurado del candidato;
- no forma parte de `P0` ni de `C2`;
- su contraste pertenece al fit profesional principal;
- mas adelante podria evaluarse una extension similar para certificaciones y herramientas, pero no forma parte del slice actual.

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

### Evolucion recomendada
`S4` debe dejar de producir preguntas largas o probes en ingles cuando vacante y CV estan en espanol. La evolucion recomendada es:
- probes cortos
- idioma dominante de la vacante/CV
- sin `?`
- validados programaticamente tras la generacion

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

### Evolucion recomendada
`S6` debe evolucionar de consolidacion por thresholds a rerank real:
- `S5` conserva candidate generation con multiples queries
- `S6` deduplica y rerankea por `criterio -> chunk` usando `Cohere`
- el rerank no depende de `criterion_type`, `section` o `block_type` como senales primarias
- `S6` debe soportar descarte, estado `pending_rerank` y relanzamiento parcial (`subset` o `pending_only`) para manejar limites del proveedor
- si `Cohere` esta deshabilitado desde administracion, `S6` debe volver temporalmente a la logica actual basada en thresholds sin romper el resto del pipeline

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

## S6.5. Adjudicacion grounded de evidencia
### Objetivo
Transformar la evidencia consolidada de `S6` en un juicio por item grounded y trazable, antes de la matriz de presentacion y del relato final.

### Tipo de ejecucion
`LLM-first`

### Input
- `vacancy_evidence_analysis.v1`

### Output
- contrato `vacancy_evidence_adjudication.v1`
- por item:
  - `alignment_status`
  - `proof_summary`
  - `best_supporting_evidence`
  - `weak_or_discarded_evidence`
  - `confidence`
  - `candidate_risk`
  - `cv_improvement_opportunity`

### Regla operativa
El juicio principal ocurre a nivel item. La evidencia visible debe salir de la evidencia aceptada o descartada ya trazada en `S6`, preservando metadata estructural y evitando reconstrucciones libres del snippet.

### Regla vigente de diseno
- `proof_summary` es la explicacion principal a nivel item
- `best_supporting_evidence` usa soporte minimo por snippet (`support_scope` y `support_note_short` opcional)
- el paso no debe atribuir a un snippet hechos que solo vivan en otro snippet hermano del mismo item

### Transformaciones permitidas
- consolidar juicio semantico por item
- seleccionar evidencia visible por referencia grounded
- clasificar fuerza local de soporte por snippet

### Transformaciones prohibidas
- no inventar `source_ref`, `block_title`, `section` o `snippet`
- no usar evidencia fuera de lo recuperado y consolidado aguas arriba
- no reemplazar a `S6`; este paso adjudica, no rehace retrieval

### Prompt key
- `task_vacancy_evidence_adjudication`

### Contrato principal
- `vacancy_evidence_adjudication.v1`

## S7. Resumen de alineacion
### Objetivo
Sintetizar `S6` y/o `S6.5` en un resumen estructurado de consumo rapido para el paso final.

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
