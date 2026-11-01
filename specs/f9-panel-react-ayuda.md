---
type: spec
project_id: dogfood
phase: 9
version: 0.1
depends_on:
  - docs/arch/002-panel-react.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-11-01
title: Panel en React y ayuda
---

# F9 — Panel en React y ayuda

Rehacer el panel y la vista en vivo con React + Tailwind + shadcn/ui y sumar una página de ayuda con el paso a paso de cómo funciona dogfood y una base de conocimiento con búsqueda. Arquitectura: `docs/arch/002-panel-react.md`. Referencia de stack: `/mnt/storage/project/predicts/web` (léelo antes de empezar; copia su patrón, no su contenido).

## F9.1 — Package: api

### F9.1.T1 — API JSON del panel y servidor de la SPA

Implementa *Componentes → API JSON del panel* y *Servir la SPA* de la arquitectura.

1. `src/dogfood/panel/api.py`: `registrar_api(app, raiz, cfg)` con todas las rutas de la tabla *Interfaces → Rutas JSON*, **salvo las de `/api/ayuda`** (son de F9.1.T2). Reutiliza `consultas.py`, `detalle.py`, `dispositivos.py` e `issue.py`; si una función devuelve dataclasses o tuplas, define modelos Pydantic de respuesta en `api.py` y convierte ahí, sin cambiar la lógica de esos módulos. Para el detalle de ejecución, extrae en `detalle.py` una función pura `datos_ejecucion(raiz, ejecucion_id) -> dict` que usen tanto la ruta HTML actual como la JSON (único cambio permitido en `detalle.py`). El `POST /api/ejecuciones/{id}/issue` exige el header `X-Dogfood: 1` (sin él, 403).
2. `src/dogfood/panel/spa.py`: `montar_spa(app, carpeta: Path)` como dice la arquitectura (assets, fallback a `index.html`, 503 con el mensaje de `scripts/build-web.sh` si falta el build). No intercepta `/api/*`, `/archivos/*`, `/dispositivos/*/mjpeg`, `/ws`, `/docs` ni `/openapi.json`.
3. `src/dogfood/panel/openapi.py`: `python -m dogfood.panel.openapi` imprime el OpenAPI de `crear_app_panel` (con una raíz temporal vacía) sin levantar el servidor.
4. `src/dogfood/panel/app.py`: registra la API y, **solo si existe** `src/dogfood/panel/estatico/index.html`, monta la SPA en `/`. Si no existe, las rutas HTML Jinja de hoy siguen respondiendo igual (convivencia, decisión D6).
5. Agrega `src/dogfood/panel/estatico/` y `web/src/api/openapi.json`, `web/src/api/schema.ts` a `.gitignore`.

Done when: estos tests pasan en `tests/test_panel_api.py` (con un `runs/` de prueba armado con el almacén, como hacen `tests/test_panel.py` y `tests/test_panel_detalle.py`):
- `/api/ejecuciones` devuelve las filas y respeta cada filtro;
- `/api/corridas/{id}` trae resumen y comparación, y da 404 con una corrida inexistente;
- `/api/ejecuciones/{id}` trae pasos con URL de captura que responde 200 en `/archivos/...`;
- el POST del issue sin `X-Dogfood` da 403, y con el header llama a `publicar_issue` (falseado);
- `/openapi.json` incluye todas las rutas `/api/*` con sus esquemas;
- con un `estatico/index.html` de prueba, `GET /ejecuciones/x` devuelve ese HTML y `/api/filtros` sigue devolviendo JSON; sin el build, `/` responde la página Jinja de hoy;
- los tests existentes del panel siguen verdes.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Adaptar rutas existentes a JSON con contratos claros; standard alcanza.
- **Dependencies**:
- **Files**:
  - `src/dogfood/panel/api.py`
  - `src/dogfood/panel/spa.py`
  - `src/dogfood/panel/openapi.py`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/panel/detalle.py`
  - `.gitignore`
  - `tests/test_panel_api.py`

### F9.1.T2 — API de la base de conocimiento

Implementa *Componentes → API de ayuda* y las rutas `/api/ayuda*` de la arquitectura en `src/dogfood/panel/ayuda.py`, con `registrar_ayuda(app, raiz_repo: Path)` llamado desde `app.py` (única línea que agregas ahí).

- Lee `docs/ayuda/*.md` y `docs/ops/*.md` con frontmatter YAML (`titulo`, `seccion`, `orden`, `pantallas`). Un archivo sin frontmatter entra con `titulo` = primer encabezado `#`, `seccion: guias`, `orden: 100`, `pantallas: []`. El slug es el nombre del archivo sin `.md`, con prefijo `ops-` para los de `docs/ops/`.
- `/api/ayuda?pantalla=<slug>` filtra por pantalla. La lista va ordenada por sección (`empezar`, `guias`, `referencia`) y `orden`.
- `/api/ayuda/buscar?q=`: búsqueda sin dependencias nuevas, sin acentos y sin mayúsculas; puntaje título 3, encabezado 2, cuerpo 1; `fragmento` de ~160 caracteres alrededor de la primera coincidencia; máximo 20 resultados; `q` vacío o de menos de 2 caracteres devuelve `[]`.
- Cachea el índice y lo rehace si cambia el `mtime` de algún archivo (así la ayuda se actualiza sin reiniciar).
- Un slug con `/` o `..` da 404 (nada de leer fuera de las carpetas).

Done when: estos tests pasan en `tests/test_panel_ayuda.py`, con carpetas de docs falsas en `tmp_path`:
- un doc con frontmatter sale con sus campos y uno sin frontmatter con los valores por defecto;
- el filtro por pantalla y el orden por sección funcionan;
- buscar «vista» encuentra antes el doc con «vista» en el título que el que solo lo tiene en el cuerpo, y «corrída» encuentra «corrida»;
- `/api/ayuda/..%2F..%2Fetc` da 404;
- editar un archivo cambia el resultado de la búsqueda sin reiniciar la app.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 2h
- **Reason**: Lectura de archivos y búsqueda simple.
- **Dependencies**: F9.1.T1
- **Files**:
  - `src/dogfood/panel/ayuda.py`
  - `src/dogfood/panel/app.py`
  - `tests/test_panel_ayuda.py`

## F9.2 — Package: web

### F9.2.T1 — Andamio del frontend: Vite, Tailwind, shadcn y layout

Crea `web/` siguiendo el patrón de `/mnt/storage/project/predicts/web` (*Componentes → Frontend* e *Interfaces → Build* de la arquitectura).

1. Vite + React 19 + TypeScript estricto, Tailwind v4 con `@tailwindcss/vite`, `@tailwindcss/typography`, shadcn/ui (`components.json`, `src/lib/utils.ts` con `cn`, y en `src/components/ui/` los componentes que usarán las pantallas: `button`, `card`, `badge`, `table`, `input`, `select`, `tabs`, `dialog`, `tooltip`, `skeleton`, `separator`, `sheet`, `toast`/`sonner`, `scroll-area`), `lucide-react`, TanStack Router (rutas por archivo en `src/routes/`) y TanStack Query, `openapi-typescript` + `openapi-fetch` (`src/api/cliente.ts`). Instala **ya** también `react-markdown` y `remark-gfm` (los usa F9.3.T2), para que ninguna otra tarea toque `package.json` ni `package-lock.json`.
2. `vite.config.ts`: `build.outDir` = `../src/dogfood/panel/estatico`, `emptyOutDir: true`; en dev, proxy de `/api`, `/archivos`, `/dispositivos` y `/ws` a `http://127.0.0.1:7470`.
3. Layout en `src/components/layout/`: barra lateral con Corridas, Recorridos, Dispositivos, Vista en vivo y Ayuda (en móvil, un `sheet`), selector de tema claro/oscuro guardado en `localStorage`, y `PageHeader({titulo, descripcion?, ayuda?: SlugPantalla, acciones?})` que muestra un botón ⓘ con tooltip «Ayuda de esta pantalla» que navega a `/ayuda?pantalla=<slug>`.
4. Una ruta stub por pantalla (`/`, `/corridas/$id`, `/recorridos`, `/ejecuciones/$id`, `/dispositivos`, `/vista`, `/ayuda`, `/ayuda/$slug`), cada una con su `PageHeader` y el texto «en construcción». Son de las tareas F9.2.T2–T4 y F9.3.T2: cada una reemplaza solo sus archivos de ruta.
5. `scripts/build-web.sh` (`npm ci`, `gen:api` con `uv run python -m dogfood.panel.openapi`, build) y `.github/workflows/web.yml` (path-filter `web/**`, `src/dogfood/panel/**`, `docs/ayuda/**`; `runs-on: ${{ vars.RUNNER || 'ubuntu-latest' }}`; `astral-sh/setup-uv` + `actions/setup-node` con Node 22; `npm ci`, `npm run lint`, `npx tsc --noEmit`, `npx vitest run`, build).
6. Todo el texto de la interfaz en español.

Done when: `bash scripts/build-web.sh` termina sin errores y deja `src/dogfood/panel/estatico/index.html`; `uv run dogfood panel` sirve el layout en `/` y cualquier ruta del SPA; y estos tests pasan en `web/src/components/layout/layout.test.tsx` (vitest + Testing Library):
- la barra lateral tiene los 5 enlaces;
- `PageHeader` con `ayuda="corridas"` muestra el ⓘ con link a `/ayuda?pantalla=corridas`, y sin `ayuda` no lo muestra;
- el selector de tema alterna la clase `dark` en `<html>` y la recuerda.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Andamio con muchas piezas pero conocidas; el patrón ya existe en predicts.
- **Dependencies**: F9.1.T1
- **Files**:
  - `web/`
  - `scripts/build-web.sh`
  - `.github/workflows/web.yml`

### F9.2.T2 — Pantallas de corridas, corrida y recorridos

Reemplaza los stubs `web/src/routes/index.tsx`, `web/src/routes/corridas.$id.tsx` y `web/src/routes/recorridos.tsx` con las pantallas reales, consumiendo la API de F9.1.T1 con TanStack Query. Mira las plantillas Jinja actuales (`src/dogfood/panel/plantillas/corridas.html`, `corrida.html`, `recorridos.html`) para no perder ningún dato.

- Pantalla **Corridas** (`/`): tabla shadcn de ejecuciones con badges de resultado (éxito verde, rendido ámbar, fallo rojo, no concluyente gris), filtros con `select` sincronizados con la query string, estados de carga con `skeleton` y vacío con un mensaje que lleva a la ayuda «cómo correr dogfood». Clic en una fila va a `/ejecuciones/$id`.
- Pantalla **Corrida** (`/corridas/$id`): tarjetas de resumen (personas, éxito, hallazgos, costo, duración) y la tabla de comparación de motores.
- Pantalla **Recorridos**: conteo de resultados por recorrido con barras simples hechas con Tailwind (sin librería de gráficos).
- `PageHeader` con `ayuda` = `corridas`, `corrida` y `recorridos`.
- Componentes propios de estas pantallas en `web/src/features/corridas/` (no en `components/ui/`).

Done when: estos tests pasan en `web/src/features/corridas/corridas.test.tsx`, con la API falseada (MSW o un `fetch` falso):
- la tabla muestra las filas y el badge correcto por resultado;
- cambiar un filtro actualiza la URL y vuelve a pedir `/api/ejecuciones` con ese parámetro;
- sin filas se muestra el estado vacío con el link a la ayuda;
- la corrida muestra el costo con dos decimales y la tabla de motores.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Pantallas de datos con componentes estándar.
- **Dependencies**: F9.2.T1
- **Files**:
  - `web/src/routes/index.tsx`
  - `web/src/routes/corridas.$id.tsx`
  - `web/src/routes/recorridos.tsx`
  - `web/src/features/corridas/`

### F9.2.T3 — Detalle de ejecución paso a paso con «Crear issue»

Reemplaza el stub `web/src/routes/ejecuciones.$id.tsx` por la pantalla de detalle, con todo lo que hoy muestra `src/dogfood/panel/plantillas/ejecucion.html` (léela entera).

- Visor de pasos: captura grande, acción, razonamiento, esperado/observado, y la consola y red de ese paso en `tabs`. Navegación con botones, línea de tiempo clicable y teclas ← / →.
- Debajo: video, link al `trace.zip` con el comando `uv run playwright show-trace trace.zip` copiable, logcat (en Android) y la opinión de la persona agrupada por pantalla.
- Tarjeta de la persona (nombre, idioma, destreza, intención) y de la corrida.
- Botón «Crear issue» que abre un `dialog` de confirmación con el título del issue y avisa que se publica en el repo configurado; hace el POST con `X-Dogfood: 1` y muestra el link del issue o el error en un toast.
- `PageHeader` con `ayuda="ejecucion"`. Componentes en `web/src/features/ejecucion/`.

Done when: estos tests pasan en `web/src/features/ejecucion/ejecucion.test.tsx`, con la API falseada:
- → y ← cambian de paso y la línea de tiempo marca el actual;
- la consola y la red del paso aparecen en sus pestañas;
- «Crear issue» no publica sin confirmar; al confirmar manda el POST con el header y muestra el link;
- un error 4xx del POST se muestra en un toast sin romper la pantalla.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 4h
- **Reason**: La pantalla más compleja y la que publica en GitHub.
- **Dependencies**: F9.2.T1
- **Files**:
  - `web/src/routes/ejecuciones.$id.tsx`
  - `web/src/features/ejecucion/`

### F9.2.T4 — Dispositivos y vista en vivo

1. Reemplaza `web/src/routes/dispositivos.tsx`: tarjetas por dispositivo con estado, plataforma y la imagen MJPEG en vivo de `/dispositivos/{id}/mjpeg` cuando está conectado. Mira `src/dogfood/panel/plantillas/dispositivos.html`.
2. Reemplaza `web/src/routes/vista.tsx`: se conecta por websocket a `/ws` del mismo origen y reproduce lo que hoy hace la vista (lee `src/dogfood/vista/servidor.py` y `src/dogfood/vista/estatico/`): una tarjeta por ejecución con el último frame, la pantalla, el razonamiento del paso y el rótulo de latencia; clic amplía la tarjeta (`dialog`), `Esc` la cierra. Si el websocket no conecta, muestra «no hay una corrida con vista activa» con el comando `uv run dogfood run --target predicts --vista` y reintenta cada 5 s.
3. `src/dogfood/vista/servidor.py`: si existe el build (`src/dogfood/panel/estatico/index.html`), monta la SPA con `montar_spa` y redirige `/` a `/vista`; si no, sigue sirviendo su página actual. No cambies el protocolo del `/ws`.
4. `PageHeader` con `ayuda` = `dispositivos` y `vista`. Componentes en `web/src/features/vivo/`.

Done when: estos tests pasan:
- en `web/src/features/vivo/vivo.test.tsx`, con un websocket falso: un mensaje de ejecución crea su tarjeta y uno nuevo actualiza el frame; sin conexión se ve el aviso y se reintenta;
- en `tests/test_vista_spa.py`: con un build de prueba la vista responde `/vista` con el `index.html` y `/ws` sigue funcionando; sin build, `/` responde la página de hoy;
- los tests existentes de la vista siguen verdes.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Websocket y MJPEG con contratos ya existentes.
- **Dependencies**: F9.2.T1
- **Files**:
  - `web/src/routes/dispositivos.tsx`
  - `web/src/routes/vista.tsx`
  - `web/src/features/vivo/`
  - `src/dogfood/vista/servidor.py`
  - `tests/test_vista_spa.py`

## F9.3 — Package: ayuda

### F9.3.T1 — Contenido de la ayuda: cómo funciona, glosario y preguntas frecuentes

Escribe la base de conocimiento en español, para alguien que nunca usó dogfood. Lee primero `docs/VISION.md`, `docs/prd/001-usuarios-agenticos.md`, `docs/arch/001-usuarios-agenticos.md`, `docs/ops/*.md` y `src/dogfood/contrato.py` (cómo se calcula cada resultado): todo dato debe salir de ahí, no inventes comandos ni opciones.

Archivos nuevos en `docs/ayuda/`, con el frontmatter de la arquitectura (`titulo`, `seccion`, `orden`, `pantallas`):
- `como-funciona.md` (`empezar`, orden 1, pantallas `corridas`): el paso a paso de una corrida en 6 pasos numerados (instancia aislada → datos con verdad conocida → personas → agentes en navegador o celular → detectores → issues y reporte), cada paso con qué hace, qué guarda en `runs/` y dónde se ve en el panel; un diagrama en texto (bloque de código) y un ejemplo real con la corrida M1 de `docs/notas/m1-hallazgos.md`.
- `primera-corrida.md` (`empezar`, orden 2, pantallas `corridas`, `vista`): prerequisitos mínimos y los comandos para la primera corrida, con `--sin-publicar` y `--vista`.
- `leer-una-ejecucion.md` (`guias`, pantallas `ejecucion`): qué significa cada parte del detalle y cuándo usar «Crear issue».
- `resultados.md` (`referencia`, pantallas `corridas`, `ejecucion`, `recorridos`): cada resultado posible y cuándo ocurre, según `contrato.py`.
- `glosario.md` (`referencia`): corrida, ejecución, persona, escenario, recorrido, objetivo, instancia, driver, motor, detector, hallazgo, huella, gravedad, fricción, oráculo, verdad, replay.
- `preguntas-frecuentes.md` (`referencia`): por qué un hallazgo no se publicó, por qué un 429 no es un error, qué hago si la vista no carga, cuánto cuesta una corrida, cómo conectar un Android, cómo pruebo una app Flutter.

Agrega también el frontmatter a cada `docs/ops/*.md` (`seccion: guias`, `pantallas` según su tema: `panel-y-vista.md` → `vista`, `corridas`, `ejecucion`; `android.md` y `flutter.md` → `dispositivos`), sin cambiar su contenido.

Sin tests de código: es documentación. Done when: los 6 archivos existen con su frontmatter válido (YAML que carga), cada comando citado aparece en `docs/ops/` o en `uv run dogfood --help`, y `uv run pytest` sigue verde.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Redacción técnica que debe ser fiel al código; haiku inventaría.
- **Dependencies**:
- **Files**:
  - `docs/ayuda/`
  - `docs/ops/prerequisitos.md`
  - `docs/ops/panel-y-vista.md`
  - `docs/ops/android.md`
  - `docs/ops/flutter.md`
  - `docs/ops/claude-code.md`

### F9.3.T2 — Páginas de ayuda con búsqueda

Reemplaza los stubs `web/src/routes/ayuda.tsx` y `web/src/routes/ayuda.$slug.tsx`, con la API de F9.1.T2.

- `/ayuda`: arriba un buscador (debounce de 250 ms) que muestra resultados con su fragmento resaltado; abajo, la portada con el paso a paso «Cómo funciona» como 6 tarjetas numeradas (título y una línea, link al documento) y el índice de documentos agrupado por sección (Empezar, Guías, Referencia). Con `?pantalla=<slug>`, muestra arriba «Ayuda para esta pantalla» con los documentos de esa pantalla.
- `/ayuda/$slug`: el Markdown renderizado con `react-markdown` + `remark-gfm` y estilos `prose` de `@tailwindcss/typography` (con `dark:prose-invert`), tabla de contenidos lateral con los `##`, botón para copiar cada bloque de código, y «anterior / siguiente» dentro de su sección. Los links relativos entre `.md` navegan dentro de la ayuda.
- Componentes en `web/src/features/ayuda/`.

Done when: estos tests pasan en `web/src/features/ayuda/ayuda.test.tsx`, con la API falseada:
- la portada muestra las 6 tarjetas y las tres secciones;
- escribir en el buscador pide `/api/ayuda/buscar` una sola vez tras el debounce y muestra los resultados;
- `?pantalla=ejecucion` muestra el bloque de ayuda de esa pantalla;
- un documento renderiza una tabla GFM, su índice lateral y el botón de copiar en un bloque de código;
- un link `[x](glosario.md)` navega a `/ayuda/glosario`.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: UI de lectura y búsqueda sobre una API simple.
- **Dependencies**: F9.1.T2, F9.2.T1
- **Files**:
  - `web/src/routes/ayuda.tsx`
  - `web/src/routes/ayuda.$slug.tsx`
  - `web/src/features/ayuda/`

## F9.9 — Package: cierre

### F9.9.T1 — E2E del panel nuevo, retiro de Jinja y redeploy

1. Escribe `web/e2e/panel.spec.ts` con Playwright (config en `web/playwright.config.ts`, siguiendo `predicts/web`): levanta `uv run dogfood panel` sobre un `runs/` de prueba (genera uno con el almacén en un script `web/e2e/preparar_runs.py`) y recorre: corridas → filtrar → abrir una ejecución → navegar pasos con el teclado → abrir el diálogo de issue y cancelar; recorridos; dispositivos (vacío); ayuda → buscar «glosario» → abrir el documento; el ⓘ de la pantalla de ejecución lleva a su ayuda; tema oscuro.
2. Con el e2e verde, borra `src/dogfood/panel/plantillas/` y las rutas HTML de `app.py`, `detalle.py` y `dispositivos.py` que ya no se usan (las de `/api`, `/archivos` y MJPEG quedan), y la página propia de la vista (`src/dogfood/vista/estatico/` y su ruta `/`) si la SPA la reemplaza. Ajusta los tests viejos que miraban HTML para que miren la API. Si falta el build, `dogfood panel` debe fallar con el mensaje de `scripts/build-web.sh` (código 2), no servir una página rota.
3. Actualiza `docs/ops/panel-y-vista.md` (cómo construir el frontend, desarrollo con `npm run dev`, el ⓘ y la ayuda), conservando su frontmatter.
4. En el server: corre `scripts/build-web.sh`, luego `systemctl --user restart dogfood-panel`, y verifica con `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:7470/ayuda` (200) y que `https://dogfood.knaimero.app/` siga redirigiendo al login de Cloudflare Access (302). Deja la salida en el PR.

Done when: `cd web && npx playwright test` pasa en el server, `uv run pytest` y el workflow `web.yml` están verdes, ya no queda ningún `.html` de Jinja en `src/dogfood/panel/`, y el panel publicado responde con la SPA.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Integración y limpieza; requiere correr de verdad en el server.
- **Dependencies**: F9.2.T2, F9.2.T3, F9.2.T4, F9.3.T1, F9.3.T2
- **Files**:
  - `web/e2e/`
  - `web/playwright.config.ts`
  - `src/dogfood/panel/plantillas/`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/panel/detalle.py`
  - `src/dogfood/panel/dispositivos.py`
  - `src/dogfood/vista/servidor.py`
  - `src/dogfood/vista/estatico/`
  - `docs/ops/panel-y-vista.md`
  - `tests/test_panel.py`
  - `tests/test_panel_detalle.py`
  - `tests/test_panel_dispositivos.py`
  - `tests/test_vista.py`
