# Corrida real de 10 personas, v2 (F10.9.T1)

Objetivo `predicts@master` (`ac879649`), semilla 2, `--sin-publicar --vista`, como servicio `systemd-run --user`.

Se hicieron dos corridas:

| Corrida | Código | Resultado |
|---|---|---|
| `20261101-210205-2-fb0c` | `main` sin los arreglos de esta tarea | 10 ejecuciones, 60 % de éxito, **3 con «juez no disponible»**, **0 sugerencias** |
| `20261101-214053-2-e82b` | con los arreglos de esta tarea (abajo) | 10 ejecuciones, 2 aprobadas, 7 fallos, 1 no concluyente, 9 sugerencias |

Lo que sigue describe la segunda, salvo que diga otra cosa.

## Arreglos hechos en dogfood

1. **Gemini envolvía el JSON en ```` ```json ````** aun con `json_schema`. `BackendApi.completar_json` fallaba la validación y el respaldo del juez (gemini) tampoco servía: por eso el 503 de sonnet acababa en «juez no disponible». Ahora quita las cercas (`backends/api.py`).
2. **El redactor de sugerencias no tenía respaldo**: un 503/429 de `ag/claude-sonnet-5-5-medium` dejaba `sugerencias.json` vacío (corrida 1). `llm.completar_json` ahora reintenta una vez con `ag/gemini-3.8-flash`.
3. **Salida del juez no JSON** (`exito: false\nmotivo: …`, en YAML): se tomaba como error no transitorio y no se reintentaba. Ahora `ValidationError` cuenta como transitorio (`agente/juez.py`). *Este arreglo se hizo al final y no se verificó con otra corrida de 35 min: solo con test.*
4. Tests nuevos en `tests/test_juez.py` (cercas y salida no JSON).

## Verificación de los criterios

| Criterio | Resultado |
|---|---|
| 10 ejecuciones, un escenario por persona | Sí: 10 escenarios distintos, cada uno con 1 ejecución |
| Ninguna con «juez no disponible» | **Casi**: quedó 1 (E10, escenario `login-fallido`): sonnet y gemini devolvieron YAML en vez de JSON. Causa corregida con el arreglo 3, sin repetir la corrida. En la corrida 1 eran 3 |
| El detector del objetivo corrió sin error | Sí: sin hallazgos «verificador … falló». Dio 2 de lógica (MAE) y 3 de aislamiento |
| Técnicos sin ruido | Parcial: 4 técnicos (504 de `/api/demo`, pantalla en blanco, `ERR_ALPN_NEGOTIATION_FAILED`, `TypeError … 'motivo'`). Ya no salen el 401 de `/auth/yo`, el 429 de login ni «Failed to load resource» repetidos |
| 404 de calidad como uno solo | El 404 de `/datasets/{id}/calidad` aparece en 5 ejecuciones (E2, E4, E5, E6, E9) y **no genera ningún hallazgo** (se tolera en vez de salir como un solo hallazgo media con hipótesis de carrera). Pendiente |
| Al menos una fricción | Sí: 4 (error en pantalla en demo, «Show Error» en análisis, 2 de espera repetida) |
| Plan, sugerencias y reporte en el panel | Verificado contra un panel local sobre `runs/` de esta corrida: `/api/corridas/{id}`, `/plan` (10 casos) y `/reporte` (con sugerencias) responden bien. **El panel publicado** (`https://dogfood.knaimero.app`) está tras Cloudflare Access (302) y lee el `runs/` del checkout principal, donde esta corrida no está: no se pudo verlo ahí |

## Tasa de éxito por escenario (corrida 2)

| Escenario | Resultado | Por qué |
|---|---|---|
| recompra-completa | aprobado | |
| recuperar-contrasena | aprobado | |
| agente-analista | fallo | la 3.ª respuesta quedó incompleta, sin «Cómo lo calculé» |
| calidad-antes-de-analizar | fallo | no apareció el informe de calidad |
| corregir-mapeo | fallo | error de duplicidad al confirmar el mapeo |
| demo | fallo | `POST /api/demo` 504 |
| explorar-universo | fallo | no abrió el historial de un cliente |
| ofertas-con-lista | fallo | |
| plantillas-mensaje | fallo | «aún no hay modelos de mensaje» |
| login-fallido | no concluyente | juez no disponible (ver arriba) |

Con una sola persona por escenario la tasa es 0 % o 100 %; no hay intervalo útil (Wilson 95 %: 0–0.79 / 0.21–1). La corrida 1, con juez algo menos caído, dio 6/10 aprobadas: el juez y los modelos de persona hacen variar mucho el resultado entre corridas con la misma semilla.

## Hallazgos reales de predicts (con su sugerencia)

Las sugerencias salen como hipótesis («sin acceso al código», `archivos` vacío, confianza baja): el redactor no leyó el repo.

- **`POST /api/demo` responde 504** (alta, 2 ocurrencias). Sugerencia: tiempo de espera en la carga de datos de ejemplo; revisar `api/src/predicts/api/demo.py`.
- **`TypeError: Cannot read properties of undefined (reading 'motivo')`** en el JS del web, más **pantalla en blanco** en `/datasets/{id}/analisis/nuevo` (alta). Sugerencia: validar que el objeto exista antes de leer `motivo`.
- **MAE de backtest** (media, 2): predicts declara `mae_dias=3.98`; dogfood recalcula 1.63 sobre 65 pares. Puede ser diferencia de universo o de criterio: a revisar con quien mantiene el cálculo.
- **`ERR_ALPN_NEGOTIATION_FAILED`** en `/datasets/{id}/ofertas` (media): suena a infraestructura local (proxy/HTTP2), no a predicts.
- **«Aislamiento» (crítica ×3)**: `GET /api/analisis/{id}/resultados` y `/exportar` con la sesión de la empresa B. La evidencia es un **422**, no un 200 con datos de A. **Probablemente falso positivo del oráculo** (el 422 es de validación): ver pendientes. No tomarlo como fuga hasta confirmarlo.

## Costo y duración

- Corrida 2: US$ 0.84 de dogfood (panel: 0.82 en ejecuciones); 34 min de reloj (21:40–22:14); el reporte suma 85 min de ejecuciones.
- Corrida 1: US$ 1.06, 29 min de reloj.
- Costo de predicts: estimado en 0 (884 decisiones de Jev).

## Lo que todavía falla en dogfood (pendientes)

1. **El oráculo de aislamiento acepta un 422 como «acceso»**: debería exigir 2xx con cuerpo, o ignorar 4xx. Genera 3 hallazgos críticos probablemente falsos (`deteccion/` / `objetivos/predicts/`, fuera de los archivos de esta tarea).
2. **404 de calidad** sin hallazgo único con hipótesis de carrera (ver tabla): la regla `carrera` no se dispara en la corrida real.
3. **`/api/corridas/{id}/reporte.pdf` da 500** en un panel local (Playwright espera `[data-reporte-listo]` y la ruta `/corridas/{id}/reporte` muestra la pantalla de la corrida, sin el artículo del reporte). Revisar `web/src/routes/corridas.$id.reporte.tsx` (¿falta `<Outlet/>` en la ruta padre?).
4. Repetir la corrida con el arreglo 3 para confirmar 0 «juez no disponible».
5. El panel publicado no muestra esta corrida: copiar `runs/` o lanzar las corridas desde el checkout que sirve el panel.
6. Sugerencias sin acceso al código (`DOGFOOD_REPO_OBJETIVO` por defecto no se montó): `archivos` sale vacío.
7. Aviso en `fb0c`: tracebacks de `ScreenshotWatchdog` (timeout 15 s) de browser-use; no tumbaron la corrida.
