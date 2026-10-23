# Hallazgos de la corrida M1

Corrida real contra predicts (`ref master`, commit `ac87964`, semilla 1, escenario `recompra-completa`, `--sin-publicar`): éxito del juez, 19 pasos, 221 s, 0,108 USD, CSV `Farmacia_recordatorios_*.csv` descargado y entorno destruido.

## Bugs de dogfood (arreglados)
- El email de la persona usaba `@dogfood.test`; predicts valida con `EmailStr` y rechaza el TLD `.test` (422 en `/auth/registro`). Ahora `@dogfood.example.com` (`corrida.py`). `reporte/redactar.py` sigue tratando `dogfood.test` como dominio no sensible: los emails de persona se redactarán en los issues (seguro, pero conviene alinearlo).
- `available_file_paths` recibía una ruta relativa (`runs/...`) y browser-use no subía el archivo. Ahora ruta absoluta (`navegador.py`).
- El modelo llamaba `upload_file` con parámetros inventados (`file`). El prompt de la tarea indica `index` y `path` (`prompts.py`).
- `dogfood run` usa `--ref main` por defecto, pero predicts usa `master`; el test pasa `--ref master`. Pendiente: configurar el ref por defecto por objetivo.

## Hallazgos de predicts (no se arreglan)
- Media: `GET /api/auth/yo` devuelve 401 en la pantalla de registro/login antes de autenticarse (error de consola). Probablemente esperado, pero ensucia la consola.
- Media: `GET /api/datasets/{id}/calidad` devolvió 404 en la corrida (pantalla de calidad); la corrida siguió con éxito. Revisar si es una carrera entre la subida y el cálculo de calidad.
