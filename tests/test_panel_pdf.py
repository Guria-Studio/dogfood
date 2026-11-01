import re
import socket
import threading
import time
from datetime import datetime

import pytest
import uvicorn
from fastapi.testclient import TestClient

from dogfood.almacen import Almacen
from dogfood.dominio import Corrida, Ejecucion, Friccion, Gravedad, Paso, Persona
from dogfood.panel.app import crear_app_panel

PERSONA = Persona(
    id="p1", nombre="Ana", email="a@x.com", contrasena="pw", empresa="Luna", rubro="farmacia",
    idioma="es", destreza=3, paciencia=3, intencion="explorar", semilla=1,
)  # fmt: skip

PAGINA = "<html><body><h1>Reporte c1</h1><div data-reporte-listo>listo</div></body></html>"


@pytest.fixture
def raiz(tmp_path):
    a = Almacen(tmp_path / "runs")
    a.nueva_corrida(
        Corrida(id="c1", objetivo="predicts", ref="main", commit="abc", semilla=7,
                inicio=datetime(2026, 1, 1), estado="completa")
    )  # fmt: skip
    a.guardar_personas("c1", [PERSONA])
    d = a.dir_ejecucion("c1", "c1-E1")
    cap = d / "capturas" / "1.png"
    cap.parent.mkdir(parents=True)
    cap.write_bytes(b"\x89PNG")
    a.guardar_ejecucion(
        "c1",
        Ejecucion(
            id="c1-E1", persona_id="p1", escenario_id="demo", modelo="m", estado="fallo",
            resultado="fallo",
            pasos=[Paso(n=1, url="http://a/", pantalla="/panel", accion="clic", captura=cap,
                        ts=datetime(2026, 1, 1))],
            fricciones=[Friccion(texto="tabla vacía", severidad=Gravedad.alta, pantalla="/panel",
                                 cita="no veo nada")],
        ),
    )  # fmt: skip
    return tmp_path / "runs"


def test_datos_del_reporte(raiz):
    r = TestClient(crear_app_panel(raiz)).get("/api/corridas/c1/reporte").json()
    assert r["fallidos"][0]["miniatura"].startswith("/archivos/")
    assert r["opiniones"][0]["pantalla"] == "/panel"
    assert r["opiniones"][0]["citas"][0]["cita"] == "no veo nada"
    assert TestClient(crear_app_panel(raiz)).get("/api/corridas/nope/reporte").status_code == 404


def test_pdf_se_genera_con_paginas(raiz, tmp_path):
    spa = tmp_path / "spa"
    spa.mkdir()
    (spa / "index.html").write_text(PAGINA)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    srv = uvicorn.Server(
        uvicorn.Config(crear_app_panel(raiz, spa=spa), port=puerto, log_level="error")
    )
    hilo = threading.Thread(target=srv.run, daemon=True)
    hilo.start()
    while not srv.started:
        time.sleep(0.05)
    try:
        import httpx

        r = httpx.get(f"http://127.0.0.1:{puerto}/api/corridas/c1/reporte.pdf", timeout=60)
    finally:
        srv.should_exit = True
        hilo.join(5)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")
    assert len(re.findall(rb"/Type\s*/Page[^s]", r.content)) > 0
