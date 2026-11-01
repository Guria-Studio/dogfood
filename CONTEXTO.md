# Contexto — dogfood

## Decisiones
- El repo es privado: `hectorcanaimero/dogfood`, en `/mnt/storage/project/dogfood`.
- Se construye con orch: PRD → arquitectura → specs → `orch atomize` → `orch run`.
- La documentación va en español.
- PRD: `docs/prd/001-usuarios-agenticos.md` (v0.2, objetivo predicts, aprobado).
- El primer objetivo es **predicts** (`/mnt/storage/project/predicts`), sobre una instancia propia de dogfood en el homelab. Después vienen Showly (agndaZAP) y agenda-barberia.
- El stack está en `docs/adr/0001-stack.md`.

## Estado
- F0–F5 (30 tareas) hechas y mergeadas.
- v0.3 del PRD y v0.2 de la arquitectura suman M6 y M7 (issues #32–#35): motores intercambiables (`api` / `claude_code` con el plan Max), interfaz `Driver` con driver web y Android (ADB), bucle de agente propio, contrato de resultado (aprobado / fallo / no concluyente), vista en vivo y panel de corridas. Specs: `specs/f6-motores-android.md` y `specs/f7-vista-panel.md`. F6–F7 hechas (44/44).
- v0.4 del PRD y v0.3 de la arquitectura suman M8 «Flutter en celular real» (FR-34 a FR-39, NFR-12, NFR-13; issue #32): ADB sobre Tailscale, cobertura de Semantics de Flutter con respaldo por visión, motor determinista Patrol / `integration_test`, fuente de frames común (pantalla real en vista y panel), nodo iOS en el Mac M1 de Héctor por SSH y filtro web con la app compilada a web. Spec: `specs/f8-flutter-celular-real.md`.

## Restricciones de F6–F7
- No hay KVM (sin emulador) ni, por ahora, Android conectado: los tests usan un `adb` falso; la prueba de punta a punta con dispositivo real queda como verificación manual (`docs/ops/android.md`).
- ADB solo por USB, localhost o Tailscale; vista y panel solo en `127.0.0.1` o una IP de Tailscale. Nunca `0.0.0.0`.
- Los tests no llaman al `claude` real: usan un script falso en el PATH.

## Restricciones de F8
- Apps Flutter de referencia, **solo lectura**: `/mnt/storage/rupies/apps/mobile-mao` (`br.com.rupies.profissional`) y `/mnt/storage/rupies/apps/mobile-empresa` (`br.com.rupies.empresa`). dogfood trabaja sobre copias en `/mnt/storage/cache/dogfood/flutter`.
- SDK de Flutter en `/mnt/storage/flutter` con `PUB_CACHE=/mnt/storage/flutter/.pub-cache` (el NVMe es solo del sistema: nada en el home). Los tests por defecto no lo usan.
- Sin celular, sin KVM y sin Mac en CI: `adb`, `flutter`, `patrol`, `ssh`, `rsync`, `ffmpeg` y Appium se reemplazan por runners falsos. Appium, el MJPEG de WebDriverAgent (9100) y el SSH del nodo solo por loopback o Tailscale.

## Pendiente
- Issue #28 (bug de mapeo encontrado por dogfood en predicts): fuera de F6–F7.
- Verificación manual con Android real por Tailscale (criterios E2E del issue #32): lista en `docs/ops/android.md` (F8.9.T1).
- Puesta en marcha del nodo iOS en el Mac (Xcode, cuenta de desarrollador de Apple, WebDriverAgent firmado, Appium): `docs/ops/ios-nodo-mac.md` (F8.9.T2).
