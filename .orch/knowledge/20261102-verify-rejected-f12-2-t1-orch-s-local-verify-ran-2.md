---
id: 20261102-verify-rejected-f12-2-t1-orch-s-local-verify-ran-2
title: 'Verify rejected F12.2.T1: orch''s local verify ran `cd ''web'' && npm run build` in your working dir an…'
area:
    - src/dogfood/panel/api_diffs.py
    - src/dogfood/panel/app.py
    - src/dogfood/comandos/ci.py
    - tests/test_panel_diffs.py
    - tests/test_cli_ci.py
    - web/
tags:
    - verify
source: verify
task: F12.2.T1
created: "2026-11-02"
---

The local verify rejected an attempt at F12.2.T1:
orch's local verify ran `cd 'web' && npm run build` in your working dir and it failed (exit status 2):
```
… corresponding type declarations.
src/features/acciones/NuevaCorrida.tsx(87,45): error TS7006: Parameter 'r' implicitly has an 'any' type.
src/features/casos/DetalleCaso.tsx(54,25): error TS7006: Parameter 'p' implicitly has an 'any' type.
src/features/casos/DetalleCaso.tsx(54,28): error TS7006: Parameter 'i' implicitly has an 'any' type.

The attempt that passed: Diffs en panel (api_diffs.py, lista/detalle/deslizador, entrada en Análisis) y en dogfood ci (sección «Cambios de comportamiento», diff_bloquea). Fix del rechazo: web/src/api/schema.ts (generado, gitignored) faltaba en el worktree; regenerado con npm run gen:api, build, vitest y pytest verdes.
