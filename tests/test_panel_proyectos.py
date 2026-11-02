import sqlite3

import pytest
from fastapi.testclient import TestClient

from dogfood.panel.app import crear_app_panel

H = {"X-Dogfood": "1"}
NUEVO = {"slug": "mi-app", "nombre": "Mi app", "tipo": "web", "objetivo": "predicts"}


@pytest.fixture
def raiz(tmp_path):
    return tmp_path


@pytest.fixture
def cliente(raiz):
    return TestClient(crear_app_panel(raiz))


def test_crud(cliente):
    assert [p["slug"] for p in cliente.get("/api/proyectos").json()] == ["predicts"]
    assert cliente.post("/api/proyectos", json=NUEVO, headers=H).status_code == 201
    assert cliente.post("/api/proyectos", json=NUEVO, headers=H).status_code == 400  # duplicado
    r = cliente.patch("/api/proyectos/mi-app", json={"url": "http://u"}, headers=H)
    assert r.json()["url"] == "http://u"
    assert cliente.get("/api/proyectos/mi-app").json()["nombre"] == "Mi app"
    assert cliente.get("/api/proyectos/nada").status_code == 404
    assert (
        cliente.post(
            "/api/proyectos", json=NUEVO | {"slug": "x", "tipo": "palm"}, headers=H
        ).status_code
        == 400
    )
    assert (
        cliente.request(
            "DELETE", "/api/proyectos/mi-app", json={"confirmar": "mi-app"}, headers=H
        ).status_code
        == 200
    )
    assert cliente.get("/api/proyectos/mi-app").status_code == 404


def test_borrar_exige_confirmacion_y_header(cliente):
    cliente.post("/api/proyectos", json=NUEVO, headers=H)
    for cuerpo in (None, {"confirmar": "otro"}):
        r = cliente.request("DELETE", "/api/proyectos/mi-app", json=cuerpo, headers=H)
        assert r.status_code == 400
    assert (
        cliente.request("DELETE", "/api/proyectos/mi-app", json={"confirmar": "mi-app"}).status_code
        == 403
    )
    assert cliente.post("/api/proyectos", json=NUEVO | {"slug": "z"}).status_code == 403
    assert cliente.patch("/api/proyectos/mi-app", json={"url": "u"}).status_code == 403
    assert cliente.get("/api/proyectos/mi-app").status_code == 200


def test_el_secreto_no_vuelve(cliente, raiz):
    cuerpo = NUEVO | {
        "acceso": {"usuario": "u", "secreto_ref": "MI_CLAVE", "secreto": "s3creto-xyz"}
    }
    r = cliente.post("/api/proyectos", json=cuerpo, headers=H)
    cliente.patch("/api/proyectos/mi-app", json={"acceso": {"secreto": "s3creto-xyz"}}, headers=H)
    todo = r.text + cliente.get("/api/proyectos/mi-app").text + cliente.get("/api/proyectos").text
    assert "s3creto-xyz" not in todo and "MI_CLAVE" in todo
    assert b"s3creto-xyz" not in (raiz / "dogfood.db").read_bytes()


def test_lista_con_conteos_de_la_ultima_corrida(cliente, raiz):
    assert cliente.get("/api/proyectos/predicts").json()["ultimos"]["corrida_id"] is None
    con = sqlite3.connect(raiz / "dogfood.db")
    for i, (cid, ini) in enumerate([("vieja", "2026-01-01"), ("nueva", "2026-02-01")]):
        con.execute(
            'INSERT INTO corridas (id, objetivo, ref, "commit", semilla, inicio, estado, proyecto)'
            " VALUES (?, 'predicts', 'm', 'c', 1, ?, 'ok', 'predicts')",
            (cid, ini),
        )
    for n, (res, exito) in enumerate([("aprobado", 1), ("fallo", 0), ("fallo", 0)]):
        con.execute(
            "INSERT INTO ejecuciones (id, corrida_id, persona_id, escenario_id, modelo, estado, pasos,"
            " duracion_s, exito, motivo_juez, resultado) VALUES (?, 'nueva', 'p', 'e', 'm', 'ok', 1, 1, ?, '', ?)",
            (f"E{n}", exito, res),
        )
    con.commit()
    u = next(p for p in cliente.get("/api/proyectos").json() if p["slug"] == "predicts")["ultimos"]
    assert (u["corrida_id"], u["pasaron"], u["fallaron"]) == ("nueva", 1, 2)
    assert u["ultima_actividad"] == "2026-02-01"
