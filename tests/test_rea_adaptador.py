import json
import os
import stat
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from dogfood.rea import adaptador, normalizacion

SECRETO = "contraseña-plantada-123"
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123"

# `rea` falso: registra sus argumentos y responde según el subcomando.
FALSO = r"""#!PYTHON
import hashlib, json, os, sys
args = sys.argv[1:]
with open(os.environ["REA_LOG"], "a") as f:
    f.write(json.dumps(args) + "\n")
if os.environ.get("REA_FALLA"):
    print(json.dumps({"error": "Browser scenario capture failed", "code": "invalid_request",
                      "message": "Analysis input is invalid."}))
    sys.exit(1)
if args[0] == "capture-browser-scenario":
    esc = json.load(open(args[1]))
    pw = os.environ.get("DOGFOOD_REA_CONTRASENA", "")
    texto = f"<p>clave {pw} token JWT_X el 2026-11-01T10:00:00Z</p>"
    texto = texto.replace("JWT_X", os.environ["JWT"])
    dom = {"sha256": hashlib.sha256(texto.encode()).hexdigest(), "bytes": len(texto.encode()),
           "text": texto}
    nr = {"steps": [{"step_id": a["step_id"], "status": "completed",
                     "artifacts": {"dom": {"state": "captured", "value": dom}}}
                    for a in esc["actions"]]}
    print(json.dumps({"evidence_id": "ev_" + "a" * 64, "parameters": esc,
                      "raw_result": {"eco": pw}, "normalized_result": nr}))
else:
    print(json.dumps({"normalized_result": {"overall_status": "unchanged", "args": args,
                                            "norm": json.load(open(args[4]))}}))
"""


@pytest.fixture
def rea_falso(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    rea = bin_ / "rea"
    rea.write_text(FALSO.replace("PYTHON", sys.executable))
    rea.chmod(rea.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "rea.log"
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("REA_LOG", str(log))
    monkeypatch.setenv("JWT", JWT)
    return lambda: [json.loads(linea) for linea in log.read_text().splitlines()]


ESCENARIO = {
    "browser": {"mode": "launch", "executable_path": "/bin/chromium"},
    "start_url": {"url": "http://127.0.0.1:18080"},
    "secrets": [{"secret_id": "contrasena", "environment_variable": "DOGFOOD_REA_CONTRASENA"}],
    "actions": [{"step_id": "p001-1", "action": "click", "timeout_ms": 15000}],
    "avisos": ["no va a REA"],
}


def test_grabar_arma_los_argumentos_y_guarda_por_separado(rea_falso, tmp_path):
    assert adaptador.disponible()
    nr = adaptador.grabar(ESCENARIO, tmp_path / "g", secretos={"DOGFOOD_REA_CONTRASENA": SECRETO})
    (args,) = rea_falso()
    assert args[0] == "capture-browser-scenario"
    assert args[-2:] == ["--format", "json"]
    assert nr == tmp_path / "g" / "normalized_result.json"
    evidencia = json.loads((tmp_path / "g" / "evidencia.json").read_text())
    assert "avisos" not in evidencia["parameters"]
    assert json.loads(nr.read_text()) == evidencia["normalized_result"]


def test_un_secreto_plantado_no_queda_en_los_archivos(rea_falso, tmp_path):
    adaptador.grabar(ESCENARIO, tmp_path / "g", secretos={"DOGFOOD_REA_CONTRASENA": SECRETO})
    for f in (tmp_path / "g").iterdir():
        texto = f.read_text()
        assert SECRETO not in texto and JWT not in texto, f.name
    # el digest del texto redactado sigue valiendo: REA lo valida al comparar
    dom = json.loads((tmp_path / "g" / "normalized_result.json").read_text())["steps"][0]
    v = dom["artifacts"]["dom"]["value"]
    import hashlib

    assert v["sha256"] == hashlib.sha256(v["text"].encode()).hexdigest()
    assert v["bytes"] == len(v["text"].encode())


def test_comparar_pasa_la_politica_de_normalizacion(rea_falso, tmp_path):
    a = adaptador.grabar(ESCENARIO, tmp_path / "a", secretos={"DOGFOOD_REA_CONTRASENA": SECRETO})
    b = adaptador.grabar(ESCENARIO, tmp_path / "b", secretos={"DOGFOOD_REA_CONTRASENA": SECRETO})
    r = adaptador.comparar(a, b, normalizacion.reglas())
    args = rea_falso()[-1]
    assert args[:3] == ["compare-web-captures", str(a), str(b)]
    assert args[3] == "--normalization-json"
    assert r["overall_status"] == "unchanged"
    matches = {regla["match"]: regla["replacement"] for regla in r["norm"]["rules"]}
    assert matches["2026-11-01T10:00:00Z"] == "«fecha»"
    # los hashes de integridad no se vuelven reglas
    assert not any(len(m) == 64 for m in matches)


def test_un_error_de_rea_sale_como_excepcion_con_su_code(rea_falso, tmp_path, monkeypatch):
    monkeypatch.setenv("REA_FALLA", "1")
    with pytest.raises(adaptador.ErrorRea) as exc:
        adaptador.grabar(ESCENARIO, tmp_path / "g")
    assert exc.value.code == "invalid_request"
    assert "invalid" in exc.value.message


def test_timeout_sale_como_error_rea(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "rea").write_text("#!/bin/sh\nsleep 5\n")
    (bin_ / "rea").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    with pytest.raises(adaptador.ErrorRea) as exc:
        adaptador.grabar(ESCENARIO, tmp_path / "g", timeout_s=0.5)
    assert exc.value.code == "timeout"


def test_reglas_suman_las_del_objetivo():
    from dogfood.objetivos.predicts import PredictsObjetivo

    ids = {p["id"] for p in normalizacion.reglas(PredictsObjetivo())["patrones"]}
    assert {"uuid", "token", "fecha_iso", "email", "id_ruta", "hora"} <= ids
    assert "hora" not in {p["id"] for p in normalizacion.reglas()["patrones"]}


def test_politica_expande_patrones_a_literales():
    uuid = "0f3e8f73-e0b1-4d5b-a2b5-eac17a579ff9"
    g1 = {"t": f"{uuid} creado 2026-11-01T10:00:00Z por ana@x.com en /proyectos/12/datos"}
    g2 = {"t": "creado 2026-11-02T11:00:00Z por ana@x.com en /proyectos/123/datos"}
    rules = normalizacion.politica(normalizacion.reglas(), g1, g2)["rules"]
    m = {r["match"]: r["replacement"] for r in rules}
    assert m["2026-11-01T10:00:00Z"] == m["2026-11-02T11:00:00Z"] == "«fecha»"
    assert m["ana@x.com"] == "«email»"
    assert m[uuid] == "«uuid»"
    assert m["/123"] == m["/12"] == "/«id»"
    # los más largos primero, para que "/12" no muerda "/123"
    assert [r["match"] for r in rules].index("/123") < [r["match"] for r in rules].index("/12")


@pytest.mark.rea
def test_rea_real_dos_grabaciones_de_una_pagina_estatica_no_cambian(tmp_path):
    from dogfood.rea.escenario import CAPTURA, chromium

    if not adaptador.disponible():
        pytest.skip("sin rea")
    sitio = tmp_path / "sitio"
    sitio.mkdir()
    (sitio / "index.html").write_text(
        '<html><body><h1>Hola</h1><input id="q"><button id="b">Ir</button></body></html>'
    )
    srv = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(sitio))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    escenario = {
        "browser": {"mode": "launch", "executable_path": chromium()},
        "command_timeout_ms": 60000,
        "start_url": {"url": url},
        "capture": CAPTURA,
        "actions": [
            {
                "step_id": "q",
                "action": "fill",
                "timeout_ms": 15000,
                "locator": {"kind": "css", "selector": "#q"},
                "value": {"source": "literal", "value": "hola"},
            },
            {
                "step_id": "b",
                "action": "click",
                "timeout_ms": 15000,
                "locator": {"kind": "role", "role": "button", "name": "Ir"},
            },
        ],
    }
    try:
        a = adaptador.grabar(escenario, tmp_path / "a")
        b = adaptador.grabar(escenario, tmp_path / "b")
        r = adaptador.comparar(a, b, normalizacion.reglas())
    finally:
        srv.shutdown()
    assert r["overall_status"] == "unchanged", json.dumps(r)[:2000]
    assert Path(a).exists()
