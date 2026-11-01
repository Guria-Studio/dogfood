"""Instancia aislada de predicts: git worktree + docker compose en el proyecto `dogfood-predicts`.

Nunca toca el proyecto de compose `predicts` ni el puerto 8080 de Héctor.
"""

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml
from dotenv import dotenv_values

from dogfood.dominio import Corrida, Instancia

PROYECTO = "dogfood-predicts"
PUERTO_WEB, PUERTO_API, PUERTO_PG = 18080, 18100, 54330
REPO_POR_DEFECTO = Path("/mnt/storage/project/predicts")
PARAMETROS = (
    "MIN_COMPRAS",
    "HORIZONTE_DIAS",
    "VENTANA_VALIDACION_SEMANAS",
    "CONFIANZA_MAPEO",
    "CONFIANZA_JEV",
)


class ErrorEntorno(RuntimeError):
    pass


def _dir_config() -> Path:
    return Path(os.environ.get("DOGFOOD_CONFIG_DIR") or Path.home() / ".config" / "dogfood")


def _dir_cache() -> Path:
    return Path.home() / ".cache" / "dogfood" / "predicts"


def _repo() -> Path:
    ruta = Path("dogfood.yaml")
    cfg = yaml.safe_load(ruta.read_text()) if ruta.exists() else None
    return Path((cfg or {}).get("predicts_repo") or REPO_POR_DEFECTO)


def _run(cmd: list[str], **kw) -> str:
    r = subprocess.run(cmd, check=False, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise ErrorEntorno(
            f"{' '.join(cmd[:4])}… falló ({r.returncode}): {r.stderr.strip()[-500:]}"
        )
    return r.stdout


def _compose(*args: str) -> list[str]:
    return ["docker", "compose", "-p", PROYECTO, *args]


def _env_file() -> Path:
    ruta = _dir_config() / "predicts.env"
    if not ruta.exists():
        raise ErrorEntorno(
            f"falta {ruta}: copia el .env de predicts con "
            f"`install -m 600 {_repo()}/deploy/.env {ruta}` (ver docs/ops/prerequisitos.md, punto 2)"
        )
    return ruta


def _worktree(ref: str) -> tuple[Path, str]:
    repo = _repo()
    commit = _run(["git", "-C", str(repo), "rev-parse", f"{ref}^{{commit}}"]).strip()
    ruta = _dir_cache() / ref.replace("/", "-")
    if ruta.exists():
        _run(["git", "-C", str(ruta), "checkout", "--detach", commit])
    else:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "-C", str(repo), "worktree", "add", "--detach", str(ruta), commit])
    return ruta, commit


def _override(carpeta: Path) -> Path:
    entorno = f"{{CORS_ORIGENES: 'http://localhost:{PUERTO_WEB}', ENTORNO: dev}}"
    texto = (
        "services:\n"
        f"  postgres: {{ports: !override ['{PUERTO_PG}:5432']}}\n"
        f"  api: {{ports: !override ['{PUERTO_API}:8000'], environment: {entorno}}}\n"
        f"  migrar: {{environment: {entorno}}}\n"
        f"  worker: {{environment: {entorno}}}\n"
        f"  web: {{ports: !override ['{PUERTO_WEB}:80']}}\n"
    )
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "docker-compose.override.yml"
    ruta.write_text(texto)
    return ruta


def _parametros(compose: Path, env: Path) -> dict[str, str]:
    base = {
        m[1]: m[2]
        for m in re.finditer(r"^\s+(\w+): \$\{\w+:-([^}]*)\}", compose.read_text(), re.MULTILINE)
        if m[1] in PARAMETROS
    }
    efectivos = {k: v for k, v in dotenv_values(env).items() if k in PARAMETROS and v}
    return {k: efectivos.get(k, base.get(k, "")) for k in PARAMETROS}


def _esperar_salud(url: str, timeout: float) -> None:
    limite = time.monotonic() + timeout
    while True:
        try:
            if httpx.get(url, timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > limite:
            raise ErrorEntorno(f"{url} no respondió 200 en {timeout:.0f}s")
        time.sleep(3)


def preparar(ref: str, corrida: Corrida, timeout_s: float = 600) -> Instancia:
    env = _env_file()
    worktree, commit = _worktree(ref)
    override = _override(Path("runs") / corrida.id)
    compose = worktree / "deploy" / "docker-compose.yml"
    _run(
        [
            "docker",
            "compose",
            "--env-file",
            str(env),
            "-p",
            PROYECTO,
            "-f",
            str(compose),
            "-f",
            str(override),
            "up",
            "-d",
            "--build",
            "--wait",
        ]
    )
    base = f"http://localhost:{PUERTO_WEB}"
    _esperar_salud(f"{base}/api/salud", timeout_s)
    return Instancia(
        base_url=base,
        # Por el proxy /api del web, como el front: la API sirve sus rutas sin /api.
        api_url=base,
        proyecto_compose=PROYECTO,
        commit=commit,
        parametros=_parametros(compose, env),
    )


def destruir(instancia: Instancia) -> None:
    if instancia.proyecto_compose != PROYECTO:
        raise ErrorEntorno(f"no destruyo el proyecto {instancia.proyecto_compose!r}")
    _run(_compose("down", "-v", "--remove-orphans"))


def logs(instancia: Instancia, desde: datetime) -> dict[str, str]:
    return {
        s: _run(
            ["docker", "compose", "-p", instancia.proyecto_compose]
            + ["logs", "--no-color", "--since", desde.isoformat(), s]
        )
        for s in ("api", "worker")
    }


def _origen(url: str) -> tuple[str, str, int | None]:
    u = urlparse(url)
    return u.scheme, (u.hostname or ""), u.port


def url_permitida(url: str, instancia: Instancia) -> bool:
    try:
        return _origen(url) in {_origen(instancia.base_url), _origen(instancia.api_url)}
    except ValueError:  # puerto inválido
        return False
