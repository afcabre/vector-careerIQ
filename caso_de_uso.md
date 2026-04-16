# Caso de uso de CareerIQ

## 1. Descripción del caso de uso y propósito de la solución
CareerIQ es un asistente conversacional especializado en trabajo sobre vacantes. Fue concebido para un escenario en el que un tutor opera sobre varios perfiles consultados y necesita mantener `Perfil`, vacantes, historial y contexto separados por cada uno.

La necesidad que atiende es concreta: evitar que el acompañamiento laboral dependa de información dispersa entre hojas de vida, notas, conversaciones previas y enlaces de vacantes. CareerIQ centraliza ese contexto y lo convierte en memoria operativa persistente.

El sistema no busca reemplazar el criterio del tutor, sino darle un entorno único para cargar o buscar vacantes, analizarlas, preparar postulaciones y continuar conversaciones contextualizadas sobre el perfil activo.

El objetivo funcional de la aplicación es asistir de forma personalizada el proceso de exploración, evaluación y preparación de postulaciones laborales para un perfil consultado específico. Para lograrlo, CareerIQ permite:

- mantener un perfil laboral persistente por persona;
- recuperar memoria conversacional entre sesiones;
- buscar o cargar vacantes y persistir las relevantes;
- analizar el ajuste entre perfil y vacante;
- generar insumos útiles para postular o preparar entrevista;
- operar todo lo anterior sin mezclar contexto entre perfiles consultados.

El resultado esperado es una experiencia de trabajo asistido donde el sistema conserva contexto, trae información actualizada cuando hace falta y produce salidas accionables sobre vacantes concretas.

## 2. Usuarios y actores involucrados
### Usuario humano principal
- **Tutor**: único usuario autenticado en V1. Inicia sesión, selecciona el perfil activo, conversa con el asistente, busca vacantes, guarda oportunidades y ejecuta acciones de `Análisis` o `Postulación`.

### Sujeto funcional del sistema
- **Perfil consultado**: perfil laboral sobre el cual se personalizan las respuestas, se almacenan CV, conversaciones y vacantes, y se ejecutan análisis.

La descripción técnica detallada de componentes, integraciones y responsabilidades de implementación se desarrolla en `.specify/03.Arquitectura-y-Plan.md`.

## 3. Escenario de uso principal
El flujo principal comienza cuando el tutor inicia sesión en la aplicación. Tras autenticarse, la interfaz presenta la vista de perfiles consultados. Allí el tutor selecciona el perfil con el que desea trabajar o crea uno nuevo si aún no existe.

El paso a paso de uso operativo de la herramienta se documenta en [guia_uso.md](./guia_uso.md). Ese documento complementa este caso de uso con instrucciones prácticas de interacción sobre `Perfil`, `Vacantes`, `Análisis`, `Postulación` y chat.

Al activar un perfil, el sistema recupera su información persistente: datos base de `Perfil`, preferencias, CV activo si existe, historial de conversación y vacantes previamente guardadas. Desde ese momento, todas las respuestas y acciones se contextualizan para ese perfil activo.

El tutor puede entonces conversar con el asistente, cargar o revisar el CV activo, buscar vacantes en fuentes externas, registrar vacantes manualmente por URL o texto y revisar vacantes ya guardadas.

Cuando una vacante resulta relevante, el sistema la persiste y la convierte en unidad de trabajo. Sobre esa vacante puede ejecutar `Perfil-vacante`, `Fit cultural` y `Entrevista`, además de generar materiales de `Postulación`: `Guía de perfil`, `Carta de presentación` y `Resumen adaptado`.

En `Perfil-vacante`, CareerIQ contrasta requerimientos de la vacante con experiencia, habilidades y contexto del perfil consultado. En `Entrevista`, toma la empresa asociada, consulta información pública mediante Tavily y consolida un brief con resumen ejecutivo, riesgos, fuentes y preguntas sugeridas. Ese resultado se registra además en el chat para permitir profundización posterior.

Cuando la respuesta se genera por un flujo compatible con streaming, el frontend la muestra de forma incremental mientras el backend emite eventos SSE. El resultado final queda persistido con histórico por acción y trazas asociadas, lo que permite reutilizarlo en sesiones posteriores y usarlo como insumo de ajuste operativo cuando corresponda.

## 4. Funcionalidades principales de la solución
### 4.1 Personalización basada en perfil de usuario
La solución mantiene un perfil estructurado por perfil consultado, con datos como nombre, roles objetivo, ubicación, años de experiencia, habilidades, expectativas salariales y preferencias culturales. Ese `Perfil` no es decorativo: se usa como insumo para construir contexto de respuesta y para orientar análisis, búsqueda y materiales generados. En V1, el sistema distingue explícitamente entre el tutor autenticado y el perfil activo, de modo que la personalización recae sobre este último.

### 4.2 Memoria conversacional persistente
Cada perfil consultado dispone de una conversación continua propia. El historial se recupera al volver a abrir el perfil y se mantiene aislado por `person_id`. Esto permite que el asistente retome contexto previo entre sesiones y evita la contaminación entre perfiles distintos. Desde la lógica funcional, esta memoria hace que el sistema “recuerde” a quién está atendiendo y qué se ha trabajado antes.

### 4.3 Consulta de información actualizada
CareerIQ incorpora búsqueda externa para traer información actualizada del entorno. En la implementación operativa actual, el proveedor efectivamente habilitado es Tavily. El tutor puede lanzar búsquedas desde la interfaz y, además, ciertos análisis se apoyan en señales públicas obtenidas en tiempo real, especialmente en contexto cultural y de entrevista. Este componente es clave porque complementa la memoria histórica con evidencia reciente del mercado y de las empresas.

Sin embargo, durante la implementación se identificó una limitación funcional importante: varios portales de empleo relevantes operan como entornos cerrados o restringidos, lo que dificulta capturar desde búsqueda web general la información completa y utilizable de una vacante. Esto afecta especialmente portales como LinkedIn, El Empleo o Computrabajo, donde la publicación visible al buscador no siempre expone el detalle suficiente para ser incorporado de manera confiable al sistema. Por esa razón, aunque la búsqueda con Tavily está disponible, la recomendación operativa actual para alimentar oportunidades de forma útil y consistente es la carga manual de vacantes.

### 4.4 Respuesta en streaming
La experiencia conversacional y varias acciones IA del sistema se presentan en streaming mediante SSE. Esto significa que el usuario no espera solo un resultado final; ve aparecer la respuesta mientras se genera. Desde el punto de vista de uso, esta capacidad mejora la percepción de continuidad de la interacción y hace visible que el sistema está procesando el contexto activo.

### 4.5 Interfaz de interacción
La interfaz permite recorrer un flujo operativo completo: autenticarse, seleccionar un perfil, editar `Perfil`, cargar CV, conversar con el asistente, buscar `Vacantes`, guardar vacantes, ejecutar `Análisis` y generar materiales de `Postulación`. El frontend no actúa como una demo aislada, sino como un workspace funcional conectado a un backend con persistencia y servicios externos reales.

### 4.6 Gestión operativa ligera de vacantes
Además del componente conversacional, la solución incluye una capa ligera de gestión de vacantes. El tutor puede guardar vacantes relevantes, revisar su detalle, agregar notas, cambiar estado y conservar snapshots del contenido. Esto permite trabajar vacantes como unidades persistentes de análisis sin convertir la aplicación en un ATS completo.

La solución permite además almacenar y actualizar estados de vacantes para mantener control sobre su avance dentro del proceso de trabajo. Los estados reales implementados en el sistema son:

- `detected`
- `analyzed`
- `prioritized`
- `application_prepared`
- `applied`
- `discarded`

En términos funcionales, esta secuencia permite saber si una vacante ya fue identificada, analizada, priorizada, preparada para postulación, aplicada o descartada. Esto introduce una capa básica de seguimiento operativo que ayuda al tutor a organizar el trabajo sobre cada vacante sin salir del mismo entorno conversacional.

### 4.7 Uso del CV como memoria semántica
Cuando existe un CV activo, el sistema extrae su contenido, lo indexa en Pinecone y lo reutiliza para recuperar evidencia relevante durante `Análisis` y generación de materiales. Funcionalmente, esto evita que el asistente dependa solo de un resumen estático del perfil y le permite fundamentar respuestas con fragmentos más específicos de la experiencia del perfil consultado.

### 4.8 Entrevista como funcionalidad de investigación asistida
La funcionalidad de entrevista es una de las piezas más elaboradas del sistema actual. No se limita a reformular la vacante: toma la empresa asociada, ejecuta consultas externas sobre ella y consolida una recomendación útil para enfrentar una entrevista con mayor contexto. Esto permite identificar riesgos, señales recientes y posibles temas de conversación relevantes antes del encuentro con la empresa. Además, el resultado inicial se registra en el chat para que el tutor siga profundizando desde allí mediante conversación contextual. En términos funcionales, esta capacidad acerca la solución a un asistente que investiga, no solo a uno que redacta.

### 4.9 Parametrización operativa del asistente
La solución incorpora una capa de parametrización administrativa que permite ajustar parte del comportamiento del sistema sin tocar código. Desde la interfaz de administración se pueden modificar plantillas de prompts, reglas de guardrails, construcción de consultas de búsqueda, activación de proveedores y parámetros globales de runtime IA, como estrategias de chunking o valores de recuperación semántica. Esta capacidad es relevante porque convierte la solución en una plataforma operable y ajustable, no en un prototipo rígido.

### 4.10 Análisis sobre vacantes
Dentro de la sección `Análisis`, CareerIQ organiza las acciones principales alrededor de la vacante activa. Los bloques visibles en la interfaz son `Perfil-vacante`, `Fit cultural` y `Entrevista`. Esta nomenclatura importa funcionalmente porque estructura la lectura del tutor: primero puede contrastar el encaje entre perfil y vacante, luego revisar señales culturales y finalmente obtener contexto investigado para entrevista.

## 5. Valor del asistente dentro del dominio elegido
En el dominio de acompañamiento laboral, la principal ventaja de CareerIQ frente a un chat genérico es que trabaja sobre contexto persistente y acciones funcionales concretas. No se limita a responder: permite operar sobre vacantes, analizarlas, preparar postulación e investigar empresas para entrevista dentro del mismo flujo.

## 6. Tabla de cumplimiento de requisitos del ejercicio
El detalle de cumplimiento del ejercicio se documenta en [cumplimiento_ejercicio.md](./cumplimiento_ejercicio.md).

## 7. Resumen técnico de la solución
La solución está compuesta por un frontend desarrollado en React con Vite y un backend implementado en FastAPI. Firestore actúa como persistencia operacional principal; Pinecone soporta recuperación semántica del CV; OpenAI se utiliza para conversación, análisis, entrevista y preparación; Tavily aporta información externa actualizada. El streaming se implementa mediante Server-Sent Events. La solución incorpora además una capa de parametrización administrativa para prompts, proveedores y runtime IA.

## 8. Conclusión
CareerIQ implementa un asistente conversacional especializado en trabajo sobre vacantes, orientado a un tutor que opera sobre múltiples perfiles consultados. Su valor principal radica en combinar `Perfil` persistente, memoria conversacional, carga o búsqueda de vacantes, `Análisis`, `Postulación` y `Entrevista` dentro de una misma experiencia operativa.

Desde el punto de vista del ejercicio, la solución demuestra de forma verificable perfil persistente, memoria entre sesiones, búsqueda en tiempo real, streaming e interfaz funcional conectada a un backend operativo. Su diferencial está en que esas capacidades no aparecen aisladas, sino articuladas alrededor de un caso de uso concreto.
