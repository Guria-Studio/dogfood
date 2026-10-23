import typer

from dogfood.comandos import datos, env, personas, replay, run, runs

app = typer.Typer(
    help="dogfood: usuarios agénticos que prueban apps de verdad.", no_args_is_help=True
)

for _nombre, _modulo in [
    ("env", env),
    ("datos", datos),
    ("personas", personas),
    ("run", run),
    ("runs", runs),
    ("replay", replay),
]:
    app.add_typer(_modulo.app, name=_nombre)


def main() -> None:
    app()
