import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from dogfood.datos.defectos import DEFECTOS, aplicar
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
    lista = [d.strip() for d in defectos.split(",") if d.strip()] if defectos else []
    desconocidos = [d for d in lista if d not in DEFECTOS]
    if desconocidos:
        raise typer.BadParameter(
            f"desconocidos: {', '.join(desconocidos)}. Válidos: {', '.join(DEFECTOS)}",
            param_hint="--defectos",
        )
    if perfil not in PERFILES:
        raise typer.BadParameter(f"usa uno de: {', '.join(PERFILES)}", param_hint="--perfil")
    if seed is None:
        seed = secrets.randbelow(2**31)
    ds = generar(perfil, clientes, seed, fecha_max.date(), salida=salida)
    ruta_csv = aplicar(ds.ruta_csv, lista, seed) if lista else ds.ruta_csv
    typer.echo(f"{ruta_csv} ({ds.n_filas} filas)\n{ds.ruta_verdad}\nsemilla: {seed}")
