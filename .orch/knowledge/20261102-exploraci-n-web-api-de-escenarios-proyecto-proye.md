---
id: 20261102-exploraci-n-web-api-de-escenarios-proyecto-proye
title: 'Exploración web: API de escenarios_proyecto, Proyecto.prd y esquema v8'
area:
    - src/dogfood/explorar.py
    - src/dogfood/almacen.py
    - src/dogfood/panel/api_escenarios.py
    - web/src/features/mapa/**
    - web/src/features/escenarios/**
    - tests/fixtures/app_web/
source: agent
task: F13.2.T1
created: "2026-11-02"
---

- Esquema v8: `escenarios_proyecto.prioridad` (alta|media) y la tabla `exploraciones` (mapa en `datos`). Métodos en Almacen: guardar_borradores (refresca solo borradores; lo aceptado/descartado no se pisa), escenarios_proyecto, actualizar_escenario, borrar_escenario, guardar_exploracion, ultima_exploracion.
- API: POST /api/proyectos/{slug}/exploraciones (X-Dogfood: 1; lanzamiento id `X-…`, estado por /api/corridas/{id}/estado), GET …/mapa (404 si nunca se exploró), GET/PATCH/DELETE …/escenarios[/{id}]. Las filas vienen planas: campos del Escenario + estado, prioridad, creado. PATCH acepta estado, prioridad o cualquier campo del Escenario (no `id`) y revalida (422).
- `Proyecto.prd` (texto Markdown) es el PRD que cruza `dogfood explorar`; `--prd ARCHIVO` lo pisa.
- tests/test_layout.py exige exactamente 4 roles en dogfood.example.yaml: el rol `explorador` NO va ahí; el código cae a sonnet si falta en cfg.roles.
- tests/test_contratos_f6.py fija VERSION_ESQUEMA: súbelo al migrar.
- El driver HTTP falso de tests/test_explorar.py (DriverHttp + _App sobre tests/fixtures/app_web/) sirve para probar recorridos sin Chromium.
