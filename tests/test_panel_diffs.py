import pytest
from fastapi.testclient import TestClient

from dogfood import proyectos
from dogfood.almacen import Almacen
from dogfood.panel.app import crear_app_panel

H = {"X-Dogfood": "1"}
DIFF = {
    "id": "diff-20260101-000000", "proyecto": "predicts", "base": "master", "nueva": "pr-7",
    "creado": "2026-01-01T00:00:00+00:00",
    "casos": [
        {"tc": "TC001", "caso_id": "a", "titulo": "Alta", "resultado": "cambios", "pasos": [
            {"step_id": "s1", "accion": "click", "cambios": [
                {"tipo": "red", "subtipo": "estado", "gravedad": "alta", "metodo": "GET",
                 "ruta": "/api/x", "antes": 200, "despues": 500}],
             "capturas": {"antes": "capturas/TC001/s1-antes.png"}}]},
        {"tc": "TC002", "caso_id": "b", "titulo": "Baja", "resultado": "sin_cambios", "pasos": []},
    ],
}  # fmt: skip


class Falso:
    def __init__(self):
        self.lanzados = []

    def lanzar(self, id, args, cwd, log):
        self.lanzados.append(args)
        return {"pid": 1}


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "runs"
    raiz.mkdir()
    proyectos.listar(raiz)  # siembra predicts
    Almacen(raiz).guardar_diff(DIFF)
    png = raiz / DIFF["id"] / "capturas" / "TC001" / "s1-antes.png"
    png.parent.mkdir(parents=True)
    png.write_bytes(b"png")
    falso = Falso()
    return TestClient(crear_app_panel(raiz, lanzador=falso)), falso


def test_lista_y_detalle_con_cambios_clasificados(entorno):
    c, _ = entorno
    (fila,) = c.get("/api/proyectos/predicts/diffs").json()
    assert (fila["base"], fila["nueva"], fila["con_cambios"], fila["total"]) == (
        "master",
        "pr-7",
        1,
        2,
    )
    d = c.get(f"/api/diffs/{DIFF['id']}").json()
    assert d["casos"][0]["pasos"][0]["cambios"][0]["gravedad"] == "alta"
    assert c.get("/api/diffs/nada").status_code == 404
    assert c.get("/api/proyectos/nada/diffs").status_code == 404


def test_captura_y_sin_salirse_de_la_carpeta(entorno):
    c, _ = entorno
    assert c.get(f"/api/diffs/{DIFF['id']}/capturas/TC001/s1-antes.png").content == b"png"
    assert c.get(f"/api/diffs/{DIFF['id']}/capturas/..%2Fdiff.json").status_code == 404


def test_lanza_diff_con_header(entorno):
    c, falso = entorno
    cuerpo = {"base": "master", "nueva": "abc123"}
    assert c.post("/api/proyectos/predicts/diffs", json=cuerpo).status_code == 403
    assert (
        c.post(
            "/api/proyectos/predicts/diffs", json={**cuerpo, "base": "--x"}, headers=H
        ).status_code
        == 422
    )
    r = c.post("/api/proyectos/predicts/diffs", json=cuerpo, headers=H)
    assert r.status_code == 200
    assert falso.lanzados[0][:8] == [
        "diff",
        "--target",
        "predicts",
        "--base",
        "master",
        "--nueva",
        "abc123",
        "--casos",
    ]
