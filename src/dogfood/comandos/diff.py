import asyncio
from pathlib import Path
from typing import Annotated

import typer

from dogfood import diff as motor
from dogfood import proyectos
from dogfood.almacen import Almacen
from dogfood.objetivos import cargar_objetivo
from dogfood.rea import adaptador

app = typer.Typer(help="Diff de comportamiento entre dos refs, grabado con REA.")


def _error(msg: str) -> typer.Exit:
    typer.echo(f"error: {msg}", err=True)
    return typer.Exit(1)


@app.callback(invoke_without_command=True)
def diff(
    target: Annotated[str, typer.Option(help="Slug del proyecto.")],
    base: Annotated[str, typer.Option(help="Ref de partida (rama, tag o commit).")],
    nueva: Annotated[str, typer.Option(help="Ref a comparar.")],
    casos: Annotated[str, typer.Option(help="alta, todos o una lista: TC001,TC007.")] = "alta",
    runs: Annotated[Path, typer.Option(help="Carpeta de corridas.")] = Path("runs"),
) -> None:
    if not adaptador.disponible():
        raise _error("no hay `rea` ni `npx` en el PATH")
    p = proyectos.obtener(target, runs)
    if p is None:
        raise _error(f"no existe el proyecto {target!r}")
    try:
        elegidos, omitidos = motor.seleccionar(runs, target, casos)
        if not elegidos:
            # ninguna ejecución exitosa: antes de grabar se lanza una corrida chica en `base`
            from dogfood.corrida import Opciones, correr

            typer.echo("no hay ejecuciones exitosas; lanzo una corrida chica en la base…")
            asyncio.run(correr(Opciones(objetivo=target, ref=base, personas=1, sin_publicar=True)))
            elegidos, omitidos = motor.seleccionar(runs, target, casos)
    except (KeyError, ValueError) as e:
        raise _error(str(e)) from e
    if omitidos:
        typer.echo(f"sin ejecución exitosa, se omiten: {', '.join(omitidos)}", err=True)
    if not elegidos:
        raise _error("ningún caso elegido tiene una ejecución exitosa")
    d = motor.diff(
        proyecto=target,
        objetivo=cargar_objetivo(p.objetivo),
        base=base,
        nueva=nueva,
        casos=elegidos,
        almacen=Almacen(runs),
    )
    con = sum(c["resultado"] == "cambios" for c in d["casos"])
    typer.echo(f"{d['id']}: {con} de {len(d['casos'])} casos con cambios → {runs / d['id']}")
