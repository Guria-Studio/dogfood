"""Una corrida con un proyecto `web` genérico, sin nada de predicts (F13.1.T1)."""

import asyncio
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin

import httpx
import pytest

from dogfood import proyectos
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion
from dogfood.objetivos.web import WebObjetivo

PAGINAS = {
    "/": "<title>Inicio</title><a href='/contacto'>Contacto</a>",
    "/contacto": (
        "<title>Contacto</title><form method='post' action='/enviar'>"
        "<input name='email'><button>Enviar</button></form>"
    ),
}


class _App(BaseHTTPRequestHandler):
    def do_GET(self):
        cuerpo = PAGINAS.get(self.path)
        self.send_response(200 if cuerpo else 404)
        self.end_headers()
        self.wfile.write((cuerpo or "no").encode())

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def app():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/"
    s.shutdown()


@pytest.fixture
def entorno(monkeypatch):
    """Nada de predicts puede llamarse; el navegador falso recorre la app de verdad."""
    visitas = []

    def prohibido(*a, **k):
        raise AssertionError("la corrida web tocó predicts")

    for ruta in (
        "dogfood.objetivos.predicts.entorno.preparar",
        "dogfood.objetivos.predicts.cuentas.confirmar_registro",
        "dogfood.objetivos.predicts.cuentas.herramientas_extra",
        "dogfood.objetivos.predicts.cliente.cliente_para",
        "dogfood.corrida.opinion.contar_uso_ia",  # el web no cuenta uso de IA en un Postgres
    ):
        monkeypatch.setattr(ruta, prohibido)

    async def ejecutar(
        persona, escenario, instancia, dataset, carpeta, llm, juez, *, objetivo, contador
    ):
        assert dataset is None
        with httpx.Client(base_url=instancia.base_url) as http:
            for path in ("/", "/contacto"):
                url = urljoin(instancia.base_url, path)
                assert objetivo.url_permitida(url, instancia)
                assert http.get(path).status_code == 200
                visitas.append(objetivo.pantalla(url, "Inicio"))
            assert http.post("/enviar", data={"email": persona.email}).status_code == 303
        assert not objetivo.url_permitida("https://otro.example/", instancia)
        return Ejecucion(
            id=carpeta.name,
            persona_id=persona.id,
            escenario_id=escenario.id,
            modelo="m",
            estado="ok",
            exito=True,
        )

    async def generar(corrida, ejecuciones, hallazgos, personas, *, destino, **_):
        md = destino / "reporte.md"
        md.write_text(f"# {corrida.objetivo}: {len(ejecuciones)} ejecuciones")
        return md, destino / "reporte.html"

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)
    monkeypatch.setattr("dogfood.corrida.issues.publicar", lambda *a, **k: [])
    monkeypatch.setattr("dogfood.corrida.opinion.generar", generar)
    monkeypatch.setattr("dogfood.corrida.slack.avisar", lambda *a, **k: True)
    return visitas


def _op(tmp_path, **kw):
    return Opciones(
        objetivo="mi-web",
        raiz=tmp_path,
        cfg=Config(roles={"persona": ["m"], "juez": ["m"]}),
        llm=object(),
        semilla=3,
        **kw,
    )


def test_corrida_web_termina_con_ejecucion_y_reporte(tmp_path, app, entorno):
    proyectos.crear({"slug": "mi-web", "nombre": "Mi web", "objetivo": "web", "url": app}, tmp_path)
    c = asyncio.run(correr(_op(tmp_path)))  # el objetivo sale del registro, desde el proyecto
    assert c.estado == "ok", c.parametros
    assert c.objetivo == "web" and c.parametros["proyecto"] == "mi-web"
    assert entorno == ["Inicio", "contacto"]  # en "/" manda el título
    con = sqlite3.connect(tmp_path / "dogfood.db")
    assert con.execute("SELECT escenario_id, exito FROM ejecuciones").fetchall() == [
        ("exploracion-libre", 1)
    ]
    assert (tmp_path / c.id / "reporte.md").read_text() == "# web: 1 ejecuciones"


def test_host_prohibido_frena_antes_de_las_personas(tmp_path, entorno):
    p = proyectos.crear(
        {
            "slug": "mi-web",
            "nombre": "Mi web",
            "objetivo": "web",
            "url": "https://fluent.usebot.chat/",
            "levantar": "docker compose up -d",
            "hosts_prohibidos": ["usebot.chat"],
        },
        tmp_path,
    )
    llamadas = []
    obj = WebObjetivo.desde_proyecto(p, raiz=tmp_path, runner=lambda cmd, **k: llamadas.append(cmd))
    c = asyncio.run(correr(_op(tmp_path, objetivo_obj=obj)))
    assert c.estado == "error"
    assert "hosts_prohibidos" in c.parametros["motivo"]
    assert "nunca corre contra producción" in c.parametros["motivo"]
    assert entorno == []  # ninguna persona arrancó
    assert llamadas == []  # ni se levantó nada
    assert not list((tmp_path / c.id / "ejecuciones").iterdir())


def test_entorno_prohibido_tambien_frena(tmp_path, app, entorno):
    """La URL del entorno pisa la del objetivo después de preparar: la guardia la mira igual."""
    proyectos.crear(
        {
            "slug": "mi-web",
            "nombre": "Mi web",
            "objetivo": "web",
            "url": app,
            "entornos": [{"nombre": "prod", "url": "https://app.prod.example/"}],
            "hosts_prohibidos": ["prod.example"],
        },
        tmp_path,
    )
    c = asyncio.run(correr(_op(tmp_path, entorno="prod")))
    assert c.estado == "error" and "prod.example" in c.parametros["motivo"]
    assert entorno == []


def test_corrida_no_menciona_predicts_salvo_el_valor_por_defecto():
    fuente = Path(__file__).parents[1] / "src/dogfood/corrida.py"
    lineas = [ln for ln in fuente.read_text().splitlines() if re.search("predicts", ln)]
    assert lineas == ['    objetivo: str = "predicts"']
