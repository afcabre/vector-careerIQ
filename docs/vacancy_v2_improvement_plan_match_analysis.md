# Plan de mejora vacancy_v2: análisis robusto candidato-vacante

## 0. Objetivo general del ajuste

Mejorar la calidad, precisión y utilidad del análisis de alineación candidato-vacante, manteniendo trazabilidad y minimizando alucinaciones.

El rediseño debe preservar la lógica de pipeline, pero corregir tres problemas:

- Fragmentación excesiva sin interpretación suficiente.
- Uso de similitud semántica como si fuera evidencia concluyente.
- Reporte final pobre, incompleto o no suficientemente centrado en la persona candidata.

El nuevo enfoque debe producir un análisis que diferencie claramente:

- cumple,
- cumple parcialmente,
- evidencia indirecta,
- no está demostrado en el CV,
- deseable no evidenciado,
- conflicto real,
- información no especificada por la vacante.

## 1. Diagnóstico técnico confirmado

### 1.1. Problema en S3

S3 atomiza correctamente, pero deja algunos criterios demasiado abstractos.

Ejemplos actuales:

- `Asegurar la excelencia técnica`
- `Garantizar entregables de alto impacto y crecimiento sostenible del negocio`

Estos ítems pierden el contexto de la misión del cargo. Deberían conservar el objeto mínimo:

- `Asegurar la excelencia técnica del área de servicios digitales y de los proyectos de transformación digital`
- `Garantizar entregables de alto impacto en proyectos de transformación digital, contribuyendo al crecimiento sostenible del negocio`

### 1.2. Problema en S4

S4 genera queries válidas, pero limitadas.

Ejemplo actual:

```json
[
  "experiencia garantizando la rentabilidad en proyectos de transformación digital",
  "responsabilidad en la gestión financiera de proyectos tecnológicos"
]
```

El problema es que estas queries pueden traer evidencia cercana, pero no necesariamente evidencia que pruebe rentabilidad, `P&L`, `business case`, presupuesto, `ROI` o control financiero.

S4 debe generar queries probatorias, no solo semánticas.

### 1.3. Problema en S6

S6 clasifica como `useful_evidence` cualquier match sobre el umbral `0.45`.

Eso es útil como señal técnica, pero no como dictamen de alineación.

Ejemplo confirmado:

Para el criterio:

`Mínimo 5 años de experiencia profesional`

S6 puede priorizar un snippet de `otros estudios` porque tiene mayor score, aunque el snippet que realmente prueba el criterio sea el perfil profesional donde aparece `20 años de experiencia profesional`.

### 1.4. Problema en S7

S7 resume todo `useful_evidence` como fortaleza.

En el ejemplo real produjo:

```json
{
  "no_evidence_count": 0,
  "useful_evidence_count": 11,
  "gaps": []
}
```

Esto no significa que el candidato cumpla todo; solo significa que Pinecone encontró similitud semántica para todos los ítems.

### 1.5. Problema en S8

S8 recibe insumos sobreoptimistas, omite criterios y genera afirmaciones no grounded.

Problemas observados:

- Incluyó solo 2 criterios en la matriz, aunque había 11 criterios evaluados.
- Inventó una brecha de `sectores específicos` que la vacante no pedía.
- No distinguió bien entre requisito obligatorio, deseable e ideal.
- No produjo una lectura suficientemente accionable para la persona candidata.

## 2. Arquitectura objetivo

La pipeline recomendada queda así:

```text
S1    Pre-ingesta de vacante
S2    Segmentación contextual
S3    Atomización mínima con contexto suficiente
S3.1  Normalización salarial
S3.9  Enriquecimiento determinístico
S4    Generación de queries probatorias de retrieval
S5    Retrieval de evidencia
S6    Consolidación técnica de evidencia recuperada
S6.5  Adjudicación semántica grounded de evidencia
S7    Resumen de alineación basado en adjudicación
S8    Reporte final centrado en la persona candidata
```

El cambio más importante es incorporar:

`S6.5 — Evidence adjudication / Adjudicación semántica grounded`

## 3. Fase 1 — Ajustar S3: atomización con contexto mínimo

### 3.1. Objetivo

Evitar que S3 genere ítems demasiado abstractos que luego produzcan queries débiles y evidencia ambigua.

### 3.2. Cambio funcional

S3 debe seguir sin inventar, resumir ni enriquecer, pero puede arrastrar contexto explícito del bloque original cuando el ítem aislado quede incompleto.

### 3.3. Regla nueva para el prompt S3

Agregar al prompt de S3:

> Cuando un item atomizado dependa del contexto de una frase madre para ser comprensible, conserva el contexto mínimo necesario dentro del raw_text.
>
> No dejes items excesivamente abstractos como:
> - "Asegurar la excelencia técnica"
> - "Garantizar entregables de alto impacto"
> - "Asegurar rentabilidad"
> - "Articular stakeholders"
>
> En esos casos, incluye el objeto explícito del criterio tomando únicamente información del mismo bloque o frase original.
>
> Ejemplos:
> - "Asegurar la excelencia técnica del área de servicios digitales y de los proyectos de transformación digital"
> - "Garantizar entregables de alto impacto en proyectos de transformación digital"
> - "Asegurar la rentabilidad de proyectos de transformación digital"
> - "Articular equipos multidisciplinarios, clientes y áreas internas en iniciativas de transformación digital"
>
> No agregues información nueva.
> No interpretes intención no explícita.
> Solo conserva contexto mínimo ya presente en la vacante.

### 3.4. Criterios de aceptación

S3 debe:

- mantener contrato `vacancy_dimensions.v2`;
- no agregar claves;
- no generar taxonomías;
- no generar queries;
- no crear criterios nuevos;
- evitar ítems huérfanos o excesivamente abstractos.

## 4. Fase 2 — Ajustar S4: queries probatorias

### 4.1. Objetivo

Mejorar la recuperación de evidencia del CV generando queries que busquen señales concretas de cumplimiento, no solo similitud textual.

### 4.2. Problema actual

S4 genera 2 queries por ítem. En roles complejos, esto es poco.

Ejemplo actual:

```json
[
  "experiencia asegurando la excelencia técnica en proyectos",
  "responsabilidad en la implementación de estándares técnicos"
]
```

Mejor sería incluir variantes como:

```json
[
  "definición de arquitectura y estándares técnicos",
  "gobierno técnico de soluciones tecnológicas",
  "aseguramiento de calidad técnica en proyectos de TI",
  "liderazgo técnico en diseño e implementación de soluciones",
  "validación de principios técnicos, arquitectura o estándares tecnológicos"
]
```

### 4.3. Cambio recomendado

Aumentar `retrieval_queries_per_item` de `2` a `4` o `5` para criterios complejos.

Configuración inicial recomendada:

- `retrieval_queries_per_item = 4`
- `top_k_semantic_per_criterion = 6`

No subir `top_k` demasiado antes de implementar `S6.5`, porque aumentaría ruido.

### 4.4. Nueva regla para S4

Agregar al prompt S4:

> Para cada query, prioriza patrones de evidencia que podrían probar el criterio en un CV.
>
> Una query no debe limitarse a repetir el requisito. Debe buscar señales concretas como:
> - cargos o responsabilidades equivalentes,
> - logros medibles,
> - tecnologías usadas,
> - resultados de negocio,
> - métricas,
> - formación,
> - certificaciones,
> - años de experiencia,
> - sectores o tipos de organización cuando sean relevantes,
> - gestión de presupuesto,
> - gestión de equipos,
> - gestión de proveedores,
> - gestión de stakeholders,
> - casos de negocio,
> - eficiencia operativa,
> - continuidad,
> - rentabilidad,
> - cumplimiento de tiempo/costo/alcance.
>
> Cuando el criterio sea abstracto, tradúcelo a evidencias observables.
>
> Ejemplos:
> - "Asegurar la excelencia técnica" puede buscar:
>   "definición de arquitectura y estándares técnicos",
>   "gobierno técnico de soluciones tecnológicas",
>   "aseguramiento de calidad técnica en proyectos de TI",
>   "validación de principios técnicos o arquitectura empresarial".
>
> - "Asegurar rentabilidad de proyectos" puede buscar:
>   "gestión de presupuesto de proyectos tecnológicos",
>   "cumplimiento de tiempo costo y alcance en proyectos TI",
>   "evaluación financiera de iniciativas tecnológicas",
>   "business case de proyectos tecnológicos",
>   "optimización de costos mediante transformación digital".
>
> - "Crecimiento sostenible del negocio" puede buscar:
>   "alineación de proyectos tecnológicos con objetivos de negocio",
>   "mejoras operativas con impacto en eficiencia o crecimiento",
>   "roadmaps tecnológicos orientados a generación de valor",
>   "transformación digital con impacto en productividad o rentabilidad".

### 4.5. Ajuste a la regla de cantidad

Si el runtime permite cantidad variable:

> Para cada item aplicable a retrieval, genera entre 3 y 5 queries.

Si el runtime exige número fijo:

> Para cada item aplicable a retrieval, genera exactamente {retrieval_queries_per_item} queries. Prioriza diversidad probatoria sobre repetición.

### 4.6. Criterios de aceptación

S4 debe:

- conservar contrato `vacancy_retrieval_queries.v1`;
- mantener `item_id`, `item_index`, `group_code`, `raw_text`;
- no reclasificar ítems;
- no inventar requisitos;
- generar queries más diversas;
- diferenciar queries literales, semánticas, probatorias y de evidencia observable, aunque el contrato no agregue `query_type`.

## 5. Fase 3 — Ajustar S6: consolidación técnica, no dictamen

### 5.1. Objetivo

Evitar que S6 sea interpretado como análisis de cumplimiento.

### 5.2. Cambio conceptual

Renombrar o reinterpretar los buckets.

Actual:

- `strong_evidence`
- `useful_evidence`
- `review`
- `no_evidence`

Recomendado:

- `high_similarity_match`
- `medium_similarity_match`
- `low_similarity_match`
- `no_retrieval_match`

O, si no se quiere cambiar contrato:

- mantener `item_status`,
- pero documentar que `useful_evidence` significa únicamente `evidencia candidata recuperada`;
- nunca debe ser usado como `cumple`.

### 5.3. Reglas nuevas de S6

S6 debe:

- consolidar matches;
- deduplicar snippets;
- ordenar por señales técnicas;
- conservar scores;
- conservar queries que dispararon cada match;
- no concluir alineación;
- no producir fortalezas ni gaps profesionales.

### 5.4. Ajuste de ranking técnico

Agregar penalizaciones o boosts por tipo de criterio y sección.

Ejemplos:

Para formación

Priorizar:

- formación académica
- `education`
- `certifications`
- otros estudios
- `profile_summary`

Penalizar:

- conocimientos
- skills genéricos
- experiencia no educativa

Para años de experiencia

Priorizar:

- `profile_summary` con años explícitos
- experiencia laboral con fechas
- cargos con duración

Penalizar:

- otros estudios
- formación académica
- skills
- conocimientos

Para certificaciones

Priorizar:

- `certifications`
- otros estudios
- formación complementaria

Penalizar:

- conocimientos
- experiencia general
- responsabilidades laborales sin certificación explícita

Para liderazgo

Priorizar:

- experiencia laboral
- `profile_summary`
- logros
- proyectos clave

Para resultados de negocio

Priorizar:

- logros
- métricas
- presupuesto
- eficiencia
- reducción de costos
- cumplimiento de tiempo/costo/alcance

### 5.5. Criterios de aceptación

S6 no debe:

- declarar cumplimiento;
- declarar brecha profesional;
- producir fortalezas finales;
- tratar score como verdad;
- elegir como `best_evidence` un snippet inadecuado por sección cuando exista otro snippet más probatorio.

## 6. Fase 4 — Crear S6.5: adjudicación semántica grounded

### 6.1. Objetivo

Evaluar con LLM si la evidencia recuperada realmente soporta cada criterio de la vacante.

Este paso es el núcleo del rediseño.

### 6.2. Tipo de ejecución

`LLM-first`

### 6.3. Input

S6.5 debe recibir:

- `person_context`;
- `opportunity_context`;
- `vacancy_dimensions_enriched.v1`;
- `vacancy_evidence_analysis.v1`;
- opcionalmente `vacancy_retrieval_evidence.v1` si se requiere evidencia completa no resumida.

### 6.4. Output

Nuevo contrato:

`vacancy_evidence_adjudication.v1`

### 6.5. Contrato sugerido

```json
{
  "contract_version": "vacancy_evidence_adjudication.v1",
  "vacancy_id": "string",
  "generated_at": "datetime",
  "items": [
    {
      "item_id": "string",
      "item_index": 0,
      "group": "required_criteria | responsibilities | desirable_criteria | work_conditions | benefits | about_the_company",
      "group_code": "req | resp | des | cond | ben | about",
      "raw_text": "string",
      "criterion_type": "education | years_experience | leadership | technical_skill | project_management | transformation | business_outcome | certification | language | condition | cultural | other",
      "priority": "critical | important | desirable | contextual",
      "alignment_status": "direct | partial | indirect | not_evidenced | conflict | not_applicable",
      "evidence_strength": "high | medium | low | none",
      "proof_summary": "string",
      "best_supporting_evidence": [
        {
          "source_ref": "string",
          "block_title": "string",
          "section": "string",
          "snippet": "string",
          "why_it_supports": "string"
        }
      ],
      "weak_or_discarded_evidence": [
        {
          "source_ref": "string",
          "block_title": "string",
          "reason": "string"
        }
      ],
      "limitations": [
        "string"
      ],
      "candidate_risk": "none | low | medium | high",
      "cv_improvement_opportunity": "string",
      "confidence": "high | medium | low"
    }
  ],
  "warnings": []
}
```

### 6.6. Definiciones obligatorias

`direct`

La evidencia prueba claramente el criterio.

Ejemplo:

Vacante:

`Mínimo 5 años de experiencia profesional`

CV:

`20 años de experiencia profesional`

Resultado:

`direct / high`

`partial`

La evidencia cubre parte del criterio, pero no todo.

Ejemplo:

Vacante:

`Al menos 4 años liderando equipos técnicos multidisciplinarios, idealmente en empresas de tecnología`

CV:

`12 años liderando equipos multidisciplinarios`

Pero no aparece experiencia en empresas puramente tecnológicas.

Resultado:

`partial` o `direct` según interpretación

La parte `idealmente` no debe tratarse como bloqueador.

`indirect`

La evidencia es transferible o análoga.

Ejemplo:

Vacante:

`Asegurar excelencia técnica`

CV:

`Arquitectura empresarial, estándares, gobierno técnico`

Resultado:

`indirect` o `partial`

`not_evidenced`

No hay evidencia suficiente en los snippets.

No significa que el candidato no lo tenga.

`conflict`

Hay contradicción explícita o altamente probable.

Debe usarse poco.

`not_applicable`

El criterio no requiere comparación contra el CV.

Ejemplo:

- beneficios genéricos;
- descripción promocional de empresa;
- condiciones no contrastables.

### 6.7. Prompt recomendado para S6.5

> Actúa como evaluador senior de evidencia candidato-vacante.
>
> Tu tarea es decidir, de forma estrictamente grounded, si la evidencia recuperada del CV soporta cada criterio de la vacante.
>
> Entrada:
> - Criterios de la vacante con item_id, item_index, group_code, group y raw_text.
> - Evidencia recuperada del CV por criterio: snippets, source_ref, block_title, section, score y query_texts.
> - Contexto general del candidato, si está disponible.
> - Contexto general de la vacante, si está disponible.
>
> Reglas obligatorias:
> - Usa únicamente la evidencia proporcionada.
> - No inventes experiencia, certificaciones, cargos, sectores, herramientas, años de experiencia ni preferencias.
> - No conviertas similitud semántica en cumplimiento.
> - No conviertas ausencia de evidencia en incumplimiento.
> - No uses el score como prueba final; úsalo solo como pista auxiliar.
> - Evalúa si el snippet realmente prueba el criterio.
> - Si un snippet es semánticamente cercano pero no prueba el criterio, colócalo en weak_or_discarded_evidence.
> - Si el criterio incluye varias partes, evalúa si la evidencia cubre todas o solo algunas.
> - Si el criterio contiene una parte obligatoria y otra deseable, no penalices la parte deseable como bloqueador.
> - Si el criterio dice "idealmente", "deseable", "preferible" o equivalente, trátalo como deseable o contextual, no como requisito crítico.
> - Si la vacante no especifica algo, no lo inventes.
> - Si el CV tiene evidencia transferible pero no literal, clasifica como indirect o partial, según corresponda.
>
> Definiciones:
> - direct: la evidencia prueba claramente el criterio.
> - partial: la evidencia prueba una parte del criterio, pero no todo.
> - indirect: la evidencia es transferible o análoga, pero no equivalente.
> - not_evidenced: no hay evidencia suficiente en los snippets.
> - conflict: hay contradicción explícita con el criterio.
> - not_applicable: el criterio no requiere comparación contra el CV.
>
> Criterios de fuerza:
> - high: evidencia específica, concreta y suficiente; incluye cargo, logro, formación, tecnología, años, resultado o responsabilidad claramente relacionada.
> - medium: evidencia razonable pero incompleta o general.
> - low: evidencia débil, indirecta o demasiado amplia.
> - none: no hay evidencia útil.
>
> Salida:
> Responde exclusivamente JSON válido conforme al contrato vacancy_evidence_adjudication.v1.
> No incluyas markdown ni explicaciones fuera del JSON.

### 6.8. Criterios de aceptación

S6.5 debe:

- incluir todos los ítems evaluables;
- clasificar cada criterio;
- separar evidencia fuerte de evidencia débil;
- explicar por qué un snippet soporta o no soporta;
- no usar score como conclusión;
- no inventar información;
- distinguir `not_evidenced` de `conflict`.

## 7. Fase 5 — Rediseñar S7: resumen basado en adjudicación

### 7.1. Objetivo

S7 debe resumir la adjudicación de `S6.5`, no solo los scores de `S6`.

### 7.2. Nuevo input de S7

- `vacancy_evidence_adjudication.v1`
- `vacancy_evidence_analysis.v1`

S6 puede seguir como respaldo técnico, pero `S6.5` debe ser la fuente principal.

### 7.3. Nuevo output sugerido

Actualizar o crear:

`vacancy_alignment_summary.v2`

### 7.4. Contrato sugerido

```json
{
  "contract_version": "vacancy_alignment_summary.v2",
  "vacancy_id": "string",
  "generated_at": "datetime",
  "overall": {
    "total_items": 0,
    "direct_count": 0,
    "partial_count": 0,
    "indirect_count": 0,
    "not_evidenced_count": 0,
    "conflict_count": 0,
    "not_applicable_count": 0
  },
  "groups": {
    "required_criteria": {
      "total_items": 0,
      "direct_count": 0,
      "partial_count": 0,
      "indirect_count": 0,
      "not_evidenced_count": 0,
      "conflict_count": 0
    },
    "responsibilities": {
      "total_items": 0,
      "direct_count": 0,
      "partial_count": 0,
      "indirect_count": 0,
      "not_evidenced_count": 0,
      "conflict_count": 0
    },
    "desirable_criteria": {
      "total_items": 0,
      "direct_count": 0,
      "partial_count": 0,
      "indirect_count": 0,
      "not_evidenced_count": 0,
      "conflict_count": 0
    },
    "work_conditions": {
      "total_items": 0,
      "direct_count": 0,
      "partial_count": 0,
      "indirect_count": 0,
      "not_evidenced_count": 0,
      "conflict_count": 0
    }
  },
  "strengths": [
    {
      "item_id": "string",
      "raw_text": "string",
      "alignment_status": "direct",
      "evidence_strength": "high | medium",
      "proof_summary": "string"
    }
  ],
  "gaps": [
    {
      "item_id": "string",
      "raw_text": "string",
      "gap_type": "real_gap | not_evidenced_in_cv | partial_coverage | unclear_requirement | desirable_not_evidenced",
      "impact": "high | medium | low",
      "explanation": "string"
    }
  ],
  "review_items": [
    {
      "item_id": "string",
      "raw_text": "string",
      "reason": "string"
    }
  ],
  "risks": [
    {
      "item_id": "string",
      "risk": "string",
      "severity": "high | medium | low"
    }
  ]
}
```

### 7.5. Reglas de derivación

- `direct + high/medium` → posible fortaleza.
- `partial` → posible fortaleza parcial o brecha parcial.
- `indirect` → revisar como transferible.
- `not_evidenced` obligatorio → gap de evidencia.
- `not_evidenced` deseable → deseable no evidenciado.
- `conflict` → alerta o bloqueador.
- `idealmente` → no debe crear bloqueador.

## 8. Fase 6 — Rediseñar S8: reporte final centrado en la persona

### 8.1. Objetivo

S8 debe producir un reporte accionable para la persona candidata o su tutor.

Debe responder:

- ¿Conviene aplicar?
- ¿Qué tan defendible es la candidatura?
- ¿Dónde está fuerte?
- ¿Dónde hay brechas reales?
- ¿Qué no está demostrado en el CV?
- ¿Qué debería ajustar antes de aplicar?
- ¿Qué debería validar con reclutador?
- ¿Qué condiciones chocan con sus preferencias?

### 8.2. Nuevo contrato

Crear:

`vacancy_alignment_report.v2`

### 8.3. Estructura recomendada

```json
{
  "report": {
    "executive_summary": {
      "fit_level": "alto | medio_alto | medio | bajo | informacion_insuficiente",
      "final_recommendation": "Avanzar | Avanzar con reservas | Avanzar si se valida X | No priorizar | Descartar",
      "summary": "string",
      "main_strength": "string",
      "main_gap_or_risk": "string",
      "confidence": "alta | media | baja"
    },
    "decision_table": {
      "alineacion_general": {
        "resultado": "🟢 Cumple | 🟡 Parcial | ⚪ Sin informacion | 🔴 En conflicto",
        "descripcion_corta": "string"
      },
      "fit_objetivo": {
        "resultado": "🟢 Cumple | 🟡 Parcial | ⚪ Sin informacion | 🔴 En conflicto",
        "descripcion_corta": "string"
      },
      "fit_preferencial": {
        "resultado": "🟢 Cumple | 🟡 Parcial | ⚪ Sin informacion | 🔴 En conflicto",
        "descripcion_corta": "string"
      },
      "requisitos_criticos_cumplidos": {
        "resultado": "string",
        "descripcion_corta": "string"
      },
      "bloqueadores": {
        "resultado": "string",
        "descripcion_corta": "string"
      },
      "alertas_relevantes": {
        "resultado": "string",
        "descripcion_corta": "string"
      },
      "potencial_mejora_fit": {
        "resultado": "string",
        "descripcion_corta": "string"
      },
      "recomendacion": {
        "resultado": "Avanzar | Avanzar con reservas | Avanzar si se valida X | No priorizar | Descartar",
        "descripcion_corta": "string"
      }
    },
    "vacancy_fit_matrix": [
      {
        "item_id": "string",
        "criterio": "string",
        "categoria": "Experiencia | Herramientas | Conocimientos | Formación | Certificaciones | Idioma | Responsabilidades | Condiciones laborales | Cultura y entorno",
        "origen_del_criterio": "Vacante obligatoria | Vacante deseable | Vacante condición",
        "prioridad": "Crítica | Importante | Deseable | Contextual",
        "estado": "🟢 Cumple | 🟡 Parcial | ⚪ Sin informacion | 🔴 En conflicto | 🔵 Deseable no evidenciado",
        "lo_que_solicita_la_vacante": "string",
        "evidencia_del_candidato": "string",
        "tipo_de_evidencia": "directa | parcial | indirecta | no evidenciada | conflicto | no aplicable",
        "fuerza_de_evidencia": "alta | media | baja | ninguna",
        "descripcion_corta": "string",
        "riesgo_para_la_postulacion": "ninguno | bajo | medio | alto",
        "fuentes": [
          "source_ref"
        ]
      }
    ],
    "candidate_preference_matrix": [
      {
        "criterio": "string",
        "categoria": "Condiciones laborales | Cultura y entorno | Compensación | Modalidad | Ubicación | Rol | Otro",
        "origen_del_criterio": "Preferencia del candidato",
        "estado": "🟢 Cumple | 🟡 Parcial | ⚪ Sin informacion | 🔴 En conflicto",
        "lo_que_ofrece_o_define_la_vacante": "string",
        "preferencia_o_condicion_del_candidato": "string",
        "descripcion_corta": "string",
        "validacion_recomendada": "string"
      }
    ],
    "fit_answer": {
      "encaja": "sí | parcialmente | no | información insuficiente",
      "respuesta_para_el_candidato": "string"
    },
    "strengths": [
      {
        "fortaleza": "string",
        "por_que_importa": "string",
        "evidencia": "string"
      }
    ],
    "gaps": [
      {
        "brecha": "string",
        "tipo": "brecha real | no demostrado en CV | requisito ambiguo | deseable no evidenciado",
        "impacto": "alto | medio | bajo",
        "accion_recomendada": "string"
      }
    ],
    "preference_conflicts": [
      {
        "criterio": "string",
        "estado": "conflicto | incertidumbre | alineado parcialmente",
        "descripcion": "string",
        "validacion_recomendada": "string"
      }
    ],
    "improvement_actions": {
      "reinforce_in_cv_or_profile": [
        "string"
      ],
      "validate_with_recruiter": [
        "string"
      ],
      "application_narrative": [
        "string"
      ]
    },
    "alerts_and_conflicts": [
      {
        "tipo": "bloqueador | alerta | ambiguedad | conflicto_preferencia",
        "severidad": "alta | media | baja",
        "descripcion": "string"
      }
    ],
    "actionable_conclusion": {
      "final_decision": "Avanzar | Avanzar con reservas | Avanzar si se valida X | No priorizar | Descartar",
      "main_reason": "string",
      "recommended_next_step": "string",
      "confidence": "alta | media | baja"
    }
  },
  "rendered_markdown": "string"
}
```

### 8.4. Prompt recomendado para S8

> Actúa como analista senior de alineación candidato-vacante, orientado a ayudar al candidato y/o a su tutor a decidir si conviene priorizar esta vacante.
>
> Responde SOLO JSON válido conforme a vacancy_alignment_report.v2.
> No escribas texto fuera del JSON.
> Debes producir exactamente dos claves raíz: report, rendered_markdown.
>
> Perspectiva del análisis:
> - El análisis se escribe para el candidato, no para la empresa.
> - El objetivo es decidir si conviene avanzar, qué tan defendible es la postulación y qué debe ajustar o validar.
> - Separa siempre fit objetivo y fit preferencial.
>
> Insumos:
> - person_context: perfil, experiencia, preferencias laborales, expectativas, restricciones y notas abiertas del candidato.
> - opportunity_context: información completa de la vacante, incluyendo snapshot_raw_text.
> - vacancy_evidence_adjudication.v1: evaluación grounded por criterio. Este es el insumo principal para determinar cumplimiento, parcialidad, evidencia indirecta, ausencia de evidencia o conflicto.
> - vacancy_alignment_summary.v2: resumen cuantitativo auxiliar.
> - vacancy_evidence_analysis.v1: evidencia técnica recuperada. Úsala solo como respaldo, no como conclusión.
>
> Reglas obligatorias de grounding:
> - No inventes información.
> - No inventes sectores, años, certificaciones, herramientas, preferencias, salario, modalidad ni condiciones.
> - No conviertas ausencia de evidencia en incumplimiento.
> - No conviertas similitud semántica en cumplimiento.
> - No contradigas la adjudicación de evidencia salvo que señales una inconsistencia explícita en limitations.
> - No recalcules scores.
> - No uses el score como justificación principal.
> - No omitas criterios evaluados relevantes.
> - La matriz vacancy_fit_matrix debe incluir todos los criterios evaluados en vacancy_evidence_adjudication.v1.
> - Si un criterio está clasificado como direct, usa 🟢 Cumple.
> - Si está clasificado como partial o indirect, usa 🟡 Parcial.
> - Si está clasificado como not_evidenced y el criterio es obligatorio, usa ⚪ Sin informacion.
> - Si está clasificado como not_evidenced y el criterio es deseable, usa 🔵 Deseable no evidenciado.
> - Usa 🔴 En conflicto solo si existe contradicción explícita o altamente probable.
> - Si la vacante no especifica una condición y el candidato sí tiene una preferencia, usa ⚪ Sin informacion.
> - Si una condición de la vacante es "ideal", "deseable" o "preferible", no la trates como bloqueador.
>
> Reglas de interpretación:
> - Distingue entre:
>   1. "no parece tenerlo": solo cuando hay evidencia razonable de ausencia o contradicción.
>   2. "no está demostrado": cuando no hay evidencia suficiente.
>   3. "la vacante no lo especifica": cuando falta información de la vacante.
> - Evalúa si el candidato tiene una narrativa defendible para aplicar.
> - Identifica brechas reales y brechas de comunicación del CV.
> - Identifica qué debe validar con reclutador antes de invertir esfuerzo.
> - No infles el perfil del candidato.
> - No penalices al candidato por información que la vacante no pide.
>
> Recomendaciones finales permitidas:
> - Avanzar
> - Avanzar con reservas
> - Avanzar si se valida X
> - No priorizar
> - Descartar
>
> Estructura obligatoria dentro de report:
> - executive_summary
> - decision_table
> - vacancy_fit_matrix
> - candidate_preference_matrix
> - fit_answer
> - strengths
> - gaps
> - preference_conflicts
> - improvement_actions
> - alerts_and_conflicts
> - actionable_conclusion
>
> rendered_markdown:
> Debe reflejar el mismo contenido del JSON.
> Debe incluir las secciones en este orden exacto:
> ## Resumen ejecutivo
> ## Matriz de alineación
> ### Ajuste frente a la vacante
> ### Ajuste frente a preferencias y condiciones del candidato
> ## 1. ¿Encaja con la vacante?
> ## 2. ¿Qué tiene a favor?
> ## 3. ¿Qué le falta o no está demostrado?
> ## 4. ¿Qué choca con sus preferencias o condiciones?
> ## 5. ¿Qué debería ajustar o mejorar para aumentar su fit?
> ## Alertas y conflictos
> ## Conclusión accionable
>
> Control de completitud:
> Antes de responder, verifica internamente:
> - número de criterios en vacancy_evidence_adjudication.v1
> - número de filas en vacancy_fit_matrix
> Ambos deben coincidir, salvo criterios not_applicable justificados explícitamente.
>
> Persona:
> {person_context}
>
> Vacante:
> {opportunity_context}
>
> Entrada vacancy_evidence_adjudication.v1:
> {evidence_adjudication_json}
>
> Entrada vacancy_alignment_summary.v2:
> {alignment_summary_json}
>
> Entrada vacancy_evidence_analysis.v1:
> {evidence_analysis_json}

## 9. Fase 7 — Validaciones automáticas posteriores a S8

### 9.1. Objetivo

Evitar reportes incompletos o no conformes al contrato.

### 9.2. Validaciones obligatorias

Después de S8, implementar validaciones determinísticas:

Validación 1 — JSON válido

El output debe parsear como JSON.

Validación 2 — claves raíz

Debe tener exactamente:

```json
{
  "report": {},
  "rendered_markdown": ""
}
```

Validación 3 — completitud de matriz

Comparar:

- número de items evaluables en S6.5
- vs
- número de filas en `vacancy_fit_matrix`

Si no coinciden, marcar error o regenerar S8.

Validación 4 — estados permitidos

Solo permitir:

- `🟢 Cumple`
- `🟡 Parcial`
- `⚪ Sin informacion`
- `🔴 En conflicto`
- `🔵 Deseable no evidenciado`

Validación 5 — recomendaciones permitidas

Solo permitir:

- `Avanzar`
- `Avanzar con reservas`
- `Avanzar si se valida X`
- `No priorizar`
- `Descartar`

Validación 6 — no contradicción entre S6.5 y S8

Mapeo obligatorio:

```text
direct                         → 🟢 Cumple
partial                        → 🟡 Parcial
indirect                       → 🟡 Parcial
not_evidenced + obligatorio    → ⚪ Sin informacion
not_evidenced + deseable       → 🔵 Deseable no evidenciado
conflict                       → 🔴 En conflicto
```

Validación 7 — no inventar criterios

Cada fila de `vacancy_fit_matrix` debe corresponder a un `item_id` existente en `S6.5`.

Validación 8 — preference matrix

Si existen preferencias del candidato y condiciones comparables en la vacante, `candidate_preference_matrix` no debe ir vacía.

Si no hay información suficiente, debe registrar incertidumbre, no conflicto.

## 10. Fase 8 — Ajustes de retrieval

### 10.1. Configuración recomendada inicial

```text
embedding_model = text-embedding-3-small
chunking = semantic_sections
chunk_size = 700 tokens
overlap = 12%
retrieval_queries_per_item = 4
top_k_semantic_per_criterion = 6
```

### 10.2. Ajuste posterior recomendado

Después de probar `S6.5`:

`top_k_semantic_per_criterion = 8`

Solo si se observa que faltan evidencias relevantes.

### 10.3. No implementar híbrida de inmediato

La búsqueda híbrida puede ayudar, pero no es el primer cambio.

Primero implementar:

- mejores queries;
- `S6.5`;
- validación de completitud;
- ajuste de `top_k`.

Después evaluar híbrida/BM25 si persisten problemas con términos exactos como:

- `PMP`,
- `Scrum`,
- `TOGAF`,
- `Power Platform`,
- `Azure`,
- `SAP`,
- `Salesforce`,
- inglés,
- certificaciones específicas.

## 11. Fase 9 — Observabilidad y trazabilidad

### 11.1. Guardar trazas completas

Para cada oportunidad, guardar:

- prompt usado en `S2`;
- prompt usado en `S3`;
- prompt usado en `S4`;
- prompt usado en `S6.5`;
- prompt usado en `S8`;
- input completo;
- output completo;
- modelo usado;
- temperatura;
- versión de contrato;
- timestamp;
- `flow_key`;
- `prompt_version`.

### 11.2. Trazas prioritarias

S8 debe tener trazas completas porque fue un punto de falla observado:

`No hay trazas cargadas de S8 para esta oportunidad.`

Eso debe corregirse.

### 11.3. Métricas recomendadas

Guardar métricas por corrida:

- `items_total`
- `items_direct`
- `items_partial`
- `items_indirect`
- `items_not_evidenced`
- `items_conflict`
- `matrix_rows_count`
- `missing_matrix_items_count`
- `s8_regeneration_count`
- `json_validation_errors`
- `contract_validation_errors`

## 12. Fase 10 — Dataset de pruebas

### 12.1. Crear set mínimo de validación

Usar al menos 10 vacantes reales:

- Vacante de transformación digital.
- Vacante de gerente/director TI.
- Vacante de arquitectura empresarial.
- Vacante de data/analytics.
- Vacante con requisitos técnicos específicos.
- Vacante con certificaciones obligatorias.
- Vacante con inglés obligatorio.
- Vacante con salario/modalidad explícitos.
- Vacante con texto pobre o ambiguo.
- Vacante con muchos beneficios/cultura y pocos requisitos técnicos.

### 12.2. Golden outputs

Para cada vacante, construir manualmente o semimanualmente:

- criterios esperados;
- evidencias esperadas;
- clasificación esperada;
- recomendación esperada.

### 12.3. Evaluar antes/después

Comparar pipeline actual vs pipeline nuevo en:

- completitud de criterios
- precisión de evidencias
- reducción de alucinaciones
- calidad de recomendación
- utilidad para ajustar CV
- claridad de fit objetivo
- claridad de fit preferencial

## 13. Resultado esperado para el caso de prueba actual

Para la vacante `Líder Estratégico en Transformación Digital`, el pipeline nuevo debería producir una matriz cercana a esta interpretación:

| Criterio | Estado esperado | Interpretación esperada |
| --- | --- | --- |
| Formación profesional en Ingeniería o afines | `🟢 Cumple` | Ingeniero Industrial, MBIT y Especialización. |
| Mínimo 5 años de experiencia profesional | `🟢 Cumple` | Evidencia directa de 20 años de experiencia. |
| 4 años liderando equipos técnicos multidisciplinarios | `🟢 Cumple` | Evidencia de 12 años liderando equipos. |
| Idealmente empresas de tecnología | `🟡 Parcial` | Experiencia en TI/consultoría/sectores regulados; no necesariamente empresa tecnológica pura. No es bloqueador. |
| Gestión de proyectos de transformación digital, automatización, desarrollo o consultoría tecnológica | `🟢 Cumple` | Evidencia fuerte en transformación digital, Power Platform, arquitectura y consultoría tecnológica. |
| Liderar área de servicios digitales | `🟡 Parcial` | Hay liderazgo de áreas TI/servicios tecnológicos; `servicios digitales` como unidad específica no está literal. |
| Excelencia técnica | `🟡 Parcial` | Evidencia indirecta por arquitectura, estándares y gobierno técnico. |
| Eficiencia operativa | `🟢 Cumple` | Evidencia directa: 40% reducción de carga administrativa/manual. |
| Rentabilidad de proyectos de transformación digital | `🟡 Parcial` | Hay presupuesto, eficiencia y cumplimiento tiempo/costo/alcance; no necesariamente rentabilidad/P&L explícita. |
| Articular equipos multidisciplinarios, clientes y áreas internas | `🟢 Cumple` | Evidencia de coordinación de equipos, áreas, stakeholders y consultoría. |
| Certificación PMP/Scrum o similares | `🟡 Parcial` o `🔵 Deseable no evidenciado` | Hay curso Scrum; no se evidencia certificación PMP/Scrum formal. Como es deseable, no es bloqueador. |

## 14. Orden recomendado de implementación

### Sprint 1 — Correcciones rápidas

- Ajustar prompt S3 para preservar contexto mínimo.
- Ajustar prompt S4 para queries probatorias.
- Subir `retrieval_queries_per_item` a `4`.
- Subir `top_k_semantic_per_criterion` a `6`.
- Corregir trazas completas de `S8`.

### Sprint 2 — Nuevo S6.5

- Crear contrato `vacancy_evidence_adjudication.v1`.
- Crear prompt `task_vacancy_evidence_adjudication`.
- Implementar servicio `S6.5`.
- Persistir artefacto `S6.5`.
- Ejecutar `S6.5` sobre 5 vacantes reales.
- Revisar calidad de clasificación.

### Sprint 3 — Rediseñar S7

- Crear `vacancy_alignment_summary.v2`.
- Hacer que `S7` consuma `S6.5`.
- Separar conteos `direct/partial/indirect/not_evidenced/conflict`.
- Recalcular `strengths/gaps` desde adjudicación, no desde score.

### Sprint 4 — Rediseñar S8

- Crear contrato `vacancy_alignment_report.v2`.
- Ajustar prompt `S8`.
- Incluir `S6.5` como insumo principal.
- Agregar control de completitud.
- Agregar validación `JSON/schema`.
- Agregar regeneración automática si falta completitud.

### Sprint 5 — Evaluación y calibración

- Construir dataset de 10 vacantes.
- Comparar outputs actuales vs nuevos.
- Ajustar prompt `S6.5`.
- Ajustar prompt `S8`.
- Revisar thresholds.
- Definir configuración recomendada de producción.

## 15. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| `S6.5` aumenta costo y latencia | Medio | Ejecutar por lote, limitar evidencias por ítem, usar solo `best_evidence + accepted_matches` deduplicados. |
| `S6.5` puede alucinar | Alto | Prompt estricto, schema, `source_refs` obligatorios, validación de no inventar. |
| `S8` sigue omitiendo criterios | Alto | Validación automática de número de filas vs número de ítems `S6.5`. |
| Más queries generan más ruido | Medio | `S6.5` filtra evidencia débil; ajustar `top_k` gradualmente. |
| Contratos `v2` rompen UI actual | Medio | Mantener compatibilidad temporal con `v1` o crear adaptador. |
| Criterios abstractos siguen débiles | Medio | Ajustar `S3` y `S4` con contexto mínimo + queries probatorias. |
| Preferencias del candidato mal interpretadas | Medio | Separar matriz de preferencias y usar `Sin información` cuando la vacante no especifique. |

## 16. Definition of Done

El rediseño puede considerarse exitoso cuando:

- `S8` incluye todos los criterios evaluados relevantes.
- El reporte diferencia evidencia directa, parcial, indirecta y no evidenciada.
- No aparecen brechas inventadas por sectores, herramientas o condiciones no solicitadas.
- Los deseables no se tratan como bloqueadores.
- Las preferencias del candidato se evalúan separadamente.
- El reporte final ayuda a decidir si aplicar, no solo a resumir coincidencias.
- El sistema produce acciones concretas para:
  - ajustar CV,
  - validar con reclutador,
  - construir narrativa de postulación.
- La salida JSON cumple contrato.
- `rendered_markdown` refleja el JSON.
- Existen trazas completas para depuración.

## 17. Decisión recomendada

Implementar el rediseño en este orden:

`S3 prompt adjustment`
→ `S4 prompt adjustment`
→ `S6 semantic reinterpretation`
→ `S6.5 new LLM adjudication step`
→ `S7 v2 summary`
→ `S8 v2 report`
→ `validations and regression dataset`

No recomiendo intentar corregir únicamente `S8`.
El problema ya viene contaminado desde `S6/S7`, donde la similitud semántica se convierte en `fortaleza`.
