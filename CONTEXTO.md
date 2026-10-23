# Contexto — dogfood

## Decisiones
- El repo es privado: `hectorcanaimero/dogfood`, en `/mnt/storage/project/dogfood`.
- Se construye con orch: PRD → arquitectura → specs → `orch atomize` → `orch run`.
- La documentación va en español.
- PRD: `docs/prd/001-usuarios-agenticos.md` (v0.2, objetivo predicts, aprobado).
- El primer objetivo es **predicts** (`/mnt/storage/project/predicts`), sobre una instancia propia de dogfood en el homelab. Después vienen Showly (agndaZAP) y agenda-barberia.
- El stack está en `docs/adr/0001-stack.md`.

## Pendiente
- PRD aprobado. Arquitectura en `docs/arch/001-usuarios-agenticos.md` y specs F0–F5 en `specs/` (30 tareas), esperando aprobación antes de `orch atomize --apply`.
- La arquitectura y los specs.
- Una prueba rápida con la skill `dogfood` sobre una app existente, antes de construir (opcional).
