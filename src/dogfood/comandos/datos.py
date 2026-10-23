from pathlib import Path
from typing import Annotated

import typer

from dogfood.comandos._stub import no_implementado

app = typer.Typer(help="Genera un dataset sintético.")


@app.callback(invoke_without_command=True)
def datos(
    perfil: Annotated[str, typer.Option(help="Rubro, p. ej. farmacia.")],
    clientes: Annotated[int, typer.Option(help="Cantidad de clientes.")],
    defectos: Annotated[str | None, typer.Option(help="Separados por coma.")] = None,
    seed: Annotated[int | None, typer.Option(help="Semilla.")] = None,
    salida: Annotated[Path | None, typer.Option(help="Carpeta de salida.")] = None,
) -> None:
    no_implementado()
