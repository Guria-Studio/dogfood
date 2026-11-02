from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogfood.cli import app
from dogfood.config import Config
from dogfood.dominio import Ejecucion, Escenario, Instancia, Paso


def _esc(id, superficies):
    return Escenario(id=id, titulo=id, objetivo="o", criterio_exito="c", superficies=superficies)


class FalsoObjetivo:
    nombre = "falso"

    def preparar(self, ref, corrida):
        return Instancia(
            base_url="http://x", api_url="http://x", proyecto_compose="p", commit="abc"
        )

    def destruir(self, instancia):
        pass

    def escenarios(self):
        return [_esc("pago", ["registro"]), _esc("curioso", ["inicio"])]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


@pytest.fixture
def entorno(monkeypatch):
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]})
    corridos = []
    monkeypatch.setattr(Config, "cargar", classmethod(lambda cls, *a, **k: cfg))
    for modulo in ("dogfood.comandos.ci", "dogfood.corrida"):
        monkeypatch.setattr(f"{modulo}.cargar_objetivo", lambda n: FalsoObjetivo())
    monkeypatch.setattr("dogfood.corrida.cliente_para", lambda *a, **k: object())

    monkeypatch.setattr("dogfood.corrida.opinion.contar_uso_ia", lambda i: None)

    def fallar(*ids):
        async def ejecutar(persona, escenario, instancia, dataset, carpeta, *a, **k):
            corridos.append(escenario.id)
            return Ejecucion(
                id=carpeta.name,
                persona_id=persona.id,
                escenario_id=escenario.id,
                modelo="m",
                estado="ok",
                exito=escenario.id not in ids,
                motivo_juez="ok",
                pasos=[
                    Paso(
                        n=1,
                        url="u",
                        pantalla="p",
                        accion="a",
                        captura=Path("c.png"),
                        ts=datetime.now(),
                    )
                ],
            )

        monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)

    return fallar, corridos


def _ci(tmp_path):
    return CliRunner().invoke(
        app, ["ci", "--target", "falso", "--ref", "abc123", "--raiz", str(tmp_path)]
    )


def test_un_caso_fallido_sale_con_1(tmp_path, entorno):
    fallar, corridos = entorno
    fallar("pago")
    r = _ci(tmp_path)
    assert r.exit_code == 1, r.output
    assert corridos == ["pago"]  # solo los de prioridad alta


def test_todo_verde_sale_con_0(tmp_path, entorno):
    fallar, _ = entorno
    fallar()
    r = _ci(tmp_path)
    assert r.exit_code == 0, r.output
    assert "1/1" in r.output
