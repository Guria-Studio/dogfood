import asyncio
from typing import Annotated

import typer

from dogfood.corrida import Opciones, correr

app = typer.Typer(help="Corre usuarios agénticos contra el objetivo.")


@app.callback(invoke_without_command=True)
def run(
    target: Annotated[str, typer.Option(help="Objetivo.")] = "predicts",
    personas: Annotated[int | None, typer.Option(help="Cantidad de personas.")] = None,
    escenarios: Annotated[str | None, typer.Option(help="Ids separados por coma.")] = None,
    seed: Annotated[int | None, typer.Option(help="Semilla.")] = None,
    ref: Annotated[str, typer.Option(help="Rama, tag o commit.")] = "main",
    concurrencia: Annotated[int, typer.Option(help="Ejecuciones en paralelo.")] = 5,
    repeat: Annotated[int, typer.Option(help="Repeticiones.")] = 1,
    sin_publicar: Annotated[bool, typer.Option("--sin-publicar", help="No crea issues.")] = False,
    tope_usd: Annotated[float | None, typer.Option("--tope-usd", help="Tope de costo.")] = None,
    driver: Annotated[
        str | None, typer.Option(help="Driver: web o android (pisa el del escenario).")
    ] = None,
    motor: Annotated[str | None, typer.Option(help="Motor: browser_use o bucle.")] = None,
    vista: Annotated[
        bool, typer.Option("--vista", help="Vista en vivo de las ejecuciones.")
    ] = False,
    vista_puerto: Annotated[
        int | None, typer.Option("--vista-puerto", help="Puerto de la vista (por defecto, config).")
    ] = None,
    mantener_entorno: Annotated[
        bool, typer.Option("--mantener-entorno", help="No destruye el entorno al terminar.")
    ] = False,
) -> None:
    if driver not in (None, "web", "android"):
        raise typer.BadParameter("web o android", param_hint="--driver")
    if motor not in (None, "browser_use", "bucle"):
        raise typer.BadParameter("browser_use o bucle", param_hint="--motor")
    corrida = asyncio.run(
        correr(
            Opciones(
                objetivo=target,
                ref=ref,
                personas=personas or 1,
                escenarios=[e.strip() for e in escenarios.split(",")] if escenarios else None,
                semilla=seed,
                repeat=repeat,
                mantener_entorno=mantener_entorno,
                sin_publicar=sin_publicar,
                tope_usd=tope_usd,
                driver=driver,
                motor=motor,
                vista=vista,
                vista_puerto=vista_puerto,
            )
        )
    )
    typer.echo(f"{corrida.id}: {corrida.estado}")
    if corrida.estado not in ("ok", "ok_con_avisos"):
        raise typer.Exit(1)
