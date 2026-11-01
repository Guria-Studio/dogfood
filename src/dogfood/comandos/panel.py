from pathlib import Path
from typing import Annotated

import typer

from dogfood.config import Config
from dogfood.panel.app import ESTATICO, crear_app_panel
from dogfood.web import servir, validar_host

app = typer.Typer(help="Abre el panel de corridas.")


@app.callback(invoke_without_command=True)
def panel(
    host: Annotated[str | None, typer.Option(help="Por defecto, cfg.panel.host.")] = None,
    puerto: Annotated[int | None, typer.Option(help="Por defecto, cfg.panel.puerto.")] = None,
    raiz: Annotated[Path, typer.Option(help="Carpeta de corridas.")] = Path("runs"),
) -> None:
    cfg = Config.cargar()
    host = host or cfg.panel.host
    try:
        validar_host(host)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from e
    if not (ESTATICO / "index.html").is_file():
        typer.echo("error: falta el build del panel: corre `scripts/build-web.sh`", err=True)
        raise typer.Exit(2)
    if not (raiz / "dogfood.db").exists():
        typer.echo(f"error: no hay {raiz / 'dogfood.db'}; corre `dogfood run` primero", err=True)
        raise typer.Exit(1)
    servir(crear_app_panel(raiz, cfg), host, puerto or cfg.panel.puerto)
