# Apps Flutter con dogfood: SDK, copia de trabajo, Semantics y motor determinista

Guía para probar apps Flutter (FR-34 a FR-39, NFR-12, NFR-13, decisiones D26 a D30) con dogfood: dónde vive el SDK, cómo apuntar a la app, cómo leer la cobertura de Semantics, qué agregar en la app para que dogfood la entienda, cómo escribir un escenario determinista (Patrol o `integration_test`), los secretos y el filtro web.

Ninguna de estas tareas toca el repositorio de la app. dogfood trabaja siempre sobre una copia.

## 1. El SDK de Flutter en `/mnt/storage/flutter`

El SDK y la caché de paquetes viven en `/mnt/storage/flutter`, no en el home. La razón: el NVMe del sistema es solo del sistema; el home y los cachés pesados van a los discos de datos. Por eso `dogfood` nunca instala nada en `~`.

Valores por defecto de `flutter:` en `src/dogfood/config.py`:

| Campo | Valor por defecto |
|---|---|
| `flutter.sdk` | `/mnt/storage/flutter/bin/flutter` |
| `flutter.patrol` | `/mnt/storage/flutter/.pub-cache/bin/patrol` |
| `flutter.pub_cache` | `/mnt/storage/flutter/.pub-cache` |
| `flutter.copia_trabajo` | `/mnt/storage/cache/dogfood/flutter` |
| `flutter.umbral_cobertura` | `0.6` |
| `flutter.timeout_s` | `1800` |

Al correr un test, `CorredorFlutter` (`src/dogfood/deterministico/corredor.py`) exporta `PUB_CACHE=<pub_cache>` y antepone el directorio de `flutter.sdk` al `PATH`. Así `flutter` y `patrol` usan el SDK y la caché de `/mnt/storage`, aunque tu shell apunte a otro lado.

**Actualizar el SDK:** usa el binario del SDK, no el que esté en otro lugar del PATH:

```bash
/mnt/storage/flutter/bin/flutter upgrade
/mnt/storage/flutter/bin/flutter --version
```

Después de actualizar, corre `uv run pytest` y un escenario determinista de prueba: los tests no usan el SDK real, así que solo una corrida real confirma que el SDK nuevo sigue compilando la app.

## 2. Apuntar dogfood a la app: `flutter.proyecto` y la copia de trabajo

En `dogfood.yaml`:

```yaml
flutter:
  proyecto: /mnt/storage/rupies/apps/mobile-mao   # raíz de la app (solo lectura)
  copia_trabajo: /mnt/storage/cache/dogfood/flutter
  umbral_cobertura: 0.6
```

- `flutter.proyecto` es la raíz de la app Flutter (la carpeta con `pubspec.yaml`). **Es solo lectura**: dogfood nunca escribe ahí.
- Antes de cada corrida determinista o de cada build web, `copia_de_trabajo` hace `rsync -a --delete` del proyecto a `<copia_trabajo>/<nombre-de-la-carpeta>` (para `mobile-mao`, `/mnt/storage/cache/dogfood/flutter/mobile-mao`). Excluye `build/`, `.dart_tool/` y `.git/`. Todo lo que dogfood añade (tests generados, `integration_test`, el build) queda en la copia.
- Si la copia y el proyecto se solapan (una dentro de la otra), dogfood se niega a seguir.
- Sin `flutter.proyecto`, un escenario determinista termina `no_concluyente` con el motivo `sin_proyecto`; no falla en silencio.

Las apps de referencia del proyecto son `mobile-mao` (`br.com.rupies.profissional`) y `mobile-empresa` (`br.com.rupies.empresa`), en `/mnt/storage/rupies/apps`.

## 3. Cobertura de Semantics y hallazgos `accesibilidad`

Un agente que mira una app Flutter ve un `FlutterView` sin texto si la app no expone sus widgets como Semantics. dogfood lo mide en cada paso (`src/dogfood/flutter/semantica.py`):

- **Interactivos**: nodos clicables, editables, enfocables con texto, checkables o desplazables (en Android); botones, campos, switches y enlaces (en iOS).
- **Etiquetados**: interactivos con texto o `content-desc` (o `label` en iOS).
- **Con id**: interactivos con `resource-id` o `identifier` estable (no el `e1`, `e2` generado por dogfood).
- **Ratio de etiqueta** = etiquetados / interactivos. Una pantalla Flutter es **ciega** si no tiene nodos o si su ratio está por debajo de `umbral_cobertura`.

La cobertura se ve en la vista y en el panel, y es lo que la detección convierte en hallazgos (`src/dogfood/deteccion/flutter.py`), solo para ejecuciones con driver `android` o `ios`:

| Caso | Hallazgo | Gravedad | Firma |
|---|---|---|---|
| Pantalla ciega (sin nodos o ratio de etiqueta < umbral) | `accesibilidad`: «pantalla sin Semantics» | media | `ciega` |
| Hay etiquetas, pero con ids en menos de la mitad de los interactivos | `accesibilidad`: «sin ids estables para tests» | baja | `sin_ids` |

Cada pantalla se reporta una sola vez por corrida, con captura y árbol como evidencia. Si una pantalla sale ciega, el bucle también fuerza una captura extra (`max_capturas_por_paso`), para que el agente vea lo que el árbol no dice.

## 4. Qué agregar en la app

Dogfood no modifica la app; estos cambios los haces tú en tu rama de la app. El objetivo es que cada control del flujo tenga un nombre estable que el test y la cobertura puedan usar.

- **`Semantics(label:, identifier:)`** alrededor de cada control interactivo que no tenga texto visible: `label` es lo que lee un lector de pantalla; `identifier` es el id estable: dogfood lo lee como `resource-id` en el árbol de Android y como `name` en el de iOS.
- **`Key` o `ValueKey`** en los campos y botones del flujo que el test toca. Dogfood los busca con `find.byKey(ValueKey('...'))` (integration_test) o con `$(#clave)` (Patrol).

Para el login (`login-determinista`), las keys que espera el escenario son `campo_email`, `campo_contrasena` y `boton_entrar`. En `mobile-mao` hoy no existe ninguna en `lib/features/` ni en el login: hay que añadirlas.

Para la compra de créditos (`pago-determinista`), el escenario anota en su cabecera las keys que faltan: `plano_tab`, `pacote_0`, `boton_continuar` y el `identifier` `pago_pendiente` de la pantalla «Pagamento em confirmação». Mientras no existan, los pasos siguen con texto (`texto:`) y dependen del idioma y del precio.

Un ejemplo mínimo:

```dart
TextField(
  key: const ValueKey('campo_email'),
  decoration: const InputDecoration(labelText: 'Correo'),
)

Semantics(
  identifier: 'boton_entrar',
  label: 'Entrar',
  child: ElevatedButton(
    key: const ValueKey('boton_entrar'),
    onPressed: _entrar,
    child: const Text('Entrar'),
  ),
)
```

Una `Key` no reemplaza al `Semantics`: la `Key` la usa el test; el `Semantics` la usa el agente y el árbol de accesibilidad. Pon las dos cuando el control es el flujo que se prueba.

Revisa después la cobertura con una corrida agéntica (`uv run dogfood run --target android --escenarios login --vista`): la pantalla deja de salir como ciega cuando la etiqueta y el id existen.

## 5. Escenario determinista: el bloque `deterministico`

Un escenario determinista corre un test Dart en lugar del bucle del agente. No usa LLM. Se activa con `--motor patrol` o `--motor integration_test` (`dogfood run`), o con `motor:` en el escenario. Sin bloque `deterministico` no hay nada que correr.

```yaml
id: login-determinista
titulo: Iniciar sesión (determinista)
superficies: [login]
driver: android
motor: integration_test
objetivo: Iniciar sesión con email y contraseña y llegar a la pantalla principal.
criterio_exito: Tras iniciar sesión se ve la pantalla principal y no queda el formulario de login.
max_pasos: 10
deterministico:
  pasos:
    - {accion: escribir, key: campo_email, valor: "{env:DOGFOOD_APP_EMAIL}"}
    - {accion: escribir, key: campo_contrasena, valor: "{env:DOGFOOD_APP_CONTRASENA}"}
    - {accion: tocar, key: boton_entrar}
    - {accion: esperar_texto, texto: Início, timeout_s: 20}
```

Cada paso (`PasoDeterministico` en `src/dogfood/dominio.py`):

| Campo | Qué es |
|---|---|
| `accion` | `tocar`, `escribir`, `esperar_texto`, `ver_texto`, `deslizar` o `volver`. |
| `key` | `ValueKey` del widget (o `Semantics(identifier:)`). Tiene prioridad sobre `texto` en `tocar` y `escribir`. |
| `texto` | Texto visible a buscar. Lo usan `esperar_texto` y `ver_texto` (esos dos ignoran `key`). |
| `valor` | Lo que se escribe. `"{env:NOMBRE}"` se pasa como `String.fromEnvironment('NOMBRE')`, con el valor del secreto. |
| `timeout_s` | Espera máxima, en segundos. Por defecto `10`. |

Dos opciones más del bloque:

- `dart_defines:` mapea nombres a literales o a `"{env:NOMBRE}"`, y se pasan como `--dart-define`.
- `archivo:` apunta a un test que ya existe en la app (ruta relativa a su raíz). Sin `archivo`, dogfood **genera** el test en `integration_test/dogfood/<id>_test.dart` dentro de la copia, a partir de `pasos`. El test generado importa `package:<nombre-del-pubspec>/main.dart` y llama a `app.main()`; la app debe tener esa forma.

Resultado: `aprobado` solo si el comando termina con código 0, hay al menos un test, todos están `ok` y no hay motivo de fallo. Un test en `fallo` da `fallo`. Lo demás (timeout, compilación, sin dispositivo, sin tests) da `no_concluyente`. El log se guarda en `runs/.../deterministico/salida.log` y el test generado en `deterministico/test.dart`; los valores de los secretos salen como `***`.

## 6. `integration_test` y Patrol

Dos herramientas, mismo contrato:

- **`integration_test`** (el SDK de Flutter): si la app no lo tiene en `dev_dependencies` de la copia, dogfood lo añade con `flutter pub add --dev integration_test --sdk=flutter` (solo en la copia). Corre `flutter test <test> -d <dispositivo> --reporter json`. No necesita nada nativo.
- **Patrol** (`patrol_cli`): se elige con `--motor patrol`. Dogfood **no** instala Patrol en la app: si la app no lo declara, el resultado es `app_sin_patrol` con la instrucción en el log. Corre `patrol test --target <test> --device <dispositivo>`.

Lo que Patrol pide en la app (dogfood solo comprueba que exista el paquete o el bloque; la configuración nativa la escribe la app):

1. **`pubspec.yaml`**: `patrol` en `dev_dependencies`, y un bloque `patrol:` de nivel superior con la configuración (nombre de la app y los paquetes de Android e iOS). `patrol bootstrap` (del CLI de Patrol, que ya está en `/mnt/storage/flutter/.pub-cache/bin`) puede generar la parte nativa; ejecútalo sobre la copia, no sobre `flutter.proyecto`, y revisa lo que escribe contra la documentación de la versión de Patrol que instales.
2. **Android**: un runner de instrumentación. En `android/app/build.gradle` (o `.kts`), `defaultConfig` con `testInstrumentationRunner` apuntando al runner de Patrol (`pl.leancode.patrol.PatrolJUnitRunner`), y una clase de test en `android/app/src/androidTest/` que corre los tests Dart. Sin esto, `patrol test` no llega al dispositivo.
3. **iOS**: un target de UI tests (`RunnerUITests`) en el proyecto de Xcode, con el archivo de entrada de Patrol, y los pods de Patrol en el `Podfile`. El determinista de iOS va por el nodo del Mac, pero `dogfood run` aún no lo cablea: hoy `driver: ios` con motor determinista lanza `NotImplementedError` (lo cierra F8.6.T4). Por ahora, la preparación de iOS se documentará en la guía del nodo (F8.9.T2).

Antes de confiar en un escenario, corre `patrol doctor` en la copia para ver qué le falta.

Patrol no es obligatorio. Si la app no lo quiere, usa `motor: integration_test` y el mismo bloque `deterministico`.

## 7. Secretos en `~/.config/dogfood/flutter.env`

Las credenciales de la app (y cualquier `{env:...}`) viven en `~/.config/dogfood/*.env`, nunca en `dogfood.yaml` ni en el escenario. `Config.cargar()` lee todos los `*.env` de ese directorio (o de `DOGFOOD_CONFIG_DIR` si lo defines). Crea el archivo con permisos restringidos:

```bash
mkdir -p ~/.config/dogfood
touch ~/.config/dogfood/flutter.env && chmod 600 ~/.config/dogfood/flutter.env
```

```dotenv
DOGFOOD_APP_EMAIL=usuario-de-prueba@ejemplo.com
DOGFOOD_APP_CONTRASENA=cambia-esto
```

Notas:

- Hoy `~/.config/dogfood/flutter.env` **no existe** en este equipo: créalo antes de correr `login-determinista`.
- Si falta una variable, el error dice `falta DOGFOOD_APP_EMAIL en ~/.config/dogfood/predicts.env`. El nombre de archivo que muestra es un valor por defecto de `Config.secreto` (solo `ROUTER_*` y `SLACK_*` tienen el suyo): la variable va en `flutter.env` aunque el mensaje diga `predicts.env`.
- Los valores nunca salen en el log: los tests se sustituyen por `***`, y `Config.__repr__` solo muestra los nombres.

## 8. Filtro web: `dogfood run --target flutter_web`

Una app Flutter compilada a web se prueba con el driver web, sin celular (D30). El objetivo `flutter_web` (`src/dogfood/objetivos/flutter_web/__init__.py`) registra los escenarios `login` y `explorar`, y el driver web calcula la misma cobertura de Semantics (con `flutter=True`), pero los hallazgos `accesibilidad` solo se generan para ejecuciones Android e iOS (sección 3).

```bash
uv run dogfood run --target flutter_web --escenarios login
uv run dogfood run --target flutter_web --escenarios explorar --vista
```

Cómo obtiene la app servida:

- Si `flutter_web.build_dir` apunta a un `build/web` ya compilado (con `index.html`), lo sirve.
- Si no, y hay `flutter.proyecto`, copia la app (sección 2) y corre `flutter build web --release` dentro de la copia, con los `flutter_web.dart_defines` como `--dart-define`.
- El servidor es estático y local, en `flutter_web.host` (`127.0.0.1` por defecto) y `flutter_web.puerto` (`7480`).

```yaml
flutter_web:
  build_dir: null                # ruta a build/web ya compilado; si es null, se compila desde flutter.proyecto
  host: 127.0.0.1                # solo loopback o una IP de Tailscale
  puerto: 7480
  api_permitidas: []             # orígenes extra que la app puede llamar (p. ej. https://api.ejemplo.com)
  dart_defines: {}               # literales o "{env:NOMBRE}"
```

El navegador solo puede abrir el origen de la app y los de `api_permitidas`; cualquier otra URL se bloquea.

No hay `docs/notas/m8-flutter-web.md` en el repo, así que esta guía no lo cita. La prueba de integración con Chromium real está en `tests/integracion/`.

## 9. Lista de comprobación antes de una corrida

- [ ] `/mnt/storage/flutter/bin/flutter --version` responde y `PUB_CACHE` apunta a `/mnt/storage/flutter/.pub-cache`.
- [ ] `flutter.proyecto` apunta a la app (solo lectura) y `copia_trabajo` está fuera de ella.
- [ ] `~/.config/dogfood/flutter.env` existe, con `chmod 600`, y tiene `DOGFOOD_APP_EMAIL` y `DOGFOOD_APP_CONTRASENA` si el escenario las usa.
- [ ] La app tiene las keys del escenario (`campo_email`, `campo_contrasena`, `boton_entrar`) y, si usa Patrol, su configuración nativa.
- [ ] Un celular conectado (`uv run dogfood android estado` en verde, ver `docs/ops/android.md`) o un `build/web` servido, según el objetivo.
