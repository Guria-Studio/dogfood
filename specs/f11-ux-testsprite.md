---
type: spec
project_id: dogfood
phase: 11
version: 0.1
depends_on:
  - docs/arch/002-panel-react.md
  - docs/analisis/testsprite.md
  - specs/f10-confiable-testsprite.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-11-01
title: UX estilo TestSprite — proyectos, casos de prueba e insights
---

# F11 — UX estilo TestSprite

Héctor revisó el dashboard de TestSprite (capturas y un video del 2026-11-01) y pidió que el panel de dogfood tenga esa UX, mejorada con lo que dogfood ya hace y TestSprite no (personas, opinión de usuario, oráculo de números, celular real). El análisis está en `docs/analisis/testsprite.md` (léelo antes de cada tarea).

**Qué se copia de TestSprite (referencia obligatoria para todas las tareas):**

- **Navegación en dos niveles.**
  - Barra global a la izquierda:
    - selector de espacio arriba;
    - Inicio, Proyectos;
    - Automatización: Suites, Programaciones;
    - Ajustes: General, Integraciones;
    - abajo: Ayuda y el usuario.
  - Al entrar a un proyecto aparece una **segunda barra** con «← Volver» y una chip del tipo (Web, Android, iOS). Tiene estos grupos:
    - Configuración: Fuentes, Acción de GitHub;
    - Espacio de trabajo: Casos de prueba con su conteo, Corridas con su conteo;
    - Análisis: Insights;
    - Actividad: Registro;
    - Ajustes del proyecto: General, Ejecución (con Entorno, Comportamiento y Archivos de prueba), Notificaciones.
- **Encabezado** con migas (`proyecto › Casos de prueba`), y a la derecha «Compartir» y «Copiar link».
- **Títulos de página en serif** grandes, con una línea gris de subtítulo («Todos los casos de este proyecto, agrupados por caso de uso, con su último resultado.»).
- **Tema claro cálido** por defecto: fondo hueso `#FAFAF7`, tarjetas blancas, borde `#E8E6E1` de 1 px, radio 8–12 px, texto casi negro, verde de marca para éxito y acentos, rojo apagado para fallo. Tipografía: serif (Instrument Serif o Newsreader, con `@fontsource`) en títulos, Geist en el resto. El tema oscuro de F9 queda como opción.
- **Botón primario negro** con ícono («+ Nuevo proyecto»), buscador con lupa, botones-ícono de filtro y orden, paginación abajo («25 filas ▾ · ‹ Anterior 1 Siguiente ›»).
- **Pestañas de estado con conteo**: Todos 19 · Planeados 0 · Generados 0 · Corriendo 0 · Pasaron 2 · Fallaron 17 · Bloqueados 0. Cada una tiene su ícono de color.
- **Filas agrupadas por caso de uso.** El encabezado del grupo es colapsable, con el conteo y una barra apilada verde y roja a la derecha. Cada fila muestra:
  - el ID `TC017`;
  - el badge de estado y «· hace 10 meses»;
  - el nombre en negrita y, debajo, el **resumen de la falla en una línea roja**;
  - la prioridad con un ícono de barras.
- **Detalle en un panel lateral (sheet) que se superpone a la lista**, con la URL `?caso=<id>`, sin cambiar de página:
  - arriba: título, chip de estado y las acciones Compartir, Copiar link, Expandir y Cerrar;
  - izquierda: secciones colapsables Básico (prioridad), Plan (objetivo y pasos) y Ajustes de corrida (timeout y viewport);
  - derecha: pestañas Vista previa, Código e Historial.
- **Insights**:
  - tarjeta de acciones arriba («17 casos fallaron en la última corrida» con **Copiar prompt de arreglo**, y «Instalar la acción de GitHub»);
  - «Última corrida» con 4 KPIs: tasa de éxito, issues abiertos, arreglados y regresiones;
  - una línea de tendencia;
  - **Issues para arreglar, agrupados por causa**: título, ruta o archivo, «N casos» y chips con los casos afectados;
  - **Cobertura por caso de uso** con dos donas y una tabla.
- **Asistente de proyecto nuevo** en 3 pasos: Básico, Acceso y Contexto extra, con un indicador de pasos. A la derecha, la tarjeta «Otras formas de empezar» (CLI y Papurri en Slack).
- **Estados vacíos ilustrados** con texto y acción; en Programaciones, además, una explicación con una imagen del gráfico.

**Qué agrega dogfood (la mejora):**
- en cada caso, la **persona** (avatar con iniciales, idioma, destreza) y su **opinión**;
- en el detalle, las **verificaciones del oráculo** (números esperados contra los mostrados);
- en Insights, la **fricción por pantalla** y el **costo por corrida**;
- en el mosaico, los **celulares reales**.

Todo pasa por `redactar` antes de mostrarse, como ahora.

Reglas para todas las tareas: usa los componentes shadcn de `web/src/components/ui` (agrega los que falten con la CLI de shadcn), TanStack Router y Query, y los tipos generados del OpenAPI. Nada de datos falsos en producción: si un dato no existe todavía, muestra el estado vacío. Cada tarea deja capturas en el PR (tema claro), tomadas con Playwright contra datos de prueba.

## F11.1 — Package: base

### F11.1.T1 — Sistema de diseño y navegación en dos niveles

1. Tema claro cálido como predeterminado (tokens en `web/src/styles.css` según la referencia de arriba), con la serif de títulos y un componente `EncabezadoPagina({titulo, subtitulo, acciones})` usado en todas las páginas.
2. Barra global (`web/src/components/layout/BarraGlobal.tsx`) y barra de proyecto (`BarraProyecto.tsx`), con rutas anidadas en TanStack Router: `/` (Inicio), `/proyectos`, `/proyectos/$proyecto/{casos,corridas,insights,actividad,fuentes,github,ajustes/general,ajustes/entorno,ajustes/comportamiento,ajustes/notificaciones}`, `/suites`, `/programaciones`, `/ayuda`. Las rutas viejas (`/corridas/$id`, `/ejecuciones/$id`, `/recorridos`, `/dispositivos`, `/vista`) redirigen a la nueva ubicación o siguen existiendo dentro del proyecto.
3. Encabezado con migas, «Compartir» (copia el link público de `dogfood.knaimero.app`) y «Copiar link».
4. Componentes compartidos:
   - `PestanasEstado`: pestañas con conteo e ícono por estado;
   - `BadgeEstado`: Pasó, Falló, Bloqueado, Corriendo, Planeado y No concluyente;
   - `Prioridad`: barras alta, media y baja;
   - `Avatar` de persona con sus iniciales;
   - `Vacio` ilustrado: reutiliza el de F9.4 y suma ilustraciones SVG lineales simples;
   - `Paginacion`;
   - `BarraApilada`.

Done when: `bash scripts/build-web.sh`, `npx tsc --noEmit` y `npm run lint` pasan, los tests de `web/` siguen verdes y estos nuevos pasan en `web/src/components/layout/layout.test.tsx`:
- dentro de `/proyectos/predicts/casos` se ven las dos barras y las migas «predicts › Casos de prueba»;
- «← Volver» lleva a `/proyectos`;
- las rutas viejas redirigen;
- `PestanasEstado` muestra los conteos y cambia el filtro en la URL (`?estado=fallo`).

- **Model**: claude/claude-opus-5-5
- **Estimate**: 5h
- **Reason**: Define el lenguaje visual y la estructura de navegación que heredan todas las demás tareas.
- **Dependencies**: F10.2.T4
- **Files**:
  - `web/`

### F11.1.T2 — Proyectos: modelo, API y ajustes persistidos

Hoy los objetivos viven en código (`src/dogfood/objetivos/`). Un **proyecto** es un objetivo más su configuración editable.

1. `src/dogfood/proyectos.py` con estas funciones:
   - `listar()`;
   - `obtener(slug)`;
   - `crear(datos)`;
   - `actualizar(slug, cambios)`;
   - `borrar(slug)`.

   Guarda en la base sqlite del almacén (tabla `proyectos`, con migración en `almacen.py`) estos campos:
   - slug y nombre;
   - tipo: `web`, `android`, `ios` o `flutter_web`;
   - objetivo: el nombre en `objetivos/`;
   - URL;
   - acceso: usuario de prueba y referencia a un secreto (nunca el valor, que va en `~/.config/dogfood/secretos/<slug>.env`);
   - instrucciones extra;
   - entornos (nombre, URL, predeterminado);
   - comportamiento: iniciar sesión una vez por corrida, viewport, concurrencia;
   - notificaciones: Slack, issues de GitHub y repo;
   - repo del código, para las sugerencias de F10.2.T2;
   - fecha de creación.

   Al arrancar, si no existe, crea el proyecto `predicts` a partir de su objetivo actual.
2. API (en `src/dogfood/panel/api_proyectos.py`, registrada con una línea en `app.py`):
   - `GET /api/proyectos`, con los últimos resultados de cada uno: pasaron, fallaron, última actividad;
   - `POST /api/proyectos`;
   - `GET /api/proyectos/{slug}`;
   - `PATCH /api/proyectos/{slug}`;
   - `DELETE /api/proyectos/{slug}`, que pide confirmación con el slug en el cuerpo.

   Las de escritura exigen `X-Dogfood: 1`.
3. La corrida usa los ajustes del proyecto: instrucciones extra en el prompt de la persona, viewport, concurrencia y entorno. `dogfood run --target` acepta el slug de un proyecto.

Done when: estos tests pasan en `tests/test_proyectos.py` y `tests/test_panel_proyectos.py`:
- crear, leer, actualizar y borrar funcionan, y el proyecto `predicts` se siembra solo;
- el secreto nunca aparece en la respuesta de la API ni en la base (solo la referencia);
- `DELETE` sin la confirmación da 400, y sin `X-Dogfood` da 403;
- una corrida con `--target predicts` toma la concurrencia y las instrucciones extra del proyecto (con un objetivo falso);
- la lista trae los conteos de la última corrida.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Modelo de datos y CRUD con reglas claras.
- **Dependencies**: F10.2.T4
- **Files**:
  - `src/dogfood/proyectos.py`
  - `src/dogfood/almacen.py`
  - `src/dogfood/panel/api_proyectos.py`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/corrida.py`
  - `src/dogfood/cli.py`
  - `tests/test_proyectos.py`
  - `tests/test_panel_proyectos.py`

## F11.2 — Package: pantallas del proyecto

### F11.2.T1 — Casos de prueba: lista agrupada y panel lateral

Página `/proyectos/$proyecto/casos`. Los casos son los de `plan.py` de F10.2.T1, con su último resultado.

1. API `GET /api/proyectos/{slug}/casos?estado=&q=&prioridad=` con los casos agrupados por caso de uso (el escenario). Cada caso trae:
   - ID estable `TC###`, nombre y caso de uso;
   - persona: nombre, idioma, destreza e iniciales;
   - prioridad;
   - último estado, con la fecha;
   - resumen de la falla en una línea (de `motivo_juez` o del hallazgo principal);
   - link a la última ejecución.

   Además trae los conteos por estado. Y `GET /api/proyectos/{slug}/casos/{tc}`, con objetivo, criterio de éxito, pasos de la última ejecución, ajustes, historial de ejecuciones, opinión de la persona y verificaciones del oráculo.
2. Web, con la UX de la referencia:
   - encabezado serif y buscador;
   - `PestanasEstado`;
   - grupos colapsables por caso de uso, con `BarraApilada`;
   - filas con ID, badge, «· hace X», nombre, falla en rojo, persona como avatar y prioridad;
   - clic → **sheet** a la derecha con `?caso=TC017`. A la izquierda, las secciones Básico (prioridad y persona), Plan (objetivo y pasos) y Ajustes. A la derecha, las pestañas:
     - **Vista previa**: video, o la lista de pasos con captura y el paso fallido resaltado;
     - **Código**: el test Playwright o Patrol exportado, si existe; si no, el estado vacío «Todavía no se exportó»;
     - **Historial**: tabla de ejecuciones con estado, error y fecha.

     Debajo de la vista previa, cuando falló, van las pestañas **Error / Causa / Arreglo**: usa la sugerencia de F10.2.T2 y marca el arreglo como «sugerido por IA». También el botón **Copiar prompt de arreglo**: un prompt para Claude Code o Cursor con el problema, la evidencia redactada, los archivos probables y el comando `dogfood replay <id>`.
   - Expandir lleva el sheet a pantalla completa (`/proyectos/$proyecto/casos/$tc`).

Done when: estos tests pasan en `tests/test_panel_casos.py` y `web/src/features/casos/casos.test.tsx`:
- los conteos por estado coinciden con los casos;
- el filtro `?estado=fallo` deja solo los fallidos;
- un grupo se colapsa;
- el clic en una fila abre el sheet con la URL `?caso=`, y Escape lo cierra;
- el caso fallido muestra Error, Causa y Arreglo y copia el prompt, que incluye `dogfood replay`;
- un secreto plantado en la evidencia no aparece en el prompt.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 5h
- **Reason**: La pantalla central del producto; mucho detalle de UX.
- **Dependencies**: F11.1.T1, F11.1.T2
- **Files**:
  - `src/dogfood/panel/api_casos.py`
  - `src/dogfood/panel/app.py`
  - `tests/test_panel_casos.py`
  - `web/`

### F11.2.T2 — Corridas: lista y detalle con mosaico de agentes

Página `/proyectos/$proyecto/corridas`, con la tabla de corridas: estado, entorno, casos que pasaron sobre el total, costo, duración y fecha, más el buscador.

El detalle de una corrida tiene dos vistas:
- Vista **Acciones del agente**: un mosaico de tarjetas por caso, agrupado por estado (Corriendo, Pasaron, Fallaron, Bloqueados), con su conteo y la tasa de éxito arriba. Cada tarjeta muestra:
  - la última captura, o el video si existe;
  - el nombre del caso y la persona;
  - el diagnóstico de una línea si falló.

  Mientras corre, la tarjeta tiene la marca **EN VIVO** y se actualiza con el websocket `/ws` de la vista. Los celulares reales aparecen con su marco de teléfono. Tiene buscador y filtros por estado y prioridad.
- Vista **Lista**: la misma información en una tabla.

Los botones «Nueva corrida», «Cancelar» y «Repetir caso» (de F10.2.T3) y «Reporte» (de F10.2.T4) se mueven aquí.

Done when: estos tests pasan en `web/src/features/corridas/mosaico.test.tsx`:
- el mosaico agrupa por estado con sus conteos;
- un evento de websocket falso pasa una tarjeta de En vivo a Falló;
- el filtro por estado funciona;
- la lista y el mosaico muestran los mismos casos.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Pantallas con datos existentes y patrón definido.
- **Dependencies**: F11.2.T1
- **Files**:
  - `web/`
  - `src/dogfood/panel/api.py`

### F11.2.T3 — Insights del proyecto

Página `/proyectos/$proyecto/insights`, con su API `GET /api/proyectos/{slug}/insights` en `src/dogfood/panel/api_insights.py`. Tiene cuatro bloques:

1. **Tarjeta de acciones**:
   - «N casos fallaron en la última corrida», con **Copiar prompt de arreglo** para toda la corrida (agrupa las causas);
   - «Instalar la acción de GitHub», que lleva a la página de GitHub del proyecto.
2. **Última corrida**: 4 KPIs.
   - Tasa de éxito, con «N de M casos».
   - Issues abiertos: los hallazgos sin resolver por huella.
   - Arreglados: huellas que estaban y ya no aparecen.
   - Regresiones: casos que pasaban y ahora fallan, con el commit o ref en que volvieron.

   Debajo, una línea de tendencia de las últimas corridas. Si hay una sola, el aviso «La tendencia necesita una segunda corrida».
3. **Issues para arreglar, agrupados por causa**: la huella del hallazgo, con título, ruta o archivo, «N casos», chips de los casos afectados (clic → sheet del caso) y gravedad, ordenados por la cantidad de casos.
4. **Lo que dogfood suma**:
   - fricción por pantalla, con un top 5 y las citas de las personas;
   - números verificados por el oráculo (correctos contra equivocados);
   - costo por corrida.

   Al final, **cobertura por caso de uso**: dona de casos por caso de uso, dona de pasaron y fallaron, y una tabla con Caso de uso, Últimos resultados, Casos, Pasaron, Fallaron, Bloqueados, % y Última corrida, con las pestañas Todos, Cubiertos, Planeados y Brecha.

Done when: estos tests pasan en `tests/test_panel_insights.py` (dos corridas de prueba en las que un caso pasa y luego falla, y una huella desaparece) y `web/src/features/insights/insights.test.tsx`:
- la regresión se cuenta y muestra la ref;
- la huella que desapareció cuenta como arreglada;
- los issues se agrupan por huella con sus casos;
- el prompt de la corrida incluye todas las causas;
- con una sola corrida aparece el aviso de tendencia.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Agregados sobre datos existentes con reglas claras.
- **Dependencies**: F11.2.T2
- **Files**:
  - `src/dogfood/panel/api_insights.py`
  - `src/dogfood/panel/app.py`
  - `tests/test_panel_insights.py`
  - `web/`

## F11.3 — Package: inicio, proyecto nuevo y ajustes

### F11.3.T1 — Inicio, lista de proyectos y asistente de proyecto nuevo

1. **Inicio** (`/`):
   - tarjeta de bienvenida con una ilustración simple y los botones «Ver proyectos» y «Ver ayuda»;
   - **Primeros pasos**: una lista de verificación con barra («1 de 4 hechas»): crear proyecto, primera corrida, conectar Slack y conectar GitHub. Cada paso se calcula de los datos reales;
   - Proyectos recientes, en tabla;
   - Suites y Programaciones, con su estado vacío ilustrado.
2. **Proyectos** (`/proyectos`): tabla con Nombre, Últimos resultados (chips verde y roja con números), Última actividad, Creado, Tipo y Origen (Panel, CLI o Slack), con las pestañas Todos, Web, Android e iOS, buscador, filtro, orden y paginación.
3. **Proyecto nuevo** (`/proyectos/nuevo`), en 3 pasos con indicador:
   - **Básico**: tipo (Web, Android, iOS), URL u objetivo y nombre;
   - **Acceso**: cómo inicia sesión la persona. Puede ser:
     - registro propio, como predicts;
     - un usuario de prueba, cuya contraseña se guarda como secreto;
     - sin login;
   - **Contexto extra**: PRD (subir un `.md` o pegar texto), instrucciones extra y repo del código.

   A la derecha, la tarjeta «Otras formas de empezar», con el comando de la CLI y «Pedíselo a Papurri en Slack». Al terminar, el proyecto se crea con el `POST` de F11.1.T2 y se va a sus Casos de prueba, con el estado vacío «Genera el plan» y el botón que llama a `dogfood plan`.

Done when: estos tests pasan en `web/src/features/inicio/inicio.test.tsx` y `web/src/features/proyectos/nuevo.test.tsx`:
- la lista de primeros pasos refleja los datos (con proyecto y sin corridas = 1 de 4);
- el asistente no avanza sin URL válida;
- el paso de Acceso no muestra la contraseña después de guardarla;
- al terminar navega a los casos del proyecto nuevo;
- las pestañas de tipo filtran la tabla.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Formularios y tablas con un patrón ya definido.
- **Dependencies**: F11.1.T1, F11.1.T2
- **Files**:
  - `web/`

### F11.3.T2 — Ajustes del proyecto, notificaciones, fuentes, actividad y GitHub

Cada página sigue la UX de la referencia: título serif, tarjetas con secciones y «Guardar cambios» deshabilitado hasta que algo cambie.

- Página **General**: nombre, tipo (solo lectura, con la nota «no se puede cambiar después de crear»), **instrucciones extra** (con el ejemplo «Enfócate en el checkout; prueba casos borde; evita acciones destructivas») y una **zona de peligro** para borrar el proyecto escribiendo su nombre.
- Página **Entorno**: lista de entornos (nombre, URL, predeterminado, usuario de prueba o «Sin cuenta de prueba») para agregar, editar y marcar el predeterminado.
- Página **Comportamiento**: «Iniciar sesión una vez por corrida» (interruptor), viewport (1920×1080 por defecto, más los tamaños de celular) y «Casos al mismo tiempo». Cada uno con su explicación en gris.
- Página **Notificaciones e issues**: tarjetas para Slack (webhook guardado como secreto, con «Probar»), Issues de GitHub (repo, publicar sí o no, etiqueta) y Linear o Jira («Próximamente»).
- Página **Fuentes**: lo que el agente lee para entender la app (PRD, docs de `docs/ops`, el repo, las exploraciones), con un buscador y el estado vacío «Sin exploraciones todavía».
- Página **Registro de actividad**: una línea de tiempo con los eventos del proyecto (corrida lanzada, terminada o cancelada, issue publicado, ajuste cambiado), cada uno con su autor y fecha. Los eventos salen de una tabla `actividad` nueva, con su API.
- Página **Acción de GitHub**: guía en 2 pasos (agregar `.github/workflows/dogfood.yml`, mostrado con el botón «Copiar», y elegir el disparador: PR o push) y una vista previa del comentario que dogfood deja en el PR. Agrega el comando `dogfood ci --target <slug> --ref <sha>`, que corre los casos de prioridad alta y sale con código 1 si alguno falla. El comentario en el PR va solo si el proyecto lo tiene activado.

Done when: estos tests pasan en `tests/test_actividad.py`, `tests/test_cli_ci.py` y `web/src/features/ajustes/ajustes.test.tsx`:
- guardar ajustes los persiste y registra la actividad;
- «Guardar cambios» está deshabilitado sin cambios;
- borrar exige escribir el nombre;
- el webhook de Slack nunca vuelve en la API;
- `dogfood ci` con un caso fallido (objetivo falso) sale con 1, y con todo verde sale con 0.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 5h
- **Reason**: Varias páginas de formulario más un comando simple.
- **Dependencies**: F11.3.T1
- **Files**:
  - `src/dogfood/actividad.py`
  - `src/dogfood/almacen.py`
  - `src/dogfood/panel/api_proyectos.py`
  - `src/dogfood/comandos/ci.py`
  - `src/dogfood/cli.py`
  - `tests/test_actividad.py`
  - `tests/test_cli_ci.py`
  - `web/`

### F11.3.T3 — Suites y programaciones

- Página **Suites** (`/suites`): una colección de casos de uno o varios proyectos (humo, regresión, previa a release). Tiene:
  - una tabla con nombre, última ejecución, cantidad de casos y estado de la última corrida: Pasó, Advertencia, Falló, Bloqueado o En curso;
  - «Nueva suite», con un selector de casos;
  - «Correr suite».
- Página **Programaciones** (`/programaciones`): correr una suite cada hora, a diario, cada semana o con una expresión cron, con aviso a Slack al terminar. El programador es un timer de `systemd --user` por programación, creado y borrado desde la API, con el comando `dogfood suite run <id>`. Sin programaciones, la página muestra la explicación con su ilustración y tres beneficios: corridas sin pedirlas, calidad en el tiempo y regresiones encontradas de noche.

Done when: estos tests pasan en `tests/test_suites.py` (con el creador de timers falseado) y `web/src/features/suites/suites.test.tsx`:
- crear una suite con casos de dos proyectos y correrla lanza las corridas de ambos;
- crear una programación genera el timer con el horario correcto y borrarla lo quita;
- el estado «Advertencia» aparece con resultados mixtos.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: CRUD y un programador acotado.
- **Dependencies**: F11.3.T2
- **Files**:
  - `src/dogfood/suites.py`
  - `src/dogfood/almacen.py`
  - `src/dogfood/panel/api_suites.py`
  - `src/dogfood/panel/app.py`
  - `src/dogfood/comandos/suite.py`
  - `src/dogfood/cli.py`
  - `tests/test_suites.py`
  - `web/`

## F11.9 — Package: cierre

### F11.9.T1 — E2E, revisión visual contra la referencia y redeploy

1. Tests e2e de Playwright (`web/e2e/f11.spec.ts`), contra el panel con datos de prueba, que recorren:
   - Inicio → Proyectos → proyecto nuevo (los 3 pasos) → Casos de prueba;
   - filtrar fallidos → abrir el sheet → Error, Causa y Arreglo → copiar el prompt;
   - Corridas → mosaico;
   - Insights;
   - Ajustes → guardar.
2. Capturas en tema claro de cada página principal, en `docs/capturas/f11/`. Compáralas con la referencia de este spec: espaciados, tipografía serif en títulos, pestañas con conteo, filas agrupadas y sheet. Corrige lo que no se parezca.
3. Redeploy: `bash scripts/build-web.sh` y `systemctl --user restart dogfood-panel`. Verifica que `http://127.0.0.1:7470/proyectos/predicts/casos` responde 200 y que `https://dogfood.knaimero.app` sigue redirigiendo al login de Access.
4. Actualiza la ayuda (`docs/ayuda/`) con las pantallas nuevas: proyectos, casos, insights, suites y GitHub.

Done when: el e2e pasa, las capturas están en el repo, `uv run pytest` y los tests de `web/` siguen verdes, el panel publicado sirve la versión nueva y la ayuda describe las pantallas nuevas.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Verificación y ajustes finos.
- **Dependencies**: F11.2.T3, F11.3.T3
- **Files**:
  - `web/`
  - `docs/capturas/f11/`
  - `docs/ayuda/`
