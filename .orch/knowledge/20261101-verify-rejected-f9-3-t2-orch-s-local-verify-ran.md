---
id: 20261101-verify-rejected-f9-3-t2-orch-s-local-verify-ran
title: 'Verify rejected F9.3.T2: orch''s local verify ran `cd ''web'' && npm run build` in your working dir and…'
area:
    - web/src/routes/ayuda.tsx
    - web/src/routes/ayuda.$slug.tsx
    - web/src/features/ayuda/
tags:
    - verify
source: verify
task: F9.3.T2
created: "2026-11-01"
---

The local verify rejected an attempt at F9.3.T2:
orch's local verify ran `cd 'web' && npm run build` in your working dir and it failed (exit status 2):
```
> dogfood-web@0.1.0 build
> vite build && tsc --noEmit
vite v8.3.5 building client environment for production...
transforming...

The attempt that passed: Páginas de ayuda (portada con 6 tarjetas, buscador con debounce, documento con GFM/TOC/copiar/prev-sig) en web/src/features/ayuda; el fallo de build era el schema.ts generado (gitignored) que faltaba: se regeneró con npm run gen:api y build y 10 tests de vitest pasan.
