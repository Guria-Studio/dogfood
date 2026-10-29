import asyncio
from datetime import datetime

from PIL import Image

from dogfood.agente.bucle import DecisionPaso, ejecutar
from dogfood.agente.navegador import Veredicto
from dogfood.backends.base import UsoBackend
from dogfood.config import Config
from dogfood.dominio import ContratoRecorrido, Escenario, Evidencia, Persona
from dogfood.drivers.base import Accion, ElementoUI, Observacion, ResultadoAccion
from dogfood.eventos import BUS_NULO, BusVivo

CLAVE = "Cl4ve-Secreta-777"
FRAME = b"\xff\xd8jpeg-falso\xff\xd9"


def persona():
    return Persona(
        id="p1",
        nombre="Ana",
        email="ana@dogfood.test",
        contrasena=CLAVE,
        empresa="E",
        rubro="ropa",
        idioma="es",
        destreza=3,
        paciencia=3,
        intencion="explorar",
        semilla=1,
    )


def escenario(max_pasos=10):
    return Escenario(
        id="login",
        titulo="Login",
        objetivo="Entra a la app",
        criterio_exito="se ve la pantalla principal",
        max_pasos=max_pasos,
        contrato=ContratoRecorrido(
            estado_inicial="sin sesión",
            acciones=["escribir email", "escribir clave", "tocar entrar"],
            resultado_esperado="pantalla principal",
        ),
    )


def cfg(max_capturas=1, resolucion=256):
    return Config(
        roles={},
        agente={"max_capturas_por_paso": max_capturas, "resolucion_max": resolucion},
    )


ELEMENTOS = [
    ElementoUI(id="email", clase="EditText", bounds=(0, 0, 100, 40), editable=True),
    ElementoUI(id="clave", clase="EditText", bounds=(0, 50, 100, 90), editable=True),
    ElementoUI(id="entrar", texto="Entrar", bounds=(0, 100, 100, 140), clicable=True),
]


class DriverFalso:
    def __init__(self, nombre="android", elementos=ELEMENTOS, falla_en=None):
        self.nombre = nombre
        self.elementos = elementos
        self.falla_en = falla_en
        self.acciones: list[Accion] = []
        self.frames = 0
        self.cerrado = False
        self.carpeta = None

    async def iniciar(self, carpeta):
        self.carpeta = carpeta

    async def observar(self, n):
        await asyncio.sleep(0.01)
        if n == self.falla_en:
            raise RuntimeError("adb se cayó")
        png = self.carpeta / f"obs-{n}.png"
        Image.new("RGB", (1080, 2400), "white").save(png)
        return Observacion(
            pantalla=f".Pantalla{n}",
            elementos=self.elementos,
            texto_visible=f"texto {n}",
            captura=png,
            ts=datetime.now().astimezone(),
        )

    async def actuar(self, accion):
        self.acciones.append(accion)
        return ResultadoAccion(ok=True, punto=(50, 20))

    async def frame(self):
        self.frames += 1
        return FRAME

    async def evidencia(self):
        return [
            Evidencia(tipo="log", extracto="logcat"),
            Evidencia(tipo="video", ruta=self.carpeta / "video.mp4"),
        ]

    async def cerrar(self):
        self.cerrado = True


def decision(accion=None, **kw):
    base = {"razonamiento": "pienso", "paso_contrato": "p", "esperado": "algo", "accion": accion}
    return DecisionPaso(**(base | kw))


LOGIN = [
    decision(
        Accion(tipo="escribir", elemento="email", texto="ana@dogfood.test"), paso_contrato="1"
    ),
    decision(Accion(tipo="escribir", elemento="clave", texto=CLAVE), paso_contrato="2"),
    decision(Accion(tipo="tocar", elemento="entrar"), paso_contrato="3", terminado=True),
]


class BackendFalso:
    nombre = "claude_code"
    modelo = "falso-1"

    def __init__(self, decisiones):
        self.decisiones = list(decisiones)
        self.llamadas: list[dict] = []

    async def completar_json(self, prompt, esquema, *, imagenes=(), sesion=None):
        n = len(self.llamadas) + 1
        self.llamadas.append({"prompt": prompt, "imagenes": list(imagenes), "sesion": sesion})
        uso = UsoBackend(tokens_in=100, tokens_out=10, capturas=len(imagenes))
        if esquema is Veredicto:
            return Veredicto(exito=True, motivo="entró"), uso, None
        d = self.decisiones.pop(0) if self.decisiones else decision(Accion(tipo="volver"))
        return d, uso, f"s{n}"


async def correr(tmp_path, decisiones, *, driver=None, c=None, bus=BUS_NULO, esc=None):
    driver = driver or DriverFalso()
    backend, juez = BackendFalso(decisiones), BackendFalso([])
    e = await ejecutar(
        persona(),
        esc or escenario(),
        driver,
        backend,
        juez,
        tmp_path / "e1",
        cfg=c or cfg(),
        bus=bus,
        corrida_id="c1",
    )
    return e, driver, backend, juez


async def test_login_de_tres_pasos_aprobado(tmp_path):
    e, driver, backend, _juez = await correr(tmp_path, LOGIN)
    assert e.estado == "ok" and e.exito and e.motivo_juez == "entró"
    assert e.resultado == "aprobado"
    assert len(e.pasos) == 3 and len(driver.acciones) == 2  # el tercero termina sin actuar
    for p in e.pasos:
        assert p.razonamiento and p.esperado and p.observado and p.captura
    assert e.pasos[0].observado.startswith("ok; pantalla .Pantalla2")
    assert e.pasos[0].url == ".Pantalla1" and e.pasos[0].punto == (50, 20)
    assert (e.driver, e.motor, e.backend, e.modelo) == (
        "android",
        "bucle",
        "claude_code",
        "falso-1",
    )
    assert e.video and e.video.name == "video.mp4"
    assert [ev.tipo for ev in e.evidencia_driver] == ["log"]
    assert driver.cerrado
    assert len((tmp_path / "e1" / "pasos.jsonl").read_text().splitlines()) == 3
    assert "Estado inicial: sin sesión" in backend.llamadas[0]["prompt"]
    assert "[entrar] " in backend.llamadas[0]["prompt"]


async def test_sesion_del_paso_1_pasa_al_paso_2(tmp_path):
    _, _, backend, _ = await correr(tmp_path, LOGIN)
    assert [ll["sesion"] for ll in backend.llamadas] == [None, "s1", "s2"]


async def test_metricas_suman_persona_y_juez(tmp_path):
    e, *_ = await correr(tmp_path, LOGIN, driver=DriverFalso(elementos=[]))
    # 3 pasos + juez; las 3 decisiones llevan captura (árbol vacío)
    assert e.metricas.tokens_in == 400 and e.metricas.tokens_out == 40
    assert e.metricas.capturas == 3


async def test_sin_capturas_si_el_tope_es_cero(tmp_path):
    _, _, backend, _ = await correr(tmp_path, LOGIN, driver=DriverFalso(elementos=[]), c=cfg(0))
    assert all(ll["imagenes"] == [] for ll in backend.llamadas)


async def test_captura_reducida_con_arbol_vacio(tmp_path):
    _, _, backend, _ = await correr(tmp_path, LOGIN, driver=DriverFalso(elementos=[]), c=cfg(1))
    imgs = backend.llamadas[0]["imagenes"]
    assert len(imgs) == 1
    with Image.open(imgs[0]) as im:
        assert max(im.size) <= 256
    assert "captura" in backend.llamadas[0]["prompt"]


async def test_captura_solo_si_el_modelo_la_pide(tmp_path):
    guion = [decision(Accion(tipo="volver"), pedir_captura=True), *LOGIN]
    _, _, backend, _ = await correr(tmp_path, guion)
    assert [len(ll["imagenes"]) for ll in backend.llamadas] == [0, 1, 0, 0]


async def test_la_clave_nunca_sale(tmp_path):
    bus = BusVivo()
    sub = bus.suscribir(max_cola=1000)
    e, driver, *_ = await correr(tmp_path, LOGIN, bus=bus)
    assert driver.acciones[1].texto == CLAVE  # el driver sí la recibe
    assert all(CLAVE not in p.accion for p in e.pasos)
    assert "***" in e.pasos[1].accion
    eventos = []
    while not sub.cola.empty():
        eventos.append(sub.cola.get_nowait())
    assert eventos and all(CLAVE not in ev.model_dump_json() for ev in eventos)
    assert CLAVE not in (tmp_path / "e1" / "pasos.jsonl").read_text()


async def test_rendirse(tmp_path):
    e, *_ = await correr(tmp_path, [decision(rendirse="no entiendo nada")])
    assert e.estado == "rendido" and e.motivo_juez == "no entiendo nada"
    assert e.resultado == "fallo"


async def test_max_pasos(tmp_path):
    e, _driver, *_ = await correr(tmp_path, [], esc=escenario(max_pasos=3))
    assert (e.estado, e.motivo_juez) == ("fallo", "max_pasos")
    assert len(e.pasos) == 3


async def test_timeout(tmp_path):
    driver = DriverFalso()
    backend = BackendFalso([])
    e = await ejecutar(
        persona(),
        escenario(100),
        driver,
        backend,
        backend,
        tmp_path / "e1",
        cfg=cfg(),
        timeout_s=0.05,
    )
    assert (e.estado, e.motivo_juez) == ("fallo", "timeout")
    assert driver.cerrado


async def test_error_del_driver(tmp_path):
    e, driver, *_ = await correr(tmp_path, LOGIN, driver=DriverFalso(falla_en=3))
    assert e.estado == "error" and e.resultado == "no_concluyente"
    assert any("adb se cayó" in n for n in e.notas)
    assert driver.cerrado
    assert len(e.pasos) == 1  # lo registrado antes del fallo no se pierde


async def test_eventos_en_orden_con_bus_activo(tmp_path):
    bus = BusVivo()
    sub = bus.suscribir(max_cola=1000)
    await correr(tmp_path, LOGIN, bus=bus)
    eventos = []
    while not sub.cola.empty():
        eventos.append(sub.cola.get_nowait())
    tipos = [ev.tipo for ev in eventos]
    assert tipos[0] == "inicio" and tipos[-1] == "fin"
    assert eventos[-1].resultado == "aprobado"
    pasos = [ev for ev in eventos if ev.tipo == "paso"]
    assert [ev.n_paso for ev in pasos] == [1, 2, 3]
    assert [ev.paso_contrato for ev in pasos] == ["1", "2", "3"]
    frames = [ev for ev in eventos if ev.tipo == "frame"]
    assert frames and frames[0].frame_jpeg_b64
    assert all(ev.corrida_id == "c1" and ev.ejecucion_id == "e1" for ev in eventos)


async def test_sin_bus_no_se_piden_frames(tmp_path):
    _, driver, *_ = await correr(tmp_path, LOGIN)
    assert driver.frames == 0
