# ADR 0001 — Stack

- **Estado:** propuesto (se confirma en la arquitectura)
- **Fecha:** 2026-10-24

## Decisión
- **Python 3.13 + uv**: el mismo stack de referencia que guria-intake.
- **LangGraph / LangChain 1.x** para orquestar personas y escenarios.
- **browser-use / Playwright** sobre el Chrome CDP del homelab (127.0.0.1:9222, con pantalla en Xvfb).
- **Modelos vía 9router** (`ROUTER_BASE_URL`, `ROUTER_KEY`, `ROUTER_MODEL`) con `ChatOpenAI`, y salidas estructuradas con Jev (TypeSafe) donde convenga.
- **Salidas**: issues de GitHub (`gh`), un reporte en Markdown/HTML y un aviso en Slack.
- **Reglas en el código, no en el prompt**: deduplicación de issues, gravedad mínima y presupuesto por corrida.

## Por qué
Es el stack que Héctor ya mantiene. El navegador real ya existe en el servidor, y 9router centraliza el costo de los modelos.
