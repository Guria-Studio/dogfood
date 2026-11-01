---
id: 20261101-verify-rejected-f9-2-t4-orch-s-local-verify-ran
title: 'Verify rejected F9.2.T4: orch''s local verify ran `cd ''web'' && npm run build` in your working dir and…'
area:
    - web/src/routes/dispositivos.tsx
    - web/src/routes/vista.tsx
    - web/src/features/vivo/
    - src/dogfood/vista/servidor.py
    - tests/test_vista_spa.py
tags:
    - verify
source: verify
task: F9.2.T4
created: "2026-11-01"
---

The local verify rejected an attempt at F9.2.T4:
orch's local verify ran `cd 'web' && npm run build` in your working dir and it failed (exit status 2):
```
> dogfood-web@0.1.0 build
> vite build && tsc --noEmit
vite v8.3.5 building client environment for production...
transforming...

The attempt that passed: Dispositivos y vista en vivo en web/src/features/vivo, rutas dispositivos/vista con PageHeader, y servidor.py monta la SPA y redirige / a /vista si hay build. El fallo del CI era solo que faltaba src/api/schema.ts (generado, gitignorado, se crea con npm run gen:api); build, vitest y pytest pasan.
