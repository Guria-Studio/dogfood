import asyncio
import json
import shutil
import sqlite3

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dogfood.cli import app as cli
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion, Escenario, Instancia
from dogfood.objetivos import cargar_objetivo
from dogfood.panel.app import crear_app_panel
from dogfood.personas.generador import generar
from dogfood.plan import armar_plan


def _escenarios():
    return cargar_objetivo("predicts").escenarios()


def test_misma_semilla_mismo_plan():
    escs = _escenarios()
    a = armar_plan("predicts", generar(6, 3), escs, 3)
    b = armar_plan("predicts", generar(6, 3), escs, 3)
    assert a == b
    assert len({c.id for c in a.casos}) == len(a.casos) == 6


def test_un_caso_por_asignacion_con_prioridad():
    escs = {e.id: e for e in _escenarios()}
    p = armar_plan("predicts", generar(10, 2), list(escs.values()), 2)
    assert len(p.casos) == 10
    for c in p.casos:
        e = escs[c.escenario_id]
        alta = bool({"registro", "subir", "analisis", "exportar"} & set(e.superficies))
        assert c.prioridad == ("alta" if alta else "media"), c.id
        assert c.id == f"{e.id}:{c.persona_id}"
        assert c.criterio_exito and c.objetivo and c.titulo
    prior = {c.escenario_id: c.prioridad for c in p.casos}
    assert prior.get("recompra-completa", "alta") == "alta"
    assert prior.get("login-fallido", "media") == "media"


def test_cli_imprime_y_guarda(tmp_path):
    r = CliRunner().invoke(
        cli, ["plan", "--target", "predicts", "--personas", "3", "--seed", "5", "--raiz", tmp_path]
    )
    assert r.exit_code == 0, r.output
    datos = json.loads((tmp_path / "plan-5.json").read_text())
    assert len(datos["casos"]) == 3
    assert datos["casos"][0]["titulo"] in r.output


class _Objetivo:
    nombre = "falso"

    def preparar(self, ref, corrida):
        return Instancia(base_url="http://x", api_url="http://x", proyecto_compose="p", commit="c")

    def destruir(self, instancia): ...

    def escenarios(self):
        return [
            Escenario(id=i, titulo=i, objetivo="o", criterio_exito="c", superficies=s)
            for i, s in (("subir", ["subir"]), ("mirar", ["universo"]))
        ]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


def test_plan_de_la_corrida_por_api(tmp_path, monkeypatch):
    async def ejecutar(persona, escenario, instancia, dataset, carpeta, *a, **kw):
        estado = "rendido" if escenario.id == "mirar" else "ok"
        return Ejecucion(
            id=carpeta.name, persona_id=persona.id, escenario_id=escenario.id, modelo="m",
            estado=estado, exito=True, motivo_juez="ok", duracion_s=4,
        )  # fmt: skip

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)
    monkeypatch.setattr("dogfood.corrida.contrato.resultado", lambda e: "aprobado")
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]})
    c = asyncio.run(
        correr(
            Opciones(
                raiz=tmp_path,
                cfg=cfg,
                objetivo_obj=_Objetivo(),
                llm=object(),
                semilla=1,
                personas=3,
                sin_publicar=True,
            )
        )
    )
    # una ejecución que nunca terminó (borrada de la base) vuelve a «pendiente»
    plan = json.loads((tmp_path / c.id / "plan.json").read_text())
    ultima = plan["casos"][-1]["ejecuciones"][0]
    con = sqlite3.connect(tmp_path / "dogfood.db")
    with con:
        con.execute("DELETE FROM ejecuciones WHERE id = ?", (ultima,))
    shutil.rmtree(tmp_path / c.id / "ejecuciones" / ultima)

    r = TestClient(crear_app_panel(tmp_path)).get(f"/api/corridas/{c.id}/plan")
    assert r.status_code == 200
    casos = r.json()
    assert len(casos) == 3
    por_id = {x["ejecucion_id"]: x for x in casos}
    assert None in por_id and por_id[None]["estado"] == "pendiente"
    terminados = [x for x in casos if x["ejecucion_id"]]
    for x in terminados:
        esperado = "rendido" if x["escenario_id"] == "mirar" else "exito"
        assert x["estado"] == esperado
        assert x["duracion_s"] == 4
        assert x["prioridad"] == ("alta" if x["escenario_id"] == "subir" else "media")

    # con la corrida abierta, una ejecución empezada sin terminar está «en curso»
    with con:
        con.execute("UPDATE corridas SET estado = 'en_curso' WHERE id = ?", (c.id,))
    (tmp_path / c.id / "ejecuciones" / ultima).mkdir()
    casos = TestClient(crear_app_panel(tmp_path)).get(f"/api/corridas/{c.id}/plan").json()
    assert [x["estado"] for x in casos if x["ejecucion_id"] == ultima] == ["en_curso"]

    assert TestClient(crear_app_panel(tmp_path)).get("/api/corridas/nada/plan").status_code == 404
