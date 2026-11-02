---
id: 20261102-panel-web-f11-rutas-por-proyecto-redirecciones-v
title: 'Panel web F11: rutas por proyecto, redirecciones viejas y componentes compartidos'
area:
    - web/src/**
    - web/e2e/**
tags:
    - router
    - navegacion
    - f11
source: agent
task: F11.1.T1
created: "2026-11-02"
---

- Las pantallas viven en /proyectos/$proyecto/<seg>. Las secciones están definidas en web/src/components/layout/pantallas.ts (GRUPOS_PROYECTO); de ahí salen la barra de proyecto, las migas (migas.ts) y la paleta ⌘K. Si agregas una sección, súmala ahí.
- Shell muestra BarraProyecto cuando useParams({strict:false}).proyecto existe. No hay un archivo de layout para proyectos.$proyecto.
- Las rutas viejas (/corridas/$id, /ejecuciones/$id, /casos, /recorridos, /dispositivos, /vista) redirigen en beforeLoad a PROYECTO_POR_DEFECTO ('predicts'). PROYECTOS es una lista fija hasta F11.1.T2: cámbiala por GET /api/proyectos.
- /corridas/$id/reporte sigue siendo global: corridas.$id.index.tsx es la que redirige, así que el reporte no queda debajo de ella.
- Componentes compartidos: components/comun/Estado.tsx (BadgeEstado, PestanasEstado con ?estado=), Datos.tsx (Prioridad, Avatar, Paginacion, BarraApilada), estados.ts (ids paso/fallo/bloqueado/corriendo/planeado/no_concluyente). Vacio acepta ilustracion="lista|calendario|grafico|carpeta". PageHeader pasó a llamarse EncabezadoPagina (subtitulo en lugar de descripcion).
- Si `npx tsr generate` falla, `npx vite build` regenera routeTree.gen.ts. Navegar con search tipado y to:'.' necesita `as never` en el reducer de search.
- Ahora '/' es Inicio. Los tests de corridas que montan el routeTree real deben usar /proyectos/predicts/corridas.
