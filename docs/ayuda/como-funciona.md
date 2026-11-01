---
titulo: Cómo funciona dogfood
seccion: empezar
orden: 1
pantallas:
  - corridas
---

# Cómo funciona dogfood

dogfood hace que **usuarios agénticos** (agentes con personalidad) usen tu app de verdad, en un navegador o en un celular, y te entrega issues con pasos para reproducir, capturas y gravedad, más la opinión de cada persona. Encuentra bugs y fricción; **no valida mercado** (eso solo lo hacen usuarios reales).

Una **corrida** es una sola vuelta de este proceso. Se lanza con `uv run dogfood run` y cada corrida queda guardada en `runs/<corrida_id>/`.

## El camino de una corrida

```text
 1. instancia ──► 2. datos con ──► 3. personas ──► 4. agentes ──► 5. detectores ──► 6. issues
    aislada          verdad             (JSON)         usan la app     (errores,        y reporte
  (dogfood env)     (CSV + verdad)                  (web o celular)    números, UX)     (gh, Slack)
        │                │                 │               │               │               │
   logs/*.log      datos/<id>/        personas.json   ejecuciones/    hallazgos.json   reporte.md
                                                       <id>/ ...                       reporte.html
```

## Paso 1. Instancia aislada

- **Qué hace:** levanta una copia propia del objetivo (por ejemplo predicts) con Docker Compose, en puertos distintos a los de desarrollo. Nada de lo que hagan los agentes toca producción. Al terminar la destruye, salvo que uses `--mantener-entorno`.
- **Qué guarda en `runs/`:** `corrida.json` (objetivo, `ref`, commit, semilla) y `logs/api.log` y `logs/worker.log`.
- **Dónde se ve:** en el panel, en la lista de **Corridas** y en el resumen de cada corrida.

## Paso 2. Datos con verdad conocida

- **Qué hace:** genera datos sintéticos (por ejemplo CSV de ventas de una farmacia) a partir de una semilla. Como los datos los fabrica dogfood, sabe la respuesta correcta de antemano: eso es la **verdad**.
- **Qué guarda en `runs/`:** `datos/<dataset_id>/ventas.csv` y `datos/<dataset_id>/verdad.json`.
- **Dónde se ve:** en el detalle de la ejecución, cuando el agente sube el archivo y cuando el detector compara los números.

## Paso 3. Personas

- **Qué hace:** crea personas deterministas (nombre, idioma, empresa, forma de usar la app: el apurado, el torpe, el que intenta romper cosas). Con la misma semilla salen las mismas personas.
- **Qué guarda en `runs/`:** `personas.json`.
- **Dónde se ve:** en la lista de ejecuciones (columna y filtro de persona) y en el detalle de cada una.

## Paso 4. Agentes en navegador o celular

- **Qué hace:** cada persona ejecuta un **escenario** (por ejemplo «recompra completa») con un **driver** (web, Android o iOS) y un **motor** (`browser_use`, `bucle`, y los deterministas `patrol` e `integration_test`). En cada paso mira la pantalla, decide, actúa y anota su razonamiento. Al final un juez dice si cumplió el objetivo y de ahí sale el [resultado](resultados.md).
- **Qué guarda en `runs/`:** `ejecuciones/<ejecucion_id>/` con `pasos.jsonl`, `historial.json`, `red.jsonl`, `consola.jsonl`, `capturas/`, `descargas/`, y según el caso video, `trace.zip` (web) o `logcat.txt` (Android).
- **Dónde se ve:** en la **Vista en vivo** mientras corre (`--vista`) y en el **detalle de la ejecución** después.

## Paso 5. Detectores

- **Qué hace:** revisan lo que pasó y producen **hallazgos**: errores técnicos (consola, 4xx/5xx, pantallas en blanco), números que no coinciden con la verdad (el **oráculo**), aislamiento entre empresas, reglas propias del objetivo y notas de **fricción** de las personas.
- **Qué guarda en `runs/`:** `hallazgos.json`, y cada hallazgo lleva su **huella** para no duplicarse.
- **Dónde se ve:** en el detalle de la ejecución y en el resumen de la corrida.

## Paso 6. Issues y reporte

- **Qué hace:** publica los hallazgos nuevos como issues en GitHub con `gh` (con `--sin-publicar` no crea ninguno), comenta en el issue existente si la huella ya estaba, escribe el reporte de opinión y manda el resumen a Slack.
- **Qué guarda en `runs/`:** `reporte.md` y `reporte.html`; la URL de cada issue queda en el índice `runs/dogfood.db`.
- **Dónde se ve:** el panel muestra la URL del issue; desde el detalle de una ejecución también puedes pulsar **Crear issue** a mano (ver [Leer una ejecución](leer-una-ejecucion.md)).

## Ejemplo real: la corrida M1

La primera corrida real fue contra predicts (`ref master`, commit `ac87964`, semilla 1, escenario `recompra-completa`, con `--sin-publicar`):

| Dato | Valor |
|---|---|
| Resultado del juez | éxito |
| Pasos | 19 |
| Duración | 221 s |
| Costo | 0,108 USD |
| Evidencia | CSV `Farmacia_recordatorios_*.csv` descargado y entorno destruido |

Qué encontró:

- **Bugs de dogfood** (arreglados): el email de la persona usaba un dominio que predicts rechazaba (422 en el registro), la ruta del archivo a subir era relativa y el modelo inventaba parámetros en `upload_file`.
- **Hallazgos de predicts** (gravedad media): `GET /api/auth/yo` devolvía 401 en la pantalla de registro antes de autenticarse, y `GET /api/datasets/{id}/calidad` devolvió 404 en la pantalla de calidad, aunque la corrida siguió con éxito.

Para correr la tuya, sigue [Tu primera corrida](primera-corrida.md).
