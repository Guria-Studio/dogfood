from pathlib import Path
from typing import Annotated

import typer

from dogfood.personas.generador import generar

app = typer.Typer(help="Genera personas deterministas.")


def _parsear_idiomas(texto: str | None) -> dict[str, float] | None:
    if not texto:
        return None
    try:
        return {k: float(v) for k, v in (p.split(":") for p in texto.split(","))}
    except ValueError as e:
        raise typer.BadParameter("usa el formato pt-BR:0.5,es:0.5") from e


@app.callback(invoke_without_command=True)
def personas(
    n: Annotated[int, typer.Option(help="Cantidad de personas.")],
    seed: Annotated[int | None, typer.Option(help="Semilla.")] = None,
    idiomas: Annotated[str | None, typer.Option(help="Ej. pt-BR:0.5,es:0.5.")] = None,
    salida: Annotated[Path | None, typer.Option(help="Guarda las personas en JSON.")] = None,
) -> None:
    try:
        lista = generar(n, 0 if seed is None else seed, _parsear_idiomas(idiomas))
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    for p in lista:
        typer.echo(
            f"{p.id}  {p.idioma.value:5}  {p.nombre:28}  {p.rubro:11}  d{p.destreza} p{p.paciencia}"
            f"  {p.intencion.value:17}  {p.email}"
        )
    if salida:
        import json

        salida.write_text(
            json.dumps([p.model_dump(mode="json") for p in lista], ensure_ascii=False, indent=2)
        )
        typer.echo(f"guardado en {salida}")
