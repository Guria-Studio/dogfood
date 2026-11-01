import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from dogfood.eventos import BusVivo, EventoVivo
from dogfood.vista.servidor import crear_app_vista, iniciar_vista


def ev(ejec, tipo, n=0, **kw):
    return EventoVivo(corrida_id="c", ejecucion_id=ejec, tipo=tipo, n_paso=n, **kw)


def test_evento_llega():
    bus = BusVivo()
    with TestClient(crear_app_vista(bus)).websocket_connect("/ws") as ws:
        t0 = time.monotonic()
        bus.publicar(ev("e1", "paso", 1, accion="click"))
        assert ws.receive_json()["accion"] == "click"
        assert time.monotonic() - t0 < 1


def test_cliente_tardio_recibe_ultimos():
    bus = BusVivo()
    c = TestClient(crear_app_vista(bus))
    bus.publicar(ev("e1", "inicio"))
    bus.publicar(ev("e1", "paso", 1))
    bus.publicar(ev("e1", "paso", 2))
    bus.publicar(ev("e1", "frame", frame_jpeg_b64="a"))
    bus.publicar(ev("e1", "frame", frame_jpeg_b64="b"))
    with c.websocket_connect("/ws") as ws:
        recibidos = [ws.receive_json() for _ in range(3)]
    assert [(e["tipo"], e["n_paso"], e["frame_jpeg_b64"]) for e in recibidos] == [
        ("inicio", 0, None),
        ("paso", 2, None),
        ("frame", 0, "b"),
    ]


def test_tres_ejecuciones_aisladas():
    bus = BusVivo()
    with TestClient(crear_app_vista(bus)).websocket_connect("/ws") as ws:
        for i in range(5):
            for e in ("a", "b", "c"):
                bus.publicar(ev(e, "paso", i, accion=e))
        vistos = [ws.receive_json() for _ in range(15)]
    assert all(v["ejecucion_id"] == v["accion"] for v in vistos)
    assert {v["ejecucion_id"] for v in vistos} == {"a", "b", "c"}


def test_suscriptor_lento_no_bloquea():
    bus = BusVivo()
    crear_app_vista(bus)
    bus.suscribir()  # no lee
    t0 = time.monotonic()
    for _ in range(1000):
        bus.publicar(ev("e1", "frame", frame_jpeg_b64="x" * 1000))
    assert time.monotonic() - t0 < 0.5


def test_host_prohibido_antes_de_abrir_puerto():
    with pytest.raises(ValueError, match="NFR-10"):
        asyncio.run(iniciar_vista(BusVivo(), "0.0.0.0", 0))
