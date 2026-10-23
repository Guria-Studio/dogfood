# Visión — dogfood

## Problema
Los tests solo prueban lo que ya pensaste. Antes de producción no hay nadie que use la app como un usuario real: el que va apurado, el torpe, el que intenta romper cosas.

## Idea
Agentes con personalidad que usan la app de verdad en un navegador y entregan:

1. **Issues (QA)**
   - Errores técnicos: errores de consola, respuestas 4xx/5xx y pantallas en blanco.
   - Flujos rotos.
   - Bugs de lógica, como turnos duplicados o la zona horaria.
   - Casos límite: acentos y emojis, doble clic en pagar, volver atrás, red lenta.
   - Cada bug lleva pasos para reproducir, capturas, logs y gravedad, y se publica como issue en GitHub.
2. **Opinión de usuarios**: cada persona cuenta qué no entendió, qué le frustró y qué le sobró. El reporte va por pantalla y por tipo de usuario.

## Límite honesto
Encuentra bugs y fricción. **No valida mercado**: eso solo se consigue con usuarios reales.

## Componentes
- Generador de personas.
- Escenarios con criterio de éxito.
- Agente navegador.
- Detector de errores.
- Reporte: issues y opinión.
- Evaluación de costo y consistencia.

## Stack propuesto
Ver [adr/0001-stack.md](adr/0001-stack.md).

## Objetivos
- Primero: la app de barberías (agenda-barberia).
- Después: Showly y agndaZAP.
- Integración futura: cada deploy de rama en Coolify dispara una corrida antes de producción.
