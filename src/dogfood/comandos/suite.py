"""`dogfood suite run <id>`: corre una suite (una corrida por proyecto); lo invoca el timer."""

import asyncio
from pathlib import Path
from typing import Annotated

import httpx
import typer

from dogfood import suites
from dogfood.corrida import Opciones, correr
from dogfood.panel.api_proyectos import _webhook

app = typer.Typer(help="Suites de casos de uno o varios proyectos.")
TEXTO = {"paso": "Pasó", "advertencia": "Advertencia", "fallo": "Falló", "bloqueado": "Bloqueado"}


@app.callback()
def _grupo() -> None:
    pass


@app.command("run")
def run(
    suite_id: Annotated[int, typer.Argument(help="Id de la suite.")],
    raiz: Annotated[Path, typer.Option("--runs", help="Carpeta de corridas.")] = Path("runs"),
    slack: Annotated[bool, typer.Option(help="Avisa a Slack al terminar.")] = False,
) -> None:
    s = suites.obtener(raiz, suite_id)
    if s is None:
        typer.echo(f"La suite {suite_id} no existe.", err=True)
        raise typer.Exit(2)
    plan = suites.planear(raiz, s)
    suites.registrar_lanzadas(raiz, suite_id, plan)
    for g in plan:
        asyncio.run(
            correr(
                Opciones(
                    objetivo=g["objetivo"],
                    escenarios=g["escenarios"],
                    semilla=g["semilla"],
                    raiz=raiz,
                    sin_publicar=True,
                )
            )
        )
    estado, _ = suites.estado_ultima(raiz, suite_id)
    resumen = f"dogfood: la suite «{s['nombre']}» terminó: {TEXTO.get(estado or '', estado)}"
    typer.echo(resumen)
    if slack:
        for c in s["casos"]:
            if url := _webhook(c["proyecto"]):
                try:
                    httpx.post(url, json={"text": resumen}).raise_for_status()
                except httpx.HTTPError:
                    typer.echo("No se pudo avisar a Slack.", err=True)
                break
    if estado in ("fallo", "bloqueado"):
        raise typer.Exit(1)
