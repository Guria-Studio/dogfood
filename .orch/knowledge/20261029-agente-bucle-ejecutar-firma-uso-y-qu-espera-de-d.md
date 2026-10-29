---
id: 20261029-agente-bucle-ejecutar-firma-uso-y-qu-espera-de-d
title: 'agente.bucle.ejecutar: firma, uso y qué espera de drivers/backends falsos'
area:
    - src/dogfood/agente/bucle.py
    - src/dogfood/corrida.py
    - tests/test_corrida_motores.py
source: agent
task: F6.5.T1
created: "2026-10-29"
---

- `agente/bucle.py` exporta `DecisionPaso` y `ejecutar(persona, escenario, driver, backend, juez, carpeta, *, cfg, bus, corrida_id, objetivo, timeout_s)`. El uso de tokens va solo en `e.metricas` (no recibe un ContadorUso), así que F6.7 tiene que registrar el uso en la corrida a partir de `e.metricas` y `e.backend`.
- `Paso.observado` necesita la pantalla siguiente, así que el bucle observa n+1 después de actuar y reusa esa observación en el paso siguiente. Los drivers ven `observar(n)` una vez por paso, más uno al final.
- La sesión se toma tal cual la devuelve el backend: si devuelve None, el paso siguiente no lleva sesión.
- La tarea de frames arranca recién en el primer `await` que cede el control. Un driver falso tiene que hacer `await asyncio.sleep(...)` en observar/actuar, o no se publica ningún frame.
- Importar el bucle importa `agente/navegador.py` (por `Veredicto`), y con eso browser_use y playwright.
- Para distinguir el timeout se usa `asyncio.timeout(...).expired()`, así un TimeoutError del driver queda como `error` y no como `fallo/timeout`.
