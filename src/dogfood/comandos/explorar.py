import asyncio
from pathlib import Path
from typing import Annotated

import typer

from dogfood import proyectos

app = typer.Typer(help="Explora una app web: mapa de funcionalidades y escenarios propuestos.")


@app.callback(invoke_without_command=True)
def explorar(
    proyecto: Annotated[str, typer.Option(help="Slug del proyecto.")],
    max_paginas: Annotated[int, typer.Option(min=1, help="Pantallas distintas a visitar.")] = 25,
    prd: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="PRD en Markdown (si no, el del proyecto)."),
    ] = None,
    runs: Annotated[Path, typer.Option(help="Carpeta de corridas.")] = Path("runs"),
) -> None:
    from dogfood.config import Config
    from dogfood.explorar import explorar as motor

    p = proyectos.obtener(proyecto, runs)
    if p is None:
        typer.echo(f"error: no existe el proyecto {proyecto!r}", err=True)
        raise typer.Exit(1)
    try:
        r = asyncio.run(
            motor(
                p,
                raiz=runs,
                cfg=Config.cargar(),
                max_paginas=max_paginas,
                prd=prd.read_text("utf-8") if prd else None,
            )
        )
    except (ValueError, RuntimeError, TimeoutError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    casos = [c for f in r["funcionalidades"] for c in f["casos"]]
    brechas = sum(c["estado"] == "solo_prd" for c in casos)
    typer.echo(
        f"{len(r['pantallas'])} pantallas, {len(r['funcionalidades'])} funcionalidades, "
        f"{len(casos)} casos ({brechas} solo en el PRD), {len(r['escenarios'])} escenarios en "
        f"borrador; costo {r['costo_usd']:.4f} USD → {runs / r['id'] / 'mapa.json'}"
    )
