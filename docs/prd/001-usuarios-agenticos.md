---
type: prd
project_id: dogfood
version: 0.1
generated_by: orch-prd
generated_at: 2026-10-24
title: Usuarios agénticos para Showly
---

# Usuarios agénticos para Showly

## Problema

Showly (repo `agndaZAP`) es agendamiento por WhatsApp con recordatorios anti no-show. Sus tests prueban lo que el equipo ya pensó. Nadie usa el sistema como un paciente real antes de que llegue a la clínica: la señora apurada, el señor mayor que escribe mal, el que cambia de opinión tres veces o el que intenta romper el bot. Hoy esos fallos los descubre la clínica piloto, o se descubren con el smoke manual de `docs/smoke-e2e.md`, que toma unos 30 minutos y cubre un solo camino feliz.

El costo es doble: bugs que llegan a producción (turnos duplicados, horarios en la zona horaria equivocada, conversaciones que se traban) y fricción que nadie mide (qué no se entiende, dónde abandona el paciente).

dogfood crea una población de usuarios sintéticos con personalidad que usan Showly de verdad, por WhatsApp y por la web, sobre un stack local aislado. Entrega dos cosas: issues reproducibles en GitHub y la opinión de esos usuarios.

## Usuarios

- **Héctor (dueño de Showly):** quiere saber, antes de cada deploy importante, qué está roto y qué molesta, sin probar a mano.
- **Agentes de orch que trabajan en agndaZAP:** reciben los issues como tareas, así que necesitan pasos para reproducir que se puedan ejecutar.

## Metas

- G1 — Una corrida manual encuentra fallos que los tests de agndaZAP no cubren. Cada fallo llega como issue con pasos para reproducir, evidencia y gravedad.
- G2 — Una corrida simula más de 100 usuarios distintos (pacientes y personal de clínica), cada uno con su propia cuenta o teléfono.
- G3 — Cada corrida produce un reporte de opinión por superficie y por tipo de usuario, en español.
- G4 — Ninguna corrida toca producción ni envía un mensaje a un WhatsApp real.

## Fuera de alcance

- **Validar mercado:** los usuarios sintéticos no reemplazan entrevistas con clínicas reales.
- **Correr contra producción** o contra la clínica piloto.
- **Disparo automático** desde Coolify o desde un PR. La v1 es manual.
- **App Flutter del profesional:** en Showly todavía es un stub.
- **Audio, imágenes y otros adjuntos reales** por WhatsApp. Se simulan como `hasMedia` sin archivo.
- **agenda-barberia** y otros objetivos: vienen después. El diseño no debe impedirlos.
- **Arreglar los bugs encontrados:** eso lo hacen orch o Héctor en agndaZAP.

## Requisitos funcionales

### Entorno aislado
- **FR-1** — `dogfood env up --target showly` levanta un stack local de Showly en el server (base de datos, redis, backend y web) desde una revisión de `agndaZAP` (rama o commit; por defecto `main`), con migraciones y seed de demo. *Aceptación:* `/api/health` responde 200 y `/es/agendar/demo` responde 200.
- **FR-2** — En lugar de WAHA, el stack usa un **WhatsApp simulado**. dogfood entrega mensajes al webhook de Showly con la forma de WAHA y captura cada mensaje que Showly intenta enviar. *Aceptación:* un mensaje "quiero una cita" enviado por el simulador recibe una respuesta del bot que queda registrada en la corrida, y no sale ningún tráfico a WhatsApp.
- **FR-3** — `dogfood env down` destruye el stack y sus datos. Cada corrida parte de un estado limpio y conocido. *Aceptación:* dos corridas seguidas con el mismo `--seed` arrancan con la misma base de datos.
- **FR-4** — dogfood se niega a correr contra una URL que no sea la del stack local (lista blanca), salvo con un flag explícito que no existe en la v1. *Aceptación:* `--target-url https://showly…sslip.io` termina con error antes de crear usuarios.

### Población de usuarios
- **FR-5** — Un generador crea personas: nombre, idioma (es o pt-BR), edad, destreza digital, paciencia, intención (agendar, reagendar, cancelar, preguntar, romper) y estilo de escritura (faltas de ortografía, emojis, mensajes partidos, audios). *Aceptación:* `dogfood personas --n 120` produce 120 personas distintas, guardadas como datos y reproducibles con la misma semilla.
- **FR-6** — Cada persona tiene su propia identidad en Showly. Los pacientes usan un teléfono sintético único que nunca coincide con un número real asignable. El personal de clínica tiene cuentas creadas por los flujos reales de Showly (alta de clínica e invitación del superadmin del seed). *Aceptación:* una corrida con 100 personas o más termina con 100 identidades distintas o más en la base de Showly.
- **FR-7** — Los escenarios son datos (objetivo, superficie, persona compatible y criterio de éxito observable), no código. *Aceptación:* agregar un escenario en un archivo hace que la siguiente corrida lo ejecute sin cambiar código.

### Agentes
- **FR-8** — **Agente paciente por WhatsApp:** conversa con el bot como la persona hasta cumplir el objetivo del escenario, rendirse o llegar a un límite de turnos. Respeta tiempos humanos configurables y también puede responder a los recordatorios que Showly le envía. *Aceptación:* en el escenario "agendar una cita", la conversación termina con una cita creada para ese teléfono, y dogfood lo verifica en la base de datos.
- **FR-9** — **Agente web:** usa la página pública `/agendar/[clinica]`, el link con token que manda el bot y el panel de recepción en un navegador real. *Aceptación:* el escenario "agendar desde la web" termina con una cita visible en el panel de recepción.
- **FR-10** — Los agentes corren en paralelo, con una concurrencia configurable. *Aceptación:* 100 personas con concurrencia 10 terminan sin que una corrida interfiera con otra.
- **FR-11** — Para llegar a las citas futuras sin esperar días, el reloj de los recordatorios se puede adelantar mediante el mecanismo que tenga el stack local. *Aceptación:* el escenario "recordatorio 24 h y confirmación" se ejecuta en minutos.

### Detección
- **FR-12** — dogfood detecta fallos técnicos sin que el agente tenga que notarlos:
  - errores de consola y respuestas 4xx/5xx en la web;
  - excepciones y errores en los logs del backend durante la corrida;
  - mensajes del bot vacíos, repetidos o que no llegan antes de un timeout.
  *Aceptación:* un 500 provocado en una ruta aparece como hallazgo con su log.
- **FR-13** — Al terminar cada escenario, dogfood compara el estado esperado con el real en la base de datos de Showly. Así detecta bugs de lógica: citas duplicadas, la hora equivocada por la zona horaria, un slot ocupado dos veces o una cancelación que no liberó el turno. *Aceptación:* una cita creada con la hora desplazada se reporta como hallazgo de lógica.
- **FR-14** — Los agentes reportan fricción: cuando no entienden algo, repiten, se frustran o abandonan, lo registran con la cita textual del bot o la pantalla. *Aceptación:* cada escenario abandonado tiene al menos una nota de fricción con evidencia.

### Reporte
- **FR-15** — Cada hallazgo trae:
  - título, superficie y gravedad (crítica, alta, media o baja);
  - pasos para reproducir, en forma de conversación o de acciones;
  - evidencia: capturas, transcripción y extracto de logs;
  - el commit de agndaZAP y la semilla de la corrida.
  *Aceptación:* los pasos de un hallazgo vuelven a ejecutarse con `dogfood replay <id>` y reproducen el fallo o informan que ya no se reproduce.
- **FR-16** — Los hallazgos de una corrida se **deduplican** entre sí y contra los issues abiertos de dogfood en `agndaZAP`. Si un hallazgo ya existe, se agrega como comentario con la nueva ocurrencia. *Aceptación:* correr dos veces el mismo bug deja un issue con dos ocurrencias, no dos issues.
- **FR-17** — Los hallazgos nuevos se **publican como issues en GitHub** (`hectorcanaimero/agndaZAP`) con etiquetas `dogfood`, superficie y gravedad, sin pedir aprobación. *Aceptación:* al terminar la corrida, cada hallazgo nuevo tiene la URL de su issue en el reporte.
- **FR-18** — El reporte de opinión, en español, se agrupa por superficie y por tipo de usuario. Dice qué no se entendió, qué frustró, qué sobró y qué funcionó bien, con citas textuales y conteos. *Aceptación:* el reporte se genera como Markdown y como HTML en la carpeta de la corrida.
- **FR-19** — Al terminar se envía un resumen a Slack: hallazgos por gravedad, links a los issues, link al reporte, costo y duración. *Aceptación:* el mensaje llega al canal configurado.

### Operación
- **FR-20** — `dogfood run --target showly [--personas N] [--escenarios …] [--seed S] [--ref main]` ejecuta todo de punta a punta: entorno, población, agentes, detección, reporte y aviso. *Aceptación:* un comando sin más argumentos produce un reporte y sus issues.
- **FR-21** — Cada corrida queda guardada: personas, transcripciones, capturas, hallazgos, modelos usados, tokens y costo. *Aceptación:* `dogfood runs` lista las corridas con su costo y número de hallazgos.
- **FR-22** — Los modelos se eligen por rol (persona, juez de éxito, deduplicación y redacción del reporte) y son configurables. Varios modelos distintos pueden tomar el mismo rol en una corrida, para comparar. *Aceptación:* el reporte muestra qué modelo hizo cada cosa.
- **FR-23** — dogfood mide la consistencia: el mismo escenario con la misma persona varias veces da la tasa de éxito y la variación de los hallazgos. *Aceptación:* `dogfood run --repeat 3` reporta la tasa de éxito por escenario.

## Requisitos no funcionales

- **NFR-1 — Restricción:** Python 3.13 con uv. Modelos solo vía 9router (`ROUTER_BASE_URL`, `ROUTER_KEY`). El navegador es el Chrome del server o un Chromium que maneje dogfood.
- **NFR-2 — Seguridad:** nunca hay tráfico hacia WhatsApp real ni hacia producción (FR-4). Las credenciales (9router, GitHub y las del seed) se leen de `~/.config/dogfood/*.env` y nunca aparecen en issues, reportes ni logs. Antes de publicar se eliminan los tokens de la evidencia.
- **NFR-3 — Datos:** todos los datos son sintéticos. `agndaZAP` es un **repo público**, así que un issue no puede contener datos de la clínica piloto.
- **NFR-4 — Escala:** una corrida con 120 personas y concurrencia 10 termina en menos de 60 minutos en el server.
- **NFR-5 — Costo:** no hay tope duro, por decisión de Héctor. Igual se mide y se muestra el costo por corrida, por rol y por modelo, y existe un tope opcional que corta la corrida.
- **NFR-6 — Reproducibilidad:** la misma semilla y el mismo commit de agndaZAP dan la misma población y los mismos escenarios. Los modelos pueden variar; eso es lo que mide FR-23.
- **NFR-7 — Ruido:** con la deduplicación de FR-16 y un umbral de gravedad configurable, una corrida sobre `main` sin cambios no abre más de 10 issues nuevos.
- **NFR-8 — Extensible:** Showly es un "objetivo" con su entorno, sus superficies y sus verificaciones de estado. Agregar agenda-barberia debe ser un objetivo nuevo, no cambios en el núcleo.

## Supuestos

- **Dónde corre** (respuesta 2: "tu recomendación"): solo sobre un stack local de Showly, desde `docker-compose.e2e.yml` y el seed. Showly no tiene staging y producción queda descartada.
- **Cuentas** (respuesta 3): "crear cuentas para tener más de 100 usuarios" se interpreta así:
  - los **pacientes** son teléfonos sintéticos únicos, porque en Showly el paciente se identifica por su número;
  - el **personal de clínica** se crea por los flujos reales de alta e invitación;
  - si para escalar hace falta crear muchas clínicas, se hace con el superadmin del seed.
- **Issues** (respuesta 4): se publican directo en `agndaZAP`, sin aprobación previa. La deduplicación y el umbral de gravedad (NFR-7) son lo que evita el ruido.
- **Idioma** (respuesta 5): las personas hablan español o pt-BR (mezcla configurable, por defecto 50/50). El reporte va en español.
- **Modelos** (respuesta 6): todos vía 9router, sin tope de monto, con varios modelos por rol.
- **Disparo** (respuesta 7): manual, por CLI.
- **Sin prueba previa** (respuesta 8): se construye el agente directamente. El primer milestone valida igual el WhatsApp simulado (FR-2) antes que todo lo demás.
- **Superficies:** el paciente por WhatsApp y la página pública son la prioridad; el panel de recepción entra en M3 y `/admin` solo se usa para crear cuentas.

## Preguntas abiertas

- **¿Se puede adelantar el reloj de los recordatorios en Showly sin cambiar su código (FR-11)?** Si no, hace falta un pequeño hook de test en agndaZAP (por ejemplo, un endpoint de solo-dev para disparar los jobs de BullMQ). Lo responde la arquitectura, revisando el código, y lo decide Héctor.
- **¿El simulador de WhatsApp reemplaza a WAHA a nivel de API (un falso WAHA que Showly llama) o se intercepta de otra forma?** Lo define la arquitectura. Lo ideal es no tocar el código de Showly, solo su configuración.
- **¿A qué canal de Slack va el resumen (FR-19)?** Propongo el de proyectos (C0C84E42LDA).

## Milestones

- **M1 — Entorno aislado y primera conversación:** dogfood levanta Showly local, un paciente sintético agenda por WhatsApp simulado y la corrida queda guardada. FR-1, FR-2, FR-3, FR-4, FR-7, FR-8, FR-20, FR-21.
- **M2 — Población y detección:** más de 100 personas en es y pt-BR, cada una con su cuenta, en paralelo, con detección técnica y de lógica y notas de fricción. FR-5, FR-6, FR-10, FR-11, FR-12, FR-13, FR-14.
- **M3 — Web:** página pública, link con token y panel de recepción en un navegador real. FR-9.
- **M4 — Reporte e issues:** hallazgos reproducibles, deduplicados y publicados en GitHub, reporte de opinión y aviso en Slack. FR-15, FR-16, FR-17, FR-18, FR-19.
- **M5 — Modelos y consistencia:** modelos por rol, comparación entre modelos y tasa de éxito por repetición. FR-22, FR-23.
