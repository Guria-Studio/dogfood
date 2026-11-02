import json
import sqlite3
import subprocess
import threading
from contextlib import closing
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from dogfood import proyectos
from dogfood.dominio import Corrida, Escenario, Instancia
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.web import EXPLORACION_LIBRE, WebObjetivo
from dogfood.panel.app import crear_app_panel


class _Sano(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(302 if self.path == "/" else 200)
        self.send_header("Location", "/inicio")
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def servidor():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _Sano)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/"
    s.shutdown()


def _proyecto(tmp_path, **kw):
    return proyectos.crear(
        {"slug": "app", "nombre": "App", "objetivo": "web", "url": "http://127.0.0.1:1/"} | kw,
        tmp_path,
    )


def _corrida():
    return Corrida(
        id="c", objetivo="web", ref="main", commit="", semilla=1, inicio=datetime.now(), estado="x"
    )


class Runner:
    def __init__(self):
        self.llamadas = []

    def __call__(self, cmd, **kw):
        self.llamadas.append(cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, stdout="api | listo\n", stderr="")


def test_levantar_y_bajar_en_orden(tmp_path, servidor):
    p = _proyecto(
        tmp_path,
        url=servidor,
        salud="/salud",
        levantar="docker compose -f app.yml up -d",
        bajar="docker compose -f app.yml down -v",
    )
    runner = Runner()
    obj = WebObjetivo.desde_proyecto(p, raiz=tmp_path, runner=runner, timeout_salud_s=5)
    inst = obj.preparar("main", _corrida())
    assert inst.base_url == servidor
    assert obj.logs(inst, datetime.now().astimezone()) == {"app": "api | listo\n"}
    obj.destruir(inst)
    assert runner.llamadas[0] == "docker compose -f app.yml up -d"
    assert runner.llamadas[1].startswith("docker compose -f app.yml logs --no-color --since ")
    assert runner.llamadas[2] == "docker compose -f app.yml down -v"


def test_salud_3xx_basta_y_sin_levantar_no_hay_logs(tmp_path, servidor):
    runner = Runner()
    obj = WebObjetivo.desde_proyecto(_proyecto(tmp_path, url=servidor), runner=runner)
    inst = obj.preparar("main", _corrida())  # la raíz responde 302
    obj.destruir(inst)
    assert obj.logs(inst, datetime.now()) == {}
    assert runner.llamadas == []


def test_salud_que_no_responde_da_timeout(tmp_path):
    obj = WebObjetivo.desde_proyecto(_proyecto(tmp_path), timeout_salud_s=0)
    with pytest.raises(TimeoutError, match="2xx/3xx"):
        obj.preparar("main", _corrida())


def test_host_prohibido_frena_antes_de_levantar(tmp_path):
    p = _proyecto(
        tmp_path,
        url="https://app.fluent.example/",
        levantar="docker compose up -d",
        hosts_prohibidos=["fluent.example"],
    )
    runner = Runner()
    with pytest.raises(proyectos.ErrorProyecto, match="hosts_prohibidos"):
        WebObjetivo.desde_proyecto(p, runner=runner).preparar("main", _corrida())
    assert runner.llamadas == []


def test_url_permitida_con_origenes_extra(tmp_path):
    p = _proyecto(tmp_path, origenes_extra=["https://api.ejemplo.com", "cdn.ejemplo.com"])
    obj = WebObjetivo.desde_proyecto(p)
    inst = Instancia(base_url="http://localhost:3000/", api_url="", proyecto_compose="", commit="")
    assert obj.url_permitida("http://localhost:3000/ajustes?x=1", inst)
    assert obj.url_permitida("https://api.ejemplo.com/v1/yo", inst)
    assert obj.url_permitida("https://cdn.ejemplo.com/a.js", inst)
    assert obj.url_permitida("about:blank", inst)
    assert not obj.url_permitida("http://api.ejemplo.com/v1/yo", inst)  # otro esquema
    assert not obj.url_permitida("https://otro.com/", inst)
    assert not obj.url_permitida("http://localhost:3001/", inst)
    assert not obj.url_permitida("https://evil.com/?https://api.ejemplo.com", inst)


def test_sin_aceptados_exploracion_libre_y_con_aceptados_solo_esos(tmp_path):
    obj = WebObjetivo.desde_proyecto(_proyecto(tmp_path), raiz=tmp_path)
    assert obj.escenarios() == [EXPLORACION_LIBRE]
    assert "función principal" in EXPLORACION_LIBRE.objetivo
    esc = Escenario(id="pagar", titulo="Pagar", objetivo="o", criterio_exito="c")
    with closing(sqlite3.connect(tmp_path / "dogfood.db")) as con, con:
        for id_, estado in (("pagar", "aceptado"), ("borrar", "borrador")):
            con.execute(
                "INSERT INTO escenarios_proyecto (proyecto, id, estado, datos, creado)"
                " VALUES ('app', ?, ?, ?, '2026-11-02')",
                (id_, estado, json.dumps(esc.model_dump(mode="json") | {"id": id_})),
            )
    assert [e.id for e in obj.escenarios()] == ["pagar"]


def test_pantalla_verificadores_y_registro(tmp_path):
    obj = cargar_objetivo("web", _proyecto(tmp_path), tmp_path)
    assert isinstance(obj, WebObjetivo) and obj.proyecto.slug == "app"
    assert obj.pantalla("http://x/proyectos/42/datos") == "proyectos"
    assert obj.pantalla("http://x/123/ajustes") == "ajustes"
    assert obj.pantalla("http://x/#/perfil") == "perfil"
    assert obj.pantalla("http://x/", "Mi app") == "Mi app"
    assert obj.pantalla("http://x/") == "inicio"
    assert obj.verificadores() == []
    assert cargar_objetivo("web").verificadores() == []  # así lo carga `deteccion.objetivo`


def test_api_acepta_los_campos_nuevos(tmp_path):
    cliente = TestClient(crear_app_panel(tmp_path))
    h = {"X-Dogfood": "1"}
    nuevo = {
        "slug": "fluent",
        "nombre": "Fluent",
        "objetivo": "web",
        "url": "http://localhost:3000",
        "levantar": "docker compose -f f.yml up -d",
        "bajar": "docker compose -f f.yml down",
        "salud": "/api/health",
        "origenes_extra": ["http://localhost:8000"],
        "hosts_prohibidos": ["fluent.usebot.chat"],
        "entornos": [{"nombre": "local", "url": "http://localhost:3000", "tipo": "local"}],
    }
    r = cliente.post("/api/proyectos", json=nuevo, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["hosts_prohibidos"] == ["fluent.usebot.chat"]
    r = cliente.patch(
        "/api/proyectos/fluent",
        json={"entornos": [{"nombre": "stg", "url": "https://stg.x", "tipo": "staging"}]},
        headers=h,
    )
    assert r.json()["entornos"][0]["tipo"] == "staging"
    assert r.json()["salud"] == "/api/health"
    malo = nuevo | {"slug": "y", "entornos": [{"nombre": "p", "url": "u", "tipo": "produccion"}]}
    assert cliente.post("/api/proyectos", json=malo, headers=h).status_code == 400
