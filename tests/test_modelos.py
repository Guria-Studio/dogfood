import asyncio
from collections import Counter
from datetime import datetime
from pathlib import Path

from dogfood.config import Config
from dogfood.dominio import (
    Corrida,
    Ejecucion,
    Gravedad,
    Hallazgo,
    TipoHallazgo,
    UsoLlm,
)
from dogfood.llm import indice_modelo, modelos_para
from dogfood.reporte import modelos
from dogfood.reporte.opinion import Agrupacion, Redaccion, generar

MODELOS = ["a", "b", "c"]


def cfg(modo="rotar"):
    return Config(roles={"persona": MODELOS, "juez": ["j1", "j2"]}, asignacion_modelos=modo)


def reparto(semilla, modo="rotar"):
    c = cfg(modo)
    return [
        modelos_para("persona", c)[indice_modelo("persona", n, semilla, c)] for n in range(1, 10)
    ]


def test_rotar_reparte_parejo():
    assert Counter(reparto(7)) == {"a": 3, "b": 3, "c": 3}


def test_misma_semilla_mismo_reparto():
    assert reparto(42) == reparto(42)


def test_primero_y_juez_usan_siempre_el_mismo():
    c = cfg()
    assert {indice_modelo("juez", n, 5, c) for n in range(1, 10)} == {0}
    assert set(reparto(5, "primero")) == {"a"}


def ejec(i, modelo, exito, fric=0):
    return Ejecucion(
        id=f"e{i}", persona_id="p", escenario_id="s", modelo=modelo,
        estado="ok" if exito else "fallo", exito=exito,
        fricciones=[{"texto": "t", "severidad": Gravedad.baja, "pantalla": "x"}] * fric,
    )  # fmt: skip


def hall(huella, ej):
    return Hallazgo(
        tipo=TipoHallazgo.friccion, gravedad=Gravedad.alta, pantalla="x", titulo=huella,
        descripcion="d", huella=huella, ejecucion_id=ej, semilla=1, commit="c",
    )  # fmt: skip


EJECS = [ejec(1, "a", True, 2), ejec(2, "a", False), ejec(3, "b", True)]
HALLS = [hall("h1", "e1"), hall("h2", "e3"), hall("h1", "e3")]
USOS = [UsoLlm(rol="persona", modelo="a", tokens_in=100, tokens_out=100, costo_usd=0.5)]


def test_tabla_exito_y_unicos():
    t = {f["modelo"]: f for f in modelos.tabla(EJECS, HALLS, USOS)}
    assert t["a"]["exito_pct"] == 50 and t["b"]["exito_pct"] == 100
    assert t["a"]["hallazgos_unicos"] == 0  # h1 lo vieron a y b
    assert t["b"]["hallazgos_unicos"] == 1  # h2 solo b
    assert t["a"]["fricciones_por_ejecucion"] == 1.0
    assert t["a"]["tokens_por_ejecucion"] == 100 and t["a"]["costo_por_ejecucion_usd"] == 0.25


def test_reporte_incluye_seccion_modelos(tmp_path):
    async def falso(rol, prompt, esquema, **kw):
        return Agrupacion(grupos=[]) if rol == "dedupe" else Redaccion()

    corrida = Corrida(
        id="c1", objetivo="predicts", ref="main", commit="c", semilla=1,
        inicio=datetime.now().astimezone(), estado="ok",
    )  # fmt: skip
    md, html = asyncio.run(
        generar(corrida, EJECS, HALLS, [], destino=tmp_path, usos=USOS, completar=falso)
    )
    assert "Modelos" in Path(md).read_text() and "Modelos" in Path(html).read_text()
