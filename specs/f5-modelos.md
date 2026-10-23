---
type: spec
project_id: dogfood
phase: 5
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
  - specs/f4-reporte.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-24
title: Modelos y consistencia
---

# F5 — Modelos y consistencia

M5 del PRD: varios modelos por rol vía 9router, comparación entre ellos y tasa de éxito al repetir escenarios. FR-24 y FR-25.

## F5.1 — Package: modelos por rol

### F5.1.T1 — Varios modelos por rol y comparación en el reporte

1. En `src/dogfood/llm.py`, agrega `modelos_para(rol) -> list[str]` y una estrategia de asignación configurable en `dogfood.yaml` (`asignacion_modelos: rotar | primero`). Con `rotar`, las ejecuciones de la corrida reparten los modelos del rol `persona` de forma determinista según la semilla. El rol `juez` sigue usando un solo modelo por corrida, para que la comparación sea justa.
2. En `src/dogfood/corrida.py`, guarda en cada `Ejecucion.modelo` el modelo efectivo y pasa el índice a `cliente_para`.
3. Crea `src/dogfood/reporte/modelos.py`: una tabla por modelo con ejecuciones, tasa de éxito, pasos promedio, fricciones por ejecución, hallazgos únicos que solo encontró ese modelo, tokens y costo por ejecución. Agrega la sección «Modelos» al reporte desde `opinion.generar`, sumando una sola llamada en `opinion.py`, que es la única edición permitida en ese archivo.

Done when: estos tests pasan en `tests/test_modelos.py`:
- con tres modelos y nueve ejecuciones en modo `rotar`, cada modelo recibe tres;
- la misma semilla da el mismo reparto;
- el juez usa siempre el mismo modelo;
- la tabla calcula bien la tasa de éxito y los hallazgos únicos por modelo;
- el reporte incluye la sección «Modelos».

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Cambios acotados en piezas ya probadas.
- **Dependencies**: F4.6.T1
- **Files**:
  - `src/dogfood/llm.py`
  - `src/dogfood/corrida.py`
  - `src/dogfood/reporte/modelos.py`
  - `src/dogfood/reporte/opinion.py`
  - `tests/test_modelos.py`

## F5.2 — Package: repetición

### F5.2.T1 — `--repeat` y tasa de éxito por escenario

1. En `src/dogfood/comandos/run.py` y `src/dogfood/corrida.py`, `--repeat N` ejecuta cada asignación (persona × escenario) N veces, con la **misma** persona y el mismo dataset, sobre la misma instancia. Cada repetición necesita su propia cuenta, porque el email ya existe: la persona recibe el sufijo `+r<k>` en el email (`ana.3+r2@dogfood.test`).
2. Crea `src/dogfood/reporte/consistencia.py`. Por escenario calcula: tasa de éxito con su intervalo de Wilson al 95 %, desvío de pasos, hallazgos que aparecen en todas las repeticiones contra los que aparecen en algunas (inestables), y lo mismo por modelo si hay varios. Agrega la sección «Consistencia» al reporte con una sola llamada en `opinion.py`.
3. Los hallazgos que aparecen en menos de la mitad de las repeticiones se marcan como `inestable` en la evidencia y se publican con gravedad un nivel menor (NFR-8).

Done when: estos tests pasan en `tests/test_consistencia.py`:
- `--repeat 3` con 2 asignaciones produce 6 ejecuciones con emails `+r1`, `+r2` y `+r3` distintos;
- 2 éxitos de 3 dan una tasa de 0,67 con el intervalo de Wilson correcto;
- un hallazgo en 1 de 3 queda como inestable y baja de gravedad;
- el reporte incluye la sección «Consistencia».

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Estadística simple y cambios acotados.
- **Dependencies**: F5.1.T1
- **Files**:
  - `src/dogfood/comandos/run.py`
  - `src/dogfood/corrida.py`
  - `src/dogfood/reporte/consistencia.py`
  - `src/dogfood/reporte/opinion.py`
  - `tests/test_consistencia.py`
