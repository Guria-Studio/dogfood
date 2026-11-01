---
titulo: Resultados posibles de una ejecución
seccion: referencia
orden: 1
pantallas:
  - corridas
  - ejecucion
  - recorridos
---

# Resultados posibles de una ejecución

El resultado lo calcula una sola función, `contrato.resultado` (`src/dogfood/contrato.py`), igual para todos los motores y drivers. Hay tres valores:

| Resultado | Cuándo ocurre |
|---|---|
| **no concluyente** | La ejecución terminó en `error`, **o** no hay ninguna captura (no hay evidencia), **o** el juez dio éxito pero sin motivo. No dice nada de la app. |
| **aprobado** | Hay evidencia (al menos una captura) y el juez dio éxito, con motivo. |
| **falló** (`fallo`) | Hay evidencia y el juez dio fracaso. |

## Orden de evaluación

1. Si el estado es `error`, no hay capturas, o hay éxito sin motivo del juez → **no concluyente**.
2. Si no, éxito → **aprobado**; fracaso → **fallo**.

Lo no concluyente gana a todo: un «aprobado» sin capturas es no concluyente, no aprobado.

## Qué hacer con cada uno

- **aprobado:** el recorrido se completó y hay evidencia de que funcionó.
- **falló:** hay un problema probable en la app. Abre el detalle y revisa los pasos.
- **no concluyente:** el problema pudo ser de la ejecución (se cayó el motor, faltó evidencia), no de la app. Reintenta o revisa el log.

## En el panel

Los no concluyentes cuentan en el total de ejecuciones y **bajan la tasa de aprobación** (aprobadas / ejecuciones): un motor que se cae mucho se ve peor, no se oculta. Las ejecuciones guardadas antes de que existiera el resultado no lo tienen; el panel lo deduce de `exito` (aprobado o falló).

## Motores deterministas (`patrol`, `integration_test`)

Corren un test Dart sin LLM, con su propia regla: cualquier test en `fallo` da **fallo** (aunque haya timeout); **aprobado** solo con código de salida 0, al menos un test, todos ok y sin motivo; todo lo demás es **no concluyente**.
