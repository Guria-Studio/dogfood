"""Driver web sobre Playwright (FR-28, FR-31, FR-32): Chromium propio, screencast CDP, video y trace."""

import asyncio
import base64
import json
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from playwright.async_api import Error as ErrorPlaywright
from playwright.async_api import async_playwright

from dogfood.dominio import EventoConsola, EventoRed, Evidencia
from dogfood.drivers.base import Accion, ElementoUI, Observacion, ResultadoAccion
from dogfood.flutter.semantica import cobertura_elementos

ATRIBUTO = "data-dogfood-id"
BLOQUEOS_NO_FALLO = ("net::ERR_BLOCKED_BY_CLIENT", "net::ERR_ABORTED")

# Asigna `data-dogfood-id` (estable entre observaciones) y devuelve los elementos visibles.
JS_ELEMENTOS = """() => {
  const sel = 'button, a[href], input, select, textarea, [role], flt-semantics[role], flt-semantics[aria-label]';
  window.__dogfoodN = window.__dogfoodN || 0;
  const salida = [];
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    if (!el.hasAttribute('data-dogfood-id')) el.setAttribute('data-dogfood-id', 'e' + (++window.__dogfoodN));
    const tag = el.tagName.toLowerCase();
    const flt = tag === 'flt-semantics';
    const rol = el.getAttribute('role');
    salida.push({
      id: el.getAttribute('data-dogfood-id'),
      texto: (flt ? (el.getAttribute('aria-label') || el.innerText || '') : (el.innerText || el.value || '')).trim().slice(0, 200),
      descripcion: el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || '',
      clase: rol || tag,
      bounds: [r.left, r.top, r.right, r.bottom].map(Math.round),
      clicable: (flt && ['button', 'link', 'tab', 'checkbox', 'menuitem'].includes(rol)) || ['button', 'a', 'select'].includes(tag) || ['button', 'link', 'tab', 'menuitem'].includes(el.getAttribute('role')) || (tag === 'input' && ['submit', 'button', 'checkbox', 'radio'].includes(el.type)),
      editable: (flt && rol === 'textbox') || ['textarea'].includes(tag) || (tag === 'input' && !['submit', 'button', 'checkbox', 'radio'].includes(el.type)) || el.isContentEditable,
    });
  }
  return salida;
}"""

# Flutter web monta los Semantics solo si alguien activa el placeholder (FR-39, D30).
JS_ACTIVAR_SEMANTICS = """() => {
  const p = document.querySelector('flt-semantics-placeholder');
  if (!p) return false;
  p.click();
  return true;
}"""
JS_HAY_SEMANTICS = "() => document.querySelectorAll('flt-semantics').length"


class DriverWeb:
    nombre = "web"

    def __init__(
        self,
        url_inicial: str,
        permitida: Callable[[str], bool],
        viewport: dict[str, int],
        movil: bool = False,
        flutter: bool = False,
        umbral_cobertura: float = 0.6,
    ):
        self.flutter, self.umbral_cobertura = flutter, umbral_cobertura
        self.url_inicial, self.permitida, self.viewport, self.movil = (
            url_inicial,
            permitida,
            viewport,
            movil,
        )
        self.consola: list[EventoConsola] = []
        self.red: list[EventoRed] = []
        self._ultimo: bytes | None = None
        self._pw = self._perfil = self.ctx = self.page = self.cdp = None
        self._carpeta: Path | None = None
        self._cerrado = False

    async def iniciar(self, carpeta: Path) -> None:
        self._carpeta = Path(carpeta)
        for sub in ("capturas", "arboles", "video"):
            (self._carpeta / sub).mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()
        self._perfil = tempfile.TemporaryDirectory(prefix="dogfood-perfil-")
        self.ctx = await self._pw.chromium.launch_persistent_context(
            self._perfil.name,
            headless=True,
            viewport=self.viewport,
            is_mobile=self.movil,
            has_touch=self.movil,
            record_video_dir=self._carpeta / "video",
            record_video_size=self.viewport,
        )
        self.ctx.on("response", self._al_responder)
        self.ctx.on("requestfailed", self._al_fallar)
        self.ctx.on("console", self._al_loguear)
        self.ctx.on(
            "weberror",
            lambda w: self.consola.append(EventoConsola(nivel="error", texto=str(w.error))),
        )
        await self.ctx.route("**/*", self._ruta)
        await self.ctx.tracing.start(screenshots=True, snapshots=True)
        self.page = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
        self.cdp = await self.ctx.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", lambda p: asyncio.ensure_future(self._al_frame(p)))
        await self.cdp.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": 60, "maxWidth": 1024, "everyNthFrame": 2},
        )
        await self.page.goto(self.url_inicial)
        if self.flutter:
            await self._activar_semantics(esperar=True)

    async def _activar_semantics(self, esperar: bool = False) -> None:
        try:
            if esperar:
                await self.page.wait_for_selector(
                    "flutter-view, flt-glass-pane", state="attached", timeout=20_000
                )
            await self.page.evaluate(JS_ACTIVAR_SEMANTICS)
        except ErrorPlaywright:  # no es Flutter o tardó: la cobertura saldrá ciega
            pass

    # --- captura por eventos ---
    async def _ruta(self, route) -> None:
        if self.permitida(route.request.url):
            await route.continue_()
        else:  # FR-3
            self.red.append(
                EventoRed(metodo=route.request.method, url=route.request.url, estado=0, ms=0)
            )
            await route.abort("blockedbyclient")

    def _al_responder(self, r) -> None:
        if r.status >= 400:
            self.red.append(EventoRed(metodo=r.request.method, url=r.url, estado=r.status, ms=0))

    def _al_fallar(self, r) -> None:
        if r.failure not in BLOQUEOS_NO_FALLO:
            self.red.append(EventoRed(metodo=r.method, url=r.url, estado=0, ms=0))

    def _al_loguear(self, m) -> None:
        if m.type in ("error", "warning"):
            self.consola.append(
                EventoConsola(nivel=m.type, texto=m.text, url=m.location.get("url", ""))
            )

    async def _al_frame(self, params: dict) -> None:
        self._ultimo = base64.b64decode(params["data"])
        try:
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        except ErrorPlaywright:  # la página se cerró entre el frame y el ack
            pass

    # --- Driver ---
    async def observar(self, n_paso: int) -> Observacion:
        nombre = f"paso-{n_paso:03d}"
        captura = self._carpeta / "capturas" / f"{nombre}.png"
        arbol = self._carpeta / "arboles" / f"{nombre}.json"
        await self.page.screenshot(path=captura)
        aria = await self.page.locator("body").aria_snapshot()  # page.accessibility ya no existe
        arbol.write_text(json.dumps({"aria": aria}, ensure_ascii=False))
        if self.flutter and not await self.page.evaluate(JS_HAY_SEMANTICS):
            await self._activar_semantics()
            await self.page.wait_for_timeout(300)
        elementos = [ElementoUI(**e) for e in await self.page.evaluate(JS_ELEMENTOS)]
        cobertura = (
            cobertura_elementos(elementos, flutter=True, umbral=self.umbral_cobertura)
            if self.flutter
            else None
        )
        return Observacion(
            cobertura=cobertura,
            pantalla=self.page.url,
            elementos=elementos,
            texto_visible=await self.page.inner_text("body"),
            captura=captura,
            arbol=arbol,
            ts=datetime.now().astimezone(),
        )

    async def _centro(self, a: Accion) -> tuple[int, int]:
        if a.elemento:
            caja = await self.page.locator(f'[{ATRIBUTO}="{a.elemento}"]').bounding_box()
            if not caja:
                raise ValueError(f"elemento {a.elemento} no está en pantalla")
            return round(caja["x"] + caja["width"] / 2), round(caja["y"] + caja["height"] / 2)
        if a.x is None or a.y is None:
            raise ValueError("tocar necesita elemento o x/y")
        return a.x, a.y

    async def actuar(self, accion: Accion) -> ResultadoAccion:
        p, a = self.page, accion
        try:
            match a.tipo:
                case "tocar":
                    punto = await self._centro(a)
                    await p.mouse.click(*punto)
                    return ResultadoAccion(ok=True, punto=punto)
                case "escribir":
                    if a.elemento:
                        await p.locator(f'[{ATRIBUTO}="{a.elemento}"]').fill(a.texto or "")
                    else:
                        await p.keyboard.type(a.texto or "")
                case "tecla":
                    await p.keyboard.press(a.texto or "Enter")
                case "navegar":
                    if not a.texto or not self.permitida(a.texto):
                        return ResultadoAccion(ok=False, error=f"URL no permitida: {a.texto}")
                    await p.goto(a.texto)
                case "volver":
                    await p.go_back()
                case "deslizar":
                    x, y = a.x or 0, a.y or 0
                    # deslizar hacia arriba (y2 < y) baja la página
                    await p.mouse.wheel(x - (a.x2 if a.x2 is not None else x), y - (a.y2 or 0))
                case "esperar":
                    await p.wait_for_timeout(a.ms or 1000)
                case _:
                    return ResultadoAccion(ok=False, error=f"acción no soportada en web: {a.tipo}")
        except (ErrorPlaywright, ValueError) as exc:
            return ResultadoAccion(ok=False, error=str(exc))
        return ResultadoAccion(ok=True)

    async def frame(self) -> bytes | None:
        return self._ultimo

    async def evidencia(self) -> list[Evidencia]:
        if not self._cerrado:
            self._cerrado = True
            await self.ctx.tracing.stop(path=self._carpeta / "trace.zip")
            await self.ctx.close()  # escribe el video
        evs = [
            Evidencia(tipo="log", extracto=f"{e.nivel}: {e.texto}"[:500]) for e in self.consola
        ] + [Evidencia(tipo="red", extracto=f"{e.metodo} {e.url} {e.estado}") for e in self.red]
        for v in sorted((self._carpeta / "video").glob("*.webm")):
            evs.append(Evidencia(tipo="video", ruta=v))
        evs.append(Evidencia(tipo="trace", ruta=self._carpeta / "trace.zip"))
        return evs

    async def cerrar(self) -> None:
        if self.ctx and not self._cerrado:
            self._cerrado = True
            try:
                await self.ctx.close()
            except ErrorPlaywright:
                pass
        if self._pw:
            await self._pw.stop()
            self._pw = None
        if self._perfil:
            self._perfil.cleanup()
            self._perfil = None
