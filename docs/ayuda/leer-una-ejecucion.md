---
titulo: Leer una ejecución
seccion: guias
orden: 1
pantallas:
  - ejecucion
---

# Leer una ejecución

Una **ejecución** es lo que hizo una persona con un escenario. Su detalle está en el panel, en `/ejecuciones/<id>`.

## Las partes del detalle

- **Resultado:** aprobado, falló o no concluyente. Mira [Resultados](resultados.md) para saber cuándo ocurre cada uno.
- **Pasos:** con **← / →** (o los botones y la línea de tiempo) cambias de paso. Cada paso muestra:
  - la **captura** de la pantalla;
  - la **acción** que hizo el agente;
  - su **razonamiento**: por qué decidió eso;
  - **esperado / observado**, cuando el recorrido define un contrato;
  - la **consola y la red** de esa pantalla (errores, respuestas 4xx/5xx).
- **Video:** la grabación de la ejecución.
- **`trace.zip`:** el rastro de Playwright (solo web). Se abre con `uv run playwright show-trace trace.zip`.
- **Logcat:** el registro de Android, cuando el driver es Android.
- **Opinión de la persona:** sus notas de fricción agrupadas por pantalla: qué no entendió, qué le frustró y qué le sobró.

## Cuándo usar «Crear issue»

Úsalo cuando **tú** reconoces un problema que dogfood no publicó solo: por ejemplo, una ejecución no concluyente que ves rota en el video, o un hallazgo que quedó bajo el umbral de gravedad o se corrió con `--sin-publicar`.

1. Elige el **tipo** y la **gravedad**.
2. Pulsa **Crear issue**.

El panel arma el hallazgo con los pasos, esperado/obtenido y los extractos de consola, red y logcat, lo pasa por la redacción (se reemplazan email, contraseña, empresa de la persona y secretos de la config) y lo publica con `gh` en `repo_issues` de `dogfood.yaml`.

- Necesitas `gh auth status` válido y permiso de escritura en ese repo.
- Si ya hay un issue abierto con la misma **huella**, comenta en ese en vez de crear otro y te devuelve su URL.
- El resultado aparece debajo del botón: la URL del issue o el error de `gh`.

Más detalle en [Panel y vista en vivo](../ops/panel-y-vista.md).
