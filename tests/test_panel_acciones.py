import pytest
from fastapi.testclient import TestClient

from dogfood.panel.app import crear_app_panel

H = {"X-Dogfood": "1"}


class Falso:
    def __init__(self):
        self.lanzados, self.detenidos, self.vive = [], [], True

    def lanzar(self, id, args, cwd, log):
        self.lanzados.append((id, args, cwd))
        log.write_text("uno\ndos\n")
        return {"pid": 1}

    def vivo(self, h):
        return self.vive

    def detener(self, h):
        self.detenidos.append(h)
        self.vive = False


@pytest.fixture
def falso():
    return Falso()


@pytest.fixture
def cliente(tmp_path, falso):
    raiz = tmp_path / "runs"
    raiz.mkdir()
    return TestClient(crear_app_panel(raiz, lanzador=falso))


def test_lanza_con_sin_publicar_por_defecto(cliente, falso):
    r = cliente.post(
        "/api/corridas",
        json={"objetivo": "predicts", "ref": "master", "personas": 3, "escenarios": ["a", "b"],
              "semilla": 7, "vista": True},
        headers=H,
    )  # fmt: skip
    assert r.status_code == 200
    _, args, _ = falso.lanzados[0]
    assert args == ["run", "--target", "predicts", "--ref", "master", "--personas", "3",
                    "--seed", "7", "--escenarios", "a,b", "--vista", "--sin-publicar"]  # fmt: skip
    assert cliente.get(f"/api/corridas/{r.json()['id']}/estado").json()["log"] == ["uno", "dos"]


def test_publicar_quita_el_flag(cliente, falso):
    cliente.post("/api/corridas", json={"sin_publicar": False}, headers=H)
    assert "--sin-publicar" not in falso.lanzados[0][1]


def test_segunda_corrida_da_409(cliente):
    assert cliente.post("/api/corridas", json={}, headers=H).status_code == 200
    assert cliente.post("/api/corridas", json={}, headers=H).status_code == 409
    assert cliente.post("/api/ejecuciones/x-E1/replay", headers=H).status_code == 409


def test_sin_header_da_403(cliente, falso):
    assert cliente.post("/api/corridas", json={}).status_code == 403
    assert cliente.post("/api/ejecuciones/x-E1/replay").status_code == 403
    assert cliente.post("/api/corridas/L-1/cancelar").status_code == 403
    assert falso.lanzados == []


def test_cancelar_detiene_y_libera(cliente, falso):
    i = cliente.post("/api/corridas", json={}, headers=H).json()["id"]
    assert cliente.post(f"/api/corridas/{i}/cancelar", headers=H).status_code == 200
    assert falso.detenidos
    assert cliente.get(f"/api/corridas/{i}/estado").json()["estado"] == "cancelada"
    assert cliente.post("/api/corridas", json={}, headers=H).status_code == 200


def test_replay_lanza_el_comando(cliente, falso):
    r = cliente.post("/api/ejecuciones/c1-E2/replay?ref=dev", headers=H)
    assert r.status_code == 200
    args = falso.lanzados[0][1]
    assert args[:2] == ["replay", "c1-E2"] and args[3] == "dev"


def test_estado_inexistente_404(cliente):
    assert cliente.get("/api/corridas/nada/estado").status_code == 404
