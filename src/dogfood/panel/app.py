from pathlib import Path

from fastapi import FastAPI

from dogfood.config import Config
from dogfood.panel import detalle, dispositivos
from dogfood.panel.api import registrar_api
from dogfood.panel.api_plan import registrar_api_plan
from dogfood.panel.ayuda import registrar_ayuda
from dogfood.panel.spa import montar_spa

ESTATICO = Path(__file__).parent / "estatico"


def crear_app_panel(raiz: Path, cfg: Config | None = None, spa: Path = ESTATICO) -> FastAPI:
    app = FastAPI(title="Panel")
    detalle.registrar_rutas(app, Path(raiz))
    dispositivos.registrar_rutas(app, Path(raiz), cfg)
    registrar_api(app, Path(raiz), cfg)
    registrar_api_plan(app, Path(raiz), cfg)
    registrar_ayuda(app, Path(__file__).parents[3])
    montar_spa(app, spa)  # sin build responde 503 con el mensaje de scripts/build-web.sh
    return app
