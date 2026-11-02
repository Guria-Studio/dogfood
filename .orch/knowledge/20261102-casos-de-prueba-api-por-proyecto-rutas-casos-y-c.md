---
id: 20261102-casos-de-prueba-api-por-proyecto-rutas-casos-y-c
title: 'Casos de prueba: API por proyecto, rutas casos/ y casos/$tc, sheet con ?caso='
area:
    - src/dogfood/panel/api_casos.py
    - web/src/features/casos/**
    - web/src/routes/proyectos.$proyecto.casos*
source: agent
task: F11.2.T1
created: "2026-11-02"
---

- API: GET /api/proyectos/{slug}/casos?estado=&q=&prioridad= y /casos/{tc} viven en src/dogfood/panel/api_casos.py. Los estados son los del front (planeado, corriendo, paso, fallo, bloqueado, no_concluyente), mapeados desde api_plan.casos(). Los TC### se numeran por la primera aparición del caso en las corridas del proyecto, ordenadas por inicio.
- El prompt de arreglo se arma y se redacta en el servidor (falla_detalle.prompt) con las contraseñas de las personas y los secretos de cfg. El front solo lo copia.
- La ruta proyectos.$proyecto.casos.tsx pasó a casos.index.tsx (con validateSearch estado/q/prioridad/caso) más casos.$tc.tsx a pantalla completa. Para enlazar al detalle usa '/proyectos/$proyecto/casos/$tc'; para abrir el sheet, ?caso=TCxxx.
- El SheetTitle de Radix también es un heading: si repite el título visible, getByRole('heading') encuentra dos. Ponle otro texto en sr-only.
- En los tests web, userEvent.setup() instala un portapapeles falso: lee lo copiado con navigator.clipboard.readText().
