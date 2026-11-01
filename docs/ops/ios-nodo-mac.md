# Nodo iOS en el Mac M1 (guria → Mac → iPhone)

Puesta en marcha manual del nodo iOS (FR-38, NFR-12, issue #32) para Héctor. Dogfood corre en **guria** (el servidor); el **Mac M1** compila y maneja el iPhone por Appium/XCUITest; guria le manda trabajos por SSH sobre Tailscale. Esta guía no tiene tests: es una lista para seguir de arriba abajo, con casillas. Marca cada paso cuando lo compruebes.

Reglas que atraviesan toda la guía:

- **Nada de SSH, Appium ni el puerto 9100 fuera de Tailscale.** Appium escucha en `127.0.0.1:4723` y WebDriverAgent (MJPEG) en `127.0.0.1:9100` del Mac; guria llega a ellos solo por el túnel SSH (`ClienteNodo.tunel`, `ssh -N -L`). Nunca `0.0.0.0`.
- **Ningún secreto en `dogfood.yaml`.** Las credenciales de la app van en `~/.config/dogfood/flutter.env` (ver `docs/ops/flutter.md`).

Comandos de esta guía: `dogfood nodo estado|ejecutar` (`src/dogfood/comandos/nodo.py`), `dogfood run` con `--target`, `--driver`, `--escenarios`, `--motor`, `--vista` (`src/dogfood/comandos/run.py`) y `dogfood panel` (`src/dogfood/comandos/panel.py`).

## 1. Requisitos

- [ ] **Mac M1** con macOS al día (Ajustes → General → Actualización de software).
- [ ] **Xcode** desde la App Store, abierto una vez para aceptar la licencia y dejar que instale componentes adicionales.
- [ ] **Command line tools** y licencia aceptada:

  ```bash
  xcode-select --install
  sudo xcodebuild -license accept
  xcodebuild -version        # debe imprimir "Xcode X.Y"
  ```

- [ ] **Cuenta de desarrollador de Apple** (de pago, 99 USD/año). Con la cuenta gratuita, el certificado de desarrollo caduca a los **7 días**: WebDriverAgent deja de arrancar y hay que volver a firmar y reinstalar cada semana. La de pago dura un año.
- [ ] **iPhone** con **modo desarrollador** activado (Ajustes → Privacidad y seguridad → Modo de desarrollador; reinicia y confirma). Conéctalo al Mac por cable la primera vez y pulsa *Confiar* en ambos.
- [ ] **iPhone desbloqueado** durante las corridas (ver «device locked» en la sección 8).

## 2. Tailscale y SSH en el Mac

- [ ] **Tailscale** instalado en el Mac, con sesión en el mismo tailnet que guria. Anota su IP:

  ```bash
  tailscale ip -4            # en el Mac: su IP 100.x.y.z
  ```

- [ ] **Sesión remota** activada: Ajustes del Sistema → General → Compartir → *Sesión remota*. Solo tu usuario debe poder entrar.
- [ ] **Clave SSH de guria** en `~/.ssh/authorized_keys` del Mac (con permisos `600`), o bien **Tailscale SSH** si prefieres no gestionar claves. Con la clave en su sitio:

  ```bash
  # en guria: comprueba que la clave que usa dogfood es la que está en el Mac
  ssh -o BatchMode=yes hector@100.x.y.z true && echo "SSH ok"
  ```

  `BatchMode=yes` falla en vez de pedir contraseña, igual que lo hace dogfood. Si imprime `Permission denied (publickey)`, la clave no está en `authorized_keys` o el usuario no es `hector`.

- [ ] **Firewall**: no abras SSH, Appium (4723) ni 9100 al resto de la red. Si usas el firewall del Mac, deja la sesión remota solo para Tailscale.

## 3. Herramientas en el Mac

- [ ] **Homebrew**: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- [ ] **uv** y **Node** (para Appium):

  ```bash
  brew install uv node
  ```

- [ ] **Appium 2 con el driver XCUITest**:

  ```bash
  npm i -g appium
  appium driver install xcuitest
  appium driver list --installed     # debe aparecer xcuitest
  ```

- [ ] **Firmar WebDriverAgent con tu equipo**. Appium compila WDA la primera vez que abre una sesión, pero el driver de dogfood no manda credenciales de firma (solo `udid` y `bundleId`), así que la firma se configura una vez en Xcode. Busca el proyecto (la ruta exacta depende de la versión del driver):

  ```bash
  find ~/.appium -name WebDriverAgent.xcodeproj -maxdepth 6
  ```

  Ábrelo con Xcode y, en los targets **WebDriverAgentLib**, **WebDriverAgentRunner** e **IntegrationApp** si aparece:

  - [ ] *Signing & Capabilities* → *Team*: tu equipo de desarrollador.
  - [ ] *Bundle Identifier* propio, p. ej. `com.hector.WebDriverAgentRunner` (el de Appium es de otra cuenta y no se puede firmar).
  - [ ] Sin errores de firma en *Product → Build* con el iPhone seleccionado como destino.

- [ ] **Appium responde y arranca solo**. Prueba a mano:

  ```bash
  appium --address 127.0.0.1 --port 4723     # déjalo corriendo en otra terminal
  curl -s http://127.0.0.1:4723/status        # debe devolver JSON con "ready": true
  ```

  Para la prueba de sesión real, con el iPhone conectado y desbloqueado, usa el mismo protocolo que el nodo. Ojo: esta sesión deja Appium corriendo, así que ciérrala después:

  ```bash
  echo '{"id":"prueba-sesion","tipo":"sesion_appium","udid":"UDID_DEL_IPHONE"}' | dogfood nodo ejecutar
  echo '{"id":"prueba-cerrar","tipo":"cerrar_sesion","udid":"UDID_DEL_IPHONE"}' | dogfood nodo ejecutar
  ```

  La primera debe imprimir `ok` y `appium_url`. Si el Appium que arrancó la prueba no es del nodo, `cerrar_sesion` lo deja tal cual: el nodo solo mata el proceso que él mismo arrancó (`appium.pid`).

- [ ] **Flutter** en el Mac (solo si vas a correr Patrol o `integration_test`). Instálalo en una ruta que tenga `flutter` en el PATH de un shell no interactivo, por ejemplo con Homebrew:

  ```bash
  brew install --cask flutter
  flutter doctor                              # Xcode y CocoaPods en verde
  ```

- [ ] **Patrol CLI** (solo para el escenario `login-patrol`):

  ```bash
  dart pub global activate patrol_cli
  patrol --version                            # el nodo lo busca con `which patrol`
  ```

  Si `patrol` no está en el PATH de SSH, añade `~/.pub-cache/bin` al PATH de `~/.zshenv` (los shells no interactivos no leen `~/.zshrc`).

- [ ] **dogfood en el PATH del Mac**. Clona el repo (privado, `hectorcanaimero/dogfood`) y instala el comando con uv:

  ```bash
  git clone git@github.com:hectorcanaimero/dogfood.git ~/dogfood
  cd ~/dogfood && uv tool install .
  dogfood nodo --help
  ```

  `uv tool install` deja el binario en `~/.local/bin`. Ese directorio tiene que estar en el PATH de SSH, no solo en el de tu terminal (ver sección 8).

- [ ] **App de referencia** clonada en el Mac, en una ruta fija. Esa ruta va en `nodos.<nombre>.proyectos` (sección 4).

## 4. Configurar guria

En `dogfood.yaml` de guria (el archivo real no está en el repo; partes de `dogfood.example.yaml`):

```yaml
nodos:
  mac:                          # nombre del nodo; lo usa driver.nodo
    host: 100.x.y.z             # IP de Tailscale del Mac; nunca otra red
    usuario: hector             # usuario SSH del Mac (^[a-z_][a-z0-9_.-]*$)
    puerto_ssh: 22
    comando: dogfood nodo       # en el PATH de SSH del Mac; si no se encuentra, ruta absoluta
    dir_trabajo: ~/dogfood-nodo # carpeta de trabajo en el Mac (por defecto)
    proyectos:
      mobile-mao: /Users/hector/rupies/mobile-mao   # nombre de flutter.proyecto → ruta en el Mac

driver:
  tipo: ios
  nodo: mac
  udid: UDID_DEL_IPHONE         # `dogfood nodo estado` lo lista
  bundle_id: br.com.rupies.profissional
```

Notas:

- `proyectos` se busca por el **nombre** de `flutter.proyecto` (la carpeta, `mobile-mao`). Si no coincide, dogfood usa la primera entrada. Con una sola app, basta con una entrada.
- `comando` es la orden que guria ejecuta por SSH. Con uv instalado en `~/.local/bin`, pon la ruta absoluta del binario, p. ej. `/Users/hector/.local/bin/dogfood nodo`.
- `bundle_id` y `udid` son obligatorios para el driver iOS; si falta uno, `IosObjetivo` falla antes de abrir ninguna sesión.

## 5. Comprobar el nodo

- [ ] **En el Mac**, en local:

  ```bash
  dogfood nodo estado                 # Xcode, Flutter, Patrol, Appium y dispositivos (udid, nombre, os)
  dogfood nodo estado --json          # la misma información en una línea de JSON
  ```

  `estado` crea `~/dogfood-nodo` si no existe. El iPhone debe aparecer en la lista con su UDID.

- [ ] **Desde guria**, por SSH, con el mismo comando que usa el cliente:

  ```bash
  ssh -o BatchMode=yes -o ConnectTimeout=10 hector@100.x.y.z dogfood nodo estado --json
  ```

  Debe imprimir una línea JSON con `xcode`, `dispositivos` y `appium`. Un `command not found` significa que el PATH de SSH no tiene uv: usa la ruta absoluta en `comando`.

- [ ] El `udid` de `driver.udid` aparece en la lista de `dispositivos`. Si no, `IosObjetivo` se detiene antes de abrir la sesión con el mensaje «El iPhone … no aparece en el nodo».

## 6. Correr el login

Dogfood abre el túnel SSH hacia `127.0.0.1:4723` y `127.0.0.1:9100` del Mac (`ClienteNodo.tunel([4723, 9100])`) y abre la sesión de Appium en el iPhone. Corre desde guria:

```bash
# agéntico: el LLM elige los pasos (motor bucle, driver ios)
uv run dogfood run --target ios --driver ios --escenarios login --vista

# determinista: Patrol en el Mac, sin LLM
uv run dogfood run --target ios --driver ios --escenarios login-patrol
```

- [ ] **Login agéntico** termina y la corrida aparece en la lista de corridas (`uv run dogfood runs`).
- [ ] **Login determinista** (`login-patrol`) pasa en el Mac. Antes, las Keys y las credenciales de la app tienen que estar listas (ver `docs/ops/flutter.md`, secciones 4 y 7).
- [ ] **Vista en vivo** (`--vista`): en `http://127.0.0.1:7460` se ve la pantalla del iPhone junto al razonamiento de cada paso. Si el puerto está ocupado, usa `--vista-puerto`. La vista nunca tumba la corrida.
- [ ] **Panel**: `uv run dogfood panel` abre en `127.0.0.1:7470`. En **Dispositivos** aparece `mac (hector@100.x.y.z)`. La pantalla del iPhone solo se ve **mientras corre una sesión**: el panel lee el MJPEG de `http://127.0.0.1:9100`, y ese puerto existe en guria únicamente por el túnel que abre el objetivo durante la corrida.

  Si la pantalla sale en negro o no aparece, la corrida sigue funcionando: el MJPEG es solo para mirar. Revisa primero que la corrida esté activa y el túnel abierto (sección 8).

## 7. Correr sin mirar

Para correr sin la vista ni el panel, quita `--vista`. Los artefactos de cada trabajo llegan a guria por `rsync` desde `dir_trabajo/<id>/` del Mac: logs, reporte de Patrol y captura final.

## 8. Problemas comunes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| WDA no arranca, `Signing for "WebDriverAgentRunner" requires a development team` | WDA sin firmar, o firmado con el bundle id de Appium | Abre `WebDriverAgent.xcodeproj` en Xcode y completa la sección 3 («Firmar WebDriverAgent»). Con cuenta gratuita, caduca a los 7 días: vuelve a firmar. |
| `device locked` / la sesión se cae al bloquear | El iPhone está bloqueado o la pantalla se apaga | Mantén el iPhone desbloqueado durante la corrida. En Ajustes → Pantalla y brillo → Bloqueo automático, sube el tiempo. |
| `El nodo no abrió Appium: Appium no respondió en 30 s (ver appium.log)` | Appium no arranca o no encuentra Xcode/WDA | Lee `~/dogfood-nodo/appium.log` en el Mac. Prueba `appium` a mano (sección 3). Si falla con WDA, vuelve a firmar. |
| `Permission denied (publickey)` | La clave de guria no está en `authorized_keys` del Mac, o el usuario no es el de `usuario` | Comprueba la clave y ejecuta `ssh -o BatchMode=yes hector@100.x.y.z true` desde guria. El mensaje de dogfood dice «configura la clave SSH y Tailscale; ver docs/ops/ios-nodo-mac.md». |
| `command not found` / `instala dogfood en el Mac` | `dogfood` no está en el PATH de SSH | Pon la ruta absoluta en `nodos.<nombre>.comando` o añade `~/.local/bin` al PATH en `~/.zshenv`. |
| El túnel no abre: `bind: Address already in use` | El puerto local 4723 o 9100 de guria está ocupado (otra sesión, o un Appium o WDA viejo) | Mira qué lo usa: `ss -ltnp \| grep -E ':(4723\|9100)\b'`. Termina el proceso que sobra. El túnel usa `ExitOnForwardFailure=yes`, así que falla en vez de quedarse a medias. |
| `el nodo no respondió en N s` | Tailscale caído o el Mac dormido | Mantén el Mac despierto (Ajustes → Batería → Evitar que el Mac entre en reposo) y comprueba `tailscale status`. |
| `Falta driver.nodo` o `faltan driver.udid o driver.bundle_id` | `dogfood.yaml` incompleto | Completa la sección 4. |
| `El iPhone <udid> no aparece en el nodo` | iPhone desconectado, sin confiar en el Mac, o modo desarrollador apagado | Reconecta por cable, confía en el Mac y repite `dogfood nodo estado`. |

Si el nodo se queda con un Appium viejo, para el que arrancó dogfood (`cerrar_sesion` solo mata el suyo) con `kill $(cat ~/dogfood-nodo/appium.pid)` en el Mac.

## Referencias

- Contrato del nodo y `Trabajo`: `src/dogfood/nodos/protocolo.py`; comando: `src/dogfood/comandos/nodo.py`; runner: `src/dogfood/nodos/runner.py`.
- Cliente SSH, túnel y rsync: `src/dogfood/nodos/cliente.py`; objetivo: `src/dogfood/objetivos/ios/__init__.py`; driver: `src/dogfood/drivers/ios.py`.
- Escenarios: `src/dogfood/objetivos/ios/escenarios/login.yaml` y `login-patrol.yaml`.
- Configuración: `src/dogfood/config.py` (`Nodo`, `Driver`) y `dogfood.example.yaml`.
- Apps Flutter, Keys y secretos: `docs/ops/flutter.md`. Android: `docs/ops/android.md`. Vista y panel: `docs/ops/panel-y-vista.md`.
