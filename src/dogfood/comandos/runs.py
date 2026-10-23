import typer

from dogfood.comandos._stub import no_implementado

app = typer.Typer(help="Lista las corridas guardadas.")


@app.callback(invoke_without_command=True)
def runs() -> None:
    no_implementado()
