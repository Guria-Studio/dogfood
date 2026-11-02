---
type: spec
project_id: dogfood
phase: 12
version: 0.1
depends_on:
  - docs/analisis/testsprite.md
  - specs/f11-ux-testsprite.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-11-01
title: Diff de comportamiento entre versiones (con REA)
---

# F12 — Diff de comportamiento entre versiones

Héctor pidió instalar REA (`morluto/rea`, «Reverse Engineer Anything») y tomar de ahí algo que dogfood no hace. REA está instalado en el server: CLI `rea` 6.8.0 en `/home/knaimero/.hermes/tools/node-26.12.1-linux-x64/bin/rea`, MCP registrado en Claude Code y skill en `~/.claude/skills/reverse-engineer-anything/` (léela, en especial `references/environments.md`).

**La idea:** REA graba un recorrido de navegador como evidencia normalizada (`rea capture-browser-scenario`: pasos, red, consola, storage y capturas) y **compara dos grabaciones** (`rea compare-web-captures`), alineando paso a paso qué cambió: requests nuevas o que desaparecieron, códigos de estado, texto, capturas. Ni dogfood ni TestSprite hacen eso. Hoy dogfood dice «este caso pasó o falló», pero no **qué cambió en el comportamiento entre `master` y un PR** cuando los dos «pasan».

**Lo que construimos:** grabar los casos de prioridad alta contra la ref base y contra la ref nueva, compararlos con REA y mostrar el diff de comportamiento en el panel y en el PR. Por ejemplo:
- «En el paso *Subir CSV*, `POST /api/datasets` pasó de 201 a 422»;
- «Apareció `GET /api/datasets/{id}/calidad` con 404»;
- «Cambió el texto del total de 1.234 a 1.243»;
- «La captura difiere un 18 %».

Probado a mano el 2026-11-01: dos grabaciones del mismo escenario, comparadas con `compare-web-captures` sobre su `normalized_result`, dan `comparison_kind: browser_scenario`, `alignment.status: aligned` y `steps[].artifact_diffs`. La comparación exige el `normalized_result` de la evidencia, no la evidencia completa. Sin reglas de normalización, cualquier valor que cambia en cada corrida (tokens, ids, fechas) sale como cambio, así que hacen falta reglas propias.

Reglas para todas las tareas:
- Llama a REA solo por su CLI, desde un único adaptador, con la versión fija (`rea` del PATH; si no está, `npx -y rea-agents@6.8.0`) y `--format json`.
- Ningún secreto en la grabación: las contraseñas de las personas van como `secrets` del escenario (por variable de entorno), y todo lo que se guarda pasa por `redactar`.
- Solo contra instancias aisladas de dogfood, nunca contra producción.

## F12.1 — Package: núcleo

### F12.1.T1 — Adaptador de REA y grabación de un caso como escenario

1. `src/dogfood/rea/adaptador.py`:
   - `disponible() -> bool`;
   - `grabar(escenario: dict, destino: Path) -> Path`: corre `capture-browser-scenario` y guarda la evidencia y su `normalized_result` por separado;
   - `comparar(antes: Path, despues: Path, reglas: dict) -> dict`: corre `compare-web-captures` con `--normalization-json`.

   Timeouts, errores de REA como excepción tipada con su `code` y `message`, y lo que imprime REA pasado por `redactar` antes de escribirlo.
2. `src/dogfood/rea/escenario.py`: `desde_ejecucion(ejecucion, instancia) -> dict`. Convierte el historial de una ejecución exitosa (el mismo que usa `agente/replay.py`) en un escenario de REA:
   - `goto`, `click`, `fill` y `press` con locators CSS o de rol, cada uno con `timeout_ms`;
   - la contraseña como `secret`;
   - `start_url` de la instancia;
   - `browser.mode: launch` con el Chromium de Playwright.

   Si una acción no se puede traducir, el escenario se corta ahí, con un aviso.
3. `src/dogfood/rea/normalizacion.py`: reglas por defecto para que el diff no salga lleno de ruido. Ignoran tokens, ids, UUIDs, fechas y emails de las personas, que cambian en cada corrida. Además, cada objetivo puede sumar las suyas (método opcional `reglas_diff()` en el objetivo de predicts).

Done when: estos tests pasan en `tests/test_rea_adaptador.py` y `tests/test_rea_escenario.py`:
- con un `rea` falso en el PATH, `grabar` y `comparar` arman los argumentos correctos, y un error de REA sale como excepción con su `code`;
- un historial de ejecución de prueba se traduce a un escenario válido, con la contraseña como secreto y no literal;
- una acción no traducible corta el escenario con su aviso;
- un secreto plantado no queda en los archivos guardados.

Hay también un test marcado `@pytest.mark.rea` (excluido del CI por defecto) que, con el `rea` real, graba dos veces una página HTML estática servida localmente y verifica que la comparación con las reglas por defecto da `unchanged`.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 5h
- **Reason**: Integración con una herramienta externa nueva y traducción de historiales; requiere criterio.
- **Dependencies**: F11.3.T2
- **Files**:
  - `src/dogfood/rea/`
  - `src/dogfood/objetivos/predicts/__init__.py`
  - `tests/test_rea_adaptador.py`
  - `tests/test_rea_escenario.py`
  - `pyproject.toml`

### F12.1.T2 — Comando `dogfood diff` entre dos refs

`dogfood diff --target <proyecto> --base <ref> --nueva <ref> [--casos alta|todos|TC001,TC007]`. Hace lo siguiente:
1. Toma, de la última corrida exitosa del proyecto, las ejecuciones que pasaron de los casos elegidos (o lanza antes una corrida chica si no hay ninguna).
2. Levanta la instancia aislada de `--base`, graba cada caso y la destruye. Después hace lo mismo con `--nueva`.
3. Compara caso por caso y escribe `runs/diff-<id>/` con:
   - `diff.json`: por caso, un resultado (`sin_cambios`, `cambios` o `no_alineado`) y sus pasos con cambios;
   - `resumen.md`;
   - las capturas de antes y después de cada paso que cambió.
4. Clasifica cada cambio:
   - red: request nueva, request que desapareció, cambio de código de estado (en un 4xx o 5xx nuevo la gravedad es `alta`), cambio de método o ruta;
   - texto: cambio de texto visible;
   - visual: diferencia de captura, usando `rea compare-web-screenshots` si hace falta;
   - consola: error nuevo.
5. Guarda el diff en el almacén (tabla `diffs`, con su migración) para el panel.

Done when: estos tests pasan en `tests/test_diff.py`, con el adaptador falso devolviendo comparaciones grabadas en `tests/fixtures/rea/`:
- un 201 que pasa a 422 sale como cambio de red de gravedad alta en el paso correcto;
- una request nueva y otra que desapareció salen como tales;
- dos grabaciones iguales dan `sin_cambios`;
- un caso cuyos pasos no se alinean sale `no_alineado` con su motivo;
- `resumen.md` lista los casos con cambios primero;
- el diff queda en la base y se lee de vuelta.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Orquestación y clasificación sobre un formato ya definido.
- **Dependencies**: F12.1.T1
- **Files**:
  - `src/dogfood/comandos/diff.py`
  - `src/dogfood/diff.py`
  - `src/dogfood/almacen.py`
  - `src/dogfood/cli.py`
  - `tests/test_diff.py`
  - `tests/fixtures/rea/`

## F12.2 — Package: producto

### F12.2.T1 — Diff en el panel y en el PR

1. API:
   - `GET /api/proyectos/{slug}/diffs`;
   - `GET /api/diffs/{id}`;
   - `POST /api/proyectos/{slug}/diffs`, que lanza `dogfood diff` con el mismo lanzador de F10.2.T3 y exige `X-Dogfood: 1`.
2. Web: una entrada **«Cambios entre versiones»** en la barra del proyecto (grupo Análisis, debajo de Insights), con:
   - la lista de diffs: base → nueva, casos con cambios sobre el total, fecha;
   - el detalle por caso, con la línea de tiempo de pasos alineados. Cada paso cambiado muestra sus chips por tipo (red, texto, visual, consola), la tabla de requests antes y después con el código de estado en rojo o verde, el texto antes y después resaltado, y el **deslizador antes/después** de las capturas;
   - el botón «Nuevo diff» (dialog con base y nueva, que trae `master` y el último PR por defecto).
3. En `dogfood ci` (de F11.3.T2): si el proyecto tiene el diff activado, después de los casos corre `dogfood diff --base <rama base del PR> --nueva <sha>`. El comentario del PR suma la sección «Cambios de comportamiento» con los cambios de gravedad alta y el link al diff en el panel. Un 4xx o 5xx nuevo hace fallar el check solo si el proyecto lo pide (`diff_bloquea: true`).

Done when: estos tests pasan en `tests/test_panel_diffs.py`, `tests/test_cli_ci.py` (casos nuevos) y `web/src/features/diffs/diffs.test.tsx`:
- la lista y el detalle muestran los cambios clasificados;
- el deslizador cambia entre las dos capturas;
- el comentario del PR incluye la sección cuando hay cambios altos y la omite si no hay;
- `diff_bloquea` decide el código de salida.

Deja capturas del detalle en el PR.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Pantalla y wiring sobre datos ya estructurados.
- **Dependencies**: F12.1.T2, F11.9.T1
- **Files**:
  - `src/dogfood/panel/api_diffs.py`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/comandos/ci.py`
  - `tests/test_panel_diffs.py`
  - `tests/test_cli_ci.py`
  - `web/`

## F12.9 — Package: verificación

### F12.9.T1 — Diff real de predicts entre dos commits

En el server, con todo lo anterior mergeado:
1. Elige dos commits reales de predicts: `master` y el anterior que haya tocado `web/` o la API (`git -C /mnt/storage/project/predicts log`).
2. Corre `uv run dogfood diff --target predicts --base <anterior> --nueva master --casos alta`.
3. Revisa el resultado en el panel y ajusta las reglas de normalización hasta que el ruido (ids, fechas, tokens) desaparezca y solo queden cambios reales. Cada regla nueva lleva su test.
4. Escribe `docs/notas/diff-predicts.md`: los commits, qué cambios reales detectó, cuánto ruido quedó, el costo y la duración, y si vale la pena dejarlo en el CI de predicts.
5. Agrega la página `docs/ayuda/cambios-entre-versiones.md` a la ayuda.

Done when: el diff real terminó, `docs/notas/diff-predicts.md` y la página de ayuda existen, y `uv run pytest` sigue verde.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Corrida real y ajuste fino de reglas.
- **Dependencies**: F12.2.T1
- **Files**:
  - `docs/notas/diff-predicts.md`
  - `docs/ayuda/cambios-entre-versiones.md`
  - `src/dogfood/rea/normalizacion.py`
  - `tests/test_rea_normalizacion.py`
