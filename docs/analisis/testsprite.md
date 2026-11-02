# TestSprite vs dogfood — análisis y plan de paridad

Fecha: 2026-11-01. Fuentes: testsprite.com (inspeccionada con REA `inspect-web-page` vía CDP: sitio Next.js, sin APIs públicas útiles), docs.testsprite.com (Web Portal: overview, Step-by-Step Replay, Auto-Heal, Agent Actions, Test Lists, Test Schedules, AI Chat, GitHub Integration) y capturas de producto de la documentación. No se creó cuenta ni se entró a la app: solo material público.

## Cómo funciona TestSprite (flujo del producto)

1. **Nuevo proyecto** en 3 pasos: datos básicos, acceso (URL, cómo iniciar sesión: credenciales, OTP o SSO) y fuentes de prueba (PRD «muy recomendado», docs de API, repo, Figma, tickets).
2. **Explorar**: el agente recorre la app viva (UI) o sondea la API.
3. **Mapa de funcionalidades** («Test Coverage»): grafo con funcionalidades → casos de uso → pasos, con captura de cada pantalla. Botón «Regenerate From Sources».
4. **Revisar el plan** («Review proposed tests»): casos agrupados por funcionalidad, con check, prioridad editable (High/Medium/Low), nombre, descripción y «Show flow». Nada se agrega hasta confirmar.
5. **Correr y revisar**: cada caso termina Passed / Failed / Blocked.
   - *Agent Actions*: un mosaico de videos por caso, agrupado por estado, con «LIVE» mientras corre, tasa de paso arriba, búsqueda y filtros.
   - *Step-by-Step Replay*: lista de pasos (acción o aserción, descripción, estado) a la izquierda; a la derecha el video o el **snapshot HTML** del paso; pestaña Code con el test.
   - Falla en 3 pestañas: **Error / Cause / Fix** (el arreglo marcado como generado por IA) y **«Copy fix prompt»** para pegar en Claude Code o Cursor, por caso o por corrida.
6. **Mantener**: *Auto-Heal* en las repeticiones (absorbe cambios de UI, no esconde bugs reales), *Test Lists* (suites de varios proyectos), *Test Schedules* (cron + aviso a Slack), *GitHub*: check en cada PR o push; *Insights*: regresiones y tendencias entre corridas.
7. **Extras**: tests exportables (Playwright + Python), AI Chat copiloto que propone acciones y espera aprobación, CLI y MCP.

Diseño: fondo blanco hueso, verde como color de marca, tipografía serif en títulos de marketing y sans en el producto, tarjetas con borde suave y esquinas grandes, badges de prioridad en rojo suave, puntos de color por estado, lienzo punteado para el mapa.

## Comparación

Lo que dogfood ya tiene y TestSprite **no**:
- **Población de personas** (idioma, destreza, intención, dispositivo): prueba como usuarios distintos, no como un QA único.
- **Opinión de usuario por pantalla** (fricción, citas), además del pasa/falla.
- **Oráculo con verdad conocida** (`verdad.json`): detecta números equivocados, no solo pantallas rotas. Y verificación de **aislamiento** entre empresas.
- **Celular real** (Android por ADB, Flutter, Patrol) y vista en vivo del dispositivo.
- **Instancia aislada** levantada por cada corrida, **costo por corrida** visible, todo self-hosted y redactado antes de publicar.

Lo que TestSprite tiene y a dogfood le falta (o tiene a medias):

- Proyecto nuevo desde el panel, para cualquier app: no lo tenemos, porque los objetivos están en código (`objetivos/predicts`). Va en **F11.1.T1**.
- Exploración y mapa de funcionalidades: no lo tenemos. Va en **F11.1.T2**.
- Revisar y editar el plan antes de correr: F10.2.T1 solo muestra los casos. Va en **F11.1.T3**.
- Mosaico de videos por estado, con LIVE: tenemos la vista en vivo de a una. Va en **F11.2.T1**.
- Error / Causa / Arreglo y «Copiar prompt de arreglo»: F10.2.T2 da una sugerencia. Va en **F11.2.T2**.
- Snapshot HTML por paso: tenemos captura PNG. Va en **F11.2.T2**.
- Auto-heal al repetir: el replay es literal. Va en **F11.2.T3**.
- Exportar el test (Playwright Python): solo existe para Patrol. Va en **F11.2.T3**.
- Suites, programaciones e insights: no los tenemos. Van en **F11.3.T1**.
- Check en PRs de GitHub: no lo tenemos. Va en **F11.3.T2**.
- Lanzar corridas y reporte compartible: ya cubierto por F10.2.T3 y F10.2.T4.
- AI Chat copiloto: fuera de alcance por ahora; Papurri ya cumple ese rol desde Slack.
- Pruebas de API (backend): fuera de alcance; dogfood prueba como usuario.

## Dónde mejoramos a TestSprite (lo que pedimos de más en F11)

- El plan se arma con **personas × casos de uso**: cada caso dice *quién* lo prueba (persona pt-BR novata, es avanzada…), no solo *qué*.
- La revisión de cada caso muestra, además de Error/Causa/Arreglo, la **opinión de la persona** y los **números verificados por el oráculo**.
- «Copiar prompt de arreglo» incluye los archivos probables del repo (F10.2.T2) y el comando para reproducir con `dogfood replay`.
- Auto-heal **muestra el diff** de lo que cambió en la UI (el paso viejo, el nuevo y las capturas) y lo marca para revisar, en vez de pasarlo en silencio.
- Insights cruza las corridas por **huella**: un hallazgo que reaparece se marca como regresión con el commit en el que volvió.
