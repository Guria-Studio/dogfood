"""Bucle propio observar → decidir → actuar (FR-27, FR-28, FR-30, FR-31) con cualquier `Driver`
y cualquier `BackendLlm`.

El modelo decide sobre el árbol de UI en texto; la captura solo viaja cuando el árbol no alcanza
o el modelo la pidió, reducida a `agente.resolucion_max` y con tope por paso (control de costo).
"""

import asyncio
import base64
import contextlib
import time
from pathlib import Path

from PIL import Image
from pydantic import BaseModel

from dogfood import contrato
from dogfood.agente import prompts, prompts_bucle
from dogfood.agente.juez import MOTIVO_NO_DISPONIBLE, JuezNoDisponible, juzgar
from dogfood.agente.navegador import N_CAPTURAS_JUEZ, TIMEOUT_S, friccion_automatica
from dogfood.backends.base import BackendLlm, UsoBackend
from dogfood.config import Config
from dogfood.dominio import Ejecucion, Escenario, Friccion, Gravedad, Paso, Persona
from dogfood.drivers.base import Accion, Driver, ElementoUI, arbol_a_texto
from dogfood.eventos import BUS_NULO, BusVivo, EventoVivo
from dogfood.frames import FuenteDeDriver, FuenteFrames
from dogfood.llm import ContadorUso
from dogfood.objetivos.base import Objetivo

N_HISTORIAL = 8
MIN_ELEMENTOS_UTILES = 3
INTERVALO_FRAME_S = {"web": 0.2, "android": 1.0, "ios": 1.0}


class DecisionPaso(BaseModel):
    razonamiento: str  # breve, para la columna de la vista
    paso_contrato: str  # qué paso del contrato persigue
    accion: Accion | None
    esperado: str  # qué debería pasar tras la acción
    friccion: str | None = None
    pedir_captura: bool = False
    terminado: bool = False
    rendirse: str | None = None


def _util(el: ElementoUI) -> bool:
    return el.clicable or el.editable or bool(el.texto or el.descripcion)


def _reducir(captura: Path, lado: int, destino: Path) -> Path:
    with Image.open(captura) as im:
        im.thumbnail((lado, lado))
        im.save(destino)
    return destino


async def _frames(fuente: FuenteFrames, bus: BusVivo, base: dict) -> None:
    while True:
        try:
            jpeg = await fuente.frame()
        except Exception:  # noqa: BLE001 - la vista nunca frena ni rompe la corrida (NFR-11)
            jpeg = None
        if jpeg:
            bus.publicar(
                EventoVivo(**base, tipo="frame", frame_jpeg_b64=base64.b64encode(jpeg).decode())
            )
        await asyncio.sleep(fuente.intervalo_s)


async def ejecutar(
    persona: Persona,
    escenario: Escenario,
    driver: Driver,
    backend: BackendLlm,
    juez: BackendLlm,
    carpeta: Path,
    *,
    cfg: Config,
    bus: BusVivo = BUS_NULO,
    corrida_id: str = "",
    objetivo: Objetivo | None = None,
    timeout_s: float = TIMEOUT_S,
    fuente_frames: FuenteFrames | None = None,
    contador: ContadorUso | None = None,
) -> Ejecucion:
    carpeta = Path(carpeta)
    para_llm = carpeta / "capturas"
    para_llm.mkdir(parents=True, exist_ok=True)

    def sin_clave(texto: str) -> str:
        return texto.replace(persona.contrasena, "***") if persona.contrasena else texto

    def pantalla(p: str) -> str:
        return objetivo.pantalla(p) if objetivo else p

    e = Ejecucion(
        id=carpeta.name,
        persona_id=persona.id,
        escenario_id=escenario.id,
        modelo=backend.modelo,
        estado="error",
        driver=driver.nombre,
        motor="bucle",
        backend=backend.nombre,
    )
    base = {
        "corrida_id": corrida_id,
        "ejecucion_id": e.id,
        "persona": persona.nombre,
        "escenario": escenario.id,
    }

    def sumar(uso: UsoBackend) -> None:
        m = e.metricas
        m.tokens_in += uso.tokens_in
        m.tokens_out += uso.tokens_out
        m.capturas += uso.capturas
        m.costo_usd += uso.costo_usd
        m.costo_equivalente_usd += uso.costo_equivalente_usd

    async def recorrer() -> tuple[str, str]:
        """Devuelve (estado, motivo); lo registrado queda en `e` aunque algo lance."""
        historial: list[str] = []
        previas: list[str] = []
        anotadas: set[str] = set()
        sesion: str | None = None
        pedir_captura = False
        obs = await driver.observar(1)
        for n in range(1, escenario.max_pasos + 1):
            imagenes: list[Path] = []
            tope = cfg.agente.max_capturas_por_paso
            utiles = sum(map(_util, obs.elementos))
            ciega = bool(obs.cobertura and obs.cobertura.ciega)
            if tope and obs.captura and (utiles < MIN_ELEMENTOS_UTILES or pedir_captura or ciega):
                reducida = para_llm / f"paso-{n:03d}-llm.png"
                imagenes = [_reducir(obs.captura, cfg.agente.resolucion_max, reducida)][:tope]
            tamano = None
            if ciega and obs.captura:
                with Image.open(obs.captura) as im:
                    tamano = im.size
            prompt = prompts_bucle.paso(
                persona,
                escenario,
                n=n,
                pantalla=obs.pantalla,
                arbol=arbol_a_texto(obs.elementos),
                texto_visible=obs.texto_visible,
                historial=historial[-N_HISTORIAL:],
                con_captura=bool(imagenes),
                ciega=ciega,
                tamano=tamano,
            )
            d, uso, sesion = await backend.completar_json(
                prompt, DecisionPaso, imagenes=imagenes, sesion=sesion
            )
            sumar(uso)
            pedir_captura = d.pedir_captura
            if d.friccion:
                e.fricciones.append(
                    Friccion(
                        texto=sin_clave(d.friccion),
                        severidad=Gravedad.media,
                        pantalla=pantalla(obs.pantalla),
                        captura=obs.captura,
                    )
                )

            accion, punto, siguiente, efecto = "", None, None, ""
            if d.rendirse:
                observado = f"se rinde: {d.rendirse}"
            elif d.terminado:
                observado = "da el objetivo por cumplido"
            else:
                if d.accion:
                    accion = d.accion.model_dump_json(exclude_none=True)
                    r = await driver.actuar(d.accion)
                    punto = r.punto
                    efecto = "ok" if r.ok else f"error: {r.error}"
                else:
                    efecto = "sin acción"
                siguiente = await driver.observar(n + 1)
                observado = (
                    f"{efecto}; pantalla {siguiente.pantalla}: {siguiente.texto_visible[:300]}"
                )

            previas.append(accion)
            if not d.rendirse and not d.terminado:
                textos = friccion_automatica(
                    accion, siguiente.texto_visible if siguiente else "", previas, anotadas
                )
                if accion and not efecto.startswith("ok") and efecto != "sin acción":
                    textos.append(f"La acción falló: {efecto[:200]}")
                for t in textos:
                    e.fricciones.append(
                        Friccion(
                            texto=sin_clave(t),
                            severidad=Gravedad.media,
                            pantalla=pantalla(obs.pantalla),
                            captura=obs.captura,
                        )
                    )

            if ciega and not imagenes:
                observado += "; pantalla ciega sin captura por configuración"
            paso = Paso(
                n=n,
                url=obs.pantalla,
                pantalla=pantalla(obs.pantalla),
                accion=sin_clave(accion),
                captura=obs.captura,
                texto_visible=sin_clave(obs.texto_visible),
                ts=obs.ts,
                razonamiento=sin_clave(d.razonamiento),
                paso_contrato=sin_clave(d.paso_contrato),
                esperado=sin_clave(d.esperado),
                observado=sin_clave(observado),
                arbol=obs.arbol,
                punto=punto,
                cobertura=obs.cobertura,
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
                    punto=punto,
                )
            )
            historial.append(f"{n}. {paso.accion or '(ninguna)'} → {paso.observado}")

            if d.rendirse:
                return "rendido", sin_clave(d.rendirse)
            if d.terminado:
                return "ok", ""
            obs = siguiente
        return "fallo", "max_pasos"

    inicio = time.monotonic()
    frames: asyncio.Task | None = None
    fuente: FuenteFrames | None = None
    plazo = asyncio.timeout(timeout_s)
    try:
        async with plazo:
            await driver.iniciar(carpeta)
            bus.publicar(EventoVivo(**base, tipo="inicio"))
            if bus.activo:
                fuente = fuente_frames or FuenteDeDriver(
                    driver, INTERVALO_FRAME_S.get(driver.nombre, 1.0)
                )
                await fuente.iniciar()
                frames = asyncio.create_task(_frames(fuente, bus, base))
            e.estado, e.motivo_juez = await recorrer()
    except Exception as exc:  # noqa: BLE001 - la ejecución queda como `error`, no se pierde
        if isinstance(exc, TimeoutError) and plazo.expired():
            e.estado, e.motivo_juez = "fallo", "timeout"
        else:
            e.notas.append(sin_clave(f"error del bucle: {exc!r}"))
    finally:
        if frames:
            frames.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await frames
        if fuente:
            try:
                await fuente.cerrar()
            except Exception as exc:  # noqa: BLE001 - cerrar la fuente nunca rompe la ejecución
                e.notas.append(sin_clave(f"no pude cerrar la fuente de frames: {exc!r}"))
        try:
            for ev in await driver.evidencia():
                if ev.tipo == "video":
                    e.video = ev.ruta
                elif ev.tipo == "trace":
                    e.trace = ev.ruta
                else:
                    e.evidencia_driver.append(ev)
        except Exception as exc:  # noqa: BLE001
            e.notas.append(sin_clave(f"sin evidencia del driver: {exc!r}"))
        try:
            await driver.cerrar()
        except Exception as exc:  # noqa: BLE001
            e.notas.append(sin_clave(f"error al cerrar el driver: {exc!r}"))

    if e.estado == "ok":
        prompt = prompts.juez(
            escenario,
            [p.texto_visible for p in e.pasos[-N_CAPTURAS_JUEZ:]],
            [],
            e.pasos[-1].razonamiento if e.pasos else "",
        )
        try:
            v = await juzgar(
                prompt, cfg, primero=juez, contador=contador, ejecucion_id=e.id, al_uso=sumar
            )
            e.exito, e.motivo_juez = v.exito, sin_clave(v.motivo)
        except JuezNoDisponible:  # sin veredicto: no concluyente, no fallo
            e.estado, e.motivo_juez = "error", MOTIVO_NO_DISPONIBLE

    e.duracion_s = round(time.monotonic() - inicio, 2)
    e.resultado = contrato.resultado(e)
    (carpeta / "pasos.jsonl").write_text("".join(p.model_dump_json() + "\n" for p in e.pasos))
    bus.publicar(EventoVivo(**base, tipo="fin", resultado=e.resultado))
    return e
