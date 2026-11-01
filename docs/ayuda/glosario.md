---
titulo: Glosario
seccion: referencia
orden: 2
pantallas: []
---

# Glosario

- **Corrida:** una vuelta completa de dogfood (`uv run dogfood run`). Se guarda en `runs/<corrida_id>/`.
- **Ejecución:** lo que hace una persona con un escenario dentro de una corrida. Tiene pasos, capturas y un [resultado](resultados.md).
- **Persona:** usuario ficticio y determinista (idioma, empresa, estilo de uso). Con la misma semilla salen las mismas.
- **Escenario:** una tarea con criterio de éxito que se le pide a la persona (por ejemplo `login` o `recompra-completa`).
- **Recorrido:** el escenario visto desde el panel, con su contrato: estado inicial, acciones, resultado esperado y evidencia requerida. `/recorridos` cuenta resultados por recorrido.
- **Objetivo:** la app que se prueba (`--target`): `predicts`, `android`, `flutter_web`…
- **Instancia:** la copia aislada del objetivo que dogfood levanta (`dogfood env up`) y destruye (`dogfood env down`) para la corrida.
- **Driver:** cómo se observa y se maneja la app: `web`, `android` (ADB) o `ios` (nodo en el Mac). Se elige con `--driver`.
- **Motor:** quién decide los pasos: `browser_use`, `bucle` (bucle propio), o los deterministas `patrol` e `integration_test`. Se elige con `--motor`. No confundir con el backend de modelos de cada rol (`api` o `claude_code`).
- **Detector:** código que revisa una ejecución y produce hallazgos (errores técnicos, números contra la verdad, aislamiento, reglas del objetivo, fricción, accesibilidad Flutter).
- **Hallazgo:** un problema encontrado, con tipo, gravedad, pantalla y título. Si es nuevo se publica como issue.
- **Huella:** identificador (sha1) del hallazgo, calculado con su tipo, pantalla y una firma normalizada. Sirve para no duplicar: si ya hay un issue abierto con la misma huella, se comenta en él.
- **Gravedad:** `crítica`, `alta`, `media` o `baja`. Hay un umbral configurable para decidir qué se publica.
- **Fricción:** nota de una persona cuando no entiende algo, repite, se frustra o abandona, con la pantalla y el texto exacto.
- **Oráculo:** el detector que compara los números que muestra la app con la verdad, con tolerancias.
- **Verdad:** la respuesta correcta conocida de antemano para los datos sintéticos (`verdad.json`).
- **Replay:** repetir una ejecución sin modelo: `uv run dogfood replay <id>`.
