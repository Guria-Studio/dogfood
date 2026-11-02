"""Exploración y escenarios propuestos de un proyecto (F13.2.T1).

`POST …/exploraciones` lanza `dogfood explorar` con el lanzador del panel (F10.2.T3); su estado se
lee por `GET /api/corridas/{id}/estado`, como cualquier lanzamiento.
"""

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Body, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, ValidationError

from dogfood import proyectos
from dogfood.almacen import Almacen
from dogfood.dominio import Escenario
from dogfood.panel.acciones import Lanzador, LanzadorSistema, Lanzamiento

ESTADOS = ("borrador", "aceptado", "descartado")


class NuevaExploracion(BaseModel):
    max_paginas: int = Field(default=25, ge=1, le=200)


def registrar_api_escenarios(app: FastAPI, raiz: Path, lanzador: Lanzador | None = None) -> None:
    raiz = Path(raiz)
    lanz = lanzador or LanzadorSistema()

    def exigir(x_dogfood: str | None) -> None:
        if x_dogfood != "1":  # un formulario de otro sitio no puede poner este header
            raise HTTPException(403, "falta el header X-Dogfood: 1")

    def proyecto(slug: str) -> proyectos.Proyecto:
        p = proyectos.obtener(slug, raiz)
        if p is None:
            raise HTTPException(404, f"el proyecto {slug!r} no existe")
        return p

    def escenario(slug: str, id: str) -> dict:
        proyecto(slug)
        filas = Almacen(raiz).escenarios_proyecto(slug, id)
        if not filas:
            raise HTTPException(404, f"el escenario {id!r} no existe en {slug!r}")
        return filas[0]

    @app.post("/api/proyectos/{slug}/exploraciones", response_model=Lanzamiento)
    def api_explorar(
        slug: str,
        n: Annotated[NuevaExploracion | None, Body()] = None,
        x_dogfood: str | None = Header(default=None),
    ):
        exigir(x_dogfood)
        p = proyecto(slug)
        if p.objetivo != "web":
            raise HTTPException(422, f"explorar es para proyectos web; {slug!r} es {p.objetivo!r}")
        carpeta = raiz / "_lanzamientos"
        carpeta.mkdir(parents=True, exist_ok=True)
        id = f"X-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        args = ["explorar", "--proyecto", slug, "--max-paginas", str((n or NuevaExploracion()).max_paginas),
                "--runs", str(raiz.resolve())]  # fmt: skip
        h = lanz.lanzar(id, args, raiz.resolve().parent, carpeta / f"{id}.log")
        reg = {"id": id, "h": h, "semilla": None, "inicio": datetime.now().timestamp()}
        (carpeta / f"{id}.json").write_text(json.dumps(reg))
        return Lanzamiento(id=id)

    @app.get("/api/proyectos/{slug}/mapa")
    def api_mapa(slug: str) -> dict:
        proyecto(slug)
        m = Almacen(raiz).ultima_exploracion(slug)
        if m is None:
            raise HTTPException(404, f"el proyecto {slug!r} todavía no se exploró")
        return m

    @app.get("/api/proyectos/{slug}/escenarios")
    def api_escenarios(
        slug: str, estado: Literal["borrador", "aceptado", "descartado"] | None = None
    ):
        proyecto(slug)
        return [e for e in Almacen(raiz).escenarios_proyecto(slug) if estado in (None, e["estado"])]

    @app.get("/api/proyectos/{slug}/escenarios/{id}")
    def api_escenario(slug: str, id: str) -> dict:
        return escenario(slug, id)

    @app.patch("/api/proyectos/{slug}/escenarios/{id}")
    def api_editar_escenario(
        slug: str,
        id: str,
        cambios: Annotated[dict, Body()],
        x_dogfood: str | None = Header(default=None),
    ) -> dict:
        """`estado` (aceptar o descartar), `prioridad` o cualquier campo del escenario, salvo `id`."""
        exigir(x_dogfood)
        actual = escenario(slug, id)
        estado = cambios.pop("estado", actual["estado"])
        prioridad = cambios.pop("prioridad", actual["prioridad"])
        if estado not in ESTADOS:
            raise HTTPException(422, f"estado inválido: {estado!r} (válidos: {', '.join(ESTADOS)})")
        if prioridad not in ("alta", "media"):
            raise HTTPException(422, f"prioridad inválida: {prioridad!r} (válidas: alta, media)")
        datos = {k: v for k, v in actual.items() if k not in ("estado", "prioridad", "creado")}
        datos |= {k: v for k, v in cambios.items() if k not in ("id", "creado")}
        try:
            esc = Escenario.model_validate(datos)
        except ValidationError as e:
            raise HTTPException(422, json.loads(e.json(include_url=False))) from None
        Almacen(raiz).actualizar_escenario(
            slug, id, esc.model_dump(mode="json", exclude_none=True), estado, prioridad
        )
        return escenario(slug, id)

    @app.delete("/api/proyectos/{slug}/escenarios/{id}")
    def api_borrar_escenario(slug: str, id: str, x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        escenario(slug, id)
        Almacen(raiz).borrar_escenario(slug, id)
        return {"id": id, "borrado": True}
