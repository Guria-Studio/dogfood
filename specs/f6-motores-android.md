---
type: spec
project_id: dogfood
phase: 6
version: 0.1
depends_on:
  - docs/prd/001-usuarios-agenticos.md
  - docs/arch/001-usuarios-agenticos.md
  - specs/f5-modelos.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-29
title: Motores intercambiables y Android
---

# F6 — Motores intercambiables y Android

M6 del PRD (v0.3): el motor del agente se puede cambiar entre un backend por API (9router) y Claude Code con el plan Max (`claude -p`), y el agente habla con la app por una interfaz `Driver` común con un driver web (Playwright) y uno Android (ADB/UIAutomator). FR-26 a FR-30 y NFR-10; issues #35 y #32 de hectorcanaimero/dogfood.

Contexto común para todas las tareas de esta fase:
- Lee `CONTEXTO.md`, el PRD `docs/prd/001-usuarios-agenticos.md` (sección «Motores, drivers y observabilidad») y la arquitectura `docs/arch/001-usuarios-agenticos.md`: secciones *Componentes* (bloques v0.2), *Modelo de datos* («Cambios v0.2»), *Interfaces* (bloques «v0.2») y decisiones D15 a D22. Las firmas de las *Interfaces* son el contrato: impleméntalas tal cual.
- Código, comentarios, docstrings y mensajes en español. Python 3.13 con uv; `uv run pytest` y `uv run ruff check . && uv run ruff format --check .` deben pasar antes de terminar.
- **No hay dispositivo Android conectado ni KVM, y CI no tiene sesión de Claude Code.** Ningún test llama al `adb` ni al `claude` reales: se usan *runners* inyectables o un script `claude` falso en un directorio temporal agregado al `PATH` (D22). Lo que necesite hardware real va con la marca `integracion`, que está excluida por defecto.
- Sin secretos en el repo. ADB solo por USB, `127.0.0.1` o Tailscale (`100.64.0.0/10`); nunca expongas ADB ni abras puertos en `0.0.0.0` (NFR-10).
- Los tests existentes (F0–F5) deben seguir pasando sin cambios, salvo que el brief diga lo contrario.

## F6.1 — Package: contratos v0.2

### F6.1.T1 — Contratos de motores, drivers, contrato de resultado y eventos

Esqueleto de la fase: deja fijos todos los contratos y archivos compartidos para que F6.2–F6.6 y F7 trabajen en paralelo sin tocar los mismos archivos.

1. `pyproject.toml` + `uv.lock`: agrega `fastapi` y `uvicorn[standard]` (WebSocket incluido) como dependencias, y `httpx` ya está. Son todas las dependencias nuevas de F6 y F7; ninguna tarea posterior edita estos dos archivos. Regenera el lock con `uv lock`.
2. `src/dogfood/cli.py`: reemplaza la lista fija de comandos por autodescubrimiento con `pkgutil` sobre `dogfood.comandos` (se saltan los módulos que empiezan con `_`); cada módulo expone `app: typer.Typer` y opcionalmente `NOMBRE` (por defecto el nombre del módulo). `dogfood --help` sigue listando `env`, `datos`, `personas`, `run`, `runs` y `replay`.
3. `src/dogfood/dominio.py`: agrega los campos y modelos de «Cambios v0.2» del *Modelo de datos*: en `Paso` `razonamiento`, `paso_contrato`, `esperado`, `observado`, `arbol: Path | None`, `punto: tuple[int, int] | None`; `MetricasEjecucion` (tokens_in, tokens_out, capturas, costo_usd, costo_equivalente_usd); en `Ejecucion` `driver` (`web` | `android`, por defecto `web`), `motor` (por defecto `browser_use`), `backend` (por defecto `api`), `resultado` (`aprobado` | `fallo` | `no_concluyente` | None), `metricas`, `video`, `trace`, `evidencia_driver: list[Evidencia]`; `ContratoRecorrido` (estado_inicial, acciones: list[str], resultado_esperado, evidencia_requerida: list[str]) y en `Escenario` `contrato: ContratoRecorrido | None` y `driver` (por defecto `web`); en `UsoLlm` `backend` y `costo_equivalente_usd`; en `Corrida` `version_app: str | None`. Todo con valores por defecto, para que los JSON de corridas viejas sigan cargando.
4. `src/dogfood/almacen.py`: `VERSION_ESQUEMA = 2` y una migración v1 → v2 con `ALTER TABLE … ADD COLUMN` exactamente con las columnas de «Cambios v0.2». Una base nueva queda en v2; una base v1 existente se migra sin perder filas. Guardar una `Ejecucion` escribe las columnas nuevas (driver, motor, backend, resultado, métricas, video, trace) y guardar un `UsoLlm` escribe `backend` y `costo_equivalente_usd`.
5. `src/dogfood/config.py` y `dogfood.example.yaml`: los bloques `motores`, `claude_code`, `agente`, `driver`, `vista` y `panel` de la interfaz «BackendLlm» de la arquitectura, como modelos Pydantic con valores por defecto (`motores` en `api` para todos los roles; `vista` en `127.0.0.1:7460`; `panel` en `127.0.0.1:7470`; `driver.tipo` en `web`). Un `dogfood.yaml` viejo sin esos bloques sigue cargando.
6. `src/dogfood/contrato.py`: `Resultado` y `resultado(e: Ejecucion) -> Resultado` con la regla de la interfaz «Contrato y eventos» (no concluyente si `estado == "error"`, si ningún paso tiene captura o si `exito` es verdadero sin `motivo_juez`; aprobado solo si `exito` y hay evidencia; fallo en el resto).
7. `src/dogfood/eventos.py`: `EventoVivo`, `BusVivo` (pub/sub en memoria; `publicar` nunca bloquea; cada suscriptor tiene una cola acotada y, si está llena, se descarta el evento más viejo) y `BUS_NULO` (inactivo, no hace nada).
8. `src/dogfood/drivers/__init__.py` y `src/dogfood/drivers/base.py`: `ElementoUI`, `Observacion`, `Accion`, `ResultadoAccion` y el protocolo `Driver`, tal cual la interfaz «Driver». Además una función `arbol_a_texto(elementos) -> str` (una línea por elemento: id, clase corta, texto o descripción, centro, marcas clicable/editable) que usan los dos drivers y el bucle.
9. `src/dogfood/backends/__init__.py` y `src/dogfood/backends/base.py`: `UsoBackend`, `ErrorMotor` y el protocolo `BackendLlm`, tal cual la interfaz «BackendLlm».

Done when: estos tests pasan en `tests/test_contratos_f6.py` y los tests existentes siguen verdes:
- `dogfood --help` lista los seis comandos de siempre tras el autodescubrimiento;
- una `Ejecucion` serializada con el esquema de F5 (sin campos nuevos) carga y tiene `driver == "web"` y `resultado is None`;
- una base SQLite creada con el esquema v1 se migra a v2, conserva sus filas y acepta las columnas nuevas;
- `resultado` da `no_concluyente` con `exito=True` y ningún paso con captura, `aprobado` con capturas y `motivo_juez`, `fallo` con `estado="fallo"` y capturas, y `no_concluyente` con `estado="error"`;
- `BusVivo.publicar` con un suscriptor que no lee no bloquea y la cola nunca pasa su tope; `BUS_NULO.activo` es falso;
- `Config.cargar` con un `dogfood.yaml` sin bloques nuevos da `motores.persona == "api"` y `vista.host == "127.0.0.1"`;
- `arbol_a_texto` da una línea por elemento con su id y su centro.

- **Modelo**: claude/claude-opus-5-5
- **Estimación**: 4h
- **Razón**: Fija los contratos de dos fases y la migración del almacén; un error aquí se arrastra a todo lo demás.
- **Dependencies**:
- **Files**:
  - `pyproject.toml`
  - `uv.lock`
  - `src/dogfood/cli.py`
  - `src/dogfood/dominio.py`
  - `src/dogfood/almacen.py`
  - `src/dogfood/config.py`
  - `dogfood.example.yaml`
  - `src/dogfood/contrato.py`
  - `src/dogfood/eventos.py`
  - `src/dogfood/drivers/__init__.py`
  - `src/dogfood/drivers/base.py`
  - `src/dogfood/backends/__init__.py`
  - `src/dogfood/backends/base.py`
  - `tests/test_contratos_f6.py`

## F6.2 — Package: backend claude_code

### F6.2.T1 — Backend claude_code (plan Max) intercambiable con el de API

Issue #35, FR-26 y FR-27, decisiones D15 y D16.

1. `src/dogfood/backends/api.py`: `BackendApi(modelo, cfg, contador=None)` que cumple `BackendLlm` moviendo detrás del protocolo la lógica de `completar_json` de `llm.py` (9router, `response_format` `json_schema`, `stream: False`, sin `tool_choice` forzado). Las imágenes van como partes `image_url` con data URL base64 y suman `capturas` en `UsoBackend`. El costo sale de `precios_usd_por_millon`.
2. `src/dogfood/backends/claude_code.py`: `BackendClaudeCode(modelo, cfg)` que ejecuta `claude -p` como subproceso asíncrono (`asyncio.create_subprocess_exec`, nunca con shell) con `--output-format json`, `--json-schema` (el `model_json_schema()` del esquema), `--model`, `--strict-mcp-config` (y `--mcp-config <ruta>` solo si `claude_code.mcp_config` está configurado), `--resume <sesion>` cuando se pasa `sesion`, y las herramientas restringidas a `Read` sobre el directorio de las imágenes (`--allowedTools Read` y `--add-dir`). Lee `claude --help` del binario instalado para confirmar los nombres exactos de las opciones. El `cwd` del subproceso es un directorio temporal o el de las imágenes, nunca el repo, para no cargar el `CLAUDE.md` de dogfood. Las imágenes se mencionan en el prompt por ruta absoluta para que el modelo las lea. Del JSON de salida toma la salida estructurada (`structured_output` si existe; si no, `result` parseado como JSON), `session_id`, `usage` (input + cache como `tokens_in`/`tokens_cache`, `output_tokens` como `tokens_out`) y `total_cost_usd` como `costo_equivalente_usd`; `costo_usd` es 0 (plan Max). Timeout `claude_code.timeout_s`.
3. Errores claros (`ErrorMotor`, sin volcar el entorno ni secretos): `claude` no está en el PATH → «instala Claude Code y ejecuta `claude` para iniciar sesión»; salida con `is_error` o texto de sesión ausente o inválida (p. ej. «Not logged in», «Invalid API key», «/login») → «Claude Code no está autenticado: ejecuta `claude` y luego /login con la cuenta del plan Max»; JSON que no valida contra el esquema → error con los primeros 300 caracteres de la respuesta; timeout → error con el tiempo.
4. `src/dogfood/llm.py`: `backend_para(rol, cfg=None, indice=0, contador=None) -> BackendLlm` según `cfg.motores[rol]` (`api` o `claude_code`; otro valor → `ValueError` con los válidos). El modelo de `claude_code` sale de `claude_code.modelos[rol]` y, si falta, de `roles[rol][indice]`. `completar_json` existente pasa a delegar en `BackendApi` y conserva su firma y su comportamiento (los tests de F0–F5 no cambian); `ContadorUso.registrar` acepta `backend` y `costo_equivalente_usd` opcionales.

Done when: estos tests pasan en `tests/test_backend_claude_code.py`, con un script `claude` falso en un directorio temporal antepuesto al `PATH` (monkeypatch) que imprime un JSON grabado y deja en un archivo los argumentos recibidos, y con `respx` para la API:
- `claude_code` devuelve la salida validada, el `session_id`, los tokens y `costo_usd == 0` con `costo_equivalente_usd == total_cost_usd`;
- los argumentos incluyen `-p`, `--output-format json`, `--json-schema`, `--model` y `--resume <id>` cuando se pasa la sesión, y nunca `--mcp-config` si no está configurado;
- sin `claude` en el PATH el error dice cómo instalarlo; con una salida «Not logged in» el error dice que falta autenticar con `claude` y /login;
- una respuesta que no valida contra el esquema da `ErrorMotor`;
- el subproceso corre fuera del repo (el `cwd` grabado no es la raíz del proyecto);
- `BackendApi` manda las imágenes como `image_url` y cuenta las capturas;
- `backend_para` elige `api` o `claude_code` según `motores` y rechaza un valor desconocido;
- `completar_json` sigue funcionando como antes (mismo cuerpo de petición).

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Integración con un CLI y un protocolo ya fijados; tier estándar.
- **Dependencies**: F6.1.T1
- **Files**:
  - `src/dogfood/backends/api.py`
  - `src/dogfood/backends/claude_code.py`
  - `src/dogfood/llm.py`
  - `tests/test_backend_claude_code.py`

## F6.3 — Package: driver Android

### F6.3.T1 — Driver Android por ADB y UIAutomator

Issue #32, FR-28 y FR-29, decisiones D17, D21 y D22. `adb` está en `/usr/bin/adb`, pero **no hay dispositivo conectado**: todo se prueba con un *runner* falso.

Implementa `src/dogfood/drivers/android.py`:
1. `validar_destino(serial: str | None, host_puerto: str | None)`: acepta un serial USB, `127.0.0.1:<p>`/`localhost:<p>` o una IP de Tailscale (`100.64.0.0/10`) con puerto; rechaza cualquier otra dirección (LAN, pública, `0.0.0.0`) con un error que explica NFR-10.
2. `Adb(serial | host_puerto, runner=None)`: envuelve el binario con `asyncio.create_subprocess_exec` (sin shell; los textos para `input text` se escapan: espacios como `%s` y caracteres especiales del shell de Android escapados). El `runner(args: list[str], *, binario: bool) -> bytes` es inyectable. Si hay `host_puerto`, `conectar()` corre `adb connect` y verifica `get-state == device`.
3. `DriverAndroid(adb, paquete, actividad=None)` que cumple `Driver`:
   - `observar(n)`: `exec-out screencap -p` → `capturas/paso-NNN.png`; `shell uiautomator dump /sdcard/dogfood-ui.xml` + `exec-out cat` → `arboles/paso-NNN.xml`; parsea el XML (`node` con `resource-id`, `text`, `content-desc`, `class`, `bounds="[x1,y1][x2,y2]"`, `clickable`, `focusable` / `class` EditText para editable) a `ElementoUI`, descartando nodos sin texto, descripción ni id que no sean clicables; `pantalla` es la actividad de primer plano (`dumpsys activity activities` → `mResumedActivity`, o `dumpsys window` como respaldo). Si el dump falla o viene vacío, reintenta una vez y devuelve la observación con `elementos=[]` y la captura.
   - `actuar(accion)`: `tocar` (centro del elemento o x/y) → `input tap`; `escribir` → tap en el elemento si viene y `input text`; `deslizar` → `input swipe` con `ms`; `tecla`/`volver` → `input keyevent` (`KEYCODE_BACK` para volver); `abrir_app` → `monkey -p <paquete> -c android.intent.category.LAUNCHER 1` o `am start -n` si hay actividad; `cerrar_app` → `am force-stop`; `esperar` → `asyncio.sleep`. Devuelve `ResultadoAccion` con el `punto` tocado; un elemento inexistente da `ok=False` con el error.
   - `instalar(apk)` → `install -r`; `version_app()` → `versionName` de `dumpsys package <paquete>`.
   - `iniciar(carpeta)`: crea `capturas/`, `arboles/`, `video/`; limpia logcat (`logcat -c`) y arranca `screenrecord` en segmentos de 170 s (`/sdcard/dogfood-<n>.mp4`) en segundo plano.
   - `frame()`: `screencap -p` reducido a JPEG (Pillow, lado mayor ≤ 720 px, calidad 60); como mucho una captura por segundo (cachea la última).
   - `evidencia()`: detiene `screenrecord`, baja los segmentos con `pull` a `video/`, guarda `logcat -d` filtrado por el PID del paquete (`pidof`; si no hay PID, por `--pid` ausente filtra líneas del paquete) en `logcat.txt`, y devuelve `Evidencia` de tipo `log` (con un extracto de las últimas líneas con `E/` o `FATAL`) y la ruta del video.
   - `cerrar()`: detiene procesos pendientes sin lanzar si ya terminaron.

Deja en `tests/fixtures/android/` un `ui_dump.xml` realista (pantalla de login con campos email y contraseña, botón «Entrar» y un enlace «Esqueci minha senha») y una salida de `dumpsys` grabada.

Done when: estos tests pasan en `tests/test_driver_android.py`, con un runner falso que graba los argumentos y devuelve las fixtures:
- `observar` guarda captura y árbol y devuelve los elementos del login con sus bounds y la actividad;
- tocar «Entrar» por id manda `input tap` con el centro de sus bounds y devuelve ese punto;
- escribir un texto con espacios y `&` lo escapa para `input text`;
- `volver`, `abrir_app` y `cerrar_app` mandan `KEYCODE_BACK`, `monkey -p` y `am force-stop`;
- un dump vacío reintenta una vez y devuelve `elementos == []` con captura;
- `evidencia` guarda `logcat.txt` filtrado por el PID y devuelve el extracto con la línea `FATAL EXCEPTION`;
- `validar_destino` acepta un serial USB, `127.0.0.1:5555` y `100.101.102.103:5555`, y rechaza `192.168.0.10:5555`, `8.8.8.8:5555` y `0.0.0.0:5555`;
- `frame()` devuelve un JPEG de lado mayor ≤ 720 px y no llama dos veces a `screencap` dentro del mismo segundo.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Wrapper de un CLI con parsing de XML y bastantes casos borde; tier estándar con tests detallados.
- **Dependencies**: F6.1.T1
- **Files**:
  - `src/dogfood/drivers/android.py`
  - `tests/test_driver_android.py`
  - `tests/fixtures/android/ui_dump.xml`
  - `tests/fixtures/android/dumpsys_activity.txt`

## F6.4 — Package: driver web

### F6.4.T1 — Driver web sobre Playwright con screencast, video y trace

FR-28, FR-31 (frames) y FR-32 (video y trace). Implementa `src/dogfood/drivers/web.py` con `DriverWeb(url_inicial, permitida: Callable[[str], bool], viewport, movil=False)` que cumple `Driver`:
- `iniciar(carpeta)`: Chromium headless propio de Playwright (D2) con un contexto persistente limpio, `record_video_dir=carpeta/video`, `ctx.tracing.start(screenshots=True, snapshots=True)`, la misma lista blanca de URLs que `agente/navegador.py` (bloquea lo que `permitida` rechaza) y captura de consola y red (4xx/5xx y fallos) como `EventoConsola`/`EventoRed`. Abre una sesión CDP (`ctx.new_cdp_session(page)`) y arranca `Page.startScreencast` (JPEG, calidad 60, `maxWidth` 1024, `everyNthFrame` 2), guarda el último frame y responde `Page.screencastFrameAck`.
- `observar(n)`: captura `capturas/paso-NNN.png`, árbol de accesibilidad (`page.accessibility.snapshot()` o `locator("body").aria_snapshot()`, lo que exista en la versión instalada; léelo en el paquete) guardado en `arboles/paso-NNN.json`, y elementos interactivos con bounds (`page.evaluate` sobre botones, enlaces, inputs, selects y elementos con `role`, con un `data-dogfood-id` asignado para poder actuar por id); `pantalla` es la URL; `texto_visible` es `inner_text("body")`.
- `actuar(accion)`: `tocar` por id (`[data-dogfood-id=…]`) o coordenadas (`mouse.click`); `escribir` (`fill`); `tecla` (`keyboard.press`); `navegar` (solo URLs permitidas; si no, `ok=False`); `volver` (`go_back`); `deslizar` (`mouse.wheel`); `esperar`. Devuelve el `punto` del clic.
- `frame()`: último frame del screencast (bytes JPEG) sin capturar de nuevo.
- `evidencia()`: para el trace en `trace.zip`, cierra el contexto para que el video se escriba, y devuelve las `Evidencia` de consola y red y las rutas de video y trace.

Done when: estos tests pasan en `tests/test_driver_web.py`. Los de lógica pura usan objetos falsos (sin navegador): `actuar` traduce cada tipo de `Accion` a la llamada de Playwright correcta, `navegar` a una URL no permitida devuelve `ok=False` sin navegar, y el handler de `screencastFrame` guarda el frame y manda el ack. Un test con la marca `integracion` abre una página `file://` con un formulario en el Chromium real y comprueba observar (elementos con bounds), tocar, escribir, un frame JPEG no vacío y que `evidencia` deja `trace.zip` y un video; córrelo a mano con `uv run pytest -m integracion tests/test_driver_web.py` y deja el resultado en el PR.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Playwright y CDP con una interfaz ya fijada; tier estándar.
- **Dependencies**: F6.1.T1
- **Files**:
  - `src/dogfood/drivers/web.py`
  - `tests/test_driver_web.py`

## F6.5 — Package: bucle de agente

### F6.5.T1 — Bucle observar → decidir → actuar con cualquier driver y backend

FR-27, FR-28, FR-30 y la parte del agente de FR-31. Implementa `src/dogfood/agente/bucle.py` y `src/dogfood/agente/prompts_bucle.py`:

`async def ejecutar(persona, escenario, driver: Driver, backend: BackendLlm, juez: BackendLlm, carpeta, *, cfg, bus=BUS_NULO, corrida_id="", objetivo=None, timeout_s=15*60) -> Ejecucion`:
1. `driver.iniciar(carpeta)`; publica `EventoVivo(tipo="inicio")`.
2. Por paso: `observar(n)` → prompt con la persona (reusa `agente/prompts.sistema` y la tarea del escenario), el contrato del recorrido si existe, el historial corto (últimas 8 acciones con su resultado) y el árbol en texto (`arbol_a_texto`). Adjunta la captura reducida a `agente.resolucion_max` (Pillow, en un archivo aparte) solo si el árbol tiene menos de 3 elementos útiles o si la decisión anterior pidió captura (`pedir_captura`), con un máximo de `agente.max_capturas_por_paso` imágenes por paso (0 = nunca).
3. `backend.completar_json(prompt, DecisionPaso, imagenes=…, sesion=…)` (la sesión que devuelve el backend se reusa en el siguiente paso). `DecisionPaso` tal cual la interfaz de la arquitectura.
4. Si hay `friccion`, agrega una `Friccion` con la captura del paso; si hay `rendirse`, termina como `rendido`; si `terminado`, termina; si no, `driver.actuar(accion)`.
5. Registra un `Paso` con `url=pantalla`, captura, árbol, `accion` (JSON de la acción, con la contraseña de la persona reemplazada por `***`), `razonamiento`, `paso_contrato`, `esperado`, `observado` (resumen del resultado de la acción y de la pantalla siguiente) y `punto`; y publica `EventoVivo(tipo="paso")` con esos campos.
6. Mientras `bus.activo`, una tarea aparte llama `driver.frame()` cada 0,2 s si `driver.nombre == "web"` y cada 1 s si es `android`, y publica `EventoVivo(tipo="frame")` con el JPEG en base64; se cancela al terminar. Si `frame()` devuelve None, no publica.
7. Corta en `escenario.max_pasos` (`fallo`, `max_pasos`) o en `timeout_s` (`fallo`, `timeout`); una excepción del backend o del driver deja `estado="error"` con la nota, sin perder lo ya registrado.
8. Al final: `driver.evidencia()` → `evidencia_driver`, `video`, `trace`; `driver.cerrar()` siempre (finally). Si el estado es `ok`, el juez (`juez.completar_json` con el `Veredicto` de `agente/navegador.py` y el prompt de `prompts.juez`) decide `exito` y `motivo_juez`. Suma `metricas` con el `UsoBackend` de cada llamada (persona y juez). `e.resultado = contrato.resultado(e)`. Escribe `pasos.jsonl` como hace `navegador.py`. `e.driver`, `e.motor = "bucle"`, `e.backend = backend.nombre`, `e.modelo = backend.modelo`. Publica `EventoVivo(tipo="fin", resultado=…)`.

Done when: estos tests pasan en `tests/test_bucle.py` con un `DriverFalso` (pantallas guionadas, graba acciones, `frame()` devuelve bytes fijos) y un `BackendFalso` (decisiones guionadas, graba prompts e imágenes):
- un guion de login de 3 pasos termina `ok`, el juez lo aprueba y `resultado == "aprobado"`, con 3 `Paso` que llevan razonamiento, esperado, observado y captura;
- con `max_capturas_por_paso: 0` ningún prompt lleva imágenes; con 1 y un árbol vacío, el paso lleva una imagen de lado mayor ≤ `resolucion_max`;
- la contraseña de la persona nunca aparece en `Paso.accion` ni en los eventos publicados;
- una decisión `rendirse` termina `rendido` con el motivo; superar `max_pasos` termina `fallo`/`max_pasos`;
- una excepción del driver deja `estado="error"`, `resultado == "no_concluyente"` y `cerrar()` llamado;
- con un `BusVivo` activo se publican `inicio`, un `paso` por paso con su `paso_contrato`, al menos un `frame` y `fin`, en ese orden lógico; con `BUS_NULO` no se pide ningún frame;
- la sesión devuelta por el backend en el paso 1 se pasa en el paso 2;
- las métricas suman los tokens y capturas de todas las llamadas.

- **Modelo**: claude/claude-opus-5-5
- **Estimación**: 4h
- **Razón**: El bucle define la calidad del agente nuevo y el control de costo; diseño de prompt y de estados.
- **Dependencies**: F6.1.T1
- **Files**:
  - `src/dogfood/agente/bucle.py`
  - `src/dogfood/agente/prompts_bucle.py`
  - `tests/test_bucle.py`

## F6.6 — Package: objetivo Android

### F6.6.T1 — Objetivo Android genérico con escenario de login

NFR-9 y FR-29. Crea `src/dogfood/objetivos/android/__init__.py` con `AndroidObjetivo`, que cumple el protocolo `Objetivo` de `objetivos/base.py` como lo describe la arquitectura (*Componentes*, «Objetivo Android»), usando `Adb`, `validar_destino` y `DriverAndroid` de `drivers/android.py` (no los modifiques):
- `preparar(ref, corrida)`: lee `cfg.driver`, valida el destino, conecta (`adb connect` si es `host_puerto`), verifica `get-state`, instala `apk` si está configurado, y devuelve `Instancia(base_url=f"android://{paquete}", api_url="", proyecto_compose="", commit=ref, parametros={"serial"/"host_puerto", "paquete", "version_app"})`. Sin dispositivo, el error dice cómo conectarlo (USB o `adb pair`/`adb connect` sobre Tailscale) y remite a `docs/ops/android.md`.
- `destruir`: `am force-stop` y `pm clear <paquete>` (nunca desinstala).
- `url_permitida`: solo `android://<paquete>…`; `pantalla(url)`: la actividad sin el paquete; `logs`: `{"logcat": …}`; `verificadores()`: `[]`; `escenarios()`: los YAML de `objetivos/android/escenarios/`.
- Un escenario `objetivos/android/escenarios/login.yaml` con `driver: android`, `superficies: [login]`, `contrato` completo (estado inicial «app recién abierta sin sesión», acciones, resultado esperado «se ve la pantalla principal con la sesión iniciada», evidencia requerida «captura del paso final y árbol de UI») y `criterio_exito` observable.
- Registra `"android": "dogfood.objetivos.android:AndroidObjetivo"` en `OBJETIVOS` de `src/dogfood/objetivos/__init__.py` (única línea que cambia en ese archivo).

Done when: estos tests pasan en `tests/test_objetivo_android.py` con un runner de adb falso:
- `cargar_objetivo("android")` devuelve un `AndroidObjetivo`;
- `preparar` con un dispositivo falso en estado `device` devuelve la instancia con `version_app` leída de `dumpsys package`, e instala el apk solo si está configurado;
- sin dispositivo, `preparar` falla con el mensaje que menciona `docs/ops/android.md`;
- un `host_puerto` de LAN es rechazado antes de llamar a `adb`;
- `url_permitida` acepta `android://<paquete>` y rechaza otro paquete y cualquier `http://`;
- `escenarios()` carga el login con su contrato y `driver == "android"`;
- `destruir` manda `force-stop` y `pm clear` y nunca `uninstall`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 2h
- **Razón**: Adaptador acotado sobre piezas ya hechas.
- **Dependencies**: F6.3.T1
- **Files**:
  - `src/dogfood/objetivos/android/__init__.py`
  - `src/dogfood/objetivos/android/escenarios/login.yaml`
  - `src/dogfood/objetivos/__init__.py`
  - `tests/test_objetivo_android.py`

## F6.7 — Package: integración en la corrida

### F6.7.T1 — Corrida con motor, driver y backend elegibles, contrato y métricas

FR-26 a FR-30 de punta a punta en `dogfood run`.
1. `src/dogfood/corrida.py`: `Opciones` suma `driver: str | None`, `motor: str | None` y `bus: BusVivo = BUS_NULO`. Por ejecución se decide el motor: si el escenario o la opción dicen `driver: android`, o `motor: bucle`, se usa `agente.bucle.ejecutar` con `DriverAndroid` (desde `cfg.driver` y la instancia del objetivo) o `DriverWeb` (con `objetivo.url_permitida`), `backend_para("persona", …)` y `backend_para("juez", …)`; si no, `agente.navegador.ejecutar` como hasta ahora (browser-use sigue siendo el motor web por defecto y con backend `api`; si `motores.persona == "claude_code"` y el motor es `browser_use`, se usa el bucle con `DriverWeb`, porque browser-use necesita un cliente de chat por API — anótalo en un log informativo). Cada `Ejecucion` sale con `resultado = contrato.resultado(e)`, y la corrida guarda `version_app` del objetivo (`instancia.parametros.get("version_app")` o el commit). Los `UsoBackend` del bucle se registran en el `ContadorUso` con `backend` y `costo_equivalente_usd`.
2. `src/dogfood/comandos/run.py`: opciones `--driver web|android` y `--motor browser_use|bucle`, pasadas a `Opciones`.
3. `src/dogfood/agente/navegador.py` (motor browser-use): acepta `bus: BusVivo = BUS_NULO` y `corrida_id`; graba video (`record_video_dir=carpeta/video`) y trace (`ctx.tracing` → `trace.zip`) y los deja en `e.video`/`e.trace`; en `al_terminar_paso` copia a `Paso.razonamiento` y `Paso.paso_contrato` lo que browser-use expone del modelo (`current_state`/`thinking`, `next_goal`, `evaluation_previous_goal`, según la versión instalada; léelo en el paquete), y publica `EventoVivo(tipo="paso")`; si el bus está activo, arranca `Page.startScreencast` por CDP en la página activa y publica cada frame (`tipo="frame"`) con ack, sin bloquear; publica `inicio` y `fin`; al terminar, `e.resultado = contrato.resultado(e)` y `e.metricas` con los tokens del `token_cost_service`. El comportamiento actual (capturas, red, consola, juez, historial) no cambia.

Done when: estos tests pasan en `tests/test_corrida_motores.py` (con objetivo, drivers, backends y juez falsos, como hacen los tests de corrida existentes) y los tests de `tests/test_agente_navegador.py` y `tests/test_corrida*.py` siguen verdes:
- `--driver android` (o un escenario con `driver: android`) corre por el bucle con el driver Android falso y la ejecución queda con `driver == "android"` y `motor == "bucle"`;
- con `motores.persona: claude_code` el bucle recibe un backend `claude_code` y la corrida guarda el uso con `backend == "claude_code"`, `costo_usd == 0` y `costo_equivalente_usd > 0`;
- sin opciones nuevas la corrida sigue usando `navegador.ejecutar`;
- toda ejecución guardada en el almacén tiene `resultado`, y una sin capturas queda `no_concluyente`;
- `version_app` de la instancia llega a la corrida guardada;
- `dogfood run --help` muestra `--driver` y `--motor`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Cableado entre piezas ya probadas en archivos que ya existen; tier estándar.
- **Dependencies**: F6.2.T1, F6.3.T1, F6.4.T1, F6.5.T1, F6.6.T1
- **Files**:
  - `src/dogfood/corrida.py`
  - `src/dogfood/comandos/run.py`
  - `src/dogfood/agente/navegador.py`
  - `tests/test_corrida_motores.py`

## F6.8 — Package: operación

### F6.8.T1 — Guías de operación: Android sobre Tailscale y Claude Code

Documentación, sin código. Escribe en español:
- `docs/ops/android.md`: preparar un Android real (opciones de desarrollador, depuración USB e inalámbrica), conectarlo por USB o por **ADB inalámbrico sobre Tailscale** (`adb pair` y `adb connect <ip-tailscale>:<puerto>`, el teléfono con la app de Tailscale), por qué nunca exponer ADB fuera de USB, localhost o Tailscale (NFR-10) y qué valida `validar_destino`; la configuración `driver:` de `dogfood.yaml`; el comando para correr el escenario de login (`dogfood run --target android --driver android --escenarios login`); una **lista de verificación manual pendiente** con los criterios del issue #32 que requieren dispositivo (login de punta a punta por Tailscale; captura + árbol + acción por paso en `runs/`; fallo → issue con pasos, capturas, logcat y gravedad; sin evidencia → no concluyente); y cómo medir el spike de la opción B (Appium + UIAutomator2 o `mobile-mcp`): tiempo por paso y tasa de esperas fallidas en el mismo escenario, con el umbral para cambiar (D18).
- `docs/ops/claude-code.md`: usar el plan Max como motor (`motores:` y `claude_code:` en `dogfood.yaml`), cómo verificar la sesión (`claude -p "di ok" --output-format json`), qué hace el backend cuando no hay sesión, qué opciones pasa a `claude -p` y por qué corre fuera del repo, `--mcp-config` opcional, cómo leer `costo_usd` frente a `costo_equivalente_usd`, y cómo comparar el mismo escenario con `api` y con `claude_code` (dos corridas con la misma semilla y el panel).

Lee `src/dogfood/drivers/android.py`, `src/dogfood/backends/claude_code.py` y `src/dogfood/config.py` para que los nombres de opciones y comandos sean los reales. No hay tests que escribir: la tarea termina cuando los dos documentos existen, citan opciones que existen en el código y `uv run pytest` sigue verde.

- **Modelo**: claude/claude-haiku-5-5
- **Estimación**: 1h
- **Razón**: Documentación a partir de código ya escrito.
- **Dependencies**: F6.2.T1, F6.3.T1
- **Files**:
  - `docs/ops/android.md`
  - `docs/ops/claude-code.md`
