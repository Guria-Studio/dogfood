"""`dogfood ci`: corre los casos de prioridad alta de un proyecto y sale con 1 si alguno falla."""

import asyncio
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from typing import Annotated

import typer

from dogfood import actividad, proyectos
from dogfood.corrida import Opciones, correr
from dogfood.objetivos import cargar_objetivo
from dogfood.plan import prioridad

app = typer.Typer(help="Corre los casos de prioridad alta (para CI); sale con 1 si alguno falla.")


def _fallidas(raiz: Path, corrida_id: str) -> tuple[int, int]:
    with closing(sqlite3.connect(raiz / "dogfood.db")) as con:
        total, ok = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(COALESCE(resultado = 'aprobado', exito = 1)), 0)"
            " FROM ejecuciones WHERE corrida_id = ?",
            (corrida_id,),
        ).fetchone()
    return total - ok, total


@app.callback(invoke_without_command=True)
def ci(
    target: Annotated[str, typer.Option(help="Slug del proyecto u objetivo.")],
    ref: Annotated[str, typer.Option(help="Commit o rama a probar.")] = "main",
    raiz: Annotated[Path, typer.Option(help="Carpeta de corridas.")] = Path("runs"),
    pr: Annotated[int | None, typer.Option(help="Número del PR donde comentar.")] = None,
) -> None:
    proyecto = proyectos.obtener(target, raiz)
    objetivo = cargar_objetivo(proyecto.objetivo if proyecto else target)
    ids = [e.id for e in objetivo.escenarios() if prioridad(e) == "alta"]
    if not ids:
        typer.echo("No hay casos de prioridad alta.")
        return
    corrida = asyncio.run(correr(Opciones(objetivo=target, ref=ref, escenarios=ids, raiz=raiz)))
    malas, total = _fallidas(raiz, corrida.id)
    fallo = malas > 0 or corrida.estado not in ("ok", "ok_con_avisos")
    resumen = f"{'❌' if fallo else '✅'} dogfood: {total - malas}/{total} casos de prioridad alta pasaron ({ref[:7]})"
    typer.echo(resumen)
    if proyecto:
        actividad.registrar(
            raiz, proyecto.slug, "corrida_terminada", f"{corrida.id}: {resumen}", "ci"
        )
        if pr is not None and proyecto.notificaciones.comentar_pr:  # solo si el proyecto lo activó
            try:
                subprocess.run(["gh", "pr", "comment", str(pr), "--body", resumen], check=True)
            except (OSError, subprocess.CalledProcessError):
                typer.echo("No se pudo comentar en el PR.", err=True)
    if fallo:
        raise typer.Exit(1)
