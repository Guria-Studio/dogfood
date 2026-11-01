import asyncio
import re
import sqlite3

import pytest
from typer.testing import CliRunner

from dogfood.comandos.run import app
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.deterministico import ResultadoDeterministico, ResultadoTest
from dogfood.dominio import Escenario, Instancia, RecorridoDeterministico
from dogfood.eventos import BusVivo


class FalsoObjetivo:
    nombre = "falso"

    def __init__(self, motor=None):
        self.motor = motor

    def preparar(self, ref, corrida):
        return Instancia(
            base_url="http://x",
            api_url="http://x",
            proyecto_compose="p",
            commit="abc",
            parametros={"serial": "ABC123"},
        )

    def destruir(self, instancia):
        pass

    def escenarios(self):
        return [
            Escenario(
                id="login",
                titulo="l",
                objetivo="o",
                criterio_exito="c",
                driver="android",
                motor=self.motor,
                deterministico=RecorridoDeterministico(),
            )
        ]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}

    def url_permitida(self, url, instancia):
        return True


@pytest.fixture
def corredor(monkeypatch):
    llamadas = []

    class Falso:
        def __init__(self, cfg, runner=None):
            pass

        async def correr(self, escenario, herramienta, dispositivo, carpeta, *, proyecto, capturar):
            (carpeta / "capturas").mkdir(parents=True, exist_ok=True)
            png = await capturar(carpeta / "capturas" / "final.png")
            llamadas.append((herramienta, dispositivo, proyecto, png))
            (carpeta / "deterministico").mkdir(parents=True, exist_ok=True)
            log = carpeta / "deterministico" / "salida.log"
            log.write_text("ok")
            return ResultadoDeterministico(
                herramienta=herramienta,
                codigo_salida=0,
                tests=[ResultadoTest(nombre="login", estado="ok")],
                log=log,
                captura_final=png,
            )

    class AdbFalso:
        destino = "ABC123"

        def __init__(self, *a, **k):
            pass

        async def ejecutar(self, *args, binario=False):
            return b"PNG"

    monkeypatch.setattr("dogfood.corrida.CorredorFlutter", Falso)
    monkeypatch.setattr("dogfood.corrida.Adb", AdbFalso)
    return llamadas


def _correr(tmp_path, proyecto="/app", obj=None, **kw):
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]}, flutter={"proyecto": proyecto})
    return asyncio.run(
        correr(
            Opciones(
                raiz=tmp_path,
                cfg=cfg,
                objetivo_obj=obj or FalsoObjetivo(),
                llm=object(),
                semilla=7,
                sin_publicar=True,
                **kw,
            )
        )
    )


def _filas(tmp_path, sql):
    return sqlite3.connect(tmp_path / "dogfood.db").execute(sql).fetchall()


def test_motor_integration_test_usa_el_dispositivo_de_la_instancia(tmp_path, corredor):
    _correr(tmp_path, motor="integration_test")
    assert corredor[0][:3] == ("integration_test", "ABC123", corredor[0][2])
    assert str(corredor[0][2]) == "/app"
    assert _filas(tmp_path, "SELECT motor, resultado FROM ejecuciones") == [
        ("integration_test", "aprobado")
    ]


def test_motor_patrol_desde_el_yaml(tmp_path, corredor):
    _correr(tmp_path, obj=FalsoObjetivo(motor="patrol"))
    assert corredor[0][0] == "patrol"
    assert _filas(tmp_path, "SELECT motor FROM ejecuciones") == [("patrol",)]


def test_captura_final_en_el_paso_y_sin_uso_llm(tmp_path, corredor):
    _correr(tmp_path, motor="patrol")
    assert corredor[0][3].name == "final.png" and corredor[0][3].read_bytes() == b"PNG"
    assert _filas(tmp_path, "SELECT COUNT(*) FROM uso_llm") == [(0,)]


def test_sin_proyecto_queda_no_concluyente(tmp_path, corredor):
    c = _correr(tmp_path, proyecto=None, motor="patrol")
    assert corredor == []
    assert c.estado in ("ok", "ok_con_avisos")
    assert _filas(tmp_path, "SELECT estado, resultado FROM ejecuciones") == [
        ("error", "no_concluyente")
    ]


def test_bus_publica_inicio_y_fin(tmp_path, corredor):
    bus = BusVivo()
    sub = bus.suscribir()
    _correr(tmp_path, motor="patrol", bus=bus)
    tipos = []
    while not sub.cola.empty():
        tipos.append(sub.cola.get_nowait().tipo)
    assert tipos == ["inicio", "fin"]


def test_help_muestra_los_motores_deterministas():
    r = CliRunner().invoke(app, ["--help"], env={"NO_COLOR": "1", "COLUMNS": "200"})
    s = re.sub(r"\x1b\[[0-9;]*m", "", r.output)
    assert "patrol" in s and "integration_test" in s
