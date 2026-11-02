"""API de proyectos: lista con el último resultado, alta, lectura, cambios y baja."""

from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, Header, HTTPException

from dogfood import proyectos
from dogfood.config import Config


def registrar_api_proyectos(app: FastAPI, raiz: Path, cfg: Config | None = None) -> None:
    raiz = Path(raiz)

    def exigir(x_dogfood: str | None) -> None:
        if x_dogfood != "1":  # un formulario de otro sitio no puede poner este header
            raise HTTPException(403, "falta el header X-Dogfood: 1")

    def validar(f):
        try:
            return f()
        except ValueError as exc:  # incluye ValidationError y ErrorProyecto
            raise HTTPException(400, str(exc).replace("\n", " ")) from None

    def uno(slug: str) -> proyectos.Proyecto:
        p = proyectos.obtener(slug, raiz)
        if p is None:
            raise HTTPException(404, f"el proyecto {slug!r} no existe")
        return p

    @app.get("/api/proyectos")
    def listar():
        return [
            p.model_dump(mode="json") | {"ultimos": proyectos.ultimos_resultados(p, raiz)}
            for p in proyectos.listar(raiz)
        ]

    @app.post("/api/proyectos", status_code=201)
    def crear(datos: Annotated[dict, Body()], x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        return validar(lambda: proyectos.crear(datos, raiz)).model_dump(mode="json")

    @app.get("/api/proyectos/{slug}")
    def leer(slug: str):
        p = uno(slug)
        return p.model_dump(mode="json") | {"ultimos": proyectos.ultimos_resultados(p, raiz)}

    @app.patch("/api/proyectos/{slug}")
    def cambiar(
        slug: str, cambios: Annotated[dict, Body()], x_dogfood: str | None = Header(default=None)
    ):
        exigir(x_dogfood)
        uno(slug)
        return validar(lambda: proyectos.actualizar(slug, cambios, raiz)).model_dump(mode="json")

    @app.delete("/api/proyectos/{slug}")
    def borrar(
        slug: str,
        cuerpo: Annotated[dict | None, Body()] = None,
        x_dogfood: str | None = Header(default=None),
    ):
        exigir(x_dogfood)
        uno(slug)
        if (cuerpo or {}).get("confirmar") != slug:
            raise HTTPException(400, 'confirma con el slug en el cuerpo: {"confirmar": "<slug>"}')
        proyectos.borrar(slug, raiz)
        return {"borrado": slug}
