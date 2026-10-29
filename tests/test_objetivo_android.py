from datetime import UTC, datetime

import pytest

from dogfood.config import Config
from dogfood.drivers.android import AdbError
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.android import AndroidObjetivo

DUMPSYS = b"Packages:\n  versionCode=7 minSdk=26\n  versionName=1.2.3\n"
CORRIDA = None  # preparar no usa la corrida


class Falso:
    def __init__(self, estado=b"device\n"):
        self.estado = estado
        self.llamadas: list[list[str]] = []

    async def __call__(self, args, *, binario=False):
        self.llamadas.append(args)
        if args[0] == "get-state":
            if self.estado is None:
                raise AdbError("device not found")
            return self.estado
        if args[:3] == ["shell", "dumpsys", "package"]:
            return DUMPSYS
        if args[0] == "logcat":
            return b"E/App: boom\n"
        return b""

    def cuenta(self, fragmento: str) -> int:
        return sum(fragmento in " ".join(a) for a in self.llamadas)


def objetivo(falso, **driver):
    cfg = Config.model_validate(
        {
            "roles": {"persona": ["m/p"], "juez": ["m/j"], "dedupe": ["m/d"], "redactor": ["m/r"]},
            "driver": {"tipo": "android", "paquete": "com.example.app", **driver},
        }
    )
    return AndroidObjetivo(cfg, falso)


def test_cargar_objetivo():
    assert isinstance(cargar_objetivo("android"), AndroidObjetivo)


def test_preparar_sin_apk():
    falso = Falso()
    inst = objetivo(falso, serial="SERIAL1").preparar("main", CORRIDA)
    assert inst.base_url == "android://com.example.app"
    assert inst.commit == "main"
    assert inst.parametros == {
        "serial": "SERIAL1",
        "paquete": "com.example.app",
        "version_app": "1.2.3",
    }
    assert falso.cuenta("install") == 0


def test_preparar_instala_apk_y_conecta(tmp_path):
    falso = Falso()
    apk = tmp_path / "app.apk"
    inst = objetivo(falso, host_puerto="100.64.0.5:5555", apk=apk).preparar("main", CORRIDA)
    assert falso.cuenta("connect 100.64.0.5:5555") == 1
    assert falso.cuenta(f"install -r {apk}") == 1
    assert inst.parametros["host_puerto"] == "100.64.0.5:5555"


@pytest.mark.parametrize("estado", [None, b"offline\n"])
def test_sin_dispositivo_remite_a_la_guia(estado):
    with pytest.raises(RuntimeError, match=r"docs/ops/android\.md"):
        objetivo(Falso(estado), serial="SERIAL1").preparar("main", CORRIDA)


def test_lan_rechazado_antes_de_adb():
    falso = Falso()
    with pytest.raises(ValueError, match="NFR-10"):
        objetivo(falso, host_puerto="192.168.1.20:5555").preparar("main", CORRIDA)
    assert falso.llamadas == []


def test_url_permitida_y_pantalla():
    o = objetivo(Falso(), serial="S")
    inst = o.preparar("main", CORRIDA)
    assert o.url_permitida("android://com.example.app", inst)
    assert o.url_permitida("android://com.example.app/.MainActivity", inst)
    assert not o.url_permitida("android://com.otra.app", inst)
    assert not o.url_permitida("android://com.example.app.evil", inst)
    assert not o.url_permitida("http://com.example.app", inst)
    assert o.pantalla("android://com.example.app/com.example.app.MainActivity") == ".MainActivity"
    assert o.pantalla("android://com.example.app") == ""


def test_escenarios_login():
    (login,) = objetivo(Falso(), serial="S").escenarios()
    assert login.id == "login"
    assert login.driver == "android"
    assert login.superficies == ["login"]
    c = login.contrato
    assert c and c.estado_inicial and c.acciones and c.resultado_esperado and c.evidencia_requerida


def test_destruir_no_desinstala_y_logs():
    falso = Falso()
    o = objetivo(falso, serial="S")
    inst = o.preparar("main", CORRIDA)
    o.destruir(inst)
    assert falso.cuenta("am force-stop com.example.app") == 1
    assert falso.cuenta("pm clear com.example.app") == 1
    assert falso.cuenta("uninstall") == 0
    assert o.logs(inst, datetime.now(UTC)) == {"logcat": "E/App: boom\n"}
    assert o.verificadores() == []
