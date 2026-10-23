from datetime import datetime
from typing import Annotated

import typer

from dogfood.dominio import Corrida, Instancia
from dogfood.objetivos import cargar_objetivo

app = typer.Typer(help="Levanta o destruye la instancia del objetivo.")


@app.command()
def up(
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    ref: Annotated[str, typer.Option(help="Rama, tag o commit.")] = "main",
) -> None:
    corrida = Corrida(
        id=f"env-{target}", objetivo=target, ref=ref, commit="", semilla=0,
        inicio=datetime.now(), estado="env",
    )  # fmt: skip
    instancia = cargar_objetivo(target).preparar(ref, corrida)
    typer.echo(f"web: {instancia.base_url}\napi: {instancia.api_url}\ncommit: {instancia.commit}")


@app.command()
def down(
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    ref: Annotated[str, typer.Option(help="Rama, tag o commit.")] = "main",
) -> None:
    # destruir solo usa el proyecto de compose; el resto de la instancia no importa.
    instancia = Instancia(base_url="", api_url="", proyecto_compose=f"dogfood-{target}", commit=ref)
    cargar_objetivo(target).destruir(instancia)
    typer.echo(f"proyecto {instancia.proyecto_compose} destruido")
