---
id: 20261029-contratos-f6-evidencia-video-trace-motores-como
title: 'Contratos F6: Evidencia video/trace, Motores como str, BusVivo en el mismo loop'
area:
    - src/dogfood/drivers/
    - src/dogfood/backends/
    - src/dogfood/agente/bucle.py
    - src/dogfood/llm.py
    - src/dogfood/vista/
    - src/dogfood/almacen.py
tags:
    - f6
    - contratos
    - eventos
    - migracion
source: agent
task: F6.1.T1
created: "2026-10-29"
---

- `Evidencia.tipo` acepta además "video" y "trace": los drivers devuelven así la ruta del video y del trace.zip en `evidencia()`, y el bucle las pasa a `e.video` / `e.trace`.
- `cfg.motores.<rol>` es `str`, no Literal: `llm.backend_para` valida el valor y lanza ValueError con los válidos. `cfg.motores["persona"]` también funciona.
- `BusVivo.publicar` usa asyncio.Queue con put_nowait: llámalo desde el mismo event loop que los suscriptores (no desde otro hilo). `Suscripcion` es async-iterable y tiene `close()`; la cola se expone como `sub.cola`.
- `ElementoUI.centro` da el (x, y) central de bounds; reúsalo para tap/clic en vez de recalcularlo.
- `uv run ruff format .` también reformatea los bloques de código de docs/*.md; revierte esos cambios si tu tarea no toca docs.
- Las migraciones del almacén van en `almacen.MIGRACIONES[n]`; para una v3, sube VERSION_ESQUEMA y agrega la entrada.
