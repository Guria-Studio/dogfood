import hashlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from dogfood.almacen import Almacen
from dogfood.cli import app as cli
from dogfood.dominio import Corrida, Ejecucion, MetricasEjecucion, Persona
from dogfood.panel.app import crear_app_panel
from dogfood.panel.consultas import recorridos

runner = CliRunner()


def _persona(id, nombre, idioma):
    return Persona(
        id=id,
        nombre=nombre,
        email=f"{id}@x.com",
        contrasena="pw",
        empresa="E",
        rubro="r",
        idioma=idioma,
        destreza=3,
        paciencia=3,
        intencion="explorar",
        semilla=1,
    )


def _ej(id, persona, esc, res, driver, motor, backend, modelo, costo, equiv, tin=100, tout=50):
    return Ejecucion(
        id=id,
        persona_id=persona,
        escenario_id=esc,
        modelo=modelo,
        estado="ok",
        driver=driver,
        motor=motor,
        backend=backend,
        resultado=res,
        exito=res == "aprobado",
        duracion_s=12,
        metricas=MetricasEjecucion(
            tokens_in=tin, tokens_out=tout, capturas=2, costo_usd=costo, costo_equivalente_usd=equiv
        ),
    )


@pytest.fixture
def raiz(tmp_path):
    a = Almacen(tmp_path)
    for cid, ver in (("c1", "v1.0"), ("c2", "v2.0")):
        a.nueva_corrida(
            Corrida(
                id=cid,
                objetivo="predicts",
                ref="main",
                commit="abc",
                semilla=1,
                inicio=datetime(2026, 1, 1),
                estado="completa",
                version_app=ver,
            )
        )
        a.guardar_personas(cid, [_persona("p1", "Ana", "es"), _persona("p2", "Bob", "pt-BR")])
    ej = [
        ("c1", _ej("e1", "p1", "demo", "aprobado", "web", "browser_use", "api", "m1", 0.10, 0.10)),
        (
            "c1",
            _ej(
                "e2", "p2", "login-fallido", "fallo", "web", "browser_use", "api", "m1", 0.30, 0.30
            ),
        ),
        (
            "c1",
            _ej(
                "e3",
                "p1",
                "demo",
                "no_concluyente",
                "android",
                "browser_use",
                "api",
                "m1",
                0.20,
                0.20,
            ),
        ),
        (
            "c2",
            _ej("e4", "p1", "demo", "aprobado", "android", "bucle", "claude_code", "m2", 0.0, 0.50),
        ),
        ("c2", _ej("e5", "p2", "demo", "aprobado", "web", "bucle", "claude_code", "m2", 0.0, 0.30)),
        (
            "c2",
            _ej(
                "e6", "p2", "login-fallido", "fallo", "web", "bucle", "claude_code", "m2", 0.0, 0.10
            ),
        ),
    ]
    for cid, e in ej:
        a.guardar_ejecucion(cid, e)
    return tmp_path


@pytest.fixture
def cliente(raiz):
    return TestClient(crear_app_panel(raiz))


def _ids(html):
    return {i for i in ("e1", "e2", "e3", "e4", "e5", "e6") if f'/ejecuciones/{i}"' in html}


def test_lista_todo_con_insignia_y_costo(cliente):
    html = cliente.get("/").text
    assert _ids(html) == {"e1", "e2", "e3", "e4", "e5", "e6"}
    for esperado in (
        "res-aprobado",
        "res-fallo",
        "res-no_concluyente",
        "0.3000",
        "0.5000",
        "Ana (es)",
    ):
        assert esperado in html


@pytest.mark.parametrize(
    "query,esperado",
    [
        ("recorrido=login-fallido", {"e2", "e6"}),
        ("resultado=aprobado", {"e1", "e4", "e5"}),
        ("resultado=no_concluyente", {"e3"}),
        ("version=v2.0", {"e4", "e5", "e6"}),
        ("persona=p1", {"e1", "e3", "e4"}),
        ("driver=android", {"e3", "e4"}),
        ("motor=bucle", {"e4", "e5", "e6"}),
        ("motor=bucle&driver=web&resultado=aprobado", {"e5"}),
        ("persona=p2&version=v1.0&recorrido=login-fallido", {"e2"}),
        ("motor=browser_use&version=v2.0", set()),
    ],
)
def test_filtros(cliente, query, esperado):
    assert _ids(cliente.get(f"/?{query}").text) == esperado


def test_recorridos_muestra_contrato_y_conteos(raiz, cliente):
    esc = {r.id: r for r in recorridos(raiz)}
    assert esc["demo"].por_resultado == {"aprobado": 3, "fallo": 0, "no_concluyente": 1}
    assert esc["login-fallido"].por_resultado["fallo"] == 2
    html = cliente.get("/recorridos").text
    assert "res-aprobado" in html
    for r in esc.values():
        if r.contrato:
            assert r.contrato.resultado_esperado in html


def test_comparacion_de_motores(cliente):
    html = cliente.get("/corridas/c1").text
    assert "browser_use" in html and "33%" in html  # 1 de 3
    # tokens/ejec. 150; costo/ejec. (0.1+0.3+0.2)/3 = 0.2
    assert ">150<" in html and "0.2000" in html
    html = cliente.get("/corridas/c2").text
    assert "claude_code" in html and "67%" in html and "0.3000" in html  # equiv. 0.9/3


def test_corrida_inexistente(cliente):
    assert cliente.get("/corridas/nada").status_code == 404


def test_solo_lectura(raiz, cliente):
    db = raiz / "dogfood.db"
    antes = hashlib.sha256(db.read_bytes()).hexdigest()
    for ruta in ("/", "/?motor=bucle", "/recorridos", "/corridas/c1"):
        assert cliente.get(ruta).status_code == 200
    assert hashlib.sha256(db.read_bytes()).hexdigest() == antes
    assert sorted(p.name for p in raiz.iterdir()).count("dogfood.db-journal") == 0


def test_cli_rechaza_host_publico(raiz):
    r = runner.invoke(cli, ["panel", "--host", "0.0.0.0", "--raiz", str(raiz)])
    assert r.exit_code != 0 and "NFR-10" in r.output


def test_help_lista_panel():
    assert "panel" in runner.invoke(cli, ["--help"]).output
