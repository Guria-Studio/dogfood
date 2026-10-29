import asyncio
import re
import sqlite3

import pytest
from typer.testing import CliRunner

from dogfood.comandos.run import app
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion, Escenario, Instancia, MetricasEjecucion, Paso


def _esc(driver="web"):
    return Escenario(id="a", titulo="a", objetivo="o", criterio_exito="c", driver=driver)


class FalsoObjetivo:
    nombre = "falso"

    def __init__(self, parametros=None, driver="web"):
        self.parametros, self.driver = parametros or {}, driver

    def preparar(self, ref, corrida):
        return Instancia(
            base_url="http://x",
            api_url="http://x",
            proyecto_compose="p",
            commit="abc",
            parametros={"serial": "ABC123", "paquete": "com.x"} | self.parametros,
        )

    def destruir(self, instancia):
        pass

    def escenarios(self):
        return [_esc(self.driver)]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}

    def url_permitida(self, url, instancia):
        return True


def _ejecucion(carpeta, persona, escenario, con_captura=True, **kw):
    pasos = [
        Paso(
            n=1,
            url="u",
            pantalla="p",
            accion="",
            captura=carpeta / "c.png" if con_captura else None,
            texto_visible="",
            ts="2026-01-01T00:00:00+00:00",
        )
    ]
    return Ejecucion(
        id=carpeta.name,
        persona_id=persona.id,
        escenario_id=escenario.id,
        modelo="m",
        estado="ok",
        exito=True,
        motivo_juez="ok",
        pasos=pasos,
        **kw,
    )


@pytest.fixture
def motores(monkeypatch):
    llamadas = {"bucle": [], "navegador": 0}

    async def bucle(persona, escenario, driver, backend, juez, carpeta, **kw):
        llamadas["bucle"].append((driver, backend))
        return _ejecucion(
            carpeta,
            persona,
            escenario,
            driver=driver.nombre,
            motor="bucle",
            backend=backend.nombre,
            metricas=MetricasEjecucion(
                tokens_in=10, tokens_out=5, costo_usd=0, costo_equivalente_usd=0.5
            ),
        )

    async def navegador(persona, escenario, instancia, dataset, carpeta, llm, juez, **kw):
        llamadas["navegador"] += 1
        return _ejecucion(carpeta, persona, escenario, con_captura=not llamadas.get("sin"))

    monkeypatch.setattr("dogfood.corrida.bucle.ejecutar", bucle)
    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", navegador)
    return llamadas


def _correr(tmp_path, motor_persona="api", obj=None, **kw):
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]}, motores={"persona": motor_persona})
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


def test_driver_android_corre_por_el_bucle(tmp_path, motores):
    _correr(tmp_path, driver="android")
    assert motores["navegador"] == 0
    assert motores["bucle"][0][0].nombre == "android"
    assert _filas(tmp_path, "SELECT driver, motor FROM ejecuciones") == [("android", "bucle")]


def test_escenario_con_driver_android(tmp_path, motores):
    _correr(tmp_path, obj=FalsoObjetivo(driver="android"))
    assert _filas(tmp_path, "SELECT driver, motor FROM ejecuciones") == [("android", "bucle")]


def test_claude_code_registra_uso_equivalente(tmp_path, motores):
    _correr(tmp_path, motor_persona="claude_code")
    assert motores["bucle"][0][1].nombre == "claude_code"
    assert motores["bucle"][0][0].nombre == "web"
    fila = _filas(tmp_path, "SELECT backend, costo_usd, costo_equivalente_usd FROM uso_llm")
    assert fila == [("claude_code", 0, 0.5)]


def test_sin_opciones_usa_browser_use(tmp_path, motores):
    _correr(tmp_path)
    assert motores["navegador"] == 1 and not motores["bucle"]


def test_toda_ejecucion_tiene_resultado_y_sin_capturas_no_concluyente(tmp_path, motores):
    _correr(tmp_path)
    assert _filas(tmp_path, "SELECT resultado FROM ejecuciones") == [("aprobado",)]
    motores["sin"] = True
    _correr(tmp_path / "otra")
    assert _filas(tmp_path / "otra", "SELECT resultado FROM ejecuciones") == [("no_concluyente",)]


def test_version_app_llega_a_la_corrida(tmp_path, motores):
    _correr(tmp_path, obj=FalsoObjetivo({"version_app": "1.2.3"}))
    assert _filas(tmp_path, "SELECT version_app FROM corridas") == [("1.2.3",)]


def test_help_muestra_driver_y_motor():
    r = CliRunner().invoke(app, ["--help"], env={"NO_COLOR": "1", "COLUMNS": "200"})
    salida = re.sub(r"\x1b\[[0-9;]*m", "", r.output)
    assert "--driver" in salida and "--motor" in salida
