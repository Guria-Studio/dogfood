import asyncio
import re
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogfood.comandos.run import app
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.deterministico import ResultadoDeterministico, ResultadoTest
from dogfood.dominio import Ejecucion, Escenario, Instancia, RecorridoDeterministico
from dogfood.nodos.protocolo import EstadoNodo, ResultadoTrabajo
from dogfood.objetivos import cargar_objetivo
from dogfood.objetivos.ios import IosObjetivo

UDID = "00008110-AAAA"
BASE = {
    "roles": {"persona": ["m"], "juez": ["m"]},
    "nodos": {
        "mac": {
            "host": "100.101.102.103",
            "usuario": "hector",
            "proyectos": {"app": "/Users/h/app"},
        }
    },
}


def cfg(**driver):
    d = {"tipo": "ios", "nodo": "mac", "udid": UDID, "bundle_id": "br.com.app", **driver}
    return Config.model_validate(BASE | {"driver": d})


class Tunel:
    cerrado = False

    async def cerrar(self):
        self.cerrado = True


class ClienteFalso:
    def __init__(self, dispositivos=({"udid": UDID, "nombre": "iPhone", "os": "17"},)):
        self.dispositivos, self.trabajos, self.tunel_obj, self.puertos = (
            dispositivos,
            [],
            Tunel(),
            None,
        )

    async def estado(self):
        return EstadoNodo(xcode="15.0", dispositivos=list(self.dispositivos))

    async def tunel(self, puertos):
        self.puertos = list(puertos)
        return self.tunel_obj

    async def enviar(self, trabajo, carpeta):
        self.trabajos.append(trabajo)
        return ResultadoTrabajo(
            id=trabajo.id,
            estado="ok",
            appium_url="http://127.0.0.1:4723",
            mjpeg_url="http://127.0.0.1:9100",
        )


def test_cargar_y_escenarios():
    o = cargar_objetivo("ios")
    assert isinstance(o, IosObjetivo)
    esc = {e.id: e for e in o.escenarios()}
    assert set(esc) == {"login", "login-patrol"}
    assert esc["login-patrol"].motor == "patrol" and esc["login-patrol"].driver == "ios"
    assert esc["login"].contrato


def test_preparar_y_destruir():
    c = ClienteFalso()
    o = IosObjetivo(cfg(), c)
    i = o.preparar("main", None)
    assert i.base_url == "ios://br.com.app" and c.puertos == [4723, 9100]
    assert i.parametros["appium_url"] == "http://127.0.0.1:4723"
    assert i.parametros["udid"] == UDID and c.trabajos[0].tipo == "sesion_appium"
    o.destruir(i)
    assert c.trabajos[-1].tipo == "cerrar_sesion" and c.tunel_obj.cerrado


def test_sin_nodo_o_udid_ausente_cita_la_doc():
    with pytest.raises(ValueError, match=r"docs/ops/ios-nodo-mac\.md"):
        IosObjetivo(cfg(nodo=None)).preparar("main", None)
    with pytest.raises(RuntimeError, match=r"docs/ops/ios-nodo-mac\.md"):
        IosObjetivo(cfg(), ClienteFalso(dispositivos=())).preparar("main", None)


def test_url_y_pantalla():
    o = IosObjetivo()
    i = Instancia(base_url="ios://br.com.app", api_url="", proyecto_compose="", commit="")
    assert o.url_permitida("ios://br.com.app/login", i)
    assert not o.url_permitida("ios://otra.app/login", i)
    assert o.pantalla("ios://br.com.app/login") == "login"
    assert o.logs(i, None) == {} and o.verificadores() == []


class ObjetivoFalso:
    nombre = "falso"

    def __init__(self, motor=None):
        self.motor = motor

    def preparar(self, ref, corrida):
        return Instancia(
            base_url="ios://br.com.app",
            api_url="",
            proyecto_compose="",
            commit="abc",
            parametros={
                "nodo": "mac",
                "udid": UDID,
                "bundle_id": "br.com.app",
                "appium_url": "http://127.0.0.1:4723",
            },
        )

    def destruir(self, instancia):
        pass

    def escenarios(self):
        return [
            Escenario(
                id="l",
                titulo="l",
                objetivo="o",
                criterio_exito="c",
                driver="ios",
                motor=self.motor,
                deterministico=RecorridoDeterministico(
                    pasos=[{"accion": "escribir", "key": "k", "valor": "{env:DOGFOOD_APP_EMAIL}"}]
                ),
            )
        ]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}

    def url_permitida(self, url, instancia):
        return True


def _correr(tmp_path, **kw):
    c = Config.model_validate(BASE | {"driver": {"tipo": "ios"}})
    c._secretos["DOGFOOD_APP_EMAIL"] = "secreto@x.com"
    return asyncio.run(
        correr(
            Opciones(
                raiz=tmp_path, cfg=c, objetivo_obj=ObjetivoFalso(kw.pop("motor", None)),
                llm=object(), semilla=7, sin_publicar=True, **kw,
            )
        )
    )  # fmt: skip


def test_corrida_agentica_usa_driver_ios(tmp_path, monkeypatch):
    vistos = []

    class DriverFalso:
        nombre = "ios"

        def __init__(self, *args, **kw):
            vistos.append((args, kw))

    async def bucle(persona, escenario, driver, backend, juez, carpeta, **kw):
        return Ejecucion(
            id=carpeta.name, persona_id=persona.id, escenario_id=escenario.id, modelo="m",
            estado="ok", exito=True, driver=driver.nombre, motor="bucle", backend="api",
        )  # fmt: skip

    monkeypatch.setattr("dogfood.corrida.DriverIos", DriverFalso)
    monkeypatch.setattr("dogfood.corrida.bucle.ejecutar", bucle)
    _correr(tmp_path, driver="ios")
    assert vistos[0][0] == ("http://127.0.0.1:4723", UDID, "br.com.app")


def test_corrida_patrol_envia_trabajo_al_nodo(tmp_path, monkeypatch):
    c = ClienteFalso()

    async def enviar(trabajo, carpeta):
        c.trabajos.append(trabajo)
        return ResultadoTrabajo(
            id=trabajo.id,
            estado="ok",
            deterministico=ResultadoDeterministico(
                herramienta="patrol",
                codigo_salida=0,
                log=Path("s.log"),
                tests=[ResultadoTest(nombre="l", estado="ok")],
            ),
        )

    c.enviar = enviar
    monkeypatch.setattr("dogfood.corrida.ClienteNodo", lambda nombre, nodo: c)
    _correr(tmp_path, motor="patrol")
    t = c.trabajos[0]
    assert (t.tipo, t.udid, t.proyecto) == ("patrol", UDID, "/Users/h/app")
    assert t.dart_defines == {"DOGFOOD_APP_EMAIL": "secreto@x.com"}
    assert "secreto@x.com" not in t.escenario.model_dump_json()
    fila = sqlite3.connect(tmp_path / "dogfood.db").execute("SELECT driver, motor FROM ejecuciones")
    assert fila.fetchall() == [("ios", "patrol")]


def test_help_muestra_ios():
    r = CliRunner().invoke(app, ["--help"], env={"NO_COLOR": "1", "COLUMNS": "200"})
    assert "ios" in re.sub(r"\x1b\[[0-9;]*m", "", r.output)
