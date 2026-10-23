import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from dogfood.datos.generador import generar
from dogfood.datos.perfiles import PERFILES

app = typer.Typer(help="Genera un dataset sintético.")


@app.callback(invoke_without_command=True)
def datos(
    perfil: Annotated[str, typer.Option(help=f"Rubro: {', '.join(PERFILES)}.")],
    clientes: Annotated[int, typer.Option(min=1, help="Cantidad de clientes.")],
    defectos: Annotated[str | None, typer.Option(help="Separados por coma.")] = None,
    seed: Annotated[int | None, typer.Option(help="Semilla.")] = None,
    salida: Annotated[Path | None, typer.Option(help="Carpeta de salida.")] = None,
    fecha_max: Annotated[
        datetime, typer.Option(formats=["%Y-%m-%d"], help="Última fecha de venta.")
    ] = datetime(2026, 6, 30),
) -> None:
    if defectos:
        typer.echo("--defectos: disponible en F2")
        raise typer.Exit(2)
    if perfil not in PERFILES:
        raise typer.BadParameter(f"usa uno de: {', '.join(PERFILES)}", param_hint="--perfil")
    if seed is None:
        seed = secrets.randbelow(2**31)
    ds = generar(perfil, clientes, seed, fecha_max.date(), salida=salida)
    typer.echo(f"{ds.ruta_csv} ({ds.n_filas} filas)\n{ds.ruta_verdad}\nsemilla: {seed}")
