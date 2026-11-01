"""Sirve el build de la SPA (Vite): assets, `index.html` de respaldo y 503 si falta el build."""

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match, Mount, Route

# Rutas que la SPA nunca intercepta (otras rutas del panel o de la vista).
_RESERVADAS = re.compile(
    r"^/(api|archivos|estatico|ws|docs|redoc|openapi\.json)(/|$)|^/dispositivos/.+/mjpeg$"
)
_SIN_BUILD = "falta el build del panel: corre `scripts/build-web.sh`"


class _RutaSpa(Route):
    def matches(self, scope):
        if _RESERVADAS.match(scope.get("path", "")):
            return Match.NONE, {}
        return super().matches(scope)


def montar_spa(app: FastAPI, carpeta: Path) -> None:
    carpeta = Path(carpeta)
    index = carpeta / "index.html"

    def servir(request):
        ruta = request.path_params["ruta"]
        if not index.is_file():
            return PlainTextResponse(_SIN_BUILD, status_code=503)
        destino = (carpeta / ruta).resolve()
        if ruta and destino.is_relative_to(carpeta.resolve()) and destino.is_file():
            return FileResponse(destino)
        return FileResponse(index)

    # Al principio de la lista para ganarle a las rutas Jinja con el mismo camino.
    app.router.routes.insert(0, _RutaSpa("/{ruta:path}", servir, methods=["GET", "HEAD"]))
    if (carpeta / "assets").is_dir():
        app.router.routes.insert(
            0, Mount("/assets", app=StaticFiles(directory=carpeta / "assets"), name="assets")
        )
