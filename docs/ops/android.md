# Android real con dogfood: ADB por USB o Tailscale

Guía para probar una app Android real con el driver `android` (FR-29, issue #32). Cubre preparar el teléfono, conectarlo, la configuración de `dogfood.yaml`, correr el escenario de login, la verificación manual que aún falta y cómo medir el spike de la opción B.

> **Estado de esta rama.** El driver, `Adb` y `validar_destino` están implementados y probados con un `adb` falso (`src/dogfood/drivers/android.py`). Todavía no están conectados al flujo de `dogfood run`: `corrida.py` no lee `driver:` y el objetivo `android` lo registra F6.6.T1. Lo que sigue describe el uso previsto; las partes que dependen de esas tareas se marcan.

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

## 2. Conectar por USB

```bash
adb devices              # debe listar el serial con estado "device"
```

En `dogfood.yaml`, pon el serial en `driver.serial`. `validar_destino` acepta un serial solo si coincide con `^[A-Za-z0-9._-]+$`.

## 3. ADB inalámbrico sobre Tailscale

El emparejamiento se hace una sola vez a mano. Dogfood después se conecta solo.

1. En el teléfono: Depuración inalámbrica → *Vincular dispositivo con código de emparejamiento*. Anota la IP:puerto de vinculación y el código de 6 dígitos.
2. En el servidor, empareja con esa IP:puerto de vinculación:

```bash
adb pair 100.x.y.z:<puerto-de-vinculacion>
# Introduce el código de 6 dígitos cuando lo pida
```

3. En la pantalla principal de Depuración inalámbrica aparece otro puerto, distinto del de vinculación. Conecta con ese:

```bash
adb connect 100.x.y.z:<puerto-de-depuracion>
adb devices              # debe listar 100.x.y.z:<puerto> con estado "device"
```

4. En `dogfood.yaml`, pon `driver.host_puerto: 100.x.y.z:<puerto-de-depuracion>`. Al iniciar, `Adb.conectar()` ejecuta `adb connect` y comprueba que `get-state` sea `device`; si no, falla con un error claro.

Si el teléfono cambia de puerto (reinicio, cambio de red), repite el paso 3. El emparejamiento del paso 2 solo hace falta si olvidas el dispositivo.

## 4. Por qué ADB solo por USB, localhost o Tailscale

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

Un error lanza `ValueError` con el motivo, y el driver no ejecuta ningún comando. Si `serial` contiene `:`, se trata como `host:puerto`.

Límite de lo que valida: el rango `100.64.0.0/10` es el de CGNAT, y el validador acepta cualquier IP de ese rango. Lo que acota quién llega a tu teléfono es el ACL de tu tailnet; revísalo para que solo tu servidor pueda hablar con el puerto ADB del teléfono.

## 5. Configuración `driver:` en `dogfood.yaml`

```yaml
driver:
  tipo: android              # web (por defecto) | android
  serial: null               # USB; o bien:
  host_puerto: 100.x.y.z:5555   # localhost o Tailscale; nunca otra red
  paquete: com.ejemplo.app   # paquete de la app bajo prueba
  actividad: null            # opcional: si se da, abrir_app usa am start -n paquete/actividad
  apk: null                  # opcional: instala con adb install -r antes de la corrida
```

Campos reales de `Driver` en `src/dogfood/config.py`: `tipo`, `serial`, `host_puerto`, `paquete`, `actividad`, `apk`. Usa `serial` o `host_puerto`, no ambos.

## 6. Correr el escenario de login

```bash
dogfood run --target android --escenarios login
```

Opciones de `dogfood run` que sirven aquí (`src/dogfood/comandos/run.py`):

- `--target`: objetivo. Por defecto `predicts`. El objetivo `android` lo registra F6.6.T1.
- `--escenarios`: ids separados por coma, por ejemplo `login`.
- `--seed`: semilla de personas y asignación de escenarios; para reproducir una corrida.
- `--repeat`: repeticiones del mismo escenario.
- `--sin-publicar`: no crea issues. Úsalo mientras pruebas.
- `--mantener-entorno`: no destruye el entorno al terminar.

> **Nota sobre `--driver android`.** La especificación de F6.8.T1 lo pone en el comando, pero `dogfood run` **no tiene** esa opción en esta rama. El driver se elige en `driver:` de `dogfood.yaml`, no en la línea de comandos. Cuando F6.6.T1 cierre, revisa el comando con `dogfood run --help` antes de usarlo.

## 7. Dónde queda la evidencia

Cada ejecución guarda, en su carpeta bajo `runs/` (la que crea `Almacen`):

- `capturas/paso-NNN.png`: captura por paso (`screencap -p`).
- `arboles/paso-NNN.xml`: árbol de UI por paso (`uiautomator dump`).
- `logcat.txt`: logcat del paquete (filtrado con `--pid` cuando el proceso existe), con un extracto de errores (`E/` y `FATAL`).
- `video/dogfood-N.mp4`: `screenrecord` en segmentos de 170 s.

La acción de cada paso y el resultado quedan en la base SQLite del almacén. `dogfood runs` lista las corridas y su éxito por escenario.

## 8. Verificación manual pendiente (issue #32)

Lo que sigue requiere un Android real conectado por Tailscale. No hay KVM ni dispositivo en el entorno de desarrollo, así que los tests usan un `adb` falso. Marca cada punto cuando lo compruebes:

- [ ] **Login de punta a punta por Tailscale.** Con `host_puerto` apuntando a la IP Tailscale del teléfono, `dogfood run --target android --escenarios login` recorre el login hasta el final con el dispositivo real.
- [ ] **Evidencia por paso.** Cada paso deja captura (`capturas/`), árbol (`arboles/`) y acción en el almacén de `runs/`.
- [ ] **Fallo → issue.** Un fallo produce un issue con los pasos, las capturas, el logcat y la gravedad, del mismo tipo que el del driver web.
- [ ] **Sin evidencia → no concluyente.** Si no hay captura, árbol ni logcat, la ejecución queda como no concluyente. No cuenta como aprobada ni como fallida.
- [ ] **Rechazo de destinos.** Con `host_puerto: 0.0.0.0:5555` o una IP de LAN, dogfood se niega a conectar antes de ejecutar `adb`.

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
