import json
from pathlib import Path

import httpx
from typer.testing import CliRunner

from dogfood.cli import app
from dogfood.deterministico import ResultadoDeterministico, ResultadoTest
from dogfood.dominio import Escenario
from dogfood.nodos.protocolo import ResultadoTrabajo, Trabajo
from dogfood.nodos.runner import ejecutar, estado_nodo

XCTRACE = """== Devices ==
Mac de Héctor (14.4.1) (00006000-AAAA)
iPhone de Héctor (17.4.1) (00008110-001234567890401E)

== Simulators ==
iPhone 15 Simulator (17.4) (11111111-2222-3333-4444-555555555555)
"""


def fake_runner(salidas):
    async def run(args, *, cwd, env, timeout_s):
        for prefijo, out in salidas.items():
            if " ".join(args).startswith(prefijo):
                return 0, out.encode(), b""
        raise FileNotFoundError(args[0])

    return run


def cliente(vivo):
    return httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200) if vivo() else httpx.Response(503)
        )
    )


async def test_estado_nodo():
    r = fake_runner(
        {
            "xcodebuild": "Xcode 15.3\nBuild version 15E204a\n",
            "xcrun": XCTRACE,
            "patrol": "patrol_cli v3.0.0\n",
            "flutter": '{"frameworkVersion": "3.19.0"}',
        }
    )
    e = await estado_nodo(r, cliente(lambda: True))
    assert (e.xcode, e.flutter, e.patrol, e.appium) == ("15.3", "3.19.0", "patrol_cli v3.0.0", True)
    assert [d["udid"] for d in e.dispositivos if "iPhone de" in d["nombre"]] == [
        "00008110-001234567890401E"
    ]
    assert all("Simulator" not in d["nombre"] for d in e.dispositivos)


async def test_estado_sin_xcodebuild():
    e = await estado_nodo(fake_runner({}), cliente(lambda: False))
    assert e.xcode is None and e.flutter is None and not e.appium and e.dispositivos == []


async def test_patrol_usa_el_corredor(tmp_path):
    llamadas = []

    class Corredor:
        async def correr(self, escenario, herramienta, dispositivo, carpeta, *, proyecto=None):
            llamadas.append((herramienta, dispositivo, carpeta, proyecto))
            (carpeta / "deterministico").mkdir(parents=True)
            log = carpeta / "deterministico" / "salida.log"
            log.write_text("ok")
            return ResultadoDeterministico(
                herramienta="patrol",
                codigo_salida=0,
                tests=[ResultadoTest(nombre="login", estado="ok")],
                log=log,
            )

    esc = Escenario(id="login", titulo="Login", objetivo="x", criterio_exito="entra")
    t = Trabajo(id="t1", tipo="patrol", udid="U1", proyecto="/app", escenario=esc)
    r = await ejecutar(t, tmp_path, fake_runner({}), Corredor())
    assert llamadas == [("patrol", "U1", tmp_path / "t1", Path("/app"))]
    assert r.estado == "ok"
    assert r.deterministico.log == Path("deterministico/salida.log")
    assert "deterministico/salida.log" in r.artefactos


async def test_sesion_appium_arranca_y_cierra(tmp_path):
    vivo = {"v": False}
    arranques = []

    def arrancar(log):
        arranques.append(log)
        vivo["v"] = True
        return 4242

    muertos = []
    kw = {"arrancar": arrancar, "matar": muertos.append, "cliente": cliente(lambda: vivo["v"])}
    r = await ejecutar(Trabajo(id="s", tipo="sesion_appium"), tmp_path, **kw)
    assert arranques == [tmp_path / "appium.log"]
    assert (r.appium_url, r.mjpeg_url) == ("http://127.0.0.1:4723", "http://127.0.0.1:9100")
    assert (tmp_path / "appium.pid").read_text() == "4242"
    await ejecutar(Trabajo(id="c", tipo="cerrar_sesion"), tmp_path, **kw)
    assert muertos == [4242] and not (tmp_path / "appium.pid").exists()


async def test_appium_ajeno_no_se_arranca_ni_se_mata(tmp_path):
    muertos = []
    kw = {
        "arrancar": lambda log: 1 / 0,
        "matar": muertos.append,
        "cliente": cliente(lambda: True),
    }
    r = await ejecutar(Trabajo(id="s", tipo="sesion_appium"), tmp_path, **kw)
    assert r.estado == "ok"
    await ejecutar(Trabajo(id="c", tipo="cerrar_sesion"), tmp_path, **kw)
    assert muertos == []


def test_cli_ejecutar_ultima_linea_es_resultado(tmp_path):
    t = Trabajo(id="e1", tipo="cerrar_sesion")
    r = CliRunner().invoke(
        app, ["nodo", "ejecutar", "--dir-trabajo", str(tmp_path)], input=t.model_dump_json()
    )
    assert r.exit_code == 0
    res = ResultadoTrabajo.model_validate_json(r.output.strip().splitlines()[-1])
    assert res.id == "e1" and res.estado == "ok"


def test_cli_json_invalido(tmp_path):
    r = CliRunner().invoke(
        app, ["nodo", "ejecutar", "--dir-trabajo", str(tmp_path)], input="{no es json"
    )
    assert r.exit_code == 0
    assert ResultadoTrabajo.model_validate_json(r.output.strip().splitlines()[-1]).estado == "error"
    assert json.loads(r.output.strip().splitlines()[-1])["estado"] == "error"


def test_help_lista_nodo():
    assert "nodo" in CliRunner().invoke(app, ["--help"]).output
