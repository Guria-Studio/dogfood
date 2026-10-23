---
type: spec
project_id: dogfood
phase: 3
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
  - specs/f2-poblacion.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-24
title: Detección
---

# F3 — Detección

M3 del PRD: detectar fallos técnicos, números equivocados frente a la verdad, fugas entre empresas, violaciones de las reglas de predicts y fricción. FR-12 a FR-16.

Todos los detectores tienen la firma `detectar(ctx: ContextoDeteccion) -> list[Hallazgo]` (o `verificar` en los de predicts). Cada hallazgo trae su `huella`, calculada con `Hallazgo.calcular_huella(firma)` y la firma normalizada que se describe en cada tarea, porque F4 deduplica por huella.

## F3.1 — Package: cliente API

### F3.1.T1 — Cliente HTTP de predicts

Implementa `src/dogfood/objetivos/predicts/cliente.py`: `PredictsCliente(api_url)` con httpx, cookie de sesión y métodos tipados para las rutas que usan los detectores. Toma los nombres y las formas del OpenAPI real: levanta la instancia o lee `api/src/predicts/api/*.py` en `/mnt/storage/project/predicts`. **No inventes campos.**

Métodos:
- `login(email, contrasena)` y `yo()`;
- `proyectos()` y `datasets(proyecto_id)`;
- `mapeo(dataset_id)` y `calidad(dataset_id)`;
- `analisis_de(dataset_id)` y `analisis(analisis_id)`, que devuelve resumen y `metricas`;
- `resultados(analisis_id, tipo, todas_las_paginas=True)` para `recompra`, `ciclos`, `riesgo` y `ofertas`;
- `exportar(analisis_id, tipo) -> bytes`;
- `get_crudo(ruta) -> (status, json|texto)`, para la auditoría de aislamiento.

Además, `cliente_para(instancia, persona) -> PredictsCliente` hace login con `cuentas.credenciales` y es lo que se entrega como `ctx.cliente_api`.

Done when: estos tests pasan en `tests/test_predicts_cliente.py`, con `respx`:
- el login guarda la cookie y la envía en `yo()`;
- `resultados(..., todas_las_paginas=True)` sigue la paginación hasta el final;
- un 401 da `ErrorSesion`;
- `get_crudo` devuelve el estado sin lanzar una excepción en un 403.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 2h
- **Reason**: Cliente HTTP con contrato conocido.
- **Dependencies**: F2.3.T1
- **Files**:
  - `src/dogfood/objetivos/predicts/cliente.py`
  - `tests/test_predicts_cliente.py`

## F3.2 — Package: detector técnico

### F3.2.T1 — Fallos técnicos: consola, red, logs y trabajos colgados

Implementa `src/dogfood/deteccion/tecnicos.py` (FR-12):
- **red:** cada estado ≥ 500, o 4xx inesperado. Un 401 antes del login, un 404 de un recurso que la persona borró, un 422 de validación que la UI mostró como error de formulario y un 429 marcado como esperado en `Ejecucion.notas` no cuentan. Firma: `método + ruta con ids reemplazados por {id} + estado`. Gravedad: 5xx alta, 4xx media.
- **consola:** errores de JavaScript (`console.error` y excepciones no capturadas). Firma: el mensaje sin números, ids ni URLs. Gravedad media, o alta si después de ese evento no hay más pasos (pantalla muerta).
- **logs:** en `ctx.logs["api"]` y `ctx.logs["worker"]`, los tracebacks de Python y las líneas de nivel ERROR durante la corrida. Firma: el tipo de excepción y el último frame del paquete `predicts`. Gravedad alta. Asocia el hallazgo a la ejecución cuyo intervalo de tiempo contiene la línea, si la hay.
- **pantalla en blanco:** un paso cuya captura es casi uniforme (desvío de píxeles bajo un umbral) después de una navegación. Gravedad alta.
- **trabajo colgado:** una ejecución que esperó un trabajo (lo marca el agente con fricción o con timeout) y cuyo análisis sigue sin estar `listo` en la API después de `TIMEOUT_TRABAJO_S`. Gravedad alta.

Hallazgos con la misma huella dentro de una corrida se fusionan en uno con varias ocurrencias, sin duplicar la evidencia.

Done when: estos tests pasan en `tests/test_deteccion_tecnicos.py`, con ejecuciones y logs de ejemplo:
- un 500 genera un hallazgo alto con la ruta normalizada;
- dos 500 en la misma ruta con distintos ids dan una sola huella;
- un 429 marcado como esperado no genera nada;
- un traceback del worker da un hallazgo con el tipo de excepción;
- una captura blanca da «pantalla en blanco»;
- un `console.error` seguido del fin de los pasos da gravedad alta.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Reglas claras y bien testeables.
- **Dependencies**: F1.4.T1, F1.1.T1
- **Files**:
  - `src/dogfood/deteccion/tecnicos.py`
  - `tests/test_deteccion_tecnicos.py`
  - `tests/fixtures/logs/`

## F3.3 — Package: oráculo

### F3.3.T1 — Oráculo de números contra la verdad

Implementa `src/dogfood/objetivos/predicts/oraculo.py` (FR-13, decisión D4: tolerancias, no igualdad; las tolerancias se leen de `dogfood.yaml`). Antes de escribir nada, lee el modelo de predicts en `/mnt/storage/project/predicts/docs/arch/001-predicts.md` («Modelo de recompra» e «Interfaces → Modelo») y las columnas reales de `api/src/predicts/api/analisis.py` (`_RESULTADOS`).

Para cada ejecución con un análisis terminado, usa `ctx.cliente_api(persona)` para traer el análisis, sus métricas y todos los resultados, y compáralos con el `verdad.json` de su dataset:

1. **Correspondencia:** une los productos de predicts con los de la verdad por SKU, EAN o nombre. Cuenta los grupos de productos que hizo predicts. Lo que no se pueda unir no se compara, y si es más del 10 % genera un hallazgo `logica` medio «productos no reconocidos». Los clientes se unen por `cliente_id`. Si `verdad.defectos` incluye algo de `defectos_que_rompen_verdad()`, salta las comparaciones numéricas.
2. **Chequeos exactos** (cualquier violación es un hallazgo `logica` alto, con el par como ejemplo, el esperado y el obtenido):
   - ningún par con menos de `MIN_COMPRAS` fechas distintas en la verdad tiene `fecha_probable`;
   - en recompra, `fecha_min ≤ fecha_probable ≤ fecha_max` y `0 ≤ p ≤ 1`;
   - `n_compras` igual al de la verdad (días distintos);
   - `dias_desde_ultima` coherente con `ultima_compra` y la fecha de referencia del análisis;
   - el CSV de `exportar(recompra)` tiene las mismas filas (cliente, producto, fecha_probable) que `resultados(recompra)`.
3. **Chequeos estadísticos** (un hallazgo `logica` por chequeo fallido, con las cifras):
   - en los pares con 6 compras o más, al menos `tolerancias.ciclo_pct_pares` (80 %) tienen `|ciclo − ciclo_real| / ciclo_real ≤ tolerancias.ciclo_err` (25 %);
   - en ciclos por producto, `ciclo_mediano` está a ±20 % de la mediana de los `ciclo_real_dias` de ese producto;
   - el MAE en días que dogfood recalcula con su propia verdad, sobre la ventana de backtest que declara predicts, está a ±1 día del `mae_dias` declarado;
   - en datos sin defectos, el modelo no es peor que la línea base en `precision_at_k` por más de 0,05;
   - en riesgo, al menos el 60 % de los clientes marcados con nivel alto abandonaron en la verdad, y al menos el 50 % de los que abandonaron con 4 compras o más aparecen en riesgo.
4. **Firma:** `chequeo + tipo de análisis`. El título dice qué chequeo falló, no los números, para que la deduplicación funcione entre corridas.

Done when: estos tests pasan en `tests/test_predicts_oraculo.py`, con verdad y resultados sintéticos armados en el test (sin red):
- resultados que coinciden con la verdad no dan hallazgos;
- un ciclo desplazado un 40 % en todos los pares da el hallazgo de ciclo;
- un par con 2 compras y fecha predicha da el hallazgo exacto;
- un export con una fila de menos da el hallazgo de exportación;
- un `mae_dias` declarado inflado 3 días da el hallazgo de backtest;
- un dataset con el defecto `vacio` no se compara;
- las huellas no dependen de los números.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 6h
- **Reason**: Razonamiento estadístico y riesgo de falsos positivos en un repo público.
- **Dependencies**: F3.1.T1, F2.1.T1
- **Files**:
  - `src/dogfood/objetivos/predicts/oraculo.py`
  - `tests/test_predicts_oraculo.py`

## F3.4 — Package: aislamiento

### F3.4.T1 — Auditoría de aislamiento entre empresas

Implementa `src/dogfood/objetivos/predicts/aislamiento.py` (FR-14). Con al menos dos ejecuciones de empresas distintas que tengan proyecto, dataset y análisis:
1. Junta los ids de A (proyecto, dataset, análisis, plantillas de mensaje, grupos de productos y trabajos) con el cliente de A.
2. Con el cliente de B, pide **cada ruta GET con parámetro de ruta del OpenAPI** de la instancia (`GET {api_url}/openapi.json`), con los ids de A sustituidos. También prueba las rutas PATCH y DELETE, pero **solo** contra un set de recursos de A creado para la auditoría (un proyecto de prueba), nunca contra los recursos que usan las otras ejecuciones.
3. Toda respuesta distinta de 403/404 que devuelva datos de A es un hallazgo `aislamiento` **crítico**, con la ruta, el método, el estado y un extracto sin datos sensibles. Firma: método más ruta normalizada.
4. Prueba también `GET /analisis/{id}/exportar` y `/trabajos/{id}/eventos` (SSE: lee solo el primer evento, con timeout).

Si no hay dos empresas con datos, no hace nada y lo anota en un hallazgo `regla` de gravedad baja, «auditoría de aislamiento no ejecutada».

Done when: estos tests pasan en `tests/test_predicts_aislamiento.py`, con `respx` y un OpenAPI mínimo:
- todas las rutas con 404 no dan hallazgos;
- una ruta que devuelve 200 con datos da un hallazgo crítico con la ruta normalizada;
- los DELETE solo se envían contra el proyecto de auditoría;
- una sola empresa da el hallazgo de «no ejecutada».

- **Model**: claude/claude-opus-5-5
- **Estimate**: 3h
- **Reason**: Auditoría de seguridad; debe ser exhaustiva y no destructiva.
- **Dependencies**: F3.1.T1
- **Files**:
  - `src/dogfood/objetivos/predicts/aislamiento.py`
  - `tests/test_predicts_aislamiento.py`

## F3.5 — Package: reglas

### F3.5.T1 — Reglas propias de predicts

Implementa `src/dogfood/objetivos/predicts/reglas.py` (FR-15). Las reglas salen de `/mnt/storage/project/predicts/CONTEXTO.md`, sección «Reglas que no se negocian».

- **historia insuficiente:** un cliente con una sola compra o con menos de `MIN_COMPRAS` en la verdad no tiene `fecha_probable` en recompra ni en el export. (Comparte la idea con el oráculo, pero esta regla se evalúa también en datos con defectos, usando el conteo del propio CSV subido.) Gravedad alta.
- **evidencia e incertidumbre:** toda fila de recompra trae `n_compras`, `fecha_min` y `fecha_max` no nulos. Gravedad media.
- **Jev bajo el umbral:** si `mapeo(dataset)` trae sugerencias con confianza menor que `CONFIANZA_MAPEO`, la persona tuvo que confirmarlas (aparece un paso de confirmación en la pantalla de mapeo de su ejecución). Si se aplicaron sin confirmación, gravedad alta.
- **sin mezcla de idiomas:** en las capturas de texto del DOM (`Paso.texto_visible` de cada paso), detecta frases en otro idioma que el de la persona con una heurística de palabras frecuentes pt/es/en; se aceptan nombres de productos y marcas. Firma: pantalla más idioma intruso. Gravedad baja.
- **el sistema sugiere, no envía:** ninguna petición de red a dominios de mensajería (WhatsApp, SMTP o servicios de email) durante la corrida. Gravedad crítica.

Done when: estos tests pasan en `tests/test_predicts_reglas.py`:
- una fila con `fecha_probable` para un cliente de una compra da un hallazgo alto;
- una fila sin `fecha_min` da uno medio;
- un mapeo con confianza 0,5 aplicado sin paso de confirmación da uno alto, y con paso, nada;
- una pantalla pt-BR con un párrafo en inglés da uno bajo, pero «Online Retail II» no;
- la heurística de idioma está en una función pura con sus propios casos.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Reglas concretas con heurísticas acotadas.
- **Dependencies**: F3.1.T1
- **Files**:
  - `src/dogfood/objetivos/predicts/reglas.py`
  - `tests/test_predicts_reglas.py`

## F3.6 — Package: fricción y objetivo

### F3.6.T1 — Fricción y verificadores del objetivo en el registro de detectores

Implementa los dos stubs restantes del registro de detección (arquitectura: *Componentes → Detección*):

1. `src/dogfood/deteccion/friccion.py` (FR-16):
   - convierte las `Friccion` de cada ejecución en hallazgos `friccion`;
   - las agrupa por pantalla y por similitud de texto (normalización más similitud de tokens; **sin LLM** aquí);
   - la gravedad depende de cuántas personas distintas la sufrieron: 5 o más, media; 2 a 4, baja; 1, no se publica (queda solo para el reporte de opinión, con `solo_reporte=True`);
   - una ejecución `rendido` sin ninguna fricción recibe una sintética con el motivo de `rendirse`.
2. `src/dogfood/deteccion/objetivo.py`: llama a cada función de `ctx.objetivo.verificadores()` y concatena los resultados. El aislamiento de errores ya lo hace `ejecutar_detectores`; aquí, si un verificador falla, registra cuál fue.

Done when: estos tests pasan en `tests/test_deteccion_friccion.py`:
- cinco personas con la misma queja en el mapeo dan un hallazgo de gravedad media;
- una sola persona da un hallazgo con `solo_reporte=True`;
- textos parecidos («no entiendo qué es SKU» y «qué significa sku??») se agrupan;
- un rendido sin fricción genera la sintética;
- `objetivo.detectar` llama a todos los verificadores.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Agregación y agrupamiento simples.
- **Dependencies**: F1.4.T1, F1.1.T1
- **Files**:
  - `src/dogfood/deteccion/friccion.py`
  - `src/dogfood/deteccion/objetivo.py`
  - `tests/test_deteccion_friccion.py`
