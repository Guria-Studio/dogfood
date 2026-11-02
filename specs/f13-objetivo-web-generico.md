---
type: spec
project_id: dogfood
phase: 13
version: 0.1
depends_on:
  - docs/analisis/testsprite.md
  - specs/f11-ux-testsprite.md
consumed_by:
  - orch-atomizer
generated_by: orch-spec
generated_at: 2026-11-02
title: Objetivo web genérico — cualquier app como proyecto, desde el panel
---

# F13 — Objetivo web genérico

Hoy dogfood está atado a predicts. Desde F11 existen los **proyectos** en el panel (`src/dogfood/proyectos.py`, asistente en `/proyectos/nuevo`), pero cada proyecto tiene que apuntar a un **objetivo** escrito en código (`src/dogfood/objetivos/`: `predicts`, `android`, `ios`, `flutter_web`). Por eso, sumar otra app (Open Fluent, tradex, etc.) exige programar. Además, `src/dogfood/corrida.py` tiene ganchos fijos de predicts:
- `cuentas.confirmar_registro`;
- el caso especial de `recuperar-contrasena`;
- `objetivos.predicts.cliente.cliente_para`;
- `DOGFOOD_REPO_OBJETIVO`, que apunta al repo de predicts.

F13 agrega un objetivo `web` genérico, que se configura entero desde el proyecto: URL, cómo se entra, PRD e instrucciones. También agrega una **exploración** que arma el mapa de funcionalidades y propone los escenarios, como el «feature map» y el «review plan» de TestSprite (ver `docs/analisis/testsprite.md`). Así, cualquier app web se agrega desde el panel sin código. El objetivo a medida (como predicts, con su oráculo) sigue existiendo para quien quiera la versión profunda.

Reglas para todas las tareas:
- **Nunca contra producción.** Cada proyecto web declara si su URL es staging o local (`entorno.tipo`: `local`, `staging`). Además, una lista de hosts prohibidos (`hosts_prohibidos`) frena la corrida antes de empezar si la URL cae en uno.
- Los secretos (contraseña del usuario de prueba) van en `~/.config/dogfood/secretos/<slug>.env`. Nunca van en la base, la API, los logs ni las capturas, y todo pasa por `redactar`.
- Predicts tiene que seguir funcionando igual: los tests de predicts y de la corrida no cambian de comportamiento.

## F13.1 — Package: motor

### F13.1.T1 — Objetivo `web` genérico y corrida sin ganchos fijos de predicts

1. **Ganchos opcionales en el protocolo** (`src/dogfood/objetivos/base.py`). Agrega estos métodos opcionales, que se consultan con `getattr` y tienen un valor por defecto neutro:
   - `confirmar_registro(persona, instancia)`;
   - `preparar_escenario(escenario, persona, instancia)`, que cubre el caso de `recuperar-contrasena`;
   - `cliente_api(instancia, persona)`;
   - `repo() -> Path | None`.

   Mueve a `PredictsObjetivo` lo que hoy está fijo en `corrida.py`. Después, `corrida.py` no menciona «predicts» salvo como valor por defecto del CLI.
2. **Objetivo `web`** (`src/dogfood/objetivos/web/__init__.py`, registrado en `OBJETIVOS`). Se construye desde un `Proyecto` (`WebObjetivo.desde_proyecto(p)`):
   - `preparar`:
     - si el proyecto tiene `levantar` (un comando, por ejemplo `docker compose -f … up -d`, con su `bajar`), lo corre;
     - espera a que `salud` (una URL o la raíz) responda 2xx o 3xx, con un timeout configurable;
     - aplica la guardia anti-producción;
     - devuelve la `Instancia` con `base_url`.
   - `destruir`: corre `bajar` si existe.
   - `url_permitida`: el mismo origen que la URL, más los `origenes_extra` del proyecto (por ejemplo, el dominio de la API).
   - `escenarios`: los aceptados del proyecto (F13.2.T1). Si no hay ninguno, un escenario de exploración libre por defecto («Recorre la app como un usuario nuevo y usa su función principal»).
   - `pantalla`: el primer segmento útil del path, o el título de la página si el path es `/`.
   - `verificadores`: solo los genéricos (técnicos, fricción, opinión); el oráculo no existe sin un objetivo a medida.
   - `logs`: los de `docker compose logs` si hay `levantar`; si no, vacío.
3. El modelo `Proyecto` suma los campos `levantar`, `bajar`, `salud`, `origenes_extra`, `hosts_prohibidos` y `entorno.tipo`, con su migración en `almacen.py` (la siguiente versión libre). La API y el asistente los aceptan.

Done when: estos tests pasan en `tests/test_objetivo_web.py` y `tests/test_corrida_sin_predicts.py`:
- una corrida con un proyecto `web` contra una app HTML de prueba (servida en el test con 2 páginas y un formulario) termina con su ejecución y el reporte, sin tocar nada de predicts;
- una URL en `hosts_prohibidos` frena la corrida con un error claro antes de lanzar personas;
- `levantar` y `bajar` se llaman en orden (con un runner falso);
- `url_permitida` acepta los `origenes_extra` y rechaza otros dominios;
- sin escenarios aceptados se usa la exploración libre;
- `rg -n predicts src/dogfood/corrida.py` solo encuentra el valor por defecto;
- todos los tests existentes de predicts y de la corrida siguen verdes.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 5h
- **Reason**: Refactor del corazón de la corrida sin romper predicts; requiere criterio.
- **Dependencies**: F11.9.T1
- **Files**:
  - `src/dogfood/objetivos/base.py`
  - `src/dogfood/objetivos/__init__.py`
  - `src/dogfood/objetivos/web/`
  - `src/dogfood/objetivos/predicts/__init__.py`
  - `src/dogfood/corrida.py`
  - `src/dogfood/proyectos.py`
  - `src/dogfood/almacen.py`
  - `tests/test_objetivo_web.py`
  - `tests/test_corrida_sin_predicts.py`

### F13.1.T2 — Acceso: registro propio, usuario de prueba o sin login

El proyecto declara `acceso.modo`. Según el modo, la persona entra así:
- Modo **`registro`**: cada persona se registra sola con su email sintético (`@dogfood.example.com`). Si la app pide confirmar el email, el proyecto puede declarar `acceso.confirmacion` con uno de estos valores:
  - `no`;
  - `mailpit`: lee el link desde la API de Mailpit en la URL que declare el proyecto;
  - `manual`: la ejecución queda «bloqueada» con el motivo «la app pide confirmar el email» y no cuenta como fallo de la app.
- Modo **`usuario_prueba`**: todas las personas usan la misma cuenta, cuyo usuario se guarda en el proyecto y cuya contraseña va como secreto en `~/.config/dogfood/secretos/<slug>.env` (`DOGFOOD_PASSWORD`). Como la cuenta es compartida, la concurrencia del proyecto se fuerza a 1 y el panel lo avisa.
- Modo **`sin_login`**: no hay paso de entrada.

El prompt de la persona recibe las instrucciones de entrada según el modo. La contraseña va como dato sensible de browser-use (`sensitive_data`), nunca en el texto del prompt.

Done when: estos tests pasan en `tests/test_acceso_web.py`:
- con `usuario_prueba`, la contraseña no aparece en el prompt, en la base, en `ejecucion.json` ni en los logs, y la concurrencia queda en 1;
- con `registro` + `mailpit` falso, se sigue el link de confirmación;
- con `manual`, la ejecución queda bloqueada con su motivo;
- con `sin_login`, el prompt no menciona cuentas;
- un secreto faltante da un error claro antes de lanzar.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 3h
- **Reason**: Reglas acotadas sobre el objetivo nuevo.
- **Dependencies**: F13.1.T1
- **Files**:
  - `src/dogfood/objetivos/web/acceso.py`
  - `src/dogfood/objetivos/web/__init__.py`
  - `src/dogfood/agente/prompts.py`
  - `tests/test_acceso_web.py`

## F13.2 — Package: exploración y plan

### F13.2.T1 — Exploración: mapa de funcionalidades y escenarios propuestos

Comando: `dogfood explorar --proyecto <slug> [--max-paginas 25]`. Hace lo siguiente:

1. Un agente de navegador (el mismo motor de las personas, con el rol `explorador` en `dogfood.yaml` y sonnet por defecto) entra según el modo de acceso y recorre la app en anchura. Visita hasta `--max-paginas` pantallas distintas, sin enviar formularios destructivos: nada que diga borrar, eliminar, pagar o cancelar cuenta. En cada pantalla anota su título, su path, las acciones visibles y la captura.
2. Con lo explorado más el PRD del proyecto (si existe), un LLM arma el **mapa de funcionalidades**. Son funcionalidades, cada una con sus casos de uso y las pantallas donde ocurren, y cada caso de uso marcado como `visto` (lo encontró explorando) o `solo_prd` (está en el PRD y no se encontró, una posible brecha).
3. Para cada caso de uso visto, propone un **escenario** en el mismo formato YAML de `objetivos/predicts/escenarios/`: `id`, `titulo`, `superficies`, `persona_compatible`, `objetivo`, `criterio_exito`, `max_pasos` y `carril`, con prioridad alta en lo que toca dinero, datos o cuenta. Los guarda como **borradores** del proyecto, en la tabla `escenarios_proyecto` con su estado: borrador, aceptado o descartado.
4. Guarda el mapa, las capturas y el costo en `runs/exploracion-<slug>-<fecha>/` y en la base.

API:
- `POST /api/proyectos/{slug}/exploraciones` lanza la exploración, con el lanzador de F10.2.T3 y `X-Dogfood: 1`;
- `GET /api/proyectos/{slug}/mapa`;
- `GET`, `PATCH` y `DELETE /api/proyectos/{slug}/escenarios[/{id}]` para editar, aceptar o descartar.

Done when: estos tests pasan en `tests/test_explorar.py` y `tests/test_panel_escenarios.py` (con un LLM falso y la app HTML de prueba de F13.1.T1, ampliada a 4 pantallas con un botón «Eliminar cuenta»):
- la exploración visita las pantallas sin hacer clic en «Eliminar cuenta»;
- el mapa marca como `solo_prd` un caso del PRD que no está en la app;
- los escenarios propuestos validan contra el modelo `Escenario` y quedan como borradores;
- aceptar uno lo hace aparecer en `WebObjetivo.escenarios()`;
- un secreto plantado no llega al prompt.

- **Model**: claude/claude-opus-5-5
- **Estimate**: 5h
- **Reason**: Diseño del explorador y de la generación de escenarios; define la calidad del producto para apps nuevas.
- **Dependencies**: F13.1.T2
- **Files**:
  - `src/dogfood/explorar.py`
  - `src/dogfood/comandos/explorar.py`
  - `src/dogfood/cli.py`
  - `src/dogfood/almacen.py`
  - `src/dogfood/panel/api_escenarios.py`
  - `src/dogfood/panel/app.py`
  - `tests/test_explorar.py`
  - `tests/test_panel_escenarios.py`
  - `tests/fixtures/app_web/`

### F13.2.T2 — Panel: proyecto web de punta a punta, mapa y revisión del plan

Sigue la UX de F11 y de `docs/analisis/testsprite.md`.

1. **Asistente de proyecto nuevo**, con el tipo **Web** conectado al objetivo `web`:
   - Paso **Básico**: URL y tipo de entorno (local o staging), con un aviso fuerte si la URL parece de producción.
   - Paso **Acceso**: el modo de acceso y sus campos; la contraseña se guarda como secreto con un endpoint que escribe el `.env` y nunca la devuelve.
   - Paso **Contexto extra**: PRD, instrucciones extra, `levantar`, `bajar`, `salud` y orígenes extra.

   Al terminar, el asistente ofrece **«Explorar la app»**.
2. Página **Mapa** del proyecto (grupo Configuración, junto a Fuentes):
   - las funcionalidades como tarjetas, con sus casos de uso, las pantallas en miniatura y la marca `visto` o `solo_prd`; esta última en ámbar, como «posible brecha»;
   - el botón «Explorar de nuevo»;
   - el progreso en vivo mientras corre.
3. **Revisar el plan**: en Casos de prueba, cuando hay escenarios en borrador, aparece una franja «N escenarios propuestos para revisar». Abre una tabla con:
   - un check;
   - la prioridad editable;
   - el título y el objetivo, editables en línea;
   - «Ver flujo», que muestra las pantallas.

   Los botones «Aceptar seleccionados» y «Descartar» cierran la revisión, como el «Review proposed tests» de TestSprite. Nada corre hasta aceptar.

Done when: estos tests pasan en `web/src/features/mapa/mapa.test.tsx` y `web/src/features/escenarios/revisar.test.tsx`:
- el asistente crea un proyecto web y ofrece explorar;
- la contraseña no vuelve en ninguna respuesta;
- el mapa muestra las funcionalidades y marca en ámbar lo de `solo_prd`;
- aceptar 2 de 3 borradores deja 2 aceptados y 1 borrador;
- editar el objetivo en línea se guarda.

Deja capturas en el PR.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Pantallas sobre API ya definida y patrón de F11.
- **Dependencies**: F13.2.T1
- **Files**:
  - `web/`
  - `src/dogfood/panel/api_proyectos.py`

## F13.9 — Package: verificación con Open Fluent

### F13.9.T1 — Open Fluent como primer proyecto nuevo

Open Fluent (`/mnt/storage/project/fluent`, repo `hectorcanaimero/fluent`) es una app para practicar inglés: Flutter (`apps/mobile`, que también compila a web), API en Node (`apps/api`), `apps/interview-agent` en Python y `apps/landing`. Su regla de producto: **la entrevista y el tutor van siempre en inglés y la interfaz en el idioma del usuario**. Producción vive en `fluent.usebot.chat`, y **no se usa nunca**.

1. Levanta un **staging local** de Fluent en el homelab: API e interview-agent, con su base, siguiendo `docs/` y el `README` del repo, más el build web de `apps/mobile` apuntando a esa API local. Si el arranque necesita claves de LLM, usa las de 9router de `~/.config/dogfood/` mediante variables, sin copiarlas al repo de Fluent. Deja el comando en el campo `levantar` del proyecto y escríbelo como script en `scripts/fluent-staging.sh` del repo de dogfood.
2. Crea el proyecto `open-fluent` por la API de F13.1.T1:
   - tipo web y entorno `local`;
   - `hosts_prohibidos: [fluent.usebot.chat]`;
   - acceso según cómo entre la app: registro propio, o usuario de prueba si el registro exige algo que no se puede automatizar;
   - el `PRODUCT.md` de Fluent como PRD;
   - las instrucciones extra: «La entrevista y el tutor deben estar siempre en inglés aunque la persona escriba en español o portugués; si responden en otro idioma, anótalo como hallazgo».
3. Corre `dogfood explorar --proyecto open-fluent` y acepta los escenarios razonables, con al menos una entrevista completa.
4. Corre `uv run dogfood run --target open-fluent --personas 3 --seed 2 --sin-publicar`, con personas en es y pt-BR.
5. Escribe `docs/notas/fluent-primera.md` con:
   - cómo se levantó el staging;
   - el mapa y los escenarios aceptados;
   - los resultados por escenario;
   - los hallazgos, en especial cualquier respuesta de la entrevista que no esté en inglés;
   - el costo y la duración;
   - lo que faltó del objetivo genérico.

   Los bugs de Fluent no se arreglan acá; se anotan.

Si el staging no se puede levantar sin algo que solo tiene Héctor (claves, servicios pagos), no inventes nada: documenta qué falta en la nota y bloquea la tarea con ese motivo.

Done when: `docs/notas/fluent-primera.md` existe con esos datos, el proyecto `open-fluent` aparece en el panel con su mapa y su corrida, ninguna request salió a `fluent.usebot.chat` (verifícalo en el `red.jsonl` de las ejecuciones) y `uv run pytest` sigue verde.

- **Model**: claude/claude-sonnet-5-5
- **Estimate**: 4h
- **Reason**: Integración real de punta a punta con ajustes chicos.
- **Dependencies**: F13.2.T2
- **Files**:
  - `docs/notas/fluent-primera.md`
  - `scripts/fluent-staging.sh`
