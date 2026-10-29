import asyncio

import pytest

from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion, Escenario, Instancia
from dogfood.reporte.opinion import UsoIA


def _esc(id):
    return Escenario(id=id, titulo=id, objetivo="o", criterio_exito="c")


class Objetivo:
    nombre = "falso"

    def __init__(self, llamadas):
        self.llamadas = llamadas

    def preparar(self, ref, corrida):
        return Instancia(base_url="http://x", api_url="http://x", proyecto_compose="p", commit="c")

    def destruir(self, instancia):
        self.llamadas.append("destruir")

    def escenarios(self):
        return [_esc("a")]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


@pytest.fixture
def cierre(monkeypatch):
    ll = []
    kw = {}

    async def ejecutar(
        persona, escenario, instancia, dataset, carpeta, llm, juez, *, objetivo, contador
    ):
        contador.registrar("persona", "m", 1_000_000, 0)  # 2 USD con el precio de _op
        return Ejecucion(
            id=carpeta.name,
            persona_id=persona.id,
            escenario_id=escenario.id,
            modelo="m",
            estado="ok",
            exito=True,
        )

    def contar(instancia):
        ll.append("contar")
        return UsoIA()

    def publicar(hallazgos, corrida, config, publicar=True, **_):
        ll.append("publicar")
        kw["publicar"] = publicar
        return []

    async def generar(corrida, ejecuciones, hallazgos, personas, *, destino, **_):
        ll.append("opinion")
        md = destino / "reporte.md"
        md.write_text("# reporte")
        return md, destino / "reporte.html"

    def avisar(corrida, resumen, config, **_):
        ll.append("slack")
        return True

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)
    monkeypatch.setattr("dogfood.corrida.opinion.contar_uso_ia", contar)
    monkeypatch.setattr("dogfood.corrida.issues.publicar", publicar)
    monkeypatch.setattr("dogfood.corrida.opinion.generar", generar)
    monkeypatch.setattr("dogfood.corrida.slack.avisar", avisar)
    return ll, kw


def _op(tmp_path, cierre, **kw):
    cfg = Config(
        roles={"persona": ["m"], "juez": ["m"]},
        precios_usd_por_millon={"m": {"entrada": 0.02, "salida": 0}},
    )
    return Opciones(
        raiz=tmp_path,
        cfg=cfg,
        objetivo_obj=Objetivo(cierre[0]),
        llm=object(),
        semilla=7,
        **kw,
    )


def test_orden_contar_publicar_opinion_slack_destruir(tmp_path, cierre):
    c = asyncio.run(correr(_op(tmp_path, cierre)))
    assert c.estado == "ok"
    assert cierre[0] == ["contar", "publicar", "opinion", "slack", "destruir"]


def test_sin_publicar_pasa_publicar_false(tmp_path, cierre):
    asyncio.run(correr(_op(tmp_path, cierre, sin_publicar=True)))
    assert cierre[1]["publicar"] is False


def test_slack_falla_ok_con_avisos_y_reporte(tmp_path, cierre, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("webhook")

    monkeypatch.setattr("dogfood.corrida.slack.avisar", roto)
    c = asyncio.run(correr(_op(tmp_path, cierre)))
    assert c.estado == "ok_con_avisos"
    assert (tmp_path / c.id / "reporte.md").exists()


def test_tope_usd_corta_y_genera_reporte(tmp_path, cierre):
    c = asyncio.run(correr(_op(tmp_path, cierre, personas=3, concurrencia=1, tope_usd=0.01)))
    assert c.parametros["motivo"] == "tope_usd"
    assert (tmp_path / c.id / "reporte.md").exists()
    assert len(list((tmp_path / c.id / "ejecuciones").iterdir())) == 1
