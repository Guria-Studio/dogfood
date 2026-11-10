# dogfood

Usuarios agénticos que usan tu app de verdad, en un navegador real, y entregan dos cosas:

1. **Issues**: errores técnicos, flujos rotos, bugs de lógica y casos límite, cada uno con pasos para reproducir, capturas, logs y gravedad. Se publican como issues de GitHub.
2. **Opinión de usuarios**: cada persona cuenta qué no entendió, qué le frustró y qué le sobró. El reporte va por pantalla y por tipo de usuario.

Ver [docs/VISION.md](docs/VISION.md). Se construye con [orch](https://github.com/Guria-Studio/orch): PRD → arquitectura → specs → tareas.

```bash
uv sync
uv run pytest
uv run dogfood
```
