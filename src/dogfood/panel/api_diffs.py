"""Diffs de comportamiento entre versiones (F12.2.T1): lista, detalle, capturas y lanzamiento."""

import json
import secrets
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from dogfood import proyectos
from dogfood.almacen import Almacen
from dogfood.panel.acciones import Lanzador, LanzadorSistema

_REF = r"^[A-Za-z0-9][A-Za-z0-9._/@~^-]{0,99}$"  # sin «-» al inicio: no se cuela como opción


class ResumenDiff(BaseModel):
    id: str
    proyecto: str
    base: str
    nueva: str
    creado: str
    total: int
    con_cambios: int


class NuevoDiff(BaseModel):
    base: str = Field(pattern=_REF)
    nueva: str = Field(pattern=_REF)
    casos: str = Field(default="alta", pattern=r"^[A-Za-z0-9,]{1,200}$")


class DiffLanzado(BaseModel):
    id: str


def registrar_api_diffs(app: FastAPI, raiz: Path, lanzador: Lanzador | None = None) -> None:
    raiz = Path(raiz)
    lanz = lanzador or LanzadorSistema()

    def proyecto(slug: str) -> None:
        if proyectos.obtener(slug, raiz) is None:
            raise HTTPException(404, f"el proyecto {slug!r} no existe")

    @app.get("/api/proyectos/{slug}/diffs", response_model=list[ResumenDiff])
    def api_diffs(slug: str):
        proyecto(slug)
        return Almacen(raiz).listar_diffs(slug)

    @app.get("/api/diffs/{diff_id}")
    def api_diff(diff_id: str):
        try:
            return Almacen(raiz).diff(diff_id)
        except KeyError:
            raise HTTPException(404, f"el diff {diff_id!r} no existe") from None

    @app.get("/api/diffs/{diff_id}/capturas/{ruta:path}")
    def api_captura(diff_id: str, ruta: str):
        base = (raiz / diff_id / "capturas").resolve()
        f = (base / ruta).resolve()
        if not diff_id.startswith("diff-") or not f.is_relative_to(base) or not f.is_file():
            raise HTTPException(404, "la captura no existe")
        return FileResponse(f, media_type="image/png")

    @app.post("/api/proyectos/{slug}/diffs", response_model=DiffLanzado)
    def api_nuevo_diff(slug: str, d: NuevoDiff, x_dogfood: str | None = Header(default=None)):
        if x_dogfood != "1":  # un formulario de otro sitio no puede poner este header
            raise HTTPException(403, "falta el header X-Dogfood: 1")
        proyecto(slug)
        carpeta = raiz / "_lanzamientos"
        carpeta.mkdir(parents=True, exist_ok=True)
        id = f"D-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        args = ["diff", "--target", slug, "--base", d.base, "--nueva", d.nueva,
                "--casos", d.casos, "--runs", str(raiz)]  # fmt: skip
        h = lanz.lanzar(id, args, raiz.resolve().parent, carpeta / f"{id}.log")
        reg = {"id": id, "h": h, "semilla": None, "inicio": datetime.now().timestamp()}
        (carpeta / f"{id}.json").write_text(json.dumps(reg))
        return DiffLanzado(id=id)
