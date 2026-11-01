---
type: spec
project_id: dogfood
phase: 8
version: 0.1
depends_on:
  - docs/prd/001-usuarios-agenticos.md
  - docs/arch/001-usuarios-agenticos.md
  - specs/f6-motores-android.md
  - specs/f7-vista-panel.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-11-01
title: Flutter en celular real
---

# F8 — Flutter en celular real

M8 del PRD (v0.4): las apps Flutter de Héctor se prueban en celulares reales. Android por ADB sobre Tailscale; detección de Flutter con cobertura de Semantics y hallazgo de pantalla «ciega» con respaldo por visión; motor determinista Patrol / `integration_test` para recorridos críticos (login, pago); la pantalla real del celular en la vista en vivo y en el panel mediante una interfaz común de fuente de frames; un nodo iOS en el Mac M1 de Héctor al que guria manda trabajos por SSH; y un filtro web barato con la app compilada a web. FR-34 a FR-39, NFR-12 y NFR-13; issue #32 de hectorcanaimero/dogfood (hoy Guria-Studio/dogfood).

Contexto común para todas las tareas de esta fase:
- Lee `CONTEXTO.md`, el PRD `docs/prd/001-usuarios-agenticos.md` (sección «Flutter en celular real», FR-34 a FR-39, NFR-12 y NFR-13) y la arquitectura `docs/arch/001-usuarios-agenticos.md`: *Componentes* (bloques «v0.3»), *Modelo de datos* («Cambios v0.3»), *Interfaces* (bloques «v0.3») y decisiones D23 a D31. Las firmas de las *Interfaces* son el contrato: impleméntalas tal cual.
- Código, comentarios, docstrings y mensajes en español. Python 3.13 con uv; `uv run pytest` y `uv run ruff check . && uv run ruff format --check .` deben pasar antes de terminar. No hay dependencias nuevas: no edites `pyproject.toml` ni `uv.lock` (`httpx`, `Pillow`, `fastapi` y `playwright` ya están).
- **No hay celular conectado, ni KVM, ni Mac en CI** (NFR-13). Ningún test llama a `adb`, `flutter`, `patrol`, `ssh`, `rsync`, `ffmpeg`, `xcrun` ni Appium reales: usa *runners* inyectables con salidas grabadas, `httpx.MockTransport` o scripts falsos en un directorio temporal antepuesto al `PATH`. Lo que necesite hardware o el SDK real va con la marca `integracion` (excluida por defecto).
- El SDK de Flutter está en `/mnt/storage/flutter` (`/mnt/storage/flutter/bin/flutter`, `PUB_CACHE=/mnt/storage/flutter/.pub-cache`, `patrol` en `/mnt/storage/flutter/.pub-cache/bin/patrol` si está activado). Nunca instales nada en el home ni en el repo.
- Las apps de referencia `/mnt/storage/rupies/apps/mobile-mao` (paquete `br.com.rupies.profissional`) y `/mnt/storage/rupies/apps/mobile-empresa` (`br.com.rupies.empresa`) son **solo lectura**: puedes leerlas para entender cómo es una app Flutter real, pero nunca escribas en ellas; dogfood trabaja sobre copias en `flutter.copia_trabajo`.
- Sin secretos en el repo ni en los logs (NFR-3, NFR-12): el código de emparejamiento de ADB, las credenciales de prueba, las claves SSH y los certificados de Apple nunca se escriben a disco ni se imprimen. ADB, Appium, el MJPEG de WebDriverAgent y el SSH del nodo solo por loopback o Tailscale (`100.64.0.0/10`); nunca `0.0.0.0` ni una IP de LAN o pública.
- Los tests existentes (F0–F7) deben seguir pasando sin cambios, salvo que el brief diga lo contrario.

## F8.1 — Package: contratos v0.3

### F8.1.T1 — Contratos v0.3: dominio, config, fuentes de frames, protocolo del nodo y registros

Esqueleto de la fase: deja fijos los contratos y los archivos compartidos para que F8.2–F8.7 trabajen en paralelo sin tocar los mismos archivos. Implementa exactamente las *Interfaces* «v0.3» de la arquitectura.

1. `src/dogfood/dominio.py`: `Plataforma = Literal["web", "android", "ios"]`; `TipoHallazgo.accesibilidad`; `PasoDeterministico`, `RecorridoDeterministico` y `CoberturaSemantica`; en `Escenario`, `driver: Plataforma`, `motor` (`browser_use` | `bucle` | `patrol` | `integration_test` | None) y `deterministico`; en `Ejecucion`, `driver: Plataforma`. Todo con valores por defecto: los YAML y JSON viejos siguen cargando. No hace falta migrar SQLite (las columnas son `TEXT`); compruébalo con un test.
2. `src/dogfood/drivers/base.py`: `Observacion.cobertura: CoberturaSemantica | None = None`.
3. `src/dogfood/config.py` y `dogfood.example.yaml`: `Driver.tipo` admite `ios` y suma `nodo`, `udid`, `bundle_id`; bloques nuevos `pantalla` (`android`: `screencap` | `screenrecord`, `fps`), `flutter` (`sdk`, `patrol`, `pub_cache`, `proyecto`, `copia_trabajo` (por defecto `/mnt/storage/cache/dogfood/flutter`, con `~` expandido si se usa), `umbral_cobertura`, `timeout_s`), `flutter_web` (`build_dir`, `host`, `puerto` 7480, `api_permitidas`, `dart_defines`) y `nodos: dict[str, Nodo]` (`host`, `usuario`, `puerto_ssh`, `comando`, `dir_trabajo`, `proyectos`), con los valores por defecto de la arquitectura. `Nodo.host` y `flutter_web.host` se validan al cargar: solo loopback o Tailscale (reusa `validar_host` de `dogfood.web`). Un `dogfood.yaml` viejo sin esos bloques sigue cargando.
4. `src/dogfood/drivers/android.py`: solo agrega el parámetro `grabar_video: bool = True` a `DriverAndroid`; con `False`, `iniciar` no lanza `screenrecord` y `evidencia` no baja segmentos. Nada más cambia en ese archivo.
5. `src/dogfood/frames/__init__.py` y `src/dogfood/frames/base.py`: el protocolo `FuenteFrames`, `FuenteDeDriver` (envuelve `driver.frame()`; `intervalo_s` 0,2 en web, 1,0 en Android e iOS si no se pasa) y `validar_url_local(url)`. En `__init__.py`, `crear_fuente(cfg, driver, parametros)` devuelve por ahora siempre `FuenteDeDriver(driver)`; F8.4.T1 la completa.
6. `src/dogfood/nodos/__init__.py` y `src/dogfood/nodos/protocolo.py`: `Trabajo`, `EstadoNodo` y `ResultadoTrabajo`. Como `ResultadoTrabajo.deterministico` usa `ResultadoDeterministico`, crea también `src/dogfood/deterministico/__init__.py` con los modelos `ResultadoTest` y `ResultadoDeterministico` (incluido su método `resultado()` con la regla de la arquitectura) y el alias `Herramienta`; el corredor y el generador los agregan F8.5.T1 y F8.5.T2 en sus propios módulos.
7. `src/dogfood/flutter/__init__.py` vacío (paquete); `src/dogfood/deteccion/flutter.py` como stub `detectar(ctx) -> list[Hallazgo]` que devuelve `[]`, registrado en `DETECTORES` de `deteccion/__init__.py` (única línea que cambia ahí).
8. `src/dogfood/objetivos/__init__.py`: registra `"ios": "dogfood.objetivos.ios:IosObjetivo"` y `"flutter_web": "dogfood.objetivos.flutter_web:FlutterWebObjetivo"`. Crea `src/dogfood/objetivos/ios/__init__.py` y `src/dogfood/objetivos/flutter_web/__init__.py` con clases stub que cumplen el protocolo `Objetivo` (`nombre` correcto, `escenarios()` devuelve `[]`, y `preparar` lanza `NotImplementedError` con un texto que dice qué tarea lo implementa); F8.6.T4 y F8.7.T1 los reemplazan.

Done when: estos tests pasan en `tests/test_contratos_f8.py` y los tests existentes siguen verdes:
- un escenario YAML sin `motor` ni `deterministico` carga igual que antes, y uno con `driver: ios`, `motor: integration_test` y pasos deterministas carga con sus campos;
- `Ejecucion(driver="ios", motor="patrol")` se guarda en el almacén y se vuelve a leer;
- `ResultadoDeterministico.resultado()` da `aprobado` con código 0 y todos los tests ok, `fallo` con un test en fallo, y `no_concluyente` con timeout (`codigo_salida=None`), cero tests o `motivo="compilacion"`;
- `Config.cargar` con un yaml viejo da `pantalla.android == "screencap"`, `flutter.umbral_cobertura == 0.6` y `nodos == {}`; un nodo con host `192.168.1.10` hace fallar la carga;
- `validar_url_local` acepta `http://127.0.0.1:9100` y `http://100.101.102.103:4723`, y rechaza `http://192.168.0.5:9100`, `http://0.0.0.0:9100` y `ftp://127.0.0.1`;
- `FuenteDeDriver` devuelve lo que da `driver.frame()` y `crear_fuente` devuelve una `FuenteDeDriver`;
- `Trabajo` y `ResultadoTrabajo` hacen ida y vuelta por JSON;
- `cargar_objetivo("ios")` y `cargar_objetivo("flutter_web")` devuelven sus stubs; `DETECTORES` incluye el detector de Flutter;
- `DriverAndroid(..., grabar_video=False)` no manda `screenrecord` al iniciar (runner falso).

- **Modelo**: claude/claude-opus-5-5
- **Estimación**: 4h
- **Razón**: Fija los contratos de toda la fase; un error aquí se arrastra a seis paquetes paralelos.
- **Dependencies**:
- **Files**:
  - `src/dogfood/dominio.py`
  - `src/dogfood/drivers/base.py`
  - `src/dogfood/drivers/android.py`
  - `src/dogfood/config.py`
  - `dogfood.example.yaml`
  - `src/dogfood/frames/__init__.py`
  - `src/dogfood/frames/base.py`
  - `src/dogfood/nodos/__init__.py`
  - `src/dogfood/nodos/protocolo.py`
  - `src/dogfood/deterministico/__init__.py`
  - `src/dogfood/flutter/__init__.py`
  - `src/dogfood/deteccion/__init__.py`
  - `src/dogfood/deteccion/flutter.py`
  - `src/dogfood/objetivos/__init__.py`
  - `src/dogfood/objetivos/ios/__init__.py`
  - `src/dogfood/objetivos/flutter_web/__init__.py`
  - `tests/test_contratos_f8.py`

## F8.2 — Package: Android por Tailscale

### F8.2.T1 — ADB sobre Tailscale: emparejar, conectar, estado y reconexión

FR-34, NFR-10, NFR-12, decisión D23. `adb` está en `/usr/bin/adb` pero **no hay dispositivo**: todo con runner falso.

1. `src/dogfood/drivers/adb_red.py`: `DispositivoAdb` (serial, estado, modelo, `permitido: bool`, motivo) y, con un runner inyectable `(args: list[str], *, interactivo: bool = False) -> tuple[int, str]`:
   - `emparejar(host_puerto)`: valida con `validar_destino` y corre `adb pair <host_puerto>` **heredando stdin/stdout** (el código de 6 dígitos lo escribe Héctor en el prompt de `adb`; dogfood no lo lee, no lo pide ni lo guarda). Nunca acepta el código como argumento.
   - `conectar(host_puerto)`: `adb connect` + `adb -s <hp> get-state`; devuelve el `DispositivoAdb` con modelo (`getprop ro.product.model`) y versión de Android (`ro.build.version.release`). Un `failed to connect`/`unable to connect` da un error con el comando de emparejar y `docs/ops/android.md`.
   - `desconectar(host_puerto | None)`.
   - `listar()`: parsea `adb devices -l`; marca `permitido=False` (con el motivo de NFR-10) cualquier `host:puerto` que no pase `validar_destino`.
   - `servidor_local_ok(runner_ss=None) -> tuple[bool, str]`: lee `ss -ltn` y comprueba que el puerto 5037 (servidor `adb`) escucha solo en `127.0.0.1`/`[::1]`; si escucha en `0.0.0.0`/`*`/`[::]`, devuelve falso con la instrucción `adb kill-server` y no usar `adb -a`.
2. `src/dogfood/comandos/android.py` (Typer `app`, lo descubre `cli.py`): `dogfood android emparejar <ip:puerto>`, `conectar [<ip:puerto>]` (por defecto `cfg.driver.host_puerto`), `estado` (tabla de dispositivos con ✅/⛔ y el aviso del servidor local) y `desconectar [<ip:puerto>]`. Errores con `typer.Exit(1)` y mensaje claro.
3. `src/dogfood/drivers/android.py`: en `Adb`, si el destino es `host_puerto` y un comando falla con `device offline`, `device '…' not found`, `no devices/emulators found` o `closed`, corre **una vez** `adb connect` + `get-state` y reintenta el comando; si vuelve a fallar, `AdbError` con el texto «se perdió la conexión por Tailscale» y el comando para reconectar. Un serial USB no reconecta. No cambies nada más del driver.

Done when: estos tests pasan en `tests/test_android_tailscale.py` con runners falsos:
- `emparejar("100.101.102.103:37099")` llama a `adb pair` en modo interactivo y nunca recibe un código en los argumentos; `emparejar("192.168.0.10:37099")` falla antes de llamar a `adb`;
- `conectar` con una salida grabada de éxito devuelve modelo y versión; con `failed to connect` el error menciona `dogfood android emparejar` y `docs/ops/android.md`;
- `listar` marca permitido un serial USB y `100.64.1.2:5555`, y no permitido `192.168.1.20:5555`;
- `servidor_local_ok` es verdadero con `127.0.0.1:5037` y falso con `0.0.0.0:5037`;
- un comando que falla una vez con `device offline` reconecta y reintenta (los argumentos grabados muestran `connect` y el reintento); dos fallos seguidos dan `AdbError` con «Tailscale»; un serial USB no intenta reconectar;
- `dogfood --help` lista `android` y `dogfood android estado` imprime la tabla con el runner falso inyectado (monkeypatch).

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Wrapper de CLI con casos borde de red y seguridad; tier estándar con tests detallados.
- **Dependencies**: F8.1.T1
- **Files**:
  - `src/dogfood/drivers/adb_red.py`
  - `src/dogfood/comandos/android.py`
  - `src/dogfood/drivers/android.py`
  - `tests/test_android_tailscale.py`

## F8.3 — Package: Flutter en Android

### F8.3.T1 — Detección de Flutter, cobertura de Semantics y detector de pantallas ciegas

FR-35, decisión D26. Implementa `src/dogfood/flutter/semantica.py` con `es_flutter`, `cobertura_xml` y `cobertura_elementos` como fija la interfaz «v0.3 — Flutter»:
- `es_flutter(xml, actividad)`: verdadero si el árbol tiene una clase `io.flutter.embedding.android.FlutterView`, `FlutterSurfaceView` o `FlutterTextureView`, o si la actividad contiene `FlutterActivity` o `io.flutter`.
- `cobertura_xml(xml, umbral, actividad)`: sobre XML de `uiautomator` (nodos `node`) o de XCUITest (`XCUIElementType*`, atributos `name`, `label`, `value`, `accessible`, `enabled`, `visible`). En Android cuenta solo los nodos bajo el `FlutterView` cuando es Flutter. Interactivo = `clickable`, `long-clickable`, `checkable`, `scrollable`, clase `EditText`, o `focusable` con texto; en iOS, tipos `Button`, `TextField`, `SecureTextField`, `Switch`, `Cell`, `Link`. Etiquetado = texto o `content-desc` no vacío (iOS: `label` o `name`). Con id = `resource-id` no vacío (iOS: `name` distinto de `label`). `ciega` = Flutter y (`nodos == 0` o `ratio_etiqueta < umbral`).
- `cobertura_elementos(elementos, flutter, umbral)`: lo mismo sobre `ElementoUI` (interactivo = clicable o editable; etiquetado = texto o descripción; con id = id que no empieza con `e` seguido de dígitos).

Reemplaza el stub de `src/dogfood/deteccion/flutter.py`: para cada ejecución con `driver` `android` o `ios`, lee el `Paso.arbol` de cada paso (si existe y es XML), calcula la cobertura y agrupa por pantalla (`Paso.url`); por cada pantalla ciega emite un `Hallazgo` `accesibilidad`, gravedad `media`, título «pantalla sin Semantics: <pantalla>», descripción con los números (interactivos, etiquetados, con id) y cómo arreglarlo (`Semantics(label:, identifier:)`, `Key`), evidencia con la captura del paso y el árbol, huella con firma `ciega`; por cada pantalla Flutter no ciega con `ratio_id < 0.5` y al menos un interactivo, un `Hallazgo` `accesibilidad` gravedad `baja` («sin ids estables para tests», firma `sin_ids`). Una pantalla se reporta una sola vez por corrida aunque aparezca en muchos pasos. El umbral es `ctx.instancia.parametros.get("umbral_cobertura", 0.6)`. No modifiques `deteccion/__init__.py`.

Deja fixtures realistas en `tests/fixtures/flutter/`: `login_etiquetado.xml` (Flutter con campos y botón con `content-desc` y un `resource-id` de `Semantics(identifier:)`), `login_ciego.xml` (un `FlutterView` con un solo nodo sin hijos útiles, como cuando la app no expone Semantics), `nativo.xml` (app Android nativa) y `xcuitest_login.xml` (fuente de XCUITest de una app Flutter en iOS). Mira el código de `/mnt/storage/rupies/apps/mobile-mao/lib` (solo lectura) para que los textos se parezcan a los de una app real.

Done when: estos tests pasan en `tests/test_flutter_semantica.py`:
- `es_flutter` es verdadero con las dos fixtures Flutter y falso con la nativa; verdadero con una actividad `…/io.flutter.embedding.android.FlutterActivity`;
- la cobertura de `login_etiquetado.xml` tiene `ciega == False`, los interactivos y etiquetados esperados y `con_id >= 1`; la de `login_ciego.xml` tiene `ciega == True`;
- una app nativa nunca es ciega aunque no tenga etiquetas (no es Flutter);
- la fuente XCUITest se mide con sus etiquetas;
- `cobertura_elementos` con ids `e12` cuenta cero ids estables;
- el detector, con dos ejecuciones Android que pasan por la misma pantalla ciega, devuelve un solo hallazgo `accesibilidad` `media` con la captura y los números; una pantalla etiquetada sin ids da uno `baja`; una ejecución web no da ninguno.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Parsing de dos formatos de árbol y reglas de cobertura con fixtures; tier estándar.
- **Dependencies**: F8.1.T1
- **Files**:
  - `src/dogfood/flutter/semantica.py`
  - `src/dogfood/deteccion/flutter.py`
  - `tests/fixtures/flutter/login_etiquetado.xml`
  - `tests/fixtures/flutter/login_ciego.xml`
  - `tests/fixtures/flutter/nativo.xml`
  - `tests/fixtures/flutter/xcuitest_login.xml`
  - `tests/test_flutter_semantica.py`

### F8.3.T2 — Cobertura en el driver Android y respaldo por visión en el bucle

FR-35. Conecta la cobertura al agente:
1. `src/dogfood/drivers/android.py`: `DriverAndroid` acepta `umbral_cobertura: float = 0.6`; en `observar`, si el XML existe, calcula `es_flutter(xml, actividad)` y, si es Flutter, `Observacion.cobertura = cobertura_xml(xml, umbral=…, actividad=…)` (para apps nativas deja `cobertura` en None). En Flutter, `parsear_arbol` debe conservar los nodos con `content-desc` multilínea (Flutter junta la etiqueta y el valor con saltos de línea): usa la primera línea como `texto` si `text` está vacío y el resto como `descripcion`. No cambies la reconexión de F8.2.T1.
2. `src/dogfood/agente/bucle.py`: si `obs.cobertura` existe y `ciega`, el paso adjunta la captura reducida aunque haya 3 o más elementos útiles (siempre dentro de `agente.max_capturas_por_paso`; con 0, no se adjunta y se anota en `Paso.observado` «pantalla ciega sin captura por configuración»). La captura de esa pantalla cuenta en las métricas como siempre.
3. `src/dogfood/agente/prompts_bucle.py`: cuando la pantalla es ciega, el prompt dice que la app no expone Semantics en esa pantalla, que los elementos listados pueden faltar y que use la captura y acciones por coordenadas `x`/`y` (con el tamaño en píxeles de la captura original para escalar).

Done when: estos tests pasan en `tests/test_flutter_android.py` con un runner de adb falso que devuelve las fixtures de `tests/fixtures/flutter/` y los `BackendFalso`/`DriverFalso` de `tests/test_bucle.py` (impórtalos o copia lo mínimo):
- `observar` sobre `login_etiquetado.xml` devuelve `cobertura` con `flutter == True` y `ciega == False`, y elementos con el texto tomado de `content-desc`;
- sobre `nativo.xml` la cobertura es None;
- en el bucle, una observación ciega con 5 elementos útiles lleva una imagen en el prompt y el texto de pantalla ciega; una no ciega con 5 elementos no lleva imagen;
- con `max_capturas_por_paso: 0` una pantalla ciega no lleva imagen y el paso lo anota;
- los tests de `tests/test_bucle.py` y `tests/test_driver_android.py` siguen verdes.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Cambios acotados en el driver y el bucle con impacto en costo; tier estándar.
- **Dependencies**: F8.3.T1, F8.2.T1
- **Files**:
  - `src/dogfood/drivers/android.py`
  - `src/dogfood/agente/bucle.py`
  - `src/dogfood/agente/prompts_bucle.py`
  - `tests/test_flutter_android.py`

## F8.4 — Package: pantalla real en vista y panel

### F8.4.T1 — Fuentes de frames: screencap, screenrecord con ffmpeg y MJPEG de WebDriverAgent

FR-37, NFR-11, NFR-12, decisiones D24 y D25. Implementa según la interfaz «v0.3 — Fuente de frames»:
1. `src/dogfood/frames/android.py`:
   - `FuenteScreencap(adb, fps=2)`: `exec-out screencap -p` → JPEG de lado mayor ≤ 720 px, calidad 60 (en un hilo con `asyncio.to_thread`); `intervalo_s = 1/fps`; `frame()` devuelve el último sin pedir otro si no pasó el intervalo.
   - `FuenteScreenrecord(adb, carpeta_video, fps=5, runner_ffmpeg=None)`: arranca `adb -s <destino> exec-out screenrecord --output-format=h264 --time-limit 170 -` y lo encadena a `ffmpeg -loglevel error -f h264 -i - -f image2pipe -c:v mjpeg -q:v 7 -r <fps> -` (dos `asyncio.create_subprocess_exec`, sin shell); una tarea lee el stdout de `ffmpeg` y corta los JPEG por los marcadores `FF D8` … `FF D9`, guardando el último; otra copia el H.264 crudo a `carpeta_video/stream-<n>.h264` (evidencia; el driver se crea con `grabar_video=False` cuando esta fuente está activa). Al terminar los 170 s reinicia con `n+1`. Si `ffmpeg` no está en el PATH o el proceso muere dos veces seguidas, cae a `FuenteScreencap` y lo anota en el log. `cerrar()` mata los procesos que sigan vivos.
2. `src/dogfood/frames/mjpeg.py`: `FuenteMjpeg(url, cliente=None)`: valida la URL con `validar_url_local`; con `httpx.AsyncClient.stream("GET", url)` lee el `multipart/x-mixed-replace` (boundary del `Content-Type`, partes con `Content-Length` o cortadas por el boundary) y guarda el último JPEG; si la conexión se corta, reintenta con espera 0,5 s, 1 s, 2 s… hasta 10 s; `frame()` nunca espera a la red.
3. `src/dogfood/frames/__init__.py`: `crear_fuente(cfg, driver, parametros)`: `android` con `cfg.pantalla.android == "screencap"` → `FuenteScreencap(driver.adb, cfg.pantalla.fps)`; `"screenrecord"` → `FuenteScreenrecord`; `ios` con `parametros["mjpeg_url"]` → `FuenteMjpeg`; el resto → `FuenteDeDriver(driver)`.

Done when: estos tests pasan en `tests/test_frames.py`:
- `FuenteScreencap` con un runner falso devuelve un JPEG ≤ 720 px y no llama dos veces a `screencap` dentro del intervalo;
- `FuenteScreenrecord` con procesos falsos (scripts en un directorio temporal en el `PATH` que escriben a stdout dos JPEG concatenados y un H.264 de bytes fijos) entrega el último JPEG, escribe `stream-0.h264` y, sin `ffmpeg` en el PATH, cae a screencap;
- `FuenteMjpeg` con `httpx.MockTransport` que responde un multipart con tres frames devuelve el tercero; con una URL `http://192.168.1.4:9100` falla al construirse; una desconexión reintenta;
- `crear_fuente` elige la fuente correcta para cada caso (web, android screencap, android screenrecord, ios con y sin `mjpeg_url`).

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Streams de subprocesos y HTTP con parsing binario; tier estándar con tests de procesos falsos.
- **Dependencies**: F8.1.T1
- **Files**:
  - `src/dogfood/frames/__init__.py`
  - `src/dogfood/frames/android.py`
  - `src/dogfood/frames/mjpeg.py`
  - `tests/test_frames.py`

### F8.4.T2 — Panel: página «Dispositivos» con la pantalla en vivo

FR-37 (panel), NFR-10, NFR-12. Crea `src/dogfood/panel/dispositivos.py` con `registrar_rutas(app, plantillas, raiz, cfg=None, fuentes=None, runner_adb=None)`:
- `GET /dispositivos`: lista los Android de `adb_red.listar()` (F8.2.T1, con su runner inyectable) — los permitidos con su pantalla; los no permitidos deshabilitados con el motivo — y los nodos iOS de `cfg.nodos`; cada tarjeta muestra nombre, estado y un `<img>` con `src="/dispositivos/<id>/mjpeg"`. Sin dispositivos, un texto que remite a `docs/ops/android.md` y `docs/ops/ios-nodo-mac.md`.
- `GET /dispositivos/{id}/mjpeg`: `StreamingResponse` con `multipart/x-mixed-replace; boundary=frame`, que pide `frame()` a la `FuenteFrames` del dispositivo cada `intervalo_s` y emite cada JPEG nuevo; la fuente sale de `fuentes` (inyectable, `dict[str, FuenteFrames]`) o se crea con `FuenteScreencap` (Android) o `FuenteMjpeg` (iOS, `http://127.0.0.1:9100` del túnel); un id desconocido o no permitido da 404. Cuando el cliente se va, la fuente se cierra.
- `src/dogfood/panel/plantillas/dispositivos.html` extendiendo `base.html`, con la grilla de tarjetas y el estilo de `dogfood.css`.
- `src/dogfood/panel/app.py`: registra las rutas (una línea en `crear_app_panel`).
- `src/dogfood/web/plantillas/base.html`: enlace «Dispositivos» en la barra lateral.

Done when: estos tests pasan en `tests/test_panel_dispositivos.py` con `TestClient`, un runner de adb falso y fuentes falsas:
- `GET /dispositivos` muestra un Android permitido con su `<img>` de stream y uno de LAN deshabilitado con el motivo, más un nodo iOS de la config;
- `GET /dispositivos/<id>/mjpeg` devuelve `multipart/x-mixed-replace` y al menos dos partes JPEG de la fuente falsa (lee el stream con límite de bytes);
- un id desconocido da 404;
- la barra lateral de `GET /` tiene el enlace «Dispositivos»;
- los tests de `tests/test_panel.py` y `tests/test_panel_detalle.py` siguen verdes.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Ruta de streaming y plantilla sobre un panel ya hecho; tier estándar.
- **Dependencies**: F8.4.T1, F8.2.T1
- **Files**:
  - `src/dogfood/panel/dispositivos.py`
  - `src/dogfood/panel/plantillas/dispositivos.html`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/web/plantillas/base.html`
  - `tests/test_panel_dispositivos.py`

### F8.4.T3 — Fuente de frames, cobertura y Flutter web en el bucle y la corrida

FR-35, FR-37 y FR-39 de punta a punta en `dogfood run`.
1. `src/dogfood/agente/bucle.py`: `ejecutar(..., fuente_frames: FuenteFrames | None = None)`; el emisor de frames usa `fuente_frames` (o `FuenteDeDriver(driver)` si es None), la inicia antes del primer paso y la cierra en el `finally`, con su `intervalo_s`. `INTERVALO_FRAME_S` suma `ios: 1.0`. Sin bus activo no se crea ni se inicia ninguna fuente. No cambies la lógica de captura forzada de F8.3.T2.
2. `src/dogfood/corrida.py`: `_driver` pasa `umbral_cobertura=cfg.flutter.umbral_cobertura` a `DriverAndroid` y `grabar_video=False` cuando `cfg.pantalla.android == "screenrecord"`; para el driver web, `flutter=bool(instancia.parametros.get("flutter"))` y el umbral. Si el bus está activo, crea la fuente con `frames.crear_fuente(cfg, driver, instancia.parametros)` y la pasa al bucle. Pone `umbral_cobertura` en `instancia.parametros` si falta, para el detector de F8.3.T1.

Done when: estos tests pasan en `tests/test_corrida_frames.py` (con objetivo, drivers, backends y fuentes falsos, como `tests/test_corrida_motores.py`) y los tests de `tests/test_bucle.py`, `tests/test_corrida_motores.py` y `tests/test_corrida_vista.py` siguen verdes:
- con bus activo, el bucle publica los frames de la fuente inyectada (no los de `driver.frame()`) y la fuente se inicia y se cierra una vez;
- sin bus, la fuente nunca se inicia;
- una corrida Android con `pantalla.android: screenrecord` crea el driver con `grabar_video=False`;
- una instancia con `parametros.flutter = True` crea el `DriverWeb` con `flutter=True`;
- `instancia.parametros["umbral_cobertura"]` queda con el valor de la config.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Cableado en archivos conocidos y encadenados; tier estándar.
- **Dependencies**: F8.4.T1, F8.3.T2, F8.7.T1
- **Files**:
  - `src/dogfood/agente/bucle.py`
  - `src/dogfood/corrida.py`
  - `tests/test_corrida_frames.py`

## F8.5 — Package: motor determinista Patrol / integration_test

### F8.5.T1 — Corredor de Patrol e integration_test con copia de trabajo y mapeo al contrato

FR-36, decisión D27. Implementa `src/dogfood/deterministico/corredor.py` con `CorredorFlutter` y `a_ejecucion` según la interfaz «v0.3 — Motor determinista» (los modelos `ResultadoTest`/`ResultadoDeterministico` ya están en `deterministico/__init__.py`; no los cambies):
- `copia_de_trabajo(proyecto)`: `rsync -a --delete --exclude build/ --exclude .dart_tool/ --exclude .git/` de la app a `cfg.flutter.copia_trabajo/<nombre del directorio>`; nunca escribe en `proyecto`. Si `proyecto` está dentro de la copia o es la misma ruta, error.
- Con `escenario.deterministico.archivo`, usa ese test de la copia; si no, escribe en `integration_test/dogfood/<escenario.id>_test.dart` el texto de `generar_test(escenario, herramienta)` de `dogfood.deterministico.generador` (F8.5.T2, ya mergeado), con los defines de `defines(recorrido, cfg)` del mismo módulo. Con `integration_test`, si `pubspec.yaml` de la copia no tiene `integration_test` en `dev_dependencies`, corre `flutter pub add --dev integration_test --sdk=flutter` en la copia. Con `patrol`, si no hay `patrol` en `dev_dependencies` ni bloque `patrol:` en el pubspec, no corre nada y devuelve `motivo="app_sin_patrol"` con la instrucción de `docs/ops/flutter.md`.
- `comando(...)`: los dos comandos exactos de la arquitectura, con `cfg.flutter.sdk` / `cfg.flutter.patrol` como binario y un `--dart-define K=V` por define.
- `correr(...)`: corre con `cwd` en la copia, entorno con `PUB_CACHE=cfg.flutter.pub_cache` y `PATH` que incluye el `bin` del SDK, y timeout `cfg.flutter.timeout_s`. Escribe en `carpeta/deterministico/` el test usado (`test.dart`), `salida.log` (stdout+stderr con los valores de los defines reemplazados por `***`) y, para `integration_test`, `reporte.json` (los eventos JSON). Parseo: `--reporter json` → eventos `testStart` (nombre) y `testDone` (`result` `success`/`failure`/`error`, `skipped`, `hidden`; los `hidden` como `loading …` se ignoran); Patrol → líneas de resultado (`✅`/`❌` con el nombre, y el resumen `Test summary`/`passed`/`failed`; léelas en la documentación de `patrol_cli` instalada en `/mnt/storage/flutter/.pub-cache` si existe, si no, cubre los formatos `✅ name (file)` y `❌ name (file)`). Clasifica `motivo`: `compilacion` (salida con `Error:`/`Gradle task assembleDebug failed`/`Xcode build failed`/`Compilation failed`), `sin_dispositivo` (`No devices found`/`No supported devices connected`/`not found` del id), `timeout`, `sin_tests`. Si se pasó `capturar`, la llama al final para `capturas/final.png`.
- `a_ejecucion(r, persona, escenario, ejecucion_id, driver)`: `Ejecucion` con `motor = r.herramienta`, `backend = "ninguno"`, `modelo = r.herramienta`, un `Paso` por test (`accion` = nombre del test, `observado` = estado y mensaje, la captura final en el último paso), `estado` `ok`/`fallo`/`error` según `r.resultado()` (`no_concluyente` → `error`), `exito` y `motivo_juez` (resumen «N de M tests pasaron: …») cuando todo pasó, `evidencia_driver` con el log y el reporte, `resultado = r.resultado()`; debe coincidir con `contrato.resultado(e)` cuando hay captura final (compruébalo en un test) y quedar `no_concluyente` sin captura.

Done when: estos tests pasan en `tests/test_deterministico_corredor.py` con un `RunnerProceso` falso que graba args, cwd y env y devuelve salidas grabadas en `tests/fixtures/flutter/` (un `flutter_test_ok.jsonl`, un `flutter_test_fallo.jsonl`, un `flutter_compilacion.txt`, un `patrol_ok.txt`, un `patrol_fallo.txt`):
- el comando de `integration_test` es exactamente `[<sdk>, "test", "integration_test/dogfood/login_test.dart", "-d", "<id>", "--reporter", "json", "--dart-define", "DOGFOOD_EMAIL=…"]` y el de Patrol usa `test --target … --device …`;
- todo ok → `aprobado`; un test en fallo → `fallo` con su mensaje en el paso; error de compilación → `no_concluyente` con `motivo == "compilacion"`; timeout → `no_concluyente`; cero tests → `no_concluyente`;
- la copia de trabajo se crea con `rsync` excluyendo `build/`, `.dart_tool/` y `.git/`, el runner nunca recibe un `cwd` igual al proyecto original y se agrega `integration_test` al pubspec de la copia si falta;
- Patrol sin `patrol` en el pubspec devuelve `app_sin_patrol` sin correr nada;
- el valor de una contraseña pasada como define no aparece en `salida.log`;
- `a_ejecucion` de un resultado aprobado con captura final da `contrato.resultado(e) == "aprobado"`, y sin captura da `no_concluyente`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Integración con dos CLIs y parsing de su salida con muchos casos; tier estándar con fixtures.
- **Dependencies**: F8.5.T2
- **Files**:
  - `src/dogfood/deterministico/corredor.py`
  - `tests/fixtures/flutter/flutter_test_ok.jsonl`
  - `tests/fixtures/flutter/flutter_test_fallo.jsonl`
  - `tests/fixtures/flutter/flutter_compilacion.txt`
  - `tests/fixtures/flutter/patrol_ok.txt`
  - `tests/fixtures/flutter/patrol_fallo.txt`
  - `tests/test_deterministico_corredor.py`

### F8.5.T2 — Generador de tests Patrol / integration_test y escenarios de login y pago

FR-36. Implementa `src/dogfood/deterministico/generador.py`:
- `generar_test(escenario, herramienta) -> str`: un archivo Dart completo a partir de `escenario.deterministico.pasos`. Para `integration_test`: `import 'package:flutter_test/flutter_test.dart'; import 'package:integration_test/integration_test.dart';` más el `main.dart` de la app (`import 'package:<nombre del paquete>/main.dart' as app;`, con el nombre leído de un parámetro `paquete_dart`, por defecto `app`), `IntegrationTestWidgetsFlutterBinding.ensureInitialized()`, un `testWidgets('<escenario.titulo>', …)` que llama `app.main()`, `pumpAndSettle` y por paso: `tocar` → `tester.tap(find.byKey(ValueKey('<key>')))` o `find.text('<texto>')`; `escribir` → `tester.enterText(…, <valor>)`; `esperar_texto` → bucle de `pump` hasta `timeout_s` buscando `find.text`; `ver_texto` → `expect(find.text(…), findsOneWidget)`; `deslizar` → `tester.drag`; `volver` → `tester.pageBack()`. Para `patrol`: `import 'package:patrol/patrol.dart';`, `patrolTest('<titulo>', ($) async { … })` con `$(#key).tap()`, `$('texto').tap()`, `$(#key).enterText(…)`, `$('texto').waitUntilVisible(timeout: …)`, `expect($('texto'), findsOneWidget)`, `$.native.pressBack()`.
- Valores: `{env:NOMBRE}` → `const String.fromEnvironment('NOMBRE')`; cualquier otro valor va como literal Dart escapado (comillas y `$`). Nunca un secreto en el archivo.
- `defines(recorrido, cfg) -> dict[str, str]`: resuelve cada `{env:NOMBRE}` de los pasos y de `dart_defines` con `cfg.secreto(NOMBRE)` (por convención en `~/.config/dogfood/flutter.env`); un secreto que falta da el error de `Config.secreto`.
- Escenarios de ejemplo en `src/dogfood/objetivos/android/escenarios/`: `login-determinista.yaml` (`motor: integration_test`, login con email y contraseña por `{env:DOGFOOD_APP_EMAIL}`/`{env:DOGFOOD_APP_CONTRASENA}`, keys `campo_email`, `campo_contrasena`, `boton_entrar`, y espera del texto de la pantalla principal) y `pago-determinista.yaml` (`motor: patrol`, comprar créditos: ir a «Plano», elegir un paquete, confirmar y ver la pantalla de pago pendiente). Usa `/mnt/storage/rupies/apps/mobile-mao/lib/features/plano/` (solo lectura) para nombrar textos reales del recorrido de pago y anota en un comentario del YAML qué `Key`/`Semantics(identifier:)` faltan hoy en la app. Ambos con `contrato` completo y `driver: android`.

Done when: estos tests pasan en `tests/test_deterministico_generador.py`:
- el test generado de `integration_test` para el login contiene `testWidgets`, `find.byKey(ValueKey('campo_email'))`, `String.fromEnvironment('DOGFOOD_APP_CONTRASENA')` y ningún valor de secreto; coincide con un golden en `tests/fixtures/flutter/login_integration_test.dart`;
- el de Patrol contiene `patrolTest` y `$(#boton_entrar).tap()` y coincide con `tests/fixtures/flutter/login_patrol.dart`;
- un texto con comillas y `$` queda escapado;
- `defines` resuelve los `{env:…}` desde los secretos de la config (un `DOGFOOD_CONFIG_DIR` temporal) y falla con el nombre del archivo si falta uno;
- los dos escenarios de ejemplo cargan con `AndroidObjetivo().escenarios()` y tienen `motor` y `deterministico`;
- `tests/test_objetivo_android.py` sigue verde (ajusta solo si contaba escenarios y dilo en el PR).

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Generación de código Dart por plantilla con golden tests; tier estándar.
- **Dependencies**: F8.1.T1
- **Files**:
  - `src/dogfood/deterministico/generador.py`
  - `src/dogfood/objetivos/android/escenarios/login-determinista.yaml`
  - `src/dogfood/objetivos/android/escenarios/pago-determinista.yaml`
  - `tests/fixtures/flutter/login_integration_test.dart`
  - `tests/fixtures/flutter/login_patrol.dart`
  - `tests/test_deterministico_generador.py`

### F8.5.T3 — Motor determinista en `dogfood run`

FR-36 de punta a punta.
1. `src/dogfood/corrida.py`: por ejecución, si `op.motor` o `escenario.motor` es `patrol` o `integration_test` (y el escenario tiene `deterministico`), en lugar del bucle: con driver `android`, `CorredorFlutter(cfg).correr(escenario, herramienta, dispositivo=<serial o host_puerto de la instancia>, carpeta, proyecto=cfg.flutter.proyecto, capturar=<screencap del dispositivo a capturas/final.png>)` y `a_ejecucion(...)`; con driver `ios`, deja un `NotImplementedError` claro que F8.6.T4 reemplaza («iOS determinista va por el nodo»). Sin `cfg.flutter.proyecto` y sin `deterministico.archivo` absoluto, la ejecución termina `error` / `no_concluyente` con el motivo, sin romper la corrida. Publica `inicio` y `fin` en el bus. La ejecución no registra uso de LLM.
2. `src/dogfood/comandos/run.py`: `--motor` acepta `patrol` e `integration_test`.

Done when: estos tests pasan en `tests/test_corrida_deterministico.py` (objetivo Android falso, `CorredorFlutter` reemplazado por uno falso) y `tests/test_corrida_motores.py`, `tests/test_corrida_frames.py` y `tests/test_corrida_vista.py` siguen verdes:
- `--motor integration_test` con el escenario de login corre el corredor con el dispositivo de la instancia y guarda una ejecución con `motor == "integration_test"` y su resultado;
- un escenario con `motor: patrol` en el YAML usa el corredor sin opción en la CLI;
- sin `flutter.proyecto` la ejecución queda `no_concluyente` con el motivo y la corrida termina;
- el corredor recibe `capturar` y la captura final queda en el paso;
- con bus activo se publican `inicio` y `fin`;
- `dogfood run --help` muestra `patrol` e `integration_test`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 2h
- **Razón**: Cableado acotado sobre piezas ya probadas.
- **Dependencies**: F8.5.T1, F8.5.T2, F8.4.T3
- **Files**:
  - `src/dogfood/corrida.py`
  - `src/dogfood/comandos/run.py`
  - `tests/test_corrida_deterministico.py`

## F8.6 — Package: nodo iOS en el Mac

### F8.6.T1 — Cliente del nodo: estado, trabajos por SSH, artefactos por rsync y túnel

FR-38, NFR-12, decisión D28. Implementa `src/dogfood/nodos/cliente.py` con `ClienteNodo(nombre, nodo: Nodo, runner=None)` según la interfaz «v0.3 — Nodo iOS»:
- Valida `nodo.host` (loopback o Tailscale) al construir; el usuario solo `^[a-z_][a-z0-9_.-]*$`.
- Runner inyectable `(args, *, entrada: bytes | None, timeout_s) -> tuple[int, bytes, bytes]` sobre `asyncio.create_subprocess_exec`, sin shell. Todo `ssh` lleva `-o BatchMode=yes -o ConnectTimeout=10 -p <puerto_ssh>`.
- `estado() -> EstadoNodo`: `ssh … <usuario>@<host> <comando> estado --json`.
- `enviar(trabajo, carpeta) -> ResultadoTrabajo`: `ssh … <comando> ejecutar` con el `Trabajo` en JSON por stdin (los `dart_defines` viajan solo ahí: nunca en argv); toma la última línea no vacía de stdout como `ResultadoTrabajo`; luego `rsync -a -e "ssh -p <p> -o BatchMode=yes" <usuario>@<host>:<dir_trabajo>/<id>/ <carpeta>/`. Errores claros: host inalcanzable o `Permission denied (publickey)` → «configura la clave SSH y Tailscale; ver docs/ops/ios-nodo-mac.md»; `command not found` → «instala dogfood en el Mac»; stdout sin JSON válido → error con las últimas líneas de stderr; timeout del trabajo + 60 s → error.
- `tunel(puertos) -> Tunel`: lanza `ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:<p>:127.0.0.1:<p> …` por cada puerto (Appium 4723, MJPEG 9100) y devuelve un objeto con `cerrar()` (async context manager también).
- `a_ejecucion_ios(resultado, persona, escenario, ejecucion_id, carpeta)`: usa `a_ejecucion` de `deterministico/corredor.py` (F8.5.T1) si `deterministico` viene, si no `Ejecucion` en `error` con el mensaje; reescribe las rutas relativas del resultado a `carpeta`.

Done when: estos tests pasan en `tests/test_nodo_cliente.py` con un runner falso:
- `estado()` manda exactamente `ssh -o BatchMode=yes -o ConnectTimeout=10 -p 22 hector@100.101.102.103 dogfood nodo estado --json` y parsea un `EstadoNodo` grabado;
- `enviar` manda el trabajo por stdin, los `dart_defines` no aparecen en ningún argumento, parsea la última línea JSON aunque haya logs antes y llama a `rsync` con el directorio del trabajo;
- `Permission denied (publickey)` y `command not found` dan los mensajes accionables;
- un nodo con host `192.168.0.20` falla al construirse y un usuario `root;rm` también;
- `tunel([4723, 9100])` lanza un `ssh -N` con los dos `-L` en loopback y `cerrar()` termina el proceso.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Cliente de subprocesos con protocolo fijado y seguridad de argumentos; tier estándar.
- **Dependencies**: F8.5.T1
- **Files**:
  - `src/dogfood/nodos/cliente.py`
  - `tests/test_nodo_cliente.py`

### F8.6.T2 — Runner del nodo en el Mac y comando `dogfood nodo`

FR-38. Lo que corre en el Mac (macOS, Apple Silicon); aquí se prueba con fakes.
1. `src/dogfood/nodos/runner.py`: `estado_nodo(runner) -> EstadoNodo` (`xcodebuild -version`, `xcrun xctrace list devices` parseado a `{udid, nombre, os}` solo de dispositivos físicos —sin «Simulator»—, `GET http://127.0.0.1:4723/status` con `httpx` y timeout 2 s, `patrol --version`, `flutter --version --machine`); cada comando ausente deja su campo en None sin fallar. `ejecutar(trabajo, dir_trabajo, runner, corredor=None) -> ResultadoTrabajo`: crea `dir_trabajo/<id>/`; `estado` → `estado_nodo`; `patrol` → `CorredorFlutter` (de F8.5.T1) con la app de `trabajo.proyecto`, dispositivo `trabajo.udid`, carpeta `dir_trabajo/<id>/`, `dart_defines` solo en memoria, y las rutas del `ResultadoDeterministico` relativas a esa carpeta; `sesion_appium` → si `127.0.0.1:4723/status` no responde, arranca `appium --address 127.0.0.1 --port 4723` en segundo plano (log en `dir_trabajo/appium.log`, PID en `dir_trabajo/appium.pid`) y espera hasta 30 s; devuelve `appium_url="http://127.0.0.1:4723"` y `mjpeg_url="http://127.0.0.1:9100"`; `cerrar_sesion` → mata el Appium solo si su PID está en `appium.pid`. Nunca escucha fuera de loopback.
2. `src/dogfood/comandos/nodo.py` (Typer `app`): `dogfood nodo estado [--json] [--dir-trabajo]` y `dogfood nodo ejecutar [--dir-trabajo]` (lee un `Trabajo` de stdin, escribe logs a stderr y el `ResultadoTrabajo` como **última línea** de stdout; código de salida 0 si se pudo producir el JSON aunque el trabajo haya fallado). `--dir-trabajo` por defecto `~/dogfood-nodo` expandido.

Done when: estos tests pasan en `tests/test_nodo_runner.py` con runners falsos y `httpx.MockTransport`:
- `estado_nodo` con salidas grabadas de `xcodebuild` y `xctrace` devuelve la versión de Xcode y solo el iPhone físico; sin `xcodebuild` en el PATH devuelve `xcode=None` sin lanzar;
- un trabajo `patrol` llama al corredor falso con el udid y deja las rutas relativas;
- `sesion_appium` arranca `appium --address 127.0.0.1 --port 4723` cuando no responde y no lo arranca si ya responde; `cerrar_sesion` solo mata un Appium arrancado por el nodo;
- `dogfood nodo ejecutar` con un `Trabajo` por stdin (CliRunner) imprime logs y como última línea un `ResultadoTrabajo` válido; un JSON inválido en stdin da un `ResultadoTrabajo` con `estado == "error"`;
- `dogfood --help` lista `nodo`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Runner de procesos y CLI con protocolo fijado; tier estándar.
- **Dependencies**: F8.5.T1
- **Files**:
  - `src/dogfood/nodos/runner.py`
  - `src/dogfood/comandos/nodo.py`
  - `tests/test_nodo_runner.py`

### F8.6.T3 — Driver iOS sobre Appium XCUITest por HTTP

FR-38, FR-28, decisión D29. Implementa `src/dogfood/drivers/ios.py` con `DriverIos(appium_url, udid, bundle_id, *, cliente: httpx.AsyncClient | None = None, umbral_cobertura=0.6)` que cumple `Driver` hablando el protocolo W3C WebDriver de Appium con `httpx` (sin `Appium-Python-Client` ni Selenium):
- Valida `appium_url` con `validar_url_local`.
- `iniciar(carpeta)`: crea `capturas/`, `arboles/`, `video/`; `POST /session` con `capabilities.alwaysMatch` = `platformName: iOS`, `appium:automationName: XCUITest`, `appium:udid`, `appium:bundleId`, `appium:mjpegServerPort: 9100`, `appium:noReset: true`, `appium:newCommandTimeout: 300`; arranca `mobile: startRecordingScreen` (`POST /session/{id}/execute/sync`).
- `observar(n)`: `GET /screenshot` (base64 → `capturas/paso-NNN.png`), `GET /source` → `arboles/paso-NNN.xml`, parseo de `XCUIElementType*` a `ElementoUI` (id = `name` si existe, si no `e<n>`; texto = `label` o `value`; clase = tipo sin prefijo; bounds de `x`,`y`,`width`,`height` en puntos multiplicados por la escala de la pantalla, que sale de comparar el ancho del PNG con el de `XCUIElementTypeApplication`; clicable para `Button`, `Cell`, `Link`, `Switch`, `Image` con `accessible`; editable para `TextField`, `SecureTextField`, `TextView`; descarta los no visibles). `pantalla` = el `name` de la primera `XCUIElementTypeNavigationBar` o de la ventana. Cobertura con `cobertura_xml` de F8.3.T1 (Flutter en iOS si la fuente tiene `FlutterView` o el bundle tiene vistas Flutter; si no se puede saber, `flutter=False`).
- `actuar(accion)`: `tocar` → acciones W3C (`POST /actions`, puntero `touch`: move, down, pause 50 ms, up) en el centro en puntos; `escribir` → toca el elemento si viene y manda `POST /actions` de teclado o `element/{id}/value` si hay id de elemento WebDriver (búscalo con `POST /element` `accessibility id`); `deslizar` → acciones con `ms`; `volver` → deslizamiento desde el borde izquierdo; `tecla` → teclas W3C; `abrir_app`/`cerrar_app` → `mobile: activateApp`/`mobile: terminateApp`; `esperar` → sleep. Devuelve el `punto` en píxeles de la captura.
- `frame()`: `GET /screenshot` como mucho una vez por segundo, reducido a JPEG ≤ 720 px (la vista usa normalmente el MJPEG de F8.4.T1).
- `evidencia()`: `mobile: stopRecordingScreen` → `video/ios.mp4`; `POST /session/{id}/se/log` con `type: syslog` → `syslog.txt` filtrado por el nombre del proceso de la app (último componente del bundle id) y `Evidencia` de tipo `log` con las líneas de error/crash; `cerrar()` → `DELETE /session/{id}` sin lanzar si ya no existe.

Deja `tests/fixtures/ios/source_login.xml` (fuente de XCUITest realista de una pantalla de login Flutter) y `tests/fixtures/ios/syslog.json`.

Done when: estos tests pasan en `tests/test_driver_ios.py` con `httpx.MockTransport` que graba peticiones:
- `iniciar` manda las capabilities exactas y arranca la grabación;
- `observar` guarda captura y árbol y devuelve los elementos del login con bounds escalados y su cobertura;
- tocar «Entrar» manda una secuencia W3C de puntero en el centro correcto y devuelve el punto en píxeles;
- escribir un texto lo envía al campo; `volver` desliza desde el borde izquierdo; `abrir_app`/`cerrar_app` usan `mobile: activateApp`/`terminateApp`;
- `evidencia` guarda `ios.mp4` y `syslog.txt` con el extracto de error;
- un `appium_url` de LAN falla al construirse; `cerrar` no lanza si la sesión ya no existe.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Protocolo WebDriver con escalado de coordenadas y parsing de XML; tier estándar con tests detallados.
- **Dependencies**: F8.1.T1, F8.3.T1
- **Files**:
  - `src/dogfood/drivers/ios.py`
  - `tests/fixtures/ios/source_login.xml`
  - `tests/fixtures/ios/syslog.json`
  - `tests/test_driver_ios.py`

### F8.6.T4 — Objetivo iOS y driver iOS en `dogfood run`

FR-38 de punta a punta en guria.
1. `src/dogfood/objetivos/ios/__init__.py`: reemplaza el stub por `IosObjetivo(cfg=None, cliente=None)`: `preparar` toma `cfg.nodos[cfg.driver.nodo]` (error claro si falta, citando `docs/ops/ios-nodo-mac.md`), verifica `estado()` (Xcode y el `udid` de `cfg.driver.udid` entre los dispositivos), abre `tunel([4723, 9100])`, envía un trabajo `sesion_appium` y devuelve `Instancia(base_url=f"ios://{bundle_id}", parametros={nodo, udid, bundle_id, appium_url, mjpeg_url, version_app})` (versión con `mobile: appInfo`/`CFBundleShortVersionString` si se puede, si no vacío); `destruir` envía `cerrar_sesion` y cierra el túnel; `url_permitida` solo `ios://<bundle_id>…`; `pantalla` el resto de la URL; `logs` `{}`; `verificadores` `[]`; `escenarios` los YAML de `objetivos/ios/escenarios/`. Crea `objetivos/ios/escenarios/login.yaml` (agéntico, `driver: ios`, con contrato) y `login-patrol.yaml` (`driver: ios`, `motor: patrol`, mismos pasos que `login-determinista.yaml` de Android).
2. `src/dogfood/corrida.py`: `_driver("ios", …)` crea `DriverIos(parametros["appium_url"], parametros["udid"], parametros["bundle_id"], umbral_cobertura=…)`; el modo determinista con driver `ios` reemplaza el `NotImplementedError` de F8.5.T3: arma un `Trabajo` `patrol` (o `integration_test`) con el escenario, el `udid`, `cfg.nodos[…].proyectos` y los defines resueltos por `defines(...)`, lo manda con `ClienteNodo.enviar(trabajo, carpeta)` y convierte el resultado con `a_ejecucion_ios`.
3. `src/dogfood/comandos/run.py`: `--driver` acepta `ios`.

Done when: estos tests pasan en `tests/test_objetivo_ios.py` con un `ClienteNodo` falso y un `DriverIos` falso, y los tests de corrida existentes siguen verdes:
- `cargar_objetivo("ios")` devuelve un `IosObjetivo` y `escenarios()` carga los dos YAML;
- `preparar` con un nodo falso que tiene el udid devuelve la instancia con las URLs del túnel; sin `driver.nodo` o con un udid ausente falla con el mensaje que cita `docs/ops/ios-nodo-mac.md`;
- `destruir` cierra la sesión y el túnel;
- una corrida `--driver ios` agéntica usa `DriverIos` con los parámetros de la instancia;
- una corrida con `motor: patrol` y `driver: ios` envía un `Trabajo` `patrol` al nodo con el udid, sin secretos en el escenario serializado, y guarda la ejecución con `driver == "ios"`;
- `dogfood run --help` muestra `ios`.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Adaptador y cableado sobre piezas ya probadas; tier estándar.
- **Dependencies**: F8.6.T1, F8.6.T3, F8.5.T3
- **Files**:
  - `src/dogfood/objetivos/ios/__init__.py`
  - `src/dogfood/objetivos/ios/escenarios/login.yaml`
  - `src/dogfood/objetivos/ios/escenarios/login-patrol.yaml`
  - `src/dogfood/corrida.py`
  - `src/dogfood/comandos/run.py`
  - `tests/test_objetivo_ios.py`

## F8.7 — Package: filtro web Flutter

### F8.7.T1 — Driver web con Semantics de Flutter y objetivo `flutter_web`

FR-39, decisión D30.
1. `src/dogfood/drivers/web.py`: `DriverWeb(..., flutter: bool = False, umbral_cobertura: float = 0.6)`. Con `flutter=True`: tras `goto`, espera hasta 20 s a `flutter-view` o `flt-glass-pane`; activa los Semantics con un clic (por JS `dispatchEvent` de `click` o `element.click()`) en `flt-semantics-placeholder`; en cada `observar`, si no hay ningún `flt-semantics`, vuelve a intentarlo una vez. `JS_ELEMENTOS` suma `flt-semantics[role], flt-semantics[aria-label]` (texto desde `aria-label` o `innerText`; clicable para `role` `button`, `link`, `tab`, `checkbox`, `menuitem`; editable para `textbox` o los `input`/`textarea` que Flutter monta). Cada observación lleva `cobertura = cobertura_elementos(elementos, flutter=True, umbral=…)`. Sin `flutter`, el comportamiento actual no cambia.
2. `src/dogfood/objetivos/flutter_web/__init__.py`: reemplaza el stub por `FlutterWebObjetivo(cfg=None, runner=None)`: `preparar` usa `cfg.flutter_web.build_dir` si existe y tiene `index.html`; si no, y hay `cfg.flutter.proyecto`, hace la copia de trabajo con `CorredorFlutter(cfg, runner).copia_de_trabajo` (F8.5.T1) y corre `<sdk> build web --release` con los `dart_defines` resueltos por `defines` de F8.5.T2 y `PUB_CACHE` de la config; sirve el `build/web` con `ThreadingHTTPServer` + `SimpleHTTPRequestHandler` (directorio fijo) en un hilo, en `flutter_web.host:puerto` validado con `validar_host`; devuelve `Instancia(base_url=f"http://{host}:{puerto}/", parametros={"flutter": True, "build_dir": …, "umbral_cobertura": …})`. `destruir` apaga el servidor. `url_permitida`: su origen y los de `api_permitidas`. `pantalla(url)`: la ruta del hash o del path (`/#/login` → `login`, `/` → `inicio`). `escenarios()`: `objetivos/flutter_web/escenarios/*.yaml`; crea `login.yaml` (`driver: web`, contrato completo, sin datos) y `explorar.yaml` (recorrer las pantallas visibles sin iniciar sesión y anotar fricciones).
3. `tests/fixtures/flutter_web/index.html`: una página estática que imita Flutter web: `flutter-view` con un `flt-semantics-placeholder` (`role="button"`, `aria-label="Enable accessibility"`) que al recibir un clic crea un `flt-semantics-host` con `flt-semantics` de rol `textbox` (email, contraseña) y `button` («Entrar»), y un canvas de fondo.

Done when: estos tests pasan en `tests/test_flutter_web.py`:
- con objetos falsos de Playwright (sin navegador), `DriverWeb(flutter=True)` busca y clica el placeholder tras cargar y no lo hace con `flutter=False`;
- `FlutterWebObjetivo.preparar` con un `build_dir` temporal sirve su `index.html` en `127.0.0.1` y un puerto libre (`httpx.get` responde 200) y `destruir` cierra el puerto; con `host: 0.0.0.0` falla al cargar la config o al preparar;
- sin `build_dir` y con `flutter.proyecto`, `preparar` llama al runner con `build web --release` en la copia de trabajo (nunca en el proyecto) y luego sirve `build/web`;
- `url_permitida` acepta su origen y un origen de `api_permitidas`, y rechaza otro; `pantalla("http://127.0.0.1:7480/#/login") == "login"`;
- un test con la marca `integracion` abre `tests/fixtures/flutter_web/index.html` en el Chromium real con `flutter=True` y comprueba que `observar` devuelve los dos campos y el botón con su etiqueta y una cobertura no ciega; córrelo con `uv run pytest -m integracion tests/test_flutter_web.py` y pega la salida en el PR.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 4h
- **Razón**: Playwright con el DOM de Flutter web y un servidor estático; tier estándar.
- **Dependencies**: F8.3.T1, F8.5.T1
- **Files**:
  - `src/dogfood/drivers/web.py`
  - `src/dogfood/objetivos/flutter_web/__init__.py`
  - `src/dogfood/objetivos/flutter_web/escenarios/login.yaml`
  - `src/dogfood/objetivos/flutter_web/escenarios/explorar.yaml`
  - `tests/fixtures/flutter_web/index.html`
  - `tests/test_flutter_web.py`

### F8.7.T2 — Integración M8 sin hardware: mobile-mao compilada a web

Verificación real del filtro web (no necesita celular). Usa el SDK de `/mnt/storage/flutter` (`export PATH=/mnt/storage/flutter/bin:$PATH PUB_CACHE=/mnt/storage/flutter/.pub-cache`).
- `tests/integracion/test_flutter_web.py` (marca `integracion`; se salta con el motivo si no existe `/mnt/storage/flutter/bin/flutter` o la app): con `flutter.proyecto = /mnt/storage/rupies/apps/mobile-mao` y `flutter.copia_trabajo` en un directorio temporal bajo `/mnt/storage/cache/dogfood/` (nunca en el home ni en el repo de la app), prepara el objetivo `flutter_web` (copia + `flutter build web --release`), abre la app con `DriverWeb(flutter=True)`, observa la pantalla inicial y la siguiente tras tocar el primer elemento clicable, y comprueba que hay al menos un elemento con etiqueta o, si no los hay, que la cobertura sale `ciega` y el detector de F8.3.T1 lo reportaría (arma un `ContextoDeteccion` mínimo con los árboles). Verifica al final que `/mnt/storage/rupies/apps/mobile-mao` no cambió (`git -C … status --porcelain` igual que antes).
- Córrelo a mano con `uv run pytest -m integracion tests/integracion/test_flutter_web.py -s` y escribe `docs/notas/m8-flutter-web.md` con lo que salió de **esa** corrida: versión de Flutter, tiempo de compilación, si compiló (y si no, el error y qué falta, p. ej. variables o Firebase), pantallas observadas, elementos e interactivos etiquetados por pantalla, si quedó ciega, capturas guardadas (ruta) y recomendaciones concretas de `Semantics`/`Key` para la app. Todo número sale de la corrida; si la compilación falla por algo de la app, documenta el fallo y deja el test saltándose con ese motivo, sin tocar la app.
- No dupliques lógica: usa `FlutterWebObjetivo`, `DriverWeb` y `flutter/semantica.py` tal como están.

Done when: el test de integración pasa (o se salta con un motivo documentado que viene de la corrida real), `uv run pytest` sin integración sigue verde, `docs/notas/m8-flutter-web.md` existe con los números de la corrida y el repo de `mobile-mao` quedó intacto.

- **Modelo**: claude/claude-sonnet-5-5
- **Estimación**: 3h
- **Razón**: Exploración con el SDK y un navegador reales; tier estándar, números solo de la corrida.
- **Dependencies**: F8.7.T1
- **Files**:
  - `tests/integracion/test_flutter_web.py`
  - `docs/notas/m8-flutter-web.md`

## F8.9 — Package: operación

### F8.9.T1 — Guías: Android real por Tailscale y Flutter

Documentación, sin código. Lee el código real (`drivers/adb_red.py`, `comandos/android.py`, `drivers/android.py`, `flutter/semantica.py`, `deteccion/flutter.py`, `deterministico/`, `frames/`, `config.py`, `objetivos/flutter_web/`) para que cada comando y opción exista. En español:
- `docs/ops/android.md`: actualiza la guía de F6 (quita el aviso de «estado de esta rama» que ya no aplica): emparejar y conectar con `dogfood android emparejar|conectar|estado`, qué hace la reconexión, cómo excluir Tailscale de la optimización de batería del teléfono, la configuración `driver:` y `pantalla:` (`screencap` contra `screenrecord`, que necesita `ffmpeg`), cómo ver la pantalla en la vista (`dogfood run --vista`) y en el panel («Dispositivos»), y la **lista de verificación manual pendiente para Héctor** con casillas: emparejar un celular por Tailscale; `dogfood android estado` en verde; login agéntico de punta a punta con `mobile-mao` instalada (captura, árbol y acción por paso en `runs/`); latencia de la vista < 2 s medida; un fallo provoca un issue con logcat; el escenario `login-determinista` con `--motor integration_test` aprobado; el hallazgo de pantalla ciega en una pantalla real; el spike de la opción B (D18).
- `docs/ops/flutter.md`: SDK en `/mnt/storage/flutter` (por qué no en el home, `PUB_CACHE`, cómo actualizarlo), `flutter.proyecto` y la copia de trabajo (nunca toca el repo de la app), cómo leer la cobertura de Semantics y los hallazgos `accesibilidad`, qué agregar en la app (`Semantics(label:, identifier:)`, `Key`/`ValueKey` en campos y botones del login y del pago), cómo escribir el bloque `deterministico` de un escenario, `integration_test` contra Patrol (qué configuración nativa pide Patrol: `patrol` en `dev_dependencies`, bloque `patrol:` del pubspec, runner de instrumentación en Android y target de UI tests en iOS), los secretos en `~/.config/dogfood/flutter.env` (`DOGFOOD_APP_EMAIL`, `DOGFOOD_APP_CONTRASENA`), y el filtro web (`dogfood run --target flutter_web`), citando `docs/notas/m8-flutter-web.md` si existe.

No hay tests que escribir: la tarea termina cuando las dos guías existen, citan comandos y opciones que existen en el código y `uv run pytest` sigue verde.

- **Modelo**: claude/claude-haiku-5-5
- **Estimación**: 1.5h
- **Razón**: Documentación a partir de código ya escrito.
- **Dependencies**: F8.2.T1, F8.3.T2, F8.4.T2, F8.4.T3, F8.5.T3, F8.7.T1
- **Files**:
  - `docs/ops/android.md`
  - `docs/ops/flutter.md`

### F8.9.T2 — Guía: nodo iOS en el Mac M1

Documentación, sin código. Lee `nodos/`, `comandos/nodo.py`, `drivers/ios.py`, `objetivos/ios/` y `config.py`. Escribe `docs/ops/ios-nodo-mac.md` en español, como **puesta en marcha manual para Héctor** con casillas:
- requisitos: Mac M1 con macOS al día, Xcode y sus command line tools, cuenta de desarrollador de Apple (por qué la gratuita caduca a los 7 días), iPhone con modo desarrollador activado y confiando en el Mac;
- Tailscale en el Mac y SSH: activar «Sesión remota», clave SSH de guria en `~/.ssh/authorized_keys` del Mac (o Tailscale SSH), y comprobar `ssh -o BatchMode=yes hector@<ip-tailscale> true`; nunca exponer SSH, Appium ni el puerto 9100 fuera de Tailscale;
- instalar en el Mac: Homebrew, `uv`, Node (para Appium), `npm i -g appium`, `appium driver install xcuitest`, firmar WebDriverAgent con su equipo (abrir `WebDriverAgent.xcodeproj`, *Signing & Capabilities*, bundle id propio) y probar `appium` + una sesión; Flutter y `patrol_cli` si va a correr Patrol; dogfood (`uv tool install` desde el repo) para que `dogfood nodo` esté en el PATH;
- configurar `nodos:` y `driver:` (`tipo: ios`, `nodo`, `udid`, `bundle_id`) en `dogfood.yaml` de guria; `dogfood nodo estado --json` en el Mac y desde guria;
- correr el login agéntico (`dogfood run --target ios --driver ios --escenarios login --vista`) y el determinista (`--escenarios login-patrol`); ver la pantalla del iPhone en la vista y en «Dispositivos» del panel (MJPEG por el túnel SSH a `127.0.0.1:9100`);
- problemas comunes: WDA sin firmar, «device locked», Appium que no arranca, `Permission denied (publickey)`, el túnel que no abre porque el puerto local está ocupado.

No hay tests que escribir: la tarea termina cuando la guía existe, cita comandos y opciones que existen en el código y `uv run pytest` sigue verde.

- **Modelo**: claude/claude-haiku-5-5
- **Estimación**: 1h
- **Razón**: Documentación a partir de código ya escrito.
- **Dependencies**: F8.6.T2, F8.6.T4
- **Files**:
  - `docs/ops/ios-nodo-mac.md`
