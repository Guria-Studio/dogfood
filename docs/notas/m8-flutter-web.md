# M8 — `mobile-mao` compilada a web (F8.7.T2)

Corrida real de `tests/integracion/test_flutter_web.py` (`uv run pytest -m integracion tests/integracion/test_flutter_web.py -s`, 1 passed en 63,7 s). Los números salen de esa corrida; las capturas están en `/mnt/storage/cache/dogfood/flutter-web-vunwuxcm/ejec/capturas/` (`paso-001.png`, `paso-002.png`) y el resultado en `…/resultado.json`.

## Resultado

| Dato | Valor |
|------|-------|
| Flutter | 3.47.9 (stable), SDK `/mnt/storage/flutter` |
| Compilación (`flutter build web --release`, con copia y `pub get`) | **55,9 s**, compiló sin defines ni Firebase |
| Pantallas observadas | 2 (ambas `#/sign-in`: inicial y tras tocar el primer clicable) |
| Pantalla 1 | 2 elementos, 1 interactivo, 1 etiquetado, 0 con id, 2 nodos, **no ciega** |
| Pantalla 2 | igual que la 1 (tocó «Entrar com Google»; la app mostró «Falha na autenticação…» y la ruta no cambió) |
| `mobile-mao` y `packages/` | `git status --porcelain` igual antes y después |

Elementos vistos: un nodo sin etiqueta y el botón «Entrar com Google G» (`button`, clicable, etiquetado). Cobertura de etiqueta 1/1 = 100 % (umbral 0,6); ids 0/1.

## Lo que hubo que resolver para que compilara y se viera

1. **Monorepo:** `mobile-mao` depende de `../../packages/{core_api,core_auth,design_system,subscription}`. La copia de trabajo solo trae la carpeta de la app, así que el primer intento falló con `could not find package core_api at "../../packages/core_api"`. El test pone la copia en `<tmp>/apps/mobile-mao` y enlaza `<tmp>/packages` → `/mnt/storage/rupies/packages` (solo lectura). `FlutterWebObjetivo` no resuelve esto solo: hace falta una opción para copiar o enlazar los paquetes hermanos.
2. **CanvasKit y fuentes desde gstatic:** el build por defecto baja `canvaskit.js` y Roboto de `www.gstatic.com` / `fonts.gstatic.com`. Con la política de red del objetivo (solo el origen local) esos pedidos se bloquean y la app queda **en blanco, con 0 nodos y `ciega: true`** (corrida previa: 0 elementos, 0 nodos; la consola mostraba `Failed to fetch dynamically imported module …canvaskit.js`). El test agrega esos dos orígenes a `flutter_web.api_permitidas`. Mejor a futuro: compilar con `--no-web-resources-cdn` para que sea hermético; no se cambió porque el objetivo va «tal como está».

## Detector de F8.3.T1

El test arma un `ContextoDeteccion` con las dos observaciones y llama a `detectar`: devuelve **0 hallazgos**. Aquí es correcto (no quedó ciega), pero además `deteccion/flutter.py` solo mira ejecuciones `android`/`ios` y árboles XML, así que con driver `web` nunca reportaría una pantalla ciega. Si se quiere el hallazgo `accesibilidad` en el filtro web, el detector tiene que leer `Observacion.cobertura` del driver web.

## Recomendaciones para la app

- `Semantics(identifier: 'sign-in-google', label: 'Entrar com Google')` en el botón (hoy tiene etiqueta pero 0 ids) y `Key('sign-in-google')`.
- El mensaje «Falha na autenticação» no aparece como elemento: envolverlo en `Semantics(liveRegion: true, label: …)` para que un agente lo lea.
- «Termos» y «Privacidade» (enlaces dentro del texto) no salen como interactivos: darles `Semantics(link: true, label: 'Termos')` / `'Privacidade'`.
- El nodo sin etiqueta del árbol (primer elemento, texto vacío) es ruido: revisar que el logo tenga `Semantics(label: 'Rupies Mão')` o `excludeSemantics: true`.
- Las pantallas siguientes (tras el login) no se pudieron explorar: el login es solo con Google. Para recorrerlas hace falta un modo de prueba (p. ej. un `--dart-define` que omita el login) o credenciales.

## Después de F8.7.T3

`FlutterWebObjetivo` compila con `flutter build web --release --no-web-resources-cdn` (build hermético: CanvasKit y fuentes salen del propio `build/web`) y la copia de trabajo de F8.5.T4 trae sola los paquetes `path:` hermanos. El test de integración ya no enlaza `packages/` ni agrega orígenes de `gstatic` a `api_permitidas`; corre con el objetivo tal cual (`1 passed in 92.14s`).

| Dato | Valor |
|------|-------|
| Flutter | 3.47.9 (stable) |
| Compilación (copia, `pub get` y build) | **83,5 s** |
| Pantallas observadas | 2 (ambas `#/sign-in`) |
| Pantalla 1 | 2 elementos (1 etiquetado), 1 interactivo, 1 etiquetado, 0 con id, 2 nodos, **no ciega** |
| Pantalla 2 | igual que la 1 (tras tocar «Entrar com Google G») |
| Red con error (>= 400) | ninguna; consola solo con avisos de WebGL y un recurso bloqueado por el cliente |
| Hallazgos del detector | 0 |

La app ya no queda en blanco con la lista blanca solo local. Sigue pendiente lo de la sección anterior (detector sin lectura de `Observacion.cobertura` en web, ids 0/1).
