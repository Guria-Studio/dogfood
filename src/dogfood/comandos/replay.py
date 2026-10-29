import asyncio
from pathlib import Path
from typing import Annotated

import typer

from dogfood.agente.replay import replay as repetir
from dogfood.almacen import Almacen
from dogfood.objetivos import cargar_objetivo

app = typer.Typer(help="Repite una ejecución sin LLM.")


@app.callback(invoke_without_command=True)
def replay(
    id: Annotated[str, typer.Argument(help="hallazgo_id o ejecucion_id.")],
    ref: Annotated[str, typer.Option(help="Rama, tag o commit.")] = "main",
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    runs: Annotated[Path, typer.Option(help="Carpeta de corridas.")] = Path("runs"),
) -> None:
    try:
        resultados = asyncio.run(
            repetir(id, almacen=Almacen(runs), objetivo=cargar_objetivo(target), ref=ref)
        )
    except (KeyError, ValueError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    if not resultados:
        typer.echo("la ejecución no tiene hallazgos que repetir")
    for h, res in resultados:
        typer.echo(f"{res}\t{h.huella[:10]}\t{h.titulo}")
    if any(r != "reproduce" for _, r in resultados):
        raise typer.Exit(1)
