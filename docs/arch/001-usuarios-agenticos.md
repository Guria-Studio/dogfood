---
type: arch
project_id: dogfood
version: 0.3
depends_on:
  - docs/prd/001-usuarios-agenticos.md
generated_by: orch-arch
generated_at: 2026-11-01
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

**v0.3 (PRD v0.4, M8 — Flutter en celular real).** F0–F7 están hechas: hay interfaz `Driver` con driver web y Android (ADB), bucle agéntico, contrato de resultado, vista en vivo y panel. El driver Android nunca se probó con un celular (no hay KVM ni dispositivo conectado). M8 suma: ADB sobre Tailscale con comandos de operación, soporte Flutter (detección, cobertura de Semantics, hallazgo de pantalla «ciega» y respaldo por visión), un motor determinista Patrol / `integration_test`, una interfaz de **fuente de frames** para ver la pantalla real (Android y iPhone) en la vista y en el panel, un **nodo iOS** en el Mac M1 de Héctor al que guria manda trabajos por SSH sobre Tailscale, y un filtro web con la app Flutter compilada a web. Las apps de referencia son `/mnt/storage/rupies/apps/mobile-mao` (`br.com.rupies.profissional`) y `mobile-empresa` (`br.com.rupies.empresa`): Flutter ≥ 3.1, carpeta `web/` presente, casi sin `Semantics` ni `ValueKey` y sin Patrol ni `integration_test`; son **solo lectura** (dogfood trabaja sobre copias). El SDK de Flutter está en `/mnt/storage/flutter` (`PUB_CACHE=/mnt/storage/flutter/.pub-cache`).

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

### Motores (`backends/`, `llm.py`) — v0.2, FR-26, FR-27
- **`backends/base.py`:** el protocolo `BackendLlm` y `UsoBackend` (ver *Interfaces*). Un backend recibe un prompt, un esquema Pydantic y, opcionalmente, rutas de imágenes; devuelve la salida validada, el uso y un id de sesión para continuar.
- **`backends/api.py`:** el `completar_json` de siempre contra 9router (o cualquier endpoint compatible con OpenAI), ahora detrás del protocolo; las imágenes van como `image_url` en base64.
- **`backends/claude_code.py`:** invoca `claude -p --output-format json --json-schema <esquema> --model <m>` como subproceso, con `cwd` en la carpeta de la ejecución (para no cargar el `CLAUDE.md` de dogfood), `--strict-mcp-config` y `--mcp-config` solo si está configurado, solo la herramienta `Read` sobre la carpeta de capturas y `--resume <sesion>` para mantener el contexto entre pasos. Lee `result`/`structured_output`, `usage` y `total_cost_usd` del JSON. El costo cobrado es 0 (plan Max) y `total_cost_usd` queda como costo **equivalente**. Si `claude` no está en el PATH o responde que no hay sesión, lanza `ErrorMotor` con la instrucción de arreglo.
- **`llm.py`:** agrega `backend_para(rol, cfg, indice=0) -> BackendLlm` según `motores.<rol>` de `dogfood.yaml` (por defecto `api`). `cliente_para` (el `ChatOpenAI` de browser-use) y `completar_json` siguen igual para no romper F1–F5.

### Drivers (`drivers/`) — v0.2, FR-28, FR-29
- **`drivers/base.py`:** el protocolo `Driver` y sus modelos `ElementoUI`, `Observacion`, `Accion`, `ResultadoAccion`.
- **`drivers/web.py`:** driver web sobre Playwright (Chromium propio, como D2): observa con captura y el árbol de accesibilidad (`aria_snapshot`/`accessibility`) convertido a `ElementoUI`; actúa por id de elemento o coordenadas; guarda consola, red, video (`record_video_dir`) y *trace* (`ctx.tracing`); `frame()` devuelve el último frame de `Page.startScreencast` (CDP).
- **`drivers/android.py`:** clase `Adb` (envuelve el binario `adb` con un *runner* inyectable para tests) y `DriverAndroid`. Observa con `adb exec-out screencap -p` y `uiautomator dump /sdcard/dogfood.xml` + `exec-out cat` (XML → `ElementoUI` con `resource-id`, `text`, `content-desc`, `class`, `bounds`, `clickable`); actúa con `input tap|text|swipe|keyevent`, `am start -n`/`monkey -p`, `am force-stop`, `install -r`; evidencia: `logcat --pid=<pid del paquete>` (o filtrado por paquete), `screenrecord` en segmentos de 170 s y la captura por paso. `frame()` usa `screencap` escalado a JPEG. Valida el destino antes de conectar (NFR-10).
- **Opción B (Appium + UIAutomator2 o `mobile-mcp`)** queda como spike pendiente de dispositivo real (ver D18).

### Bucle de agente (`agente/bucle.py`, `agente/prompts_bucle.py`) — v0.2
- Una `Ejecucion` con cualquier `Driver` y cualquier `BackendLlm`: `observar → decidir (DecisionPaso en JSON) → actuar → registrar Paso → publicar EventoVivo`, hasta `terminado`, `rendirse` o `max_pasos`. El prompt lleva el árbol en texto; adjunta la captura solo cuando el árbol tiene menos de 3 elementos útiles o el modelo la pidió en el paso anterior, con tope `max_capturas_por_paso` y reducida a `resolucion_max` (Pillow). Al terminar llama al juez (`backend_para("juez")`) y aplica `contrato.resultado`.
- Mientras el bus está activo, una tarea aparte pide `driver.frame()` (5 fps web, 1 fps Android) y lo publica; nunca espera al cliente (NFR-11).
- browser-use (`agente/navegador.py`) sigue siendo el motor web por defecto (`motor: browser_use`); el bucle propio es `motor: bucle` y es el único para Android.

### Contrato y eventos (`contrato.py`, `eventos.py`) — v0.2, FR-30, FR-31
- **`contrato.py`:** `resultado(e: Ejecucion) -> Resultado` (aprobado, fallo, no concluyente), única fuente de verdad del resultado.
- **`eventos.py`:** `EventoVivo` y `BusVivo`, pub/sub en proceso con una cola acotada por suscriptor que descarta frames viejos. `BUS_NULO` no hace nada (corridas sin `--vista`).

### Web local (`web/`, `vista/`, `panel/`) — v0.2, FR-31, FR-32, FR-33
- **`web/`:** base común: `crear_app_base()` (FastAPI + Jinja2, estáticos), `validar_host()` (NFR-10), `plantillas/base.html` y `estatico/dogfood.css` con los tokens del dashboard de orch («Mesa de despacho»: fondo grafito, violeta `#5a43db` para foco y selección, escala de estado done `#1e8a4c`, failed `#d1343a`, blocked `#b86e0b`, running `#2f6bd6`, modo claro y oscuro).
- **`vista/servidor.py`:** app de la vista en vivo: `GET /` (grilla), `GET /ws` (WebSocket con los `EventoVivo` de todas las ejecuciones). `vista.js` dibuja el frame, marca el punto de la acción y llena la columna de razonamiento. Corre dentro del proceso de `dogfood run --vista` (uvicorn en el mismo loop) en `127.0.0.1:7460`.
- **`panel/`:** app del panel (`dogfood panel`, `127.0.0.1:7470`), solo lectura sobre `runs/` salvo «Crear issue». `consultas.py` lee SQLite y las carpetas; `app.py` monta las rutas; `detalle.py` el paso a paso; `issue.py` arma y publica el issue reutilizando `reporte/redactar.py` y `reporte/issues.py` (sin modificarlos).

### Objetivo Android (`objetivos/android/`) — v0.2
- `AndroidObjetivo` cumple el protocolo `Objetivo`: `preparar` verifica el dispositivo (`adb get-state`), instala el `apk` si hay y devuelve una `Instancia` con `base_url = android://<paquete>` y `parametros = {serial, paquete, version_app}` (de `dumpsys package`); `destruir` hace `force-stop` y `pm clear`; `url_permitida` acepta solo `android://<paquete>`; `pantalla` es la actividad; `logs` devuelve el logcat; `verificadores()` es `[]` en la v1. Escenarios en `objetivos/android/escenarios/*.yaml` (login de ejemplo).

### Android por Tailscale (`drivers/adb_red.py`, `comandos/android.py`) — v0.3, FR-34
- **`drivers/adb_red.py`:** operaciones de red de ADB sin estado de driver: `emparejar(host_puerto)` (`adb pair` heredando la terminal: el código lo escribe Héctor en el prompt de `adb`, dogfood no lo lee ni lo guarda), `conectar(host_puerto)` (`adb connect` + `get-state`), `listar()` (`adb devices -l` → `DispositivoAdb` con `permitido` según `validar_destino`) y `servidor_local_ok()` (el servidor `adb` en `:5037` escucha solo en loopback; mira `ss -ltn`). Runner inyectable.
- **`comandos/android.py`:** `dogfood android emparejar|conectar|estado|desconectar`.
- **`drivers/android.py`:** `Adb.ejecutar` reconecta **una vez** si el destino es `host_puerto` y `adb` responde `device offline` / `not found` / `no devices` (Tailscale se cayó), y reintenta el comando; un segundo fallo es `AdbError`. `DriverAndroid` acepta `grabar_video` (por defecto `True`; `False` cuando la fuente de frames `screenrecord` ya graba).

### Flutter (`flutter/semantica.py`, `deteccion/flutter.py`) — v0.3, FR-35
- **`flutter/semantica.py`:** `es_flutter(xml, actividad)` (clases `io.flutter.embedding.android.FlutterView`/`FlutterSurfaceView`/`FlutterTextureView` en el árbol, o `FlutterActivity`/`io.flutter` en la actividad) y la cobertura de Semantics, sobre el XML crudo de `uiautomator` (Android) o de `/source` de XCUITest (iOS), y sobre una lista de `ElementoUI` (web, iOS). Ver *Interfaces* «v0.3 — Flutter».
- **`drivers/android.py`** rellena `Observacion.cobertura` en cada `observar` cuando la app es Flutter.
- **`agente/bucle.py`:** si `obs.cobertura.ciega`, adjunta la captura (dentro de `max_capturas_por_paso`) aunque el árbol tenga elementos, y el prompt dice que la pantalla no expone Semantics y que actúe por coordenadas `x`/`y` sobre la captura.
- **`deteccion/flutter.py`:** detector registrado en `DETECTORES`: recorre los `Paso.arbol` de las ejecuciones Android/iOS, agrupa por pantalla y emite un `Hallazgo` `accesibilidad` por pantalla ciega (gravedad `media`) y uno por pantalla con ids estables insuficientes (`ratio_id < 0.5`, gravedad `baja`, «testabilidad»), con los números y la captura.

### Motor determinista (`deterministico/`) — v0.3, FR-36
- **`deterministico/generador.py`:** de `Escenario.deterministico.pasos` genera un test Dart: Patrol (`patrolTest`, `$(#key).tap()`, `$(#key).enterText(...)`, `$('texto').waitUntilVisible()`) o `integration_test` (`testWidgets`, `find.byKey(ValueKey(...))`, `find.text`). Los valores `{env:NOMBRE}` se leen con `String.fromEnvironment('NOMBRE')` y viajan por `--dart-define`; el archivo nunca lleva un secreto.
- **`deterministico/corredor.py`:** `CorredorFlutter` prepara una **copia de trabajo** de la app (`rsync -a --delete` sin `build/`, `.dart_tool/` ni `.git/` a `flutter.copia_trabajo/<nombre>`), escribe el test generado en `integration_test/dogfood/`, agrega `integration_test` a `dev_dependencies` de la copia si falta (Patrol exige que la app ya esté preparada; si no, el resultado es `no_concluyente` con la instrucción), corre `flutter test … --reporter json` o `patrol test …` con timeout y parsea el resultado. `a_ejecucion` lo convierte en una `Ejecucion` (`motor` = `patrol`/`integration_test`, un `Paso` por test, log y reporte como evidencia, captura final del dispositivo).
- Integración en `corrida.py`: `escenario.motor` o `--motor patrol|integration_test` usan el corredor en lugar del bucle; en iOS el trabajo va al nodo.

### Fuentes de frames (`frames/`) — v0.3, FR-37
- **`frames/base.py`:** el protocolo `FuenteFrames`, `FuenteDeDriver` (envuelve `driver.frame()`, lo de siempre) y `validar_url_local` (NFR-12).
- **`frames/android.py`:** `FuenteScreencap` (`exec-out screencap -p` → JPEG ≤ 720 px, a `pantalla.fps`) y `FuenteScreenrecord` (`adb exec-out screenrecord --output-format=h264 -` → `ffmpeg -f h264 -i - -f image2pipe -c:v mjpeg -q:v 7 -r <fps> -`, cortando los JPEG por sus marcadores SOI/EOI; reinicia cada 170 s; si falta `ffmpeg` o el stream muere, cae a `FuenteScreencap`). Además graba el mismo H.264 en `video/` para que el driver no lance un segundo `screenrecord`.
- **`frames/mjpeg.py`:** `FuenteMjpeg(url)`: lee el `multipart/x-mixed-replace` de WebDriverAgent (puerto 9100) con `httpx` en streaming y guarda el último JPEG; reconecta con espera creciente.
- **`frames/__init__.py`:** `crear_fuente(cfg, driver, parametros) -> FuenteFrames` según `driver.nombre` y `cfg.pantalla`.
- **`agente/bucle.py`:** el emisor de frames usa la `FuenteFrames` que recibe (por defecto `FuenteDeDriver`).
- **`panel/dispositivos.py`:** página «Dispositivos» del panel (`GET /dispositivos`) con los Android visibles por `adb` (solo los permitidos) y los nodos iOS de `cfg.nodos`, cada uno con su pantalla en vivo (`GET /dispositivos/{id}/mjpeg`, un `multipart/x-mixed-replace` armado desde su `FuenteFrames`).

### Nodo iOS (`nodos/`, `drivers/ios.py`, `objetivos/ios/`) — v0.3, FR-38
- **`nodos/protocolo.py`:** `Trabajo`, `ResultadoTrabajo`, `EstadoNodo` (ver *Interfaces*). Un trabajo es un JSON por stdin; el resultado es la **última línea** de stdout en JSON; los logs van a stderr.
- **`nodos/cliente.py`** (corre en guria): `ClienteNodo(nodo_cfg, runner)`: valida el host (loopback o Tailscale), `estado()` (`ssh -o BatchMode=yes -o ConnectTimeout=10 -p <p> usuario@host <comando> estado --json`), `enviar(trabajo, carpeta)` (`ssh … <comando> ejecutar` con el trabajo por stdin; después `rsync -a usuario@host:<dir_trabajo>/<id>/ <carpeta>/`) y `tunel(puertos)` (`ssh -N -L 127.0.0.1:<p>:127.0.0.1:<p>` en segundo plano, para Appium `4723` y el MJPEG `9100`, que en el Mac escuchan solo en loopback).
- **`nodos/runner.py` + `comandos/nodo.py`** (corre en el Mac): `dogfood nodo estado [--json]` (versión de Xcode con `xcodebuild -version`, iPhones con `xcrun xctrace list devices`, Appium en `127.0.0.1:4723/status`, `patrol --version`, `flutter --version`) y `dogfood nodo ejecutar` (lee el `Trabajo`): `patrol` usa `CorredorFlutter` con `--device <udid>` en `dir_trabajo/<id>/`; `sesion_appium` arranca `appium --address 127.0.0.1 --port 4723` si no responde y devuelve las URLs locales; `cerrar_sesion` lo detiene si lo arrancó el nodo.
- **`drivers/ios.py`:** `DriverIos` cumple `Driver` hablando WebDriver/Appium por HTTP (`httpx`, sin cliente de Appium): sesión XCUITest (`appium:udid`, `appium:bundleId`, `appium:mjpegServerPort: 9100`, `appium:noReset`), `observar` con `GET /source` (XML `XCUIElementType*` → `ElementoUI` con `name`/`label`/`value` y `x`/`y`/`width`/`height`) y `GET /screenshot`; `actuar` con acciones W3C de puntero (tocar, deslizar), `element/{id}/value` o teclas W3C (escribir), `mobile: activateApp`/`terminateApp`; «volver» es un deslizamiento desde el borde izquierdo; `evidencia` con `mobile: startRecordingScreen`/`stopRecordingScreen` (mp4) y el `syslog` (`POST /se/log`); cobertura con `flutter/semantica.py`.
- **`objetivos/ios/`:** `IosObjetivo`: `preparar` verifica el nodo, abre el túnel, pide `sesion_appium` y devuelve `Instancia(base_url=ios://<bundle_id>, parametros={nodo, udid, bundle_id, appium_url, mjpeg_url, version_app})`; `destruir` cierra la sesión y el túnel. Escenarios en `objetivos/ios/escenarios/`.

### Filtro web Flutter (`objetivos/flutter_web/`, `drivers/web.py`) — v0.3, FR-39
- **`objetivos/flutter_web/`:** `FlutterWebObjetivo` sirve `flutter_web.build_dir` (o compila `flutter build web --release` en la copia de trabajo de `flutter.proyecto`) con un servidor estático en un hilo, en `flutter_web.host:puerto` (validado con `validar_host`); `url_permitida` acepta su origen y `flutter_web.api_permitidas`; `pantalla` es la ruta del hash (`/#/login` → `login`); `parametros.flutter = True`.
- **`drivers/web.py`:** con `flutter=True`, tras cargar espera `flutter-view`/`flt-glass-pane`, activa los Semantics (clic en `flt-semantics-placeholder`, «Enable accessibility») y vuelve a activarlos si una observación no encuentra `flt-semantics`; `JS_ELEMENTOS` incluye `flt-semantics` con `role` o `aria-label`; cada observación lleva `cobertura`.

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

**Cambios v0.2 (migración a `user_version = 2` con `ALTER TABLE … ADD COLUMN`, una sola tarea: F6.1.T1):**
- `corridas`: `version_app TEXT` (versionName en Android; commit en web).
- `ejecuciones`: `driver TEXT DEFAULT 'web'`, `motor TEXT DEFAULT 'browser_use'`, `backend TEXT DEFAULT 'api'`, `resultado TEXT` (`aprobado`, `fallo`, `no_concluyente`), `tokens_in INTEGER DEFAULT 0`, `tokens_out INTEGER DEFAULT 0`, `capturas INTEGER DEFAULT 0`, `costo_usd REAL DEFAULT 0`, `costo_equivalente_usd REAL DEFAULT 0`, `video TEXT`, `trace TEXT`.
- `uso_llm`: `backend TEXT DEFAULT 'api'`, `costo_equivalente_usd REAL DEFAULT 0`.
- Carpeta de la ejecución: además `arboles/paso-NNN.xml|.json`, `video/*.webm|*.mp4`, `trace.zip` (web), `logcat.txt` (Android).
- `Paso` suma `razonamiento`, `paso_contrato`, `esperado`, `observado`, `arbol` (ruta) y `punto` (x, y de la acción). `Ejecucion` suma `driver`, `motor`, `backend`, `resultado`, `metricas: MetricasEjecucion` (tokens_in, tokens_out, capturas, costo_usd, costo_equivalente_usd), `video`, `trace` y `evidencia_driver: list[Evidencia]`. `Escenario` suma `contrato: ContratoRecorrido | None` (estado_inicial, acciones, resultado_esperado, evidencia_requerida) y `driver: web | android` (por defecto `web`). `UsoLlm` suma `backend` y `costo_equivalente_usd`. `Corrida` suma `version_app`. Todos los campos nuevos tienen valor por defecto: los JSON de corridas viejas siguen cargando.

**Cambios v0.3 (sin migración: las columnas `TEXT` ya admiten los valores nuevos; una sola tarea toca `dominio.py`/`config.py`: F8.1.T1):**
- `ejecuciones.driver` admite `ios`; `ejecuciones.motor` admite `patrol` e `integration_test`.
- `TipoHallazgo` suma `accesibilidad`.
- `Escenario` suma `motor` y `deterministico` (ver *Interfaces*); `Escenario.driver` y `Ejecucion.driver` admiten `ios`.
- `Observacion` suma `cobertura: CoberturaSemantica | None`.
- Carpeta de la ejecución determinista: `deterministico/{test.dart, salida.log, reporte.json}`, `capturas/final.png`. Ejecución iOS: lo mismo que Android, con `syslog.txt` en lugar de `logcat.txt`.
- Copias de trabajo de apps Flutter en `flutter.copia_trabajo` (por defecto `/mnt/storage/cache/dogfood/flutter/<nombre>`), nunca dentro del repo de la app ni de dogfood.

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
- **Cuerpo:** pasos, esperado/obtenido, evidencia **en texto** (extractos de log, eventos de red, el texto visible de la pantalla y las primeras filas del CSV que lo provoca), la ruta local de las capturas (`runs/<corrida>/…`), el comando de replay y un comentario oculto `<!-- dogfood:huella=<sha1> -->`. En la v1 no se suben imágenes: el repo dogfood es privado y `gh` no sube adjuntos. Ver D14.
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

### v0.2 — Driver (`drivers/base.py`)
```python
class ElementoUI(BaseModel):
    id: str                      # resource-id / selector estable; "e<n>" si no hay
    texto: str = ""
    descripcion: str = ""        # content-desc / aria-label
    clase: str = ""
    bounds: tuple[int, int, int, int]   # x1, y1, x2, y2 en píxeles
    clicable: bool = False
    editable: bool = False

class Observacion(BaseModel):
    pantalla: str                # URL (web) o actividad (Android)
    elementos: list[ElementoUI]
    texto_visible: str = ""
    captura: Path | None = None  # PNG del paso
    arbol: Path | None = None    # árbol crudo
    ts: datetime

class Accion(BaseModel):
    tipo: Literal["tocar", "escribir", "deslizar", "tecla", "navegar",
                  "abrir_app", "cerrar_app", "volver", "esperar"]
    elemento: str | None = None  # id de ElementoUI; si no, x/y
    x: int | None = None; y: int | None = None
    x2: int | None = None; y2: int | None = None
    texto: str | None = None     # texto, tecla, URL o paquete
    ms: int | None = None

class ResultadoAccion(BaseModel):
    ok: bool
    error: str = ""
    punto: tuple[int, int] | None = None   # dónde se tocó, para la vista

class Driver(Protocol):
    nombre: str                                   # "web" | "android"
    async def iniciar(self, carpeta: Path) -> None
    async def observar(self, n_paso: int) -> Observacion
    async def actuar(self, accion: Accion) -> ResultadoAccion
    async def frame(self) -> bytes | None         # JPEG para la vista; barato
    async def evidencia(self) -> list[Evidencia]  # consola/red o logcat, video, trace
    async def cerrar(self) -> None
```

### v0.2 — BackendLlm (`backends/base.py`)
```python
class UsoBackend(BaseModel):
    tokens_in: int = 0; tokens_out: int = 0; tokens_cache: int = 0
    capturas: int = 0; duracion_s: float = 0
    costo_usd: float = 0             # lo que se cobra (0 con plan Max)
    costo_equivalente_usd: float = 0 # lo que costaría por API

class ErrorMotor(RuntimeError): ...   # mensaje accionable, sin secretos

class BackendLlm(Protocol):
    nombre: str     # "api" | "claude_code"
    modelo: str
    async def completar_json(self, prompt: str, esquema: type[T], *,
                             imagenes: Sequence[Path] = (), sesion: str | None = None
                             ) -> tuple[T, UsoBackend, str | None]   # salida, uso, sesión
```
`dogfood.yaml`:
```yaml
motores: {persona: api, juez: api, dedupe: api, redactor: api}   # api | claude_code
claude_code: {modelos: {persona: sonnet, juez: sonnet}, mcp_config: null, timeout_s: 180}
agente: {max_capturas_por_paso: 1, resolucion_max: 1024}
driver:                      # por defecto web
  tipo: android
  serial: null               # USB, o
  host_puerto: 100.x.y.z:5555   # localhost o Tailscale, nunca otra red
  paquete: com.ejemplo.app
  apk: null
vista: {host: 127.0.0.1, puerto: 7460}
panel: {host: 127.0.0.1, puerto: 7470}
```

### v0.2 — DecisionPaso (salida del bucle por paso)
```python
class DecisionPaso(BaseModel):
    razonamiento: str  # breve, para la columna de la vista
    paso_contrato: str  # qué paso del contrato persigue
    accion: Accion | None
    esperado: str  # qué debería pasar tras la acción
    friccion: str | None = None
    pedir_captura: bool = False
    terminado: bool = False
    rendirse: str | None = None
```

### v0.2 — Contrato y eventos
```python
Resultado = Literal["aprobado", "fallo", "no_concluyente"]
def resultado(e: Ejecucion) -> Resultado
# no_concluyente: estado == "error", o ningún paso con captura, o exito sin motivo_juez
# aprobado: exito y hay evidencia; fallo: el resto

class EventoVivo(BaseModel):
    corrida_id: str; ejecucion_id: str
    tipo: Literal["inicio", "paso", "frame", "fin"]
    n_paso: int = 0; persona: str = ""; escenario: str = ""
    paso_contrato: str = ""; razonamiento: str = ""; accion: str = ""
    punto: tuple[int, int] | None = None; resultado: str | None = None
    frame_jpeg_b64: str | None = None
    ts: datetime

class BusVivo:
    activo: bool
    def publicar(self, ev: EventoVivo) -> None          # nunca bloquea
    def suscribir(self, max_cola: int = 50) -> Suscripcion   # async iterable; close()
BUS_NULO: BusVivo   # activo = False
```

### v0.2 — HTTP local
| App | Método y ruta | Qué hace |
| --- | --- | --- |
| vista | `GET /` | grilla de ejecuciones en vivo |
| vista | `GET /ws` (WebSocket) | `EventoVivo` en JSON, todas las ejecuciones |
| panel | `GET /` | ejecuciones con filtros `recorrido`, `resultado`, `version`, `persona`, `driver`, `motor` |
| panel | `GET /recorridos` | escenarios con su contrato |
| panel | `GET /corridas/{id}` | resumen y comparación por motor (resultado, tokens, costo y costo equivalente) |
| panel | `GET /ejecuciones/{id}` | paso a paso, video, trace, consola/red o logcat, fricciones |
| panel | `GET /archivos/{ruta}` | archivos bajo `runs/`, con guarda contra `..` |
| panel | `POST /ejecuciones/{id}/issue` | redacta y publica el issue; responde la URL |

### v0.2 — CLI
```
dogfood run … [--driver web|android] [--motor browser_use|bucle] [--vista] [--vista-puerto 7460]
dogfood panel [--host 127.0.0.1] [--puerto 7470] [--raiz runs]
```
`cli.py` descubre los comandos de `comandos/` con `pkgutil` (cada módulo expone `app` y opcionalmente `NOMBRE`), así que un comando nuevo solo agrega su archivo.

### v0.3 — Dominio (`dominio.py`, `drivers/base.py`)
```python
Plataforma = Literal["web", "android", "ios"]
class TipoHallazgo(StrEnum): ...; accesibilidad = "accesibilidad"

class PasoDeterministico(BaseModel):
    accion: Literal["tocar", "escribir", "esperar_texto", "ver_texto", "deslizar", "volver"]
    key: str | None = None        # ValueKey / Semantics(identifier:) del widget
    texto: str | None = None      # texto visible a buscar
    valor: str | None = None      # lo que se escribe; "{env:NOMBRE}" → String.fromEnvironment
    timeout_s: float = 10

class RecorridoDeterministico(BaseModel):
    archivo: str | None = None              # test existente, relativo a la raíz de la app
    pasos: list[PasoDeterministico] = []    # si no hay archivo, se genera
    dart_defines: dict[str, str] = {}       # literales o "{env:NOMBRE}" (secretos de ~/.config/dogfood)

class Escenario(BaseModel):  # suma
    driver: Plataforma = "web"
    motor: Literal["browser_use", "bucle", "patrol", "integration_test"] | None = None
    deterministico: RecorridoDeterministico | None = None

class Ejecucion(BaseModel):  # cambia
    driver: Plataforma = "web"

class CoberturaSemantica(BaseModel):
    flutter: bool = False
    nodos: int = 0            # nodos de la app (bajo FlutterView, o todos si no es Flutter)
    interactivos: int = 0     # clicables, editables, enfocables o desplazables
    etiquetados: int = 0      # interactivos con texto o content-desc/label
    con_id: int = 0           # interactivos con resource-id / identifier estable
    ratio_etiqueta: float = 1.0   # etiquetados / interactivos (1.0 si no hay interactivos)
    ratio_id: float = 1.0
    ciega: bool = False       # flutter y (nodos == 0 o ratio_etiqueta < umbral)

class Observacion(BaseModel):  # suma
    cobertura: CoberturaSemantica | None = None
```

### v0.3 — Flutter (`flutter/semantica.py`)
```python
def es_flutter(xml: str, actividad: str = "") -> bool
def cobertura_xml(xml: str, *, umbral: float = 0.6, actividad: str = "") -> CoberturaSemantica
    # uiautomator (node: text, content-desc, resource-id, clickable, focusable, scrollable, class)
    # y XCUITest (XCUIElementType*: name, label, value, accessible, type)
def cobertura_elementos(elementos: Sequence[ElementoUI], *, flutter: bool, umbral: float = 0.6) -> CoberturaSemantica
```

### v0.3 — Fuente de frames (`frames/`)
```python
class FuenteFrames(Protocol):
    nombre: str                # "driver" | "screencap" | "screenrecord" | "mjpeg"
    intervalo_s: float         # cada cuánto la pide el emisor de la vista
    async def iniciar(self) -> None
    async def frame(self) -> bytes | None   # último JPEG; barato, nunca espera a la red más de intervalo_s
    async def cerrar(self) -> None

class FuenteDeDriver:  # FuenteFrames sobre driver.frame(); intervalo según driver.nombre
    def __init__(self, driver: Driver, intervalo_s: float | None = None)

def validar_url_local(url: str) -> str     # http(s) con host 127.0.0.1/localhost/::1 o 100.64.0.0/10; si no, ValueError (NFR-12)
def crear_fuente(cfg: Config, driver: Driver, parametros: dict) -> FuenteFrames   # frames/__init__.py
class FuenteScreencap:   def __init__(self, adb: Adb, fps: float = 2)
class FuenteScreenrecord: def __init__(self, adb: Adb, carpeta_video: Path, fps: float = 5, runner_ffmpeg=None)
class FuenteMjpeg:       def __init__(self, url: str, cliente: httpx.AsyncClient | None = None)
```

### v0.3 — Motor determinista (`deterministico/`)
```python
Herramienta = Literal["patrol", "integration_test"]
RunnerProceso = Callable[..., Awaitable[tuple[int, bytes, bytes]]]
    # (args: list[str], *, cwd: Path, env: dict[str, str], timeout_s: float) -> (código, stdout, stderr)

def generar_test(escenario: Escenario, herramienta: Herramienta) -> str          # generador.py
def defines(recorrido: RecorridoDeterministico, cfg: Config) -> dict[str, str]  # resuelve {env:X}

class ResultadoTest(BaseModel):
    nombre: str; estado: Literal["ok", "fallo", "error", "saltado"]; ms: int = 0; mensaje: str = ""

class ResultadoDeterministico(BaseModel):
    herramienta: Herramienta
    codigo_salida: int | None          # None = timeout
    tests: list[ResultadoTest] = []
    motivo: str = ""                    # compilacion | sin_dispositivo | timeout | sin_tests | app_sin_patrol
    log: Path; reporte: Path | None = None; captura_final: Path | None = None
    def resultado(self) -> Resultado    # aprobado: código 0, ≥1 test y todos ok; fallo: algún test en fallo; resto no_concluyente

class CorredorFlutter:                  # corredor.py
    def __init__(self, cfg: Config, runner: RunnerProceso | None = None)
    def copia_de_trabajo(self, proyecto: Path) -> Path
    def comando(self, herramienta: Herramienta, test: Path, dispositivo: str, defines: dict[str, str]) -> list[str]
    async def correr(self, escenario: Escenario, herramienta: Herramienta, dispositivo: str, carpeta: Path,
                     *, proyecto: Path | None = None,
                     capturar: Callable[[Path], Awaitable[Path | None]] | None = None) -> ResultadoDeterministico

def a_ejecucion(r: ResultadoDeterministico, persona: Persona, escenario: Escenario, ejecucion_id: str,
                driver: Plataforma) -> Ejecucion
    # exito = r.resultado() == "aprobado"; motivo_juez = resumen de tests; estado: ok | fallo | error
```
Comandos exactos: `flutter test integration_test/dogfood/<id>_test.dart -d <dispositivo> --reporter json --dart-define K=V …` y `patrol test --target integration_test/dogfood/<id>_test.dart --device <dispositivo> --dart-define K=V …`, con `cwd` en la copia de trabajo, `PUB_CACHE` de la config y los defines solo en el entorno del proceso y en argv (nunca en el log de dogfood: se redactan).

### v0.3 — Nodo iOS (`nodos/protocolo.py`)
```python
class Trabajo(BaseModel):
    id: str
    tipo: Literal["estado", "patrol", "sesion_appium", "cerrar_sesion"]
    udid: str | None = None
    bundle_id: str | None = None
    proyecto: str | None = None             # ruta de la app en el Mac (patrol)
    escenario: Escenario | None = None      # patrol: con su bloque deterministico
    dart_defines: dict[str, str] = {}       # viajan solo por stdin; el nodo no los escribe a disco
    timeout_s: float = 1800

class EstadoNodo(BaseModel):
    xcode: str | None = None; flutter: str | None = None; patrol: str | None = None
    appium: bool = False; dispositivos: list[dict[str, str]] = []   # {udid, nombre, os}

class ResultadoTrabajo(BaseModel):
    id: str
    estado: Literal["ok", "fallo", "error"]
    mensaje: str = ""
    deterministico: ResultadoDeterministico | None = None   # rutas relativas a dir_trabajo/<id>/
    artefactos: list[str] = []
    appium_url: str | None = None; mjpeg_url: str | None = None
    estado_nodo: EstadoNodo | None = None
```
Transporte: `ssh -o BatchMode=yes -o ConnectTimeout=10 -p <puerto_ssh> <usuario>@<host> <comando> ejecutar` con el `Trabajo` en JSON por stdin; la última línea no vacía de stdout es el `ResultadoTrabajo`. Artefactos: `rsync -a -e "ssh -p <p>" <usuario>@<host>:<dir_trabajo>/<id>/ <carpeta>/`.

### v0.3 — `dogfood.yaml`
```yaml
driver:
  tipo: android                 # web | android | ios
  nodo: null                    # ios: nombre en `nodos`
  udid: null                    # ios
  bundle_id: null               # ios
pantalla:
  android: screencap            # screencap | screenrecord
  fps: 2
flutter:
  sdk: /mnt/storage/flutter/bin/flutter
  patrol: /mnt/storage/flutter/.pub-cache/bin/patrol
  pub_cache: /mnt/storage/flutter/.pub-cache
  proyecto: null                # raíz de la app Flutter (solo lectura)
  copia_trabajo: /mnt/storage/cache/dogfood/flutter
  umbral_cobertura: 0.6
  timeout_s: 1800
flutter_web:
  build_dir: null               # build/web ya compilado; si no, se compila desde flutter.proyecto
  host: 127.0.0.1
  puerto: 7480
  api_permitidas: []            # orígenes que la app web puede llamar
  dart_defines: {}
nodos:
  mac:
    host: 100.x.y.z             # Tailscale (o 127.0.0.1)
    usuario: hector
    puerto_ssh: 22
    comando: dogfood nodo       # en el PATH del Mac
    dir_trabajo: ~/dogfood-nodo
    proyectos: {}               # nombre → ruta de la app en el Mac
```

### v0.3 — HTTP local y CLI
| App | Método y ruta | Qué hace |
| --- | --- | --- |
| panel | `GET /dispositivos` | Android permitidos por `adb` y nodos iOS, con su pantalla en vivo |
| panel | `GET /dispositivos/{id}/mjpeg` | `multipart/x-mixed-replace; boundary=frame` desde la `FuenteFrames` del dispositivo |

```
dogfood android emparejar <ip:puerto> | conectar [<ip:puerto>] | estado | desconectar [<ip:puerto>]
dogfood nodo estado [--json] | ejecutar          # en el Mac
dogfood run … [--driver web|android|ios] [--motor browser_use|bucle|patrol|integration_test]
dogfood run --target flutter_web …               # filtro web
```

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
- **D14 — Evidencia sin imágenes en la v1.** El issue lleva evidencia en texto, más la ruta local de las capturas y el replay. Descartados: un release de assets en el repo privado dogfood, que en un issue público no se ve; y una rama de evidencias en predicts, que lo ensucia. Pendiente para v2: un bucket o la API de uploads de GitHub.
- **D13 — CI sin docker.** Los tests unitarios usan fakes del `Objetivo` y del LLM. Los de integración llevan la marca `integracion` y se excluyen por defecto (`addopts = -m "not integracion"`). Las tareas que los escriben los corren a mano en el server.

- **D15 — Claude Code como backend por paso, no como agente completo.** Elegido: dogfood mantiene su bucle (observa, decide, actúa) y `claude -p` solo decide el paso con salida JSON validada (`--json-schema`), con `--resume` para conservar el contexto. Así la evidencia por paso (captura, árbol, consola, red, logcat) y el contrato quedan bajo control de dogfood, igual con cualquier backend. Descartado: darle a Claude Code el escenario entero con Playwright MCP, porque la evidencia y los tiempos quedarían dentro de su sesión y no habría equivalente para Android; los MCPs siguen disponibles con `--mcp-config` para quien los quiera sumar.
- **D16 — Costo del plan Max.** `costo_usd = 0` y `costo_equivalente_usd = total_cost_usd` del JSON de `claude -p`; el panel muestra las dos columnas para comparar motores. Descartado: contar 0 sin más, porque no permitiría comparar.
- **D17 — Driver Android sobre ADB directo.** Elegido: `adb` + `uiautomator dump`, sin servicios extra en el teléfono. Descartado por ahora: Appium + UIAutomator2, que agrega un servidor Java y una dependencia pesada.
- **D18 — Spike de la opción B diferido.** El issue pide un spike medible de Appium o `mobile-mcp`, pero hoy no hay dispositivo conectado ni KVM: se documenta en `docs/ops/android.md` cómo medirlo (tiempo por paso y tasa de esperas fallidas en el escenario de login) y queda pendiente con dispositivo real.
- **D19 — Vista dentro del proceso de la corrida.** Elegido: uvicorn en el mismo loop asyncio de `dogfood run --vista`, con un bus en memoria; los frames no tocan disco. Descartado: un proceso aparte que lea archivos, porque agrega latencia (FR-31 pide < 1 s) y escritura de frames.
- **D20 — Panel server-rendered.** Elegido: FastAPI + Jinja2 con un poco de JS propio y la hoja de estilo con los tokens del dashboard de orch. Descartado: el SPA React de orch (Vite + Tailwind), porque metería Node y un build en un proyecto Python para pocas pantallas.
- **D21 — Exposición local.** Vista y panel solo en loopback o una IP de Tailscale, ADB solo USB/loopback/Tailscale (NFR-10); `validar_host` lo hace cumplir y los tests lo prueban. Descartado: auth propia, porque no hay exposición pública que proteger.
- **D22 — Tests sin dispositivo ni `claude` real.** El `adb` y el `claude` se reemplazan por *runners* falsos (y un script `claude` falso en el PATH) con salidas grabadas. Las pruebas con dispositivo real y con la sesión de Claude Code son manuales y llevan la marca `integracion`.

- **D23 — Android real por ADB inalámbrico sobre Tailscale.** Elegido: `adb pair` + `adb connect` a la IP `100.x` del teléfono, con el emparejamiento hecho a mano una vez y el código tecleado en el prompt de `adb`; reconexión automática una sola vez. Descartado: `adb tcpip 5555` en la LAN, porque deja el ADB abierto a toda la red (NFR-10), y guardar el código de emparejamiento, porque es un secreto de un solo uso.
- **D24 — Pantalla Android: `screencap` por defecto, `screenrecord`+`ffmpeg` opcional.** `screencap` a 2 fps cumple la latencia < 2 s sin procesos extra; el stream H.264 de `screenrecord` decodificado con `ffmpeg` (instalado en el homelab) da más fps y además sirve de video de evidencia. Descartados: `ws-scrcpy`, porque es un servicio Node aparte que expone el control del dispositivo en un navegador (otra superficie que proteger), y `scrcpy`, que no está instalado y es un cliente con ventana pensado para un humano.
- **D25 — Pantalla iPhone: MJPEG de WebDriverAgent.** Elegido: `appium:mjpegServerPort: 9100` y un túnel SSH a `127.0.0.1:9100`. Descartado: pedir `GET /screenshot` en bucle, que tarda ~1 s por imagen y compite con las acciones.
- **D26 — Cobertura de Semantics sobre el árbol crudo.** Elegido: medir sobre el XML de `uiautomator`/XCUITest que ya se guarda en cada paso, y tratar la pantalla ciega como hallazgo (`accesibilidad`) más captura forzada para el modelo. Descartado: Flutter Driver o el VM service, que exigen un build de depuración instrumentado y no reflejan lo que ve un lector de pantalla.
- **D27 — Motor determinista por CLI en una copia de trabajo.** Elegido: generar o reutilizar tests de Patrol / `integration_test` y correrlos con su CLI en una copia de la app, con el resultado mapeado al contrato de FR-30. `integration_test` es el valor por defecto para tests generados (no pide configuración nativa); Patrol solo si la app ya lo tiene configurado. Descartados: repetir login y pago con el bucle agéntico, que no es determinista para recorridos críticos; y escribir tests en el repo de la app, que es de Héctor y solo lectura para dogfood.
- **D28 — Nodo iOS por SSH sobre Tailscale.** Elegido: protocolo JSON por stdin/stdout de `ssh`, artefactos por `rsync`, Appium y WDA escuchando solo en loopback del Mac y alcanzados por túnel SSH. Descartados: un servicio HTTP propio en el Mac (otro puerto que exponer y autenticar), y Appium remoto sin nodo, que no cubre Patrol ni la verificación de Xcode.
- **D29 — Driver iOS por HTTP W3C, sin cliente de Appium.** Elegido: `httpx` contra la API WebDriver de Appium. Descartado: `Appium-Python-Client`, que arrastra Selenium y es síncrono, para pocas rutas.
- **D30 — Filtro web con Flutter web y Semantics habilitados.** Elegido: servir el `build/web` y activar `flt-semantics` desde el driver web existente, para probar lógica y recorridos antes del celular sin hardware. Descartado: actuar solo por visión sobre el canvas de Flutter, que es caro y no mide la cobertura.
- **D31 — SDK de Flutter fuera del home.** El SDK y su `PUB_CACHE` viven en `/mnt/storage/flutter` (el NVMe es solo del sistema); los tests no lo necesitan (runners falsos). Descartado: instalarlo en `~` o con snap.

## Riesgos

- **Que browser-use se trabe en pantallas 3D o con SSE** (universo, procesamiento en vivo). *Mitigación:* límite de pasos y timeout por ejecución; la pantalla 3D se marca como «solo mirar» en los escenarios; un timeout es un hallazgo técnico solo si lo confirma el trabajo en la API.
- **Falsos positivos del oráculo**, que llenarían de ruido el repo público. *Mitigación:* tolerancias conservadoras, umbral de gravedad para publicar y `--sin-publicar` en las primeras corridas. Las primeras corridas de M3 se revisan a mano antes de activar la publicación (la publicación entra recién en F4).
- **Memoria del homelab.** *Mitigación:* los límites del compose de predicts, 5 Chromium por defecto, `docker stats` muestreado por la corrida, y abortar si la memoria libre baja de 2 GB.
- **Que cambie la UI de predicts.** El agente es de lenguaje natural, no de selectores, así que tolera cambios. El replay puede romperse: se informa como «no reproducible por cambio de UI» y no como «arreglado».
- **Costo de IA en predicts** (Jev en cada mapeo y mensajes por análisis) con más de 100 personas. *Mitigación:* lo mide D12, y existe `--tope-usd`.
- **Latencia de `claude -p` por paso** (arranque de varios segundos). *Mitigación:* `--resume` para no reenviar contexto, `timeout_s` configurable y comparación de tiempos en el panel; si no alcanza, el backend `api` sigue disponible.
- **`uiautomator dump` lento o vacío** en pantallas con animaciones o WebView. *Mitigación:* reintento corto, captura como respaldo para el modelo y la opción B (D18) si los números del spike lo justifican.
- **Tailscale en el teléfono se duerme** (Android mata la VPN en segundo plano o cambia el puerto de depuración). *Mitigación:* reconexión una vez, mensaje con el comando `dogfood android conectar`, y la guía pide excluir Tailscale de la optimización de batería.
- **Apps Flutter casi sin Semantics** (`mobile-mao` tiene 5 `Semantics(` y ningún `identifier`): el agente vería pantallas ciegas. *Mitigación:* respaldo por visión (captura + coordenadas) y el hallazgo de accesibilidad, que es justamente lo que hay que arreglar en la app.
- **Patrol exige configuración nativa** (runner de instrumentación en Android, target de UI tests en iOS). *Mitigación:* `integration_test` por defecto para tests generados; Patrol solo con la app preparada, y si no, `no_concluyente` con la instrucción.
- **El Mac no está siempre encendido o en la tailnet.** *Mitigación:* `ClienteNodo.estado()` con `ConnectTimeout` corto; la corrida iOS falla temprano con un mensaje claro y no bloquea Android/web.
- **Firma de WebDriverAgent caduca** (perfil de desarrollo de 7 días con cuenta gratuita). *Mitigación:* la guía pide cuenta de desarrollador paga y `dogfood nodo estado` reporta si Appium puede abrir sesión.
- **Compilar Flutter web en el homelab** usa CPU y memoria. *Mitigación:* se compila una vez por commit en la copia de trabajo y se reutiliza el `build/web`.
- **Frames que saturan la memoria o la CPU con varias ejecuciones.** *Mitigación:* JPEG de baja calidad, tope de fps, cola acotada que descarta frames viejos (NFR-11) y la vista solo con `--vista`.

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
| FR-26 | backends/base.py, backends/api.py, backends/claude_code.py, llm.py (`backend_para`), panel (comparación) |
| FR-27 | agente/bucle.py (capturas y resolución), dominio.py (`MetricasEjecucion`), almacen.py v2 |
| FR-28 | drivers/base.py, agente/bucle.py |
| FR-29 | drivers/android.py, objetivos/android/, docs/ops/android.md |
| FR-30 | contrato.py, corrida.py |
| FR-31 | eventos.py, vista/, agente/bucle.py y agente/navegador.py (frames y razonamiento), corrida.py (`--vista`) |
| FR-32 | panel/app.py, panel/consultas.py, panel/detalle.py, drivers (video, trace, logcat) |
| FR-33 | panel/issue.py, reporte/redactar.py, reporte/issues.py |
| NFR-10 | web/ (`validar_host`), drivers/android.py (destino ADB) |
| NFR-11 | eventos.py (cola acotada), agente/bucle.py (emisor de frames) |
| FR-34 | drivers/adb_red.py, comandos/android.py, drivers/android.py (reconexión), docs/ops/android.md |
| FR-35 | flutter/semantica.py, drivers/android.py (cobertura), agente/bucle.py (captura forzada), deteccion/flutter.py |
| FR-36 | deterministico/generador.py, deterministico/corredor.py, corrida.py, objetivos/android/escenarios (login y pago) |
| FR-37 | frames/, agente/bucle.py (fuente), corrida.py, panel/dispositivos.py |
| FR-38 | nodos/protocolo.py, nodos/cliente.py, nodos/runner.py, comandos/nodo.py, drivers/ios.py, objetivos/ios/, docs/ops/ios-nodo-mac.md |
| FR-39 | objetivos/flutter_web/, drivers/web.py (Semantics de Flutter web), flutter/semantica.py |
| NFR-12 | frames/base.py (`validar_url_local`), nodos/cliente.py (host), drivers/adb_red.py (servidor local), drivers/ios.py |
| NFR-13 | runners inyectables en adb_red, corredor, cliente/runner del nodo, frames y driver iOS; config `flutter.sdk` |

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

### F6 — Motores intercambiables y Android (M6)
- **F6.1 — contratos v0.2** (esqueleto de la fase): dependencias nuevas (FastAPI, uvicorn) en `pyproject.toml` + `uv.lock`; `cli.py` con autodescubrimiento; campos nuevos de `dominio.py`; migración v2 de `almacen.py`; bloques nuevos de `config.py` y `dogfood.example.yaml`; `contrato.py`; `eventos.py`; `drivers/{__init__,base}.py`; `backends/{__init__,base}.py`.
- **F6.2 — backend claude_code**: `backends/claude_code.py`, `backends/api.py`, `llm.py`. Depende de F6.1.
- **F6.3 — driver Android**: `drivers/android.py`, `tests/fixtures/android/`. Depende de F6.1.
- **F6.4 — driver web**: `drivers/web.py`. Depende de F6.1.
- **F6.5 — bucle de agente**: `agente/bucle.py`, `agente/prompts_bucle.py`. Depende de F6.1.
- **F6.6 — objetivo Android**: `objetivos/android/`, `objetivos/__init__.py`. Depende de F6.3.
- **F6.7 — integración en la corrida**: `corrida.py`, `comandos/run.py`, `agente/navegador.py`. Depende de F6.2–F6.6.
- **F6.8 — docs de operación**: `docs/ops/android.md`, `docs/ops/claude-code.md`. Depende de F6.2 y F6.3.

### F7 — Vista en vivo y panel (M7)
- **F7.1 — base web**: `web/` (app base, `validar_host`, CSS con tokens de orch, `base.html`). Depende de F6.1.
- **F7.2 — vista en vivo**: `vista/`. Depende de F7.1.
- **F7.3 — vista en la corrida**: `corrida.py`, `comandos/run.py`. Depende de F7.2 y F6.7.
- **F7.4 — panel: listas y filtros**: `panel/{__init__,app,consultas}.py`, plantillas de listas, `comandos/panel.py`. Depende de F7.1.
- **F7.5 — panel: detalle y crear issue**: `panel/{detalle,issue}.py`, `panel/app.py`, `plantillas/ejecucion.html`. Depende de F7.4.
- **F7.9 — integración M7**: `tests/integracion/test_panel_vista.py`, `docs/ops/panel-y-vista.md`. Depende de F7.3 y F7.5.

### F8 — Flutter en celular real (M8)
Archivos compartidos encadenados: `agente/bucle.py` (F8.3.T2 → F8.4.T3), `corrida.py` y `comandos/run.py` (F8.4.T3 → F8.5.T3 → F8.6.T4), `drivers/android.py` (F8.2.T1 → F8.3.T2). `dominio.py`, `config.py`, `dogfood.example.yaml`, `objetivos/__init__.py` y `deteccion/__init__.py` solo los toca F8.1.
- **F8.1 — contratos v0.3** (esqueleto): `dominio.py`, `config.py`, `dogfood.example.yaml`, `drivers/base.py` (`Observacion.cobertura`), `drivers/android.py` (`grabar_video`), `frames/{__init__,base}.py`, `nodos/{__init__,protocolo}.py`, `flutter/__init__.py`, `deterministico/__init__.py`, `deteccion/{__init__,flutter}.py` (stub registrado), `objetivos/__init__.py` (registra `ios` y `flutter_web`), stubs `objetivos/{ios,flutter_web}/__init__.py`.
- **F8.2 — Android por Tailscale**: `drivers/adb_red.py`, `comandos/android.py`, `drivers/android.py` (reconexión). Depende de F8.1.
- **F8.3 — Flutter en Android**: T1 `flutter/semantica.py`, `deteccion/flutter.py`; T2 `drivers/android.py` (cobertura), `agente/bucle.py`, `agente/prompts_bucle.py`. T1 depende de F8.1; T2 de T1 y F8.2.
- **F8.4 — fuentes de frames**: T1 `frames/{__init__,android,mjpeg}.py`; T2 `panel/dispositivos.py`, `panel/app.py`, plantilla, `web/plantillas/base.html`; T3 `agente/bucle.py`, `corrida.py` (fuente, driver web Flutter, ios en el emisor). T1 depende de F8.1; T2 de T1 y F8.2; T3 de T1, F8.3.T2 y F8.7.T1.
- **F8.5 — motor determinista**: T1 `deterministico/corredor.py`; T2 `deterministico/generador.py` y escenarios de ejemplo; T3 `corrida.py`, `comandos/run.py`. T2 depende de F8.1; T1 de T2 (usa el generador); T3 de T1, T2 y F8.4.T3.
- **F8.6 — nodo iOS**: T1 `nodos/cliente.py`; T2 `nodos/runner.py`, `comandos/nodo.py`; T3 `drivers/ios.py`; T4 `objetivos/ios/`, `corrida.py`, `comandos/run.py`. T1 y T2 dependen de F8.5.T1 (`a_ejecucion` y el corredor); T3 de F8.1 y F8.3.T1; T4 de T1, T3 y F8.5.T3.
- **F8.7 — filtro web**: T1 `drivers/web.py`, `objetivos/flutter_web/`; T2 integración real con una copia de `mobile-mao` (`tests/integracion/test_flutter_web.py`, `docs/notas/m8-flutter-web.md`). T1 depende de F8.3.T1 y F8.5.T1 (copia de trabajo); T2 de T1.
- **F8.9 — operación**: T1 `docs/ops/android.md`, `docs/ops/flutter.md`; T2 `docs/ops/ios-nodo-mac.md`. T1 depende de F8.2, F8.3.T2, F8.4.T2, F8.4.T3, F8.5.T3 y F8.7.T1; T2 de F8.6.T2 y F8.6.T4.
