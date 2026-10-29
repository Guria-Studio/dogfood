import importlib
import pkgutil

import typer

from dogfood import comandos

app = typer.Typer(
    help="dogfood: usuarios agénticos que prueban apps de verdad.", no_args_is_help=True
)

# Cada módulo de `comandos/` expone `app: typer.Typer` y opcionalmente `NOMBRE`.
for _info in pkgutil.iter_modules(comandos.__path__):
    if _info.name.startswith("_"):
        continue
    _modulo = importlib.import_module(f"{comandos.__name__}.{_info.name}")
    app.add_typer(_modulo.app, name=getattr(_modulo, "NOMBRE", _info.name))


def main() -> None:
    app()
