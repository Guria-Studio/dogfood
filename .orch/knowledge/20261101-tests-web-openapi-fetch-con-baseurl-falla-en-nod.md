---
id: 20261101-tests-web-openapi-fetch-con-baseurl-falla-en-nod
title: 'Tests web: openapi-fetch con baseUrl '''' falla en Node; y un build en panel/estatico rompe pytest'
area:
    - web/src/**
    - src/dogfood/panel/estatico/
tags:
    - vitest
    - openapi-fetch
    - spa
source: agent
task: F9.2.T3
created: "2026-11-01"
---

1) `cliente` (openapi-fetch, baseUrl '') hace `new Request('/api/...')`; en vitest/jsdom el Request de Node no acepta URLs relativas ("Failed to parse URL"), así que el fetch falso nunca se llama. openapi-fetch captura `globalThis.Request` al crear el cliente, así que hay que parchearlo en `vi.hoisted` antes del import: una subclase que haga `new URL(entrada, 'http://localhost')` cuando la entrada es un string. Ver web/src/features/ejecucion/ejecucion.test.tsx. El fetch falso recibe un Request: lee req.url, req.method y req.headers.
2) `npm run build` escribe en src/dogfood/panel/estatico/ (está en .gitignore). Si existe, el panel sirve la SPA y tests/test_panel.py falla. Bórralo antes de correr `uv run pytest`.
3) Antes de tsc/vitest corre `npm run gen:api`: src/api/schema.ts está en .gitignore. Además lucide-react 1.x ya no trae íconos de marcas (no hay Github).
