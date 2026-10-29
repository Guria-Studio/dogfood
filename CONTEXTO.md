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
- v0.3 del PRD y v0.2 de la arquitectura suman M6 y M7 (issues #32–#35): motores intercambiables (`api` / `claude_code` con el plan Max), interfaz `Driver` con driver web y Android (ADB), bucle de agente propio, contrato de resultado (aprobado / fallo / no concluyente), vista en vivo y panel de corridas. Specs: `specs/f6-motores-android.md` y `specs/f7-vista-panel.md`.

## Restricciones de F6–F7
- No hay KVM (sin emulador) ni, por ahora, Android conectado: los tests usan un `adb` falso; la prueba de punta a punta con dispositivo real queda como verificación manual (`docs/ops/android.md`).
- ADB solo por USB, localhost o Tailscale; vista y panel solo en `127.0.0.1` o una IP de Tailscale. Nunca `0.0.0.0`.
- Los tests no llaman al `claude` real: usan un script falso en el PATH.

## Pendiente
- Issue #28 (bug de mapeo encontrado por dogfood en predicts): fuera de F6–F7.
- Verificación manual con Android real por Tailscale (criterios E2E del issue #32).
