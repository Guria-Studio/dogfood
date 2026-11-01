---
id: 20261101-verify-rejected-f10-2-t3-orch-s-local-verify-ran
title: 'Verify rejected F10.2.T3: orch''s local verify ran `cd ''web'' && npm run build` in your working dir an…'
area:
    - src/dogfood/panel/acciones.py
    - src/dogfood/panel/app.py
    - tests/test_panel_acciones.py
    - web/
tags:
    - verify
source: verify
task: F10.2.T3
created: "2026-11-01"
---

The local verify rejected an attempt at F10.2.T3:
orch's local verify ran `cd 'web' && npm run build` in your working dir and it failed (exit status 2):
```
> dogfood-web@0.1.0 build
> vite build && tsc --noEmit
vite v8.3.5 building client environment for production...
transforming...

The attempt that passed: Panel: acciones.py (POST /api/corridas, estado, replay, cancelar; 409 con corrida activa; X-Dogfood obligatorio) + UI Nueva corrida, progreso en vivo, Repetir caso y Cancelar. Fix del rechazo: el build fallaba por web/src/api/schema.ts (generado, gitignored) ausente; se regeneró con npm run gen:api. Tests, ruff y build en verde.
