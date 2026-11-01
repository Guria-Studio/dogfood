import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from dogfood.almacen import Almacen
from dogfood.config import Config
from dogfood.dominio import Corrida, Ejecucion, MetricasEjecucion, Paso, Persona
from dogfood.panel.app import crear_app_panel

PERSONA = Persona(
    id="p1", nombre="Ana", email="ana@x.com", contrasena="hunter2-pw", empresa="E", rubro="r",
    idioma="es", destreza=3, paciencia=3, intencion="explorar", semilla=1,
)  # fmt: skip


def _ej(a, eid, res, motor="browser_use"):
    d = a.dir_ejecucion("c1", eid)
    cap = d / "capturas" / "1.png"
    cap.parent.mkdir(parents=True, exist_ok=True)
    cap.write_bytes(b"\x89PNG")
    a.guardar_ejecucion(
        "c1",
        Ejecucion(
            id=eid, persona_id="p1", escenario_id="demo", modelo="m", estado="ok", motor=motor,
            resultado=res, exito=res == "aprobado", duracion_s=3,
            metricas=MetricasEjecucion(tokens_in=10, tokens_out=5, capturas=1),
            pasos=[Paso(n=1, url="http://app/", pantalla="/", accion="clic", captura=cap,
                        ts=datetime(2026, 1, 1))],
        ),
    )  # fmt: skip


@pytest.fixture
def raiz(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(
        Corrida(id="c1", objetivo="predicts", ref="main", commit="abc", semilla=1,
                inicio=datetime(2026, 1, 1), estado="completa")
    )  # fmt: skip
    a.guardar_personas("c1", [PERSONA])
    _ej(a, "e1", "aprobado")
    _ej(a, "e2", "fallo", motor="claude_code")
    return tmp_path


@pytest.fixture
def cliente(raiz):
    app = crear_app_panel(raiz)
    app.state.cfg = Config(roles={}, repo_issues="yo/dogfood", umbral_publicar="media")
    return TestClient(app)


def test_ejecuciones_y_filtros(cliente):
    assert {f["id"] for f in cliente.get("/api/ejecuciones").json()} == {"e1", "e2"}
    for k, v, esperado in [
        ("recorrido", "demo", {"e1", "e2"}), ("recorrido", "otro", set()),
        ("resultado", "fallo", {"e2"}), ("version", "abc", {"e1", "e2"}),
        ("persona", "p1", {"e1", "e2"}), ("persona", "zz", set()),
        ("driver", "web", {"e1", "e2"}), ("driver", "android", set()),
        ("motor", "claude_code", {"e2"}),
    ]:  # fmt: skip
        r = cliente.get("/api/ejecuciones", params={k: v}).json()
        assert {f["id"] for f in r} == esperado, (k, v)


def test_filtros_y_etiquetas(cliente):
    f = cliente.get("/api/filtros").json()
    assert {"valor": "fallo", "etiqueta": "falló"} in f["resultado"]
    assert cliente.get("/api/etiquetas").json()["fallo"] == "falló"


def test_corrida(cliente):
    r = cliente.get("/api/corridas/c1").json()
    assert r["resumen"]["ejecuciones"] == 2
    assert {c["motor"] for c in r["comparacion"]} == {"browser_use", "claude_code"}
    assert cliente.get("/api/corridas/nada").status_code == 404


def test_detalle_con_captura(cliente):
    r = cliente.get("/api/ejecuciones/e1")
    d = r.json()
    assert d["pasos"][0]["captura"] == "/archivos/c1/ejecuciones/e1/capturas/1.png"
    assert cliente.get(d["pasos"][0]["captura"]).status_code == 200
    assert "hunter2-pw" not in r.text and "ana@x.com" not in r.text
    assert cliente.get("/api/ejecuciones/nada").status_code == 404


def test_issue_exige_header(cliente, monkeypatch):
    llamadas = []

    class R:
        issue_url, accion, aviso = "https://gh/x/1", "creado", ""

    monkeypatch.setattr("dogfood.panel.issue.publicar_issue", lambda *a: llamadas.append(a) or R())
    assert cliente.post("/api/ejecuciones/e1/issue").status_code == 403
    assert not llamadas
    r = cliente.post("/api/ejecuciones/e1/issue", headers={"X-Dogfood": "1"})
    assert r.json() == {"url": "https://gh/x/1", "accion": "creado", "aviso": ""}
    assert len(llamadas) == 1


def test_dispositivos(cliente, monkeypatch):
    monkeypatch.setattr("dogfood.drivers.adb_red.listar", list)
    assert cliente.get("/api/dispositivos").json() == []


def test_openapi_incluye_api(cliente):
    paths = cliente.get("/openapi.json").json()["paths"]
    for p in ("/api/ejecuciones", "/api/filtros", "/api/etiquetas", "/api/corridas/{corrida_id}",
              "/api/recorridos", "/api/ejecuciones/{ejecucion_id}", "/api/dispositivos"):  # fmt: skip
        assert "200" in paths[p]["get"]["responses"]
        assert "$ref" in json.dumps(paths[p]["get"]["responses"]["200"]) or p == "/api/etiquetas"
    assert "post" in paths["/api/ejecuciones/{ejecucion_id}/issue"]


def test_spa_con_build(raiz, tmp_path):
    est = tmp_path / "est"
    (est / "assets").mkdir(parents=True)
    (est / "index.html").write_text("<html>SPA</html>")
    (est / "assets" / "a.js").write_text("x")
    c = TestClient(crear_app_panel(raiz, spa=est))
    assert c.get("/ejecuciones/x").text == "<html>SPA</html>"
    assert c.get("/").text == "<html>SPA</html>"
    assert c.get("/assets/a.js").text == "x"
    assert c.get("/api/filtros").status_code == 200
    assert c.get("/api/nada").status_code == 404
    assert c.get("/openapi.json").status_code == 200


def test_spa_sin_build_503(tmp_path):
    from fastapi import FastAPI

    from dogfood.panel.spa import montar_spa

    app = FastAPI()
    montar_spa(app, tmp_path / "no")
    r = TestClient(app).get("/x")
    assert r.status_code == 503 and "scripts/build-web.sh" in r.text
