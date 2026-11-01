"""Acciones del panel: lanzar, vigilar, cancelar y repetir corridas como procesos aparte."""

import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dogfood.config import Config
from dogfood.panel import api_plan

_CLI = [sys.executable, "-c", "from dogfood.cli import main; main()"]


class Lanzador(Protocol):
    def lanzar(self, id: str, args: list[str], cwd: Path, log: Path) -> dict: ...
    def vivo(self, h: dict) -> bool: ...
    def detener(self, h: dict) -> None: ...


class LanzadorSistema:
    """`systemd-run --user` si hay sesión de usuario; si no, un subprocess desacoplado."""

    def _systemd(self) -> bool:
        return bool(shutil.which("systemd-run")) and (
            subprocess.run(
                ["systemctl", "--user", "is-system-running"], check=False, capture_output=True
            ).returncode
            in (0, 1)  # 1 = degraded, pero hay manager
        )

    def lanzar(self, id: str, args: list[str], cwd: Path, log: Path) -> dict:
        cmd = [*_CLI, *args]
        if self._systemd():
            unidad = f"dogfood-{id}"
            r = subprocess.run(
                ["systemd-run", "--user", "--unit", unidad, f"--working-directory={cwd}",
                 f"--property=StandardOutput=append:{log}", f"--property=StandardError=append:{log}",
                 *cmd],
                check=False, capture_output=True,
            )  # fmt: skip
            if r.returncode == 0:
                return {"unidad": unidad}
        with log.open("ab") as f:
            p = subprocess.Popen(
                cmd, cwd=cwd, stdout=f, stderr=f, stdin=subprocess.DEVNULL, start_new_session=True
            )
        return {"pid": p.pid}

    def vivo(self, h: dict) -> bool:
        if "unidad" in h:
            r = subprocess.run(
                ["systemctl", "--user", "is-active", h["unidad"]], check=False, capture_output=True
            )
            return r.returncode == 0
        try:
            pid, _ = os.waitpid(h["pid"], os.WNOHANG)  # cosecha el zombi si es hijo nuestro
            return pid == 0
        except ChildProcessError:
            try:
                os.kill(h["pid"], 0)
            except OSError:
                return False
            return True

    def detener(self, h: dict) -> None:
        if "unidad" in h:
            subprocess.run(
                ["systemctl", "--user", "stop", h["unidad"]], check=False, capture_output=True
            )
        else:
            try:
                os.killpg(h["pid"], signal.SIGTERM)
            except OSError:
                pass


class NuevaCorrida(BaseModel):
    objetivo: str = "predicts"
    ref: str = "main"
    personas: int = Field(default=1, ge=1, le=50)
    escenarios: list[str] | None = None
    semilla: int | None = None
    vista: bool = False
    sin_publicar: bool = True


class Lanzamiento(BaseModel):
    id: str


class EstadoLanzamiento(BaseModel):
    id: str
    estado: Literal["activa", "terminada", "cancelada"]
    corrida_id: str | None
    terminados: int
    total: int
    en_curso: list[str]
    log: list[str]


def registrar_acciones(
    app: FastAPI, raiz: Path, cfg: Config | None = None, lanzador: Lanzador | None = None
) -> None:
    raiz = Path(raiz)
    lanz = lanzador or LanzadorSistema()
    carpeta = raiz / "_lanzamientos"

    def exigir(x_dogfood: str | None) -> None:
        if x_dogfood != "1":  # un formulario de otro sitio no puede poner este header
            raise HTTPException(403, "falta el header X-Dogfood: 1")

    def leer(id: str) -> dict:
        ruta = carpeta / f"{id}.json"
        if "/" in id or not ruta.is_file():
            raise HTTPException(404, f"el lanzamiento {id!r} no existe")
        return json.loads(ruta.read_text())

    def activo() -> str | None:
        for ruta in carpeta.glob("*.json") if carpeta.is_dir() else []:
            r = json.loads(ruta.read_text())
            if not r.get("cancelada") and lanz.vivo(r["h"]):
                return r["id"]
        return None

    def lanzar(tipo: str, args: list[str], semilla: int | None = None) -> Lanzamiento:
        if (otra := activo()) is not None:
            raise HTTPException(409, f"ya hay una corrida activa: {otra}")
        carpeta.mkdir(parents=True, exist_ok=True)
        id = f"{tipo}-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        log = carpeta / f"{id}.log"
        # el CLI crea la carpeta relativa a "runs": corre desde el padre de la raíz
        h = lanz.lanzar(id, args, raiz.resolve().parent, log)
        reg = {"id": id, "h": h, "semilla": semilla, "inicio": datetime.now().timestamp()}
        (carpeta / f"{id}.json").write_text(json.dumps(reg))
        return Lanzamiento(id=id)

    @app.post("/api/corridas", response_model=Lanzamiento)
    def api_nueva_corrida(c: NuevaCorrida, x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        semilla = c.semilla if c.semilla is not None else secrets.randbelow(2**31)
        args = ["run", "--target", c.objetivo, "--ref", c.ref, "--personas", str(c.personas),
                "--seed", str(semilla)]  # fmt: skip
        if c.escenarios:
            args += ["--escenarios", ",".join(c.escenarios)]
        if c.vista:
            args.append("--vista")
        if c.sin_publicar:
            args.append("--sin-publicar")
        return lanzar("L", args, semilla)

    @app.post("/api/ejecuciones/{ejecucion_id}/replay", response_model=Lanzamiento)
    def api_replay(
        ejecucion_id: str, ref: str = "main", objetivo: str = "predicts",
        x_dogfood: str | None = Header(default=None),
    ):  # fmt: skip
        exigir(x_dogfood)
        return lanzar(
            "R", ["replay", ejecucion_id, "--ref", ref, "--target", objetivo, "--runs", str(raiz)]
        )

    @app.get("/api/corridas/{lanzamiento_id}/estado", response_model=EstadoLanzamiento)
    def api_estado(lanzamiento_id: str):
        r = leer(lanzamiento_id)
        log = carpeta / f"{lanzamiento_id}.log"
        texto = log.read_text(errors="replace").splitlines()[-20:] if log.is_file() else []
        cid = None
        if r["semilla"] is not None:  # el id real lo genera el proceso: se busca por la semilla
            for d in sorted(raiz.glob(f"*-{r['semilla']}-*")):
                if d.is_dir() and d.stat().st_mtime >= r["inicio"] - 5:
                    cid = d.name
        casos = (api_plan.casos(raiz, cid) if cid else None) or []
        vivo = lanz.vivo(r["h"])
        estado = "cancelada" if r.get("cancelada") else "activa" if vivo else "terminada"
        return EstadoLanzamiento(
            id=lanzamiento_id, estado=estado, corrida_id=cid, total=len(casos),
            terminados=sum(c.estado not in ("pendiente", "en_curso") for c in casos),
            en_curso=[c.titulo for c in casos if c.estado == "en_curso"], log=texto,
        )  # fmt: skip

    @app.post("/api/corridas/{lanzamiento_id}/cancelar")
    def api_cancelar(lanzamiento_id: str, x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        r = leer(lanzamiento_id)
        lanz.detener(r["h"])
        r["cancelada"] = True
        (carpeta / f"{lanzamiento_id}.json").write_text(json.dumps(r))
        return JSONResponse({"id": lanzamiento_id, "estado": "cancelada"})
