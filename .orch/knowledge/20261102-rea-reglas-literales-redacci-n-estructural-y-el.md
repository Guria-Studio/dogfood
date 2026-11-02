---
id: 20261102-rea-reglas-literales-redacci-n-estructural-y-el
title: 'REA: reglas literales, redacción estructural y el historial de browser-use pisado por el almacén'
area:
    - src/dogfood/rea/**
    - src/dogfood/diff.py
    - src/dogfood/comandos/diff.py
    - src/dogfood/almacen.py
    - src/dogfood/agente/replay.py
tags:
    - rea
    - diff
    - redactar
    - historial
source: agent
task: F12.1.T1
created: "2026-11-02"
---

- `rea compare-web-captures --normalization-json` solo acepta reglas LITERALES `{rule_id, artifacts[action_state|dom|accessibility|url|history|storage|events], match, replacement}`. `rea.normalizacion.politica` convierte los patrones regex de dogfood en literales a partir de las dos grabaciones; `adaptador.comparar` lo hace solo.
- No pases `redactar` sobre el texto JSON entero de la evidencia: tapa los sha256 y el base64 de las capturas, y REA rechaza la comparación con `invalid_request`. Usa `adaptador.redactar_evidencia`, que salta los campos de integridad y recalcula el `sha256`/`bytes` de los artefactos de texto. Además, `redactar` reemplaza los UUID (de 32 caracteres o más) por «redactado» en lo que se guarda.
- El arranque de Chromium en REA puede pasar los 20 s de `command_timeout_ms`: el escenario usa 60000. Un primer paso con `timeout_ms` de 5 s falló en frío, así que el escenario usa 15000.
- Si un paso falla, REA igual sale con código 0: revisa que todos los `normalized_result.steps[].status` sean `completed`.
- Aun con la misma página estática, la captura del último click puede cambiar (foco o hover). El ruido visual hay que tratarlo con umbral, no con un hash exacto.
- Trampa: `Almacen.guardar_ejecucion` escribe la Ejecucion en `historial.json`, el mismo archivo donde navegador.py guardó el AgentHistoryList de browser-use. En las corridas guardadas, el historial de browser-use se pierde (también le pega al replay). `rea.escenario.desde_ejecucion` avisa y devuelve un escenario vacío. F12.1.T2 tiene que leer el historial antes de que se guarde, o hay que mover uno de los dos archivos.
