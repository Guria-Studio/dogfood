---
type: spec
project_id: dogfood
phase: 2
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
  - specs/f1-una-persona.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-24
title: Población y datos del mundo real
---

# F2 — Población y datos del mundo real

M2 del PRD: más de 100 personas en pt-BR y es, cada una con su empresa registrada, en paralelo, con CSV que traen defectos reales. FR-6, FR-8, FR-9 y FR-11.

## F2.1 — Package: defectos

### F2.1.T1 — Defectos de mundo real en los CSV

Implementa `src/dogfood/datos/defectos.py` (FR-6). La función `aplicar(csv_limpio: Path, defectos: list[str], semilla) -> Path` escribe un CSV nuevo y **no** toca `verdad.json`, salvo para agregar la lista de defectos aplicados en el campo `defectos`.

Defectos, combinables en este orden de aplicación:
- `sep_punto_coma`, `sep_tab`;
- `latin1`, `cp1252`, `utf8_bom`;
- `fecha_dmy` (`dd/mm/aaaa`), `fecha_mdy`, `fecha_con_hora`;
- `decimal_coma`;
- `ean_cientifico` (`7,89123E+12`), `ean_sin_ceros`;
- `encabezados_pt` (`cliente, pedido, data, sku, ean, produto, quantidade, preco`), `encabezados_es`, `sin_encabezados`;
- `duplicados` (5 % de filas repetidas);
- `ids_vacios` (2 %);
- `fechas_futuras` (1 %);
- `columnas_extra` (vacías y con basura);
- `grande` (repite clientes con otro id hasta llegar a N MB, con la verdad extendida de forma coherente);
- `vacio` (solo encabezados).

`defectos_que_rompen_verdad()` devuelve la lista de defectos tras los cuales el oráculo **no** debe comparar números: `ean_sin_ceros`, `ids_vacios` y `fechas_futuras` siguen siendo comparables; `vacio` no lo es. Documenta cada caso.

En `comandos/datos.py`, activa `--defectos a,b,c`; un nombre desconocido da un error que lista los válidos.

Done when: estos tests pasan en `tests/test_datos_defectos.py`:
- cada defecto, aplicado solo, produce un archivo que `csv`/`codecs` leen con el separador y la codificación esperados;
- `fecha_dmy` convierte `2026-03-05` en `05/03/2026`;
- `ean_cientifico` produce notación científica;
- `duplicados` agrega cerca del 5 % de filas;
- `vacio` deja solo los encabezados;
- la misma semilla da el mismo archivo;
- `verdad.json` solo cambia en el campo `defectos`.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Muchas transformaciones mecánicas pero precisas.
- **Dependencies**: F1.2.T1
- **Files**:
  - `src/dogfood/datos/defectos.py`
  - `src/dogfood/comandos/datos.py`
  - `tests/test_datos_defectos.py`

## F2.2 — Package: personas

### F2.2.T1 — Generador de personas

Implementa `src/dogfood/personas/generador.py` (FR-8, decisión D5: sin LLM y determinista). La función es `generar(n, semilla, idiomas={"pt-BR": 0.5, "es": 0.5}) -> list[Persona]`:
- nombres y apellidos de listas locales de Brasil y de Latam (`personas/nombres.py`, al menos 80 nombres y 80 apellidos por idioma);
- un nombre de empresa plausible por rubro;
- email único `<slug>.<n>@dogfood.test` (dominio reservado, nunca real);
- contraseña aleatoria fuerte por semilla;
- destreza y paciencia de 1 a 5;
- `intencion` repartida para que todas aparezcan cuando n ≥ 10;
- `estilo` como subconjunto de rasgos: `apurado`, `lee_todo`, `faltas_ortografia`, `movil`, `cambia_de_opinion`, `curioso`, `desconfiado`.

`comandos/personas.py`: `dogfood personas --n --seed --idiomas` imprime una tabla y puede guardar JSON con `--salida`.

Done when: estos tests pasan en `tests/test_personas.py`:
- con n=120, los 120 emails son distintos;
- la misma semilla da las mismas personas;
- la proporción de idiomas está dentro de ±10 % de la pedida;
- todas las intenciones aparecen con n=20;
- ningún email termina en un dominio que no sea `dogfood.test`.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Generación determinista con reglas simples.
- **Dependencies**: F0.1.T2, F0.1.T5
- **Files**:
  - `src/dogfood/personas/__init__.py`
  - `src/dogfood/personas/generador.py`
  - `src/dogfood/personas/nombres.py`
  - `src/dogfood/comandos/personas.py`
  - `tests/test_personas.py`

## F2.3 — Package: cuentas

### F2.3.T1 — Cuentas por persona y token de recuperación

Implementa `src/dogfood/objetivos/predicts/cuentas.py` (FR-9, decisiones D7 y D8).

1. `credenciales(persona) -> (email, contrasena)`: las mismas que verá el agente.
2. `confirmar_registro(instancia, persona) -> str | None`: después de la ejecución, verifica por API (`POST /api/auth/login` con httpx, guardando la cookie) que la cuenta existe, y devuelve el `empresa_id` de `GET /api/auth/yo`, o `None` si el registro no ocurrió.
3. `token_recuperacion(instancia, email, desde) -> str | None`: busca en `objetivo.logs(...)["api"]` el último «Email (modo dev) a <email>» posterior a `desde` y extrae el token del texto, según la plantilla de recuperación de predicts (`api/src/predicts/correo/`); lee la plantilla real para el patrón.
4. Una herramienta para el agente, `pedir_token_recuperacion()`, registrada desde aquí con una función `herramientas_extra(instancia, persona)`, que el agente usa solo en el escenario `recuperar-contrasena`. **No** edites `agente/navegador.py`: expón la función y documenta en el docstring cómo se engancha. F2.4.T1 la conecta.

Done when: estos tests pasan en `tests/test_predicts_cuentas.py`, con `respx` y logs de ejemplo:
- extrae el token de un log real copiado de la plantilla;
- devuelve `None` si el email no aparece o es anterior a `desde`;
- `confirmar_registro` devuelve el id de empresa con un login 200 y `None` con un 401;
- `credenciales` es estable.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Parsing y HTTP acotados.
- **Dependencies**: F1.1.T1
- **Files**:
  - `src/dogfood/objetivos/predicts/cuentas.py`
  - `tests/test_predicts_cuentas.py`

## F2.4 — Package: concurrencia

### F2.4.T1 — Población real, concurrencia, carriles y memoria

Modifica `src/dogfood/corrida.py` (FR-11, NFR-2, NFR-5, decisión D9):
1. Reemplaza `persona_por_defecto` por `personas.generar(n, semilla, idiomas)` y elimina la función vieja.
2. Ejecuta con `asyncio.Semaphore(concurrencia)`; por defecto toma la de `dogfood.yaml` (5).
3. Las asignaciones con escenario `carril: login_fallido` corren **al final y de a una**. Un 429 de `/auth/login` en esas ejecuciones se marca como esperado en la `Ejecucion` (campo `notas`) y no se cuenta como fallo técnico.
4. Antes de lanzar cada ejecución, lee la memoria libre del host (`/proc/meminfo`, `MemAvailable`). Si está bajo `memoria_libre_min_gb`, espera; si sigue así 5 minutos, aborta la corrida con estado `error` y motivo `memoria`.
5. Después de cada ejecución, llama a `cuentas.confirmar_registro` y guarda el `empresa_id` en la ejecución.
6. Engancha `cuentas.herramientas_extra` en el agente para `recuperar-contrasena`. Si `agente.ejecutar` necesita un parámetro `herramientas_extra`, agrégalo en `agente/navegador.py` como **único cambio** en ese archivo.
7. Para evitar recompilar 100 veces, genera los datasets **una vez por perfil y combinación de defectos**, y comparte cada uno entre las personas que lo usan.

Done when: estos tests pasan en `tests/test_corrida_concurrencia.py`, con fakes:
- con concurrencia 3 nunca hay más de 3 ejecuciones a la vez;
- las ejecuciones `login_fallido` empiezan después de que terminan todas las normales y nunca se solapan;
- con `MemAvailable` falso bajo el umbral durante más tiempo que el límite (con tiempo inyectado), la corrida termina en `error` con motivo `memoria`;
- 120 personas producen 120 ejecuciones con emails distintos;
- dos personas con el mismo perfil comparten un dataset.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Concurrencia con reglas de orden; standard con tests guiados alcanza.
- **Dependencies**: F1.9.T1, F2.2.T1, F2.3.T1
- **Files**:
  - `src/dogfood/corrida.py`
  - `src/dogfood/agente/navegador.py`
  - `tests/test_corrida_concurrencia.py`
