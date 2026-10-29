import base64
from pathlib import Path

import pytest

from dogfood.drivers.base import Accion
from dogfood.drivers.web import DriverWeb


class Llamadas:
    def __init__(self):
        self.l = []

    def __getattr__(self, nombre):
        async def f(*a, **k):
            self.l.append((nombre, a, k))

        return f


class PaginaFalsa:
    url = "http://app/"

    def __init__(self):
        self.mouse, self.keyboard, self.llamadas = Llamadas(), Llamadas(), Llamadas()

    def locator(self, sel):
        pagina = self

        class Loc:
            async def bounding_box(self):
                return {"x": 10, "y": 20, "width": 100, "height": 40}

            async def fill(self, texto):
                pagina.llamadas.l.append(("fill", (sel, texto), {}))

        return Loc()

    async def goto(self, url):
        self.llamadas.l.append(("goto", (url,), {}))

    async def go_back(self):
        self.llamadas.l.append(("go_back", (), {}))

    async def wait_for_timeout(self, ms):
        self.llamadas.l.append(("wait", (ms,), {}))


def driver(permitida=lambda u: u.startswith("http://app")):
    d = DriverWeb("http://app/", permitida, {"width": 800, "height": 600})
    d.page = PaginaFalsa()
    return d


async def test_tocar_por_id_y_coordenadas():
    d = driver()
    r = await d.actuar(Accion(tipo="tocar", elemento="e1"))
    assert r.ok and r.punto == (60, 40)
    assert d.page.mouse.l[0] == ("click", (60, 40), {})
    r = await d.actuar(Accion(tipo="tocar", x=5, y=6))
    assert r.punto == (5, 6) and d.page.mouse.l[1][1] == (5, 6)


async def test_escribir_tecla_volver_deslizar_esperar():
    d = driver()
    await d.actuar(Accion(tipo="escribir", elemento="e2", texto="hola"))
    await d.actuar(Accion(tipo="tecla", texto="Enter"))
    await d.actuar(Accion(tipo="volver"))
    await d.actuar(Accion(tipo="deslizar", x=100, y=500, x2=100, y2=100))
    await d.actuar(Accion(tipo="esperar", ms=50))
    assert d.page.llamadas.l[0] == ("fill", ('[data-dogfood-id="e2"]', "hola"), {})
    assert d.page.keyboard.l == [("press", ("Enter",), {})]
    assert ("go_back", (), {}) in d.page.llamadas.l
    assert d.page.mouse.l == [("wheel", (0, 400), {})]
    assert ("wait", (50,), {}) in d.page.llamadas.l


async def test_navegar_solo_a_urls_permitidas():
    d = driver()
    r = await d.actuar(Accion(tipo="navegar", texto="http://malo/"))
    assert not r.ok and d.page.llamadas.l == []
    r = await d.actuar(Accion(tipo="navegar", texto="http://app/x"))
    assert r.ok and d.page.llamadas.l == [("goto", ("http://app/x",), {})]


async def test_handler_de_frame_guarda_y_manda_ack():
    d = driver()
    d.cdp = Llamadas()
    await d._al_frame({"data": base64.b64encode(b"jpeg").decode(), "sessionId": 7})
    assert await d.frame() == b"jpeg"
    assert d.cdp.l == [("send", ("Page.screencastFrameAck", {"sessionId": 7}), {})]


@pytest.mark.integracion
async def test_chromium_real(tmp_path: Path):
    html = tmp_path / "f.html"
    html.write_text(
        "<form onsubmit='return false'><input aria-label='nombre'>"
        "<button id=b onclick=\"document.title='ok'\">Enviar</button></form>"
    )
    d = DriverWeb(html.as_uri(), lambda u: u.startswith("file:"), {"width": 800, "height": 600})
    salida = tmp_path / "run"
    await d.iniciar(salida)
    try:
        obs = await d.observar(1)
        assert obs.captura.exists() and obs.arbol.exists()
        campo = next(e for e in obs.elementos if e.editable)
        boton = next(e for e in obs.elementos if e.texto == "Enviar")
        assert boton.bounds[2] > boton.bounds[0]
        assert (await d.actuar(Accion(tipo="escribir", elemento=campo.id, texto="ana"))).ok
        assert (await d.actuar(Accion(tipo="tocar", elemento=boton.id))).punto
        assert await d.page.title() == "ok"
        await d.page.wait_for_timeout(500)
        f = await d.frame()
        assert f and f[:2] == b"\xff\xd8"
        evs = await d.evidencia()
        assert (salida / "trace.zip").stat().st_size > 0
        video = next(e for e in evs if e.tipo == "video")
        assert video.ruta.stat().st_size > 0
    finally:
        await d.cerrar()
