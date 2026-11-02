---
titulo: Las pantallas del panel
seccion: guias
orden: 5
pantallas:
  - corrida
  - corridas
  - inicio
  - proyectos
  - casos
  - insights
  - suites
  - github
---

# Las pantallas del panel

El panel se organiza por **proyecto**: cada proyecto es una app que dogfood prueba con sus personas. La barra de la izquierda tiene las pantallas globales (Inicio, Proyectos, Suites, Programaciones, Ayuda); al entrar en un proyecto aparece su propia barra con Casos de prueba, Corridas, Insights y los ajustes. Con `⌘K` buscas cualquier pantalla.

## Inicio y proyectos

- **Inicio** resume cómo les va a tus personas en todos los proyectos: primeros pasos, proyectos recientes, suites y programaciones.
- **Proyectos** lista cada app con su último resultado (cuántos casos pasaron y cuántos fallaron). Se puede buscar y ordenar.
- **Proyecto nuevo** son tres pasos: **Básico** (tipo, URL u objetivo y nombre), **Acceso** (cómo inicia sesión la persona: se registra sola, con un usuario de prueba o sin login) y **Contexto extra** (PRD, instrucciones y repo del código). Al terminar te lleva a Casos de prueba; si todavía no hay casos, pulsa **Generar plan**.

## Casos de prueba

Todos los casos del proyecto, agrupados por caso de uso, con su último resultado.

- Las pestañas **Todos / Planeados / Corriendo / Pasaron / Fallaron / Bloqueados / No concluyentes** muestran cuántos casos hay en cada estado y filtran la lista. También puedes buscar por ID (`TC002`), nombre o persona.
- Cada fila abre un **panel lateral** (la URL lleva `?caso=TC002`, así que se puede compartir). **Expandir** lo abre a pantalla completa.
- En un caso fallido, el diagnóstico tiene tres pestañas: **Error** (lo que vio el juez), **Causa** (la causa probable, sugerida por IA) y **Arreglo** (el cambio sugerido y los archivos probables). **Copiar prompt de arreglo** deja en el portapapeles un texto listo para pegar en tu agente de código; ya va sin contraseñas ni secretos.

## Corridas

La lista de corridas del proyecto lleva al detalle de cada una. En **Acciones del agente** (el mosaico) cada caso es una tarjeta con su pantalla, agrupada en Corriendo, Pasaron, Fallaron y Bloqueados; **Lista** muestra los mismos casos en filas y **Resumen** los números de la corrida. En una tarjeta fallida, **Repetir caso** lo vuelve a correr.

## Insights

Responde «qué arreglo primero»: la tasa de éxito de la última corrida, issues abiertos y arreglados, regresiones respecto a la corrida anterior, issues agrupados por causa (con un prompt para toda la corrida), la tendencia entre corridas, la fricción por pantalla, los números verificados por el oráculo, el costo por corrida y la **cobertura por caso de uso** (cubierto, planeado o brecha).

## Suites y programaciones

- Una **suite** es una colección de casos de uno o varios proyectos (humo, regresión, previa a un release). **Nueva suite** pide un nombre y los casos; **Correr** la lanza de una vez.
- Una **programación** corre una suite sola: cada hora, a diario, cada semana o con una expresión cron. Se crean en **Programaciones**.

## Acción de GitHub

En los ajustes del proyecto, **Acción de GitHub** te da el workflow (`.github/workflows/dogfood.yml`) que corre los casos de prioridad alta en cada cambio y falla el CI si alguno falla, el disparador a elegir y un ejemplo del comentario que dogfood deja en el pull request. También se llega desde el botón «Instalar la acción de GitHub» de Insights.

## Ajustes del proyecto

**General** (nombre e instrucciones extra), **Entorno** (URL y usuario de prueba), **Comportamiento** y **Notificaciones** (Slack e issues de GitHub). **Guardar cambios** solo se habilita cuando algo cambió. Las contraseñas y los webhooks se guardan como secretos y nunca se vuelven a mostrar.
