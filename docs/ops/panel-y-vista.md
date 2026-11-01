---
titulo: Panel y vista en vivo
seccion: guias
orden: 4
pantallas:
  - vista
  - corridas
  - ejecucion
---

# Panel y vista en vivo

Dos páginas locales para seguir a los usuarios agénticos (FR-30 a FR-33, NFR-10):

- **Vista en vivo**: mientras corre `dogfood run`, una tarjeta por ejecución con el video en vivo, la pantalla y el razonamiento de cada paso.
- **Panel**: después de la corrida, todas las ejecuciones guardadas en `runs/`, con filtros, detalle paso a paso, video y «Crear issue».

## 1. Abrir la vista

```bash
uv run dogfood run --target predicts --vista
uv run dogfood run --target predicts --vista --vista-puerto 7461
```

- Puerto por defecto: **7460** (`vista.puerto` en `dogfood.yaml`). Host por defecto: `127.0.0.1` (`vista.host`).
- La URL sale en el log: `vista en vivo: http://127.0.0.1:7460/`. Ábrela en el navegador mientras la corrida está activa.
- Al terminar la corrida la vista queda 5 s abierta para ver el resultado final y se cierra.
- Si el puerto está ocupado, la corrida avisa y sigue sin vista; nunca falla por la vista.
- Clic en una tarjeta la amplía; `Esc` la cierra. El rótulo «latencia» es el tiempo entre que se capturó el último frame y que lo dibuja el navegador (mide menos de 1 s en la prueba de integración).

## 2. Abrir el panel

```bash
uv run dogfood panel
uv run dogfood panel --puerto 7471 --raiz runs
```

- Puerto por defecto: **7470** (`panel.puerto`). Host por defecto: `127.0.0.1` (`panel.host`).
- Necesita `runs/dogfood.db`: corre `dogfood run` al menos una vez.
- `/` lista las ejecuciones y filtra por recorrido, resultado, versión, persona, driver y motor. `/corridas/<id>` resume una corrida y compara motores. `/recorridos` cuenta resultados por recorrido. `/ejecuciones/<id>` es el detalle.
- En el detalle: **← / →** (o los botones y la línea de tiempo) cambian de paso; cada paso muestra captura, acción, razonamiento, esperado/observado y la consola y red de esa pantalla. Debajo, el video, el `trace.zip` (`uv run playwright show-trace trace.zip`), el logcat en Android y la opinión de la persona agrupada por pantalla.

## 3. Verlos desde otra máquina (Tailscale)

Ni la vista ni el panel aceptan `0.0.0.0` ni una IP pública: solo `127.0.0.1`, `localhost`, `::1` o una IP de Tailscale (`100.64.0.0/10`). Cualquier otro host sale con error y código 2.

Opción A, escuchar en la IP de Tailscale del server:

```bash
tailscale ip -4                                  # p. ej. 100.101.102.103
uv run dogfood panel --host 100.101.102.103
# y en la config, para la vista: vista: { host: 100.101.102.103, puerto: 7460 }
```

Desde la otra máquina de tu tailnet: `http://100.101.102.103:7470/`.

Opción B, dejarlos en `127.0.0.1` y abrir un túnel SSH desde tu máquina:

```bash
ssh -N -L 7470:127.0.0.1:7470 -L 7460:127.0.0.1:7460 usuario@server
```

Luego abre `http://127.0.0.1:7470/` (panel) y `http://127.0.0.1:7460/` (vista) en tu navegador local. Es la opción más segura: nada escucha en la red.

## 4. Qué significa cada resultado

El resultado de cada ejecución lo calcula `contrato.resultado` (FR-30), una sola función para todos los motores y drivers:

| Resultado | Cuándo |
|---|---|
| **no concluyente** | La ejecución terminó en error (`estado == "error"`), o no hay ninguna captura (sin evidencia), o el juez dio éxito sin motivo. No dice nada de la app. |
| **aprobado** | Hay evidencia y el juez dio éxito con motivo. |
| **falló** | Hay evidencia y el juez dio fracaso. |

Se evalúa en ese orden: lo no concluyente gana a lo demás. Un «aprobado» sin capturas es no concluyente, no aprobado. Las ejecuciones guardadas antes de F6 no tienen resultado; el panel lo deduce de `exito` (aprobado o falló).

## 5. Leer la comparación de motores

En `/corridas/<id>`, la tabla agrupa las ejecuciones por **motor / backend / modelo** (p. ej. `browser_use / api / …` frente a `bucle / claude_code / sonnet`). Por grupo:

- **Ejecuciones, aprobadas, fallidas, no concluyentes** y **tasa de aprobación** = aprobadas / ejecuciones. Los no concluyentes cuentan en el total, así que bajan la tasa: un motor que se cae mucho se ve peor, no se oculta.
- **Tokens, costo y costo equivalente**, promedio por ejecución. «Costo» es lo cobrado de verdad (0 con el plan Max de `claude_code`); «costo equivalente» es lo que habría costado por API. Compara motores por el equivalente.

Con pocas ejecuciones por grupo la tasa es ruido: sube `--personas` o `--repeat` antes de sacar conclusiones.

## 6. Crear un issue desde el panel

En el detalle de una ejecución, elige **tipo** y **gravedad** y pulsa **Crear issue**. El panel arma el hallazgo con los pasos, esperado/obtenido, extractos de consola, red y logcat, y lo publica con `gh` en `repo_issues` de `dogfood.yaml`.

- Necesita `gh auth status` válido y permiso sobre `repo_issues`.
- El texto pasa por la redacción: email, contraseña y empresa de la persona y los secretos de la config se reemplazan.
- Si ya existe un issue abierto con la misma huella, comenta en ese en vez de crear otro y devuelve su URL.
- El resultado aparece debajo del botón: la URL del issue, o el error de `gh` (HTTP 502).

## 7. Probar la integración a mano

```bash
uv run pytest -m integracion tests/integracion/test_panel_vista.py -v
```

Abre un Chromium real contra el panel y la vista. El tercer escenario corre `dogfood run --motor bucle` con `motores.persona: claude_code` y se salta solo si no hay `claude` con sesión (`claude -p "di ok" --output-format json`).
