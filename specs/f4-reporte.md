---
type: spec
project_id: dogfood
phase: 4
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
  - specs/f3-deteccion.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-24
title: Issues y reporte
---

# F4 — Issues y reporte

M4 del PRD: hallazgos reproducibles, sin secretos, deduplicados y publicados como issues en `hectorcanaimero/predicts` (repo **público**); reporte de opinión en español y resumen en Slack. FR-17 a FR-21, NFR-3, NFR-4 y NFR-8.

## F4.1 — Package: redacción

### F4.1.T1 — Redacción de secretos y datos sensibles

Implementa `src/dogfood/reporte/redactar.py` (NFR-3 y NFR-4). Todo texto que salga de la máquina (issues, comentarios, Slack, reporte HTML) pasa por `redactar(texto, secretos_conocidos) -> str`, que reemplaza por `«redactado»`:
- los valores de todos los secretos cargados por `config` (vienen como lista; nunca los imprimas);
- cookies y encabezados `Cookie`, `Set-Cookie` y `Authorization`;
- tokens con forma de JWT, `sk-…`, hex o base64 de 32 caracteres o más;
- parámetros `token=`, `key=` y `password=` en URLs;
- las contraseñas de las personas;
- cualquier email que no sea de `@dogfood.test`;
- rutas absolutas de `/home/...`, salvo la de `runs/` relativa.

Además, `verificar_limpio(texto) -> list[str]` devuelve lo que parece secreto y sirve como última barrera antes de publicar.

Done when: estos tests pasan en `tests/test_redactar.py`:
- una API key conocida desaparece aunque esté dentro de una URL;
- un `Set-Cookie: sesion=abc…` queda redactado;
- un JWT queda redactado;
- `ana.3@dogfood.test` se mantiene y `x@gmail.com` se redacta;
- `verificar_limpio` detecta un `sk-` que quedó;
- un texto sin secretos queda idéntico.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 2h
- **Reason**: Reglas de redacción acotadas pero críticas para un repo público.
- **Dependencies**: F0.1.T4
- **Files**:
  - `src/dogfood/reporte/__init__.py`
  - `src/dogfood/reporte/redactar.py`
  - `tests/test_redactar.py`

## F4.2 — Package: issues

### F4.2.T1 — Publicación de hallazgos como issues con deduplicación

Implementa `src/dogfood/reporte/issues.py` (FR-17, FR-18, FR-19, NFR-8, decisiones D6 y D14, *Interfaces → Issue publicado* de la arquitectura).

`publicar(hallazgos, corrida, config, publicar=True) -> list[ResultadoIssue]`:
1. Filtra: los `solo_reporte` y los que estén bajo `umbral_publicar` no se publican; quedan en el reporte.
2. Arma el cuerpo con la plantilla de la arquitectura: pasos, esperado/obtenido, evidencia en texto, ruta local de las capturas, `dogfood replay <id>`, commit de predicts, semilla y `<!-- dogfood:huella=… -->`. Todo pasa por `redactar`; si `verificar_limpio` encuentra algo, **no publica** ese hallazgo y lo marca como `bloqueado_por_redaccion`.
3. Deduplica con `gh issue list -R <repo> --label dogfood --state open --search "dogfood:huella=<h> in:body" --json number,url`:
   - si existe, comenta la nueva ocurrencia (corrida, fecha, commit y número de ocurrencias);
   - si no, crea el issue con las etiquetas `dogfood`, `dogfood:<tipo>` y `gravedad:<g>`, creándolas antes si no existen (`gh label create --force`).
4. Usa `gh` por subprocess con el `-R` del config. Con `publicar=False` (`--sin-publicar`), no llama a `gh` para escribir, pero sí calcula qué haría.
5. Guarda en el almacén `issue_url` y `nuevo` por hallazgo.

Un tope de seguridad, `max_issues_nuevos_por_corrida` (por defecto 15), corta la publicación y avisa en el reporte, como protección de NFR-8.

Done when: estos tests pasan en `tests/test_issues.py`, con `gh` falso (un ejecutable en `tmp_path` que registra sus argumentos y responde JSON guionado):
- un hallazgo nuevo crea un issue con las tres etiquetas y la huella en el cuerpo;
- un hallazgo cuya huella ya existe comenta en vez de crear;
- un hallazgo bajo el umbral no llama a `gh`;
- un cuerpo con un secreto queda en `bloqueado_por_redaccion` y no se publica;
- con `publicar=False` no hay llamadas de escritura;
- pasado el tope, el resto queda sin publicar y con aviso.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 4h
- **Reason**: Publica en un repo público; la deduplicación y la redacción no pueden fallar.
- **Dependencies**: F4.1.T1, F0.1.T3
- **Files**:
  - `src/dogfood/reporte/issues.py`
  - `tests/test_issues.py`

## F4.3 — Package: replay

### F4.3.T1 — Replay de una ejecución o un hallazgo

Implementa `src/dogfood/agente/replay.py` y `src/dogfood/comandos/replay.py` (FR-17). `dogfood replay <hallazgo_id|ejecucion_id> [--ref main]`:
1. Busca la ejecución en el almacén, y su dataset y su persona.
2. Levanta una instancia limpia con `objetivo.preparar(ref)`.
3. Vuelve a ejecutar el historial de browser-use sin LLM (`Agent.rerun_history` o la API equivalente de la versión instalada; léela en el paquete). Como la cuenta no existe en la instancia nueva, el primer tramo (el registro) se repite tal cual.
4. Corre solo los detectores que produjeron el hallazgo original.
5. Informa uno de tres resultados: `reproduce` (misma huella), `no_reproduce` o `no_reproducible_por_cambio_ui` (el historial falló en un paso antes de llegar a la pantalla del hallazgo).
6. Destruye la instancia.

Done when: estos tests pasan en `tests/test_replay.py`, con un `Objetivo` falso, un historial falso y un `rerun` falso:
- si la huella aparece de nuevo, el resultado es `reproduce`;
- si el rerun falla en el paso 3 de 10 con el hallazgo en el paso 8, es `no_reproducible_por_cambio_ui`;
- si no aparece, `no_reproduce`;
- la instancia se destruye siempre, incluso si el rerun lanza una excepción.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Integración puntual con la API de historial de browser-use.
- **Dependencies**: F1.4.T1, F3.2.T1
- **Files**:
  - `src/dogfood/agente/replay.py`
  - `src/dogfood/comandos/replay.py`
  - `tests/test_replay.py`

## F4.4 — Package: opinión

### F4.4.T1 — Reporte de opinión de usuarios

Implementa `src/dogfood/reporte/opinion.py` y las plantillas Jinja2 en `src/dogfood/reporte/plantillas/` (FR-20).

`generar(corrida, ejecuciones, hallazgos, personas) -> (ruta_md, ruta_html)` escribe `reporte.md` y `reporte.html`, autocontenido, con las capturas como miniaturas por ruta relativa. Todo va en español. Secciones:
1. **Resumen:** personas, escenarios, tasa de éxito por escenario, hallazgos por gravedad y tipo (con los links a issues si los hay), duración y costo (el de dogfood, exacto, y el de predicts, marcado como **estimado** según D12: cuenta las filas de `decisiones_jev` y las plantillas generadas en el Postgres de la instancia antes de destruirla, a través de una función `contar_uso_ia(instancia)` de este módulo, con el costo unitario de `dogfood.yaml`).
2. **Por pantalla:** qué no se entendió, qué frustró, qué sobró y qué funcionó. Agrupa las fricciones con el rol `dedupe` del LLM (es el único lugar donde se usa) y cita textos reales con el número de personas.
3. **Por tipo de usuario:** destreza baja contra alta, por idioma y por rubro.
4. **Hallazgos sin publicar:** los de solo reporte, los que quedaron bajo el umbral y los bloqueados por redacción.

La redacción final de los párrafos la hace el rol `redactor` con `completar_json`, a partir de datos ya agregados: el LLM no inventa conteos. Todo el texto pasa por `redactar`.

Done when: estos tests pasan en `tests/test_opinion.py`, con un LLM falso:
- el Markdown tiene las cuatro secciones;
- los conteos por pantalla coinciden con los datos de entrada, sin que importe la salida del LLM;
- el HTML se genera y referencia capturas por ruta relativa;
- un secreto plantado en una fricción no aparece en ningún archivo;
- el costo de predicts aparece marcado como estimado.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Agregación más plantillas; el LLM solo redacta.
- **Dependencies**: F0.1.T3, F0.1.T4, F4.1.T1
- **Files**:
  - `src/dogfood/reporte/opinion.py`
  - `src/dogfood/reporte/plantillas/reporte.md.j2`
  - `src/dogfood/reporte/plantillas/reporte.html.j2`
  - `tests/test_opinion.py`

## F4.5 — Package: Slack

### F4.5.T1 — Resumen en Slack

Implementa `src/dogfood/reporte/slack.py` (FR-21, decisión D11). `avisar(corrida, resumen, config)` envía, por el webhook de `~/.config/dogfood/slack.env`, un mensaje en español con:
- objetivo, ref y commit;
- personas y tasa de éxito;
- hallazgos por gravedad;
- los issues nuevos y comentados (máximo 10 links);
- la ruta del reporte en el server;
- costo y duración.

Sin el archivo `slack.env`, avisa en la consola y no falla la corrida. El texto pasa por `redactar`.

Done when: estos tests pasan en `tests/test_slack.py`, con `respx`:
- el POST lleva el texto con los conteos;
- sin `slack.env` no hay POST ni excepción;
- un error 500 del webhook se registra y no rompe nada;
- un secreto plantado no aparece en el cuerpo.

- **Model**: claude/claude-haiku-5-5
- **Estimate**: 1h
- **Reason**: Integración trivial.
- **Dependencies**: F0.1.T4, F4.1.T1
- **Files**:
  - `src/dogfood/reporte/slack.py`
  - `tests/test_slack.py`

## F4.6 — Package: cierre de corrida

### F4.6.T1 — Publicación, reporte y aviso al cerrar la corrida

Modifica `src/dogfood/corrida.py` para que, después de los detectores y **antes** de destruir la instancia, haga lo siguiente:
1. calcular `contar_uso_ia(instancia)`;
2. `issues.publicar(hallazgos, publicar=not opciones.sin_publicar)`;
3. `opinion.generar(...)`;
4. `slack.avisar(...)`.

Si uno de estos pasos falla, se registra y la corrida sigue con los demás (estado `ok_con_avisos`). Imprime al final la ruta del reporte y los links de los issues. Agrega `--tope-usd` (NFR-6): antes de lanzar cada ejecución, si el costo acumulado de `uso_llm` supera el tope, no lanza más, cierra la corrida con el motivo `tope_usd` y aun así genera el reporte de lo hecho.

Done when: estos tests pasan en `tests/test_corrida_cierre.py`, con fakes:
- el orden de las llamadas es contar → publicar → opinión → Slack → destruir;
- con `sin_publicar`, `publicar` recibe `publicar=False`;
- si Slack falla, el estado es `ok_con_avisos` y el reporte existe;
- con un tope de 0,01 y ejecuciones que cuestan 0,02, se ejecuta una sola y el motivo es `tope_usd`.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 2h
- **Reason**: Cableado con contratos ya probados.
- **Dependencies**: F2.4.T1, F4.2.T1, F4.4.T1, F4.5.T1
- **Files**:
  - `src/dogfood/corrida.py`
  - `tests/test_corrida_cierre.py`
