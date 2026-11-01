---
titulo: Motor claude_code
seccion: guias
orden: 3
pantallas: []
---

# Motor `claude_code`: plan Max en lugar de API

Guía para usar Claude Code con el plan Max como motor de los roles de dogfood, en lugar del backend por API (9router). Ambos cumplen el mismo contrato `BackendLlm` (`src/dogfood/backends/`), así que el resultado y el costo se pueden comparar (FR-26, FR-27, issue #35).

> **Estado de esta rama.** `BackendClaudeCode` está implementado y probado con un `claude` falso. `llm.backend_para` ya elige el motor según `motores:`, pero **todavía no está conectado a las corridas**: `completar_json` sigue delegando en `BackendApi`, y `corrida.py` llama a `cliente_para` directamente. Hasta que se conecte, cambiar `motores:` a `claude_code` no altera `dogfood run`. Lo que sigue describe el comportamiento del backend y de la configuración.

## 1. Requisitos

- Claude Code instalado, con `claude` en el `PATH`.
- Sesión iniciada con la cuenta del plan Max: ejecuta `claude` y, dentro, `/login`.

## 2. Configuración en `dogfood.yaml`

```yaml
motores: { persona: claude_code, juez: api, dedupe: api, redactor: api }   # api | claude_code

claude_code:
  modelos: { persona: sonnet, juez: sonnet }   # opcional; si falta un rol, usa roles.<rol>
  mcp_config: null                             # ruta a un JSON de MCP, opcional
  timeout_s: 180                               # tiempo máximo por llamada a claude -p
```

- `motores` acepta `api` o `claude_code` por rol. `llm.backend_para` valida el valor y lanza `ValueError` con los válidos si escribes otra cosa.
- `claude_code.modelos` elige el modelo de `claude` por rol (`sonnet`, `opus`, etc.). Si el rol no está, usa el de `roles`.

## 3. Verificar la sesión

```bash
claude -p "di ok" --output-format json
```

Con sesión válida, la salida es un objeto JSON con `"is_error": false` y `"result"` que contiene `ok`. Si `is_error` es `true` o aparece un aviso de login, el backend lo convierte en un error (ver §4).

## 4. Qué hace el backend sin sesión

`BackendClaudeCode` revisa la salida y el `stderr` buscando marcas de sesión caída: `not logged in`, `invalid api key`, `/login`, `please run /login`. Si las encuentra, lanza `ErrorMotor` con este mensaje:

> Claude Code no está autenticado: ejecuta `claude` y luego /login con la cuenta del plan Max.

Otros errores que el backend distingue, todos como `ErrorMotor`:

- **No hay `claude` en el `PATH`:** indica instalar Claude Code y ejecutar `claude` para iniciar sesión.
- **Tiempo límite:** `` `claude -p` superó el tiempo límite de N s `` (ajusta `timeout_s`). El proceso se mata antes de lanzar el error.
- **Salida que no es JSON:** incluye el código de salida y los primeros 300 caracteres.
- **Respuesta que no valida contra el esquema del rol:** indica el nombre del esquema y la respuesta.

El backend **no cambia a API por su cuenta**: el error sube y el operador decide. Si quieres seguir la corrida con API mientras se arregla la sesión, cambia `motores:` del rol a `api`.

## 5. Qué pasa a `claude -p` y por qué corre fuera del repo

`BackendClaudeCode.completar_json` (`src/dogfood/backends/claude_code.py`) llama a `claude` con estas opciones:

| Opción | Cuándo | Para qué |
|---|---|---|
| `-p <prompt>` | Siempre | Modo headless, una sola respuesta |
| `--output-format json` | Siempre | Salida parseable con `result`, `usage`, `total_cost_usd`, `session_id` |
| `--json-schema <esquema>` | Siempre | Fuerza la salida al esquema Pydantic del rol |
| `--model <modelo>` | Siempre | Modelo de `claude_code.modelos` o de `roles` |
| `--strict-mcp-config` | Siempre | Ignora los MCP configurados por el usuario; solo cuentan los de `mcp_config` |
| `--allowedTools Read` | Siempre | Solo permite leer archivos, para revisar capturas |
| `--add-dir <carpetas>` | Si hay capturas | Da acceso de lectura a las carpetas de las imágenes |
| `--mcp-config <ruta>` | Si `mcp_config` no es nulo | Carga los MCP de ese archivo |
| `--resume <sesion>` | Si se pasa una sesión | Continúa una conversación previa |

El subproceso corre con `cwd` en un directorio temporal (`dogfood-claude-*`), no en el repo. Eso evita que `claude` cargue como contexto el `CLAUDE.md`, el `AGENTS.md` o la configuración del proyecto donde corre dogfood, y que lea archivos del repo por accidente. El entorno es una copia de `os.environ`, así que usa la sesión del usuario.

## 6. `--mcp-config` opcional

Si necesitas que el motor vea herramientas MCP, pon la ruta en `claude_code.mcp_config`:

```yaml
claude_code:
  mcp_config: /home/operador/dogfood/mcp.json
```

El archivo se pasa tal cual con `--mcp-config`, y `--strict-mcp-config` impide que se mezcle con los MCP del usuario. Deja `null` mientras no lo necesites: cada servidor MCP suma tokens a cada llamada y puede pedir autenticación.

## 7. Leer `costo_usd` frente a `costo_equivalente_usd`

Cada llamada registra dos costos (`UsoBackend` en `src/dogfood/backends/base.py`):

- **`costo_usd`**: lo que se cobra. En `claude_code` es **siempre `0`**, porque el plan Max no cobra por token.
- **`costo_equivalente_usd`**: lo que costaría la misma llamada por API. En `claude_code` es el `total_cost_usd` que reporta `claude`. En `api` es el costo calculado con `precios_usd_por_millon`, igual que `costo_usd`.

Por eso el `costo=` que muestra `dogfood runs` (que es `costo_usd`) sale en cero para las corridas hechas con `claude_code`. Para saber cuánto habrían costado, mira la columna `costo_equivalente_usd` de la base del almacén (tablas `ejecuciones` y `uso_llm`). Compara `costo_equivalente_usd` entre motores, no `costo_usd`.

## 8. Comparar el mismo escenario con `api` y con `claude_code`

Para comparar, corre el mismo escenario dos veces con la **misma semilla**, cambiando solo `motores:`:

1. Con `motores` en `api`:

```bash
dogfood run --target predicts --escenarios <id> --seed 42 --repeat 3 --sin-publicar
```

2. Cambia `motores` a `claude_code` en `dogfood.yaml` (los roles que quieras) y repite el mismo comando con `--seed 42`.

La semilla fija las personas y la asignación de escenarios (`src/dogfood/escenarios.py`), así que ambas corridas parten de los mismos usuarios. El modelo no es determinista, por eso usa `--repeat` y compara tasas de éxito, no ejecuciones sueltas. `--sin-publicar` evita que cada corrida abra issues en predicts.

Para comparar:

- `dogfood runs`: éxito por escenario y costo (`costo_usd`) de cada corrida.
- Las columnas de `ejecuciones` y `uso_llm` en la base del almacén: tokens, duración, `costo_usd` y `costo_equivalente_usd`.
- El panel de corridas (FR-32, `dogfood panel`): filtra por motor y compara resultado y costo. Aún no está registrado en esta rama; llega con F7.

Para acotar el gasto de la comparación con API, usa `--tope-usd`.
