# Guía de uso de CareerIQ

## 1. Ingresar al sistema
1. Abre CareerIQ en el navegador.
2. Ingresa tu usuario y contraseña.
3. Al entrar, verás la pantalla de perfiles consultados.

## 2. Seleccionar un perfil
1. En la pantalla principal, revisa los perfiles disponibles.
2. Haz clic sobre el perfil con el que deseas trabajar.
3. Una vez seleccionado, el sistema cargará su contexto.

## 3. Completar o ajustar el perfil
1. Entra a la pestaña `Perfil`.
2. Revisa y ajusta la información base:
   - nombre
   - ubicación
   - años de experiencia
   - roles objetivo
   - skills
3. Si corresponde, revisa el CV activo.
4. Guarda los cambios antes de continuar.

## 4. Gestionar vacantes del perfil
1. Ve a la pestaña `Vacantes`.
2. Allí puedes trabajar de dos maneras:
   - revisar y registrar vacantes de forma manual;
   - ejecutar búsquedas y revisar resultados.
3. Los resultados de búsqueda no quedan guardados automáticamente.
4. Solo cuando una vacante te interese, debes guardarla para que pase a formar parte de las vacantes del perfil activo.
5. La pestaña `Vacantes` sirve para alimentar el conjunto de vacantes asociadas al perfil con el que estás trabajando.

Nota:
Actualmente, la forma más confiable de alimentar vacantes sigue siendo la carga manual previa o el guardado explícito desde resultados, porque muchos portales de empleo no exponen bien su contenido a búsquedas abiertas. La búsqueda usa `Tavily` para consultar información en línea y actualizada, pero no siempre logra capturar el detalle completo de la vacante.

## 5. Revisar vacantes guardadas
1. Una vez guardada, la vacante queda asociada al perfil activo.
2. Esa vacante podrá trabajarse después en la pestaña `Análisis`.
3. También puedes actualizar su estado operativo y agregar notas.

Estados disponibles:
- `detected`
- `analyzed`
- `prioritized`
- `application_prepared`
- `applied`
- `discarded`

## 6. Generar análisis `Perfil-vacante`
1. Ve a la pestaña `Análisis`.
2. Selecciona la vacante guardada sobre la que deseas trabajar.
3. En el panel de resultados, entra en `Análisis`.
4. Selecciona el bloque `Perfil-vacante`.
5. Para lanzar la generación, usa el botón pequeño con icono tipo `Play`.
6. Si el análisis ya existe, puedes volver a generarlo a demanda usando el control de recálculo.
7. También puedes consultar diferentes ejecuciones previas del análisis cuando necesites revisar resultados anteriores.
8. Revisa el resultado para entender:
   - qué tan bien encaja el perfil con la vacante;
   - qué fortalezas aparecen;
   - qué brechas o faltantes existen.

## 7. Generar análisis de `Fit cultural`
1. En la misma pestaña `Análisis`, con la vacante activa, selecciona `Fit cultural`.
2. Usa el botón de ejecución para generar el análisis.
3. Si ya existe una ejecución previa, puedes recalcularla cuando quieras.
4. También puedes consultar otras ejecuciones disponibles.
5. El sistema consultará señales públicas mediante `Tavily`, usando información en línea y actualizada, y generará una lectura cualitativa.
6. Usa este resultado como orientación, no como verdad absoluta, porque depende de la evidencia pública disponible.

## 8. Generar `Entrevista`
1. En `Análisis`, con la vacante activa, selecciona `Entrevista`.
2. Usa el botón de ejecución para generar el brief.
3. Si ya existe un resultado, puedes volver a generarlo a demanda.
4. También puedes revisar diferentes ejecuciones anteriores.
5. El sistema investigará información pública y actualizada sobre la empresa asociada a la vacante mediante `Tavily`.
6. Obtendrás un brief con:
   - resumen ejecutivo
   - riesgos
   - preguntas sugeridas para entrevista
   - fuentes consultadas
7. Ese resultado también se envía al chat para que puedas profundizar desde allí.

## 9. Generar materiales de `Postulación`
1. En la misma pantalla de `Análisis`, cambia a `Postulación`.
2. Elige el bloque que necesitas:
   - `Guía de perfil`
   - `Carta de presentación`
   - `Resumen adaptado`
3. Usa el botón pequeño de ejecución para generarlo.
4. Si ya existe una versión previa, puedes recalcularla.
5. También puedes consultar diferentes ejecuciones si necesitas comparar resultados.
6. Revisa el contenido y úsalo como base de trabajo.

## 10. Usar el chat
1. Abre el panel de chat del perfil activo.
2. Escribe preguntas o instrucciones relacionadas con:
   - el perfil
   - una vacante guardada
   - un análisis generado
   - un brief de entrevista
3. El chat conserva historial por perfil, así que puedes continuar conversaciones previas.
4. Después de generar `Entrevista`, usa el chat para profundizar, por ejemplo:
   - pedir más preguntas de entrevista;
   - explorar riesgos de la empresa;
   - preparar respuestas posibles;
   - afinar narrativa de postulación.

## 11. Recomendación práctica de uso
Una secuencia útil es:
1. Seleccionar perfil.
2. Revisar o ajustar `Perfil`.
3. Cargar o buscar vacantes.
4. Guardar la vacante relevante en el perfil.
5. Ir a `Análisis`.
6. Ejecutar `Perfil-vacante`.
7. Ejecutar `Fit cultural`.
8. Ejecutar `Entrevista`.
9. Conversar en el chat sobre los resultados.
10. Generar materiales de `Postulación`.
11. Actualizar estado y notas de la vacante.

## 12. Consumir gate de consistencia `Vacancy V2` (operativo técnico)
Usa este flujo cuando quieras validar calidad de Step 2/Step 3 en lote para una persona.

1. Inicia sesión por API y conserva el `session_token`.
```bash
API="http://localhost:8000/api"
TOKEN=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"tutor","password":"change_me"}' | jq -r '.session_token')
```
2. Identifica el `person_id`.
```bash
curl -s "$API/persons" -H "x-session-id: $TOKEN" | jq
```
3. Ejecuta el gate.
```bash
PERSON_ID="p-001"
curl -s "$API/persons/$PERSON_ID/opportunities/vacancy-v2/consistency?sample_limit=20" \
  -H "x-session-id: $TOKEN" | jq
```
Opcional: define umbrales del gate en la query:
```bash
curl -s "$API/persons/$PERSON_ID/opportunities/vacancy-v2/consistency?sample_limit=20&min_salary_transfer_rate=0.8&max_salary_signal_in_step2_benefits_rate=0.05&min_salary_transfer_eligible=1" \
  -H "x-session-id: $TOKEN" | jq
```
4. Revisa principalmente:
- `salary_transfer_rate`
- `salary_transfer_missing`
- `salary_signal_in_step2_benefits`
- `gate_passed`
- `failed_checks`
- `issue_samples`

Si `salary_transfer_rate` cae a `0.0` y `salary_transfer_missing` es mayor a `0`, considera el gate en falla para salario y abre hardening antes de cerrar integracion de `v2`.

Opcional (runner CLI en backend):
```bash
cd apps/backend
PERSISTENCE_BACKEND=firestore .venv/bin/python scripts/vacancy_v2_gate_report.py --all-persons --sample-limit 20
```

Para un perfil puntual:
```bash
PERSISTENCE_BACKEND=firestore .venv/bin/python scripts/vacancy_v2_gate_report.py --person-id p-3fa73182 --sample-limit 20
```
