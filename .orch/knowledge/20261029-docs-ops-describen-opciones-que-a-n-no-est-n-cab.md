---
id: 20261029-docs-ops-describen-opciones-que-a-n-no-est-n-cab
title: Docs ops describen opciones que aún no están cableadas en dogfood run
area:
    - docs/ops/
    - src/dogfood/comandos/run.py
    - src/dogfood/corrida.py
    - src/dogfood/llm.py
tags:
    - docs
    - android
    - claude_code
    - wiring
source: agent
task: F6.8.T1
created: "2026-10-29"
---

En F6.8.T1 se documentó docs/ops/android.md y docs/ops/claude-code.md. En esta rama: `dogfood run` no tiene --driver (el driver sale de driver: en dogfood.yaml, pero corrida.py no lo lee todavía); el objetivo android no está en objetivos.OBJETIVOS (lo registra F6.6.T1); llm.backend_para no lo llama nadie, completar_json sigue en BackendApi, así que motores: claude_code no altera las corridas; dogfood panel y vista no existen aún (F7). Al cerrar tareas que cableen estas piezas, revisar los dos docs y quitar las notas de Estado.
