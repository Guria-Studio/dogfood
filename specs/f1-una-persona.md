---
type: spec
project_id: dogfood
phase: 1
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
  - specs/f0-base.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-10-24
title: Una persona, de punta a punta
---

# F1 — Una persona, de punta a punta

M1 del PRD: dogfood levanta su propia instancia de predicts, genera un CSV sintético con su verdad, y una persona se registra, sube, mapea, analiza y exporta en un navegador real. La corrida queda guardada. FR-1 a FR-5, FR-7, FR-10, FR-22 y FR-23.

## F1.1 — Package: entorno predicts

### F1.1.T1 — Instancia aislada de predicts

Crea el paquete `src/dogfood/objetivos/predicts/` e implementa el entorno (arquitectura: decisión D3, *Interfaces → Protocolo Objetivo*, FR-1 a FR-4).

1. `__init__.py`: `PredictsObjetivo`, que implementa el protocolo de `objetivos/base.py`. `escenarios()` lee los YAML de `objetivos/predicts/escenarios/` con `dogfood.escenarios.cargar` si ese módulo existe, y si no devuelve `[]` (lo trae F1.3.T1). `verificadores()` devuelve `[oraculo.verificar, aislamiento.verificar, reglas.verificar]`.
2. Crea como **stubs** los módulos que llenan tareas posteriores; cada uno con su firma y un `return []` o un `NotImplementedError` documentado:
   - `cliente.py`: `PredictsCliente`;
   - `cuentas.py`;
   - `oraculo.py`, `aislamiento.py` y `reglas.py`, con `def verificar(ctx) -> list[Hallazgo]`;
   - `escenarios/.gitkeep`.
3. `entorno.py`:
   - `preparar(ref, corrida)` crea o actualiza un `git worktree` de `/mnt/storage/project/predicts` (la ruta se puede cambiar en `dogfood.yaml`) en `~/.cache/dogfood/predicts/<ref>`, en el commit de `ref`;
   - escribe un `docker-compose.override.yml` propio en la carpeta de la corrida, con web en 18080, api en 18100, postgres en 54330, `CORS_ORIGENES=http://localhost:18080` y `ENTORNO=dev`;
   - pasa las variables de `~/.config/dogfood/predicts.env` por `--env-file`;
   - corre `docker compose -p dogfood-predicts -f <worktree>/deploy/docker-compose.yml -f <override> up -d --build --wait`;
   - espera a que `GET http://localhost:18080/api/salud` responda 200 (timeout configurable, 10 minutos por defecto);
   - devuelve una `Instancia` con el commit y los parámetros efectivos (`MIN_COMPRAS`, `HORIZONTE_DIAS`, `VENTANA_VALIDACION_SEMANAS`, `CONFIANZA_MAPEO` y `CONFIANZA_JEV`, leídos del compose y del env).
   - `destruir()` hace `down -v --remove-orphans` sobre ese proyecto.
   - `logs(instancia, desde)` devuelve el texto de `docker compose logs --since` de `api` y `worker`.
   - **Nunca** toques el proyecto de compose `predicts` ni el puerto 8080.
4. `url_permitida(url, instancia)` acepta solo URLs con el origen exacto de `base_url` o de `api_url`.
5. `pantallas.py`: `pantalla(url)` mapea las rutas del panel (`web/src/routes/`: `login`, `registro`, `recuperar`, `restablecer`, `inicio`, `proyectos`, `datasets/...`, `analisis/...`, `demo`) a nombres estables (`registro`, `subir`, `mapeo`, `calidad`, `analisis`, `resultados`, `universo`, `agente`, `mensajes`, `productos`, `exportar`, `demo`). Lee los archivos de rutas de predicts para no inventar ninguna; una URL desconocida da `otra`.
6. `comandos/env.py`: implementa `dogfood env up|down --target predicts [--ref main]` con el objetivo del registro, e imprime las URLs.

Si `~/.config/dogfood/predicts.env` no existe, `preparar` falla con el mensaje de `docs/ops/prerequisitos.md` y nombra el archivo.

Done when: estos tests pasan.
- En `tests/test_predicts_entorno.py` (unitarios, con `subprocess` falseado):
  - el comando de compose usa `-p dogfood-predicts` y nunca `-p predicts`;
  - el override tiene los puertos 18080, 18100 y 54330;
  - `url_permitida` rechaza `http://localhost:8080/` y acepta `http://localhost:18080/api/x`;
  - sin `predicts.env`, el error nombra el archivo;
  - `pantalla("/datasets/abc/mapeo")` da `mapeo`.
- En `tests/integracion/test_predicts_entorno.py` (marcado `integracion`): `env up` y luego `/api/salud` dan 200, y `env down` no deja contenedores del proyecto. Córrelo a mano en el server antes de terminar. Si falta `~/.config/dogfood/predicts.env`, bloquea la tarea con `scripts/task-block.sh` explicando qué falta.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Orquestación de docker y git con cuidado de no tocar la instancia del dueño.
- **Dependencies**: F0.1.T4, F0.1.T5
- **Files**:
  - `src/dogfood/objetivos/predicts/__init__.py`
  - `src/dogfood/objetivos/predicts/entorno.py`
  - `src/dogfood/objetivos/predicts/pantallas.py`
  - `src/dogfood/objetivos/predicts/cliente.py`
  - `src/dogfood/objetivos/predicts/cuentas.py`
  - `src/dogfood/objetivos/predicts/oraculo.py`
  - `src/dogfood/objetivos/predicts/aislamiento.py`
  - `src/dogfood/objetivos/predicts/reglas.py`
  - `src/dogfood/objetivos/predicts/escenarios/.gitkeep`
  - `src/dogfood/comandos/env.py`
  - `tests/test_predicts_entorno.py`
  - `tests/integracion/test_predicts_entorno.py`

## F1.2 — Package: datos con verdad

### F1.2.T1 — Generador de ventas sintéticas con verdad conocida

Implementa `src/dogfood/datos/generador.py` y `src/dogfood/datos/perfiles.py` (arquitectura: *Componentes → Datos sintéticos*, *Modelo de datos → verdad.json*, FR-5, NFR-7).

`perfiles.py` define los rubros farmacia, pet shop, cosmética, café, e-commerce y agencia. Cada uno trae:
- un catálogo de 20 a 60 productos con nombre en pt-BR y en es, SKU y EAN-13 válido;
- un precio;
- un rango de ciclo verdadero en días (por ejemplo, farmacia 20–35 y café 10–20);
- una proporción de productos durables, que no se recompran.

`generador.py`, `generar(perfil, n_clientes, semilla, fecha_max, meses=12) -> DatasetSintetico`:
- por cliente, elige 1 a 6 productos;
- a cada par le asigna un `ciclo_real_dias` del rango del producto, con variación por cliente;
- simula las compras con intervalos log-normales (`sigma_log` por producto entre 0.15 y 0.4);
- un 10 % de los clientes abandona desde una fecha;
- un 15 % de los pares tiene menos de 3 compras;
- agrega cantidades, precio y número de pedido.

Escribe `ventas.csv` limpio (UTF-8, coma, ISO, encabezados en inglés neutro: `customer_id, order_id, date, sku, ean, product, qty, price`) y `verdad.json` con el formato de la arquitectura. Todo sale de `numpy.random.default_rng(semilla)`: la misma semilla da archivos idénticos byte a byte.

`comandos/datos.py`: `dogfood datos --perfil --clientes [--seed] [--salida]`. `--defectos` se declara, pero da «disponible en F2» y sale con código 2 si no viene vacío.

Done when: estos tests pasan en `tests/test_datos_generador.py`:
- la misma semilla da el mismo sha256 en los dos archivos;
- la mediana empírica de los intervalos de los pares con 8 compras o más está a ±15 % de `ciclo_real_dias` en al menos el 85 % de los pares;
- los pares marcados con menos de 3 compras tienen menos de 3 fechas distintas;
- ningún cliente que abandonó compra después de `abandono_desde`;
- los EAN tienen dígito verificador válido;
- ninguna fecha es mayor que `fecha_max`.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 4h
- **Reason**: La verdad estadística es la base del oráculo; un error aquí da falsos positivos en un repo público.
- **Dependencies**: F0.1.T2, F0.1.T5
- **Files**:
  - `src/dogfood/datos/__init__.py`
  - `src/dogfood/datos/generador.py`
  - `src/dogfood/datos/perfiles.py`
  - `src/dogfood/comandos/datos.py`
  - `tests/test_datos_generador.py`

## F1.3 — Package: escenarios

### F1.3.T1 — Cargador de escenarios y escenarios iniciales de predicts

Implementa `src/dogfood/escenarios.py`:
- `cargar(carpeta) -> list[Escenario]`, que valida cada YAML con el modelo `Escenario` de `dominio.py` y da un error con el archivo y el campo;
- `compatibles(persona, escenarios) -> list[Escenario]`, según `persona_compatible`;
- `asignar(personas, escenarios, semilla) -> list[tuple[Persona, Escenario]]`, que es determinista y cubre cada escenario al menos una vez si hay personas compatibles.

Escribe los escenarios iniciales en `src/dogfood/objetivos/predicts/escenarios/`, uno por archivo, con el formato de *Interfaces → Escenario YAML*. Lee las pantallas reales en `/mnt/storage/project/predicts/web/src/routes/` para que el objetivo describa lo que la persona ve, sin inventar botones:
- `recompra-completa`;
- `demo` (probar con datos de ejemplo);
- `corregir-mapeo` (el agente debe cambiar al menos una columna sugerida);
- `calidad-antes-de-analizar`;
- `ofertas-con-lista` (sube también una lista de ofertas);
- `agente-analista` (hace tres preguntas sobre sus datos);
- `plantillas-mensaje` (edita una plantilla);
- `explorar-universo` (solo mirar y volver);
- `recuperar-contrasena`;
- `login-fallido` (`carril: login_fallido`: falla la contraseña tres veces y después entra bien).

El `criterio_exito` de cada uno es observable en la pantalla o en la descarga.

Done when: estos tests pasan en `tests/test_escenarios.py`:
- todos los YAML de predicts cargan;
- un YAML sin `criterio_exito` da un error que nombra el archivo;
- `asignar` con la misma semilla da la misma asignación;
- con 10 personas compatibles con todo, los 10 escenarios quedan cubiertos;
- `login-fallido` tiene `carril == "login_fallido"`.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Carga simple; los escenarios necesitan leer la UI real con criterio.
- **Dependencies**: F1.1.T1
- **Files**:
  - `src/dogfood/escenarios.py`
  - `src/dogfood/objetivos/predicts/escenarios/recompra-completa.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/demo.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/corregir-mapeo.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/calidad-antes-de-analizar.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/ofertas-con-lista.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/agente-analista.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/plantillas-mensaje.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/explorar-universo.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/recuperar-contrasena.yaml`
  - `src/dogfood/objetivos/predicts/escenarios/login-fallido.yaml`
  - `tests/test_escenarios.py`

## F1.4 — Package: agente

### F1.4.T1 — Agente navegador con personalidad

Implementa `src/dogfood/agente/navegador.py` y `src/dogfood/agente/prompts.py` (arquitectura: *Componentes → Agente*, decisiones D1, D2 y D7, FR-10 y FR-16).

`async def ejecutar(persona, escenario, instancia, dataset, carpeta: Path, llm, juez) -> Ejecucion`:
1. Lanza un Chromium headless **propio** con Playwright: contexto limpio, `accept_downloads=True` y la carpeta `descargas/`. Viewport de escritorio, o de móvil si la persona tiene el rasgo `movil`. Locale e idioma de la persona.
2. Usa el `Agent` de browser-use con el LLM del rol `persona`:
   - el prompt de sistema (`prompts.py`) describe a la persona (nombre, rubro, destreza, paciencia, estilo e idioma) y le pide actuar como ella, con sus errores típicos si su destreza es baja;
   - la tarea es el `objetivo` del escenario, más sus credenciales (email y contraseña para registrarse o entrar) y la ruta del CSV, ofrecida como `available_file_paths`;
   - hay que pasarle la URL inicial `instancia.base_url`.
3. Agrega dos herramientas: `anotar_friccion(texto, severidad)`, para cuando algo confunde o molesta, con la cita textual de la pantalla; y `rendirse(motivo)`, para cuando la persona dejaría la app.
4. Captura, con eventos de Playwright y sin pasar por el LLM:
   - la consola (`error` y `warning`);
   - la red (respuestas con estado ≥ 400 y peticiones fallidas, con método, URL, estado y ms);
   - una captura por paso en `capturas/`, y el texto visible del DOM en `Paso.texto_visible`;
   - las descargas.
   Escribe `pasos.jsonl`, `red.jsonl` y `consola.jsonl`.
5. Antes de cada navegación, bloquea toda URL que no cumpla `url_permitida` (FR-3), con `page.route`, y registra el intento como un evento de red con estado 0.
6. Corta en `max_pasos`, o en un timeout total configurable (15 minutos por defecto).
7. Guarda el historial de browser-use en `historial.json`, para el replay.
8. El juez (`llm.completar_json` con el rol `juez`) recibe el criterio de éxito, las últimas 5 capturas como texto o visión, la lista de descargas y el último estado, y devuelve `{exito: bool, motivo: str}`.

Cada llamada al LLM registra su `UsoLlm`. Nunca escribas la contraseña de la persona en los logs de dogfood; sí puede quedar en el historial local, que no se publica.

Done when: estos tests pasan en `tests/test_agente_navegador.py`, con un LLM falso que devuelve acciones guionadas, contra una página HTML local servida por la prueba (sin predicts):
- un guion que llena un formulario y descarga un archivo termina con `exito=True` y la descarga registrada;
- una respuesta 500 de la página de prueba queda en `red.jsonl`;
- un `console.error` queda en `consola.jsonl`;
- un enlace a un origen no permitido queda bloqueado y registrado;
- `anotar_friccion` agrega una `Friccion` con captura;
- al pasar `max_pasos`, el estado es `fallo` con el motivo `max_pasos`.

Además, prueba a mano una ejecución real contra la instancia de F1.1, si está levantada, y deja el resultado en el PR.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 6h
- **Reason**: Pieza central y la más difícil: integración con browser-use, captura de eventos y juez.
- **Dependencies**: F0.1.T3, F0.1.T4
- **Files**:
  - `src/dogfood/agente/__init__.py`
  - `src/dogfood/agente/navegador.py`
  - `src/dogfood/agente/prompts.py`
  - `tests/test_agente_navegador.py`
  - `tests/fixtures/pagina_prueba/index.html`

## F1.5 — Package: corrida

### F1.5.T1 — Orquestador de corrida, `dogfood run` y `dogfood runs`

Implementa `src/dogfood/corrida.py`, `comandos/run.py` y `comandos/runs.py` (arquitectura: *Componentes → Corrida*, FR-22 y FR-23).

`async def correr(opciones) -> Corrida`:
1. Crea la corrida en el almacén.
2. Llama a `objetivo.preparar(ref)`.
3. Genera un dataset por perfil necesario con `datos.generar`.
4. Arma las personas. **Por ahora** usa `persona_por_defecto(semilla, i)`, definida aquí: una persona fija y válida con email único `@dogfood.test`. F2.4.T1 la reemplaza por el generador.
5. Asigna escenarios con `escenarios.asignar`.
6. Ejecuta con `agente.ejecutar`, en serie (la concurrencia llega en F2.4).
7. Junta los logs con `objetivo.logs`.
8. Llama a `deteccion.ejecutar_detectores(ctx)`.
9. Guarda todo y cierra la corrida con su costo (suma de `uso_llm`).
10. Si no se pidió `--mantener-entorno`, llama a `objetivo.destruir`. Si la corrida falla, destruye el entorno igual y la deja con estado `error`.

`--sin-publicar` se acepta y por ahora no hace nada: la publicación llega en F4.

`dogfood runs` lista las corridas: id, fecha, objetivo, ref, personas, éxito por escenario, hallazgos y costo.

Done when: estos tests pasan en `tests/test_corrida.py`, con un `Objetivo` falso y un `agente.ejecutar` falso:
- una corrida con 2 personas guarda 2 ejecuciones y cierra con estado `ok`;
- si `preparar` falla, la corrida queda en `error` y `destruir` se llama igual;
- un detector falso que devuelve un hallazgo hace que `dogfood runs` muestre 1 hallazgo;
- el costo es la suma de los `UsoLlm` registrados;
- la misma semilla da la misma asignación.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Orquestación con contratos ya fijados.
- **Dependencies**: F1.1.T1, F1.2.T1, F1.3.T1, F1.4.T1
- **Files**:
  - `src/dogfood/corrida.py`
  - `src/dogfood/comandos/run.py`
  - `src/dogfood/comandos/runs.py`
  - `tests/test_corrida.py`

## F1.9 — Package: integración

### F1.9.T1 — Integración M1: una corrida real contra predicts

Escribe `tests/integracion/test_m1.py`, marcado `integracion`. Ejecuta `dogfood run --target predicts --personas 1 --escenarios recompra-completa --sin-publicar --seed 1` y comprueba:
- que la corrida quedó en el almacén;
- que la ejecución tiene pasos, capturas y un `historial.json`;
- que hay un CSV descargado;
- que la instancia se destruyó al final.

**Córrelo de verdad en el server.** Si falla por un bug de dogfood, arréglalo en el archivo que corresponda; puedes editar los archivos listados abajo. Si falla por un bug de predicts, es un hallazgo: anótalo en `docs/notas/m1-hallazgos.md` y no lo arregles. Si falta un prerrequisito de `docs/ops/prerequisitos.md`, bloquea la tarea con `scripts/task-block.sh` nombrando el archivo que falta.

Deja en el PR el resumen de la corrida: duración, pasos, costo y si el juez dio éxito.

Done when: `uv run pytest -m integracion tests/integracion/test_m1.py` pasa en el server y `uv run pytest` (sin integración) sigue pasando.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Prueba real de punta a punta; puede requerir ajustes en varias piezas.
- **Dependencies**: F1.5.T1
- **Files**:
  - `tests/integracion/test_m1.py`
  - `docs/notas/m1-hallazgos.md`
  - `src/dogfood/corrida.py`
  - `src/dogfood/agente/navegador.py`
  - `src/dogfood/agente/prompts.py`
  - `src/dogfood/objetivos/predicts/entorno.py`
