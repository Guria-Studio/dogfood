from datetime import datetime
from pathlib import Path

import pytest

from dogfood.dominio import Corrida, Instancia
from dogfood.objetivos.predicts import entorno
from dogfood.objetivos.predicts.pantallas import pantalla

INST = Instancia(
    base_url="http://localhost:18080",
    api_url="http://localhost:18100",
    proyecto_compose="dogfood-predicts",
    commit="abc",
)


def _corrida() -> Corrida:
    return Corrida(
        id="c1", objetivo="predicts", ref="main", commit="", semilla=1,
        inicio=datetime.now(), estado="x",
    )  # fmt: skip


@pytest.fixture
def falso(tmp_path, monkeypatch):
    """subprocess falseado; devuelve la lista de comandos ejecutados."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "predicts.env").write_text("MIN_COMPRAS=5\n")
    repo = tmp_path / "predicts"
    (repo / "deploy").mkdir(parents=True)
    (repo / "deploy" / "docker-compose.yml").write_text("      MIN_COMPRAS: ${MIN_COMPRAS:-3}\n")
    (tmp_path / "dogfood.yaml").write_text(f"predicts_repo: {repo}\n")
    cmds: list[list[str]] = []

    def run(cmd, **kw):
        cmds.append(cmd)
        if "worktree" in cmd:  # el worktree falso es una copia del repo
            Path(cmd[-2]).mkdir(parents=True)
            (Path(cmd[-2]) / "deploy").symlink_to(repo / "deploy")
        return type("R", (), {"returncode": 0, "stdout": "deadbeef\n", "stderr": ""})()

    monkeypatch.setattr(entorno.subprocess, "run", run)
    monkeypatch.setattr(entorno, "_esperar_salud", lambda url, t: None)
    return cmds


def test_compose_usa_proyecto_propio_y_override_con_puertos(falso, tmp_path):
    inst = entorno.preparar("main", _corrida())
    up = next(c for c in falso if "up" in c)
    assert up[up.index("-p") + 1] == "dogfood-predicts"
    assert all(c[c.index("-p") + 1] != "predicts" for c in falso if "-p" in c)
    assert "--env-file" in up
    override = (tmp_path / "runs" / "c1" / "docker-compose.override.yml").read_text()
    for p in ("18080", "18100", "54330", "CORS_ORIGENES: 'http://localhost:18080'", "ENTORNO: dev"):
        assert p in override
    assert "8080:" not in override.replace("18080:", "")
    assert inst.commit == "deadbeef"
    assert inst.parametros["MIN_COMPRAS"] == "5"


def test_destruir_solo_el_proyecto_propio(falso):
    entorno.destruir(INST)
    assert falso[-1] == [
        "docker",
        "compose",
        "-p",
        "dogfood-predicts",
        "down",
        "-v",
        "--remove-orphans",
    ]
    with pytest.raises(entorno.ErrorEntorno):
        entorno.destruir(INST.model_copy(update={"proyecto_compose": "predicts"}))


def test_url_permitida():
    assert not entorno.url_permitida("http://localhost:8080/", INST)
    assert entorno.url_permitida("http://localhost:18080/api/x", INST)
    assert entorno.url_permitida("http://localhost:18100/salud", INST)
    assert not entorno.url_permitida("http://localhost:18080.evil.com/", INST)


def test_sin_predicts_env_el_error_nombra_el_archivo(falso, tmp_path):
    (tmp_path / "cfg" / "predicts.env").unlink()
    with pytest.raises(entorno.ErrorEntorno, match="predicts.env"):
        entorno.preparar("main", _corrida())


def test_pantalla():
    assert pantalla("/datasets/abc/mapeo") == "mapeo"
    assert pantalla("http://localhost:18080/analisis/1/universo") == "universo"
    assert pantalla("/nada") == "otra"
