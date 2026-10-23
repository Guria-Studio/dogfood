# Prerrequisitos del operador

Lo que Héctor tiene que tener listo en el server antes de una corrida real de dogfood contra predicts. Cada punto dice qué fase lo necesita y cómo verificarlo.

Regla general: los secretos viven solo en `~/.config/dogfood/*.env`, con permisos `600`. Ningún comando de esta página imprime un valor; solo comprueban que la clave existe y no está vacía. No pegues valores en issues, reportes ni logs.

```bash
mkdir -p ~/.config/dogfood && chmod 700 ~/.config/dogfood
```

Comprobación rápida de todo lo de abajo, en un solo bloque, desde la raíz del repo:

```bash
uv run pytest && echo "pytest ok"
```

## 1. `~/.config/dogfood/router.env`

Credenciales de 9router, el gateway que da acceso a los modelos de todos los roles (`persona`, `juez`, `dedupe`, `redactor`).

- **Claves:** `ROUTER_BASE_URL` (la URL base de 9router, terminada en `/v1`) y `ROUTER_API_KEY`.
- **Fase que la necesita:** F0.1.T4 (`cliente_para`, configuración por rol), y desde ahí todas las fases que llaman a un modelo.
- **Verificar:**

```bash
f=~/.config/dogfood/router.env
stat -c '%a %n' "$f"                                   # debe decir 600
for k in ROUTER_BASE_URL ROUTER_API_KEY; do
  grep -q "^$k=.\+" "$f" && echo "$k presente" || echo "FALTA $k"
done
```

## 2. `~/.config/dogfood/predicts.env`

Variables que necesita la instancia propia de predicts que dogfood levanta con compose (web, api, worker y postgres).

- **Claves:** `ROUTER_BASE_URL`, `ROUTER_API_KEY`, `ROUTER_MODEL`, `TYPESAFE_API_KEY` y `TYPESAFE_MODEL`.
- **Origen:** se puede copiar de `/mnt/storage/project/predicts/deploy/.env`. Copia el archivo tal cual y con permisos restringidos:

```bash
install -m 600 /mnt/storage/project/predicts/deploy/.env ~/.config/dogfood/predicts.env
```

  Después de copiarlo, revisa que las claves de arriba estén. Si predicts cambió sus nombres de variables, la copia manda: ajusta aquí, no en predicts.
- **Fase que la necesita:** F1.1 (entorno predicts: el compose de la instancia de dogfood).
- **Verificar:**

```bash
f=~/.config/dogfood/predicts.env
stat -c '%a %n' "$f"                                   # debe decir 600
for k in ROUTER_BASE_URL ROUTER_API_KEY ROUTER_MODEL TYPESAFE_API_KEY TYPESAFE_MODEL; do
  grep -q "^$k=.\+" "$f" && echo "$k presente" || echo "FALTA $k"
done
```

## 3. `~/.config/dogfood/slack.env`

Webhook para el resumen de la corrida.

- **Clave:** `SLACK_WEBHOOK_URL`.
- **Cómo crear el incoming webhook:**
  1. En Slack, entra a <https://api.slack.com/apps> y crea una app «From scratch» en el workspace.
  2. En la app, abre **Incoming Webhooks** y actívalo con el interruptor.
  3. **Add New Webhook to Workspace**, elige el canal del resumen (el de proyectos, según el PRD) y autoriza.
  4. Copia la URL que empieza con `https://hooks.slack.com/services/` y pégala en el archivo.
- **Fase que la necesita:** F4.5 (resumen en Slack). Sin el archivo, la corrida avisa en consola y no falla; pero no llega el resumen.
- **Verificar:** la URL existe y tiene el formato del webhook, sin hacer un POST real.

```bash
f=~/.config/dogfood/slack.env
stat -c '%a %n' "$f"                                   # debe decir 600
grep -q '^SLACK_WEBHOOK_URL=https://hooks\.slack\.com/services/.\+' "$f" \
  && echo "SLACK_WEBHOOK_URL con formato válido" || echo "FALTA o formato inválido"
```

Si quieres probar que el canal recibe mensajes, manda un mensaje de prueba a mano; es el único paso que escribe en Slack, así que hazlo solo cuando lo quieras.

## 4. `gh` autenticado con permiso en `hectorcanaimero/predicts`

dogfood publica issues con `gh`. `gh` usa su propio login (no hay token en `~/.config/dogfood/`).

- **Qué hace falta:** sesión activa y permiso de escritura (crear issues y etiquetas) en el repo público `hectorcanaimero/predicts`.
- **Fase que la necesita:** F4.2 (issues). Sin esto, las corridas no pueden publicar ni deduplicar.
- **Verificar:**

```bash
gh auth status                                         # debe mostrar una cuenta activa
gh repo view hectorcanaimero/predicts --json viewerPermission --jq .viewerPermission
# debe imprimir WRITE, MAINTAIN o ADMIN
gh repo view hectorcanaimero/predicts --json hasIssuesEnabled --jq .hasIssuesEnabled
# debe imprimir true
```

Si imprime `READ` o `NONE`, la cuenta de `gh` no puede crear issues: vuelve a autenticar con la cuenta correcta (`gh auth login`).

## 5. Docker con Compose v2

La instancia de dogfood se levanta con `docker compose -p dogfood-predicts` y un override de puertos.

- **Qué hace falta:** Docker en marcha y el plugin `compose` en la versión 2 (el comando es `docker compose`, con espacio; no `docker-compose`).
- **Fase que la necesita:** F1.1 (entorno predicts) y todas las corridas reales. Los tests unitarios no lo usan.
- **Verificar:**

```bash
docker compose version                                 # debe decir v2.x
docker info --format '{{.ServerVersion}}'              # debe imprimir una versión, sin error
docker ps --format '{{.Names}}' | head -n 5            # el usuario debe tener acceso al socket
```

Si `docker info` falla con permisos, el usuario no está en el grupo `docker`.

## 6. Chromium de Playwright

El agente corre en un Chromium headless propio por ejecución, lanzado con Playwright. El navegador del server (CDP en `:9222`) no se usa para esto.

- **Instalación:**

```bash
uv run playwright install chromium
```

- **Fase que la necesita:** F1.4 (agente) y F1.5 (corrida).
- **Verificar:**

```bash
uv run python -c "from playwright.sync_api import sync_playwright as s
with s() as p:
    b = p.chromium.launch(headless=True); print('chromium ok', b.version); b.close()"
```

Debe imprimir `chromium ok` seguido de una versión. Si falla con «Executable doesn't exist», vuelve a correr la instalación.

Este paso depende de que las dependencias del proyecto estén sincronizadas (`uv sync`). El paquete `playwright` lo trae F0.1.T1.

## 7. `dogfood.yaml` copiado desde `dogfood.example.yaml`

La configuración real (roles → modelos, concurrencia, topes, umbral de gravedad, repo de issues, canal de Slack). Es local y no se commitea (`.gitignore`).

- **Cómo:**

```bash
cp dogfood.example.yaml dogfood.yaml
```

  `dogfood.example.yaml` lo crea F0.1.T1. Hasta que exista en la raíz del repo, este paso no se puede hacer.
- **Fase que la necesita:** F0.1.T4 (carga de configuración). Si `dogfood.yaml` no existe, el código usa `dogfood.example.yaml` y avisa; para una corrida real conviene tener la copia propia.
- **Verificar:**

```bash
test -f dogfood.yaml && echo "dogfood.yaml presente"
git check-ignore -q dogfood.yaml && echo "ignorado por git"
```

## 8. Puertos libres: 18080, 18100 y 54330

Son los puertos de la instancia de dogfood de predicts: web (18080), api (18100) y postgres (54330). Deben estar libres antes de `dogfood env up`. Los puertos de desarrollo de Héctor (`WEB_PORT=8080`, `API_PORT=8100`) no se tocan.

- **Fase que la necesita:** F1.1 (override de puertos del compose).
- **Verificar:** ninguno de los tres debe tener un proceso escuchando.

```bash
for p in 18080 18100 54330; do
  if ss -ltnH "sport = :$p" | grep -q .; then echo "OCUPADO :$p"; else echo "libre :$p"; fi
done
```

Si alguno está ocupado, identifica el proceso con `ss -ltnp "sport = :PUERTO"` antes de matarlo. Si es una instancia de predicts de una corrida anterior, bájala con `docker compose -p dogfood-predicts down -v` en lugar de tocar otros proyectos de compose.

## Resumen

| # | Requisito | Fase | Verificación |
|---|-----------|------|--------------|
| 1 | `router.env` | F0.1.T4 | `stat` 600 y claves con valor |
| 2 | `predicts.env` | F1.1 | `stat` 600 y claves con valor |
| 3 | `slack.env` | F4.5 | formato de `SLACK_WEBHOOK_URL` |
| 4 | `gh` con permiso | F4.2 | `gh auth status` y `viewerPermission` ≠ READ |
| 5 | Docker + compose v2 | F1.1 | `docker compose version` |
| 6 | Chromium de Playwright | F1.4, F1.5 | `chromium.launch` ok |
| 7 | `dogfood.yaml` | F0.1.T4 | `test -f` y gitignored |
| 8 | Puertos 18080, 18100, 54330 | F1.1 | `ss` sin listeners |
