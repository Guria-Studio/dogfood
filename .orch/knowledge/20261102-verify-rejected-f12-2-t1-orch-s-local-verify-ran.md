---
id: 20261102-verify-rejected-f12-2-t1-orch-s-local-verify-ran
title: 'Verify rejected F12.2.T1: orch''s local verify ran `cd ''web'' && npm test` in your working dir and it …'
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
orch's local verify ran `cd 'web' && npm test` in your working dir and it failed (exit status 1):
```
…debar-wrapper"[39m
[33mstyle[39m=[32m"--sidebar-width: 16rem; --sidebar-width-icon: 3rem;"[39m
[36m>[39m
[36m<div[39m

The attempt that passed: Diffs en panel (api_diffs.py, lista/detalle/deslizador en web/src/features/diffs, entrada en Análisis) y en dogfood ci (sección «Cambios de comportamiento», diff_bloquea). Fix del rechazo: tests de web intermitentes con la máquina cargada; subí asyncUtilTimeout a 10 s en web/src/test/setup.ts y testTimeout en web/vite.config.ts. También toqué src/dogfood/proyectos.py (campos diff/diff_bloquea) y routeTree.gen.ts. Falta: capturas del detalle en el PR.
