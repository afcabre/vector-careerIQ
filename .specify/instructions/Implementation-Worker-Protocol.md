# Implementation Worker Protocol

## Proposito
Definir la mecanica operativa para ejecutar implementacion iterativa desde este repositorio con apoyo de `Notion`, preservando una sola fuente de verdad tecnica y evitando que el usuario tenga que emitir una instruccion nueva para cada tarea.

## Relacion Con El Prompt Maestro
Este protocolo no reemplaza `.specify/instructions/SDD-Prompt-Maestro.md`.

Lo complementa:
- el `SDD-Prompt-Maestro` define la logica general del proyecto, el rigor SDD, el alcance y la disciplina de documentacion
- este documento define como ejecutar trabajo iterativo de implementacion sobre tareas concretas ya decididas

Por tanto:
- la logica general sale del `SDD-Prompt-Maestro`
- la mecanica de ejecucion continua sale de este protocolo

## Fuentes De Verdad
Orden operativo:
1. codigo y documentacion local del repositorio
2. `PROJECT_STATUS.md`
3. documentos normativos `.specify/00.*`, `.specify/01.*`, `.specify/02.*`, `.specify/03.*`
4. `Notion` como capa de seguimiento operativo

Regla:
- `Notion` no sustituye la verdad tecnica local
- ninguna decision nueva importante debe vivir solo en `Notion`

## Lectura Obligatoria Antes De Ejecutar
1. `AGENTS.md`
2. `PROJECT_STATUS.md`
3. `.specify/instructions/SDD-Prompt-Maestro.md`
4. documentos normativos principales en `.specify/`
5. tarea activa en `Notion`

## Seleccion De Trabajo
### Regla principal
- si existe una sola tarea en estado `Doing`, esa es la tarea activa
- si no existe tarea en `Doing`, tomar la primera tarea `To do` de la wave vigente definida en `Notion`
- no saltar a una tarea posterior si la tarea actual bloquea trabajo previo necesario

### Regla de alcance
- trabajar solo dentro del `Write Scope` de la tarea activa
- si la implementacion exige salir del `Write Scope`, se permite solo cuando:
  - es un ajuste tecnico menor estrictamente necesario
  - no cambia alcance
  - no contradice documentos normativos
- si la salida de scope implica decision de diseno, detenerse y pedir aclaracion

## Mecanica Iterativa
### Inicio de ciclo
1. identificar tarea activa
2. releer `Objective`, `Write Scope`, `Acceptance Criteria`, `Out Of Scope` y `Execution Notes`
3. contrastar con el estado real del repo
4. ejecutar el slice sin rediseñar alcance ya cerrado

### Durante el ciclo
- avanzar por incrementos pequenos y verificables
- si hay ambiguedad real, hacer una sola pregunta por vez
- si no hay ambiguedad bloqueante, no detenerse innecesariamente
- mantener cambios aditivos cuando el objetivo sea introducir trabajo paralelo al baseline estable

### Cierre de ciclo
Al terminar una tarea o un avance relevante:
1. validar el cambio con pruebas razonables o verificacion tecnica equivalente
2. actualizar `PROJECT_STATUS.md` si hubo avance relevante o nueva decision
3. actualizar `Notion` con estado, notas y siguiente paso
4. si la tarea quedo completa, moverla segun corresponda y tomar la siguiente

## Regla De Commits En Branch Experimental
Cuando el trabajo ocurra en una branch experimental o de spike, por ejemplo `spike/*`:
- preferir un commit por slice o por tarea cerrada, no por microcambio
- no mezclar en un mismo commit multiples slices con objetivos distintos
- el commit debe ocurrir despues de validacion razonable del slice
- si la validacion queda parcial por entorno, dejarlo explicitado antes de proponer commit

Formato recomendado:
- un commit pequeno, trazable y alineado con la tarea activa
- mensaje en ingles, orientado al slice y no a cambios incidentales

## Regla De Checkpoint Con Usuario
La ejecucion sigue siendo iterativa, pero en branch experimental debe haber control por checkpoints:
- dentro de una tarea activa, el worker puede avanzar de forma autonoma hasta cerrar el slice
- al cerrar el slice, debe detenerse y reportar:
  - que hizo
  - que valido
  - que quedo pendiente
  - que se puede probar operativamente
  - propuesta de mensaje de commit en ingles
- antes de crear el commit o pasar a la siguiente tarea, debe esperar confirmacion del usuario
- el commit se crea solo despues de que el usuario valide la operatividad o acepte explicitamente el riesgo residual

Esto permite:
- continuidad operativa sin reemitir prompts detallados a cada paso
- control paso a paso del usuario entre slices
- commits limpios y trazables en la branch del spike
- minimizar publicar versiones con errores evitables

## Regla De Aclaraciones
- hacer una sola pregunta a la vez
- solo preguntar cuando la respuesta no pueda descubrirse localmente y una suposicion razonable sea riesgosa
- no formular preguntas para confirmar trabajo ya decidido en documentos o en `Notion`

## Regla De Cambios De Decision
Si aparece una necesidad de cambiar contrato, alcance o decision tecnica:
1. registrar primero el cambio en documentacion local y/o `PROJECT_STATUS.md`
2. luego reflejar el cambio en `Notion`
3. solo despues continuar implementacion derivada de ese cambio

## Regla De Runtime Config V2
Para `vacancy_v2`:
- `Step 2` y `Step 3` arrancan con schema interno y defaults en backend
- no se expone configuracion en administracion del sistema en esta fase
- controles operativos de ejecucion permanecen internos hasta validar corridas reales

Ejemplos de controles internos en esta fase:
- retries
- timeout
- output token limits
- validation retry controls

## Condiciones De Stop
Detener la iteracion automatica y escalar al usuario cuando:
- hay conflicto con el baseline estable
- aparece un cambio de contrato o alcance no documentado
- faltan permisos o configuracion de entorno necesarios
- la tarea siguiente depende de una decision aun no cerrada
- la implementacion exige romper las reglas de V1 acotada o de no duplicacion

## Regla De Continuidad
El usuario no necesita emitir una nueva instruccion detallada para cada tarea si ya existe:
- protocolo vigente
- plan en `Notion`
- tarea activa clara
- reglas de fuente de verdad y de aclaracion ya definidas

Instrucciones validas de continuidad incluyen:
- `continua la implementacion siguiendo el protocolo`
- `retoma desde la tarea en Doing`
- `avanza con la siguiente tarea del plan`

En branch experimental, esa continuidad aplica dentro del slice activo. Para pasar al siguiente slice o consolidar commit, se usa checkpoint con el usuario.

## Resultado Esperado
Este protocolo debe permitir que un modelo pequeno:
- itere sobre slices consecutivos con contexto suficiente
- pida aclaraciones solo cuando haga falta
- preserve la disciplina SDD ya definida
- mantenga sincronizados repo, `PROJECT_STATUS.md` y `Notion`
