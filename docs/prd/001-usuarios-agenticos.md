---
type: prd
project_id: dogfood
version: 0.4
generated_by: orch-prd
generated_at: 2026-11-01
title: Usuarios agénticos para predicts
---

# Usuarios agénticos para predicts

## Problema

predicts (repo público `hectorcanaimero/predicts`, en el homelab con `deploy/docker-compose.yml`) predice cuándo cada cliente vuelve a comprar cada producto a partir de un CSV.

El flujo completo tiene muchos pasos y cada uno puede fallar de forma silenciosa:
- registro;
- proyecto;
- subir el CSV;
- mapear columnas (con Jev);
- informe de calidad;
- análisis (recompra, ofertas, riesgo, ciclos);
- resultados, universo 3D y agente analista;
- plantillas de mensaje;
- exportar.

Sus tests prueban lo que el equipo ya pensó, con CSV limpios. Nadie lo usa como lo haría un analista de CRM de verdad: alguien que exporta de su ERP un CSV con punto y coma, fechas `dd/mm/aa`, codificación Latin-1, EAN como notación científica, filas duplicadas y la mitad de los clientes con una sola compra.

Además, predicts promete números medidos («nunca inventados»): un error en el ciclo de recompra o en el backtest no rompe la pantalla, solo da una respuesta equivocada que nadie nota.

dogfood crea una población de usuarios sintéticos con personalidad que usan predicts de verdad, en un navegador y en el homelab. Les da CSV sintéticos con la respuesta correcta conocida y entrega dos cosas: issues reproducibles en GitHub y la opinión de esos usuarios.

## Usuarios

- **Héctor (dueño de predicts):** quiere saber qué está roto, qué da números equivocados y qué molesta, antes de mostrar predicts en público.
- **Agentes de orch que trabajan en predicts:** reciben los issues como tareas, así que necesitan pasos para reproducir que se puedan ejecutar.

## Metas

- G1 — Una corrida manual encuentra fallos que los tests de predicts no cubren. Cada fallo llega como issue con pasos para reproducir, evidencia y gravedad.
- G2 — Una corrida simula más de 100 usuarios distintos, cada uno con su propia empresa y cuenta creadas por el registro real.
- G3 — dogfood detecta predicciones equivocadas: compara lo que predicts devuelve con la verdad conocida de cada CSV sintético.
- G4 — Cada corrida produce un reporte de opinión, en español, por pantalla y por tipo de usuario.
- G5 — Ninguna corrida toca la instancia de desarrollo que Héctor usa, ni deja datos en ella.
- G6 — El motor del agente es intercambiable: Claude Code con el plan Max (sin pagar computer use por API) o un backend por API, con resultado y costo comparables (issue #35).
- G7 — Los usuarios agénticos también prueban apps Android reales, con el mismo modelo de personas, escenarios, contratos y reporte (issue #32).
- G8 — Lo que hacen los agentes se ve en vivo y se revisa después en un panel, sin leer logs (issues #33 y #34).
- G9 — Las apps Flutter de Héctor (p. ej. `mobile-mao` y `mobile-empresa`) se prueban en celulares reales: Android por ADB sobre Tailscale e iPhone a través de un nodo en su Mac, con recorridos agénticos, recorridos deterministas (Patrol / `integration_test`) para lo crítico (login, pago) y un filtro web barato antes del celular (v0.4, issue #32).

## Fuera de alcance

- **Validar mercado:** los usuarios sintéticos no reemplazan conversaciones con equipos de CRM reales.
- **Disparo automático** desde un PR o un deploy. La v1 es manual.
- **La API pública con claves** como superficie de prueba propia. En la v1 solo se usa por el navegador.
- **Pruebas de carga:** concurrencia sí, estrés no. El homelab tiene 14 GB compartidos.
- **Showly, agenda-barberia y otros objetivos:** vienen después. El diseño no debe impedirlos.
- **Arreglar los bugs encontrados:** eso lo hacen orch o Héctor en predicts.

## Requisitos funcionales

### Entorno
- **FR-1** — `dogfood env up --target predicts [--ref main]` levanta en el homelab una instancia **propia y aislada** de predicts (proyecto de compose y puertos aparte de la instancia de desarrollo en `:8080`), desde una revisión del repo. *Aceptación:* `/api/salud` de la instancia de dogfood responde 200, mientras la instancia de `:8080` no cambia.
- **FR-2** — `dogfood env down` destruye la instancia y sus datos. Cada corrida parte de un estado limpio. *Aceptación:* después de `down` no quedan contenedores ni volúmenes de dogfood.
- **FR-3** — dogfood se niega a correr contra una URL que no sea la de su propia instancia (lista blanca). *Aceptación:* `--target-url http://localhost:8080` termina con error antes de crear usuarios.
- **FR-4** — La instancia de dogfood usa IA real (Jev y 9router) con las credenciales de `~/.config/dogfood/`, porque el mapeo, el agente analista y los mensajes son parte de lo que se prueba. *Aceptación:* el mapeo sugerido en una corrida trae la confianza de Jev, no un valor por defecto.

### Datos sintéticos con verdad conocida
- **FR-5** — Un generador produce CSV de ventas sintéticos a partir de clientes con ciclos de recompra **conocidos** por producto (más ruido, clientes que abandonan y productos durables). Junto a cada CSV guarda la verdad: el ciclo real por cliente y producto, la próxima compra esperada y quién abandonó. *Aceptación:* `dogfood datos --perfil farmacia --clientes 2000` produce un CSV y su archivo de verdad, reproducibles con la misma semilla.
- **FR-6** — El generador aplica «defectos de mundo real», configurables y combinables. *Aceptación:* cada defecto tiene al menos un CSV de ejemplo, y el informe de calidad de predicts debería señalarlo.
  - Separador `;` o tabulador.
  - Codificaciones Latin-1, Windows-1252 o UTF-8 con BOM.
  - Fechas `dd/mm/aaaa`, `mm/dd`, ISO o con hora.
  - Decimales con coma.
  - EAN en notación científica o con ceros a la izquierda perdidos.
  - Encabezados en pt o es, o sin encabezados.
  - Filas duplicadas, IDs vacíos y fechas futuras.
  - Archivos grandes (hasta el límite de predicts) o vacíos.
- **FR-7** — Los escenarios son datos (objetivo, persona compatible, CSV o perfil de datos, criterio de éxito observable), no código. *Aceptación:* agregar un escenario en un archivo hace que la siguiente corrida lo ejecute sin cambiar código.

### Población de usuarios
- **FR-8** — Un generador crea personas: nombre, empresa y rubro (farmacia, pet shop, cosmética, café, e-commerce, agencia), idioma (pt-BR o es), destreza con datos, paciencia e intención (análisis completo, explorar, solo exportar, confundirse, romper). *Aceptación:* `dogfood personas --n 120` produce 120 personas distintas, reproducibles con la misma semilla.
- **FR-9** — Cada persona se registra por el flujo real de `/registro` (empresa y dueño), inicia sesión y usa su propia cuenta. *Aceptación:* una corrida de 100 personas o más deja 100 empresas distintas o más en la instancia de dogfood.

### Agente
- **FR-10** — **Agente navegador:** hace el recorrido de la persona en un navegador real, en el idioma de la persona, hasta cumplir el objetivo, rendirse o llegar a un límite de pasos. Cubre:
  - registro, login y recuperación de contraseña;
  - proyectos;
  - subir el CSV;
  - mapeo (aceptar o corregir lo que sugiere Jev);
  - informe de calidad;
  - análisis con parámetros;
  - resultados y universo;
  - agente analista;
  - plantillas de mensaje;
  - grupos de productos;
  - exportar;
  - demo.
  *Aceptación:* el escenario «análisis de recompra completo» termina con un CSV exportado y descargado por el agente.
- **FR-11** — Los agentes corren en paralelo, con una concurrencia configurable. *Aceptación:* 100 personas con concurrencia 5 terminan sin interferir entre sí y sin que ningún contenedor supere su límite de memoria.

### Detección
- **FR-12** — **Fallos técnicos:** errores de consola, respuestas 4xx/5xx, pantallas en blanco, trabajos que no terminan dentro de un tiempo límite y excepciones en los logs de `api` y `worker` durante la corrida. *Aceptación:* un 500 provocado aparece como hallazgo con su log.
- **FR-13** — **Números equivocados:** dogfood compara lo que predicts devuelve con la verdad del CSV. Revisa:
  - el ciclo por cliente y producto;
  - la fecha de la próxima compra, que debe caer dentro del rango que predicts declara;
  - la precisión de backtest declarada, recalculada por dogfood;
  - el riesgo de abandono;
  - que el CSV exportado coincida con lo que muestra el panel.
  *Aceptación:* si el ciclo de recompra cambia en un día, aparece como hallazgo de lógica con el cliente, el producto, el valor esperado y el obtenido.
- **FR-14** — **Aislamiento entre empresas:** con varias cuentas, dogfood intenta leer proyectos, datasets, análisis y exportaciones de otra empresa por URL y por API con su sesión. *Aceptación:* cualquier respuesta distinta de 403/404 es un hallazgo crítico.
- **FR-15** — **Reglas propias de predicts:**
  - con poca historia no predice («se dice, no se predice»);
  - toda predicción trae su evidencia y su incertidumbre;
  - las decisiones de Jev bajo el umbral se le preguntan a la persona;
  - la interfaz no mezcla idiomas.
  *Aceptación:* un cliente con una sola compra que recibe una fecha predicha es un hallazgo.
- **FR-16** — Los agentes reportan fricción: cuando no entienden algo, repiten, se frustran o abandonan, lo registran con la pantalla y el texto exacto. *Aceptación:* cada escenario abandonado tiene al menos una nota de fricción con su captura.

### Reporte
- **FR-17** — Cada hallazgo trae:
  - título, pantalla y gravedad (crítica, alta, media o baja);
  - pasos para reproducir;
  - evidencia: capturas, red, logs y, si hay, el CSV que lo provoca;
  - el commit de predicts y la semilla.
  *Aceptación:* `dogfood replay <id>` repite los pasos y reproduce el fallo o informa que ya no se reproduce.
- **FR-18** — Los hallazgos se **deduplican** entre sí y contra los issues abiertos de dogfood en predicts. Una repetición se agrega como comentario con la nueva ocurrencia. *Aceptación:* dos corridas con el mismo bug dejan un issue con dos ocurrencias.
- **FR-19** — Los hallazgos nuevos se **publican como issues** en `hectorcanaimero/predicts` con las etiquetas `dogfood`, la pantalla y la gravedad, sin pedir aprobación. *Aceptación:* cada hallazgo nuevo tiene la URL de su issue en el reporte.
- **FR-20** — El reporte de opinión, en español, va por pantalla y por tipo de usuario. Dice qué no se entendió, qué frustró, qué sobró y qué funcionó, con citas y conteos. *Aceptación:* se genera en Markdown y HTML en la carpeta de la corrida.
- **FR-21** — Al terminar se envía un resumen a Slack: hallazgos por gravedad, issues, link al reporte, costo y duración. *Aceptación:* el mensaje llega al canal configurado.

### Operación
- **FR-22** — `dogfood run --target predicts [--personas N] [--escenarios …] [--seed S] [--ref main]` ejecuta todo de punta a punta: entorno, datos, población, agentes, detección, reporte y aviso. *Aceptación:* el comando sin más argumentos produce un reporte y sus issues.
- **FR-23** — Cada corrida queda guardada: personas, CSV y su verdad, pasos, capturas, hallazgos, modelos, tokens y costo. *Aceptación:* `dogfood runs` lista las corridas con su costo y el número de hallazgos.
- **FR-24** — Los modelos se eligen por rol (persona, juez de éxito, deduplicación y redacción) y son configurables. Varios modelos pueden tomar el mismo rol en una corrida, para comparar. *Aceptación:* el reporte muestra qué modelo hizo qué.
- **FR-25** — dogfood mide la consistencia: el mismo escenario varias veces da la tasa de éxito y la variación de los hallazgos. *Aceptación:* `dogfood run --repeat 3` reporta la tasa de éxito por escenario.

### Motores, drivers y observabilidad (v0.3, issues #32–#35)
- **FR-26** — **Motor intercambiable por rol** (#35). Cada rol (`persona`, `juez`, `dedupe`, `redactor`) elige en `dogfood.yaml` su backend: `api` (9router u otro endpoint compatible con OpenAI) o `claude_code` (`claude -p` en modo headless con la suscripción Max, salida JSON validada contra un esquema y MCPs opcionales con `--mcp-config`). Los dos cumplen el mismo contrato `BackendLlm`. *Aceptación:* el mismo escenario corre con `claude_code` y con `api`, y el panel compara resultado y costo; no hay claves en el repo; si `claude` no está instalado o no está autenticado, el backend falla con un mensaje que dice qué hacer.
- **FR-27** — **Control de costo del motor** (#35): el agente manda primero el árbol de UI en texto, adjunta como máximo `max_capturas_por_paso` capturas y las reduce a `resolucion_max`. Cada ejecución guarda tokens de entrada y salida, capturas enviadas, tiempo, costo cobrado y costo equivalente por API. *Aceptación:* con `max_capturas_por_paso: 0` ningún prompt lleva imagen; `dogfood runs` y el panel muestran las métricas por ejecución.
- **FR-28** — **Interfaz `Driver` común** (#32): el agente habla con la app solo por `observar()`, `actuar(acción)` y `evidencia()`. Hay un driver web (Playwright) y uno Android (ADB). *Aceptación:* el bucle del agente corre sin cambios con un driver falso, el web y el Android.
- **FR-29** — **Driver Android por ADB/UIAutomator** (#32): observa con `screencap` y `uiautomator dump` (elementos con texto, id y bounds); actúa con `input tap/text/swipe/keyevent`, `am start`, `am force-stop` e `adb install`; guarda `logcat` filtrado por paquete, `screenrecord` por ejecución y una captura por paso. Se configura en `dogfood.yaml` (`driver: android`, `serial` o `host:puerto`, `paquete`, `apk` opcional) y solo usa dispositivos reales por USB, localhost o Tailscale. *Aceptación:* (a) los tests con un `adb` falso cubren observar, actuar y evidencia; (b) **verificación manual pendiente**: un escenario de login corre de punta a punta en un Android real conectado por Tailscale, cada paso deja captura, árbol y acción en el almacén, y un fallo produce el mismo tipo de issue que el driver web (pasos, capturas, logcat, gravedad).
- **FR-30** — **Contrato de resultado**: cada ejecución termina como `aprobado`, `fallo` o `no_concluyente`. Sin evidencia observable (capturas de los pasos y motivo del juez) nunca es `aprobado`. *Aceptación:* una ejecución con `exito=True` y sin capturas es `no_concluyente`.
- **FR-31** — **Vista en vivo** (#33): `dogfood run --vista` sirve en `127.0.0.1` una página de solo lectura con la pantalla de cada ejecución en streaming (CDP `Page.startScreencast` en web; `scrcpy` o `screencap` a baja frecuencia en Android), la acción en curso marcada sobre la imagen y una columna de razonamiento con el paso del contrato. Varias ejecuciones en grilla, clic para ampliar. *Aceptación:* latencia menor a 1 s en web y a 2 s en Android; la columna de razonamiento muestra el paso que corresponde a la imagen; con 3 ejecuciones simultáneas la duración de la corrida no sube más de un 10 % respecto de correr sin vista.
- **FR-32** — **Panel de corridas** (#34): `dogfood panel` sirve en `127.0.0.1` los recorridos con su contrato (estado inicial, acciones, resultado esperado y evidencia requerida) y las ejecuciones con versión de la app, persona, driver, motor, resultado, duración y costo en tokens. El detalle por paso muestra captura, acción, razonamiento, esperado contra observado y consola/red (web) o logcat (Android); cada ejecución tiene su video y, en web, el *trace* de Playwright descargable; también la opinión de la persona por pantalla. Mismo estilo visual que el dashboard de orch. *Aceptación:* desde el panel se recorre cualquier ejecución paso a paso con su evidencia, y se filtra por recorrido, resultado, versión, persona, driver y motor.
- **FR-33** — **Crear issue desde el panel** (#34): el botón «Crear issue» publica en el repo configurado un issue con pasos, rutas de capturas y del video, y el comando de replay, pasado antes por la redacción de NFR-3 (secretos, emails y contraseñas de las personas, datos de prueba). *Aceptación:* el issue creado no contiene ningún secreto ni contraseña de las personas, y lleva la huella para la deduplicación de FR-18.

### Flutter en celular real (v0.4, issue #32)
- **FR-34** — **Android real por ADB sobre Tailscale.** `dogfood android emparejar <ip-tailscale>:<puerto>` corre `adb pair` (el código de 6 dígitos lo escribe Héctor en el prompt de `adb`; dogfood nunca lo guarda), `dogfood android conectar [<ip:puerto>]` conecta con el `driver.host_puerto` de `dogfood.yaml` y comprueba `get-state`, `dogfood android estado` lista los dispositivos y avisa de cualquiera fuera de USB, localhost o Tailscale, y de un servidor `adb` escuchando fuera de `127.0.0.1`. Si la conexión por Tailscale se cae durante una ejecución, el driver reconecta una vez antes de dar error. *Aceptación:* (a) los tests con un `adb` falso cubren emparejar, conectar, estado, el rechazo de destinos LAN/públicos y la reconexión; (b) **verificación manual pendiente** (`docs/ops/android.md`): un celular real emparejado por Tailscale corre el escenario de login de punta a punta.
- **FR-35** — **Soporte Flutter en Android.** El driver detecta una app Flutter (`io.flutter.embedding.android.FlutterView`/`FlutterActivity` en el árbol o la actividad) y mide en cada paso la cobertura de Semantics del árbol de `uiautomator`: nodos interactivos, cuántos tienen etiqueta (texto o `content-desc`) y cuántos tienen id estable (`resource-id`, que en Flutter sale de `Semantics(identifier:)`). Una pantalla «ciega» (Flutter con menos interactivos etiquetados que el umbral de `flutter.umbral_cobertura`, o sin nodos) es un **hallazgo de accesibilidad/testabilidad** con la pantalla, los números y la captura; en esa pantalla el agente recibe la captura aunque el árbol tenga elementos y actúa por coordenadas (respaldo por visión del motor). *Aceptación:* con árboles grabados de una pantalla Flutter etiquetada y de una ciega, la primera no da hallazgo y la segunda da uno de tipo `accesibilidad` con su cobertura; en la ciega el prompt del paso lleva la captura.
- **FR-36** — **Motor determinista Flutter.** Un escenario puede declarar `motor: patrol` o `motor: integration_test` y un bloque `deterministico` (archivo de test existente o pasos a generar). dogfood genera el test de Patrol / `integration_test` en una **copia de trabajo** de la app (nunca en su repo), lo corre con `patrol test` o `flutter test integration_test/… --reporter json` contra el dispositivo, y mapea el resultado al contrato: todo pasó con evidencia → `aprobado`; un test falló → `fallo`; error de compilación, sin dispositivo, timeout o cero tests → `no_concluyente`. Guarda el log, el reporte y la captura final como evidencia. Las credenciales van por `--dart-define`, nunca escritas en el test. *Aceptación:* los tests con un `flutter`/`patrol` falso cubren los tres resultados, el comando exacto y que la contraseña no aparece en el archivo generado; existen escenarios de ejemplo de login y de pago.
- **FR-37** — **Pantalla del celular real en la vista en vivo y el panel.** Una interfaz común de **fuente de frames** alimenta la vista: Android con `screencap` (por defecto) o `screenrecord` H.264 decodificado con `ffmpeg` (opcional, más fps); iPhone con el MJPEG de WebDriverAgent (puerto 9100). El panel suma una página «Dispositivos» con la pantalla en vivo de cada dispositivo configurado. *Aceptación:* con fuentes falsas, la vista recibe frames de cada tipo; la página de dispositivos sirve un stream MJPEG; la latencia objetivo sigue siendo < 2 s en Android (FR-31) y se mide en la verificación manual.
- **FR-38** — **Nodo iOS en el Mac.** guria manda trabajos por SSH sobre Tailscale a un **nodo** (el Mac M1 de Héctor con Xcode y un iPhone real): `dogfood nodo estado` informa Xcode, dispositivos y Appium; `dogfood nodo ejecutar` recibe un trabajo JSON por stdin (correr Patrol en el iPhone, o levantar una sesión de Appium XCUITest) y devuelve el resultado en JSON; los artefactos vuelven por `rsync`. Con una sesión de Appium, el bucle agéntico corre con un driver iOS (WebDriver/Appium por HTTP) igual que con Android. *Aceptación:* (a) los tests con `ssh`/`rsync`/Appium falsos cubren el protocolo, el runner del nodo, el driver iOS y el rechazo de hosts fuera de loopback/Tailscale; (b) **puesta en marcha manual pendiente** (`docs/ops/ios-nodo-mac.md`): Xcode, cuenta de desarrollador de Apple, WebDriverAgent firmado, Appium y un recorrido de login en el iPhone real.
- **FR-39** — **Filtro web barato.** El objetivo `flutter_web` sirve en `127.0.0.1` la app Flutter compilada a web (desde un `build/web` existente o compilándola con el SDK en una copia de trabajo) y el driver web habilita los Semantics de Flutter web (`flt-semantics`) para que el agente vea elementos con etiqueta; la cobertura se mide igual que en Android. *Aceptación:* con una página de prueba que imita Flutter web, el driver habilita Semantics y observa los elementos; una prueba de integración compila una copia de `mobile-mao` a web, la abre y reporta su cobertura en la pantalla inicial.

## Requisitos no funcionales

- **NFR-1 — Restricción:** Python 3.13 con uv. Modelos vía 9router o vía Claude Code con el plan Max (FR-26). El navegador es el Chrome del server o un Chromium que maneje dogfood, en el homelab. Android solo con dispositivos reales: el homelab no tiene KVM. iOS solo a través del nodo en el Mac de Héctor.
- **NFR-2 — Memoria:** el homelab tiene 14 GB compartidos con otros proyectos. La instancia de dogfood respeta los límites de memoria del compose de predicts; la concurrencia por defecto es de 5 navegadores y es configurable; ningún proceso de dogfood puede tumbar el servidor.
- **NFR-3 — Seguridad:** las credenciales (9router, Jev, GitHub) se leen de `~/.config/dogfood/*.env` y nunca aparecen en issues, reportes ni logs. Antes de publicar se eliminan los tokens y las cookies de la evidencia.
- **NFR-4 — Datos públicos:** predicts es un **repo público**. Todos los datos son sintéticos; un issue nunca lleva datos reales ni menciona al empleador de Héctor (regla de confidencialidad de predicts).
- **NFR-5 — Escala:** 120 personas con concurrencia 5 terminan en menos de 90 minutos.
- **NFR-6 — Costo:** no hay tope duro, por decisión de Héctor. Se mide y se muestra el costo por corrida, por rol y por modelo, e incluye la IA que consume la propia instancia de predicts (Jev y 9router). Existe un tope opcional que corta la corrida.
- **NFR-7 — Reproducibilidad:** la misma semilla y el mismo commit dan la misma población, los mismos CSV y la misma verdad.
- **NFR-8 — Ruido:** con la deduplicación de FR-18 y un umbral de gravedad configurable, una corrida sobre `main` sin cambios no abre más de 10 issues nuevos.
- **NFR-10 — Exposición:** la vista en vivo y el panel escuchan en `127.0.0.1` por defecto; solo aceptan otra dirección si es de Tailscale (`100.64.0.0/10`) y nunca `0.0.0.0`. ADB solo por USB, localhost o Tailscale; dogfood se niega a conectar a un `host:puerto` fuera de esos rangos.
- **NFR-11 — Vista sin costo de velocidad:** la vista descarta frames cuando un cliente va lento; nunca bloquea al agente.
- **NFR-12 — Exposición de dispositivos y nodos:** Appium, el MJPEG de WebDriverAgent y el SSH del nodo iOS solo se usan por loopback o Tailscale; dogfood rechaza otra dirección antes de conectar. El servidor `adb` local escucha solo en `127.0.0.1`. Ningún secreto (código de emparejamiento, certificados de Apple, claves SSH, credenciales de prueba) entra al repo ni a los logs.
- **NFR-13 — Pruebas sin hardware:** CI y los tests por defecto no llaman a `adb`, `flutter`, `patrol`, `ssh`, `rsync`, `ffmpeg` ni Appium reales (runners falsos inyectables). El SDK de Flutter vive en `/mnt/storage/flutter` (con su `PUB_CACHE`), nunca en el home. Lo que necesita celular real o el Mac es verificación manual documentada en `docs/ops/`.
- **NFR-9 — Extensible:** predicts es un «objetivo» con su entorno, sus pantallas, sus datos y sus verificaciones. Agregar Showly o agenda-barberia debe ser un objetivo nuevo, no cambios en el núcleo.

## Supuestos

- **Objetivo:** predicts, que corre en el homelab, en lugar de Showly. Showly sigue como posible segundo objetivo.
- **Dónde corre:** sobre una **instancia propia de dogfood** en el homelab, aparte de la de desarrollo en `:8080`. Así 100 cuentas o más no ensucian la instancia que Héctor usa y cada corrida parte limpia.
- **Cuentas:** cada persona crea su empresa por el registro público de predicts.
- **Recuperación de contraseña:** predicts en desarrollo no tiene SMTP. dogfood lee el token desde los logs de su instancia, y si no es posible, ese escenario queda fuera.
- **Issues:** se publican directo en predicts, sin aprobación. Hay deduplicación y un umbral de gravedad (NFR-8).
- **Idioma:** las personas usan pt-BR o es (por defecto 50/50) y la interfaz se pone en ese idioma. El reporte va en español. El inglés de la interfaz no se prueba en la v1.
- **Modelos:** todos vía 9router, sin tope de monto, con varios modelos por rol.
- **Disparo:** manual, por CLI.
- **Sin prueba previa:** se construye el agente directamente; M1 valida el camino completo con una sola persona.

## Preguntas abiertas

- **¿Hay un límite de registros o de rate limit en `/registro` y `/login` que frene 100 cuentas o más?** Si lo hay, la instancia de dogfood lo sube por configuración. Lo revisa la arquitectura.
- **¿La instancia de dogfood comparte la cuenta de Jev y 9router de desarrollo?** Propongo que sí, con el costo medido aparte (NFR-6). Lo decide Héctor.
- **¿A qué canal de Slack va el resumen?** Propongo el de proyectos (C0C84E42LDA).

## Milestones

- **M1 — Una persona, de punta a punta:** instancia aislada de predicts, un CSV sintético con verdad y una persona que se registra, sube, mapea, analiza y exporta. La corrida queda guardada. FR-1, FR-2, FR-3, FR-4, FR-5, FR-7, FR-10, FR-22, FR-23.
- **M2 — Población y datos del mundo real:** más de 100 personas en pt-BR y es, cada una con su empresa, en paralelo, con CSV con defectos reales. FR-6, FR-8, FR-9, FR-11.
- **M3 — Detección:** fallos técnicos, números equivocados frente a la verdad, aislamiento entre empresas, reglas propias de predicts y notas de fricción. FR-12, FR-13, FR-14, FR-15, FR-16.
- **M4 — Issues y reporte:** hallazgos reproducibles, deduplicados y publicados en GitHub, reporte de opinión y aviso en Slack. FR-17, FR-18, FR-19, FR-20, FR-21.
- **M5 — Modelos y consistencia:** modelos por rol, comparación entre modelos y tasa de éxito por repetición. FR-24, FR-25.
- **M6 — Motores intercambiables y Android:** backend `claude_code` junto al de API, interfaz `Driver` con driver web y Android, bucle de agente propio y contrato de resultado. FR-26, FR-27, FR-28, FR-29, FR-30, NFR-10.
- **M7 — Vista en vivo y panel:** streaming de la pantalla con razonamiento y panel de corridas con evidencia, video, costo y «Crear issue». FR-31, FR-32, FR-33, NFR-11.
- **M8 — Flutter en celular real:** Android real por Tailscale, cobertura de Semantics y respaldo por visión, motor determinista Patrol / `integration_test`, pantalla real en vista y panel, nodo iOS en el Mac y filtro web. FR-34, FR-35, FR-36, FR-37, FR-38, FR-39, NFR-12, NFR-13. La prueba con dispositivos reales (Android e iPhone) queda como verificación manual hasta que Héctor los conecte.
