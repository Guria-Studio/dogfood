from typing import Annotated

import typer

from dogfood.comandos._stub import no_implementado

app = typer.Typer(help="Levanta o destruye la instancia del objetivo.")


@app.command()
def up(
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    ref: Annotated[str, typer.Option(help="Rama, tag o commit.")] = "main",
) -> None:
    no_implementado()


@app.command()
def down(
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    ref: Annotated[str, typer.Option(help="Rama, tag o commit.")] = "main",
) -> None:
    no_implementado()
