---
type: arch
project_id: dogfood
version: 0.1
depends_on:
  - docs/prd/001-usuarios-agenticos.md
generated_by: orch-arch
generated_at: 2026-10-24
title: Usuarios agénticos para predicts — arquitectura
---

# Usuarios agénticos para predicts — arquitectura

## Contexto

dogfood es hoy un esqueleto: paquete Python `dogfood` (uv, Python 3.13), un test, ruff, CI en el runner self-hosted `guria-dogfood` y `orch init`. Todo lo de abajo es trabajo nuevo.

El primer objetivo es **predicts** (`/mnt/storage/project/predicts`). Lo que importa de su código para este diseño:

- **Despliegue:** `deploy/docker-compose.yml` (proyecto `predicts`) levanta `postgres`, `migrar`, `api`, `worker` y `web`, con límites de memoria. `web` sirve el panel y hace de proxy de `/api/*`. La configuración va por variables (`ROUTER_*`, `TYPESAFE_*`, `MIN_COMPRAS=3`, `HORIZONTE_DIAS=7`, `VENTANA_VALIDACION_SEMANAS=4`, `CONFIANZA_MAPEO=0.8`, `CONFIANZA_JEV=0.7`, `MAX_CSV_MB=500`, `CORS_ORIGENES`). La instancia de desarrollo de Héctor usa `WEB_PORT=8080` y `API_PORT=8100`.
- **Auth:** `POST /auth/registro` crea empresa y dueño y deja la cookie de sesión. El límite de `/auth/login` y `/auth/recuperar` cuenta **solo intentos fallidos**: 5 por email o 20 por IP en 15 minutos. Sin SMTP, `correo.enviar` escribe el email completo, token incluido, en el log de `api`.
- **Modelo de recompra** (`docs/arch/001-predicts.md`, «Modelo de recompra»):
  - el ciclo del par es la mediana de los intervalos, contraída hacia la del producto con `k=2`;
  - el intervalo sigue una log-normal;
  - con menos de `MIN_COMPRAS` no se predice;
  - la fecha probable es la mediana condicional, con rango p25–p75;
  - el backtest se corta en `fecha_max − 4 semanas`;
  - las métricas son precision@k, cobertura@k, Brier, calibración y MAE en días, siempre comparadas con una línea base.
- **API:** la fuente de verdad es el OpenAPI generado (`/openapi.json`). Las rutas que usa dogfood son `/auth/*`, `/proyectos`, `/proyectos/{id}/datasets`, `/datasets/{id}/mapeo|ingesta|calidad|analisis`, `/analisis/{id}`, `/analisis/{id}/resultados?tipo=`, `/analisis/{id}/exportar?tipo=`, `/agente/preguntas`, `/demo` y `/trabajos/{id}/eventos` (SSE).
- La interfaz está en pt-BR, es y en.

**Qué se reutiliza:**
- `browser-use` (ya instalado como herramienta en el server) y los Chromium de Playwright que ya están en `~/.cache/ms-playwright`.
- 9router (`https://routers.usebot.chat/v1`), con 219 modelos disponibles.
- `gh`, ya autenticado.

**Qué NO se copia:**
- El Chrome CDP compartido de `:9222`: es un solo perfil y las sesiones se cruzarían.
- La instancia de predicts en `:8080`.

## Componentes

Todo vive en `src/dogfood/`.

### Núcleo (`dominio.py`, `config.py`, `llm.py`, `almacen.py`)
- **`dominio.py`:** modelos Pydantic compartidos por todo el sistema: `Persona`, `Escenario`, `Corrida`, `Ejecucion`, `Paso`, `Hallazgo`, `Evidencia`, `Friccion`, `UsoLlm` y `DatasetSintetico`. Es el contrato central y no tiene lógica.
- **`config.py`:** lee `dogfood.yaml` (roles → modelos, concurrencia, topes, umbral de gravedad, repo de issues, canal de Slack) y los secretos de `~/.config/dogfood/*.env`. Nunca imprime un secreto.
- **`llm.py`:** fábrica de clientes por rol (`persona`, `juez`, `dedupe`, `redactor`) contra 9router. Registra tokens y costo de cada llamada en `UsoLlm` mediante una tabla de precios de `dogfood.yaml`.
- **`almacen.py`:** carpeta por corrida más un índice SQLite (`runs/dogfood.db`). El esquema completo se crea en F0.

### Objetivos (`objetivos/`)
- **`objetivos/base.py`:** el protocolo `Objetivo` (ver *Interfaces*). **`objetivos/__init__.py`** es el registro `{"predicts": PredictsObjetivo}`.
- **`objetivos/predicts/`:** todo lo propio de predicts.
  - `entorno.py`: instancia aislada.
  - `cliente.py`: cliente HTTP de la API, para verificar sin pasar por el navegador.
  - `cuentas.py`: credenciales por persona y token de recuperación sacado de los logs.
  - `oraculo.py`: números contra la verdad.
  - `aislamiento.py`: auditoría entre empresas.
  - `reglas.py`: reglas propias de predicts.
  - `escenarios/*.yaml`: los escenarios.
  - `pantallas.py`: nombres de pantalla por ruta, usados para agrupar hallazgos y opinión.

### Datos sintéticos (`datos/`)
- **`generador.py`:** a partir de un perfil de rubro y una semilla, simula clientes y productos con ciclos verdaderos, ruido log-normal, abandono a partir de cierta fecha, productos durables y clientes con menos de `MIN_COMPRAS`. Escribe `ventas.csv` (limpio) y `verdad.json`.
- **`perfiles.py`:** rubros (farmacia, pet shop, cosmética, café, e-commerce, agencia) con catálogos, rangos de ciclo y precios.
- **`defectos.py`:** transforma un CSV limpio en uno «de mundo real» con defectos combinables. Nunca toca `verdad.json`, salvo para anotar qué defectos se aplicaron.

### Personas (`personas/`)
- **`generador.py`:** personas **deterministas** a partir de la semilla, sin LLM, para que sean reproducibles (NFR-7). Cubre nombre, email único `@dogfood.test`, empresa, rubro, idioma, destreza, paciencia, intención y estilo.

### Escenarios (`escenarios.py`)
- Carga y valida los YAML de un objetivo y empareja personas con escenarios según `persona_compatible`.

### Agente (`agente/`)
- **`navegador.py`:** una `Ejecucion` (persona × escenario) en un Chromium headless **propio**, lanzado con Playwright. Usa el `Agent` de browser-use con el LLM del rol `persona` y un prompt de sistema armado desde la persona (`prompts.py`). Además:
  - tiene herramientas propias: `anotar_friccion(texto, severidad)` y `rendirse(motivo)`;
  - captura la consola, la red (4xx/5xx con método, URL y estado), una captura por paso y las descargas;
  - guarda el historial de browser-use para el replay;
  - al final, el rol `juez` decide si se cumplió el `criterio_exito` con la evidencia observable.
- **`replay.py`:** vuelve a ejecutar el historial guardado de una ejecución sin LLM (`Agent.rerun_history`) y dice si el hallazgo se reproduce.

### Corrida (`corrida.py`)
- Orquesta el flujo: entorno → datos → personas → asignación → ejecuciones en paralelo (semáforo `concurrencia`) → detectores → reporte → aviso.
- **Carriles:** los escenarios marcados `carril: login_fallido` corren al final y de a uno, porque 20 fallos desde la misma IP bloquean el login de todos durante 15 minutos.

### Detección (`deteccion/`)
- **`deteccion/__init__.py`:** registro de detectores. Cada detector es una función `detectar(ctx: ContextoDeteccion) -> list[Hallazgo]`, y F0 crea todos los módulos como stubs que devuelven `[]`.
  - `tecnicos.py`: consola, red, logs de `api` y `worker` y timeouts de trabajos.
  - `friccion.py`: notas de fricción a hallazgos de UX y a entradas de opinión.
  - `objetivo.py`: delega en `objetivo.verificadores()`, es decir, el oráculo, el aislamiento y las reglas de predicts.

### Reporte (`reporte/`)
- **`redactar.py`:** quita secretos, cookies, tokens y emails reales de cualquier texto o imagen de evidencia antes de que salga de la máquina.
- **`issues.py`:** huella del hallazgo, deduplicación y publicación con `gh` (crear, o comentar una nueva ocurrencia).
- **`opinion.py`:** reporte de opinión en Markdown y HTML (Jinja2), redactado en español por el rol `redactor` a partir de fricciones y resultados agregados.
- **`slack.py`:** resumen por incoming webhook.
- **`modelos.py`**, **`consistencia.py`:** secciones de F5.

### CLI (`cli.py` + `comandos/`)
- **`cli.py`** (Typer) monta los comandos de `comandos/*.py`; cada comando vive en su propio archivo, creado como stub en F0: `env`, `datos`, `personas`, `run`, `runs` y `replay`.

## Modelo de datos

**Carpeta por corrida:** `runs/<corrida_id>/` (gitignored).
- `corrida.json`
- `personas.json`
- `datos/<dataset_id>/{ventas.csv, verdad.json}`
- `ejecuciones/<ejecucion_id>/{historial.json, pasos.jsonl, red.jsonl, consola.jsonl, capturas/*.png, descargas/*}`
- `logs/{api,worker}.log`
- `hallazgos.json`
- `reporte.md`, `reporte.html`

**Índice SQLite:** `runs/dogfood.db`, con el esquema completo creado en F0 y migraciones con `PRAGMA user_version`. Tablas:
- `corridas`: id, objetivo, ref, commit, semilla, inicio, fin, estado, costo_usd, n_personas.
- `personas`: id, corrida_id, json.
- `ejecuciones`: id, corrida_id, persona_id, escenario_id, modelo, estado (`ok`, `fallo`, `rendido`, `error`), pasos, duracion_s, exito, motivo_juez.
- `hallazgos`: id, corrida_id, ejecucion_id, tipo (`tecnico`, `logica`, `aislamiento`, `regla`, `friccion`), gravedad, pantalla, titulo, huella, issue_url, nuevo.
- `uso_llm`: corrida_id, ejecucion_id, rol, modelo, tokens_in, tokens_out, costo_usd.

**`verdad.json`:**
- `semilla`, `perfil`, `fecha_max`, `parametros` (`MIN_COMPRAS`, horizonte y ventana usados para comparar), `defectos` aplicados;
- `clientes[]`, cada uno con `cliente_id`, `abandono_desde` (fecha o null) y `pares[]`;
- cada par trae `producto_id`, `sku`, `ciclo_real_dias`, `sigma_log`, `n_compras`, `ultima_compra` y `durable`.

## Interfaces

### Registros (para que los paquetes paralelos no se pisen)
- **CLI:** `cli.py` importa `comandos.env|datos|personas|run|runs|replay` y cada uno expone `app: typer.Typer`. Una tarea solo edita su propio archivo de comando.
- **Detectores:** `deteccion/__init__.py` define `DETECTORES = [tecnicos.detectar, friccion.detectar, objetivo.detectar]` desde F0. Cada tarea solo edita su propio módulo.
- **Objetivos:** `objetivos/__init__.py` tiene `OBJETIVOS = {"predicts": "dogfood.objetivos.predicts:PredictsObjetivo"}`. F1.1 crea `objetivos/predicts/` con todos sus módulos como stubs; las tareas posteriores rellenan cada uno.

### Protocolo `Objetivo` (`objetivos/base.py`)
```python
class Objetivo(Protocol):
    nombre: str
    def preparar(self, ref: str, corrida: Corrida) -> Instancia      # levanta y espera salud
    def destruir(self, instancia: Instancia) -> None
    def url_permitida(self, url: str, instancia: Instancia) -> bool
    def escenarios(self) -> list[Escenario]
    def pantalla(self, url: str) -> str                               # "mapeo", "calidad", …
    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]
    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]   # servicio → texto
```
`Instancia` trae: `base_url`, `api_url`, `proyecto_compose`, `commit` y `parametros` (las variables efectivas: `MIN_COMPRAS`, `HORIZONTE_DIAS`, etc.).

### Escenario YAML (`objetivos/<x>/escenarios/*.yaml`)
```yaml
id: recompra-completa
titulo: Análisis de recompra completo
superficies: [registro, subir, mapeo, calidad, analisis, resultados, exportar]
persona_compatible: {intencion: [analisis_completo, explorar], destreza_min: 1}
datos: {perfil: farmacia, clientes: 300, defectos: []}
objetivo: >
  Crea una cuenta, sube el CSV de ventas, confirma el mapeo, corre un análisis de
  recompra y descarga el CSV de recordatorios.
criterio_exito: Se descargó un CSV de recordatorios con al menos una fila.
max_pasos: 60
carril: normal            # normal | login_fallido
```

### `ContextoDeteccion`
`corrida`, `instancia`, `ejecuciones: list[Ejecucion]`, `datasets: dict[str, DatasetSintetico]` (con la ruta a `verdad.json`), `cliente_api(persona) -> PredictsCliente` y `logs: dict[str, str]`.

### `Hallazgo` (en `dominio.py`)
- `tipo`, `gravedad` (`critica`, `alta`, `media`, `baja`), `pantalla`, `titulo`, `descripcion`;
- `pasos: list[str]`, `evidencia: list[Evidencia]`;
- `esperado`, `obtenido` (opcionales);
- `huella`: sha1 de `tipo | pantalla | firma`, donde la firma la normaliza cada detector: método más ruta con los ids reemplazados por `{id}` y el código de estado; el mensaje de error sin números; o la regla y el campo;
- `ejecucion_id`, `semilla`, `commit`.

### Issue publicado
- **Título:** `[dogfood][<gravedad>] <pantalla>: <titulo>`.
- **Etiquetas:** `dogfood`, `dogfood:<tipo>`, `gravedad:<gravedad>`.
- **Cuerpo:** pasos, esperado/obtenido, evidencia (capturas como enlaces a un release de assets del repo dogfood, o incrustadas en texto si son logs), comando de replay y un comentario oculto `<!-- dogfood:huella=<sha1> -->`.
- **Deduplicación:** `gh issue list -R <repo> --label dogfood --state open --search "dogfood:huella=<sha1> in:body"`. Si hay coincidencia, se comenta la nueva ocurrencia.

### CLI
```
dogfood env up|down --target predicts [--ref main]
dogfood datos --perfil farmacia --clientes 2000 [--defectos sep_punto_coma,latin1] [--seed S] [--salida DIR]
dogfood personas --n 120 [--seed S] [--idiomas pt-BR:0.5,es:0.5]
dogfood run --target predicts [--personas N] [--escenarios a,b] [--seed S] [--ref main]
            [--concurrencia 5] [--repeat 1] [--sin-publicar] [--tope-usd X]
dogfood runs
dogfood replay <hallazgo_id|ejecucion_id>
```

### Secretos (`~/.config/dogfood/`)
- `router.env`: `ROUTER_BASE_URL`, `ROUTER_API_KEY`.
- `predicts.env`: lo que necesita la instancia (`ROUTER_*`, `TYPESAFE_*`).
- `slack.env`: `SLACK_WEBHOOK_URL`.
- `gh` usa su propio login.

## Decisiones

- **D1 — Motor del agente.** Elegido: la librería `browser-use`, con LLM por 9router. Trae visión, acciones y un historial que se puede repetir. Descartados: un bucle propio sobre Playwright, porque es mucho trabajo para lo mismo; y el `browser_exec` de Hermes, que es un solo Chrome compartido.
- **D2 — Un Chromium por ejecución.** Elegido: Chromium headless de Playwright, con un contexto limpio por persona. Descartado: el Chrome CDP de `:9222`, que es un solo perfil y mezclaría sesiones.
- **D3 — Instancia propia de predicts.** Elegido: `git worktree` de predicts en el `--ref` pedido, bajo `~/.cache/dogfood/predicts/<ref>`, más `docker compose -p dogfood-predicts` con un override de puertos (web 18080, api 18100, postgres 54330), `CORS_ORIGENES` acorde y volúmenes propios; `down -v` borra todo. Descartado: usar la instancia de `:8080`, porque 100 cuentas la ensuciarían y las corridas no partirían limpias.
- **D4 — El oráculo compara con tolerancias, no por igualdad.** El modelo de predicts contrae los ciclos hacia la mediana del producto, así que el ciclo predicho no es el verdadero. Hay dos tipos de chequeo:
  - **exactos:** historia insuficiente sin fecha, exportación igual al panel y un rango con `fecha_min ≤ fecha_probable ≤ fecha_max`;
  - **estadísticos:** por ejemplo, que al menos el 80 % de los pares con 6 compras o más tengan `|ciclo − ciclo_real| ≤ 25 %`; que el MAE en días recalculado por dogfood con su verdad esté a ±1 día del declarado; y que el modelo no sea peor que la línea base en precision@k sobre datos con ciclos limpios.
  Las tolerancias están en `dogfood.yaml`. Descartado: reimplementar el modelo de predicts, porque se probaría a sí mismo.
- **D5 — Personas deterministas.** Se generan por semilla sin LLM; el LLM solo actúa. Descartado: personas inventadas por LLM, que rompen NFR-7.
- **D6 — Deduplicación por huella, no por LLM.** Es determinista y explicable. El LLM (`dedupe`) solo se usa para fusionar fricciones parecidas en el reporte de opinión, nunca para issues.
- **D7 — Registro por la UI, verificación por la API.** El agente se registra en el navegador, que es lo que se prueba (FR-9). dogfood guarda las credenciales y, para los detectores, inicia sesión por API con `cliente.py`.
- **D8 — El token de recuperación sale de los logs.** Se lee de `docker compose logs api` («Email (modo dev)»). Descartado: configurar SMTP con un buzón de prueba, que es más infraestructura sin ganar nada en la v1.
- **D9 — Carril de login fallido.** Los escenarios que fallan el login a propósito corren al final y en serie. Un 429 después de los fallos esperados no es un hallazgo. Descartado: cambiar el límite de predicts, porque es parte de lo que se prueba. Se registra **una vez** como observación que 20 fallos por IP bloquean a una oficina detrás de una misma NAT.
- **D10 — Almacén en archivos más SQLite.** Elegido porque no agrega un servicio. Descartado: Postgres.
- **D11 — Slack por incoming webhook.** Descartado: el gateway de Hermes, porque dogfood no debe depender de él.
- **D12 — Costo de la instancia.** El costo propio de dogfood se mide exacto en `uso_llm`. El de predicts (Jev y 9router) se *estima* contando filas de `decisiones_jev` y plantillas generadas en su Postgres, y en el reporte se marca como estimado. Descartado: la API de uso de 9router, que no está documentada.
- **D13 — CI sin docker.** Los tests unitarios usan fakes del `Objetivo` y del LLM. Los de integración llevan la marca `integracion` y se excluyen por defecto (`addopts = -m "not integracion"`). Las tareas que los escriben los corren a mano en el server.

## Riesgos

- **Que browser-use se trabe en pantallas 3D o con SSE** (universo, procesamiento en vivo). *Mitigación:* límite de pasos y timeout por ejecución; la pantalla 3D se marca como «solo mirar» en los escenarios; un timeout es un hallazgo técnico solo si lo confirma el trabajo en la API.
- **Falsos positivos del oráculo**, que llenarían de ruido el repo público. *Mitigación:* tolerancias conservadoras, umbral de gravedad para publicar y `--sin-publicar` en las primeras corridas. Las primeras corridas de M3 se revisan a mano antes de activar la publicación (la publicación entra recién en F4).
- **Memoria del homelab.** *Mitigación:* los límites del compose de predicts, 5 Chromium por defecto, `docker stats` muestreado por la corrida, y abortar si la memoria libre baja de 2 GB.
- **Que cambie la UI de predicts.** El agente es de lenguaje natural, no de selectores, así que tolera cambios. El replay puede romperse: se informa como «no reproducible por cambio de UI» y no como «arreglado».
- **Costo de IA en predicts** (Jev en cada mapeo y mensajes por análisis) con más de 100 personas. *Mitigación:* lo mide D12, y existe `--tope-usd`.

## Cobertura de requisitos

| Requisito | Componente(s) |
| --- | --- |
| FR-1 | objetivos/predicts/entorno.py, comandos/env.py |
| FR-2 | objetivos/predicts/entorno.py |
| FR-3 | objetivos/base.py (`url_permitida`), corrida.py |
| FR-4 | objetivos/predicts/entorno.py, config.py (`predicts.env`) |
| FR-5 | datos/generador.py, datos/perfiles.py, comandos/datos.py |
| FR-6 | datos/defectos.py |
| FR-7 | escenarios.py, objetivos/predicts/escenarios/*.yaml |
| FR-8 | personas/generador.py, comandos/personas.py |
| FR-9 | agente/navegador.py, objetivos/predicts/cuentas.py |
| FR-10 | agente/navegador.py, agente/prompts.py, escenarios |
| FR-11 | corrida.py (semáforo, carriles, memoria) |
| FR-12 | deteccion/tecnicos.py |
| FR-13 | objetivos/predicts/oraculo.py |
| FR-14 | objetivos/predicts/aislamiento.py |
| FR-15 | objetivos/predicts/reglas.py |
| FR-16 | agente/navegador.py (`anotar_friccion`), deteccion/friccion.py |
| FR-17 | dominio.py (`Hallazgo`), agente/replay.py, comandos/replay.py |
| FR-18 | reporte/issues.py (huella) |
| FR-19 | reporte/issues.py |
| FR-20 | reporte/opinion.py |
| FR-21 | reporte/slack.py |
| FR-22 | corrida.py, comandos/run.py |
| FR-23 | almacen.py, comandos/runs.py |
| FR-24 | llm.py, reporte/modelos.py |
| FR-25 | corrida.py (`--repeat`), reporte/consistencia.py |
| NFR-1 | pyproject.toml, llm.py, agente/navegador.py |
| NFR-2 | corrida.py (memoria), entorno.py (límites del compose) |
| NFR-3 | config.py, reporte/redactar.py |
| NFR-4 | datos/, personas/ (todo sintético), reporte/redactar.py |
| NFR-5 | corrida.py, agente/navegador.py (timeouts) |
| NFR-6 | llm.py (`uso_llm`), corrida.py (`--tope-usd`), D12 |
| NFR-7 | datos/generador.py, personas/generador.py (semilla) |
| NFR-8 | reporte/issues.py (dedupe + umbral) |
| NFR-9 | objetivos/base.py, registros |

## Desglose del trabajo

Las fases siguen los milestones del PRD (M1 = F1, …) y van precedidas de F0 con los contratos. orch despacha por dependencias, no por fase. Los archivos compartidos entre fases (`corrida.py`, `comandos/run.py`, `comandos/datos.py`) se encadenan con dependencias explícitas.

### F0 — Base y contratos
- **F0.1 — núcleo**:
  - T1, dependencias, layout y CI: `pyproject.toml`, `uv.lock`, `.github/workflows/orch-ci.yml`, `dogfood.example.yaml`, `.gitignore`.
  - T2, dominio: `src/dogfood/dominio.py`.
  - T3, almacén: `src/dogfood/almacen.py`.
  - T4, config y LLM por rol: `src/dogfood/config.py`, `src/dogfood/llm.py`.
  - T5, CLI y registros: `src/dogfood/cli.py`, `src/dogfood/comandos/*`, `src/dogfood/objetivos/{__init__,base}.py`, `src/dogfood/deteccion/*`.
- **F0.2 — ops**: prerrequisitos del operador en `docs/ops/prerequisitos.md`.

### F1 — Una persona, de punta a punta (M1)
- **F1.1 — entorno predicts**: `src/dogfood/objetivos/predicts/` (paquete con stubs, `entorno.py`, `pantallas.py`), `comandos/env.py`.
- **F1.2 — datos con verdad**: `src/dogfood/datos/{generador,perfiles}.py`, `comandos/datos.py`.
- **F1.3 — escenarios**: `src/dogfood/escenarios.py`, `objetivos/predicts/escenarios/*.yaml`. Depende de F1.1.
- **F1.4 — agente**: `src/dogfood/agente/{navegador,prompts}.py`.
- **F1.5 — corrida**: `src/dogfood/corrida.py`, `comandos/run.py`, `comandos/runs.py`. Depende de F1.1–F1.4.
- **F1.9 — integración M1**: `tests/integracion/test_m1.py`.

### F2 — Población y datos del mundo real (M2)
- **F2.1 — defectos**: `datos/defectos.py`, `comandos/datos.py`. Depende de F1.2.
- **F2.2 — personas**: `personas/`, `comandos/personas.py`.
- **F2.3 — cuentas**: `objetivos/predicts/cuentas.py`. Depende de F1.1.
- **F2.4 — concurrencia**: `corrida.py`. Depende de F1.5 y F2.2.

### F3 — Detección (M3)
- **F3.1 — cliente API**: `objetivos/predicts/cliente.py`.
- **F3.2 — técnicos**: `deteccion/tecnicos.py`.
- **F3.3 — oráculo**: `objetivos/predicts/oraculo.py`.
- **F3.4 — aislamiento**: `objetivos/predicts/aislamiento.py`.
- **F3.5 — reglas**: `objetivos/predicts/reglas.py`.
- **F3.6 — fricción**: `deteccion/friccion.py`, `deteccion/objetivo.py`.

### F4 — Issues y reporte (M4)
- **F4.1 — redacción**: `reporte/redactar.py`.
- **F4.2 — issues**: `reporte/issues.py`.
- **F4.3 — replay**: `agente/replay.py`, `comandos/replay.py`.
- **F4.4 — opinión**: `reporte/opinion.py`, `reporte/plantillas/`.
- **F4.5 — Slack**: `reporte/slack.py`.
- **F4.6 — cierre de corrida**: `corrida.py`. Depende de F2.4, F4.2, F4.4 y F4.5.

### F5 — Modelos y consistencia (M5)
- **F5.1 — modelos por rol**: `llm.py`, `reporte/modelos.py`, `corrida.py`. Depende de F4.6.
- **F5.2 — repetición**: `reporte/consistencia.py`, `corrida.py`, `comandos/run.py`. Depende de F5.1.
