---
titulo: Preguntas frecuentes
seccion: referencia
orden: 3
pantallas: []
---

# Preguntas frecuentes

## ¿Por qué un hallazgo no se publicó?

Las causas posibles:

- Corriste con `--sin-publicar`, que no crea issues.
- Su gravedad quedó bajo el umbral de gravedad configurado.
- Ya existía un issue abierto con la misma **huella**: en ese caso dogfood comenta ahí en vez de crear otro.
- Falló `gh` (sin sesión o sin permiso de escritura en `repo_issues`). Revisa `gh auth status`.

Si quieres publicarlo a mano, usa **Crear issue** en el detalle de la ejecución ([Leer una ejecución](leer-una-ejecucion.md)).

## ¿Por qué un 429 no es un error?

Algunos escenarios fallan el login a propósito. Corren al final y en serie, y un 429 (demasiados intentos) después de esos fallos esperados **no es un hallazgo**: es el límite de predicts funcionando. dogfood no lo cambia porque es parte de lo que se prueba.

## ¿Qué hago si la vista no carga?

- La vista solo existe con `--vista` y mientras la corrida está activa; al terminar queda 5 s abierta y se cierra.
- Busca en el log la línea `vista en vivo: http://127.0.0.1:7460/`.
- Si el puerto está ocupado, la corrida avisa y sigue sin vista. Prueba `--vista-puerto 7461`.
- Solo acepta `127.0.0.1`, `localhost`, `::1` o una IP de Tailscale. Desde otra máquina usa un túnel SSH o la IP de Tailscale: ver [Panel y vista en vivo](../ops/panel-y-vista.md).
- Para ver corridas ya terminadas, usa `uv run dogfood panel`.

## ¿Cuánto cuesta una corrida?

No hay tope duro, pero se mide y se muestra el costo por corrida, por rol y por modelo. Como referencia, la corrida M1 (una persona, 19 pasos, 221 s) costó 0,108 USD. Para limitarlo usa `--tope-usd`. Con el motor `claude_code` (plan Max) el costo cobrado es 0 y el panel muestra el **costo equivalente** por API para poder comparar motores ([Motor claude_code](../ops/claude-code.md)). El costo de la IA de la instancia de predicts es una estimación y se marca como tal.

## ¿Cómo conecto un Android?

Resumen (guía completa en [Android real](../ops/android.md)):

```bash
uv run dogfood android emparejar 100.x.y.z:<puerto-de-vinculacion>
uv run dogfood android conectar 100.x.y.z:<puerto-de-depuracion>
uv run dogfood android estado
```

Necesitas Depuración inalámbrica y Tailscale en el teléfono. ADB solo se usa por USB, localhost o Tailscale.

## ¿Cómo pruebo una app Flutter?

- **Sin celular:** compila la app a web y pruébala con `uv run dogfood run --target flutter_web --escenarios login`.
- **En un celular real:** conéctalo como arriba y corre `uv run dogfood run --target android --escenarios login --vista`.
- **Sin LLM:** `--motor patrol` o `--motor integration_test` corren un test Dart.

dogfood siempre trabaja sobre una copia de la app. Detalles en [Apps Flutter](../ops/flutter.md).
