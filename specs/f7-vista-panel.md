---
type: spec
project_id: dogfood
phase: 7
version: 0.1
depends_on:
  - docs/prd/001-usuarios-agenticos.md
  - docs/arch/001-usuarios-agenticos.md
  - specs/f6-motores-android.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-29
title: Vista en vivo y panel de corridas
---

# F7 — Vista en vivo y panel de corridas

M7 del PRD (v0.3): ver en vivo lo que hace cada usuario agéntico (pantalla en streaming, acción marcada y razonamiento con el paso del contrato) y revisar después cada corrida en un panel estilo TestSprite (recorridos con contrato, resultados aprobado / falló / no concluyente, paso a paso con evidencia, video, costo en tokens y «Crear issue»). FR-31 a FR-33, NFR-10 y NFR-11; issues #33 y #34 de hectorcanaimero/dogfood.

Contexto común para todas las tareas de esta fase:
- Lee `CONTEXTO.md`, el PRD `docs/prd/001-usuarios-agenticos.md` (FR-31 a FR-33) y la arquitectura `docs/arch/001-usuarios-agenticos.md`: *Componentes* («Web local», «Contrato y eventos»), *Interfaces* («Contrato y eventos», «HTTP local», «CLI» v0.2) y decisiones D19 a D21.
- Stack: FastAPI + Jinja2 + JavaScript propio sin build (D20). Las dependencias (`fastapi`, `uvicorn[standard]`) ya están en `pyproject.toml` desde F6.1.T1: no edites `pyproject.toml` ni `uv.lock`. No uses CDN: todo lo estático se sirve desde el paquete.
- Estilo: el del dashboard de orch («Mesa de despacho»): los tokens de color están en la arquitectura y la fuente de referencia es `/mnt/storage/project/orch/web/src/index.css` (léela; no la copies entera).
- Vista y panel escuchan en `127.0.0.1` por defecto y solo aceptan una IP de Tailscale (`100.64.0.0/10`) como alternativa; nunca `0.0.0.0` (NFR-10). Sin auth: no hay exposición pública.
- Textos de la interfaz en español. Tests con `fastapi.testclient.TestClient`; nada de red externa. `uv run pytest` y `uv run ruff check . && uv run ruff format --check .` deben pasar.

## F7.1 — Package: base web

### F7.1.T1 — Base web compartida: app, validación de host y estilo de orch

Crea `src/dogfood/web/`:
- `web/__init__.py`: `validar_host(host: str) -> str` (acepta `127.0.0.1`, `localhost`, `::1` y direcciones de `100.64.0.0/10`; cualquier otra, incluida `0.0.0.0`, lanza `ValueError` explicando NFR-10); `crear_app_base(titulo: str, plantillas_extra: Path | None = None) -> tuple[FastAPI, Jinja2Templates]` que monta `/estatico` con los archivos de `web/estatico/` y un cargador Jinja2 que busca primero en `plantillas_extra` y luego en `web/plantillas/`; filtros Jinja comunes `duracion` (s → «1 min 05 s»), `usd` (4 decimales) y `fecha`; `servir(app, host, puerto)` que valida el host y arranca uvicorn.
- `web/plantillas/base.html`: esqueleto con barra lateral (enlaces «Corridas», «Recorridos», «En vivo»), conmutador claro/oscuro (clase `dark` en `<html>`, guardado en `localStorage`), y bloques `titulo` y `contenido`.
- `web/estatico/dogfood.css`: los tokens de orch como variables CSS en `:root` y `.dark` (fondo, tarjeta, borde, texto atenuado, marca `#5a43db`, estados `--estado-aprobado` `#1e8a4c`, `--estado-fallo` `#d1343a`, `--estado-no-concluyente` `#b86e0b`, `--estado-en-curso` `#2f6bd6`), tipografía de sistema, tablas densas, insignias de resultado (`.res-aprobado`, `.res-fallo`, `.res-no_concluyente` con ✅ ❌ ⚠️), tarjetas, grilla, y foco visible.

Done when: estos tests pasan en `tests/test_web_base.py`:
- `validar_host` acepta `127.0.0.1`, `localhost` y `100.100.1.2`, y rechaza `0.0.0.0`, `192.168.1.5` y `8.8.8.8`;
- una app de `crear_app_base` sirve `/estatico/dogfood.css` con los tokens `--estado-aprobado` y `.dark`;
- una plantilla que extiende `base.html` se renderiza con la barra lateral y el conmutador de tema;
- los filtros `duracion` y `usd` dan «1 min 05 s» para 65 y «0.0123» para 0.01234.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 2h
- **Razón**: Base visual y de seguridad compartida por dos apps; tier estándar.
- **Dependencies**: F6.1.T1
- **Files**:
  - `src/dogfood/web/__init__.py`
  - `src/dogfood/web/plantillas/base.html`
  - `src/dogfood/web/estatico/dogfood.css`
  - `tests/test_web_base.py`

## F7.2 — Package: vista en vivo

### F7.2.T1 — Servidor y página de la vista en vivo

Issue #33, FR-31, NFR-11, D19. Crea `src/dogfood/vista/`:
- `vista/__init__.py` y `vista/servidor.py`: `crear_app_vista(bus: BusVivo) -> FastAPI` sobre `crear_app_base`, con `GET /` (página `vista.html`) y el WebSocket `GET /ws`, que suscribe al bus (cola acotada) y manda cada `EventoVivo` como JSON; al conectarse recibe primero el último `inicio`, el último `paso` y el último `frame` de cada ejecución activa (el servidor guarda ese estado), para que una pestaña abierta tarde vea algo enseguida. Un cliente lento pierde frames viejos, nunca frena al bus ni a otros clientes. `async def iniciar_vista(bus, host, puerto) -> asyncio.Task` arranca uvicorn (`uvicorn.Server` con `config.install_signal_handlers` apagado) en el loop actual, tras `validar_host`, y devuelve la tarea para cancelarla al final.
- `vista/plantillas/vista.html` y `vista/estatico/vista.js`: grilla de tarjetas, una por ejecución (persona, escenario, driver, paso actual, resultado al final); cada tarjeta tiene un `<canvas>` donde se dibuja el último frame (JPEG base64), un círculo sobre el `punto` de la última acción que se desvanece en 1 s, y una columna de razonamiento con los últimos pasos («paso del contrato → acción → razonamiento»), el más nuevo arriba. Clic en una tarjeta la amplía; Escape vuelve a la grilla. Reconexión automática del WebSocket. Muestra la latencia (ahora − `ts` del último frame) en cada tarjeta.

Done when: estos tests pasan en `tests/test_vista.py`:
- `GET /` responde 200 con el canvas y la columna de razonamiento;
- un evento publicado en el bus llega al cliente del WebSocket (TestClient) en menos de 1 s;
- un cliente que se conecta tarde recibe primero el último `paso` y el último `frame` de cada ejecución activa;
- tres ejecuciones publicando a la vez llegan con su `ejecucion_id` y ningún evento de una aparece en otra;
- con un suscriptor que no lee, publicar 1000 frames no bloquea y tarda menos de 0,5 s en total;
- `iniciar_vista` con host `0.0.0.0` falla antes de abrir el puerto.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: WebSocket, asyncio y una página interactiva; tier estándar con tests de latencia.
- **Dependencies**: F7.1.T1
- **Files**:
  - `src/dogfood/vista/__init__.py`
  - `src/dogfood/vista/servidor.py`
  - `src/dogfood/vista/plantillas/vista.html`
  - `src/dogfood/vista/estatico/vista.js`
  - `tests/test_vista.py`

## F7.3 — Package: vista en la corrida

### F7.3.T1 — `dogfood run --vista`

FR-31 de punta a punta. En `src/dogfood/corrida.py`, si `Opciones.vista` es verdadero, crea un `BusVivo`, arranca `iniciar_vista(bus, cfg.vista.host, puerto)` antes de las ejecuciones, pasa el bus (y el id de la corrida) a `navegador.ejecutar` y a `bucle.ejecutar`, imprime en el log la URL (`http://127.0.0.1:7460/`) y, al terminar la corrida, deja la vista 5 s más para que se vea el resultado final y cancela la tarea. Si el puerto está ocupado, avisa en el log y sigue sin vista (la corrida nunca falla por la vista). En `src/dogfood/comandos/run.py`, agrega `--vista` y `--vista-puerto` (por defecto el de la config).

Mide el costo de la vista: un test con 3 ejecuciones falsas que publican pasos y frames compara la duración con y sin vista (con un cliente WebSocket conectado) y exige que la diferencia sea menor al 10 % más 0,5 s.

Done when: estos tests pasan en `tests/test_corrida_vista.py` con objetivo, drivers y LLM falsos:
- sin `--vista` el bus es `BUS_NULO` y no se abre ningún puerto;
- con `--vista` las ejecuciones reciben el mismo bus activo y un cliente WebSocket ve `inicio`, `paso` y `fin` de cada una;
- un puerto ocupado no hace fallar la corrida y deja un aviso en el log;
- 3 ejecuciones simultáneas con vista tardan como mucho un 10 % (+0,5 s) más que sin vista;
- `dogfood run --help` muestra `--vista` y `--vista-puerto`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 2h
- **Razón**: Cableado acotado en archivos ya conocidos.
- **Dependencies**: F7.2.T1, F6.7.T1
- **Files**:
  - `src/dogfood/corrida.py`
  - `src/dogfood/comandos/run.py`
  - `tests/test_corrida_vista.py`

## F7.4 — Package: panel, listas y filtros

### F7.4.T1 — Panel: ejecuciones con filtros, recorridos y comparación de motores

Issue #34 (FR-32) y la comparación de FR-26. Crea `src/dogfood/panel/`:
- `panel/consultas.py`: lectura de solo consulta sobre `runs/dogfood.db` (esquema v2 de F6.1.T1) y las carpetas de corrida: `ejecuciones(filtros) -> list[FilaEjecucion]` (corrida, fecha, versión de la app o commit, persona con nombre e idioma desde `personas`, escenario, driver, motor, backend, modelo, resultado, duración, pasos, tokens, capturas, costo y costo equivalente), con filtros por `recorrido`, `resultado`, `version`, `persona`, `driver` y `motor`, y los valores posibles de cada filtro; `corrida(id)` con su resumen; `comparacion_motores(corrida_id)` agrupada por motor + backend + modelo (ejecuciones, aprobadas, fallidas, no concluyentes, tasa de aprobación, tokens, costo y costo equivalente por ejecución); `recorridos(objetivo)` con los escenarios del objetivo y su `contrato` (estado inicial, acciones, resultado esperado, evidencia requerida) y, por escenario, cuántas ejecuciones hay de cada resultado. Abre SQLite en modo solo lectura (`mode=ro`).
- `panel/app.py`: `crear_app_panel(raiz: Path) -> FastAPI` sobre `crear_app_base`, con `GET /` (tabla de ejecuciones con formulario de filtros por GET y enlaces al detalle `/ejecuciones/{id}`), `GET /recorridos` y `GET /corridas/{id}` (resumen + tabla de comparación de motores). Expone una función `registrar_rutas(app, templates, raiz)` por módulo para que F7.5 sume sus rutas.
- `panel/plantillas/corridas.html`, `panel/plantillas/recorridos.html`, `panel/plantillas/corrida.html`, extendiendo `base.html`, con las insignias de resultado ✅ aprobado / ❌ falló / ⚠️ no concluyente.
- `src/dogfood/comandos/panel.py`: `dogfood panel [--host] [--puerto] [--raiz runs]` (por defecto los de `cfg.panel`), que valida el host y llama `servir`. El autodescubrimiento de `cli.py` lo registra solo: no edites `cli.py`.

Done when: estos tests pasan en `tests/test_panel.py`, con un almacén armado en `tmp_path` con dos corridas (una con motor `browser_use`/`api` y otra con `bucle`/`claude_code`, ejecuciones aprobadas, fallidas y no concluyentes, en web y Android):
- `GET /` lista todas las ejecuciones con su insignia de resultado y su costo;
- cada filtro (`recorrido`, `resultado`, `version`, `persona`, `driver`, `motor`) reduce la tabla a lo esperado y se combinan entre sí;
- `GET /recorridos` muestra el contrato de cada escenario y los conteos por resultado;
- `GET /corridas/{id}` muestra la comparación de motores con tasa de aprobación, tokens, costo y costo equivalente correctos;
- una corrida inexistente da 404;
- el panel no escribe en la base (el archivo no cambia tras las peticiones);
- `dogfood panel --host 0.0.0.0` termina con error sin abrir el puerto, y `dogfood --help` lista `panel`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Consultas y plantillas server-rendered; tier estándar.
- **Dependencies**: F7.1.T1
- **Files**:
  - `src/dogfood/panel/__init__.py`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/panel/consultas.py`
  - `src/dogfood/panel/plantillas/corridas.html`
  - `src/dogfood/panel/plantillas/recorridos.html`
  - `src/dogfood/panel/plantillas/corrida.html`
  - `src/dogfood/comandos/panel.py`
  - `tests/test_panel.py`

## F7.5 — Package: panel, detalle y crear issue

### F7.5.T1 — Panel: paso a paso con evidencia, video y «Crear issue»

Issue #34 (FR-32 y FR-33).
- `src/dogfood/panel/detalle.py`: `GET /ejecuciones/{id}` lee `pasos.jsonl`, `red.jsonl`, `consola.jsonl`, `logcat.txt`, las fricciones y la ejecución guardada; muestra una línea de tiempo de pasos y, por paso, la captura, la acción, el razonamiento, el paso del contrato, esperado contra observado, y la consola/red (web) o el extracto de logcat (Android) de ese momento; botones «anterior/siguiente» y teclas ← →; el video de la ejecución en `<video>` (webm o mp4), el enlace para descargar `trace.zip` (web) con la indicación de abrirlo con `uv run playwright show-trace`, y la opinión de la persona: sus fricciones agrupadas por pantalla con cita y captura. `GET /archivos/{ruta:path}` sirve solo archivos dentro de `raiz` (resuelve la ruta y rechaza `..`, enlaces simbólicos fuera de `raiz` y rutas absolutas con 404).
- `src/dogfood/panel/issue.py`: `armar_issue(ejecucion, persona, corrida) -> tuple[str, str]` (título y cuerpo) con el formato de *Issue publicado* de la arquitectura: pasos numerados, esperado/observado del paso que falló, rutas locales de capturas y del video, extractos de consola, red o logcat, comando de replay y el comentario oculto con la huella; todo el texto pasa por `redactar(texto, secretos_conocidos)` de `reporte/redactar.py` y además se reemplazan el email, la contraseña y el nombre de la empresa de la persona, y cualquier valor de los secretos de `Config`. `publicar_issue(...)` construye un `Hallazgo` (tipo y gravedad elegidos en el formulario, por defecto `tecnico`/`media`; pantalla del paso que falló; pasos, evidencia, esperado y obtenido) y llama a `publicar([hallazgo], corrida, cfg, secretos=[persona.contrasena, …])` de `reporte/issues.py` (con su deduplicación por huella) sin modificar ese archivo; `POST /ejecuciones/{id}/issue` la llama y responde la URL, que la página muestra como enlace. El repo es `cfg.repo_issues`.
- `src/dogfood/panel/app.py`: registra las rutas de `detalle.py` (solo esa línea cambia en el archivo).
- `src/dogfood/panel/plantillas/ejecucion.html`.

Done when: estos tests pasan en `tests/test_panel_detalle.py`, con el almacén de prueba de `tests/test_panel.py` (o uno equivalente propio) y la publicación de `gh` reemplazada por un falso que graba título y cuerpo:
- `GET /ejecuciones/{id}` muestra cada paso con su captura, acción, razonamiento y esperado contra observado, el `<video>` y el enlace a `trace.zip` en web, y el extracto de logcat en Android;
- las fricciones aparecen agrupadas por pantalla;
- `GET /archivos/` sirve una captura de `runs/` y responde 404 para `../dogfood.db` fuera de la raíz, rutas absolutas y un enlace simbólico que sale de la raíz;
- `POST /ejecuciones/{id}/issue` devuelve la URL del issue falso; el cuerpo grabado tiene los pasos, la ruta del video, el comando de replay y la huella, y no contiene el email, la contraseña ni la empresa de la persona, ni un token de prueba sembrado en la consola;
- una segunda llamada con la misma huella comenta en vez de crear (deduplicación de FR-18).

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Pantalla de detalle y publicación con redacción; tier estándar con tests de seguridad.
- **Dependencies**: F7.4.T1
- **Files**:
  - `src/dogfood/panel/detalle.py`
  - `src/dogfood/panel/issue.py`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/panel/plantillas/ejecucion.html`
  - `tests/test_panel_detalle.py`

## F7.9 — Package: integración M7

### F7.9.T1 — Integración M7: panel y vista en un navegador real

Cierra M7 con pruebas en un Chromium real (Playwright, ya instalado) y la guía de uso.
- `tests/integracion/test_panel_vista.py` (marca `integracion`): (1) arma un almacén de prueba con una corrida web y una Android falsas (capturas PNG, video pequeño, `pasos.jsonl`), levanta `dogfood panel` en un puerto libre de `127.0.0.1`, y con Playwright filtra por resultado, entra al detalle, navega pasos con ← →, comprueba que el `<video>` carga y que «Crear issue» (con `gh` falso) muestra la URL; (2) levanta la vista con un bus y un publicador falso de 3 ejecuciones, abre la página y comprueba que las tres tarjetas dibujan frames, que el razonamiento cambia con cada paso y que la latencia mostrada es menor a 1 s; (3) si hay sesión de Claude Code y un Chromium, corre `dogfood run --motor bucle` con `motores.persona: claude_code` contra una página `file://` de login de prueba y verifica que la ejecución queda guardada con `backend == "claude_code"` y se ve en el panel; si no hay sesión, se salta con el motivo.
- Córrelos con `uv run pytest -m integracion tests/integracion/test_panel_vista.py` y pega la salida en el PR. Todo número que reportes sale de esa corrida.
- `docs/ops/panel-y-vista.md`: cómo abrir la vista (`dogfood run --vista`) y el panel (`dogfood panel`), puertos por defecto, cómo verlos desde otra máquina por Tailscale sin exponerlos (`--host <ip-tailscale>` o un túnel SSH), qué significa cada resultado y cómo se calcula (contrato de FR-30), cómo leer la comparación de motores y cómo crear un issue desde el panel.

Done when: los tres escenarios de `tests/integracion/test_panel_vista.py` pasan a mano en el server (el tercero puede saltarse solo si no hay sesión de Claude Code, y el PR lo dice), `uv run pytest` (sin integración) sigue verde y la guía existe con comandos que funcionan.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Exploración en navegador real y specs estables.
- **Dependencies**: F7.3.T1, F7.5.T1
- **Files**:
  - `tests/integracion/test_panel_vista.py`
  - `docs/ops/panel-y-vista.md`
