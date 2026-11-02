import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from dogfood import suites
from dogfood.panel.app import crear_app_panel

H = {"X-Dogfood": "1"}


class Lanz:
    def __init__(self):
        self.lanzados = []

    def lanzar(self, id, args, cwd, log):
        self.lanzados.append(args)
        return {"pid": 1}

    def vivo(self, h):
        return False

    def detener(self, h): ...


class Timers:
    def __init__(self):
        self.activos = {}

    def crear(self, id, calendario, comando, cwd):
        self.activos[id] = (calendario, comando)

    def borrar(self, id):
        self.activos.pop(id, None)


@pytest.fixture
def ctx(tmp_path):
    lanz, timers = Lanz(), Timers()
    c = TestClient(crear_app_panel(tmp_path, lanzador=lanz, programador=timers))
    c.post(
        "/api/proyectos",
        headers=H,
        json={"slug": "otra", "nombre": "Otra", "objetivo": "flutter_web"},
    )
    return c, lanz, timers, tmp_path


def test_suite_con_dos_proyectos_lanza_ambas_corridas(ctx):
    c, lanz, _, _ = ctx
    casos = [
        {"proyecto": "predicts", "caso": "registro:p1"},
        {"proyecto": "otra", "caso": "login:p2"},
    ]
    r = c.post("/api/suites", headers=H, json={"nombre": "Humo", "casos": casos})
    assert r.status_code == 201 and r.json()["n_casos"] == 2 and r.json()["estado"] is None
    assert c.post("/api/suites", headers=H, json={"nombre": "x", "casos": []}).status_code == 400
    r = c.post(f"/api/suites/{r.json()['id']}/correr", headers=H)
    assert r.json()["corridas"] == 2
    objetivos = {a[a.index("--target") + 1]: a[a.index("--escenarios") + 1] for a in lanz.lanzados}
    assert objetivos == {"predicts": "registro", "flutter_web": "login"}
    assert c.get("/api/suites").json()[0]["estado"] == "corriendo"  # lanzada, sin corrida aún


def test_programacion_crea_y_borra_el_timer(ctx):
    c, _, timers, _ = ctx
    sid = c.post(
        "/api/suites",
        headers=H,
        json={"nombre": "S", "casos": [{"proyecto": "predicts", "caso": "a"}]},
    ).json()["id"]
    r = c.post(
        "/api/programaciones", headers=H,
        json={"suite_id": sid, "frecuencia": "semana", "dia": "Mon", "hora": "03:30", "slack": True},
    )  # fmt: skip
    assert r.status_code == 201
    cal, cmd = timers.activos[r.json()["id"]]
    assert cal == "Mon *-*-* 03:30:00"
    assert cmd[3:5] == ["suite", "run"] and "--slack" in cmd and str(sid) in cmd
    assert len(c.get("/api/programaciones").json()) == 1
    assert c.delete(f"/api/programaciones/{r.json()['id']}", headers=H).status_code == 200
    assert timers.activos == {} and c.get("/api/programaciones").json() == []
    bad = {"suite_id": sid, "frecuencia": "cron", "cron": "x y"}
    assert c.post("/api/programaciones", headers=H, json=bad).status_code == 400


def test_calendarios():
    assert suites.calendario("hora") == "hourly"
    assert suites.calendario("dia", "07:05") == "*-*-* 07:05:00"
    assert suites.cron_a_calendario("*/15 2 * * 1-5") == "Mon..Fri *-*-* 2:*/15:00"


def _corrida(raiz, objetivo, semilla, ejecuciones, fin="2026-01-01"):
    with closing(sqlite3.connect(raiz / "dogfood.db")) as con, con:
        con.execute(
            'INSERT INTO corridas (id, objetivo, ref, "commit", semilla, inicio, fin, estado)'
            " VALUES (?, ?, 'main', 'c', ?, '2026-01-01', ?, 'ok')",
            (f"c{semilla}", objetivo, semilla, fin),
        )
        for i, (resultado, estado) in enumerate(ejecuciones):
            con.execute(
                "INSERT INTO ejecuciones (id, corrida_id, persona_id, escenario_id, modelo, estado,"
                " pasos, duracion_s, exito, motivo_juez, resultado) VALUES (?, ?, 'p', 'e', 'm', ?,"
                " 1, 1, ?, '', ?)",
                (f"e{semilla}{i}", f"c{semilla}", estado, int(resultado == "aprobado"), resultado),
            )


@pytest.mark.parametrize(
    ("resultados", "esperado"),
    [
        ([("aprobado", "ok")] * 2, "paso"),
        ([("aprobado", "ok"), ("fallo", "fallo")], "advertencia"),
        ([("fallo", "fallo")], "fallo"),
        ([("no_concluyente", "rendido")], "bloqueado"),
    ],
)
def test_estado_de_la_ultima_corrida(ctx, resultados, esperado):
    c, _, _, raiz = ctx
    s = c.post(
        "/api/suites",
        headers=H,
        json={"nombre": "S", "casos": [{"proyecto": "predicts", "caso": "a"}]},
    ).json()
    suites.registrar_lanzadas(raiz, s["id"], [{"objetivo": "predicts", "semilla": 7}])
    _corrida(raiz, "predicts", 7, resultados)
    assert c.get("/api/suites").json()[0]["estado"] == esperado
