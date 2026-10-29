import asyncio
import logging
import re
import socket
import time

import pytest
from starlette.testclient import TestClient  # noqa: F401
from typer.testing import CliRunner
from websockets.asyncio.client import connect

from dogfood.comandos.run import app
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion, Escenario, Instancia
from dogfood.eventos import BUS_NULO, EventoVivo


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FalsoObjetivo:
    nombre = "falso"

    def preparar(self, ref, corrida):
        return Instancia(base_url="http://x", api_url="http://x", proyecto_compose="p", commit="a")

    def destruir(self, instancia):
        pass

    def escenarios(self):
        return [Escenario(id="a", titulo="a", objetivo="o", criterio_exito="c")]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}

    def url_permitida(self, url, instancia):
        return True


@pytest.fixture
def buses(monkeypatch):
    vistos = []

    async def navegador(persona, escenario, instancia, dataset, carpeta, llm, juez, **kw):
        bus, cid = kw.get("bus", BUS_NULO), kw.get("corrida_id", "")
        vistos.append(bus)
        base = {"corrida_id": cid, "ejecucion_id": carpeta.name}
        bus.publicar(EventoVivo(**base, tipo="inicio"))
        for n in range(1, 4):
            bus.publicar(EventoVivo(**base, tipo="paso", n_paso=n, accion="click"))
            bus.publicar(EventoVivo(**base, tipo="frame", frame_jpeg_b64="x" * 2000))
            await asyncio.sleep(0.1)
        bus.publicar(EventoVivo(**base, tipo="fin", resultado="aprobado"))
        return Ejecucion(
            id=carpeta.name,
            persona_id=persona.id,
            escenario_id=escenario.id,
            modelo="m",
            estado="ok",
            exito=True,
            motivo_juez="ok",
        )

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", navegador)
    return vistos


def _opciones(tmp_path, **kw):
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]})
    return Opciones(
        raiz=tmp_path,
        cfg=cfg,
        objetivo_obj=FalsoObjetivo(),
        llm=object(),
        semilla=7,
        sin_publicar=True,
        espera_vista_s=0,
        **kw,
    )


def test_sin_vista_bus_nulo_y_sin_puerto(tmp_path, buses):
    asyncio.run(correr(_opciones(tmp_path)))
    assert buses == [BUS_NULO]


def test_con_vista_cliente_ve_inicio_paso_fin(tmp_path, buses):
    puerto = _puerto_libre()

    async def todo():
        tarea = asyncio.create_task(
            correr(_opciones(tmp_path, vista=True, vista_puerto=puerto, personas=2))
        )
        tipos: dict[str, set] = {}
        for _ in range(100):
            try:
                ws = await connect(f"ws://127.0.0.1:{puerto}/ws")
                break
            except OSError:
                await asyncio.sleep(0.05)
        async with ws:
            while not tarea.done() or True:
                try:
                    ev = EventoVivo.model_validate_json(await asyncio.wait_for(ws.recv(), 3))
                except TimeoutError:
                    break
                tipos.setdefault(ev.ejecucion_id, set()).add(ev.tipo)
                if sum("fin" in t for t in tipos.values()) == 2:
                    break
        await tarea
        return tipos

    tipos = asyncio.run(todo())
    assert len(tipos) == 2
    assert all({"inicio", "paso", "fin"} <= t for t in tipos.values())
    assert len(buses) == 2 and buses[0] is buses[1] and buses[0].activo


def test_puerto_ocupado_no_falla(tmp_path, buses, caplog):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        with caplog.at_level(logging.WARNING, logger="dogfood"):
            c = asyncio.run(
                correr(_opciones(tmp_path, vista=True, vista_puerto=s.getsockname()[1]))
            )
    assert c.estado.startswith("ok")
    assert buses == [BUS_NULO]
    assert "sin vista" in caplog.text


def test_costo_de_la_vista(tmp_path, buses):
    def medir(**kw):
        t0 = time.monotonic()
        asyncio.run(correr(_opciones(tmp_path / str(kw), personas=3, **kw)))
        return time.monotonic() - t0

    async def con_cliente(puerto):
        tarea = asyncio.create_task(
            correr(_opciones(tmp_path / "v", personas=3, vista=True, vista_puerto=puerto))
        )
        for _ in range(100):
            try:
                ws = await connect(f"ws://127.0.0.1:{puerto}/ws")
                break
            except OSError:
                await asyncio.sleep(0.05)
        async with ws:
            lector = asyncio.create_task(_leer(ws))
            await tarea
            lector.cancel()

    async def _leer(ws):
        async for _ in ws:
            pass

    base = medir()
    t0 = time.monotonic()
    asyncio.run(con_cliente(_puerto_libre()))
    # FR-31: la vista no frena las ejecuciones más de un 10 %. El margen fijo cubre arrancar y
    # apagar uvicorn y conectar el WebSocket (en el runner de CI cargado llega a ~1,1 s), que no
    # dependen del número de pasos.
    assert time.monotonic() - t0 < base * 1.1 + 1.5


def test_help_muestra_vista():
    r = CliRunner().invoke(app, ["--help"], env={"NO_COLOR": "1", "COLUMNS": "200"})
    salida = re.sub(r"\x1b\[[0-9;]*m", "", r.output)
    assert "--vista" in salida and "--vista-puerto" in salida
