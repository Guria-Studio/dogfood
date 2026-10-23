---
type: prd
project_id: dogfood
version: 0.2
generated_by: orch-prd
generated_at: 2026-10-24
title: Usuarios agénticos para predicts
---

# Usuarios agénticos para predicts

## Problema

predicts (repo público `hectorcanaimero/predicts`, en el homelab con `deploy/docker-compose.yml`) predice cuándo cada cliente vuelve a comprar cada producto a partir de un CSV.

El flujo completo tiene muchos pasos y cada uno puede fallar de forma silenciosa:
- registro;
- proyecto;
- subir el CSV;
- mapear columnas (con Jev);
- informe de calidad;
- análisis (recompra, ofertas, riesgo, ciclos);
- resultados, universo 3D y agente analista;
- plantillas de mensaje;
- exportar.

Sus tests prueban lo que el equipo ya pensó, con CSV limpios. Nadie lo usa como lo haría un analista de CRM de verdad: alguien que exporta de su ERP un CSV con punto y coma, fechas `dd/mm/aa`, codificación Latin-1, EAN como notación científica, filas duplicadas y la mitad de los clientes con una sola compra.

Además, predicts promete números medidos («nunca inventados»): un error en el ciclo de recompra o en el backtest no rompe la pantalla, solo da una respuesta equivocada que nadie nota.

dogfood crea una población de usuarios sintéticos con personalidad que usan predicts de verdad, en un navegador y en el homelab. Les da CSV sintéticos con la respuesta correcta conocida y entrega dos cosas: issues reproducibles en GitHub y la opinión de esos usuarios.

## Usuarios

- **Héctor (dueño de predicts):** quiere saber qué está roto, qué da números equivocados y qué molesta, antes de mostrar predicts en público.
- **Agentes de orch que trabajan en predicts:** reciben los issues como tareas, así que necesitan pasos para reproducir que se puedan ejecutar.

## Metas

- G1 — Una corrida manual encuentra fallos que los tests de predicts no cubren. Cada fallo llega como issue con pasos para reproducir, evidencia y gravedad.
- G2 — Una corrida simula más de 100 usuarios distintos, cada uno con su propia empresa y cuenta creadas por el registro real.
- G3 — dogfood detecta predicciones equivocadas: compara lo que predicts devuelve con la verdad conocida de cada CSV sintético.
- G4 — Cada corrida produce un reporte de opinión, en español, por pantalla y por tipo de usuario.
- G5 — Ninguna corrida toca la instancia de desarrollo que Héctor usa, ni deja datos en ella.

## Fuera de alcance

- **Validar mercado:** los usuarios sintéticos no reemplazan conversaciones con equipos de CRM reales.
- **Disparo automático** desde un PR o un deploy. La v1 es manual.
- **La API pública con claves** como superficie de prueba propia. En la v1 solo se usa por el navegador.
- **Pruebas de carga:** concurrencia sí, estrés no. El homelab tiene 14 GB compartidos.
- **Showly, agenda-barberia y otros objetivos:** vienen después. El diseño no debe impedirlos.
- **Arreglar los bugs encontrados:** eso lo hacen orch o Héctor en predicts.

## Requisitos funcionales

### Entorno
- **FR-1** — `dogfood env up --target predicts [--ref main]` levanta en el homelab una instancia **propia y aislada** de predicts (proyecto de compose y puertos aparte de la instancia de desarrollo en `:8080`), desde una revisión del repo. *Aceptación:* `/api/salud` de la instancia de dogfood responde 200, mientras la instancia de `:8080` no cambia.
- **FR-2** — `dogfood env down` destruye la instancia y sus datos. Cada corrida parte de un estado limpio. *Aceptación:* después de `down` no quedan contenedores ni volúmenes de dogfood.
- **FR-3** — dogfood se niega a correr contra una URL que no sea la de su propia instancia (lista blanca). *Aceptación:* `--target-url http://localhost:8080` termina con error antes de crear usuarios.
- **FR-4** — La instancia de dogfood usa IA real (Jev y 9router) con las credenciales de `~/.config/dogfood/`, porque el mapeo, el agente analista y los mensajes son parte de lo que se prueba. *Aceptación:* el mapeo sugerido en una corrida trae la confianza de Jev, no un valor por defecto.

### Datos sintéticos con verdad conocida
- **FR-5** — Un generador produce CSV de ventas sintéticos a partir de clientes con ciclos de recompra **conocidos** por producto (más ruido, clientes que abandonan y productos durables). Junto a cada CSV guarda la verdad: el ciclo real por cliente y producto, la próxima compra esperada y quién abandonó. *Aceptación:* `dogfood datos --perfil farmacia --clientes 2000` produce un CSV y su archivo de verdad, reproducibles con la misma semilla.
- **FR-6** — El generador aplica «defectos de mundo real», configurables y combinables. *Aceptación:* cada defecto tiene al menos un CSV de ejemplo, y el informe de calidad de predicts debería señalarlo.
  - Separador `;` o tabulador.
  - Codificaciones Latin-1, Windows-1252 o UTF-8 con BOM.
  - Fechas `dd/mm/aaaa`, `mm/dd`, ISO o con hora.
  - Decimales con coma.
  - EAN en notación científica o con ceros a la izquierda perdidos.
  - Encabezados en pt o es, o sin encabezados.
  - Filas duplicadas, IDs vacíos y fechas futuras.
  - Archivos grandes (hasta el límite de predicts) o vacíos.
- **FR-7** — Los escenarios son datos (objetivo, persona compatible, CSV o perfil de datos, criterio de éxito observable), no código. *Aceptación:* agregar un escenario en un archivo hace que la siguiente corrida lo ejecute sin cambiar código.

### Población de usuarios
- **FR-8** — Un generador crea personas: nombre, empresa y rubro (farmacia, pet shop, cosmética, café, e-commerce, agencia), idioma (pt-BR o es), destreza con datos, paciencia e intención (análisis completo, explorar, solo exportar, confundirse, romper). *Aceptación:* `dogfood personas --n 120` produce 120 personas distintas, reproducibles con la misma semilla.
- **FR-9** — Cada persona se registra por el flujo real de `/registro` (empresa y dueño), inicia sesión y usa su propia cuenta. *Aceptación:* una corrida de 100 personas o más deja 100 empresas distintas o más en la instancia de dogfood.

### Agente
- **FR-10** — **Agente navegador:** hace el recorrido de la persona en un navegador real, en el idioma de la persona, hasta cumplir el objetivo, rendirse o llegar a un límite de pasos. Cubre:
  - registro, login y recuperación de contraseña;
  - proyectos;
  - subir el CSV;
  - mapeo (aceptar o corregir lo que sugiere Jev);
  - informe de calidad;
  - análisis con parámetros;
  - resultados y universo;
  - agente analista;
  - plantillas de mensaje;
  - grupos de productos;
  - exportar;
  - demo.
  *Aceptación:* el escenario «análisis de recompra completo» termina con un CSV exportado y descargado por el agente.
- **FR-11** — Los agentes corren en paralelo, con una concurrencia configurable. *Aceptación:* 100 personas con concurrencia 5 terminan sin interferir entre sí y sin que ningún contenedor supere su límite de memoria.

### Detección
- **FR-12** — **Fallos técnicos:** errores de consola, respuestas 4xx/5xx, pantallas en blanco, trabajos que no terminan dentro de un tiempo límite y excepciones en los logs de `api` y `worker` durante la corrida. *Aceptación:* un 500 provocado aparece como hallazgo con su log.
- **FR-13** — **Números equivocados:** dogfood compara lo que predicts devuelve con la verdad del CSV. Revisa:
  - el ciclo por cliente y producto;
  - la fecha de la próxima compra, que debe caer dentro del rango que predicts declara;
  - la precisión de backtest declarada, recalculada por dogfood;
  - el riesgo de abandono;
  - que el CSV exportado coincida con lo que muestra el panel.
  *Aceptación:* si el ciclo de recompra cambia en un día, aparece como hallazgo de lógica con el cliente, el producto, el valor esperado y el obtenido.
- **FR-14** — **Aislamiento entre empresas:** con varias cuentas, dogfood intenta leer proyectos, datasets, análisis y exportaciones de otra empresa por URL y por API con su sesión. *Aceptación:* cualquier respuesta distinta de 403/404 es un hallazgo crítico.
- **FR-15** — **Reglas propias de predicts:**
  - con poca historia no predice («se dice, no se predice»);
  - toda predicción trae su evidencia y su incertidumbre;
  - las decisiones de Jev bajo el umbral se le preguntan a la persona;
  - la interfaz no mezcla idiomas.
  *Aceptación:* un cliente con una sola compra que recibe una fecha predicha es un hallazgo.
- **FR-16** — Los agentes reportan fricción: cuando no entienden algo, repiten, se frustran o abandonan, lo registran con la pantalla y el texto exacto. *Aceptación:* cada escenario abandonado tiene al menos una nota de fricción con su captura.

### Reporte
- **FR-17** — Cada hallazgo trae:
  - título, pantalla y gravedad (crítica, alta, media o baja);
  - pasos para reproducir;
  - evidencia: capturas, red, logs y, si hay, el CSV que lo provoca;
  - el commit de predicts y la semilla.
  *Aceptación:* `dogfood replay <id>` repite los pasos y reproduce el fallo o informa que ya no se reproduce.
- **FR-18** — Los hallazgos se **deduplican** entre sí y contra los issues abiertos de dogfood en predicts. Una repetición se agrega como comentario con la nueva ocurrencia. *Aceptación:* dos corridas con el mismo bug dejan un issue con dos ocurrencias.
- **FR-19** — Los hallazgos nuevos se **publican como issues** en `hectorcanaimero/predicts` con las etiquetas `dogfood`, la pantalla y la gravedad, sin pedir aprobación. *Aceptación:* cada hallazgo nuevo tiene la URL de su issue en el reporte.
- **FR-20** — El reporte de opinión, en español, va por pantalla y por tipo de usuario. Dice qué no se entendió, qué frustró, qué sobró y qué funcionó, con citas y conteos. *Aceptación:* se genera en Markdown y HTML en la carpeta de la corrida.
- **FR-21** — Al terminar se envía un resumen a Slack: hallazgos por gravedad, issues, link al reporte, costo y duración. *Aceptación:* el mensaje llega al canal configurado.

### Operación
- **FR-22** — `dogfood run --target predicts [--personas N] [--escenarios …] [--seed S] [--ref main]` ejecuta todo de punta a punta: entorno, datos, población, agentes, detección, reporte y aviso. *Aceptación:* el comando sin más argumentos produce un reporte y sus issues.
- **FR-23** — Cada corrida queda guardada: personas, CSV y su verdad, pasos, capturas, hallazgos, modelos, tokens y costo. *Aceptación:* `dogfood runs` lista las corridas con su costo y el número de hallazgos.
- **FR-24** — Los modelos se eligen por rol (persona, juez de éxito, deduplicación y redacción) y son configurables. Varios modelos pueden tomar el mismo rol en una corrida, para comparar. *Aceptación:* el reporte muestra qué modelo hizo qué.
- **FR-25** — dogfood mide la consistencia: el mismo escenario varias veces da la tasa de éxito y la variación de los hallazgos. *Aceptación:* `dogfood run --repeat 3` reporta la tasa de éxito por escenario.

## Requisitos no funcionales

- **NFR-1 — Restricción:** Python 3.13 con uv. Modelos solo vía 9router. El navegador es el Chrome del server o un Chromium que maneje dogfood, en el homelab.
- **NFR-2 — Memoria:** el homelab tiene 14 GB compartidos con otros proyectos. La instancia de dogfood respeta los límites de memoria del compose de predicts; la concurrencia por defecto es de 5 navegadores y es configurable; ningún proceso de dogfood puede tumbar el servidor.
- **NFR-3 — Seguridad:** las credenciales (9router, Jev, GitHub) se leen de `~/.config/dogfood/*.env` y nunca aparecen en issues, reportes ni logs. Antes de publicar se eliminan los tokens y las cookies de la evidencia.
- **NFR-4 — Datos públicos:** predicts es un **repo público**. Todos los datos son sintéticos; un issue nunca lleva datos reales ni menciona al empleador de Héctor (regla de confidencialidad de predicts).
- **NFR-5 — Escala:** 120 personas con concurrencia 5 terminan en menos de 90 minutos.
- **NFR-6 — Costo:** no hay tope duro, por decisión de Héctor. Se mide y se muestra el costo por corrida, por rol y por modelo, e incluye la IA que consume la propia instancia de predicts (Jev y 9router). Existe un tope opcional que corta la corrida.
- **NFR-7 — Reproducibilidad:** la misma semilla y el mismo commit dan la misma población, los mismos CSV y la misma verdad.
- **NFR-8 — Ruido:** con la deduplicación de FR-18 y un umbral de gravedad configurable, una corrida sobre `main` sin cambios no abre más de 10 issues nuevos.
- **NFR-9 — Extensible:** predicts es un «objetivo» con su entorno, sus pantallas, sus datos y sus verificaciones. Agregar Showly o agenda-barberia debe ser un objetivo nuevo, no cambios en el núcleo.

## Supuestos

- **Objetivo:** predicts, que corre en el homelab, en lugar de Showly. Showly sigue como posible segundo objetivo.
- **Dónde corre:** sobre una **instancia propia de dogfood** en el homelab, aparte de la de desarrollo en `:8080`. Así 100 cuentas o más no ensucian la instancia que Héctor usa y cada corrida parte limpia.
- **Cuentas:** cada persona crea su empresa por el registro público de predicts.
- **Recuperación de contraseña:** predicts en desarrollo no tiene SMTP. dogfood lee el token desde los logs de su instancia, y si no es posible, ese escenario queda fuera.
- **Issues:** se publican directo en predicts, sin aprobación. Hay deduplicación y un umbral de gravedad (NFR-8).
- **Idioma:** las personas usan pt-BR o es (por defecto 50/50) y la interfaz se pone en ese idioma. El reporte va en español. El inglés de la interfaz no se prueba en la v1.
- **Modelos:** todos vía 9router, sin tope de monto, con varios modelos por rol.
- **Disparo:** manual, por CLI.
- **Sin prueba previa:** se construye el agente directamente; M1 valida el camino completo con una sola persona.

## Preguntas abiertas

- **¿Hay un límite de registros o de rate limit en `/registro` y `/login` que frene 100 cuentas o más?** Si lo hay, la instancia de dogfood lo sube por configuración. Lo revisa la arquitectura.
- **¿La instancia de dogfood comparte la cuenta de Jev y 9router de desarrollo?** Propongo que sí, con el costo medido aparte (NFR-6). Lo decide Héctor.
- **¿A qué canal de Slack va el resumen?** Propongo el de proyectos (C0C84E42LDA).

## Milestones

- **M1 — Una persona, de punta a punta:** instancia aislada de predicts, un CSV sintético con verdad y una persona que se registra, sube, mapea, analiza y exporta. La corrida queda guardada. FR-1, FR-2, FR-3, FR-4, FR-5, FR-7, FR-10, FR-22, FR-23.
- **M2 — Población y datos del mundo real:** más de 100 personas en pt-BR y es, cada una con su empresa, en paralelo, con CSV con defectos reales. FR-6, FR-8, FR-9, FR-11.
- **M3 — Detección:** fallos técnicos, números equivocados frente a la verdad, aislamiento entre empresas, reglas propias de predicts y notas de fricción. FR-12, FR-13, FR-14, FR-15, FR-16.
- **M4 — Issues y reporte:** hallazgos reproducibles, deduplicados y publicados en GitHub, reporte de opinión y aviso en Slack. FR-17, FR-18, FR-19, FR-20, FR-21.
- **M5 — Modelos y consistencia:** modelos por rol, comparación entre modelos y tasa de éxito por repetición. FR-24, FR-25.
