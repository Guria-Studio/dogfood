---
type: spec
project_id: dogfood
phase: 0
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-24
title: Base y contratos
---

# F0 — Base y contratos

Dependencias, modelos de dominio, almacén, configuración, LLM por rol, CLI y registros. Todo lo que las fases siguientes usan sin volver a tocar. Arquitectura: `docs/arch/001-usuarios-agenticos.md`.

## F0.1 — Package: núcleo

### F0.1.T1 — Dependencias, layout y CI

Deja el proyecto listo para que ninguna tarea posterior tenga que tocar `pyproject.toml` ni `uv.lock`. Varias tareas agregando dependencias en paralelo chocan en el lockfile, así que aquí se agregan **todas** las del MVP de una vez.

Dependencias de ejecución (con `uv add`): `pydantic>=2`, `typer`, `pyyaml`, `httpx`, `browser-use` (la misma línea 0.13 que está instalada como herramienta en el server), `playwright`, `jinja2`, `numpy`, `python-dotenv`. Dependencias de desarrollo: `pytest`, `pytest-asyncio`, `ruff` y `respx`.

En `pyproject.toml`:
- el script de consola `dogfood = "dogfood.cli:main"`;
- en `[tool.pytest.ini_options]`, el marcador `integracion` («necesita docker, predicts y credenciales reales»), `addopts = "-m 'not integracion'"` y `asyncio_mode = "auto"`;
- en `[tool.ruff]`, `line-length = 100` y `target-version = "py313"`.

Crea `dogfood.example.yaml`, la configuración de ejemplo descrita en la sección *Componentes → Núcleo* de la arquitectura:
- `roles`: `persona`, `juez`, `dedupe`, `redactor`, cada uno con una lista de modelos de 9router. Usa ids reales, por ejemplo `ag/gemini-3.8-flash` para `persona` y `ag/claude-sonnet-5-5-medium` para `juez` y `redactor`;
- `precios_usd_por_millon` por modelo;
- `concurrencia: 5`, `tope_usd: null`, `umbral_publicar: media`;
- `repo_issues: hectorcanaimero/predicts`;
- `tolerancias` del oráculo, con los valores de la decisión D4;
- `memoria_libre_min_gb: 2`.

Agrega `runs/` y `dogfood.yaml` a `.gitignore` (lo local no se commitea). En `.github/workflows/orch-ci.yml` mantén `runs-on: ${{ vars.RUNNER || 'ubuntu-latest' }}` y los pasos de ruff y pytest que ya existen. No crees código de dominio aquí.

Done when: `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .` y `uv run pytest` pasan, y `tests/test_layout.py` comprueba:
- que `import browser_use, playwright, typer, jinja2, numpy` funciona;
- que `dogfood.example.yaml` se parsea y tiene los cuatro roles;
- que el marcador `integracion` está registrado.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 2h
- **Reason**: Setup mecánico, pero hay que elegir versiones compatibles y no se puede equivocar.
- **Dependencies**:
- **Files**:
  - `pyproject.toml`
  - `uv.lock`
  - `.gitignore`
  - `.github/workflows/orch-ci.yml`
  - `dogfood.example.yaml`
  - `tests/test_layout.py`

### F0.1.T2 — Modelos de dominio

Implementa `src/dogfood/dominio.py` exactamente como lo fija la arquitectura (secciones *Componentes → Núcleo*, *Modelo de datos* e *Interfaces*). Son modelos Pydantic v2, sin lógica de negocio. Este archivo es el contrato que usan todas las fases; piensa los nombres y los tipos con cuidado, porque después no se cambian.

Modelos y enums:
- `Idioma` (`pt-BR`, `es`), `Intencion` (`analisis_completo`, `explorar`, `solo_exportar`, `confundirse`, `romper`), `Gravedad` (`critica`, `alta`, `media`, `baja`, ordenable) y `TipoHallazgo` (`tecnico`, `logica`, `aislamiento`, `regla`, `friccion`);
- `Persona`: id, nombre, email, contrasena, empresa, rubro, idioma, destreza (1–5), paciencia (1–5), intencion, estilo (lista de rasgos) y semilla;
- `Escenario`: los campos del YAML de *Interfaces → Escenario YAML*, con `carril` en `normal` o `login_fallido`;
- `DatasetSintetico`: id, perfil, ruta_csv, ruta_verdad, defectos, n_clientes, n_filas y semilla;
- `Paso`: n, url, pantalla, accion, captura, texto_visible (el texto del DOM recortado a 4.000 caracteres) y ts;
- `EventoRed`: metodo, url, estado y ms;
- `EventoConsola`: nivel, texto, url;
- `Friccion`: texto, severidad, pantalla, captura y cita;
- `Ejecucion`: id, persona_id, escenario_id, dataset_id (opcional), modelo, estado (`ok`, `fallo`, `rendido`, `error`), pasos, red, consola, fricciones, descargas, exito, motivo_juez, duracion_s, ruta_historial, empresa_id (opcional, lo llena la corrida) y notas (lista de textos, por ejemplo «429 esperado»);
- `Evidencia`: tipo (`captura`, `log`, `red`, `csv`, `texto`), ruta y extracto;
- `Hallazgo`: los campos de *Interfaces → Hallazgo*, más `solo_reporte: bool = False` (va al reporte de opinión, pero no se publica como issue) y `ocurrencias: int = 1`, con un método `calcular_huella(firma: str) -> str` (sha1 de `tipo|pantalla|firma`);
- `UsoLlm`: rol, modelo, tokens_in, tokens_out, costo_usd y ejecucion_id;
- `Corrida`: id, objetivo, ref, commit, semilla, inicio, fin, estado y parametros;
- `Instancia`: base_url, api_url, proyecto_compose, commit y parametros;
- `ContextoDeteccion`: un dataclass con los campos de *Interfaces*; `cliente_api` es un `Callable`.

Done when: estos tests pasan en `tests/test_dominio.py`:
- una `Persona` con destreza 6 se rechaza;
- `Gravedad.alta > Gravedad.media`;
- un `Escenario` cargado desde el YAML de ejemplo de la arquitectura valida;
- `Hallazgo.calcular_huella` es estable: misma entrada, misma huella; distinto tipo, distinta huella;
- todos los modelos van y vuelven por JSON sin pérdida.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 3h
- **Reason**: Contrato central del que dependen todas las tareas; un error aquí se propaga.
- **Dependencies**: F0.1.T1
- **Files**:
  - `src/dogfood/dominio.py`
  - `tests/test_dominio.py`

### F0.1.T3 — Almacén de corridas

Implementa `src/dogfood/almacen.py` según *Modelo de datos* de la arquitectura:
- la carpeta por corrida `runs/<corrida_id>/`, con su estructura completa de subcarpetas y los helpers para rutas;
- el índice SQLite `runs/dogfood.db`, con **todas** las tablas del MVP (`corridas`, `personas`, `ejecuciones`, `hallazgos`, `uso_llm`), creado en una sola migración, versionado con `PRAGMA user_version = 1`.

API sugerida: `Almacen(raiz: Path)` con `nueva_corrida(corrida)`, `guardar_personas`, `guardar_ejecucion`, `guardar_hallazgos`, `registrar_uso(UsoLlm, corrida_id)`, `cerrar_corrida(id, estado, costo)`, `listar_corridas() -> list[ResumenCorrida]` (con costo total y n_hallazgos) y `hallazgo(id)` / `ejecucion(id)` para el replay. Las fases siguientes **no** cambian el esquema.

Done when: estos tests pasan en `tests/test_almacen.py`, usando `tmp_path`:
- crear una corrida crea la carpeta con sus subcarpetas y una fila;
- guardar dos ejecuciones y tres hallazgos se refleja en `listar_corridas` con n_hallazgos=3;
- `registrar_uso` suma el costo en el resumen;
- abrir un almacén existente no recrea las tablas ni pierde datos;
- `user_version` es 1.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Persistencia simple pero central; standard alcanza.
- **Dependencies**: F0.1.T2
- **Files**:
  - `src/dogfood/almacen.py`
  - `tests/test_almacen.py`

### F0.1.T4 — Configuración y LLM por rol

Implementa `src/dogfood/config.py` y `src/dogfood/llm.py` (arquitectura: *Componentes → Núcleo* e *Interfaces → Secretos*).

`config.py`:
- carga `dogfood.yaml`; si no existe, usa `dogfood.example.yaml` y avisa;
- carga los `.env` de `~/.config/dogfood/` (la ruta se puede cambiar con `DOGFOOD_CONFIG_DIR`, para los tests);
- expone un objeto `Config` tipado;
- `Config.secreto(nombre)` falla con un mensaje que nombra el archivo y la variable que faltan, **sin imprimir nunca un valor**;
- `repr(Config)` y los logs muestran los secretos como `***`.

`llm.py`:
- `cliente_para(rol: str, indice: int = 0)` devuelve un chat model de browser-use (`browser_use.llm.ChatOpenAI` con `base_url` de 9router) para el rol `persona`, y un cliente para `juez`, `dedupe` y `redactor`;
- un `ContadorUso` que, a partir de la respuesta (usage), crea `UsoLlm` con el costo de la tabla de precios. Un modelo sin precio registra costo 0 y avisa una sola vez;
- `completar_json(rol, prompt, esquema: type[BaseModel])` para el juez y el redactor, con salida estructurada `json_schema` (gotcha de 9router: no usar `tool_choice` forzado; ver `/mnt/storage/project/agndaZAP/docs/notas/2026-09-23-9router-gotchas.md`).

Done when: estos tests pasan en `tests/test_config_llm.py`, con `respx` en lugar de la red:
- un secreto faltante da un error que nombra el archivo, sin valores;
- `repr` no contiene la API key;
- `cliente_para("persona")` usa el primer modelo del rol;
- `ContadorUso` calcula el costo con la tabla;
- `completar_json` envía `response_format` con `json_schema` y parsea la respuesta.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Integración conocida (OpenAI compatible) con un cuidado puntual con los secretos.
- **Dependencies**: F0.1.T2
- **Files**:
  - `src/dogfood/config.py`
  - `src/dogfood/llm.py`
  - `tests/test_config_llm.py`

### F0.1.T5 — CLI y registros

Crea los registros de *Interfaces → Registros* de la arquitectura, para que las tareas paralelas no editen archivos centrales.

1. `src/dogfood/cli.py`: una app Typer con `main()`, que monta `comandos.env`, `comandos.datos`, `comandos.personas`, `comandos.run`, `comandos.runs` y `comandos.replay`. Cada comando es un archivo `src/dogfood/comandos/<x>.py` que expone `app: typer.Typer`. Créalos todos como **stubs** que imprimen «no implementado todavía» y salen con código 2, con los argumentos de *Interfaces → CLI* ya declarados.
2. `src/dogfood/objetivos/base.py`: el protocolo `Objetivo` exactamente como en la arquitectura. `src/dogfood/objetivos/__init__.py`: `OBJETIVOS = {"predicts": "dogfood.objetivos.predicts:PredictsObjetivo"}` y `cargar_objetivo(nombre)`, que importa perezosamente y da un error claro si el objetivo no existe. **No** crees `objetivos/predicts/`, que es de F1.1.T1.
3. `src/dogfood/deteccion/__init__.py`: `DETECTORES` y `ejecutar_detectores(ctx) -> list[Hallazgo]`. Si un detector lanza una excepción, la convierte en un hallazgo `tecnico` de gravedad `baja` con el título «detector X falló» y sigue con los demás. Crea `deteccion/tecnicos.py`, `deteccion/friccion.py` y `deteccion/objetivo.py` como stubs con `def detectar(ctx) -> list[Hallazgo]: return []`.
4. Borra la función `main` de `src/dogfood/__init__.py` (queda solo `__version__`) y actualiza `tests/test_smoke.py` si hace falta.

Done when: estos tests pasan en `tests/test_cli_registros.py`:
- `dogfood --help` lista los seis comandos;
- `dogfood run --help` muestra `--seed` y `--concurrencia`;
- `cargar_objetivo("x")` da un error que lista los objetivos válidos;
- `ejecutar_detectores` con un detector que lanza una excepción devuelve un hallazgo de baja gravedad y los hallazgos de los demás.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 2h
- **Reason**: Andamiaje con contratos claros.
- **Dependencies**: F0.1.T2
- **Files**:
  - `src/dogfood/__init__.py`
  - `src/dogfood/cli.py`
  - `src/dogfood/comandos/__init__.py`
  - `src/dogfood/comandos/env.py`
  - `src/dogfood/comandos/datos.py`
  - `src/dogfood/comandos/personas.py`
  - `src/dogfood/comandos/run.py`
  - `src/dogfood/comandos/runs.py`
  - `src/dogfood/comandos/replay.py`
  - `src/dogfood/objetivos/__init__.py`
  - `src/dogfood/objetivos/base.py`
  - `src/dogfood/deteccion/__init__.py`
  - `src/dogfood/deteccion/tecnicos.py`
  - `src/dogfood/deteccion/friccion.py`
  - `src/dogfood/deteccion/objetivo.py`
  - `tests/test_cli_registros.py`
  - `tests/test_smoke.py`

## F0.2 — Package: ops

### F0.2.T1 — Prerrequisitos del operador

Escribe `docs/ops/prerequisitos.md` (en español) con todo lo que Héctor tiene que tener en el server antes de una corrida real:
- `~/.config/dogfood/router.env` (`ROUTER_BASE_URL`, `ROUTER_API_KEY`);
- `~/.config/dogfood/predicts.env` (`ROUTER_*`, `ROUTER_MODEL`, `TYPESAFE_API_KEY`, `TYPESAFE_MODEL`), que se puede copiar de `/mnt/storage/project/predicts/deploy/.env`;
- `~/.config/dogfood/slack.env` (`SLACK_WEBHOOK_URL`, y cómo crear un incoming webhook);
- `gh auth status` con permiso para crear issues en `hectorcanaimero/predicts`;
- docker con compose v2;
- los Chromium de Playwright (`uv run playwright install chromium`);
- `dogfood.yaml` copiado desde `dogfood.example.yaml`;
- puertos libres: 18080, 18100 y 54330.

Para cada punto, qué fase lo necesita y cómo verificarlo con un comando. No pongas valores de secretos. Sin tests: es documentación.

Done when: el archivo existe, cubre cada punto de arriba con su comando de verificación, y `uv run pytest` sigue pasando.

- **Model**: claude/claude-haiku-5-5
- **Estimate**: 1h
- **Reason**: Documentación mecánica.
- **Dependencies**:
- **Files**:
  - `docs/ops/prerequisitos.md`
