from fastapi.testclient import TestClient

from dogfood.eventos import BusVivo, EventoVivo
from dogfood.vista.servidor import crear_app_vista


def test_con_build_sirve_la_spa_y_el_ws(tmp_path):
    (tmp_path / "index.html").write_text("<html>SPA</html>")
    bus = BusVivo()
    c = TestClient(crear_app_vista(bus, spa=tmp_path))
    assert "SPA" in c.get("/vista").text
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/vista"
    with c.websocket_connect("/ws") as ws:
        bus.publicar(EventoVivo(corrida_id="c", ejecucion_id="e", tipo="paso", accion="x"))
        assert ws.receive_json()["accion"] == "x"


def test_sin_build_503(tmp_path):
    r = TestClient(crear_app_vista(BusVivo(), spa=tmp_path)).get("/vista")
    assert r.status_code == 503 and "scripts/build-web.sh" in r.text
