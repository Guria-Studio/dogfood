import asyncio
import sqlite3

import pytest

from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion, Escenario, Instancia


def _esc(id, carril="normal"):
    return Escenario(
        id=id,
        titulo=id,
        objetivo="o",
        criterio_exito="c",
        carril=carril,
        datos={"perfil": "farmacia", "clientes": 20},
    )


class Objetivo:
    nombre = "falso"

    def __init__(self, escs):
        self.escs = escs

    def preparar(self, ref, corrida):
        return Instancia(base_url="http://x", api_url="http://x", proyecto_compose="p", commit="c")

    def destruir(self, instancia):
        pass

    def escenarios(self):
        return self.escs

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


@pytest.fixture
def traza(monkeypatch):
    t = {"activas": 0, "max": 0, "eventos": [], "datasets": []}

    async def ejecutar(
        persona, escenario, instancia, dataset, carpeta, llm, juez, *, objetivo, contador
    ):
        t["activas"] += 1
        t["max"] = max(t["max"], t["activas"])
        t["eventos"].append(("ini", escenario.carril, t["activas"]))
        t["datasets"].append(dataset)
        await asyncio.sleep(0.01)
        t["eventos"].append(("fin", escenario.carril, t["activas"]))
        t["activas"] -= 1
        return Ejecucion(
            id=carpeta.name,
            persona_id=persona.id,
            escenario_id=escenario.id,
            modelo="m",
            estado="ok",
            exito=True,
        )

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)
    return t


def _op(tmp_path, escs, **kw):
    return Opciones(
        raiz=tmp_path,
        cfg=Config(roles={"persona": ["m"], "juez": ["m"]}),
        objetivo_obj=Objetivo(escs),
        llm=object(),
        semilla=7,
        **kw,
    )


def test_nunca_mas_de_n_a_la_vez(tmp_path, traza):
    c = asyncio.run(correr(_op(tmp_path, [_esc("a"), _esc("b")], personas=10, concurrencia=3)))
    assert c.estado == "ok"
    assert traza["max"] == 3


def test_login_fallido_al_final_y_de_a_una(tmp_path, traza):
    escs = [_esc("a"), _esc("b"), _esc("l", "login_fallido")]
    asyncio.run(correr(_op(tmp_path, escs, personas=9, concurrencia=4)))
    ev = traza["eventos"]
    primero = next(i for i, e in enumerate(ev) if e[1] == "login_fallido")
    assert all(e[1] == "login_fallido" for e in ev[primero:])
    assert sum(1 for e in ev if e[1] == "login_fallido") == 2 * 3
    assert all(e[2] == 1 for e in ev[primero:])


def test_memoria_baja_aborta_con_error(tmp_path, traza):
    ahora = [0.0]

    async def dormir(s):
        ahora[0] += s

    c = asyncio.run(
        correr(
            _op(
                tmp_path, [_esc("a")], memoria_gb=lambda: 0.1, reloj=lambda: ahora[0], dormir=dormir
            )
        )
    )
    assert c.estado == "error"
    assert c.parametros["motivo"] == "memoria"
    assert traza["eventos"] == []


def test_120_personas_120_ejecuciones_emails_distintos(tmp_path, traza):
    asyncio.run(correr(_op(tmp_path, [_esc("a"), _esc("b")], personas=120, concurrencia=20)))
    con = sqlite3.connect(tmp_path / "dogfood.db")
    assert con.execute("SELECT COUNT(*) FROM ejecuciones").fetchone()[0] == 120
    assert len(traza["datasets"]) == 120
    n = con.execute(
        "SELECT COUNT(DISTINCT json_extract(json, '$.email')) FROM personas"
    ).fetchone()[0]
    assert n == 120


def test_mismo_perfil_comparte_dataset(tmp_path, traza):
    asyncio.run(correr(_op(tmp_path, [_esc("a"), _esc("b")], personas=2)))
    d1, d2 = traza["datasets"]
    assert d1 is not None and d1.id == d2.id and d1.ruta_csv == d2.ruta_csv


@pytest.fixture(autouse=True)
def _sin_cierre(monkeypatch):
    # El cierre (docker, gh, Slack, LLM) tiene sus tests en test_corrida_cierre.py.
    async def generar(*a, destino, **k):
        return destino / "reporte.md", destino / "reporte.html"

    monkeypatch.setattr("dogfood.corrida.opinion.contar_uso_ia", lambda i: None)
    monkeypatch.setattr("dogfood.corrida.issues.publicar", lambda *a, **k: [])
    monkeypatch.setattr("dogfood.corrida.opinion.generar", generar)
    monkeypatch.setattr("dogfood.corrida.slack.avisar", lambda *a, **k: True)
