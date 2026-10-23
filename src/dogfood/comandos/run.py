from typing import Annotated

import typer

from dogfood.comandos._stub import no_implementado

app = typer.Typer(help="Corre usuarios agénticos contra el objetivo.")


@app.callback(invoke_without_command=True)
def run(
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    personas: Annotated[int | None, typer.Option(help="Cantidad de personas.")] = None,
    escenarios: Annotated[str | None, typer.Option(help="Ids separados por coma.")] = None,
    seed: Annotated[int | None, typer.Option(help="Semilla.")] = None,
    ref: Annotated[str, typer.Option(help="Rama, tag o commit.")] = "main",
    concurrencia: Annotated[int, typer.Option(help="Ejecuciones en paralelo.")] = 5,
    repeat: Annotated[int, typer.Option(help="Repeticiones.")] = 1,
    sin_publicar: Annotated[bool, typer.Option("--sin-publicar", help="No crea issues.")] = False,
    tope_usd: Annotated[float | None, typer.Option("--tope-usd", help="Tope de costo.")] = None,
) -> None:
    no_implementado()
