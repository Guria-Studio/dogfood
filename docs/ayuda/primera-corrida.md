---
titulo: Tu primera corrida
seccion: empezar
orden: 2
pantallas:
  - corridas
  - vista
---

# Tu primera corrida

Una corrida de prueba que **no publica nada** en GitHub y te deja ver los agentes en vivo.

## Prerrequisitos mínimos

Todo está explicado, con su verificación, en [Prerrequisitos del operador](../ops/prerequisitos.md). Lo mínimo:

1. **`dogfood.yaml`**, copiado de `dogfood.example.yaml`.
2. **Secretos** en `~/.config/dogfood/` con permisos `600`: `router.env` (credenciales del gateway de modelos) y `predicts.env` (variables de la instancia de predicts).
3. **Docker con Compose v2** (`docker compose version`).
4. **Chromium de Playwright**: `uv run playwright install chromium`.
5. **Puertos libres** 18080, 18100 y 54330 (la instancia de predicts).
6. `gh` autenticado solo hace falta para publicar issues; con `--sin-publicar` no se usa.

## Comandos

Desde la raíz del repo:

```bash
uv run dogfood run --target predicts --ref master --personas 1 --sin-publicar --vista
```

- `--target predicts`: el objetivo (es el valor por defecto).
- `--ref master`: rama, tag o commit a probar. El valor por defecto es `main`, pero predicts usa `master`.
- `--personas 1`: una sola persona, para empezar barato.
- `--sin-publicar`: no crea issues.
- `--vista`: abre la vista en vivo. La URL sale en el log (`vista en vivo: http://127.0.0.1:7460/`); con `--vista-puerto` cambias el puerto.

Opciones útiles: `--escenarios` (ids separados por coma), `--seed`, `--concurrencia`, `--repeat`, `--tope-usd` (corta la corrida al pasar ese costo) y `--mantener-entorno` (no destruye la instancia al terminar).

## Ver el resultado

```bash
uv run dogfood runs      # lista las corridas guardadas
uv run dogfood panel     # abre el panel en http://127.0.0.1:7470/
```

El panel necesita `runs/dogfood.db`, que existe después de la primera corrida. Para entender lo que ves, lee [Leer una ejecución](leer-una-ejecucion.md) y [Resultados](resultados.md).

## Repetir una ejecución sin modelo

```bash
uv run dogfood replay <id>
```

`<id>` es un `hallazgo_id` o un `ejecucion_id`. Repite la ejecución sin LLM, útil para confirmar un hallazgo.

Más detalle de la vista y el panel: [Panel y vista en vivo](../ops/panel-y-vista.md).
