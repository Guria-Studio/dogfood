"""Contratos v0.3 (F8.1.T1): dominio, config, frames, protocolo del nodo y registros."""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from dogfood.almacen import Almacen
from dogfood.config import Config
from dogfood.deteccion import DETECTORES
from dogfood.deteccion import flutter as det_flutter
from dogfood.deterministico import ResultadoDeterministico, ResultadoTest
from dogfood.dominio import Corrida, Ejecucion, Escenario, TipoHallazgo
from dogfood.drivers.android import Adb, DriverAndroid
from dogfood.drivers.base import Observacion
from dogfood.escenarios import cargar
from dogfood.frames import FuenteDeDriver, crear_fuente, validar_url_local
from dogfood.nodos import EstadoNodo, ResultadoTrabajo, Trabajo
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.flutter_web import FlutterWebObjetivo
from dogfood.objetivos.ios import IosObjetivo

YAML_VIEJO = """\
roles: {persona: [m]}
driver: {tipo: android, serial: S1}
"""

ESC_VIEJO = """\
id: e1
titulo: Viejo
objetivo: hacer algo
criterio_exito: ok
"""

ESC_IOS = """\
id: e2
titulo: Login iOS
objetivo: entrar
criterio_exito: ve el inicio
driver: ios
motor: integration_test
deterministico:
  dart_defines: {CLAVE: "{env:APP_CLAVE}"}
  pasos:
    - {accion: tocar, key: btn_entrar}
    - {accion: escribir, key: email, valor: "{env:APP_EMAIL}"}
    - {accion: esperar_texto, texto: Inicio, timeout_s: 20}
"""


def test_escenarios_viejo_y_determinista(tmp_path):
    (tmp_path / "a.yaml").write_text(ESC_VIEJO)
    (tmp_path / "b.yaml").write_text(ESC_IOS)
    viejo, ios = cargar(tmp_path)
    assert (viejo.driver, viejo.motor, viejo.deterministico) == ("web", None, None)
    assert (ios.driver, ios.motor) == ("ios", "integration_test")
    d = ios.deterministico
    assert [p.accion for p in d.pasos] == ["tocar", "escribir", "esperar_texto"]
    assert d.pasos[1].valor == "{env:APP_EMAIL}" and d.pasos[2].timeout_s == 20
    assert d.dart_defines == {"CLAVE": "{env:APP_CLAVE}"}
    assert TipoHallazgo("accesibilidad") is TipoHallazgo.accesibilidad
    assert Observacion(pantalla="x", elementos=[], ts=datetime.now()).cobertura is None


def test_ejecucion_ios_patrol_en_almacen(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(
        Corrida(
            id="c1", objetivo="ios", ref="main", commit="abc", semilla=1,
            inicio=datetime(2026, 1, 1), estado="en_curso",
        )
    )  # fmt: skip
    e = Ejecucion(
        id="x1", persona_id="p", escenario_id="e", modelo="m", estado="ok",
        driver="ios", motor="patrol",
    )  # fmt: skip
    a.guardar_ejecucion("c1", e)
    leida = a.ejecucion("x1")
    assert (leida.driver, leida.motor) == ("ios", "patrol")
    with sqlite3.connect(tmp_path / "dogfood.db") as con:
        fila = con.execute("SELECT driver, motor FROM ejecuciones WHERE id='x1'").fetchone()
    assert fila == ("ios", "patrol")


def _rd(codigo, *estados, motivo=""):
    return ResultadoDeterministico(
        herramienta="patrol",
        codigo_salida=codigo,
        tests=[ResultadoTest(nombre=f"t{i}", estado=s) for i, s in enumerate(estados)],
        motivo=motivo,
        log=Path("salida.log"),
    )


def test_resultado_deterministico():
    assert _rd(0, "ok", "ok").resultado() == "aprobado"
    assert _rd(1, "ok", "fallo").resultado() == "fallo"
    assert _rd(None, "ok", motivo="timeout").resultado() == "no_concluyente"
    assert _rd(None, "ok").resultado() == "no_concluyente"
    assert _rd(0).resultado() == "no_concluyente"
    assert _rd(1, motivo="compilacion").resultado() == "no_concluyente"


def test_config_vieja_con_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "nada"))
    (tmp_path / "dogfood.yaml").write_text(YAML_VIEJO)
    cfg = Config.cargar(tmp_path)
    assert cfg.pantalla.android == "screencap" and cfg.pantalla.fps == 2
    assert cfg.flutter.umbral_cobertura == 0.6
    assert cfg.flutter.copia_trabajo == Path("/mnt/storage/cache/dogfood/flutter")
    assert cfg.flutter_web.puerto == 7480 and cfg.flutter_web.host == "127.0.0.1"
    assert cfg.nodos == {}
    assert cfg.driver.tipo == "android" and cfg.driver.udid is None


def test_config_nodo_y_copia_trabajo(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "nada"))
    monkeypatch.setenv("HOME", str(tmp_path))
    yaml_ok = YAML_VIEJO + (
        "flutter: {copia_trabajo: ~/copias}\n"
        "nodos: {mac: {host: 100.101.102.103, usuario: hector}}\n"
    )
    (tmp_path / "dogfood.yaml").write_text(yaml_ok)
    cfg = Config.cargar(tmp_path)
    assert cfg.flutter.copia_trabajo == tmp_path / "copias"
    mac = cfg.nodos["mac"]
    assert (mac.puerto_ssh, mac.comando, mac.dir_trabajo) == (22, "dogfood nodo", "~/dogfood-nodo")

    (tmp_path / "dogfood.yaml").write_text(
        YAML_VIEJO + "nodos: {mac: {host: 192.168.1.10, usuario: hector}}\n"
    )
    with pytest.raises(ValidationError, match="192.168.1.10"):
        Config.cargar(tmp_path)
    (tmp_path / "dogfood.yaml").write_text(YAML_VIEJO + "flutter_web: {host: 0.0.0.0}\n")
    with pytest.raises(ValidationError):
        Config.cargar(tmp_path)


def test_ejemplo_carga():
    cfg = Config.cargar(Path(__file__).parent.parent)
    assert cfg.flutter_web.puerto == 7480 and cfg.nodos == {}


@pytest.mark.parametrize("url", ["http://127.0.0.1:9100", "http://100.101.102.103:4723"])
def test_url_local_acepta(url):
    assert validar_url_local(url) == url


@pytest.mark.parametrize(
    "url", ["http://192.168.0.5:9100", "http://0.0.0.0:9100", "ftp://127.0.0.1", "http://"]
)
def test_url_local_rechaza(url):
    with pytest.raises(ValueError):
        validar_url_local(url)


class DriverFrames:
    def __init__(self, nombre):
        self.nombre = nombre

    async def frame(self):
        return b"jpeg"


async def test_fuente_de_driver(tmp_path):
    f = FuenteDeDriver(DriverFrames("android"))
    await f.iniciar()
    assert await f.frame() == b"jpeg"
    await f.cerrar()
    assert (f.nombre, f.intervalo_s) == ("driver", 1.0)
    assert FuenteDeDriver(DriverFrames("web")).intervalo_s == 0.2
    assert FuenteDeDriver(DriverFrames("ios"), intervalo_s=0.5).intervalo_s == 0.5
    cfg = Config(roles={"persona": ["m"]})
    assert isinstance(crear_fuente(cfg, DriverFrames("web"), {}), FuenteDeDriver)


def test_protocolo_nodo_ida_y_vuelta():
    t = Trabajo(
        id="t1",
        tipo="patrol",
        udid="0000-AAAA",
        proyecto="/Users/hector/app",
        escenario=Escenario.model_validate(yaml.safe_load(ESC_IOS)),
        dart_defines={"K": "v"},
    )
    assert Trabajo.model_validate_json(t.model_dump_json()) == t
    r = ResultadoTrabajo(
        id="t1",
        estado="ok",
        deterministico=_rd(0, "ok"),
        artefactos=["deterministico/salida.log"],
        estado_nodo=EstadoNodo(xcode="16.0", dispositivos=[{"udid": "u", "nombre": "iPhone"}]),
    )
    vuelta = ResultadoTrabajo.model_validate_json(r.model_dump_json())
    assert vuelta == r and vuelta.deterministico.resultado() == "aprobado"


def test_registros():
    for nombre, clase in (("ios", IosObjetivo), ("flutter_web", FlutterWebObjetivo)):
        obj = cargar_objetivo(nombre)
        assert isinstance(obj, clase) and obj.nombre == nombre
        assert obj.escenarios() == []
        with pytest.raises(NotImplementedError, match="F8"):
            obj.preparar("main", None)
    assert det_flutter.detectar in DETECTORES
    assert det_flutter.detectar(None) == []


async def test_android_sin_grabar_video(tmp_path):
    llamadas = []

    async def runner(args, *, binario=False):
        llamadas.append(" ".join(args))
        return b""

    d = DriverAndroid(Adb("S1", runner=runner), "com.app", grabar_video=False)
    d.espera_cierre = 0
    await d.iniciar(tmp_path)
    await d.evidencia()
    await d.cerrar()
    assert not any("screenrecord" in a or a.startswith("pull") for a in llamadas)
    assert any(a.startswith("logcat -c") for a in llamadas)
