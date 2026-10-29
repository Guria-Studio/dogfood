import pytest
from fastapi.testclient import TestClient

from dogfood.web import crear_app_base, validar_host


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "100.100.1.2"])
def test_host_valido(host):
    assert validar_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "8.8.8.8"])
def test_host_rechazado(host):
    with pytest.raises(ValueError, match="NFR-10"):
        validar_host(host)


def test_css_servido():
    app, _ = crear_app_base("t")
    r = TestClient(app).get("/estatico/dogfood.css")
    assert r.status_code == 200
    assert "--estado-aprobado" in r.text and ".dark" in r.text


def test_plantilla_extiende_base(tmp_path):
    (tmp_path / "x.html").write_text(
        '{% extends "base.html" %}{% block contenido %}hola{% endblock %}'
    )
    _, plantillas = crear_app_base("t", tmp_path)
    html = plantillas.env.get_template("x.html").render()
    for esperado in ("Corridas", "Recorridos", "En vivo", 'id="tema"', "hola"):
        assert esperado in html


def test_filtros():
    _, plantillas = crear_app_base("t")
    f = plantillas.env.filters
    assert f["duracion"](65) == "1 min 05 s"
    assert f["usd"](0.01234) == "0.0123"
