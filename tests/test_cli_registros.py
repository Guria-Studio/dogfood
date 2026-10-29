import re
from datetime import datetime

import pytest
from typer.testing import CliRunner

from dogfood import deteccion
from dogfood.cli import app
from dogfood.dominio import ContextoDeteccion, Corrida, Gravedad, Hallazgo, Instancia, TipoHallazgo
from dogfood.objetivos import cargar_objetivo

runner = CliRunner()
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _salida(args: list[str]) -> str:
    # Rich colorea y parte las opciones con códigos ANSI cuando el entorno fuerza color
    # (el runner de CI lo hace); se comparan textos planos.
    return _ANSI.sub("", runner.invoke(app, args, env={"NO_COLOR": "1", "COLUMNS": "200"}).output)


def test_help_lista_comandos() -> None:
    out = _salida(["--help"])
    for c in ("env", "datos", "personas", "run", "runs", "replay"):
        assert c in out


def test_run_help() -> None:
    out = _salida(["run", "--help"])
    assert "--seed" in out and "--concurrencia" in out


def test_stub_sale_con_2() -> None:
    # replay ya está implementado (F4.3.T1); se prueba el stub directamente.
    import typer

    from dogfood.comandos._stub import no_implementado

    stub = typer.Typer()
    stub.command()(no_implementado)
    r = runner.invoke(stub, [])
    assert r.exit_code == 2 and "no implementado todavía" in r.output


def test_objetivo_desconocido() -> None:
    with pytest.raises(ValueError, match="predicts"):
        cargar_objetivo("x")


def _hallazgo(titulo: str) -> Hallazgo:
    return Hallazgo(
        tipo=TipoHallazgo.logica,
        gravedad=Gravedad.alta,
        pantalla="p",
        titulo=titulo,
        descripcion="",
        semilla=1,
        commit="c",
    )


def test_detector_que_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    def malo(ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        deteccion, "DETECTORES", [lambda c: [_hallazgo("a")], malo, lambda c: [_hallazgo("b")]]
    )
    ctx = ContextoDeteccion(
        corrida=Corrida(
            id="r",
            objetivo="predicts",
            ref="main",
            commit="c",
            semilla=1,
            inicio=datetime.now(),
            estado="x",
        ),
        instancia=Instancia(base_url="", api_url="", proyecto_compose="", commit="c"),
        ejecuciones=[],
        datasets={},
        cliente_api=lambda p: None,
        logs={},
    )
    res = deteccion.ejecutar_detectores(ctx)
    assert [h.titulo for h in res if h.gravedad != Gravedad.baja] == ["a", "b"]
    baja = [h for h in res if h.gravedad == Gravedad.baja]
    assert len(baja) == 1 and "falló" in baja[0].titulo and baja[0].tipo == TipoHallazgo.tecnico
