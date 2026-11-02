"""`dogfood ci`: corre los casos de prioridad alta de un proyecto y sale con 1 si alguno falla."""

import asyncio
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import Annotated

import typer

from dogfood import actividad, proyectos
from dogfood.almacen import Almacen
from dogfood.corrida import Opciones, correr
from dogfood.diff import _describir
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


def _correr_diff(target: str, base: str, nueva: str, raiz: Path) -> dict | None:
    """Corre `dogfood diff` y devuelve el diff nuevo (None si el comando falló)."""
    r = subprocess.run(
        [sys.executable, "-m", "dogfood", "diff", "--target", target, "--base", base,
         "--nueva", nueva, "--runs", str(raiz)],
        check=False,
    )  # fmt: skip
    if r.returncode:
        return None
    ultimo = Almacen(raiz).listar_diffs(target)
    return Almacen(raiz).diff(ultimo[0]["id"]) if ultimo else None


def _altos(d: dict) -> list[str]:
    return [
        f"- **{c['tc']}** paso `{p['step_id']}`: {_describir(x)}"
        for c in d["casos"]
        for p in c["pasos"]
        for x in p["cambios"]
        if x["gravedad"] == "alta"
    ]


def _seccion(d: dict, altos: list[str]) -> str:
    panel = os.environ.get("DOGFOOD_PANEL_URL", "").rstrip("/")
    return "\n".join(
        ["", "### Cambios de comportamiento", "", *altos, "",
         f"[Ver el diff en el panel]({panel}/proyectos/{d['proyecto']}/diffs/{d['id']})"]
    )  # fmt: skip


@app.callback(invoke_without_command=True)
def ci(
    target: Annotated[str, typer.Option(help="Slug del proyecto u objetivo.")],
    ref: Annotated[str, typer.Option(help="Commit o rama a probar.")] = "main",
    raiz: Annotated[Path, typer.Option(help="Carpeta de corridas.")] = Path("runs"),
    pr: Annotated[int | None, typer.Option(help="Número del PR donde comentar.")] = None,
    base: Annotated[str, typer.Option(help="Rama base del PR, para el diff.")] = "master",
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
    cuerpo = ""
    if proyecto and proyecto.diff_activo:
        d = _correr_diff(target, base, ref, raiz)
        if d is None:
            typer.echo("No se pudo correr el diff.", err=True)
        elif altos := _altos(d):
            cuerpo = _seccion(d, altos)
            fallo = fallo or proyecto.diff_bloquea
    resumen = f"{'❌' if fallo else '✅'} dogfood: {total - malas}/{total} casos de prioridad alta pasaron ({ref[:7]})"
    typer.echo(resumen + cuerpo)
    if proyecto:
        actividad.registrar(
            raiz, proyecto.slug, "corrida_terminada", f"{corrida.id}: {resumen}", "ci"
        )
        if pr is not None and proyecto.notificaciones.comentar_pr:  # solo si el proyecto lo activó
            try:
                subprocess.run(
                    ["gh", "pr", "comment", str(pr), "--body", resumen + cuerpo], check=True
                )
            except (OSError, subprocess.CalledProcessError):
                typer.echo("No se pudo comentar en el PR.", err=True)
    if fallo:
        raise typer.Exit(1)
