from typing import Annotated

import typer

from dogfood.comandos._stub import no_implementado

app = typer.Typer(help="Repite una ejecución sin LLM.")


@app.callback(invoke_without_command=True)
def replay(
    id: Annotated[str, typer.Argument(help="hallazgo_id o ejecucion_id.")],
) -> None:
    no_implementado()
