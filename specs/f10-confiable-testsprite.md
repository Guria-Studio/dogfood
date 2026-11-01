---
type: spec
project_id: dogfood
phase: 10
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
  - docs/arch/002-panel-react.md
  - specs/f9-panel-react-ayuda.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-11-01
title: Corridas confiables y producto estilo TestSprite
---

# F10 — Corridas confiables y producto estilo TestSprite

La primera corrida con 10 personas (`runs/20261101-125232-2-85b1`, log en `/home/knaimero/.local/state/dogfood/corrida-10.log`) dio 0 % de éxito por fallas de dogfood, no de predicts: el juez recibió 503 de 9router en todas las ejecuciones, solo se crearon 8 de 10 ejecuciones, el detector del objetivo falló entero, y el ruido técnico (401 y 429 esperados) salió como gravedad alta. F10.1 arregla eso. F10.2 suma lo que hace que dogfood se sienta un producto como TestSprite: plan de pruebas, sugerencia de arreglo por hallazgo, lanzar y repetir corridas desde el panel y un reporte compartible. F10.9 repite la corrida real y verifica.

Antes de cada tarea, mira esa corrida en el panel (`uv run dogfood panel`) o en `runs/`: es el caso real que tiene que quedar bien.

## F10.1 — Package: corridas confiables

### F10.1.T1 — Juez con reintentos y modelo de respaldo, y fricción que sí se registra

El juez es el que decide si la persona cumplió el `criterio_exito`. Hoy, en `src/dogfood/agente/navegador.py` (≈ línea 360) y `src/dogfood/agente/bucle.py` (≈ línea 277), cualquier excepción del juez deja `exito=False` con «el juez falló: …», y la ejecución cuenta como fracaso.

1. Crea `src/dogfood/agente/juez.py` con `async def juzgar(criterio, evidencia, cfg) -> Veredicto` que usan ambos motores (reemplaza su código duplicado):
   - reintenta errores transitorios (5xx, timeouts, 429) con backoff exponencial (3 intentos, tope 30 s);
   - si el primer modelo del rol `juez` sigue fallando, prueba los siguientes del rol en `dogfood.yaml` (y un respaldo fijo `ag/gemini-3.8-flash` si la lista tiene uno solo);
   - si todos fallan, el veredicto es **no concluyente** (no «fallo»): `Ejecucion.resultado` pasa a `no_concluyente` según `contrato.resultado`, con el motivo «juez no disponible».
   - registra cada intento en `UsoLlm`.
2. Arregla la excepción de `al_terminar_paso` de `navegador.py` (≈ línea 266) que aparece en el log de la corrida (busca `on_step_end` en el log). Agrega un test que la reproduzca.
3. **Fricción:** en la corrida, ninguna persona anotó fricción, aunque varias se trabaron. En `src/dogfood/agente/prompts.py` haz explícito cuándo llamar a `anotar_friccion` (repetir una acción, no encontrar algo, un error en pantalla, esperar más de 20 s), y en el agente registra fricción automática cuando se repite la misma acción 3 veces o aparece un error visible, sin depender de que el LLM la anote.

Done when: estos tests pasan en `tests/test_juez.py` y `tests/test_agente_friccion.py`:
- con un cliente falso que da 503 dos veces y luego responde, el veredicto es el de la respuesta;
- con el primer modelo siempre en 503 y el segundo bien, responde el segundo;
- con todos en 503, el resultado de la ejecución es `no_concluyente` y no `fallo`;
- un 400 (error no transitorio) no se reintenta;
- la misma acción 3 veces seguidas genera una fricción automática con su captura;
- la excepción de `al_terminar_paso` del log ya no ocurre;
- los tests existentes del agente y del bucle siguen verdes.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Robustez con casos acotados y tests guiados.
- **Dependencies**:
- **Files**:
  - `src/dogfood/agente/juez.py`
  - `src/dogfood/agente/navegador.py`
  - `src/dogfood/agente/bucle.py`
  - `src/dogfood/agente/prompts.py`
  - `tests/test_juez.py`
  - `tests/test_agente_friccion.py`

### F10.1.T2 — Asignación: todas las personas corren y todos los escenarios se cubren

En la corrida, 10 personas dieron 8 ejecuciones, y los escenarios `recompra-completa`, `demo` y `plantillas-mensaje` no corrieron. `escenarios.asignar` (`src/dogfood/escenarios.py`) deja fuera a las personas sin escenario compatible, y su greedy puede dejar escenarios sin cubrir (ver el comentario `ponytail` ahí).

- Encuentra la causa real con los datos de esa corrida (`runs/20261101-125232-2-85b1/personas.json` y los YAML de `src/dogfood/objetivos/predicts/escenarios/`) y documéntala en el docstring.
- `asignar` debe: cubrir cada escenario que tenga al menos una persona compatible (usa un matching bipartito, no el greedy), asignar a **toda** persona algún escenario (si ninguno es compatible por intención o destreza, el más cercano, con una nota en la ejecución), y devolver además una lista de avisos («escenario X sin personas compatibles»).
- La corrida imprime esos avisos y el reporte los muestra en el resumen (solo agrega la línea que llama, en `src/dogfood/corrida.py`).

Done when: estos tests pasan en `tests/test_escenarios_asignacion.py`:
- con las 10 personas de esa corrida (copia `personas.json` a `tests/fixtures/`) salen 10 asignaciones y quedan cubiertos todos los escenarios con alguna persona compatible;
- un caso adverso en el que el greedy viejo dejaba un escenario sin cubrir ahora lo cubre;
- un escenario sin ninguna persona compatible produce su aviso;
- la misma semilla da la misma asignación;
- los tests existentes de escenarios siguen verdes.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 2h
- **Reason**: Algoritmo chico y bien definido.
- **Dependencies**:
- **Files**:
  - `src/dogfood/escenarios.py`
  - `src/dogfood/corrida.py`
  - `tests/test_escenarios_asignacion.py`
  - `tests/fixtures/personas-corrida-10.json`

### F10.1.T3 — El detector del objetivo vuelve a funcionar (oráculo, aislamiento y reglas)

En la corrida salió el hallazgo «detector dogfood.deteccion.objetivo.detectar falló», o sea que no se revisó ningún número, ni el aislamiento entre empresas, ni las reglas de predicts. Es lo más valioso de dogfood.

1. Reproduce el fallo con los datos de esa corrida: arma un `ContextoDeteccion` desde `runs/20261101-125232-2-85b1` (la instancia ya no existe; falsea `cliente_api` con respuestas grabadas, o vuelve a levantar predicts con `dogfood env up --target predicts --ref master` si hace falta capturarlas) y encuentra qué verificador lanza y por qué.
2. Arregla la causa en el verificador que corresponda (`src/dogfood/objetivos/predicts/oraculo.py`, `aislamiento.py` o `reglas.py`), sin bajar las tolerancias de la decisión D4.
3. En `src/dogfood/deteccion/objetivo.py`, que un verificador que falla no tumbe a los demás: cada uno se ejecuta por separado y su error queda como hallazgo `baja` con el nombre del verificador y el tipo de excepción (no un genérico «el detector falló»).

Done when: estos tests pasan en `tests/test_detector_objetivo_corrida.py`:
- con el contexto de la corrida, el detector del objetivo termina sin excepción y produce los hallazgos que correspondan (o ninguno, si no hay);
- un verificador falso que lanza deja un hallazgo con su nombre y los otros dos corren igual;
- el caso exacto que rompía queda como test de regresión;
- los tests existentes del oráculo, aislamiento y reglas siguen verdes.
Si para reproducir necesitas levantar predicts, hazlo en el server y deja en el PR qué capturaste.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 4h
- **Reason**: Diagnóstico sobre datos reales en la parte más delicada (oráculo y aislamiento).
- **Dependencies**:
- **Files**:
  - `src/dogfood/deteccion/objetivo.py`
  - `src/dogfood/objetivos/predicts/oraculo.py`
  - `src/dogfood/objetivos/predicts/aislamiento.py`
  - `src/dogfood/objetivos/predicts/reglas.py`
  - `tests/test_detector_objetivo_corrida.py`
  - `tests/fixtures/corrida-10/`

### F10.1.T4 — Menos ruido técnico: lo esperado no es un hallazgo alto

En la corrida, 8 hallazgos técnicos: varios eran ruido. Ajusta `src/dogfood/deteccion/tecnicos.py`:
- un 401 de `GET /api/auth/yo` (o la ruta de sesión que declare el objetivo) **antes** de que la persona inicie sesión es esperado: no es hallazgo;
- en ejecuciones del carril `login_fallido`, los 401 y 429 de `/auth/login` son esperados (hoy el 429 salió «alta»);
- el error de consola «Failed to load resource: … status of N» que corresponde a una respuesta de red ya registrada **no** es un segundo hallazgo: se fusiona con el de red (misma huella);
- el 404 de `/api/datasets/{id}/calidad` repetido en varias ejecuciones queda como **un** hallazgo con varias ocurrencias, gravedad `media`, y en su descripción la hipótesis «carrera entre la subida y el cálculo de calidad» si siempre ocurre en los primeros segundos tras la subida (compáralo con el tiempo del POST de subida en `red.jsonl`).
- Las rutas «esperadas» las declara el objetivo (un método nuevo opcional `rutas_esperadas()` en `PredictsObjetivo`, en `src/dogfood/objetivos/predicts/__init__.py`), no se escriben en el detector.

Done when: estos tests pasan en `tests/test_tecnicos_ruido.py`, con los `red.jsonl` y `consola.jsonl` de la corrida copiados a `tests/fixtures/`:
- de los 8 hallazgos de la corrida quedan los reales (el 404 de calidad como uno solo, con sus ocurrencias) y desaparecen los 401 y 429 esperados;
- un 500 sigue siendo `alta`;
- un `Failed to load resource` con su respuesta de red da un solo hallazgo;
- los tests existentes de `tecnicos` siguen verdes.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Reglas concretas con datos reales para probarlas.
- **Dependencies**:
- **Files**:
  - `src/dogfood/deteccion/tecnicos.py`
  - `src/dogfood/objetivos/predicts/__init__.py`
  - `tests/test_tecnicos_ruido.py`
  - `tests/fixtures/corrida-10-red/`

## F10.2 — Package: producto estilo TestSprite

Referencia de producto: TestSprite (testsprite.com). Genera un plan de pruebas a partir de la app, corre cada caso con un agente, muestra cada caso con su estado, pasos y video, propone el arreglo de cada falla, y deja un reporte que se comparte. Este paquete trae eso a dogfood con el diseño de F9.4 (shadcn, sidebar, ⌘K). Todas sus tareas van en serie porque comparten la navegación del panel.

### F10.2.T1 — Plan de pruebas y casos de prueba

1. Backend, `src/dogfood/plan.py`: `armar_plan(objetivo, personas, escenarios, semilla) -> PlanPruebas` con un **caso de prueba** por asignación (escenario × persona): id estable, título legible («Analista de pet shop, pt-BR, sube un CSV con `;` y corre recompra»), objetivo, criterio de éxito, prioridad (`alta` para recorridos de dinero o datos: registro, subir, analizar, exportar; `media` el resto), superficie y datos. `dogfood plan --target predicts --personas N` lo imprime y lo guarda en `runs/plan-<semilla>.json`; `dogfood run` guarda el plan de la corrida y cada ejecución apunta a su caso.
2. API: `GET /api/corridas/{id}/plan` devuelve los casos con su estado (pendiente, en curso, éxito, fallo, rendido, no concluyente) y el link a la ejecución. Rutas en `src/dogfood/panel/api_plan.py`, registradas con una línea en `src/dogfood/panel/app.py`.
3. Web: pestaña **«Casos de prueba»** en la pantalla de corrida (`web/src/features/plan/`), con la tabla de casos (estado como badge, prioridad, persona, duración), filtros por estado y prioridad, y clic que abre la ejecución. Agrega el link en la navegación.

Done when: estos tests pasan:
- en `tests/test_plan.py`: la misma semilla da el mismo plan; cada asignación tiene su caso con prioridad correcta; el plan guardado de una corrida se lee por la API con los estados de sus ejecuciones;
- en `web/src/features/plan/plan.test.tsx`: la tabla muestra los casos con su badge y filtra por estado.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 4h
- **Reason**: Define el concepto central del producto (caso de prueba) que usan las tareas siguientes.
- **Dependencies**: F9.9.T1, F10.1.T2
- **Files**:
  - `src/dogfood/plan.py`
  - `src/dogfood/comandos/plan.py`
  - `src/dogfood/cli.py`
  - `src/dogfood/corrida.py`
  - `src/dogfood/panel/api_plan.py`
  - `src/dogfood/panel/app.py`
  - `tests/test_plan.py`
  - `web/`

### F10.2.T2 — Sugerencia de arreglo por hallazgo

Como TestSprite, cada falla viene con «por qué pasó y cómo arreglarlo».

1. `src/dogfood/reporte/sugerencia.py`: `sugerir(hallazgo, evidencia, repo_objetivo: Path | None) -> Sugerencia` (causa probable, archivos probables del repo con su línea si se encuentran, cambio propuesto en texto y un nivel de confianza). Usa el rol `redactor` con `completar_json`. Si `repo_objetivo` existe (predicts está en `/mnt/storage/project/predicts`, configurable por objetivo), busca con `ripgrep` las rutas, endpoints o textos de la evidencia y pasa solo esos fragmentos al LLM (máx. 4 archivos, 200 líneas). La sugerencia nunca afirma más de lo que muestra la evidencia: si la confianza es baja, lo dice.
2. La corrida genera la sugerencia de cada hallazgo publicable y la guarda; `reporte/issues.py` la agrega al cuerpo del issue en una sección «Posible causa y arreglo (sugerido por dogfood, revisar)». Todo pasa por `redactar`.
3. API `GET /api/hallazgos/{id}` con la sugerencia, y en la web una tarjeta **«Posible causa y arreglo»** en el detalle de ejecución, con los archivos como links al repo en GitHub.

Done when: estos tests pasan en `tests/test_sugerencia.py` (LLM falso) y `web/src/features/sugerencia/sugerencia.test.tsx`:
- con la evidencia del 404 de `/calidad` y un repo falso que tiene esa ruta, la sugerencia cita el archivo de la ruta;
- sin repo, la sugerencia se genera igual con confianza baja;
- un secreto plantado en la evidencia no llega al prompt ni a la sugerencia;
- el cuerpo del issue incluye la sección;
- la tarjeta muestra causa, archivos y confianza.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: LLM acotado con datos ya estructurados.
- **Dependencies**: F10.2.T1
- **Files**:
  - `src/dogfood/reporte/sugerencia.py`
  - `src/dogfood/reporte/issues.py`
  - `src/dogfood/corrida.py`
  - `src/dogfood/panel/api_plan.py`
  - `tests/test_sugerencia.py`
  - `web/`

### F10.2.T3 — Lanzar y repetir corridas desde el panel

1. Backend, `src/dogfood/panel/acciones.py`: `POST /api/corridas` (objetivo, ref, personas, escenarios, semilla, vista, sin_publicar; por defecto `sin_publicar=true`) lanza la corrida como proceso aparte (`systemd-run --user` si está disponible, si no `subprocess` desacoplado) y devuelve su id; `GET /api/corridas/{id}/estado` da progreso (casos terminados de total) y log reciente; `POST /api/ejecuciones/{id}/replay` lanza `dogfood replay`; `POST /api/corridas/{id}/cancelar` la detiene. Solo una corrida a la vez (409 si ya hay una). Todas exigen `X-Dogfood: 1`.
2. Web: botón **«Nueva corrida»** con un `dialog` (formulario con objetivo, ref, número de personas, escenarios multi-select, publicar sí/no con advertencia de que publica en GitHub), página de progreso en vivo de la corrida (barra, casos en curso, link a la vista en vivo), botones **«Repetir caso»** en la ejecución y **«Cancelar»** en la corrida.

Done when: estos tests pasan en `tests/test_panel_acciones.py` (lanzador falso) y `web/src/features/acciones/acciones.test.tsx`:
- el POST lanza con los argumentos correctos y `--sin-publicar` por defecto;
- una segunda corrida mientras hay una activa da 409;
- sin `X-Dogfood` da 403;
- cancelar detiene el proceso;
- el formulario manda lo elegido y la página de progreso se actualiza con el estado.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Orquestación de procesos con contratos claros.
- **Dependencies**: F10.2.T2
- **Files**:
  - `src/dogfood/panel/acciones.py`
  - `src/dogfood/panel/app.py`
  - `tests/test_panel_acciones.py`
  - `web/`

### F10.2.T4 — Reporte de corrida compartible

1. Web: página **«Reporte»** de cada corrida (`/corridas/$id/reporte`), pensada para mostrársela a alguien: portada con la tasa de éxito como gráfico radial, casos por estado, hallazgos por gravedad con su sugerencia resumida, tabla de casos fallidos con miniatura y link, opinión de usuarios por pantalla con citas, y costo y duración. Diseño limpio de una sola columna, apto para imprimir (`@media print`).
2. Botón **«Descargar PDF»**: `GET /api/corridas/{id}/reporte.pdf` lo genera con Playwright (`page.pdf`) sobre esa misma página, en `src/dogfood/panel/pdf.py`.
3. Botón **«Copiar resumen»** que copia un texto corto para Slack o un PR (tasa de éxito, hallazgos altos y críticos con link, link al reporte).

Done when: estos tests pasan en `web/src/features/reporte/reporte.test.tsx` y `tests/test_panel_pdf.py`:
- el reporte muestra la tasa de éxito, los conteos por estado y gravedad y las citas;
- el PDF de una corrida de prueba se genera y tiene más de 0 páginas;
- «Copiar resumen» deja en el portapapeles el texto con los conteos.
Deja capturas del reporte y del PDF en el PR.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Pantalla de presentación con datos ya existentes.
- **Dependencies**: F10.2.T3
- **Files**:
  - `src/dogfood/panel/pdf.py`
  - `src/dogfood/panel/app.py`
  - `tests/test_panel_pdf.py`
  - `web/`

## F10.9 — Package: verificación

### F10.9.T1 — Repetir la corrida real de 10 personas y verificar

En el server, con todo lo anterior mergeado: corre `uv run dogfood run --target predicts --ref master --personas 10 --seed 2 --sin-publicar --vista` (como servicio con `systemd-run --user`, para que no se corte) y verifica:
- 10 ejecuciones y todos los escenarios con personas compatibles cubiertos;
- ninguna ejecución con «juez no disponible» (si 9router falla, que el respaldo responda);
- el detector del objetivo corrió sin error (hallazgos del oráculo, aislamiento y reglas, o ninguno);
- los hallazgos técnicos sin el ruido esperado, y el 404 de calidad como uno solo;
- al menos una fricción registrada;
- el plan de pruebas, las sugerencias y el reporte se ven en el panel publicado (`https://dogfood.knaimero.app`, tras el redeploy de F9.9; si el panel no se actualizó, corre `scripts/build-web.sh` y `systemctl --user restart dogfood-panel`).

Escribe el resultado en `docs/notas/corrida-10-v2.md`: tasa de éxito por escenario, hallazgos reales de predicts (con su sugerencia), costo, duración y lo que todavía falla en dogfood. Si algo de dogfood falla, arréglalo si es chico (puedes editar los archivos de abajo) o anótalo como pendiente; los bugs de predicts no se arreglan aquí.

Done when: la corrida terminó, `docs/notas/corrida-10-v2.md` existe con esos datos y `uv run pytest` sigue verde.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Corrida real de punta a punta con ajustes chicos.
- **Dependencies**: F10.1.T1, F10.1.T3, F10.1.T4, F10.2.T4
- **Files**:
  - `docs/notas/corrida-10-v2.md`
  - `src/dogfood/corrida.py`
  - `src/dogfood/agente/navegador.py`
  - `src/dogfood/deteccion/tecnicos.py`
