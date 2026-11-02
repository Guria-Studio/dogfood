"""API de suites y programaciones (F11.3.T3). Las que escriben exigen `X-Dogfood: 1`."""

import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, Header, HTTPException

from dogfood import suites
from dogfood.panel.acciones import Lanzador, LanzadorSistema


def registrar_api_suites(
    app: FastAPI,
    raiz: Path,
    lanzador: Lanzador | None = None,
    programador: suites.Programador | None = None,
) -> None:
    raiz = Path(raiz)
    lanz = lanzador or LanzadorSistema()
    prog = programador or suites.ProgramadorSystemd()

    def exigir(x_dogfood: str | None) -> None:
        if x_dogfood != "1":
            raise HTTPException(403, "falta el header X-Dogfood: 1")

    def validar(f):
        try:
            return f()
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    def suite(id: int) -> dict:
        s = suites.obtener(raiz, id)
        if s is None:
            raise HTTPException(404, f"la suite {id} no existe")
        return s

    @app.get("/api/suites")
    def listar():
        return suites.listar(raiz)

    @app.post("/api/suites", status_code=201)
    def crear(datos: Annotated[dict, Body()], x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        return validar(
            lambda: suites.crear(raiz, datos.get("nombre", ""), datos.get("casos") or [])
        )

    @app.delete("/api/suites/{id}")
    def borrar(id: int, x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        for p in suites.listar_programaciones(raiz):
            if p["suite_id"] == id:
                prog.borrar(p["id"])  # el timer no sobrevive a su suite
        if not suites.borrar(raiz, id):
            raise HTTPException(404, f"la suite {id} no existe")
        return {"borrada": id}

    @app.post("/api/suites/{id}/correr")
    def correr(id: int, x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        plan = suites.planear(raiz, suite(id))
        if not plan:
            raise HTTPException(400, "la suite no tiene casos de proyectos existentes")
        carpeta = raiz / "_lanzamientos"
        carpeta.mkdir(parents=True, exist_ok=True)
        ids = []
        for g in plan:
            lid = f"S{id}-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
            args = ["run", "--target", g["objetivo"], "--escenarios", ",".join(g["escenarios"]),
                    "--seed", str(g["semilla"]), "--sin-publicar"]  # fmt: skip
            lanz.lanzar(lid, args, raiz.resolve().parent, carpeta / f"{lid}.log")
            ids.append(lid)
        suites.registrar_lanzadas(raiz, id, plan)
        return {"lanzamientos": ids, "corridas": len(plan)}

    @app.get("/api/programaciones")
    def listar_programaciones():
        return suites.listar_programaciones(raiz)

    @app.post("/api/programaciones", status_code=201)
    def crear_programacion(
        datos: Annotated[dict, Body()], x_dogfood: str | None = Header(default=None)
    ):
        exigir(x_dogfood)
        try:
            sid = int(datos.get("suite_id"))
        except (TypeError, ValueError):
            raise HTTPException(400, "falta suite_id") from None
        return validar(lambda: suites.crear_programacion(raiz, prog, sid, datos))

    @app.delete("/api/programaciones/{id}")
    def borrar_programacion(id: int, x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        if not suites.borrar_programacion(raiz, prog, id):
            raise HTTPException(404, f"la programación {id} no existe")
        return {"borrada": id}
