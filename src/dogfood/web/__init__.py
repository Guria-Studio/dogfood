"""Base web compartida por la vista en vivo y el panel."""

import ipaddress
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, Environment, FileSystemLoader

_AQUI = Path(__file__).parent
_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")


def validar_host(host: str) -> str:
    """Acepta loopback o Tailscale (NFR-10); cualquier otro host lanza ValueError."""
    if host == "localhost":
        return host
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_loopback or ip in _TAILSCALE):
        return host
    raise ValueError(
        f"host {host!r} no permitido (NFR-10): la vista y el panel solo escuchan en "
        "127.0.0.1, localhost, ::1 o una IP de Tailscale (100.64.0.0/10); nunca 0.0.0.0"
    )


def _duracion(segundos: float | None) -> str:
    if segundos is None:
        return "—"
    total = round(segundos)
    minutos, seg = divmod(total, 60)
    return f"{minutos} min {seg:02d} s" if minutos else f"{seg} s"


def _usd(valor: float | None) -> str:
    return "—" if valor is None else f"{valor:.4f}"


def _fecha(valor: datetime | str | float | None) -> str:
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, (int, float)):
        valor = datetime.fromtimestamp(valor)
    elif isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    return valor.strftime("%Y-%m-%d %H:%M")


def crear_app_base(
    titulo: str, plantillas_extra: Path | None = None
) -> tuple[FastAPI, Jinja2Templates]:
    app = FastAPI(title=titulo)
    app.mount("/estatico", StaticFiles(directory=_AQUI / "estatico"), name="estatico")
    carpetas = [str(plantillas_extra)] if plantillas_extra else []
    carpetas.append(str(_AQUI / "plantillas"))
    env = Environment(loader=ChoiceLoader([FileSystemLoader(c) for c in carpetas]), autoescape=True)
    env.filters.update(duracion=_duracion, usd=_usd, fecha=_fecha)
    env.globals["titulo_app"] = titulo
    return app, Jinja2Templates(env=env)


def servir(app: FastAPI, host: str, puerto: int) -> None:
    uvicorn.run(app, host=validar_host(host), port=puerto)
