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


# --- F12.2.T1: diff en el PR ---
DIFF_ALTO = {
    "id": "diff-1", "proyecto": "falso",
    "casos": [{"tc": "TC001", "pasos": [{"step_id": "s1", "cambios": [
        {"tipo": "red", "subtipo": "estado", "gravedad": "alta", "metodo": "GET",
         "ruta": "/api/x", "antes": 200, "despues": 500}]}]}],
}  # fmt: skip
DIFF_BAJO = {"id": "diff-2", "proyecto": "falso", "casos": [{"tc": "TC001", "pasos": [
    {"step_id": "s1", "cambios": [{"tipo": "visual", "gravedad": "baja", "detalle": "x"}]}]}]}  # fmt: skip


def _con_diff(tmp_path, monkeypatch, diff, bloquea=False):
    from dogfood import proyectos

    proyectos.crear(
        {"slug": "falso", "nombre": "Falso", "objetivo": "predicts", "diff_activo": True,
         "diff_bloquea": bloquea, "notificaciones": {"comentar_pr": True}},
        tmp_path,
    )  # fmt: skip
    monkeypatch.setattr("dogfood.comandos.ci._correr_diff", lambda *a: diff)
    comentarios = []
    monkeypatch.setattr(
        "dogfood.comandos.ci.subprocess.run", lambda cmd, **k: comentarios.append(cmd[-1])
    )
    return comentarios


def _ci_pr(tmp_path):
    return CliRunner().invoke(
        app, ["ci", "--target", "falso", "--ref", "abc123", "--raiz", str(tmp_path), "--pr", "5"]
    )


def test_comentario_incluye_cambios_altos_y_link(tmp_path, entorno, monkeypatch):
    entorno[0]()
    comentarios = _con_diff(tmp_path, monkeypatch, DIFF_ALTO)
    r = _ci_pr(tmp_path)
    assert r.exit_code == 0, r.output  # sin diff_bloquea no falla
    assert "### Cambios de comportamiento" in comentarios[0]
    assert "GET /api/x: 200 → 500" in comentarios[0]
    assert "/proyectos/falso/diffs/diff-1" in comentarios[0]


def test_comentario_omite_la_seccion_sin_cambios_altos(tmp_path, entorno, monkeypatch):
    entorno[0]()
    comentarios = _con_diff(tmp_path, monkeypatch, DIFF_BAJO, bloquea=True)
    assert _ci_pr(tmp_path).exit_code == 0
    assert "Cambios de comportamiento" not in comentarios[0]


def test_diff_bloquea_decide_el_codigo_de_salida(tmp_path, entorno, monkeypatch):
    entorno[0]()
    _con_diff(tmp_path, monkeypatch, DIFF_ALTO, bloquea=True)
    assert _ci_pr(tmp_path).exit_code == 1
