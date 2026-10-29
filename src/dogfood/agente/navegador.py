"""Agente navegador: una `Ejecucion` (persona × escenario) en un Chromium propio (D1, D2, FR-10).

Playwright lanza el Chromium y captura consola, red y bloqueos sin pasar por el LLM; browser-use
lo maneja por CDP con el LLM del rol `persona` y guarda las descargas.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel

from dogfood import contrato
from dogfood.agente import prompts
from dogfood.dominio import (
    DatasetSintetico,
    Ejecucion,
    Escenario,
    EventoConsola,
    EventoRed,
    Friccion,
    Gravedad,
    Instancia,
    Paso,
    Persona,
)
from dogfood.eventos import BUS_NULO, BusVivo, EventoVivo
from dogfood.llm import ContadorUso
from dogfood.objetivos.base import Objetivo

# La telemetría de browser-use envía el texto de la tarea, que lleva la contraseña (NFR-3).
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["BROWSER_USE_CLOUD_SYNC"] = "false"

from browser_use import Agent, BrowserSession, Tools
from browser_use.agent.views import ActionResult
from playwright.async_api import Error as ErrorPlaywright
from playwright.async_api import async_playwright

log = logging.getLogger("dogfood")

TIMEOUT_S = 15 * 60
ESCRITORIO = {"width": 1366, "height": 768}
MOVIL = {"width": 390, "height": 844}
N_CAPTURAS_JUEZ = 5
HOST_BROWSER_USE = "cf.browser-use.com"  # el logo de su animación de espera en about:blank


def de_browser_use(url: str) -> bool:
    """Recursos de browser-use, no de la app: se bloquean igual, pero no se registran."""
    return urlparse(url).netloc == HOST_BROWSER_USE


class Veredicto(BaseModel):
    exito: bool
    motivo: str


Juez = Callable[[str, type[Veredicto]], Awaitable[Veredicto]]


async def ejecutar(
    persona: Persona,
    escenario: Escenario,
    instancia: Instancia,
    dataset: DatasetSintetico | None,
    carpeta: Path,
    llm,
    juez: Juez,
    *,
    objetivo: Objetivo | None = None,
    contador: ContadorUso | None = None,
    timeout_s: float = TIMEOUT_S,
    herramientas_extra: list[Callable] | None = None,
    bus: BusVivo = BUS_NULO,
    corrida_id: str = "",
) -> Ejecucion:
    """`juez(prompt, Veredicto)` es `llm.completar_json` con el rol `juez` ya aplicado.

    Sin `objetivo`, solo se permiten los orígenes de `base_url` y `api_url`, y la pantalla es
    la ruta de la URL.
    """
    carpeta = Path(carpeta)
    capturas, descargas_dir = carpeta / "capturas", carpeta / "descargas"
    capturas.mkdir(parents=True, exist_ok=True)
    descargas_dir.mkdir(exist_ok=True)

    def permitida(url: str) -> bool:
        if objetivo:
            return objetivo.url_permitida(url, instancia)
        origenes = {urlparse(u).netloc for u in (instancia.base_url, instancia.api_url)}
        return urlparse(url).netloc in origenes

    def pantalla(url: str) -> str:
        return objetivo.pantalla(url) if objetivo else urlparse(url).path or "/"

    def sin_clave(texto: str) -> str:
        return texto.replace(persona.contrasena, "***") if persona.contrasena else texto

    e = Ejecucion(
        id=carpeta.name,
        persona_id=persona.id,
        escenario_id=escenario.id,
        dataset_id=dataset.id if dataset else None,
        modelo=llm.model,
        estado="error",
    )
    base = {
        "corrida_id": corrida_id,
        "ejecucion_id": e.id,
        "persona": persona.nombre,
        "escenario": escenario.id,
    }
    rendido: list[str] = []
    inicio = time.monotonic()

    async with async_playwright() as pw:
        perfil = tempfile.TemporaryDirectory(prefix="dogfood-perfil-")
        movil = "movil" in persona.estilo
        ctx = await pw.chromium.launch_persistent_context(
            perfil.name,
            headless=True,
            accept_downloads=True,
            viewport=MOVIL if movil else ESCRITORIO,
            is_mobile=movil,
            has_touch=movil,
            locale=persona.idioma.value,
            args=["--remote-debugging-port=0"],
            record_video_dir=carpeta / "video",
            record_video_size=MOVIL if movil else ESCRITORIO,
        )
        await ctx.tracing.start(screenshots=True, snapshots=True)
        bus.publicar(EventoVivo(**base, tipo="inicio"))

        async def al_frame(cdp, params: dict) -> None:
            if params.get("data"):
                bus.publicar(EventoVivo(**base, tipo="frame", frame_jpeg_b64=params["data"]))
            try:
                await cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
            except ErrorPlaywright:  # la página se cerró entre el frame y el ack
                pass

        async def iniciar_screencast() -> None:
            if not (bus.activo and ctx.pages):
                return
            try:
                cdp = await ctx.new_cdp_session(ctx.pages[0])
                cdp.on("Page.screencastFrame", lambda p: asyncio.ensure_future(al_frame(cdp, p)))
                await cdp.send(
                    "Page.startScreencast",
                    {"format": "jpeg", "quality": 60, "maxWidth": 1024, "everyNthFrame": 2},
                )
            except ErrorPlaywright:  # la vista nunca rompe la corrida (NFR-11)
                log.warning("no pude iniciar el screencast de %s", e.id)

        # --- captura por eventos de Playwright ---
        def ms(request) -> float:
            t = request.timing
            return max(t.get("responseEnd", -1), t.get("responseStart", -1), 0)

        def al_responder(r) -> None:
            if r.status >= 400:
                e.red.append(
                    EventoRed(metodo=r.request.method, url=r.url, estado=r.status, ms=ms(r.request))
                )

        def al_fallar(r) -> None:
            # Los bloqueos ya quedaron en `ruta`; ERR_ABORTED es una navegación que terminó en
            # descarga o que se canceló, no un fallo de la app.
            ignorados = ("net::ERR_BLOCKED_BY_CLIENT", "net::ERR_ABORTED")
            if r.failure not in ignorados and not de_browser_use(r.url):
                e.red.append(EventoRed(metodo=r.method, url=r.url, estado=0, ms=ms(r)))

        def al_loguear(m) -> None:
            url = m.location.get("url", "")
            if m.type in ("error", "warning") and not de_browser_use(url):
                e.consola.append(EventoConsola(nivel=m.type, texto=sin_clave(m.text), url=url))

        async def ruta(route) -> None:
            if permitida(route.request.url):
                await route.continue_()
            else:  # FR-3
                if not de_browser_use(route.request.url):
                    e.red.append(
                        EventoRed(
                            metodo=route.request.method, url=route.request.url, estado=0, ms=0
                        )
                    )
                await route.abort("blockedbyclient")

        ctx.on("response", al_responder)
        ctx.on("requestfailed", al_fallar)
        ctx.on("console", al_loguear)
        ctx.on(
            "weberror",
            lambda w: e.consola.append(EventoConsola(nivel="error", texto=sin_clave(str(w.error)))),
        )
        await ctx.route("**/*", ruta)

        puerto = (Path(perfil.name) / "DevToolsActivePort").read_text().split()[0]
        sesion = BrowserSession(
            cdp_url=f"http://127.0.0.1:{puerto}",
            keep_alive=True,
            no_viewport=True,  # manda el viewport de Playwright
            # browser-use toma el control de las descargas por CDP (el `download` de Playwright
            # queda vacío), así que las guarda él y aquí solo se listan.
            downloads_path=descargas_dir,
        )

        async def pagina():
            url = await sesion.get_current_page_url()
            return ([p for p in ctx.pages if p.url == url] or ctx.pages)[-1]

        async def fotografiar(nombre: str):
            p = await pagina()
            ruta_png = capturas / nombre
            try:
                await p.screenshot(path=ruta_png)
            except ErrorPlaywright:
                ruta_png = None
            return p, ruta_png

        # --- herramientas de la persona ---
        tools = Tools()

        @tools.action(
            "Anota una fricción: algo que te confunde, te molesta, te hace repetir o no entiendes. "
            "`cita` es el texto exacto de la pantalla que la causó."
        )
        async def anotar_friccion(texto: str, severidad: Gravedad, cita: str = "") -> ActionResult:
            p, ruta_png = await fotografiar(f"friccion-{len(e.fricciones) + 1:02d}.png")
            e.fricciones.append(
                Friccion(
                    texto=sin_clave(texto),
                    severidad=severidad,
                    pantalla=pantalla(p.url),
                    captura=ruta_png,
                    cita=sin_clave(cita),
                )
            )
            return ActionResult(extracted_content="Fricción anotada.")

        @tools.action("Abandona la app, como lo haría tu persona en este punto, con el motivo.")
        async def rendirse(motivo: str) -> ActionResult:
            rendido.append(sin_clave(motivo))
            return ActionResult(is_done=True, success=False, extracted_content=motivo)

        for f in herramientas_extra or []:
            tools.action(f.__doc__ or f.__name__)(f)

        async def al_terminar_paso(agente: Agent) -> None:
            h = agente.history.history[-1] if agente.history.history else None
            acciones = (
                [a.model_dump(exclude_none=True) for a in h.model_output.action]
                if h and h.model_output
                else []
            )
            n = len(e.pasos) + 1
            p, ruta_png = await fotografiar(f"paso-{n:03d}.png")
            try:
                texto = await p.inner_text("body", timeout=5000)
            except ErrorPlaywright:
                texto = ""
            salida = h.model_output if h else None
            razonamiento = (getattr(salida, "thinking", None) or "") if salida else ""
            meta = getattr(salida, "next_goal", None) or ""
            paso = Paso(
                n=n,
                url=p.url,
                pantalla=pantalla(p.url),
                accion=sin_clave(json.dumps(acciones, ensure_ascii=False, default=str)),
                captura=ruta_png,
                texto_visible=sin_clave(texto),
                ts=datetime.now().astimezone(),
                razonamiento=sin_clave(razonamiento or meta),
                paso_contrato=sin_clave(meta),
                esperado="",
                observado=sin_clave(getattr(salida, "evaluation_previous_goal", None) or ""),
            )
            e.pasos.append(paso)
            bus.publicar(
                EventoVivo(
                    **base,
                    tipo="paso",
                    n_paso=n,
                    paso_contrato=paso.paso_contrato,
                    razonamiento=paso.razonamiento,
                    accion=paso.accion,
                )
            )

        # browser-use solo sube archivos con ruta absoluta que esté en available_file_paths.
        ruta_csv = str(dataset.ruta_csv.resolve()) if dataset else None
        agente = Agent(
            task=prompts.tarea(escenario, persona, ruta_csv),
            llm=llm,
            browser_session=sesion,
            tools=tools,
            extend_system_message=prompts.sistema(persona),
            available_file_paths=[ruta_csv] if ruta_csv else None,
            initial_actions=[{"navigate": {"url": instancia.base_url, "new_tab": False}}],
            use_judge=False,
            enable_signal_handler=False,
            file_system_path=str(Path(perfil.name) / "fs"),
        )
        try:
            await iniciar_screencast()
            await asyncio.wait_for(
                agente.run(max_steps=escenario.max_pasos, on_step_end=al_terminar_paso), timeout_s
            )
        except TimeoutError:
            e.estado, e.motivo_juez = "fallo", "timeout"
        except Exception as exc:  # noqa: BLE001 - la ejecución queda como `error`, no se pierde
            e.notas.append(sin_clave(f"error del agente: {exc!r}"))
        else:
            if rendido:
                e.estado, e.motivo_juez = "rendido", rendido[-1]
            elif agente.history.is_done():
                e.estado = "ok"
            elif agente.state.n_steps > escenario.max_pasos:
                e.estado, e.motivo_juez = "fallo", "max_pasos"
            else:  # browser-use se detuvo solo, p. ej. por fallos seguidos
                e.notas.append(sin_clave(f"el agente se detuvo: {agente.history.errors()[-1:]}"))
        finally:
            e.descargas = sorted(descargas_dir.iterdir())
            agente.save_history(carpeta / "historial.json")  # local, puede llevar la contraseña
            e.ruta_historial = carpeta / "historial.json"
            await _registrar_uso(agente, contador, e)
            try:
                await sesion.stop()
            finally:
                try:
                    await ctx.tracing.stop(path=carpeta / "trace.zip")
                    e.trace = carpeta / "trace.zip"
                except ErrorPlaywright:
                    log.warning("no pude guardar el trace de %s", e.id)
                await ctx.close()  # cierra el video: el .webm se escribe aquí
                perfil.cleanup()
                e.video = next(iter(sorted((carpeta / "video").glob("*.webm"))), None)

    if e.estado == "ok":
        ultimo = agente.history.final_result() or str(agente.history.errors()[-1:])
        prompt = prompts.juez(
            escenario,
            [p.texto_visible for p in e.pasos[-N_CAPTURAS_JUEZ:]],
            [d.name for d in e.descargas],
            sin_clave(ultimo),
        )
        try:
            v = await juez(prompt, Veredicto)
            e.exito, e.motivo_juez = v.exito, sin_clave(v.motivo)
        except Exception as exc:  # noqa: BLE001 - sin veredicto, `exito` queda en False
            e.motivo_juez = sin_clave(f"el juez falló: {exc!r}")

    e.duracion_s = round(time.monotonic() - inicio, 2)
    e.resultado = contrato.resultado(e)
    bus.publicar(EventoVivo(**base, tipo="fin", resultado=e.resultado))
    for nombre, items in (("pasos", e.pasos), ("red", e.red), ("consola", e.consola)):
        (carpeta / f"{nombre}.jsonl").write_text("".join(i.model_dump_json() + "\n" for i in items))
    return e


async def _registrar_uso(agente: Agent, contador: ContadorUso | None, e: Ejecucion) -> None:
    # Del servicio y no de `history.usage`, que queda vacío si el timeout corta la corrida.
    uso = await agente.token_cost_service.get_usage_summary()
    for modelo, s in uso.by_model.items():
        e.metricas.tokens_in += s.prompt_tokens
        e.metricas.tokens_out += s.completion_tokens
        if contador:
            u = contador.registrar("persona", modelo, s.prompt_tokens, s.completion_tokens, e.id)
            e.metricas.costo_usd += u.costo_usd
            e.metricas.costo_equivalente_usd += u.costo_equivalente_usd
