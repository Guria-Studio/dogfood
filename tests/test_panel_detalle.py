import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from dogfood.almacen import Almacen
from dogfood.config import Config
from dogfood.dominio import (
    Corrida,
    Ejecucion,
    EventoConsola,
    EventoRed,
    Friccion,
    Gravedad,
    Paso,
    Persona,
)
from dogfood.panel.app import crear_app_panel

TOKEN = "tok9" + "a1b2c3d4" * 5  # parece un token de sesión
PERSONA = Persona(
    id="p1", nombre="Ana", email="ana@correo-real.com", contrasena="hunter2-pw",
    empresa="Farmacia Luna", rubro="farmacia", idioma="es", destreza=3, paciencia=3,
    intencion="explorar", semilla=1,
)  # fmt: skip


def _paso(n, raiz_ej):
    cap = raiz_ej / "capturas" / f"{n}.png"
    cap.parent.mkdir(parents=True, exist_ok=True)
    cap.write_bytes(b"\x89PNG-" + bytes([n]))
    return Paso(
        n=n, url="http://app/login", pantalla="/login", accion=f"clic {n}", captura=cap,
        ts=datetime(2026, 1, 1), razonamiento=f"porque {n}", paso_contrato=f"contrato {n}",
        esperado=f"ver panel {n}", observado=f"error 500 {n}",
    )  # fmt: skip


def _guardar(a, eid, driver):
    d = a.dir_ejecucion("c1", eid)
    video = d / "video" / ("v.mp4" if driver == "android" else "v.webm")
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"video")
    trace = d / "trace.zip"
    if driver == "web":
        trace.write_bytes(b"zip")
    e = Ejecucion(
        id=eid, persona_id="p1", escenario_id="demo", modelo="m", estado="fallo", driver=driver,
        resultado="fallo", pasos=[_paso(1, d), _paso(2, d)], video=video,
        trace=trace if driver == "web" else None,
        consola=[
            EventoConsola(
                nivel="error", url="http://app/login",
                texto=f"fallo de {PERSONA.email} con {PERSONA.contrasena} en {PERSONA.empresa}; token={TOKEN}",
            )
        ],
        red=[EventoRed(metodo="POST", url="http://app/login", estado=500, ms=12)],
        fricciones=[
            Friccion(texto="no sé dónde entrar", severidad=Gravedad.media, pantalla="/login",
                     cita="¿dónde está el botón?", captura=d / "capturas" / "1.png"),
            Friccion(texto="texto confuso", severidad=Gravedad.baja, pantalla="/login"),
            Friccion(texto="tabla vacía", severidad=Gravedad.alta, pantalla="/panel"),
        ],
    )  # fmt: skip
    a.guardar_ejecucion("c1", e)
    if driver == "android":
        (d / "logcat.txt").write_text("I/x: ok\nE/AndroidRuntime: FATAL EXCEPTION boom\n")


@pytest.fixture
def raiz(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(
        Corrida(id="c1", objetivo="predicts", ref="main", commit="abc1234", semilla=7,
                inicio=datetime(2026, 1, 1), estado="completa")
    )  # fmt: skip
    a.guardar_personas("c1", [PERSONA])
    _guardar(a, "web1", "web")
    _guardar(a, "and1", "android")
    return tmp_path


@pytest.fixture
def gh(monkeypatch):
    """`gh` falso con estado: graba título/cuerpo y encuentra issues por huella en el cuerpo."""
    llamadas, creados = [], []

    def falso(*args):
        llamadas.append(args)
        if args[:2] == ("issue", "list"):
            huella = args[args.index("--search") + 1].split()[0]
            hallados = [
                {"number": i, "url": f"https://gh/x/{i}"}
                for i, (_, cuerpo) in enumerate(creados, 1)
                if huella in cuerpo
            ]
            return json.dumps(hallados)
        if args[:2] == ("issue", "create"):
            creados.append((args[args.index("--title") + 1], args[args.index("--body") + 1]))
            return f"https://gh/x/{len(creados)}\n"
        return ""

    monkeypatch.setattr("dogfood.reporte.issues._gh", falso)
    falso.creados, falso.llamadas = creados, llamadas
    return falso


@pytest.fixture
def cliente(raiz):
    app = crear_app_panel(raiz)
    app.state.cfg = Config(roles={}, repo_issues="yo/dogfood", umbral_publicar="media")
    return TestClient(app)


def test_detalle_web(cliente):
    html = cliente.get("/ejecuciones/web1").text
    for n in (1, 2):
        for esperado in (
            f"clic {n}",
            f"porque {n}",
            f"contrato {n}",
            f"ver panel {n}",
            f"error 500 {n}",
        ):
            assert esperado in html
        assert f"/archivos/c1/ejecuciones/web1/capturas/{n}.png" in html
    assert "<video" in html and "/archivos/c1/ejecuciones/web1/video/v.webm" in html
    assert "trace.zip" in html and "playwright show-trace" in html
    assert "ArrowLeft" in html and "anterior" in html and "siguiente" in html
    assert "FATAL" not in html


def test_detalle_android_muestra_logcat(cliente):
    html = cliente.get("/ejecuciones/and1").text
    assert "FATAL EXCEPTION boom" in html and "v.mp4" in html and "trace.zip" not in html


def test_fricciones_agrupadas_por_pantalla(cliente):
    html = cliente.get("/ejecuciones/web1").text
    assert html.count("<h3>/login</h3>") == 1 and html.count("<h3>/panel</h3>") == 1
    login, panel = html.index("<h3>/login</h3>"), html.index("<h3>/panel</h3>")
    assert login < html.index("no sé dónde entrar") < html.index("texto confuso") < panel
    assert "¿dónde está el botón?" in html and html.index("tabla vacía") > panel


def test_ejecucion_inexistente(cliente):
    assert cliente.get("/ejecuciones/nada").status_code == 404


def test_archivos_sirve_captura_y_rechaza_fuera_de_raiz(raiz, tmp_path_factory):
    fuera = tmp_path_factory.mktemp("fuera")
    (fuera / "secreto.txt").write_text("no")
    (raiz / "c1" / "enlace").symlink_to(fuera)
    c = TestClient(crear_app_panel(raiz / "c1"))
    ok = c.get("/archivos/ejecuciones/web1/capturas/1.png")
    assert ok.status_code == 200 and ok.content.startswith(b"\x89PNG")
    for malo in (
        "../dogfood.db",
        "%2e%2e/dogfood.db",
        "ejecuciones/../../dogfood.db",
        f"/{fuera}/secreto.txt",
        f"%2F{fuera}/secreto.txt",
        "enlace/secreto.txt",
        "ejecuciones",  # un directorio
        "nada.png",
    ):
        assert c.get(f"/archivos/{malo}").status_code == 404, malo
    # dentro de la raíz pero con contraseñas: tampoco
    assert TestClient(crear_app_panel(raiz)).get("/archivos/dogfood.db").status_code == 404
    assert TestClient(crear_app_panel(raiz)).get("/archivos/c1/personas.json").status_code == 404


def test_crear_issue_redacta_y_deduplica(cliente, gh):
    r = cliente.post("/ejecuciones/web1/issue")
    assert r.status_code == 200 and r.json()["url"] == "https://gh/x/1"
    [(titulo, cuerpo)] = gh.creados
    assert titulo.startswith("[dogfood][media] /login:")
    assert "1. clic 1" in cuerpo and "2. clic 2" in cuerpo
    assert "ver panel 2" in cuerpo and "error 500 2" in cuerpo
    assert "runs/c1/ejecuciones/web1/video/v.webm" in cuerpo
    assert "dogfood replay web1" in cuerpo
    assert "<!-- dogfood:huella=" in cuerpo
    for secreto in (PERSONA.email, PERSONA.contrasena, PERSONA.empresa, TOKEN):
        assert secreto not in cuerpo and secreto not in titulo
    # misma huella: comenta en vez de crear
    r = cliente.post("/ejecuciones/web1/issue")
    assert r.json()["accion"] == "comentar" and r.json()["url"] == "https://gh/x/1"
    assert len(gh.creados) == 1
    assert any(c[:2] == ("issue", "comment") for c in gh.llamadas)


def test_crear_issue_android_lleva_logcat(cliente, gh):
    cliente.post("/ejecuciones/and1/issue?tipo=logica&gravedad=alta")
    [(titulo, cuerpo)] = gh.creados
    assert "[alta]" in titulo and "FATAL EXCEPTION boom" in cuerpo
