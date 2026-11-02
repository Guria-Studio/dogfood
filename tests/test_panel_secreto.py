"""PUT /api/proyectos/{slug}/secreto: escribe el .env y nunca devuelve la contraseña (F13.2.T2)."""

from fastapi.testclient import TestClient

from dogfood import proyectos
from dogfood.panel.app import crear_app_panel

H = {"X-Dogfood": "1"}


def test_guarda_la_contrasena_sin_devolverla(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "cfg"))
    proyectos.crear(
        {"slug": "tienda", "nombre": "T", "objetivo": "web", "url": "http://127.0.0.1:1/"}, tmp_path
    )
    c = TestClient(crear_app_panel(tmp_path))
    assert c.put("/api/proyectos/tienda/secreto", json={"valor": "s3creto"}).status_code == 403
    r = c.put("/api/proyectos/tienda/secreto", json={"valor": "s3creto"}, headers=H)
    assert r.status_code == 200 and "s3creto" not in r.text
    env = tmp_path / "cfg" / "secretos" / "tienda.env"
    assert env.read_text() == "DOGFOOD_PASSWORD=s3creto\n"
    assert env.stat().st_mode & 0o777 == 0o600
    assert "s3creto" not in c.get("/api/proyectos/tienda").text
    assert c.put("/api/proyectos/tienda/secreto", json={"valor": ""}, headers=H).status_code == 400
    assert c.put("/api/proyectos/nada/secreto", json={"valor": "x"}, headers=H).status_code == 404
