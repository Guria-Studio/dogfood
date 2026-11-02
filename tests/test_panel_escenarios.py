"""API de exploración y escenarios propuestos de un proyecto (F13.2.T1)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dogfood import proyectos
from dogfood.almacen import Almacen
from dogfood.objetivos.web import WebObjetivo
from dogfood.panel.app import crear_app_panel

H = {"X-Dogfood": "1"}


class LanzadorFalso:
    def __init__(self):
        self.lanzados = []

    def lanzar(self, id, args, cwd, log):
        self.lanzados.append((id, args, cwd))
        return {"pid": 0}

    def vivo(self, h):
        return False

    def detener(self, h):
        pass


def _esc(id, titulo):
    return {"id": id, "titulo": titulo, "superficies": ["productos"], "objetivo": "o",
            "criterio_exito": "c", "max_pasos": 20}  # fmt: skip


@pytest.fixture
def entorno(tmp_path):
    p = proyectos.crear(
        {"slug": "tienda", "nombre": "Tienda", "objetivo": "web", "url": "http://127.0.0.1:1/"},
        tmp_path,
    )
    alm = Almacen(tmp_path)
    alm.guardar_borradores(
        "tienda", [(_esc("a", "A"), "alta"), (_esc("b", "B"), "media"), (_esc("c", "C"), "media")]
    )
    lanz = LanzadorFalso()
    return p, TestClient(crear_app_panel(tmp_path, lanzador=lanz)), lanz, tmp_path


def test_aceptar_uno_lo_lleva_a_los_escenarios_del_objetivo(entorno):
    p, cli, _, raiz = entorno
    filas = cli.get("/api/proyectos/tienda/escenarios").json()
    assert [(e["id"], e["estado"], e["prioridad"]) for e in filas] == [
        ("a", "borrador", "alta"), ("b", "borrador", "media"), ("c", "borrador", "media"),
    ]  # fmt: skip
    assert [e.id for e in WebObjetivo.desde_proyecto(p, raiz=raiz).escenarios()] == [
        "exploracion-libre"
    ]
    r = cli.patch("/api/proyectos/tienda/escenarios/b", json={"estado": "aceptado"}, headers=H)
    assert r.status_code == 200 and r.json()["estado"] == "aceptado"
    assert [e.id for e in WebObjetivo.desde_proyecto(p, raiz=raiz).escenarios()] == ["b"]
    assert [
        e["id"] for e in cli.get("/api/proyectos/tienda/escenarios?estado=borrador").json()
    ] == [
        "a",
        "c",
    ]


def test_editar_validar_descartar_y_borrar(entorno):
    _, cli, _, _ = entorno
    url = "/api/proyectos/tienda/escenarios/a"
    r = cli.patch(
        url, json={"objetivo": "Compra un café", "prioridad": "media", "id": "x"}, headers=H
    )
    assert r.status_code == 200
    e = cli.get(url).json()
    assert (e["id"], e["objetivo"], e["prioridad"], e["estado"]) == (
        "a",
        "Compra un café",
        "media",
        "borrador",
    )
    assert cli.patch(url, json={"max_pasos": 0}, headers=H).status_code == 422
    assert cli.patch(url, json={"estado": "otro"}, headers=H).status_code == 422
    assert cli.patch(url, json={"estado": "descartado"}).status_code == 403  # sin X-Dogfood
    assert cli.patch(url, json={"estado": "descartado"}, headers=H).json()["estado"] == "descartado"
    assert cli.delete(url).status_code == 403
    assert cli.delete(url, headers=H).status_code == 200
    assert cli.get(url).status_code == 404
    assert cli.get("/api/proyectos/nada/escenarios").status_code == 404


def test_lanzar_exploracion_y_leer_el_mapa(entorno):
    _, cli, lanz, raiz = entorno
    assert cli.get("/api/proyectos/tienda/mapa").status_code == 404
    assert cli.post("/api/proyectos/tienda/exploraciones").status_code == 403
    r = cli.post("/api/proyectos/tienda/exploraciones", json={"max_paginas": 5}, headers=H)
    assert r.status_code == 200
    id_, args, cwd = lanz.lanzados[0]
    assert r.json()["id"] == id_
    assert args[:5] == ["explorar", "--proyecto", "tienda", "--max-paginas", "5"]
    assert cwd == Path(raiz).resolve().parent
    assert cli.get(f"/api/corridas/{id_}/estado").json()["estado"] == "terminada"

    Almacen(raiz).guardar_exploracion(
        {"id": "exploracion-tienda-1", "proyecto": "tienda", "creado": "2026-11-02T10:00:00",
         "costo_usd": 0.02, "pantallas": [], "funcionalidades": [], "escenarios": []}
    )  # fmt: skip
    m = cli.get("/api/proyectos/tienda/mapa").json()
    assert m["id"] == "exploracion-tienda-1" and m["costo_usd"] == 0.02


def test_explorar_solo_proyectos_web(entorno):
    _, cli, _, _ = entorno
    r = cli.post("/api/proyectos/predicts/exploraciones", headers=H)
    assert r.status_code == 422
