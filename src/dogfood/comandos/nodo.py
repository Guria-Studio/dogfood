import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated

import pydantic
import typer

from dogfood.deterministico.corredor import _runner_real
from dogfood.nodos.protocolo import ResultadoTrabajo, Trabajo
from dogfood.nodos.runner import ejecutar, estado_nodo

app = typer.Typer(help="Nodo iOS (corre en el Mac): estado y ejecución de trabajos.")

DirTrabajo = Annotated[Path, typer.Option("--dir-trabajo", help="Carpeta de trabajo del nodo.")]
_DIR = Path("~/dogfood-nodo")


@app.command()
def estado(
    json_: Annotated[bool, typer.Option("--json")] = False, dir_trabajo: DirTrabajo = _DIR
) -> None:
    """Xcode, Flutter, Patrol, Appium y dispositivos físicos."""
    dir_trabajo.expanduser().mkdir(parents=True, exist_ok=True)
    e = asyncio.run(estado_nodo(_runner_real))
    if json_:
        typer.echo(e.model_dump_json())
        return
    typer.echo(f"Xcode: {e.xcode or '—'}  Flutter: {e.flutter or '—'}  Patrol: {e.patrol or '—'}")
    typer.echo(f"Appium: {'sí' if e.appium else 'no'}")
    for d in e.dispositivos:
        typer.echo(f"{d['udid']}\t{d['nombre']}\t{d['os']}")


@app.command("ejecutar")
def ejecutar_cmd(dir_trabajo: DirTrabajo = _DIR) -> None:
    """Lee un `Trabajo` (JSON) de stdin; la última línea de stdout es el `ResultadoTrabajo`."""
    texto = sys.stdin.read()
    try:
        trabajo = Trabajo.model_validate_json(texto)
    except pydantic.ValidationError as e:
        try:
            raw = json.loads(texto)
            id_ = str(raw.get("id", "desconocido")) if isinstance(raw, dict) else "desconocido"
        except ValueError:
            id_ = "desconocido"
        r = ResultadoTrabajo(id=id_, estado="error", mensaje=f"Trabajo inválido: {e}")
    else:
        typer.echo(f"trabajo {trabajo.id} ({trabajo.tipo})", err=True)
        r = asyncio.run(ejecutar(trabajo, dir_trabajo.expanduser()))
        typer.echo(f"{r.estado}: {r.mensaje}", err=True)
    typer.echo(r.model_dump_json())
