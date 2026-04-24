# Vacancy Structure Contract V2

## Proposito
Definir un contrato propuesto para la estructura de vacante sin tocar el extractor legacy estable ni el flujo analitico vigente.

Fuente ejecutable de verdad:
- `apps/backend/app/services/vacancy_structure_contract_v2.py`

Estado:
- `draft`
- no integrado al extractor actual
- no integrado a UI ni a `JobCriteriaMapper`
- decision vigente de diseno: `v2` arranca sin `JobCriteriaMapper`
- decision vigente de diseno: Paso 2 persiste como artefacto consultable en BD

## Objetivos de diseno
- mover la vacante estructurada hacia un contrato centrado en contenido evaluable
- evitar que el esquema obligue a mezclar listas legacy (`requisitos_*`, `condiciones_trabajo`) con semanticas distintas
- separar `role_properties` de `criteria[]`
- dejar `criteria[]` como unica fuente de verdad para todo lo evaluable
- mantener `summary`, `confidence` y `extraction_source` como metadatos compactos
- eliminar `JobCriteriaMapper` del diseno objetivo; si reaparece una capa intermedia, debera justificarse desde cero y no como arrastre del baseline

## Decisiones cerradas hasta ahora
- Paso 2 se persiste como artefacto consultable en base de datos
- mientras no haya migracion formal, ese artefacto puede vivir en `vacancy_profile` para no romper la logica actual
- Paso 2 usa claves fijas; no se permiten claves arbitrarias creadas por el modelo
- Paso 2 debe incluir `contract_version` explicito en la raiz del artefacto
- Paso 2 debe incluir `vacancy_id` explicito en la raiz del artefacto
- Paso 2 debe incluir `generated_at` explicito en la raiz del artefacto
- si hay contenido que no encaja, debe ir a `unclassified` y/o reflejarse en `warnings` y `coverage_notes`
- en esta version, Paso 2 guarda texto limpio por bloque y no offsets ni trazabilidad posicional
- Paso 2 puede fragmentar un mismo parrafo o lista en multiples piezas si eso es necesario para clasificar toda la vacante con precision
- si una misma oracion contiene requisitos separables, Paso 2 debe dividirlos en fragmentos distintos en lugar de duplicar texto completo en varias dimensiones
- solo cuando un fragmento quede semanticamente inseparable, se asigna una dimension principal y se deja advertencia
- `work_conditions` se define en version amplia controlada: incluye condiciones comparables por logica y tambien condiciones operativas o de elegibilidad del puesto
- cada bloque de `vacancy_blocks` persiste una lista de `string`
- `warnings` y `coverage_notes` son globales al artefacto de Paso 2, no por bloque
- `warnings` y `coverage_notes` se tratan como opcionales a nivel semantico, pero la forma canonica persistida los mantiene presentes como arrays globales
- Paso 3 produce un artefacto atomizado nuevo y no embebe `vacancy_blocks` dentro del JSON final
- Paso 2 y Paso 3 quedan consultables por separado
- Paso 3 se orienta por `vacancy_dimensions`; se descarta el lenguaje `searchable_requirements`
- Paso 3 debe incluir `contract_version` explicito en la raiz del artefacto
- Paso 3 debe incluir `vacancy_id` explicito en la raiz del artefacto
- Paso 3 debe incluir `generated_at` explicito en la raiz del artefacto

## TODO de revision de contrato
### TODO. Alinear naming entre Paso 2 y Paso 3 sin colapsar ambos artefactos
Estado:
- `pendiente de decision`
- no implementado
- no cambia contratos ejecutables actuales

Recomendacion actual:
- si conviene normalizar el vocabulario entre Paso 2 y Paso 3
- no conviene renombrar la raiz de Paso 2 a `vacancy_dimensions`
- si conviene evaluar una clave `about_the_company` en Paso 2
- antes de elegir `required_competencies` para Paso 2, cerrar si el artefacto intermedio modela `competencies` o `criteria`

Propuesta defendida por ahora:
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
  }
}
```

Razon:
- mantiene separado el artefacto intermedio de Paso 2 respecto al artefacto final `vacancy_dimensions.v1`
- reduce friccion cognitiva entre pasos sin hacer que ambos parezcan el mismo contrato
- `required_criteria` y `desirable_criteria` describen mejor el contenido amplio de Paso 2 que `required_competencies`
- `about_the_company` permite recoger senales de empresa, sector, posicionamiento y contexto corporativo que hoy pueden perderse o caer en `unclassified`

Impacto esperado si se adopta luego:
- actualizar contrato y normalizador de Paso 2
- actualizar prompt y parser de Step 2
- actualizar fixtures y pruebas de Step 2, Step 3, endpoints y gate
- actualizar documentacion normativa y operativa
- definir estrategia de compatibilidad de lectura para artefactos ya persistidos en Firestore

## Contrato propuesto para Paso 2
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

## Criterio de contrato para arrays globales
- `warnings` y `coverage_notes` pueden estar vacios
- semantica: son opcionales porque no siempre habra observaciones
- alcance: ambas claves son globales al artefacto y no viven dentro de `vacancy_blocks`
- contrato persistido recomendado: mantener ambas claves siempre presentes con `[]`

Razon:
- simplifica validacion
- evita bifurcaciones innecesarias en UI y backend
- hace mas estable la lectura del artefacto entre corridas

## Regla de Paso 2
- Paso 2 clasifica y limpia
- Paso 2 no resume
- Paso 2 no atomiza
- Paso 2 no inventa claves nuevas
- Paso 2 debe hacer visible el ruido o la ambiguedad, no ocultarlo dentro de una categoria incorrecta
- la unidad de clasificacion es el fragmento semantico minimo util, no necesariamente el parrafo completo
- un mismo parrafo puede aportar contenido a mas de una clave si mezcla dimensiones distintas
- no se debe duplicar por defecto el mismo fragmento completo en varios bloques
- si el texto expresa dos exigencias distintas, debe separarse en dos fragmentos y cada uno va a su bloque
- si el texto no puede separarse limpiamente, va al bloque de dimension principal y se reporta en `warnings` o `coverage_notes`
- cada clave de `vacancy_blocks` guarda una coleccion de fragmentos clasificados y no un `string` concatenado
- el uso de `;` puede servir para render o export, pero no debe ser la forma canonica persistida

## Regla de solapamiento
Ejemplo:
- `Experiencia en metodologias agiles y certificacion Scrum deseable`

Salida esperada:
- fragmento 1 a `required_criteria`: `Experiencia en metodologias agiles`
- fragmento 2 a `desirable_criteria`: `Certificacion Scrum deseable`

Principio:
- separar cuando haya dos requisitos semanticamente distinguibles
- evitar duplicacion literal del mismo texto entre bloques

## Regla de `work_conditions`
`work_conditions` debe capturar:
- salario, modalidad, ubicacion, horario, tipo de contrato, disponibilidad, viajes
- y tambien condiciones operativas o de elegibilidad del puesto cuando no son una competencia profesional en si mismas

Ejemplos que si van a `work_conditions`:
- `Disponibilidad para viajar 30%`
- `Guardias nocturnas durante cierres`
- `Permiso de trabajo vigente en Colombia`
- `Vehiculo propio para visitar clientes`
- `Disponibilidad para trabajar algunos sabados`
- `Residencia en ciudad con aeropuerto principal`

Ejemplos que no van a `work_conditions`:
- `Ingles B2`
- `Certificacion Scrum`
- `5 anos de experiencia en ventas B2B`
- `Dominio de SQL`
- `Experiencia liderando equipos`

Regla practica:
- si responde a `bajo que condiciones se ejerce o se puede ejercer este trabajo`, va a `work_conditions`
- si responde a `que sabe, tiene o demuestra el candidato como perfil profesional`, va a `required_criteria` o `desirable_criteria`

## Regla de `about_the_company`
`about_the_company` debe capturar contexto corporativo que ayude a interpretar la vacante, pero que no sea responsabilidad, criterio de candidato ni condicion operativa del puesto.

Ejemplos que si van a `about_the_company`:
- `Empresa lider en transformacion digital para banca y seguros`
- `Compania multinacional con presencia en 12 paises`
- `Empresa del sector salud enfocada en atencion domiciliaria`
- `Organizacion nacional con operaciones en Colombia y Peru`

Ejemplos que no van a `about_the_company`:
- `Experiencia en sector retail`
- `Disponibilidad para viajar`
- `Liderar el equipo de analitica`

Regla practica:
- si describe quien es la empresa, en que sector opera, su escala, posicionamiento o contexto corporativo, va a `about_the_company`
- si describe lo que debe hacer, saber o cumplir la persona candidata, no va a `about_the_company`

## Forma canonica de `vacancy_blocks`
Cada bloque debe persistirse como lista de fragmentos limpios.

Ejemplo:
```json
{
  "vacancy_blocks": {
    "responsibilities": [
      "Realizar el levantamiento de necesidades de datos a traves de un flujo de procesos arquitectonico.",
      "Organizar workshops, entrevistas y analisis de procesos con stakeholders clave.",
      "Documentar y modelar procesos de negocio utilizando herramientas y metodologias reconocidas.",
      "Establecer relaciones claras entre procesos de negocio y activos de TI."
    ]
  }
}
```

Razon:
- preserva granularidad util para Paso 3
- evita tener que volver a partir texto unido artificialmente
- mantiene estable el contrato aunque luego la UI lo renderice unido o en lista

## Contrato propuesto
```json
{
  "contract_version": "vacancy_structure.v2",
  "summary": "",
  "role_properties": {
    "organizational_level": "no_especificado",
    "company_type": "no_especificado",
    "sector": "no_especificado"
  },
  "criteria": [
    {
      "criterion_id": "criterion_1_minimo_8_anos_liderando_equipos_comerciales",
      "label": "Minimo 8 anos liderando equipos comerciales",
      "priority": "required",
      "vacancy_dimension": "experience",
      "category": "years_of_experience",
      "raw_text": "Debe acreditar minimo 8 anos liderando equipos comerciales",
      "normalized_value": {
        "years_min": 8
      },
      "metadata": {
        "source_section": "requirements"
      }
    }
  ],
  "confidence": "medium",
  "extraction_source": "llm"
}
```

## Reglas semanticas
- `summary`: sintesis breve de la vacante. No reemplaza `criteria[]`.
- `role_properties`: contexto de rol/empresa que ayuda a interpretar la vacante, pero que no siempre se evalua criterio a criterio.
- `criteria[]`: lista canonica de items evaluables.
- `priority`:
  - `required`: condicion necesaria para avanzar
  - `preferred`: diferenciador deseable
  - `constraint`: condicion operativa o de elegibilidad
  - `signal`: senal contextual util pero no decisiva por si sola
- `vacancy_dimension`: eje estable para retrieval, evaluacion y UI.
- `category`: subclasificacion puntual dentro de la dimension.
- `raw_text`: evidencia textual anclada a la vacante. Debe evitar labels vacios o demasiado genericos.
- `normalized_value`: estructura opcional para valores comparables (`years_min`, `currency`, `mode`, etc.).
- `metadata`: espacio tecnico controlado para trazabilidad, no para inventar semantica nueva.

## Diferencias frente al contrato legacy
- `seniority` deja de ser campo top-level y pasa a `criteria[]`
- `requisitos_obligatorios`, `requisitos_deseables` y `condiciones_trabajo` dejan de ser buckets separados
- `criteria[]` incorpora prioridad explicita en vez de depender del nombre del bucket
- `role_properties` queda reducido a contexto de interpretacion
- no existe una fase `vacancy_profile -> mapped_criteria`; el contrato `v2` debe nacer ya orientado a consumo analitico

## Limites de esta iteracion
- no hay migracion automatica desde `vacancy_profile` legacy
- no hay compatibilidad runtime con el extractor actual
- no hay cambios en prompts activos
- no hay cambios en backend/frontend productivo
- no hay trazabilidad por offsets, lineas o `char_ranges` en Paso 2 para esta version

## Separacion entre Paso 2 y Paso 3
- Paso 2 conserva su propio artefacto consultable de segmentacion contextual
- Paso 3 toma Paso 2 como insumo, pero produce un artefacto nuevo orientado a atomizacion semantica
- el artefacto final de Paso 3 no debe duplicar `vacancy_blocks` en su payload canonico
- si en algun momento se requiere navegacion entre ambos, esa relacion debe resolverse por referencia/versionado y no copiando el contenido de Paso 2 dentro de Paso 3
- ambos artefactos deben poder identificarse por si mismos con `contract_version` y `vacancy_id`
- ambos artefactos deben indicar explicitamente cuando fueron generados mediante `generated_at`
- `artifact_id` queda fuera del contrato canonico por ahora y se resuelve en persistencia mientras no se cierre un requisito formal de historial

## Propuesta acordada para Paso 3 siguiente
```json
{
  "contract_version": "vacancy_dimensions.v2",
  "vacancy_id": "VAL-123",
  "generated_at": "2026-04-23T10:31:05-05:00",
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
        "raw_text": "..."
      }
    ],
    "required_criteria": [
      {
        "raw_text": "..."
      }
    ],
    "desirable_criteria": [
      {
        "raw_text": "..."
      }
    },
    "benefits": [
      {
        "raw_text": "..."
      }
    ],
    "about_the_company": [
      {
        "raw_text": "..."
      }
    ]
  }
}
```

## Lectura acordada para Paso 3 siguiente
- `contract_version` vive en la raiz del artefacto final para versionado y compatibilidad
- `work_conditions` queda reducido a un set pequeno y util: `salary`, `modality`, `location`, `contract_type`, `other_conditions`
- dentro de Paso 3, `salary` solo preserva `raw_text`
- `responsibilities`, `required_criteria`, `desirable_criteria`, `benefits` y `about_the_company` quedan como listas homogeneas de items minimos
- cada item atomico queda como objeto con solo `raw_text`
- Paso 3 no asigna `id`
- Paso 3 no asigna `category`
- Paso 3 no genera campo resumido por item
- Paso 3 no genera `semantic_queries`
- `about_the_company` sobrevive en Paso 3 para no perder contexto corporativo capturado en Paso 2
- la responsabilidad de formular consultas semanticas se mueve a un paso posterior separado

## Set acordado para `work_conditions` en Paso 3 siguiente
Las subclaves canonicas de `work_conditions` quedan reducidas en esta propuesta a:
- `salary`
- `modality`
- `location`
- `contract_type`
- `other_conditions`

No se deben inventar subclaves nuevas fuera de este set sin aprobacion explicita.

## Campos minimos acordados por item atomico
Las listas atomicas de:
- `responsibilities`
- `required_criteria`
- `desirable_criteria`
- `benefits`
- `about_the_company`
- `other_conditions`

deben mantenerse solo con estos campos minimos:
- `raw_text`

No se deben agregar en esta iteracion campos extra de normalizacion ligera o avanzada sin aprobacion explicita.

## Regla acordada para `category`
- `category` queda fuera de Paso 3
- si mas adelante reaparece, debe justificarse en un paso posterior por valor analitico o de presentacion
- no debe volver a introducirse en Paso 3 sin decision explicita

## Convencion de valores vacios para Paso 3
- las subclaves de `work_conditions` permanecen siempre presentes
- `string` sin dato: `""`
- `number` sin dato: `null`
- `boolean` sin dato: `null`
- `array` sin dato: `[]`
- los objetos estructurales permanecen presentes aunque sus campos internos esten vacios

Ejemplo:
```json
{
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
    "other_conditions": []
  },
  "responsibilities": [],
  "required_criteria": [],
  "desirable_criteria": [],
  "benefits": [],
  "about_the_company": []
}
```

## Paso 3.1 propuesto para salario
Objetivo:
- resolver la normalizacion de salario como responsabilidad separada por su estructura distinta al resto de items

Input:
- artefacto `vacancy_dimensions.v2`
- especificamente `work_conditions.salary.raw_text`

Output esperado:
```json
{
  "contract_version": "vacancy_salary_normalization.v1",
  "vacancy_id": "VAL-123",
  "generated_at": "2026-04-23T10:33:00-05:00",
  "salary": {
    "min": null,
    "max": null,
    "currency": "",
    "period": "",
    "raw_text": ""
  }
}
```

Regla:
- Paso 3.1 no reatomiza responsabilidades ni criterios
- Paso 3.1 no genera queries
- Paso 3.1 se limita a salario
- Paso 3.1 requiere `salary.raw_text` no vacio para ejecutarse
- si no hay evidencia suficiente, conserva defaults y preserva `raw_text` cuando exista senal salarial parcial

Razon:
- salario tiene una estructura distinta al resto de los items atomicos
- separarlo reduce carga cognitiva sobre `4o-mini`
- permite medir con mas claridad la calidad de la normalizacion salarial sin mezclarla con la atomizacion general

## Paso 3.9 propuesto para enriquecimiento deterministico
Objetivo:
- asignar referencias tecnicas estables y operativas a cada item atomico antes de `Paso 4`

Naturaleza del paso:
- programatico
- no usa LLM
- no reclasifica
- no resume
- no deduplica silenciosamente
- no genera `semantic_queries`

Artefacto propuesto:
- `vacancy_dimensions_enriched.v1`

Campos por item:
- `item_id`: fingerprint estable del contenido
- `item_index`: posicion del item dentro de su lista padre
- `group_code`: codigo corto del grupo padre (`resp`, `req`, `des`, `ben`, `comp`, `cond`)

Regla recomendada:
- `item_id` se construye con un prefijo por `group_code` y los primeros `10` caracteres hex de un `sha256`
- la entrada al hash se fija como `vacancy_id + "|" + group_code + "|" + normalized_raw_text`
- `item_index` se persiste aparte y no se embebe dentro de `item_id`

Normalizacion previa de `raw_text` para el hash:
- `trim` de espacios al inicio y al final
- convertir saltos de linea y tabs a espacios simples
- colapsar multiples espacios consecutivos a un solo espacio
- convertir a minusculas
- no truncar texto
- no usar solo prefijos parciales del texto

Catalogo inicial cerrado de `group_code`:
- `resp` -> `responsibilities`
- `req` -> `required_criteria`
- `des` -> `desirable_criteria`
- `ben` -> `benefits`
- `comp` -> `about_the_company`
- `cond` -> `work_conditions.other_conditions`

Formato final:
- `item_id = group_code + "_" + first_10_hex(sha256(vacancy_id + "|" + group_code + "|" + normalized_raw_text))`

Ejemplo:
```json
{
  "raw_text": "Experiencia liderando equipos de desarrollo",
  "group_code": "req",
  "item_id": "req_7f3a9c12ab",
  "item_index": 0
}
```

Razon:
- `item_id` aporta estabilidad entre corridas cuando el contenido no cambia
- `item_index` aporta unicidad operativa dentro del artefacto incluso si existen textos duplicados
- `group_code` evita depender de rutas largas o nombres de path demasiado verbosos

## Paso 4 propuesto para queries de retrieval
Objetivo:
- generar consultas semanticas por item ya atomizado, sin reclasificar ni reinterpretar la vacante completa

Input:
- artefacto `vacancy_dimensions.v2`
- y resultado de `Paso 3.1` para salario cuando exista

Output esperado:
```json
{
  "contract_version": "vacancy_retrieval_queries.v1",
  "vacancy_id": "VAL-123",
  "generated_at": "2026-04-23T10:35:00-05:00",
  "queries": {
    "responsibilities": [
      {
        "item_index": 0,
        "raw_text": "...",
        "queries": [
          "liderazgo de equipos tecnicos, direccion de desarrolladores, gestion de backlog"
        ]
      }
    ],
    "required_criteria": [],
    "desirable_criteria": [],
    "benefits": [],
    "about_the_company": [],
    "work_conditions": {
      "salary": [],
      "modality": [],
      "location": [],
      "contract_type": [],
      "other_conditions": []
    }
  }
}
```

Regla:
- Paso 4 no reatomiza
- Paso 4 no asigna `category`
- Paso 4 no decide cumplimiento
- Paso 4 formula consultas orientadas a evidencia de CV por item
- si un item no amerita query util, puede devolver `queries: []`

## Paso 5 propuesto para retrieval de evidencia
Objetivo:
- ejecutar retrieval en Pinecone por item/query y persistir evidencia recuperada con score y metadata

Input:
- artefacto `vacancy_retrieval_queries.v1`

Output esperado:
```json
{
  "contract_version": "vacancy_retrieval_evidence.v1",
  "vacancy_id": "VAL-123",
  "generated_at": "2026-04-23T10:36:00-05:00",
  "evidence": {
    "responsibilities": [
      {
        "item_index": 0,
        "raw_text": "...",
        "matches": [
          {
            "query_index": 0,
            "score": 0.87,
            "snippet": "...",
            "source_ref": "cv_chunk_12"
          }
        ]
      }
    ],
    "required_criteria": [],
    "desirable_criteria": [],
    "benefits": [],
    "about_the_company": [],
    "work_conditions": {
      "salary": [],
      "modality": [],
      "location": [],
      "contract_type": [],
      "other_conditions": []
    }
  }
}
```

Regla:
- Paso 5 no concluye alineacion final
- Paso 5 no modifica queries
- Paso 5 solo recupera, ordena y persiste evidencia
- la interpretacion de scores queda para el paso de analisis posterior

## Criterio propuesto de lectura de scores
- `score > 0.85`: evidencia casi textual
- `score >= 0.70 y <= 0.85`: evidencia semantica razonable
- `score < 0.60`: probable ruido o senal debil

Este criterio es operativo y debe validarse con corridas reales antes de tratarse como regla cerrada de producto.

## Ambiguedades abiertas de Paso 3
- falta confirmar si `vacancy_dimensions.v2` debe generarse en un solo paso logico con `Paso 3 + Paso 3.1` o si ambos artefactos deben persistirse por separado
- falta cerrar si `benefits` necesitara en el futuro normalizacion adicional mas fuerte para participar mejor en el analisis de fit
- falta cerrar si `other_conditions` debe permanecer solo como lista textual o luego requerira una taxonomia posterior

## Decision cerrada por ahora
- `JobCriteriaMapper` no forma parte del diseno `v2`
- el siguiente paso de diseno debe asumir consumo directo desde `criteria[]`
- si luego aparece una capa intermedia, debe responder a una necesidad nueva y explicita, no a compatibilidad conceptual con el esquema legacy

## Riesgo conocido de la decision actual
- al guardar solo texto limpio en Paso 2, se simplifica el contrato inicial y baja el costo de implementacion
- a cambio, se pierde trazabilidad fina al `raw_text` original para debug automatizado, diff de corridas y auditoria exacta del clasificador
- si mas adelante esa trazabilidad hace falta, conviene agregarla como metadato adicional y no mezclarla en el texto del bloque
