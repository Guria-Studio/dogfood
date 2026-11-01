import asyncio

from fastapi.testclient import TestClient

from dogfood.config import Config, Nodo

SALIDA = (
    "List of devices attached\n"
    "100.64.1.2:5555 device model:Pixel_7\n"
    "192.168.0.10:5555 device model:Viejo\n"
)


def runner_adb(args, *, interactivo=False):
    return 0, SALIDA


class Fuente:
    nombre = "falsa"
    intervalo_s = 0.01

    def __init__(self):
        self.n = 0
        self.cerrada = False

    async def iniciar(self):
        pass

    async def frame(self):
        self.n += 1
        return b"\xff\xd8jpeg%d\xff\xd9" % self.n

    async def cerrar(self):
        self.cerrada = True


def _app_limpia(tmp_path, fuente=None):
    # app mínima: solo las rutas de dispositivos (las de crear_app_panel ya llevan /dispositivos)
    from fastapi import FastAPI

    from dogfood.panel import dispositivos

    app = FastAPI()
    cfg = Config.model_construct(nodos={"mac": Nodo(host="100.64.0.9", usuario="hector")})
    dispositivos.registrar_rutas(
        app,
        tmp_path,
        cfg,
        {"100.64.1.2:5555": fuente, "ios-mac": fuente} if fuente else None,
        runner_adb,
    )
    return app


def test_404(tmp_path):
    c = TestClient(_app_limpia(tmp_path))
    assert c.get("/dispositivos/nada/mjpeg").status_code == 404
    assert c.get("/dispositivos/192.168.0.10:5555/mjpeg").status_code == 404


def test_mjpeg(tmp_path):
    fuente = Fuente()
    app = _app_limpia(tmp_path, fuente)
    recibido = bytearray()
    cabeceras = {}
    parar = asyncio.Event()

    async def receive():
        await parar.wait()
        return {"type": "http.disconnect"}

    async def send(msg):
        if msg["type"] == "http.response.start":
            cabeceras.update({k.decode(): v.decode() for k, v in msg["headers"]})
        elif msg["type"] == "http.response.body":
            recibido.extend(msg.get("body", b""))
            if recibido.count(b"--frame") >= 2:
                parar.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/dispositivos/100.64.1.2:5555/mjpeg",
        "raw_path": b"/dispositivos/100.64.1.2:5555/mjpeg",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 1),
        "root_path": "",
    }
    asyncio.run(asyncio.wait_for(app(scope, receive, send), 5))
    assert cabeceras["content-type"].startswith("multipart/x-mixed-replace")
    assert "boundary=frame" in cabeceras["content-type"]
    assert recibido.count(b"image/jpeg") >= 2 and b"jpeg1" in recibido and b"jpeg2" in recibido
    assert fuente.cerrada
