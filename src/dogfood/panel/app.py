from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

from dogfood.panel import consultas, detalle
from dogfood.web import crear_app_base

_PLANTILLAS = Path(__file__).parent / "plantillas"
FILTROS = ("recorrido", "resultado", "version", "persona", "driver", "motor")


def registrar_rutas(app: FastAPI, plantillas: Jinja2Templates, raiz: Path) -> None:
    @app.get("/")
    def inicio(request: Request):
        filtros = {k: request.query_params.get(k, "") for k in FILTROS}
        return plantillas.TemplateResponse(
            request,
            "corridas.html",
            {
                "filas": consultas.ejecuciones(raiz, filtros),
                "filtros": filtros,
                "opciones": consultas.opciones_filtro(raiz),
                "etiquetas": consultas.ETIQUETAS,
            },
        )

    @app.get("/recorridos")
    def recorridos(request: Request, objetivo: str = "predicts"):
        return plantillas.TemplateResponse(
            request,
            "recorridos.html",
            {"recorridos": consultas.recorridos(raiz, objetivo), "etiquetas": consultas.ETIQUETAS},
        )

    @app.get("/corridas/{corrida_id}")
    def detalle_corrida(request: Request, corrida_id: str):
        resumen = consultas.corrida(raiz, corrida_id)
        if resumen is None:
            raise HTTPException(404, f"corrida {corrida_id!r} no existe")
        return plantillas.TemplateResponse(
            request,
            "corrida.html",
            {
                "c": resumen,
                "comparacion": consultas.comparacion_motores(raiz, corrida_id),
                "etiquetas": consultas.ETIQUETAS,
            },
        )


def crear_app_panel(raiz: Path) -> FastAPI:
    app, plantillas = crear_app_base("Panel", _PLANTILLAS)
    registrar_rutas(app, plantillas, Path(raiz))
    detalle.registrar_rutas(app, plantillas, Path(raiz))
    return app
