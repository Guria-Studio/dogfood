import asyncio
import sqlite3

import pytest
from typer.testing import CliRunner

from dogfood import deteccion
from dogfood.almacen import Almacen
from dogfood.comandos import runs
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import (
    Ejecucion,
    Escenario,
    Gravedad,
    Hallazgo,
    Instancia,
    TipoHallazgo,
)


def _esc(id):
    return Escenario(
        id=id,
        titulo=id,
        objetivo="o",
        criterio_exito="c",
        datos={"perfil": "farmacia", "clientes": 20},
    )


class FalsoObjetivo:
    nombre = "falso"

    def __init__(self, falla=False):
        self.falla = falla
        self.destruidos = []

    def preparar(self, ref, corrida):
        if self.falla:
            raise RuntimeError("no levanta")
        return Instancia(
            base_url="http://x", api_url="http://x", proyecto_compose="p", commit="abc"
        )

    def destruir(self, instancia):
        self.destruidos.append(instancia)

    def escenarios(self):
        return [_esc("a"), _esc("b")]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {"api": "log api"}


@pytest.fixture
def fake(monkeypatch):
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]})

    async def ejecutar(
        persona, escenario, instancia, dataset, carpeta, llm, juez, *, objetivo, contador
    ):
        contador.registrar("persona", "m", 10, 5, ejecucion_id=carpeta.name)
        contador.usos[-1].costo_usd = 0.25
        return Ejecucion(
            id=carpeta.name,
            persona_id=persona.id,
            escenario_id=escenario.id,
            modelo="m",
            estado="ok",
            exito=True,
        )

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)

    def opciones(tmp_path, objetivo=None, **kw):
        return Opciones(
            raiz=tmp_path,
            cfg=cfg,
            objetivo_obj=objetivo or FalsoObjetivo(),
            llm=object(),
            semilla=7,
            **kw,
        )

    return opciones


def _estado(tmp_path, corrida_id):
    con = sqlite3.connect(tmp_path / "dogfood.db")
    return con.execute(
        "SELECT estado, costo_usd FROM corridas WHERE id=?", (corrida_id,)
    ).fetchone()


def test_dos_personas_dos_ejecuciones_estado_ok(tmp_path, fake):
    obj = FalsoObjetivo()
    c = asyncio.run(correr(fake(tmp_path, obj, personas=2)))
    assert c.estado == "ok"
    con = sqlite3.connect(tmp_path / "dogfood.db")
    assert con.execute("SELECT COUNT(*) FROM ejecuciones").fetchone()[0] == 2
    assert _estado(tmp_path, c.id)[0] == "ok"
    assert len(obj.destruidos) == 1
    assert (tmp_path / c.id / "logs" / "api.log").read_text() == "log api"


def test_mantener_entorno_no_destruye(tmp_path, fake):
    obj = FalsoObjetivo()
    asyncio.run(correr(fake(tmp_path, obj, mantener_entorno=True)))
    assert obj.destruidos == []


def test_preparar_falla_error_y_destruye(tmp_path, fake):
    obj = FalsoObjetivo(falla=True)
    c = asyncio.run(correr(fake(tmp_path, obj)))
    assert c.estado == "error"
    assert _estado(tmp_path, c.id)[0] == "error"
    assert len(obj.destruidos) == 1


def test_detector_falso_aparece_en_runs(tmp_path, fake, monkeypatch):
    def detector(ctx):
        return [
            Hallazgo(
                tipo=TipoHallazgo.tecnico,
                gravedad=Gravedad.alta,
                pantalla="mapeo",
                titulo="t",
                descripcion="d",
                semilla=ctx.corrida.semilla,
                commit=ctx.instancia.commit,
                huella="h",
            )
        ]

    monkeypatch.setattr(deteccion, "DETECTORES", [detector])
    asyncio.run(correr(fake(tmp_path, personas=2)))
    r = CliRunner().invoke(runs.app, ["--raiz", str(tmp_path)])
    assert "hallazgos=1" in r.output
    assert "a 1/1" in r.output or "b 1/1" in r.output


def test_costo_es_suma_de_uso(tmp_path, fake):
    c = asyncio.run(correr(fake(tmp_path, personas=2)))
    assert _estado(tmp_path, c.id)[1] == pytest.approx(0.5)
    assert Almacen(tmp_path).listar_corridas()[0].costo_usd == pytest.approx(0.5)


def test_misma_semilla_misma_asignacion(tmp_path, fake):
    def asignacion(sub):
        raiz = tmp_path / sub
        c = asyncio.run(correr(fake(raiz, personas=2)))
        con = sqlite3.connect(raiz / "dogfood.db")
        return con.execute(
            "SELECT persona_id, escenario_id FROM ejecuciones WHERE corrida_id=? ORDER BY id",
            (c.id,),
        ).fetchall()

    assert asignacion("uno") == asignacion("dos")
