import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Annotated

import typer

from dogfood.almacen import Almacen

app = typer.Typer(help="Lista las corridas guardadas.")


@app.callback(invoke_without_command=True)
def runs(raiz: Annotated[Path, typer.Option(hidden=True)] = Path("runs")) -> None:
    almacen = Almacen(raiz)
    exito: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    with closing(sqlite3.connect(almacen.db)) as con:
        for corrida_id, escenario_id, ok in con.execute(
            "SELECT corrida_id, escenario_id, exito FROM ejecuciones"
        ):
            exito[corrida_id][escenario_id].append(ok)
    for c in almacen.listar_corridas():
        por_esc = ", ".join(f"{e} {sum(v)}/{len(v)}" for e, v in sorted(exito[c.id].items()))
        typer.echo(
            f"{c.id}  {c.inicio:%Y-%m-%d %H:%M}  {c.objetivo}@{c.ref}  {c.estado}  "
            f"personas={c.n_personas}  éxito: {por_esc or '-'}  "
            f"hallazgos={c.n_hallazgos}  costo=${c.costo_usd:.4f}"
        )
