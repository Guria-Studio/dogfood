---
type: arch
project_id: dogfood
version: 0.1
depends_on:
  - docs/arch/001-usuarios-agenticos.md
generated_by: orch-arch
generated_at: 2026-11-01
title: Panel en React con Tailwind y shadcn, y página de ayuda — arquitectura
---

# Panel en React con Tailwind y shadcn, y página de ayuda — arquitectura

## Contexto

Hoy el panel (`src/dogfood/panel/`) es FastAPI con plantillas Jinja2 renderizadas en el servidor (5 pantallas: corridas, corrida, recorridos, ejecución y dispositivos), HTML y CSS propios y un poco de JS inline en el detalle. La vista en vivo (`src/dogfood/vista/`) es otra app FastAPI con su propia página y un websocket `/ws`. El panel se publica en `https://dogfood.knaimero.app` (túnel de Cloudflare + Access) y corre como servicio `dogfood-panel` en `127.0.0.1:7470`.

Héctor pide: rehacer el frontend con **Tailwind + shadcn/ui** y sumar una **página de ayuda** con un paso a paso de cómo funciona dogfood y una **base de conocimiento**.

Se copia el patrón de `predicts/web` (`/mnt/storage/project/predicts/web`): Vite + React 19 + TypeScript, Tailwind v4 (`@tailwindcss/vite`), componentes shadcn en `src/components/ui/` (Radix + `class-variance-authority` + `tailwind-merge`), TanStack Router y TanStack Query, `openapi-typescript` + `openapi-fetch` para tipar la API desde el OpenAPI de FastAPI, `lucide-react` para íconos. **No** se copian three.js, i18n ni recharts (el panel es solo en español y no tiene gráficos 3D).

## Componentes

### API JSON del panel (`src/dogfood/panel/api.py`)
Expone bajo `/api/` los mismos datos que hoy arman las plantillas, reutilizando `consultas.py`, `detalle.py`, `dispositivos.py` e `issue.py` sin cambiar su lógica. Cada ruta tiene `response_model` Pydantic para que el OpenAPI sea la fuente de tipos del frontend. Las rutas que ya no son HTML (`/archivos/{ruta}`, `/dispositivos/{id}/mjpeg`) se mantienen tal cual.

### API de ayuda (`src/dogfood/panel/ayuda.py`)
Sirve la base de conocimiento leyendo Markdown del repo, sin base de datos: `docs/ayuda/*.md` (contenido escrito para la ayuda) y `docs/ops/*.md` (guías de operación que ya existen). Cada documento tiene frontmatter `titulo`, `seccion` (`empezar` | `guias` | `referencia`), `orden` y `pantallas` (lista de slugs de pantalla donde aplica, para la ayuda en contexto). Búsqueda en memoria (tokens normalizados sin acentos, puntaje por título > encabezado > cuerpo), sin dependencias nuevas.

### Frontend (`web/`)
SPA de Vite. El build sale a `src/dogfood/panel/estatico/` (gitignored) y lo sirve FastAPI. Un layout común con barra lateral (Corridas, Recorridos, Dispositivos, Vista en vivo, Ayuda), encabezado de página con ⓘ (`PageHeader` con prop `ayuda`) y tema claro/oscuro.

### Servir la SPA (`src/dogfood/panel/spa.py`)
`montar_spa(app, carpeta)`: monta los assets y responde `index.html` a cualquier GET que no sea `/api/*`, `/archivos/*`, `/dispositivos/*/mjpeg`, `/ws` ni `/docs`/`/openapi.json` (fallback de SPA). Si la carpeta no existe, responde 503 con el texto «falta el build del panel: corre `scripts/build-web.sh`». La vista en vivo usa la misma función, así que comparte el build y su ruta `/vista` del SPA se conecta a `/ws` del mismo origen.

## Interfaces

### Rutas JSON (todas `GET` salvo la del issue)
| Ruta | Devuelve | Hoy sale de |
|---|---|---|
| `/api/ejecuciones?recorrido&resultado&version&persona&driver&motor` | `list[FilaEjecucion]` | `consultas.ejecuciones` |
| `/api/filtros` | `dict[str, list[Opcion]]` (`Opcion = {valor, etiqueta}`) | `consultas.opciones_filtro` |
| `/api/etiquetas` | `dict[str, str]` | `consultas.ETIQUETAS` |
| `/api/corridas/{id}` | `{resumen, comparacion}` | `consultas.corrida`, `comparacion_motores` |
| `/api/recorridos?objetivo=predicts` | `list[Recorrido]` | `consultas.recorridos` |
| `/api/ejecuciones/{id}` | `DetalleEjecucion` (ejecución, corrida, persona, pasos con URL de captura, video, trace, logcat, opinión por pantalla) | `detalle.py` |
| `POST /api/ejecuciones/{id}/issue` | `{url}` o error 4xx con `{codigo, detalle}` | `issue.publicar_issue` |
| `/api/dispositivos` | `list[Dispositivo]` | `dispositivos.py` |
| `/api/ayuda` | `list[DocAyuda]` (`slug, titulo, seccion, orden, pantallas`) | `ayuda.py` |
| `/api/ayuda/{slug}` | `{doc: DocAyuda, markdown: str}` | `ayuda.py` |
| `/api/ayuda/buscar?q=` | `list[{slug, titulo, fragmento, puntaje}]` (máx. 20) | `ayuda.py` |

Los 404 devuelven `{"detail": "..."}` como hoy. El POST del issue exige el header `X-Dogfood: 1` (protección CSRF simple: un formulario de otro sitio no puede ponerlo).

### Rutas del SPA
`/` corridas · `/corridas/$id` · `/recorridos` · `/ejecuciones/$id` · `/dispositivos` · `/vista` · `/ayuda` · `/ayuda/$slug`. Los filtros de la lista van en la query string (se puede compartir el link).

### Slugs de pantalla para la ayuda en contexto
`corridas`, `corrida`, `recorridos`, `ejecucion`, `dispositivos`, `vista`. El ⓘ de cada pantalla abre `/ayuda?pantalla=<slug>`, que lista los documentos con ese slug en `pantallas`.

### Build
`scripts/build-web.sh`: `cd web && npm ci && npm run gen:api && npm run build`. `gen:api` lee el OpenAPI con `uv run python -m dogfood.panel.openapi > web/src/api/openapi.json` (sin levantar el servidor). `openapi.json` y `schema.ts` son generados y gitignored. CI: workflow nuevo `.github/workflows/web.yml` (path-filter `web/**`, `src/dogfood/panel/**`, `docs/ayuda/**`) con `actions/setup-node`, `npm ci`, lint, `tsc`, vitest y build; `runs-on: ${{ vars.RUNNER || 'ubuntu-latest' }}`.

## Decisiones

- **D1 — SPA de React con shadcn, no Tailwind sobre Jinja.** Elegido: SPA, porque shadcn son componentes React y Héctor ya usa ese stack en predicts. Descartado: Tailwind en las plantillas Jinja (menos trabajo, pero sin shadcn).
- **D2 — Un solo build para panel y vista.** Elegido: la vista sirve la misma SPA y su página `/vista` usa el `/ws` de su origen. Descartado: dos frontends.
- **D3 — Base de conocimiento en Markdown del repo.** Elegido: archivos en `docs/ayuda/` y `docs/ops/`, servidos por la API; la doc y la ayuda no se desincronizan. Descartado: CMS o base de datos.
- **D4 — Búsqueda en memoria sin dependencias.** Son decenas de documentos; un índice simple alcanza. Descartado: SQLite FTS o Lunr en el cliente.
- **D5 — Markdown renderizado en el cliente** con `react-markdown` + `remark-gfm` (tablas y listas de tareas), estilado con `@tailwindcss/typography`. Descartado: renderizar HTML en el servidor (exigiría sanear HTML).
- **D6 — Las plantillas Jinja se borran al final** (F9.9), cuando el e2e confirma que el SPA cubre todo. Mientras tanto conviven: el SPA vive en `/` sólo cuando existe el build.

## Riesgos

- **El runner no tiene Node.** *Mitigación:* `actions/setup-node` en el workflow; en el server ya hay Node 26 en `~/.hermes/tools/node-26.12.1-linux-x64/bin`, y el servicio `dogfood-panel` necesita el build hecho antes (`scripts/build-web.sh`).
- **Romper el panel publicado mientras se migra.** *Mitigación:* D6, y el redeploy del servicio solo se hace en F9.9 tras el e2e verde.
- **Cloudflare Access corta el websocket de la vista.** *Mitigación:* Access deja pasar websockets del mismo origen ya autenticado; se verifica en F9.9.

## Cobertura

| Pedido | Componente |
|---|---|
| Frontend con Tailwind + shadcn | `web/`, `spa.py` |
| Paso a paso de cómo funciona | `docs/ayuda/como-funciona.md`, página `/ayuda` |
| Base de conocimiento | `ayuda.py`, `docs/ayuda/*`, `docs/ops/*`, búsqueda |
| Ayuda en contexto | `PageHeader` con ⓘ, `pantallas` en el frontmatter |

## Desglose del trabajo

### F9 — Panel en React y ayuda
- **F9.1 — api**: T1 rutas JSON + `spa.py` + `openapi.py` (`src/dogfood/panel/api.py`, `spa.py`, `openapi.py`, `app.py`); T2 ayuda (`src/dogfood/panel/ayuda.py`), depende de T1 por `app.py`.
- **F9.2 — web**: T1 andamio (Vite, Tailwind, shadcn, router, layout, `PageHeader`, cliente API, CI `web.yml`, `scripts/build-web.sh`), depende de F9.1.T1; T2 corridas, corrida y recorridos; T3 detalle de ejecución con issue; T4 dispositivos y vista en vivo (incluye `vista/servidor.py`). T2–T4 dependen de T1 y no comparten archivos.
- **F9.3 — ayuda**: T1 contenido (`docs/ayuda/*.md` + frontmatter en `docs/ops/*.md`), sin dependencias; T2 páginas `/ayuda` y `/ayuda/$slug` con búsqueda, depende de F9.1.T2 y F9.2.T1.
- **F9.9 — cierre**: T1 e2e Playwright de todas las pantallas, borrar plantillas Jinja, actualizar `docs/ops/panel-y-vista.md` y redesplegar el servicio, depende de todo F9.
