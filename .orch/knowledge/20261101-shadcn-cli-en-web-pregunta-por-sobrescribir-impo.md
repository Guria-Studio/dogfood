---
id: 20261101-shadcn-cli-en-web-pregunta-por-sobrescribir-impo
title: 'shadcn CLI en web/: pregunta por sobrescribir, importa ''cn'' y trae TanStack Table v9'
area:
    - web/**
tags:
    - shadcn
    - vitest
    - tanstack-table
source: agent
task: F9.4.T1
created: "2026-11-01"
---

- `npx shadcn add` se queda esperando en «already exists, overwrite?» incluso con -y: pásale `n` por stdin (`(for i in $(seq 20); do echo n; sleep 1.5; done) | npx shadcn add ...`) para no pisar los ui/ hechos a mano (estilo forwardRef y variables HSL).
- Los componentes nuevos importan `cn` desde "cn" y el CLI agrega el paquete `cn` a package.json: cámbialo a '@/lib/utils' y desinstala `cn`. Las variables --sidebar-* que agrega a styles.css usan otra paleta: ya están mapeadas al tema (--sidebar, --sidebar-accent).
- `npm i @tanstack/react-table` instala la v9 (otra API, useTable). El ejemplo *data table* de shadcn es v8: usa `@tanstack/react-table@^8`.
- jsdom no trae ResizeObserver ni scrollIntoView (cmdk, Recharts) ni matchMedia (use-mobile): los stubs van en src/test/setup.ts, y use-mobile usa `window.matchMedia?.`.
- El Shell ahora necesita un SidebarProvider: los tests que montan BarraLateral o SelectorTema sueltos tienen que envolverlos en uno. Para probar la app entera, monta el `routeTree` real de routeTree.gen (ver features/pulido/pulido.test.tsx).
- Después de las capturas o de `npm run build`, borra src/dogfood/panel/estatico/ antes de correr pytest. Y no uses `pkill -f` con un patrón que aparezca en tu propio comando: mata tu propio shell.
