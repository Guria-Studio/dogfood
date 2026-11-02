"""Acceso de las personas a un proyecto `web` (F13.1.T2)."""

import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from dogfood import proyectos
from dogfood.agente import prompts
from dogfood.config import Config
from dogfood.contrato import resultado
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion, Instancia, Paso
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.web import WebObjetivo, acceso

CLAVE = "Sup3r-Secreta-9137"


class _App(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<title>Inicio</title>")

    def log_message(self, *a):
        pass


@pytest.fixture
def app():
    s = ThreadingHTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/"
    s.shutdown()


@pytest.fixture
def secretos(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "cfg" / "secretos").mkdir(parents=True)
    return tmp_path / "cfg" / "secretos"


def _crear(tmp_path, url, **acc):
    return proyectos.crear(
        {"slug": "mi-web", "nombre": "Mi web", "objetivo": "web", "url": url, "acceso": acc},
        tmp_path,
    )


def _op(tmp_path, **kw):
    return Opciones(
        objetivo="mi-web",
        raiz=tmp_path,
        cfg=Config(roles={"persona": ["m"], "juez": ["m"]}),
        llm=object(),
        semilla=3,
        **kw,
    )


@pytest.fixture
def navegador(monkeypatch):
    """Navegador falso: guarda el prompt completo y los kwargs que recibiría el agente."""
    vistos = []

    async def ejecutar(persona, escenario, instancia, dataset, carpeta, llm, juez, **kw):
        vistos.append(
            {"prompt": prompts.sistema(persona) + prompts.tarea(escenario, persona, None), **kw}
        )
        return Ejecucion(
            id=carpeta.name,
            persona_id=persona.id,
            escenario_id=escenario.id,
            modelo="m",
            estado="ok",
            exito=True,
            pasos=[_paso()],
            motivo_juez="ok",
        )

    async def generar(corrida, ejecuciones, hallazgos, personas, *, destino, **_):
        md = destino / "reporte.md"
        md.write_text("# r")
        return md, destino / "reporte.html"

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)
    monkeypatch.setattr("dogfood.corrida.issues.publicar", lambda *a, **k: [])
    monkeypatch.setattr("dogfood.corrida.opinion.generar", generar)
    monkeypatch.setattr("dogfood.corrida.slack.avisar", lambda *a, **k: True)
    return vistos


def test_usuario_prueba_no_filtra_la_contrasena(tmp_path, app, secretos, navegador, caplog):
    (secretos / "mi-web.env").write_text(f"DOGFOOD_PASSWORD={CLAVE}\n")
    p = _crear(tmp_path, app, modo="usuario_prueba", usuario="qa@mi-web.test")
    assert cargar_objetivo("web", p, tmp_path) and p.comportamiento.concurrencia == 1
    with caplog.at_level(logging.DEBUG):
        c = asyncio.run(correr(_op(tmp_path, personas=2)))
    assert c.estado == "ok", c.parametros
    assert len(navegador) == 2
    for v in navegador:
        assert CLAVE not in v["prompt"] and "qa@mi-web.test" in v["prompt"]
        assert "<secret>DOGFOOD_PASSWORD</secret>" in v["prompt"]
        assert v["sensitive_data"] == {"DOGFOOD_PASSWORD": CLAVE}  # solo por este canal
    assert CLAVE not in caplog.text
    for f in tmp_path.rglob("*"):  # base, ejecucion.json, reportes…
        if f.is_file() and "cfg" not in f.parts:
            assert CLAVE.encode() not in f.read_bytes(), f


def test_registro_mailpit_sigue_el_link(tmp_path, app, secretos):
    visitas = []

    class Cliente:
        def get(self, url, **kw):
            visitas.append(url)
            cuerpo = (
                {"messages": [{"ID": "m1"}]}
                if "/search" in url
                else {"Text": f"Confirma aquí: {app}confirmar?t=1 gracias"}
            )
            return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: cuerpo})()

    assert (
        acceso.link_de_confirmacion("http://mailpit:8025/", "a@dogfood.example.com", Cliente())
        == f"{app}confirmar?t=1"
    )
    assert visitas[0] == "http://mailpit:8025/api/v1/search"

    p = _crear(tmp_path, app, modo="registro", confirmacion="mailpit", mailpit_url="http://m:1")
    obj = WebObjetivo(p)
    persona = _persona()
    extra = obj.preparar_escenario(None, persona, _inst(app))
    assert [f.__name__ for f in extra["herramientas_extra"]] == ["confirmar_email"]
    assert "confirmar_email" in persona.instrucciones and "sensitive_data" not in extra


def test_registro_mailpit_ejecuta_la_herramienta(tmp_path, app, secretos, monkeypatch):
    pedidos = []
    monkeypatch.setattr(
        "dogfood.objetivos.web.acceso.link_de_confirmacion", lambda *a, **k: f"{app}ok"
    )
    monkeypatch.setattr("dogfood.objetivos.web.httpx.get", lambda url, **k: pedidos.append(url))
    p = _crear(tmp_path, app, modo="registro", confirmacion="mailpit", mailpit_url="http://m:1")
    obj = WebObjetivo(p)
    (herr,) = obj.preparar_escenario(None, _persona(), _inst(app))["herramientas_extra"]
    assert herr() == "Email confirmado." and pedidos == [f"{app}ok"]


def test_manual_queda_bloqueada_sin_ser_fallo(tmp_path, app, secretos):
    p = _crear(tmp_path, app, modo="registro", confirmacion="manual")
    persona = _persona()
    WebObjetivo(p).preparar_escenario(None, persona, _inst(app))
    assert "la app pide confirmar el email" in persona.instrucciones
    e = Ejecucion(
        id="E1",
        persona_id="p",
        escenario_id="e",
        modelo="m",
        estado="rendido",
        motivo_juez=f"{acceso.BLOQUEADO} {acceso.MOTIVO_CONFIRMAR}",
        pasos=[_paso()],
    )
    assert resultado(e) == "no_concluyente"
    e.motivo_juez = "no entendí la pantalla"
    assert resultado(e) == "fallo"


def test_sin_login_el_prompt_no_menciona_cuentas(tmp_path, app, secretos, navegador):
    _crear(tmp_path, app, modo="sin_login")
    c = asyncio.run(correr(_op(tmp_path)))
    assert c.estado == "ok", c.parametros
    prompt = navegador[0]["prompt"].lower()
    for palabra in ("cuenta", "contraseña", "email", "registr", "@"):
        assert palabra not in prompt
    assert "sensitive_data" not in navegador[0]


def test_secreto_faltante_falla_antes_de_lanzar(tmp_path, app, secretos, navegador):
    _crear(tmp_path, app, modo="usuario_prueba", usuario="qa@mi-web.test")
    c = asyncio.run(correr(_op(tmp_path)))
    assert navegador == [] and c.estado != "ok"
    assert c.estado == "error"
    with pytest.raises(acceso.ErrorAcceso, match="DOGFOOD_PASSWORD"):
        acceso.validar(proyectos.obtener("mi-web", tmp_path))


def _persona():
    from dogfood.personas.generador import generar

    return generar(1, 3, None)[0]


def _inst(url):
    return Instancia(base_url=url, api_url=url, proyecto_compose="x", commit="c")


def _paso():
    return Paso(n=1, accion="x", pantalla="i", captura="c.png", url="http://x/", ts=0)
