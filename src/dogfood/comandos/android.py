from typing import Annotated

import typer

from dogfood.config import Config
from dogfood.drivers import adb_red
from dogfood.drivers.android import AdbError

app = typer.Typer(help="ADB sobre Tailscale: emparejar, conectar y ver el estado.")

# Los tests lo reemplazan con un runner falso.
_runner = adb_red.runner_real


def _fallo(e: Exception) -> typer.Exit:
    typer.echo(f"Error: {e}", err=True)
    return typer.Exit(1)


@app.command()
def emparejar(host_puerto: Annotated[str, typer.Argument(help="ip:puerto de emparejado.")]) -> None:
    """Empareja el celular. El código de 6 dígitos se escribe en el prompt de adb."""
    try:
        adb_red.emparejar(host_puerto, lambda *a, **k: _runner(*a, **k))
    except AdbError as e:
        raise _fallo(e) from None


@app.command()
def conectar(host_puerto: Annotated[str | None, typer.Argument(help="ip:puerto.")] = None) -> None:
    """Conecta (por defecto, driver.host_puerto de dogfood.yaml)."""
    destino = host_puerto or Config.cargar().driver.host_puerto
    if not destino:
        raise _fallo(AdbError("indica ip:puerto o define driver.host_puerto en dogfood.yaml"))
    try:
        d = adb_red.conectar(destino, lambda *a, **k: _runner(*a, **k))
    except AdbError as e:
        raise _fallo(e) from None
    typer.echo(f"✅ {d.serial}: {d.modelo or '?'} (Android {d.android or '?'})")


@app.command()
def estado() -> None:
    """Dispositivos ADB y estado del servidor local."""
    try:
        lista = adb_red.listar(lambda *a, **k: _runner(*a, **k))
    except AdbError as e:
        raise _fallo(e) from None
    if not lista:
        typer.echo("Sin dispositivos.")
    for d in lista:
        typer.echo(
            f"{'✅' if d.permitido else '⛔'} {d.serial}\t{d.estado}\t{d.modelo}"
            + (f"\t{d.motivo}" if d.motivo else "")
        )
    ok, aviso = adb_red.servidor_local_ok()
    typer.echo(f"{'✅' if ok else '⛔'} {aviso}")


@app.command()
def desconectar(
    host_puerto: Annotated[str | None, typer.Argument(help="ip:puerto.")] = None,
) -> None:
    """Desconecta un destino (o todos)."""
    adb_red.desconectar(host_puerto, lambda *a, **k: _runner(*a, **k))
    typer.echo("Desconectado.")
