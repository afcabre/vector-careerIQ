# Pantallas funcionales de CareerIQ

## 1. Candidatos

La pantalla `Candidatos` es el punto de entrada operativo de la solución. Su función no es analizar información ni editar configuraciones, sino definir con qué perfil consultado va a trabajar el sistema en ese momento.

### Composición de la pantalla

- Un encabezado superior persistente compartido con el resto de la aplicación
- Un bloque principal de `Perfiles consultados`
- Un conjunto de tarjetas seleccionables, una por candidato
- Un formulario de alta de perfil, oculto por defecto y visible solo por acción explícita del usuario

### Contenido funcional

La pantalla muestra la lista de perfiles disponibles para consulta. Cada tarjeta presenta:

- identificador del perfil
- nombre del candidato
- rol principal u objetivo visible
- ubicación
- años de experiencia

El formulario de alta permite registrar nuevos perfiles, pero no interfiere con la operación normal de consulta, porque permanece oculto hasta que el usuario pulsa `Agregar perfil`.

### Interacción del usuario

1. El usuario ingresa a la aplicación autenticado como tutor u operador único de V1
2. Revisa los perfiles disponibles
3. Hace clic sobre una tarjeta para definir el candidato activo
4. A partir de esa selección, el sistema carga el contexto global de trabajo

### Función dentro del sistema

Esta pantalla existe para separar claramente dos niveles:

- el usuario autenticado que opera la herramienta
- la persona consultada sobre la cual se analizan vacantes, CV, entrevista y postulación

En V1, el sistema está pensado para un único operador protegido por usuario y contraseña, pero con posibilidad de cambiar entre múltiples personas consultadas. Por eso el candidato activo se convierte en un contexto global de sesión de trabajo.

## 2. Header global y contexto activo

El encabezado superior es persistente y acompaña todas las pantallas principales. No es solo un elemento visual de navegación; es el componente que mantiene visible el contexto operativo actual.

### Qué contiene el header

- La marca `CareerIQ`
- El selector del candidato activo, cuando existe uno seleccionado
- La navegación contextual principal
- Accesos de administración y cierre de sesión

### Por qué el candidato se mantiene global

El candidato activo se mantiene global porque toda la aplicación trabaja sobre un mismo contexto transversal:

- el `Perfil` que se edita corresponde al candidato activo
- las `Vacantes` que se cargan o guardan quedan asociadas a ese candidato activo
- los resultados de `Análisis` y `Postulación` se generan para vacantes del candidato activo
- el `chat` conserva historial por candidato activo

Si el candidato no fuera global, el usuario tendría que redefinir manualmente el contexto en cada pantalla, lo que aumentaría ambigüedad y riesgo de mezclar información entre personas distintas.

### Comportamiento del header

Cuando no hay candidato seleccionado:

- el selector central invita a elegir un candidato
- las tabs contextuales no se muestran
- el usuario puede ir a administración, pero no operar `Perfil`, `Vacantes` ni `Análisis`

Cuando sí hay candidato seleccionado:

- el selector central muestra nombre y rol principal del candidato activo
- el usuario puede desplegar el menú para cambiar de candidato o volver al perfil activo
- aparecen las tabs contextuales de operación:
  - `Perfil`
  - `Vacantes`
  - `Análisis`

### Función del header dentro del flujo

El header resuelve tres necesidades a la vez:

- hace visible el contexto activo en todo momento
- evita pérdida de orientación al cambiar de pantalla
- permite cambiar de candidato sin salir del flujo principal

Por eso su comportamiento es global y persistente, y no local a una pantalla específica.

## 3. Perfil

La pantalla `Perfil` está diseñada para definir y mantener el contexto base del candidato consultado. Es la pantalla donde el sistema reúne la información estable que luego usa para personalizar el chat, los análisis y los materiales de postulación.

### Composición de la pantalla

- Un encabezado superior persistente con la marca `CareerIQ`, el candidato activo y la navegación contextual
- Un bloque principal de `Perfil` con formulario editable
- Un bloque de `Condiciones de trabajo y preferencias culturales`
- Un bloque de `CV`
- El `chat` contextual como panel lateral o deslizable

### Contenido funcional

En `Perfil`, el usuario puede editar:

- nombre
- ubicación
- años de experiencia
- roles objetivo
- skills
- expectativa salarial

En `Condiciones de trabajo y preferencias culturales`, el usuario marca opciones aceptables por dimensión. Esta información no se usa como descarte rígido desde backend, sino como contexto para interpretación en prompts y análisis.

En `CV`, el usuario puede cargar o reemplazar el CV activo del perfil seleccionado. La interfaz muestra una vista previa del contenido extraído y permite expandirlo para revisar más texto.

El `chat` mantiene una conversación continua por perfil, no por sesión aislada.

### Interacción del usuario

1. Selecciona un perfil desde la pantalla inicial
2. Entra a `Perfil`
3. Ajusta datos estructurados del candidato
4. Revisa o reemplaza el CV
5. Guarda cambios
6. Puede abrir el chat en cualquier momento para consultar sobre ese perfil

### Función dentro del sistema

- Define el contexto base persistente del candidato
- Alimenta prompts de chat, alineación perfil-vacante, fit cultural, entrevista y postulación
- Sirve como fuente de retrieval semántico cuando existe CV vectorizado

## 4. Vacantes

La pantalla `Vacantes` no es todavía un gestor de selección para análisis directo. Su función principal es alimentar el conjunto de vacantes asociadas al perfil activo.

### Composición de la pantalla

- Un encabezado superior persistente con candidato activo y navegación
- Un bloque principal con tabs
- Dos modos: `Carga manual` y `Búsqueda`
- Una sección de resultados de búsqueda, cuando aplica
- Una sección de `Vacantes guardadas`

### Contenido funcional

`Carga manual` es el tab principal. Allí el usuario registra una vacante con URL, título, empresa, ubicación, salario y descripción o snapshot.

`Búsqueda` usa `Tavily` para consultar información en línea y actualizada, pero con limitaciones reales frente a portales de empleo cerrados.

Los resultados de búsqueda se muestran como tarjetas.

Las vacantes guardadas quedan persistidas por perfil y muestran datos resumidos, estado, origen y acceso a detalle expandido.

### Interacción del usuario

1. Puede cargar manualmente una vacante si ya la tiene identificada
2. Puede ejecutar una búsqueda y revisar resultados
3. Los resultados no quedan persistidos por defecto
4. Si una vacante le interesa, la guarda explícitamente
5. Una vez guardada, pasa a formar parte del conjunto de vacantes del perfil activo
6. Desde esta pantalla puede revisar las vacantes guardadas, expandir descripción, abrir la vacante original o copiar la URL

### Papel dentro del flujo

- Es la capa de entrada y persistencia de vacantes
- No es donde se ejecuta el análisis principal
- Prepara el insumo que luego se trabaja en `Análisis`

### Limitación operativa relevante

Aunque `Búsqueda` existe y usa `Tavily`, muchos portales como LinkedIn, Computrabajo o El Empleo restringen fuertemente la captura útil. Por eso, en V1, la carga manual sigue siendo la vía más confiable para alimentar vacantes de calidad.

## 5. Análisis

La pantalla `Análisis` es el centro operativo de trabajo sobre una vacante ya guardada. Aquí el usuario selecciona una vacante del perfil activo, ejecuta análisis y genera materiales.

### Composición de la pantalla

- Bloque superior de `Vacantes guardadas`
- Panel central de resultados
- Bloque de `Gestión de oportunidad`
- Columna lateral de `Contextual Intelligence`, que puede colapsarse
- Integración con el `chat`

### Parte de vacantes

La lista de vacantes guardadas asociadas al perfil activo muestra:

- título
- empresa
- metadatos
- preview de descripción
- acceso a la vacante
- copia de URL

La selección de una vacante activa visualmente su tarjeta y despliega el detalle operativo debajo.

### Comportamiento de selección

- Ninguna vacante queda activa por defecto al entrar
- El usuario hace clic en una tarjeta para activarla
- Si vuelve a hacer clic en la misma, la desactiva
- Al seleccionar una nueva, el sistema enfoca el bloque de trabajo asociado

### Panel central

El panel central contiene dos tabs principales:

- `Análisis`
- `Postulación`

Dentro de `Análisis`, existen bloques funcionales:

- `Perfil-vacante`
- `Fit cultural`
- `Entrevista`

Dentro de `Postulación`, existen bloques:

- `Guía de perfil`
- `Carta de presentación`
- `Resumen adaptado`

### Interacción del usuario con los bloques

- Cada bloque puede estar sin generar o con resultados previos
- La generación se lanza con un botón pequeño tipo `play`
- Si ya existe un resultado, se puede recalcular
- Cada bloque admite navegación entre ejecuciones previas, porque el sistema conserva histórico
- El contenido se muestra colapsado o expandible según longitud
- El usuario puede copiar el contenido generado

### Qué hace cada bloque

#### Perfil-vacante

Compara el perfil del candidato con la vacante usando contexto estructurado y evidencia semántica del CV.

#### Fit cultural

Interpreta compatibilidad probable entre preferencias del perfil y señales públicas obtenidas mediante `Tavily`, usando información en línea y actualizada.

#### Entrevista

Ejecuta un flujo más complejo de investigación sobre la empresa asociada a la vacante, usando `Tavily` e información pública actualizada. Produce un brief con contexto para entrevista.

#### Guía de perfil

Genera ayuda textual para orientar la postulación.

#### Carta de presentación

Genera una carta contextualizada a la vacante.

#### Resumen adaptado

Produce un resumen de experiencia enfocado a esa vacante.

### Gestión de oportunidad

`Gestión de oportunidad` contiene:

- estado de la vacante
- notas operativas
- persistencia explícita de ambos

Esto permite llevar control del avance de la vacante dentro del proceso. Los estados soportan seguimiento operativo del tipo: detectada, analizada, priorizada, preparada para aplicación, aplicada o descartada.

### Contextual Intelligence

La columna `Contextual Intelligence` contiene:

- `Historial IA`
- `Trazas técnicas`

`Historial IA` muestra ejecuciones relacionadas con la vacante y el bloque seleccionado.

`Trazas técnicas` muestra request y response persistidos de las ejecuciones.

Esta columna está pensada como capa de inspección y auditoría, no como contenido principal de trabajo. Puede ocultarse para dar más espacio al panel central.

### Relación con el chat

El chat sigue siendo por perfil.

En `Entrevista`, el resultado inicial se envía también al chat para continuar profundización conversacional.

Esto permite pasar de una ejecución puntual a una exploración asistida más abierta, manteniendo contexto del perfil y de la vacante activa.

## 6. Relación entre las pantallas

- `Candidatos` define la persona consultada sobre la que se trabajará
- el `header` mantiene visible ese contexto y permite navegar sin perderlo
- `Perfil` define el contexto persistente del candidato
- `Vacantes` alimenta y conserva las vacantes asociadas a ese perfil
- `Análisis` toma una vacante guardada y la convierte en análisis, contexto para entrevista y materiales de postulación
