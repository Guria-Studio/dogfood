---
titulo: Android real con ADB
seccion: guias
orden: 5
pantallas:
  - dispositivos
---

# Android real con dogfood: ADB por USB o Tailscale

Guía para probar una app Android real con el driver `android` (FR-29, FR-34, FR-37, issue #32). Cubre preparar el teléfono, emparejarlo y conectarlo, la configuración de `dogfood.yaml`, correr el login agéntico o determinista, ver la pantalla en vivo y la verificación manual que aún falta.

Regla que atraviesa toda la guía: **ADB nunca se expone fuera de USB, localhost o Tailscale** (NFR-10). Un teléfono con depuración por red es un teléfono que cualquiera de la red puede controlar.

## 1. Preparar el teléfono

1. **Opciones de desarrollador.** En Ajustes → Acerca del teléfono, toca *Número de compilación* siete veces. Luego, en Ajustes → Sistema → Opciones de desarrollador, actívalas.
2. **Depuración USB** (para el cable). Actívala en Opciones de desarrollador. Al conectar por primera vez, acepta la huella RSA del equipo.
3. **Depuración inalámbrica** (para Tailscale, Android 11 o superior). Actívala en Opciones de desarrollador. Mantén la pantalla de Depuración inalámbrica abierta mientras emparejas.
4. **Tailscale en el teléfono.** Instala la app de Tailscale, inicia sesión en el mismo tailnet que el servidor y confirma que el teléfono tiene una IP `100.x.y.z`:

```bash
tailscale ip -4          # en el servidor: su IP de Tailscale
tailscale status         # el teléfono debe aparecer como conectado
```

5. **Excluir Tailscale de la optimización de batería.** Android puede suspender la red de una app en segundo plano, y entonces la conexión ADB por Tailscale se cae a mitad de una corrida. En Ajustes → Aplicaciones → Tailscale → Batería, elige *Sin restricciones* (o *Sin optimizar*; el nombre cambia según la versión y el fabricante). Si el teléfono tiene un ahorro de energía agresivo, exclúyelo también para Depuración inalámbrica.

## 2. Emparejar y conectar

Dogfood trae un comando propio, `dogfood android`, con cuatro subcomandos (`src/dogfood/comandos/android.py`):

| Comando | Qué hace |
|---|---|
| `dogfood android emparejar IP:PUERTO` | Corre `adb pair` interactivo. El código de 6 dígitos lo escribes tú en el prompt de adb; dogfood nunca lo recibe ni lo guarda. |
| `dogfood android conectar [IP:PUERTO]` | Corre `adb connect` y comprueba `get-state = device`. Sin argumento usa `driver.host_puerto` de `dogfood.yaml`. Imprime modelo y versión de Android. |
| `dogfood android estado` | Lista los dispositivos de `adb devices -l` (✅ permitido, ⛔ rechazado con su motivo) y revisa que el servidor adb escuche solo en loopback. |
| `dogfood android desconectar [IP:PUERTO]` | Desconecta un destino, o todos si no das ninguno. |

El flujo, una sola vez por teléfono:

1. En el teléfono: Depuración inalámbrica → *Vincular dispositivo con código de emparejamiento*. Anota la IP:puerto de vinculación y el código de 6 dígitos.
2. En el servidor:

```bash
uv run dogfood android emparejar 100.x.y.z:<puerto-de-vinculacion>
# escribe el código de 6 dígitos cuando lo pida adb
```

3. En la pantalla principal de Depuración inalámbrica aparece otro puerto, distinto del de vinculación. Conecta con ese y pon el mismo valor en `dogfood.yaml`:

```bash
uv run dogfood android conectar 100.x.y.z:<puerto-de-depuracion>
uv run dogfood android estado    # debe mostrar ✅ 100.x.y.z:<puerto>  device
```

4. En `dogfood.yaml`, `driver.host_puerto: 100.x.y.z:<puerto-de-depuracion>`. Desde ahí, `dogfood android conectar` sin argumentos basta.

Para USB basta con `adb devices` (debe listar el serial con estado `device`) y poner ese serial en `driver.serial`. `validar_destino` acepta un serial solo si coincide con `^[A-Za-z0-9._-]+$`.

Si `dogfood android estado` marca ⛔ en el servidor adb, corre `adb kill-server` y no uses `adb -a`.

### Qué hace la reconexión

Si el teléfono cambia de red o se duerme, el puerto por Tailscale puede dejar de responder. `Adb.ejecutar` (`src/dogfood/drivers/android.py`) detecta el error (`device offline`, `device ... not found`, `no devices/emulators found` o `closed`) y hace **una sola** reconexión: `adb connect` a `driver.host_puerto`, `get-state`, y un reintento del comando. Si vuelve a fallar, la corrida recibe un error con la orden exacta para reconectar a mano:

```
se perdió la conexión por Tailscale con 100.x.y.z:5555 (...). Reconecta con: dogfood android conectar 100.x.y.z:5555
```

La reconexión no vuelve a emparejar. Si el teléfono olvidó el emparejamiento (reinicio, cambio de clave), repite el paso 2 del flujo de arriba.

## 3. Por qué ADB solo por USB, localhost o Tailscale

ADB no tiene más autenticación que la clave RSA aceptada en el teléfono. Quien alcance el puerto puede instalar apps, leer datos y tocar la pantalla. Por eso dogfood valida el destino **antes** de llamar a `adb`, en `validar_destino` (`src/dogfood/drivers/android.py`):

| Destino | Admitido | Rechazado |
|---|---|---|
| Serial USB | Coincide con `^[A-Za-z0-9._-]+$` | Cualquier otro texto |
| `host:puerto` con host `localhost` | Sí | |
| `host:puerto` con IP `127.0.0.1` | Sí | Otras IP de loopback |
| `host:puerto` con IP en `100.64.0.0/10` (Tailscale) | Sí | Cualquier IP fuera del rango |
| `host:puerto` con nombre de host (no IP) | | Sí, se exige IP |
| Puerto fuera de 1–65535 o no numérico | | Sí |
| `0.0.0.0` o cualquier IP pública o de LAN | | Sí |
| Sin serial ni `host:puerto` | | Sí |

Un error lanza `ValueError` con el motivo, y el driver no ejecuta ningún comando. Si `serial` contiene `:`, se trata como `host:puerto`. `dogfood android emparejar` y `conectar` usan la misma validación.

Límite de lo que valida: el rango `100.64.0.0/10` es el de CGNAT, y el validador acepta cualquier IP de ese rango. Lo que acota quién llega a tu teléfono es el ACL de tu tailnet; revísalo para que solo tu servidor pueda hablar con el puerto ADB del teléfono.

## 4. Configuración `driver:` y `pantalla:` en `dogfood.yaml`

```yaml
driver:
  tipo: android                 # web (por defecto) | android | ios
  serial: null                  # USB; o bien:
  host_puerto: 100.x.y.z:5555   # localhost o Tailscale; nunca otra red
  paquete: br.com.rupies.profissional   # paquete de la app bajo prueba
  actividad: null               # opcional: si se da, abrir_app usa am start -n paquete/actividad
  apk: null                     # opcional: instala con adb install -r antes de la corrida

pantalla:
  android: screencap            # screencap (por defecto) | screenrecord
  fps: 2                        # frames por segundo que pide la vista y el panel
```

Campos reales de `Driver` y `Pantalla` en `src/dogfood/config.py`. Usa `serial` o `host_puerto`, no ambos.

`pantalla.android` elige cómo se captura la pantalla:

- **`screencap`** (por defecto): una captura PNG por frame (`adb exec-out screencap -p`), convertida a JPEG. Simple, no necesita nada extra y basta para la vista en vivo.
- **`screenrecord`**: un `adb shell screenrecord` H.264 en segmentos de 170 s, decodificado con **`ffmpeg`**. Necesita `ffmpeg` en el PATH del servidor. Si no está, dogfood lo avisa en el log (`screenrecord → screencap: ffmpeg no está en el PATH`) y sigue con `screencap`. Con `screenrecord` la corrida también guarda el video en `video/dogfood-N.mp4`.

## 5. Correr el login

```bash
uv run dogfood run --target android --escenarios login
uv run dogfood run --target android --escenarios login --vista     # con la pantalla en vivo
```

Opciones de `dogfood run` que sirven aquí (`src/dogfood/comandos/run.py`):

- `--target`: objetivo. Por defecto `predicts`; para Android, `android`.
- `--escenarios`: ids separados por coma (`login`, `login-determinista`, `pago-determinista`).
- `--driver`: `web` o `android`; pisa el driver del escenario. El driver de la instancia sale de `driver:` en `dogfood.yaml`.
- `--motor`: `browser_use`, `bucle`, `patrol` o `integration_test`. Los dos últimos no usan LLM (ver `docs/ops/flutter.md`).
- `--vista`: vista en vivo de las ejecuciones (ver la sección 7).
- `--seed`, `--repeat`, `--personas`: semilla, repeticiones y cantidad de personas.
- `--sin-publicar`: no crea issues. Úsalo mientras pruebas.
- `--mantener-entorno`: no destruye el entorno al terminar.

Escenarios Android en `src/dogfood/objetivos/android/escenarios/`:

- `login`: agéntico, con el LLM y el bucle propio.
- `login-determinista`: motor `integration_test`, sin LLM; necesita las keys de la app y las credenciales (ver `docs/ops/flutter.md`).
- `pago-determinista`: el mismo esquema para el flujo de pago.

## 6. Dónde queda la evidencia

Cada ejecución guarda, en su carpeta bajo `runs/` (la que crea `Almacen`):

- `capturas/paso-NNN.png`: captura por paso (`screencap -p`).
- `arboles/paso-NNN.xml`: árbol de UI por paso (`uiautomator dump`).
- `logcat.txt`: logcat del paquete (filtrado con `--pid` cuando el proceso existe), con un extracto de errores (`E/` y `FATAL`).
- `video/dogfood-N.mp4`: solo con `pantalla.android: screenrecord`, en segmentos de 170 s.

La acción de cada paso y el resultado quedan en la base SQLite del almacén (`runs/dogfood.db`). `uv run dogfood runs` lista las corridas y su éxito por escenario.

Si la pantalla es Flutter y no expone Semantics, el hallazgo `accesibilidad` aparece en el panel (ver `docs/ops/flutter.md`).

## 7. Ver la pantalla: vista y panel «Dispositivos»

**En la vista en vivo** (`uv run dogfood run ... --vista`): cada ejecución muestra la pantalla del teléfono junto con el razonamiento de cada paso. La vista escucha en `vista:` de `dogfood.yaml` (por defecto `127.0.0.1:7460`; cambia el puerto con `--vista-puerto`). Solo acepta `127.0.0.1` o una IP de Tailscale. La vista nunca hace fallar la corrida: si no arranca, la corrida sigue sin ella.

**En el panel** (`uv run dogfood panel`, por defecto `127.0.0.1:7470`): la página **«Dispositivos»** (enlace en la barra lateral, ruta `/dispositivos`) muestra una tarjeta por dispositivo. Los Android salen de `adb devices` (el mismo listado que `dogfood android estado`); un dispositivo que no pasa `validar_destino` aparece con el motivo del rechazo. Los nodos iOS de `nodos:` también aparecen. Cada tarjeta es un `<img>` con el stream de `/dispositivos/<id>/mjpeg`, que se cierra cuando cierras la página. El panel necesita `runs/dogfood.db`, así que corre `dogfood run` al menos una vez antes.

Más detalle de la vista y del panel en `docs/ops/panel-y-vista.md`.

## 8. Lista de verificación manual pendiente (issue #32)

Lo que sigue requiere un Android real conectado por Tailscale y la app `mobile-mao` (`br.com.rupies.profissional`) instalada. No hay KVM ni dispositivo en el entorno de desarrollo; los tests usan un `adb` falso (`tests/test_android_tailscale.py`). Marca cada punto cuando lo compruebes:

- [ ] **Emparejar un celular por Tailscale.** `dogfood android emparejar 100.x.y.z:<puerto-de-vinculacion>` termina sin error y `dogfood android conectar 100.x.y.z:<puerto-de-depuracion>` imprime modelo y versión de Android.
- [ ] **`dogfood android estado` en verde.** El dispositivo sale con ✅ y el servidor adb dice que escucha solo en loopback.
- [ ] **Login agéntico de punta a punta.** Con `mobile-mao` instalada, `dogfood run --target android --escenarios login` recorre el login hasta el final con el dispositivo real.
- [ ] **Evidencia por paso.** Cada paso deja captura (`capturas/`), árbol (`arboles/`) y acción en el almacén de `runs/`.
- [ ] **Latencia de la vista < 2 s, medida.** Con `--vista`, el tiempo entre una acción en el teléfono y su aparición en la vista es menor de 2 s. Anota la medida (método y número) en este documento.
- [ ] **Fallo → issue con logcat.** Un fallo produce un issue con los pasos, las capturas, el `logcat.txt` y la gravedad, del mismo tipo que el del driver web.
- [ ] **Sin evidencia → no concluyente.** Si no hay captura, árbol ni logcat, la ejecución queda como no concluyente. No cuenta como aprobada ni como fallida.
- [ ] **Rechazo de destinos.** Con `host_puerto: 0.0.0.0:5555` o una IP de LAN, dogfood se niega a conectar antes de ejecutar `adb`.
- [ ] **Login determinista aprobado.** `dogfood run --target android --escenarios login-determinista --motor integration_test` termina `aprobado` (ver `docs/ops/flutter.md`).
- [ ] **Hallazgo de pantalla ciega en una pantalla real.** Una pantalla Flutter sin Semantics produce el hallazgo `accesibilidad` con su captura y su árbol en el panel.
- [ ] **Spike de la opción B (D18).** Medido según la sección 9.

## 9. Medir el spike de la opción B (Appium + UIAutomator2 o `mobile-mcp`)

La arquitectura deja la opción B como spike pendiente de dispositivo real (D18, `docs/arch/001-usuarios-agenticos.md`). La forma de decidir es medirla contra el driver actual en el mismo escenario:

1. **Mismo escenario, mismo dispositivo, misma versión de la app.** Solo `login`, con una semilla fija.
2. **Mismo número de repeticiones** para cada opción (`--repeat 3`, por ejemplo).
3. **Métricas:**
   - *Tiempo por paso*: duración de la ejecución dividida entre los pasos (`duracion_s` y `pasos` en la tabla `ejecuciones`).
   - *Tasa de esperas fallidas*: porcentaje de pasos en que no hubo árbol útil (el `uiautomator dump` volvió vacío tras los reintentos) o en que la acción devolvió `ok=False` porque el elemento no apareció.
4. **Anota** ambos números por opción en el propio spike, junto con el dispositivo y la versión de Android.

**Umbral propuesto para cambiar a B** (D18 no fija un número; confírmalo antes de usarlo): cambiar si la opción A tiene más de 10 % de esperas fallidas **y** B reduce el tiempo por paso al menos 30 % en las tres repeticiones. Si no se cumple, se queda A. Si hay dudas, se queda A: el cambio de driver es más caro que un reintento.

El spike se hace en una rama aparte, no en el núcleo de dogfood.
