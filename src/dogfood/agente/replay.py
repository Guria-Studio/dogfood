"""Replay (FR-17): repite el historial de browser-use sin LLM en una instancia limpia y comprueba
si la huella del hallazgo vuelve a aparecer."""

import asyncio
import json
import os
import re
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Literal

from dogfood.almacen import Almacen
from dogfood.deteccion import friccion, tecnicos
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    DatasetSintetico,
    Ejecucion,
    EventoConsola,
    EventoRed,
    Hallazgo,
    Instancia,
    Paso,
    Persona,
    TipoHallazgo,
)
from dogfood.objetivos.base import Objetivo

Resultado = Literal["reproduce", "no_reproduce", "no_reproducible_por_cambio_ui"]
Detector = Callable[[ContextoDeteccion], list[Hallazgo]]


class ErrorRerun(Exception):
    """El historial falló en el paso `paso` (1-based, como `Paso.n`)."""

    def __init__(self, paso: int, detalle: str = ""):
        super().__init__(f"el historial falló en el paso {paso}: {detalle}")
        self.paso = paso


# (ruta_historial, instancia, persona, dataset, carpeta) -> ejecución observada en la repetición
Rerun = Callable[[Path, Instancia, Persona, DatasetSintetico | None, Path], Awaitable[Ejecucion]]


async def rerun_browser_use(
    historial: Path,
    instancia: Instancia,
    persona: Persona,
    dataset: DatasetSintetico | None,
    carpeta: Path,
) -> Ejecucion:
    """`Agent.rerun_history` con un LLM que nunca se llama; captura red y consola con Playwright.

    ponytail: sin captura por paso, solo la pantalla final; basta para los detectores técnicos.
    """
    os.environ["ANONYMIZED_TELEMETRY"] = "false"
    os.environ["BROWSER_USE_CLOUD_SYNC"] = "false"
    from browser_use import Agent, BrowserSession
    from browser_use.agent.views import AgentHistoryList
    from playwright.async_api import async_playwright

    from dogfood.agente.navegador import ESCRITORIO, MOVIL, de_browser_use

    e = Ejecucion(
        id=carpeta.name,
        persona_id=persona.id,
        escenario_id="replay",
        dataset_id=dataset.id if dataset else None,
        modelo="sin-llm",
        estado="error",
    )
    async with async_playwright() as pw:
        with tempfile.TemporaryDirectory(prefix="dogfood-replay-") as perfil:
            movil = "movil" in persona.estilo
            ctx = await pw.chromium.launch_persistent_context(
                perfil,
                headless=True,
                viewport=MOVIL if movil else ESCRITORIO,
                locale=persona.idioma.value,
                args=["--remote-debugging-port=0"],
            )
            ctx.on(
                "response",
                lambda r: (
                    r.status >= 400
                    and e.red.append(
                        EventoRed(metodo=r.request.method, url=r.url, estado=r.status, ms=0)
                    )
                ),
            )
            ctx.on(
                "console",
                lambda m: (
                    m.type in ("error", "warning")
                    and not de_browser_use(m.location.get("url", ""))
                    and e.consola.append(
                        EventoConsola(nivel=m.type, texto=m.text, url=m.location.get("url", ""))
                    )
                ),
            )
            try:
                puerto = (Path(perfil) / "DevToolsActivePort").read_text().split()[0]
                sesion = BrowserSession(
                    cdp_url=f"http://127.0.0.1:{puerto}", keep_alive=True, no_viewport=True
                )
                agente = Agent(task="replay", llm=_LlmMudo(), browser_session=sesion)
                historia = AgentHistoryList.load_from_file(historial, agente.AgentOutput)
                try:
                    await agente.rerun_history(historia, max_retries=1, skip_failures=False)
                except RuntimeError as exc:
                    m = re.match(r"Step (\d+) failed", str(exc))
                    # el paso 0 son las acciones iniciales: el primero real es el 1
                    raise ErrorRerun(int(m[1]) if m else 1, str(exc)) from exc
                p = ctx.pages[-1] if ctx.pages else None
                if p:
                    texto = await p.inner_text("body", timeout=5000)
                    e.pasos.append(
                        Paso(
                            n=len(historia.history),
                            url=p.url,
                            pantalla=p.url,
                            accion="replay",
                            texto_visible=texto,
                            ts=datetime.now().astimezone(),
                        )
                    )
                e.estado = "ok"
            finally:
                await ctx.close()
    return e


class _LlmMudo:
    """rerun_history no llama al LLM salvo en pasos `extract`; si ocurre, que falle fuerte."""

    model = "sin-llm"
    provider = "dogfood"
    name = "sin-llm"
    model_name = "sin-llm"

    async def ainvoke(self, *a, **kw):
        raise RuntimeError("el replay no usa LLM")


def detectores_de(h: Hallazgo, objetivo: Objetivo) -> list[Detector]:
    """Solo los detectores que pueden producir el tipo del hallazgo original."""
    if h.tipo is TipoHallazgo.tecnico:
        return [tecnicos.detectar]
    if h.tipo is TipoHallazgo.friccion:
        return [friccion.detectar]
    return list(objetivo.verificadores())


def _paso_hallazgo(original: Ejecucion, h: Hallazgo) -> int:
    """Primer paso original en la pantalla del hallazgo; si no hay, el último paso."""
    for p in original.pasos:
        if p.pantalla == h.pantalla:
            return p.n
    return len(original.pasos)


def _buscar(almacen: Almacen, ident: str) -> tuple[str, Ejecucion, list[Hallazgo]]:
    """(corrida_id, ejecución, hallazgos a repetir) para un hallazgo_id o un ejecucion_id."""
    try:
        h = almacen.hallazgo(ident)
    except KeyError:
        h = None
    if h is not None:
        if not h.ejecucion_id:
            raise ValueError(f"el hallazgo {ident} no tiene ejecución asociada")
        corrida_id, eid, hallazgos = ident.rsplit("-H", 1)[0], h.ejecucion_id, [h]
    else:
        with closing(almacen._con()) as con:
            r = con.execute("SELECT corrida_id FROM ejecuciones WHERE id = ?", (ident,)).fetchone()
        if r is None:
            raise KeyError(f"no existe el hallazgo ni la ejecución {ident!r}")
        corrida_id, eid = r["corrida_id"], ident
        todos = json.loads((almacen.dir_corrida(corrida_id) / "hallazgos.json").read_text())
        hallazgos = [Hallazgo.model_validate(d) for d in todos if d.get("ejecucion_id") == eid]
    return corrida_id, almacen.ejecucion(eid), hallazgos


def _dataset(almacen: Almacen, corrida_id: str, e: Ejecucion) -> DatasetSintetico | None:
    if not e.dataset_id:
        return None
    d = almacen.dir_dataset(corrida_id, e.dataset_id)
    csv, verdad = next(d.glob("*.csv"), None), next(d.glob("*.json"), None)
    if csv is None or verdad is None:
        return None
    return DatasetSintetico(
        id=e.dataset_id, perfil="", ruta_csv=csv, ruta_verdad=verdad, n_clientes=0, n_filas=0,
        semilla=0,
    )  # fmt: skip


async def replay(
    ident: str,
    *,
    almacen: Almacen,
    objetivo: Objetivo,
    ref: str = "main",
    rerun: Rerun = rerun_browser_use,
    cliente_api: Callable | None = None,
) -> list[tuple[Hallazgo, Resultado]]:
    """Repite la ejecución de `ident` y devuelve el resultado por cada hallazgo."""
    corrida_id, original, hallazgos = _buscar(almacen, ident)
    if not hallazgos:
        return []
    if original.ruta_historial is None:
        raise ValueError(f"la ejecución {original.id} no guardó historial")
    corrida0 = Corrida.model_validate_json(
        (almacen.dir_corrida(corrida_id) / "corrida.json").read_text()
    )
    personas = json.loads((almacen.dir_corrida(corrida_id) / "personas.json").read_text())
    persona = next(Persona.model_validate(p) for p in personas if p["id"] == original.persona_id)
    dataset = _dataset(almacen, corrida_id, original)
    corrida = corrida0.model_copy(update={"id": f"replay-{original.id}", "ref": ref, "fin": None})

    instancia = await asyncio.to_thread(objetivo.preparar, ref, corrida)
    try:
        with tempfile.TemporaryDirectory(prefix=f"dogfood-{corrida.id}-") as tmp:
            carpeta = Path(tmp) / original.id
            carpeta.mkdir()
            fallo: ErrorRerun | None = None
            inicio = datetime.now().astimezone()
            try:
                nueva = await rerun(original.ruta_historial, instancia, persona, dataset, carpeta)
            except ErrorRerun as exc:
                fallo, nueva = (
                    exc,
                    original.model_copy(update={"pasos": [], "red": [], "consola": []}),
                )
            nuevos: list[Hallazgo] = []
            if fallo is None:
                ctx = ContextoDeteccion(
                    corrida=corrida.model_copy(update={"commit": instancia.commit}),
                    instancia=instancia,
                    ejecuciones=[nueva],
                    datasets={dataset.id: dataset} if dataset else {},
                    cliente_api=cliente_api or (lambda p: _cliente(instancia, persona)),
                    logs=await asyncio.to_thread(objetivo.logs, instancia, inicio),
                )
                vistos: set[int] = set()
                for h in hallazgos:
                    for det in detectores_de(h, objetivo):
                        if id(det) not in vistos:
                            vistos.add(id(det))
                            nuevos += det(ctx)
    finally:
        await asyncio.to_thread(objetivo.destruir, instancia)

    huellas = {n.huella for n in nuevos}
    salida: list[tuple[Hallazgo, Resultado]] = []
    for h in hallazgos:
        if h.huella in huellas:
            res: Resultado = "reproduce"
        elif fallo is not None and fallo.paso < _paso_hallazgo(original, h):
            res = "no_reproducible_por_cambio_ui"
        else:
            res = "no_reproduce"
        salida.append((h, res))
    return salida


def _cliente(instancia: Instancia, persona: Persona):
    from dogfood.objetivos.predicts.cliente import cliente_para

    return cliente_para(instancia, persona)
