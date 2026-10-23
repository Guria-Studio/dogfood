from typing import Annotated

import typer

from dogfood.comandos._stub import no_implementado

app = typer.Typer(help="Genera personas deterministas.")


@app.callback(invoke_without_command=True)
def personas(
    n: Annotated[int, typer.Option(help="Cantidad de personas.")],
    seed: Annotated[int | None, typer.Option(help="Semilla.")] = None,
    idiomas: Annotated[str | None, typer.Option(help="Ej. pt-BR:0.5,es:0.5.")] = None,
) -> None:
    no_implementado()
