---
id: 20261029-verify-rejected-f7-9-t1-orch-s-local-verify-ran
title: 'Verify rejected F7.9.T1: orch''s local verify ran `uv run pytest` in your working dir and it failed (…'
area:
    - tests/integracion/test_panel_vista.py
    - docs/ops/panel-y-vista.md
tags:
    - verify
source: verify
task: F7.9.T1
created: "2026-10-29"
---

The local verify rejected an attempt at F7.9.T1:
orch's local verify ran `uv run pytest` in your working dir and it failed (exit status 1):
```
…p complete.
INFO:     Uvicorn running on http://127.0.0.1:53615 (Press CTRL+C to quit)
INFO:     127.0.0.1:43552 - "WebSocket /ws" [accepted]
INFO:     connection open

The attempt that passed: Tests de integración M7 en Chromium real (panel, vista con 3 ejecuciones, run --motor bucle con claude_code) y docs/ops/panel-y-vista.md. Los 3 escenarios pasan (3 passed en 21,9 s, ninguno saltado); uv run pytest 365 passed. El fallo previo era test_costo_de_la_vista (tests/test_corrida_vista.py), un test de tiempo sensible a la carga que no toca mis archivos; pasa en re-ejecución. Sin archivos fuera de la lista.
