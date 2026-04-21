# Project Status

## Estado
- fase_actual: `Implementacion`
- checkpoint_actual: `consistency gate vacancy v2 extendido con evaluacion pass/fail y umbrales configurables por query`
- repo_status: `flujo V1 operativo con analisis, postulacion, chat, CV semantico, admin de prompts y extraccion estructurada de vacantes en forma legacy estable; propuesta v2 desacoplada en branch experimental`
- ultima_actualizacion: `2026-04-21`

## Progreso Por Fase
- `Fase 0`: completada
- `Fase 1`: completada
- `Fase 2`: completada
- `Fase 3`: completada
- `Fase 4`: completada
- `Implementacion`: iniciada

## Estado Vigente
- backend y frontend compilan en estado de trabajo actual
- extraccion de vacantes restaurada a la version estable inicial de V1.1
- prompt recomendado de extraccion restaurado al contrato legacy estable
- UI de `Vacantes > Editar estructura > JSON avanzado` alineada otra vez con el esquema legacy persistido
- compatibilidad de contexto de vacante restaurada para que analisis siga leyendo la estructura legacy
- branch de trabajo para exploracion creado: `spike/vacancy-structure-v2`
- contrato propuesto `vacancy_structure.v2` agregado como artefacto aislado en backend para revision de esquema
- nota tecnica del contrato propuesta agregada en `docs/vacancy_structure_contract_v2.md`
- plan operativo de implementacion agregado en `docs/vacancy_structure_implementation_plan.md`
- plan de implementacion y tareas de seguimiento volcados a Notion en `Engineering Projects Hub`
- mecanica operativa de ejecucion y fuente de verdad formalizada en `AGENTS.md`
- protocolo iterativo de implementacion agregado en `.specify/instructions/Implementation-Worker-Protocol.md`
- regla de commits por slice y checkpoint con usuario en branch `spike/*` formalizada en el protocolo operativo
- criterio de commit refinado: mensaje en ingles y propuesta de commit solo despues de explicitar pruebas operativas del slice
- Slice 1 de persistencia paralela implementado en backend/frontend para `vacancy_blocks` y `vacancy_dimensions`
- Slice 1 validado operativamente por el usuario: creacion de oportunidad, presencia de campos `vacancy_blocks_*`/`vacancy_dimensions_*`, extraccion legacy y analisis `perfil-vacante` sin regresion observada
- Slice 2 de contratos ejecutables implementado con modulos separados para `vacancy_blocks.v1` y `vacancy_dimensions.v1`
- Slice 2 validado tecnicamente: `py_compile` y `unittest` dedicados en verde para contratos de Paso 2 y Paso 3
- Slice 3 de servicio `vacancy_blocks` implementado con flow dedicado `task_vacancy_blocks_extract` y pruebas unitarias dedicadas
- decision de rediseño registrada: Paso 2 opera `LLM-first` sin fallback heuristico de clasificacion; ante entrada invalida o salida LLM invalida falla de forma controlada
- Slice 4 de servicio `vacancy_dimensions` implementado con flow dedicado `task_vacancy_dimensions_extract` y pruebas unitarias dedicadas
- decision de rediseño registrada: Paso 3 opera `LLM-first` sin fallback heuristico de atomizacion; ante entrada Paso 2 invalida o salida LLM invalida falla de forma controlada
- Slice 5 backend implementado: endpoints `recompute` y `recompute/stream` para `vacancy_blocks` y `vacancy_dimensions`, con persistencia de estado `draft/error` y etapas SSE por flujo
- Slice 5 validado tecnicamente en `apps/backend/.venv`: `python -m unittest tests.test_vacancy_v2_endpoints` en verde (`6 tests`)
- Slice runtime config interno implementado: nuevo modulo `vacancy_v2_runtime_config` con schema y defaults para Step 2/3, override opcional por `vacancy_v2_runtime_config_json` y validacion de rango para `llm_temperature`
- Step 2 y Step 3 ahora leen `llm_temperature` desde el schema interno de `vacancy_v2` (sin cambios en admin runtime)
- Slice runtime config validado tecnicamente en `apps/backend/.venv`: `python -m unittest tests.test_vacancy_v2_runtime_config tests.test_vacancy_blocks_service tests.test_vacancy_dimensions_service` en verde (`16 tests`)
- Slice 6 frontend implementado en modo experimental: panel `Vacancy V2` por oportunidad con recomputo independiente de Step 2/Step 3, visualizacion de `status`/`generated_at`, inspeccion JSON read-only y cambio manual de estado `draft/approved`
- Slice 6 validado tecnicamente en frontend: `npm run build` en verde
- micro-ajuste de calidad aplicado en Step 2/Step 3: toda señal de salario/compensacion se fuerza por prompt a `work_conditions` (no `benefits`)
- ajuste aplicado en tres capas: `system_prompt` de servicios, fallback prompts de servicios y templates default en `prompt_config_store`
- validacion tecnica del ajuste salary mapping: `PERSISTENCE_BACKEND=memory .venv/bin/python -m unittest tests.test_vacancy_blocks_service tests.test_vacancy_dimensions_service` en verde (`12 tests`)
- consistency gate tecnico implementado en backend para `vacancy v2`: metrica de traspaso salary Step 2 -> Step 3, deteccion de salary mal clasificado en `benefits` y muestreo de incidencias por oportunidad
- endpoint nuevo de reporte por persona: `GET /persons/{person_id}/opportunities/vacancy-v2/consistency?sample_limit=20`
- pruebas dedicadas del consistency gate en verde: `PERSISTENCE_BACKEND=memory .venv/bin/python -m unittest tests.test_vacancy_v2_consistency_gate` (`2 tests`)
- prueba de no-regresion de endpoints v2 existente en verde: `PERSISTENCE_BACKEND=memory .venv/bin/python -m unittest tests.test_vacancy_v2_endpoints` (`6 tests`)
- consumo del consistency gate documentado paso a paso en `README.md` y `guia_uso.md` (login, obtencion de `person_id`, invocacion endpoint e interpretacion de metricas)
- micro-hardening aplicado en Step 3: si `vacancy_blocks.work_conditions` contiene senal salarial, `vacancy_dimensions.work_conditions.salary.text` no puede quedar vacio (regla reforzada en `system_prompt`, fallback y template default)
- validacion tecnica del micro-hardening Step 3: `PERSISTENCE_BACKEND=memory .venv/bin/python -m unittest tests.test_vacancy_dimensions_service tests.test_vacancy_v2_consistency_gate tests.test_vacancy_v2_endpoints` en verde (`14 tests`)
- consistency gate extendido: respuesta ahora incluye `gate_passed`, `failed_checks` y `thresholds`
- endpoint de consistency gate ahora soporta umbrales por query: `min_salary_transfer_rate`, `max_salary_signal_in_step2_benefits_rate`, `min_salary_transfer_eligible`
- validacion tecnica del gate extendido: `PERSISTENCE_BACKEND=memory .venv/bin/python -m unittest tests.test_vacancy_v2_consistency_gate tests.test_vacancy_v2_endpoints tests.test_vacancy_dimensions_service` en verde (`15 tests`)
- decision de rediseño registrada: `v2` arranca sin `JobCriteriaMapper`
- decision de rediseño registrada: Paso 2 persiste como `vacancy_blocks` con claves fijas, `warnings`, `coverage_notes` y texto limpio por bloque
- decision de rediseño registrada: Paso 2 incluye `contract_version` explicito en la raiz del artefacto
- decision de rediseño registrada: Paso 2 incluye `vacancy_id` explicito en la raiz del artefacto
- decision de rediseño registrada: Paso 2 incluye `generated_at` en la raiz del artefacto
- decision de rediseño registrada: Paso 2 clasifica por fragmento semantico minimo util y no queda limitado al parrafo completo
- decision de rediseño registrada: en Paso 2 no se duplica texto por defecto; si hay requisitos separables se divide en fragmentos, y si no, se asigna dimension principal con advertencia
- decision de rediseño registrada: `work_conditions` se cierra como version amplia controlada, incluyendo condiciones operativas o de elegibilidad no equivalentes a competencias
- decision de rediseño registrada: cada clave de `vacancy_blocks` persiste una lista de fragmentos clasificados; no se usa `string` canonico concatenado con `;`
- decision de rediseño registrada: los items de `vacancy_blocks` son `string`; `warnings` y `coverage_notes` son globales al artefacto, opcionales en semantica y persistidos como arrays presentes en el contrato canonico
- decision de rediseño registrada: Paso 3 genera un artefacto atomizado separado; `vacancy_blocks` queda consultable solo como artefacto de Paso 2
- decision de rediseño registrada: Paso 3 se orienta por `vacancy_dimensions`; se descarta la idea de `searchable_requirements`
- borrador vigente de Paso 3: `work_conditions` como objeto normalizado y listas atomicas para `responsibilities`, `required_competencies`, `desirable_competencies` y `benefits`
- decision de rediseño registrada: Paso 3 incluye `contract_version` explicito en la raiz del artefacto
- decision de rediseño registrada: Paso 3 incluye `vacancy_id` explicito en la raiz del artefacto
- decision de rediseño registrada: Paso 3 incluye `generated_at` en la raiz del artefacto
- decision de rediseño registrada: en Paso 3 los `string` vacios se persisten como `\"\"`, los `number`/`boolean` desconocidos como `null` y los arrays vacios como `[]`
- decision de rediseño registrada: `semantic_queries` se formaliza como `string[]`; criterio inicial de generacion: una sola query principal por item
- decision de rediseño registrada: `benefits` puede participar luego en analisis de fit, condicionado por la evolucion del modelo de preferencias del candidato
- decision de rediseño registrada: `benefits` queda alineado con las otras listas atomicas, con `category` como texto libre controlado y `semantic_queries` presentes pero no obligatorias en esta fase
- decision de rediseño registrada: set fijo aprobado para `work_conditions`: `salary`, `modality`, `location`, `contract_type`, `schedule`, `availability`, `travel`, `legal_requirements`, `relocation`, `mobility_requirements`
- decision de rediseño registrada: los items atomicos de Paso 3 quedan con campos minimos solamente (`id`, campo principal, `category`, `semantic_queries`, `raw_text`)
- decision de rediseño registrada: todos los campos `category` de Paso 3 quedan como texto libre controlado; no se usan por ahora como eje fuerte de logica ni de presentacion
- decision de rediseño registrada: `artifact_id` queda fuera del contrato canonico por ahora y se resuelve en persistencia mientras no exista requerimiento formal de historial
- decision de rediseño registrada: el naming nuevo evita ordinales; se usaran nombres semanticos (`vacancy_blocks`, `vacancy_dimensions`) en lugar de `step2`/`step3`
- decision de rediseño registrada: plan de implementacion por fases definido para ejecutar `v2` en paralelo al baseline estable
- decision de rediseño registrada: la configuracion de corrida de Paso 2 y Paso 3 queda interna en backend en esta fase; no se expone aun en administracion
- decision de rediseño registrada: controles operativos como retries, timeout, token limits y validation retries quedan fuera de admin hasta validar corridas reales
- extractor estable, `JobCriteriaMapper` activo y UI legacy permanecen sin cambios funcionales

## Artefactos Clave
- `.specify/00.Caso-de-Uso-y-Alcance.md`: vigente
- `.specify/01.Constitucion.md`: vigente
- `.specify/02.Spec.md`: vigente
- `.specify/03.Arquitectura-y-Plan.md`: vigente
- `docs/project_status_history.md`: historico acumulado de estados previos
- `docs/vacancy_structure_contract_v2.md`: propuesta aislada de contrato de estructura de vacante
- `docs/vacancy_structure_implementation_plan.md`: plan detallado de implementacion por fases y slices
- `apps/backend/app/services/vacancy_structure_contract_v2.py`: contrato ejecutable v2 no integrado
- `apps/backend/tests/test_vacancy_structure_contract_v2.py`: cobertura unitaria del contrato v2

## Bloqueadores
- falta ejecutar consistency gate de calidad sobre vacantes reales para cerrar desviaciones de Step 2/Step 3
- falta cerrar si `benefits` requerira luego una normalizacion mas fuerte
- el experimento de nueva estructura de vacante no debe reintroducirse sobre este baseline ni conectarse al extractor estable antes de acuerdo

## Siguiente Actividad
- ejecutar consistency gate en datos reales (10-20 vacantes) usando el endpoint y revisar incidencias muestreadas
- abrir micro-slice de hardening adicional solo si el gate reporta `salary_transfer_missing` o `salary_signal_in_step2_benefits` por encima del umbral esperado
- mantener analisis legacy sin integracion v2 hasta validar calidad con datos reales
