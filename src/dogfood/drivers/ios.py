"""Driver iOS (FR-38, FR-28, D29): protocolo W3C WebDriver de Appium (XCUITest) con httpx, sin Selenium."""

import asyncio
import base64
import contextlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from dogfood.dominio import Evidencia
from dogfood.drivers.android import _a_jpeg
from dogfood.drivers.base import Accion, ElementoUI, Observacion, ResultadoAccion
from dogfood.flutter.semantica import cobertura_xml
from dogfood.frames.base import validar_url_local

_PREFIJO = "XCUIElementType"
_CLICABLES = {"Button", "Cell", "Link", "Switch"}
_EDITABLES = {"TextField", "SecureTextField", "TextView"}
_TECLAS = {
    "ENTER": "",
    "RETURN": "",
    "BACKSPACE": "",
    "TAB": "",
    "ESCAPE": "",
}
_ELEMENTO_W3C = "element-6066-11e4-a52e-4f735466cecf"
_ERROR = re.compile(r"error|fault|crash|fatal|exception", re.IGNORECASE)


class AppiumError(RuntimeError):
    pass


def _toque(x: int, y: int) -> dict:
    return _puntero(
        [
            {"type": "pointerMove", "duration": 0, "x": x, "y": y},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 50},
            {"type": "pointerUp", "button": 0},
        ]
    )


def _puntero(acciones: list[dict]) -> dict:
    return {
        "type": "pointer",
        "id": "finger1",
        "parameters": {"pointerType": "touch"},
        "actions": acciones,
    }


def _deslizamiento(x1: int, y1: int, x2: int, y2: int, ms: int) -> dict:
    return _puntero(
        [
            {"type": "pointerMove", "duration": 0, "x": x1, "y": y1},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 50},
            {"type": "pointerMove", "duration": ms, "x": x2, "y": y2},
            {"type": "pointerUp", "button": 0},
        ]
    )


def _teclas(texto: str) -> dict:
    acciones = []
    for c in texto:
        acciones += [{"type": "keyDown", "value": c}, {"type": "keyUp", "value": c}]
    return {"type": "key", "id": "keyboard", "actions": acciones}


def parsear_fuente(xml: str, escala: float = 1.0) -> tuple[str, list[ElementoUI]]:
    """(pantalla, elementos) de la fuente de XCUITest; bounds en píxeles = puntos × escala."""
    raiz = ET.fromstring(xml.lstrip())
    pantalla = ""
    elementos: list[ElementoUI] = []
    for i, n in enumerate(raiz.iter()):
        if not n.tag.startswith(_PREFIJO):
            continue
        a = n.attrib
        clase = n.tag.removeprefix(_PREFIJO)
        if clase == "NavigationBar" and not pantalla:
            pantalla = a.get("name", "")
        if clase == "Window" and not pantalla:
            pantalla = a.get("name", "")
        if clase in ("Application", "Window") or a.get("visible") == "false":
            continue
        texto = a.get("label") or a.get("value") or ""
        clicable = clase in _CLICABLES or (clase == "Image" and a.get("accessible") == "true")
        editable = clase in _EDITABLES
        # los contenedores sin texto (Other, FlutterView…) no aportan nada al agente
        if not (texto or clicable or editable):
            continue
        try:
            x, y, w, h = (float(a[k]) for k in ("x", "y", "width", "height"))
        except (KeyError, ValueError):
            continue
        elementos.append(
            ElementoUI(
                id=a.get("name") or f"e{i}",
                texto=texto,
                clase=clase,
                bounds=(
                    round(x * escala),
                    round(y * escala),
                    round((x + w) * escala),
                    round((y + h) * escala),
                ),
                clicable=clicable,
                editable=editable,
            )
        )
    return pantalla, elementos


class DriverIos:
    nombre = "ios"

    def __init__(
        self,
        appium_url: str,
        udid: str,
        bundle_id: str,
        *,
        cliente: httpx.AsyncClient | None = None,
        umbral_cobertura: float = 0.6,
    ):
        self.appium_url = validar_url_local(appium_url).rstrip("/")
        self.udid = udid
        self.bundle_id = bundle_id
        self.umbral_cobertura = umbral_cobertura
        self._cliente = cliente
        self._propio = cliente is None
        self._sesion: str | None = None
        self._carpeta: Path | None = None
        self._elementos: dict[str, ElementoUI] = {}
        self._escala = 1.0
        self._ancho_pts: float | None = None
        self._frame: tuple[float, bytes | None] = (float("-inf"), None)

    async def _req(self, metodo: str, ruta: str, cuerpo: dict | None = None) -> Any:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(timeout=60)
        try:
            r = await self._cliente.request(metodo, self.appium_url + ruta, json=cuerpo)
        except httpx.HTTPError as e:
            raise AppiumError(f"Appium {metodo} {ruta}: {e}") from e
        try:
            valor = r.json().get("value")
        except ValueError:
            valor = None
        if r.is_error:
            msg = valor.get("message") if isinstance(valor, dict) else r.text[:200]
            raise AppiumError(f"Appium {metodo} {ruta} → {r.status_code}: {msg}")
        return valor

    def _s(self, ruta: str) -> str:
        assert self._sesion, "llama a iniciar() primero"
        return f"/session/{self._sesion}{ruta}"

    async def _mobile(self, comando: str, **args: Any) -> Any:
        return await self._req(
            "POST", self._s("/execute/sync"), {"script": f"mobile: {comando}", "args": [args]}
        )

    async def iniciar(self, carpeta: Path) -> None:
        self._carpeta = carpeta
        for sub in ("capturas", "arboles", "video"):
            (carpeta / sub).mkdir(parents=True, exist_ok=True)
        caps = {
            "platformName": "iOS",
            "appium:automationName": "XCUITest",
            "appium:udid": self.udid,
            "appium:bundleId": self.bundle_id,
            "appium:mjpegServerPort": 9100,
            "appium:noReset": True,
            "appium:newCommandTimeout": 300,
        }
        res = await self._req("POST", "/session", {"capabilities": {"alwaysMatch": caps}})
        self._sesion = res.get("sessionId") if isinstance(res, dict) else None
        if not self._sesion:
            raise AppiumError("Appium no devolvió sessionId")
        await self._mobile("startRecordingScreen")

    async def _captura(self) -> bytes:
        return base64.b64decode(await self._req("GET", self._s("/screenshot")))

    async def observar(self, n_paso: int) -> Observacion:
        assert self._carpeta is not None, "llama a iniciar() antes de observar()"
        png = await self._captura()
        captura = self._carpeta / "capturas" / f"paso-{n_paso:03d}.png"
        captura.write_bytes(png)
        xml = await self._req("GET", self._s("/source"))
        arbol = self._carpeta / "arboles" / f"paso-{n_paso:03d}.xml"
        arbol.write_text(xml, encoding="utf-8")
        pantalla, elementos = "", []
        cobertura = None
        try:
            app = next(ET.fromstring(xml.lstrip()).iter(_PREFIJO + "Application"), None)
            ancho_png = Image.open(BytesIO(png)).width
            if app is not None and float(app.get("width", 0)) > 0:
                self._ancho_pts = float(app.get("width"))
                self._escala = ancho_png / self._ancho_pts
            pantalla, elementos = parsear_fuente(xml, self._escala)
            # cobertura_xml espera la raíz XCUIElementType*, no el envoltorio <AppiumAUT>
            cobertura = cobertura_xml(
                ET.tostring(app, encoding="unicode") if app is not None else xml,
                umbral=self.umbral_cobertura,
                actividad="io.flutter" if "FlutterView" in xml else "",
            )
        except (ET.ParseError, OSError, ValueError):
            pass
        self._elementos = {e.id: e for e in elementos}
        return Observacion(
            pantalla=pantalla,
            elementos=elementos,
            texto_visible="\n".join(e.texto for e in elementos if e.texto),
            captura=captura,
            arbol=arbol,
            ts=datetime.now(),
            cobertura=cobertura,
        )

    def _punto(self, a: Accion) -> tuple[int, int]:
        if a.elemento is not None:
            el = self._elementos.get(a.elemento)
            if el is None:
                raise LookupError(f"El elemento {a.elemento!r} no existe en la última observación.")
            return el.centro
        if a.x is None or a.y is None:
            raise ValueError("Falta el elemento o las coordenadas x/y.")
        return a.x, a.y

    def _pts(self, x: int, y: int) -> tuple[int, int]:
        return round(x / self._escala), round(y / self._escala)

    async def _acciones(self, *acciones: dict) -> None:
        await self._req("POST", self._s("/actions"), {"actions": list(acciones)})

    async def _tocar(self, punto: tuple[int, int]) -> None:
        await self._acciones(_toque(*self._pts(*punto)))

    async def actuar(self, accion: Accion) -> ResultadoAccion:
        try:
            punto = None
            match accion.tipo:
                case "tocar":
                    punto = self._punto(accion)
                    await self._tocar(punto)
                case "escribir":
                    if accion.texto is None:
                        raise ValueError("Falta el texto a escribir.")
                    if accion.elemento is not None:
                        punto = self._punto(accion)
                        await self._tocar(punto)
                        wd_id = await self._id_webdriver(accion.elemento)
                        if wd_id:
                            await self._req(
                                "POST", self._s(f"/element/{wd_id}/value"), {"text": accion.texto}
                            )
                            return ResultadoAccion(ok=True, punto=punto)
                    await self._acciones(_teclas(accion.texto))
                case "deslizar":
                    punto = self._punto(accion)
                    if accion.x2 is None or accion.y2 is None:
                        raise ValueError("Falta x2/y2 para deslizar.")
                    await self._acciones(
                        _deslizamiento(
                            *self._pts(*punto), *self._pts(accion.x2, accion.y2), accion.ms or 300
                        )
                    )
                case "volver":
                    r = await self._rect()
                    y = round(r["height"] / 2)
                    await self._acciones(_deslizamiento(1, y, round(r["width"] * 0.6), y, 300))
                case "tecla":
                    if not accion.texto:
                        raise ValueError("Falta la tecla (p. ej. ENTER).")
                    await self._acciones(_teclas(_TECLAS.get(accion.texto.upper(), accion.texto)))
                case "abrir_app":
                    await self._mobile("activateApp", bundleId=accion.texto or self.bundle_id)
                case "cerrar_app":
                    await self._mobile("terminateApp", bundleId=accion.texto or self.bundle_id)
                case "esperar":
                    await asyncio.sleep((accion.ms or 1000) / 1000)
                case _:
                    raise ValueError(f"Acción {accion.tipo!r} no soportada en iOS.")
        except (AppiumError, LookupError, ValueError) as e:
            return ResultadoAccion(ok=False, error=str(e))
        return ResultadoAccion(ok=True, punto=punto)

    async def _rect(self) -> dict:
        return await self._req("GET", self._s("/window/rect"))

    async def _id_webdriver(self, elemento: str) -> str | None:
        if re.fullmatch(r"e\d+", elemento):
            return None
        try:
            res = await self._req(
                "POST", self._s("/element"), {"using": "accessibility id", "value": elemento}
            )
        except AppiumError:
            return None
        return res.get(_ELEMENTO_W3C) if isinstance(res, dict) else None

    async def frame(self) -> bytes | None:
        ts, cache = self._frame
        if time.monotonic() - ts < 1:
            return cache
        self._frame = (time.monotonic(), cache)
        try:
            jpeg = await asyncio.to_thread(_a_jpeg, await self._captura())
        except (AppiumError, OSError, ValueError):
            return cache
        self._frame = (time.monotonic(), jpeg)
        return jpeg

    async def evidencia(self) -> list[Evidencia]:
        assert self._carpeta is not None, "llama a iniciar() antes de evidencia()"
        salida: list[Evidencia] = []
        try:
            mp4 = await self._mobile("stopRecordingScreen")
            if mp4:
                ruta = self._carpeta / "video" / "ios.mp4"
                ruta.write_bytes(base64.b64decode(mp4))
                salida.append(Evidencia(tipo="video", ruta=ruta))
        except (AppiumError, ValueError):
            pass
        try:
            entradas = await self._req("POST", self._s("/se/log"), {"type": "syslog"}) or []
        except AppiumError:
            entradas = []
        proceso = self.bundle_id.rsplit(".", 1)[-1]
        lineas = [
            m
            for e in entradas
            if proceso in (m := e.get("message", "") if isinstance(e, dict) else str(e))
        ]
        log = self._carpeta / "syslog.txt"
        log.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        errores = [l for l in lineas if _ERROR.search(l)]
        salida.insert(0, Evidencia(tipo="log", ruta=log, extracto="\n".join(errores[-20:])))
        return salida

    async def cerrar(self) -> None:
        with contextlib.suppress(Exception):  # la sesión puede haber expirado: no lanzar
            if self._sesion:
                sesion, self._sesion = self._sesion, None
                await self._req("DELETE", f"/session/{sesion}")
        if self._propio and self._cliente is not None:
            with contextlib.suppress(Exception):
                await self._cliente.aclose()
