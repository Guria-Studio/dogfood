import socket
from pathlib import Path

import httpx
import pytest

from dogfood.config import Config
from dogfood.drivers.web import DriverWeb
from dogfood.objetivos.flutter_web import FlutterWebObjetivo

FIX = Path(__file__).parent / "fixtures" / "flutter_web"
RAIZ = Path(__file__).parent.parent


def _cfg(tmp_path: Path) -> Config:
    cfg = Config.cargar(RAIZ)
    cfg.flutter_web.puerto = 0  # el SO elige un puerto libre
    cfg.flutter_web.build_dir = None
    cfg.flutter_web.api_permitidas = ["http://127.0.0.1:9999"]
    cfg.flutter.copia_trabajo = tmp_path / "copias"
    cfg.flutter.sdk = Path("/sdk/bin/flutter")
    return cfg


class PaginaFalsa:
    def __init__(self, semantics: int = 0):
        self.semantics, self.llamadas = semantics, []

    async def wait_for_selector(self, sel, **kw):
        self.llamadas.append(("esperar", sel))

    async def evaluate(self, js):
        if "flt-semantics-placeholder" in js:
            self.llamadas.append(("clic", None))
            return True
        return self.semantics


@pytest.mark.asyncio
async def test_activa_el_placeholder_solo_con_flutter():
    for flutter, esperado in ((True, 1), (False, 0)):
        d = DriverWeb("http://x/", lambda u: True, {"width": 1, "height": 1}, flutter=flutter)
        d.page = PaginaFalsa()
        if flutter:
            await d._activar_semantics(esperar=True)
        assert sum(c[0] == "clic" for c in d.page.llamadas) == esperado


def _servir(tmp_path: Path, cfg: Config):
    build = tmp_path / "web"
    build.mkdir()
    (build / "index.html").write_text("<h1>hola</h1>")
    cfg.flutter_web.build_dir = build
    return FlutterWebObjetivo(cfg)


def test_preparar_sirve_y_destruir_cierra(tmp_path):
    cfg = _cfg(tmp_path)
    obj = _servir(tmp_path, cfg)
    inst = obj.preparar("main", None)
    assert inst.base_url.startswith("http://127.0.0.1:")
    assert inst.parametros["flutter"] is True
    assert httpx.get(inst.base_url).status_code == 200
    puerto = int(inst.base_url.rsplit(":", 1)[1].strip("/"))
    obj.destruir(inst)
    with pytest.raises(OSError), socket.create_connection(("127.0.0.1", puerto), timeout=1):
        pass


def test_host_publico_falla(tmp_path):
    cfg = _cfg(tmp_path)
    with pytest.raises(ValueError):
        type(cfg.flutter_web)(host="0.0.0.0")


def test_compila_en_la_copia_y_sirve_build_web(tmp_path):
    cfg = _cfg(tmp_path)
    app = tmp_path / "app"
    app.mkdir()
    (app / "pubspec.yaml").write_text("name: app\n")
    cfg.flutter.proyecto = app
    llamadas = []

    async def runner(args, *, cwd, env, timeout_s):
        llamadas.append((args, cwd))
        if args[0] == "rsync":
            (cfg.flutter.copia_trabajo / "app").mkdir(parents=True, exist_ok=True)
        elif args[1:5] == ["build", "web", "--release", "--no-web-resources-cdn"]:
            web = cwd / "build" / "web"
            web.mkdir(parents=True)
            (web / "index.html").write_text("ok")
        return 0, b"", b""

    obj = FlutterWebObjetivo(cfg, runner)
    inst = obj.preparar("main", None)
    try:
        build = [c for c in llamadas if c[0][1:3] == ["build", "web"]]
        assert len(build) == 1
        assert "--no-web-resources-cdn" in build[0][0]
        assert build[0][1] == cfg.flutter.copia_trabajo.resolve() / "app" != app
        assert inst.parametros["build_dir"] == str(build[0][1] / "build" / "web")
        assert httpx.get(inst.base_url).text == "ok"
    finally:
        obj.destruir(inst)


def test_url_permitida_y_pantalla(tmp_path):
    cfg = _cfg(tmp_path)
    obj = _servir(tmp_path, cfg)
    inst = obj.preparar("main", None)
    try:
        assert obj.url_permitida(inst.base_url + "main.dart.js", inst)
        assert obj.url_permitida("http://127.0.0.1:9999/api/x", inst)
        assert not obj.url_permitida("https://otro.com/", inst)
    finally:
        obj.destruir(inst)
    assert obj.pantalla("http://127.0.0.1:7480/#/login") == "login"
    assert obj.pantalla("http://127.0.0.1:7480/") == "inicio"
    assert {e.id for e in obj.escenarios()} == {"login", "explorar"}


@pytest.mark.integracion
@pytest.mark.asyncio
async def test_chromium_real_ve_los_semantics(tmp_path):
    d = DriverWeb(
        (FIX / "index.html").as_uri(), lambda u: True, {"width": 800, "height": 600}, flutter=True
    )
    await d.iniciar(tmp_path)
    try:
        obs = await d.observar(1)
    finally:
        await d.evidencia()
        await d.cerrar()
    etiquetas = {e.texto: e for e in obs.elementos}
    assert etiquetas["Email"].editable and etiquetas["Contraseña"].editable
    assert etiquetas["Entrar"].clicable
    assert obs.cobertura and obs.cobertura.flutter and not obs.cobertura.ciega
