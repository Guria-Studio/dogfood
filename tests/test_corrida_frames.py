"""F8.4.T3: la fuente de frames, la cobertura y Flutter web llegan al bucle y a la corrida."""

import asyncio
import base64

from test_bucle import LOGIN, BackendFalso, DriverFalso, cfg, escenario, persona
from test_corrida_motores import FalsoObjetivo, _ejecucion

from dogfood.agente.bucle import ejecutar
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.eventos import BUS_NULO, BusVivo

JPEG = b"\xff\xd8de-la-fuente\xff\xd9"


class FuenteFalsa:
    nombre = "falsa"
    intervalo_s = 0.01

    def __init__(self):
        self.iniciada = self.cerrada = 0

    async def iniciar(self):
        self.iniciada += 1

    async def frame(self):
        return JPEG

    async def cerrar(self):
        self.cerrada += 1


async def _bucle(tmp_path, bus, fuente):
    driver = DriverFalso()
    await ejecutar(
        persona(),
        escenario(),
        driver,
        BackendFalso(LOGIN),
        BackendFalso([]),
        tmp_path / "e1",
        cfg=cfg(),
        bus=bus,
        corrida_id="c1",
        fuente_frames=fuente,
    )
    return driver


async def test_bus_activo_publica_los_frames_de_la_fuente(tmp_path):
    bus, fuente = BusVivo(), FuenteFalsa()
    sub = bus.suscribir()
    driver = await _bucle(tmp_path, bus, fuente)
    frames = []
    while not sub.cola.empty():
        ev = sub.cola.get_nowait()
        if ev.tipo == "frame":
            frames.append(base64.b64decode(ev.frame_jpeg_b64))
    assert frames and set(frames) == {JPEG}
    assert driver.frames == 0
    assert (fuente.iniciada, fuente.cerrada) == (1, 1)


async def test_sin_bus_la_fuente_no_se_inicia(tmp_path):
    fuente = FuenteFalsa()
    await _bucle(tmp_path, BUS_NULO, fuente)
    assert (fuente.iniciada, fuente.cerrada) == (0, 0)


def _correr(tmp_path, cfg_extra, obj=None):
    llamadas = {}
    return llamadas, asyncio.run(_correr_async(tmp_path, cfg_extra, obj, llamadas))


async def _correr_async(tmp_path, cfg_extra, obj, llamadas):
    import dogfood.corrida as mod

    async def falso(persona, escenario, driver, backend, juez, carpeta, **kw):
        llamadas["driver"] = driver
        llamadas["fuente"] = kw.get("fuente_frames")
        return _ejecucion(carpeta, persona, escenario)

    original = mod.bucle.ejecutar
    mod.bucle.ejecutar = falso
    try:
        cfg_ = Config(roles={"persona": ["m"], "juez": ["m"]}, **cfg_extra)
        return await correr(
            Opciones(
                raiz=tmp_path,
                cfg=cfg_,
                objetivo_obj=obj or FalsoObjetivo(),
                llm=object(),
                semilla=7,
                sin_publicar=True,
                driver="android" if "pantalla" in cfg_extra else None,
                motor="bucle",
            )
        )
    finally:
        mod.bucle.ejecutar = original


def test_screenrecord_crea_el_driver_sin_grabar_video(tmp_path):
    ll, _ = _correr(tmp_path, {"pantalla": {"android": "screenrecord"}})
    assert ll["driver"].nombre == "android" and ll["driver"].grabar_video is False
    assert ll["fuente"] is None  # sin vista no se crea fuente


def test_screencap_conserva_el_video_del_driver(tmp_path):
    ll, _ = _correr(tmp_path, {"pantalla": {"android": "screencap"}})
    assert ll["driver"].grabar_video is True


def test_parametros_flutter_activa_flutter_en_el_driver_web(tmp_path):
    ll, _ = _correr(tmp_path, {}, FalsoObjetivo({"flutter": True}))
    assert ll["driver"].nombre == "web" and ll["driver"].flutter is True


def test_umbral_de_cobertura_llega_a_parametros_y_driver(tmp_path):
    obj = FalsoObjetivo()
    capturado = {}
    preparar = obj.preparar

    def espiar(ref, corrida):
        capturado["i"] = preparar(ref, corrida)
        return capturado["i"]

    obj.preparar = espiar
    ll, _ = _correr(tmp_path, {"flutter": {"umbral_cobertura": 0.8}}, obj)
    assert capturado["i"].parametros["umbral_cobertura"] == 0.8
    assert ll["driver"].umbral_cobertura == 0.8
