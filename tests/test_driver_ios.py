import base64
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from dogfood.drivers import Accion
from dogfood.drivers.ios import DriverIos

FIX = Path(__file__).parent / "fixtures" / "ios"
URL = "http://127.0.0.1:4723"
BUNDLE = "com.example.Runner"
S = "/session/sid1"


def png(w=1170, h=2532) -> bytes:
    b = BytesIO()
    Image.new("RGB", (w, h), "white").save(b, "PNG")
    return b.getvalue()


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


class Appium:
    def __init__(self, sesion_viva=True):
        self.peticiones: list[tuple[str, str, dict | None]] = []
        self.sesion_viva = sesion_viva

    def __call__(self, req: httpx.Request) -> httpx.Response:
        ruta = req.url.path
        cuerpo = json.loads(req.content) if req.content else None
        self.peticiones.append((req.method, ruta, cuerpo))
        if not self.sesion_viva and req.method == "DELETE":
            return httpx.Response(404, json={"value": {"error": "invalid session id"}})
        v: object = None
        if ruta == "/session":
            v = {"sessionId": "sid1", "capabilities": {}}
        elif ruta == f"{S}/screenshot":
            v = b64(png())
        elif ruta == f"{S}/source":
            v = (FIX / "source_login.xml").read_text()
        elif ruta == f"{S}/window/rect":
            v = {"x": 0, "y": 0, "width": 390, "height": 844}
        elif ruta == f"{S}/element":
            v = {"element-6066-11e4-a52e-4f735466cecf": "wd9"}
        elif ruta == f"{S}/se/log":
            v = json.loads((FIX / "syslog.json").read_text())["value"]
        elif ruta == f"{S}/execute/sync" and cuerpo["script"] == "mobile: stopRecordingScreen":
            v = b64(b"mp4-falso")
        return httpx.Response(200, json={"value": v})

    def rutas(self):
        return [(m, r) for m, r, _ in self.peticiones]

    def cuerpo(self, ruta):
        return next(c for _, r, c in self.peticiones if r == ruta)


@pytest.fixture
async def ios(tmp_path):
    mock = Appium()
    d = DriverIos(
        URL, "UDID1", BUNDLE, cliente=httpx.AsyncClient(transport=httpx.MockTransport(mock))
    )
    await d.iniciar(tmp_path)
    await d.observar(1)
    mock.peticiones.clear()
    d.mock = mock
    return d


async def test_iniciar_capabilities_y_grabacion(tmp_path):
    mock = Appium()
    d = DriverIos(
        URL, "UDID1", BUNDLE, cliente=httpx.AsyncClient(transport=httpx.MockTransport(mock))
    )
    await d.iniciar(tmp_path)
    assert mock.cuerpo("/session") == {
        "capabilities": {
            "alwaysMatch": {
                "platformName": "iOS",
                "appium:automationName": "XCUITest",
                "appium:udid": "UDID1",
                "appium:bundleId": BUNDLE,
                "appium:mjpegServerPort": 9100,
                "appium:noReset": True,
                "appium:newCommandTimeout": 300,
            }
        }
    }
    assert mock.cuerpo(f"{S}/execute/sync")["script"] == "mobile: startRecordingScreen"
    assert all((tmp_path / s).is_dir() for s in ("capturas", "arboles", "video"))


async def test_observar(tmp_path):
    mock = Appium()
    d = DriverIos(URL, "U", BUNDLE, cliente=httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    await d.iniciar(tmp_path)
    o = await d.observar(3)
    assert (tmp_path / "capturas/paso-003.png").exists()
    assert (tmp_path / "arboles/paso-003.xml").exists()
    assert o.pantalla == "Iniciar sesión"
    por_id = {e.id: e for e in o.elementos}
    assert set(por_id) == {"Bienvenido", "email", "password", "Entrar"}  # sin el oculto
    assert por_id["Entrar"].bounds == (72, 1200, 1098, 1344)  # escala 3
    assert por_id["Entrar"].clicable and por_id["Entrar"].clase == "Button"
    assert por_id["email"].editable and por_id["password"].editable
    assert por_id["email"].texto == "Correo"
    assert o.cobertura.flutter and not o.cobertura.ciega and o.cobertura.interactivos == 4


async def test_tocar_entrar(ios):
    r = await ios.actuar(Accion(tipo="tocar", elemento="Entrar"))
    assert r.ok and r.punto == (585, 1272)
    acts = ios.mock.cuerpo(f"{S}/actions")["actions"][0]
    assert acts["parameters"] == {"pointerType": "touch"}
    assert acts["actions"] == [
        {"type": "pointerMove", "duration": 0, "x": 195, "y": 424},
        {"type": "pointerDown", "button": 0},
        {"type": "pause", "duration": 50},
        {"type": "pointerUp", "button": 0},
    ]


async def test_escribir_en_el_campo(ios):
    r = await ios.actuar(Accion(tipo="escribir", elemento="email", texto="a@b.co"))
    assert r.ok
    assert ios.mock.cuerpo(f"{S}/element") == {"using": "accessibility id", "value": "email"}
    assert ios.mock.cuerpo(f"{S}/element/wd9/value") == {"text": "a@b.co"}


async def test_escribir_con_teclado_sin_elemento_webdriver(ios):
    r = await ios.actuar(Accion(tipo="escribir", texto="hi"))
    assert r.ok
    teclas = ios.mock.cuerpo(f"{S}/actions")["actions"][0]
    assert teclas["type"] == "key" and teclas["actions"][0] == {"type": "keyDown", "value": "h"}


async def test_volver_desde_el_borde_izquierdo(ios):
    assert (await ios.actuar(Accion(tipo="volver"))).ok
    a = ios.mock.cuerpo(f"{S}/actions")["actions"][0]["actions"]
    assert a[0]["x"] == 1 and a[0]["y"] == 422
    assert a[3] == {"type": "pointerMove", "duration": 300, "x": 234, "y": 422}


async def test_abrir_y_cerrar_app(ios):
    await ios.actuar(Accion(tipo="abrir_app"))
    await ios.actuar(Accion(tipo="cerrar_app"))
    cuerpos = [c for _, r, c in ios.mock.peticiones if r.endswith("execute/sync")]
    assert cuerpos == [
        {"script": "mobile: activateApp", "args": [{"bundleId": BUNDLE}]},
        {"script": "mobile: terminateApp", "args": [{"bundleId": BUNDLE}]},
    ]


async def test_evidencia(ios, tmp_path):
    ev = await ios.evidencia()
    assert (tmp_path / "video/ios.mp4").read_bytes() == b"mp4-falso"
    log = next(e for e in ev if e.tipo == "log")
    texto = (tmp_path / "syslog.txt").read_text()
    assert "Runner[812]" in texto and "SpringBoard" not in texto
    assert "Unhandled Exception" in log.extracto and "EXC_BAD_ACCESS" in log.extracto
    assert "arrancó" not in log.extracto
    assert any(e.tipo == "video" for e in ev)


async def test_frame_limitado_a_uno_por_segundo(ios):
    f = await ios.frame()
    assert f and Image.open(BytesIO(f)).width <= 720
    ios.mock.peticiones.clear()
    assert await ios.frame() == f
    assert ios.mock.peticiones == []


def test_url_de_lan_falla():
    with pytest.raises(ValueError):
        DriverIos("http://192.168.1.20:4723", "U", BUNDLE)


async def test_cerrar_sin_sesion_no_lanza(tmp_path):
    mock = Appium(sesion_viva=False)
    d = DriverIos(URL, "U", BUNDLE, cliente=httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    await d.iniciar(tmp_path)
    await d.cerrar()
    await d.cerrar()
