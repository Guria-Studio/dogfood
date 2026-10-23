"""Replay con un Objetivo falso, un historial falso y un rerun falso."""

import json
from datetime import datetime

import pytest

from dogfood.agente.replay import ErrorRerun, replay
from dogfood.almacen import Almacen
from dogfood.dominio import (
    Corrida,
    Ejecucion,
    Gravedad,
    Hallazgo,
    Idioma,
    Instancia,
    Intencion,
    Paso,
    Persona,
    TipoHallazgo,
)

AHORA = datetime(2026, 1, 1).astimezone()


def _pasos():
    return [
        Paso(n=n, url=f"http://x/p{n}", pantalla=f"p{n}", accion="{}", ts=AHORA)
        for n in range(1, 11)
    ]


@pytest.fixture
def almacen(tmp_path):
    a = Almacen(tmp_path / "runs")
    a.nueva_corrida(
        Corrida(
            id="c1", objetivo="fake", ref="main", commit="abc", semilla=1, inicio=AHORA, estado="ok"
        )
    )
    a.guardar_personas(
        "c1",
        [
            Persona(
                id="p1", nombre="Ana", email="a@x", contrasena="s", empresa="E", rubro="r",
                idioma=Idioma.es, destreza=3, paciencia=3, intencion=Intencion.explorar, semilla=1,
            )
        ],
    )  # fmt: skip
    hist = tmp_path / "historial.json"
    hist.write_text(json.dumps({"history": []}))
    a.guardar_ejecucion(
        "c1",
        Ejecucion(
            id="e1", persona_id="p1", escenario_id="s", modelo="m", estado="ok",
            pasos=_pasos(), ruta_historial=hist,
        ),
    )  # fmt: skip
    a.guardar_hallazgos(
        "c1",
        [
            Hallazgo(
                tipo=TipoHallazgo.tecnico, gravedad=Gravedad.alta, pantalla="p8", titulo="t",
                descripcion="d", huella="H1", ejecucion_id="e1", semilla=1, commit="abc",
            )
        ],
    )  # fmt: skip
    return a


class Fake:
    nombre = "fake"

    def __init__(self):
        self.destruidas = 0

    def preparar(self, ref, corrida):
        return Instancia(
            base_url="http://x", api_url="http://x", proyecto_compose="p", commit="new"
        )

    def destruir(self, instancia):
        self.destruidas += 1

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


def _detector(monkeypatch, huellas):
    def det(ctx):
        return [
            Hallazgo(
                tipo=TipoHallazgo.tecnico, gravedad=Gravedad.alta, pantalla="p8", titulo="t",
                descripcion="d", huella=h, semilla=1, commit="new",
            )
            for h in huellas
        ]  # fmt: skip

    monkeypatch.setattr("dogfood.agente.replay.tecnicos.detectar", det)


async def _ok(*a):
    return Ejecucion(id="e1", persona_id="p1", escenario_id="s", modelo="m", estado="ok")


async def _resultado(almacen, rerun, obj=None):
    return (
        await replay(
            "c1-H1",
            almacen=almacen,
            objetivo=obj or Fake(),
            rerun=rerun,
            cliente_api=lambda p: None,
        )
    )[0][1]


async def test_reproduce(almacen, monkeypatch):
    _detector(monkeypatch, ["H1"])
    assert await _resultado(almacen, _ok) == "reproduce"


async def test_no_reproduce(almacen, monkeypatch):
    _detector(monkeypatch, [])
    assert await _resultado(almacen, _ok) == "no_reproduce"


async def test_cambio_ui_falla_en_paso_3_hallazgo_en_8(almacen, monkeypatch):
    _detector(monkeypatch, ["H1"])

    async def falla(*a):
        raise ErrorRerun(3)

    assert await _resultado(almacen, falla) == "no_reproducible_por_cambio_ui"


async def test_por_ejecucion_id(almacen, monkeypatch):
    _detector(monkeypatch, ["H1"])
    r = await replay("e1", almacen=almacen, objetivo=Fake(), rerun=_ok, cliente_api=lambda p: None)
    assert [x[1] for x in r] == ["reproduce"]


@pytest.mark.parametrize("exc", [ErrorRerun(3), RuntimeError("boom")])
async def test_siempre_destruye(almacen, monkeypatch, exc):
    _detector(monkeypatch, [])
    obj = Fake()

    async def falla(*a):
        raise exc

    try:
        await _resultado(almacen, falla, obj)
    except RuntimeError:
        pass
    assert obj.destruidas == 1
