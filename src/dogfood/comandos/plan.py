from pathlib import Path
from typing import Annotated

import typer

from dogfood.objetivos import cargar_objetivo
from dogfood.personas.generador import generar
from dogfood.plan import armar_plan

app = typer.Typer(help="Arma el plan de pruebas (casos) sin correrlo.")


@app.callback(invoke_without_command=True)
def plan(
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    personas: Annotated[int, typer.Option(help="Cantidad de personas.")] = 1,
    seed: Annotated[int, typer.Option(help="Semilla.")] = 0,
    raiz: Annotated[Path, typer.Option(help="Carpeta de corridas.")] = Path("runs"),
) -> None:
    try:
        objetivo = cargar_objetivo(target)
        lista = generar(personas, seed)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    p = armar_plan(objetivo.nombre, lista, objetivo.escenarios(), seed)
    for c in p.casos:
        typer.echo(f"{c.id:36}  {c.prioridad:5}  {c.titulo}")
    for aviso in p.avisos:
        typer.echo(f"Aviso: {aviso}")
    raiz.mkdir(parents=True, exist_ok=True)
    salida = raiz / f"plan-{seed}.json"
    salida.write_text(p.model_dump_json(indent=2))
    typer.echo(f"guardado en {salida}")
