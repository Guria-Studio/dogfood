from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from dogfood.drivers import Accion
from dogfood.drivers.android import Adb, AdbError, DriverAndroid, escapar_texto, validar_destino

FIX = Path(__file__).parent / "fixtures" / "android"
PAQUETE = "com.example.app"
LOGCAT = (
    "I/ActivityManager(  100): Start proc com.example.app\n"
    "E/AndroidRuntime( 4321): FATAL EXCEPTION: main\n"
    "E/AndroidRuntime( 4321): java.lang.NullPointerException\n"
    "D/otro( 4321): ruido\n"
)


def png(w=1080, h=2400) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


class Falso:
    def __init__(self, ui=None, pid=b"4321\n"):
        self.llamadas: list[list[str]] = []
        self.ui = (FIX / "ui_dump.xml").read_bytes() if ui is None else ui
        self.pid = pid

    async def __call__(self, args, *, binario=False):
        self.llamadas.append(args)
        s = " ".join(args)
        if "screencap" in s:
            return png()
        if "cat /sdcard/dogfood-ui.xml" in s:
            return self.ui
        if "dumpsys activity" in s:
            return (FIX / "dumpsys_activity.txt").read_bytes()
        if args[:2] == ["shell", "pidof"]:
            if not self.pid:
                raise AdbError("sin proceso")
            return self.pid
        if args[0] == "logcat" and "-d" in args:
            return LOGCAT.encode()
        if args[0] == "get-state":
            return b"device\n"
        return b""

    def cuenta(self, fragmento: str) -> int:
        return sum(fragmento in " ".join(a) for a in self.llamadas)


@pytest.fixture
def falso():
    return Falso()


@pytest.fixture
async def driver(falso, tmp_path):
    d = DriverAndroid(Adb("SERIAL1", runner=falso), PAQUETE)
    d.espera_cierre = 0
    await d.iniciar(tmp_path)
    yield d
    await d.cerrar()


async def test_observar_guarda_captura_arbol_y_parsea(driver, tmp_path):
    obs = await driver.observar(1)
    assert obs.captura == tmp_path / "capturas" / "paso-001.png" and obs.captura.exists()
    assert obs.arbol == tmp_path / "arboles" / "paso-001.xml" and obs.arbol.exists()
    assert obs.pantalla == "com.example.app/.ui.LoginActivity"
    por_id = {e.id: e for e in obs.elementos}
    entrar = por_id["com.example.app:id/btn_entrar"]
    assert entrar.texto == "Entrar" and entrar.bounds == (60, 960, 1020, 1120) and entrar.clicable
    assert por_id["com.example.app:id/email"].editable
    assert "Esqueci minha senha" in obs.texto_visible
    assert not any(e.clase == "android.widget.FrameLayout" for e in obs.elementos)  # raíz sin datos


async def test_tocar_por_id_manda_tap_al_centro(driver, falso):
    await driver.observar(1)
    r = await driver.actuar(Accion(tipo="tocar", elemento="com.example.app:id/btn_entrar"))
    assert r.ok and r.punto == (540, 1040)
    assert ["shell", "input", "tap", "540", "1040"] in falso.llamadas


async def test_elemento_inexistente(driver):
    await driver.observar(1)
    r = await driver.actuar(Accion(tipo="tocar", elemento="nada"))
    assert not r.ok and "nada" in r.error


def test_escapar_texto():
    assert escapar_texto("a b&c") == "a%sb\\&c"


async def test_escribir_escapa_y_toca_antes(driver, falso):
    await driver.observar(1)
    r = await driver.actuar(
        Accion(tipo="escribir", elemento="com.example.app:id/email", texto="a b&c")
    )
    assert r.ok and r.punto == (540, 600)
    assert falso.llamadas[-2:] == [
        ["shell", "input", "tap", "540", "600"],
        ["shell", "input", "text", "a%sb\\&c"],
    ]


async def test_volver_abrir_y_cerrar_app(driver, falso):
    for t in ("volver", "abrir_app", "cerrar_app"):
        assert (await driver.actuar(Accion(tipo=t))).ok
    assert ["shell", "input", "keyevent", "KEYCODE_BACK"] in falso.llamadas
    assert falso.cuenta(f"monkey -p {PAQUETE} -c android.intent.category.LAUNCHER 1") == 1
    assert ["shell", "am", "force-stop", PAQUETE] in falso.llamadas


async def test_abrir_app_con_actividad(falso, tmp_path):
    d = DriverAndroid(Adb("S", runner=falso), PAQUETE, ".Main")
    await d.actuar(Accion(tipo="abrir_app"))
    assert ["shell", "am", "start", "-n", f"{PAQUETE}/.Main"] in falso.llamadas


async def test_dump_vacio_reintenta_una_vez(tmp_path):
    f = Falso(ui=b"")
    d = DriverAndroid(Adb("S", runner=f), PAQUETE)
    d.espera_cierre = 0
    await d.iniciar(tmp_path)
    obs = await d.observar(2)
    await d.cerrar()
    assert obs.elementos == [] and obs.captura.exists()
    assert f.cuenta("uiautomator dump") == 2


async def test_evidencia_filtra_por_pid(driver, falso, tmp_path):
    ev = await driver.evidencia()
    assert ["logcat", "-d", "-v", "brief", "--pid=4321"] in falso.llamadas
    log = next(e for e in ev if e.tipo == "log")
    assert log.ruta == tmp_path / "logcat.txt" and log.ruta.exists()
    assert "FATAL EXCEPTION" in log.extracto and "ruido" not in log.extracto


async def test_evidencia_sin_pid_filtra_por_paquete(tmp_path):
    f = Falso(pid=b"")
    d = DriverAndroid(Adb("S", runner=f), PAQUETE)
    d.espera_cierre = 0
    await d.iniciar(tmp_path)
    ev = await d.evidencia()
    assert not any("--pid" in " ".join(a) for a in f.llamadas)
    texto = (tmp_path / "logcat.txt").read_text()
    assert "Start proc" in texto and "ruido" not in texto
    assert "FATAL EXCEPTION" in ev[0].extracto


@pytest.mark.parametrize(
    "serial,hp",
    [
        ("R58M123ABC", None),
        (None, "127.0.0.1:5555"),
        (None, "localhost:5555"),
        (None, "100.101.102.103:5555"),
    ],
)
def test_destino_valido(serial, hp):
    assert validar_destino(serial, hp)


@pytest.mark.parametrize(
    "hp", ["192.168.0.10:5555", "8.8.8.8:5555", "0.0.0.0:5555", "100.101.102.103", "10.0.0.1:5555"]
)
def test_destino_rechazado(hp):
    with pytest.raises(ValueError):
        validar_destino(None, hp)
    with pytest.raises(ValueError):
        Adb(host_puerto=hp)


def test_destino_rechazado_explica_nfr10():
    with pytest.raises(ValueError, match="NFR-10"):
        validar_destino(None, "192.168.0.10:5555")


async def test_conectar_verifica_estado(falso):
    await Adb(host_puerto="127.0.0.1:5555", runner=falso).conectar()
    assert ["connect", "127.0.0.1:5555"] in falso.llamadas and ["get-state"] in falso.llamadas


async def test_frame_jpeg_reducido_y_cacheado(driver, falso):
    antes = falso.cuenta("screencap")
    a = await driver.frame()
    b = await driver.frame()
    assert a == b and falso.cuenta("screencap") == antes + 1
    img = Image.open(BytesIO(a))
    assert img.format == "JPEG" and max(img.size) <= 720
