import pytest
from fastapi.testclient import TestClient

from dogfood import actividad
from dogfood.panel.app import crear_app_panel

H = {"X-Dogfood": "1"}
WEBHOOK = "https://hooks.slack.com/services/T0/B0/secreto-xyz-123"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "secretos"))
    return TestClient(crear_app_panel(tmp_path))


def test_guardar_ajustes_persiste_y_registra(cliente, tmp_path):
    r = cliente.patch(
        "/api/proyectos/predicts",
        json={
            "instrucciones": "Enfócate en el checkout",
            "comportamiento": {"login_una_vez": True},
        },
        headers=H | {"X-Dogfood-Autor": "hector"},
    )
    assert r.status_code == 200
    p = cliente.get("/api/proyectos/predicts").json()
    assert p["instrucciones"] == "Enfócate en el checkout"
    assert p["comportamiento"]["login_una_vez"] is True
    [e] = cliente.get("/api/proyectos/predicts/actividad").json()
    assert (e["tipo"], e["autor"]) == ("ajuste_cambiado", "hector")
    assert "instrucciones" in e["detalle"] and e["fecha"]
    assert actividad.listar(tmp_path, "predicts")[0]["id"] == e["id"]


def test_actividad_de_proyecto_inexistente_404(cliente):
    assert cliente.get("/api/proyectos/nada/actividad").status_code == 404


def test_el_webhook_de_slack_nunca_vuelve(cliente, tmp_path):
    r = cliente.patch(
        "/api/proyectos/predicts", json={"notificaciones": {"slack_webhook": WEBHOOK}}, headers=H
    )
    assert r.json()["notificaciones"]["slack"] is True
    todo = (
        r.text
        + cliente.get("/api/proyectos/predicts").text
        + cliente.get("/api/proyectos").text
        + cliente.get("/api/proyectos/predicts/actividad").text
    )
    assert "secreto-xyz-123" not in todo
    assert b"secreto-xyz-123" not in (tmp_path / "dogfood.db").read_bytes()
    assert "secreto-xyz-123" in (tmp_path / "secretos" / "slack-predicts.env").read_text()


def test_webhook_no_https_se_rechaza(cliente):
    r = cliente.patch(
        "/api/proyectos/predicts", json={"notificaciones": {"slack_webhook": "http://x"}}, headers=H
    )
    assert r.status_code == 400


def test_fuentes(cliente):
    assert isinstance(cliente.get("/api/proyectos/predicts/fuentes").json(), list)
