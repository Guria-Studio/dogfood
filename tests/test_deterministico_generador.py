from pathlib import Path

import pytest

from dogfood.config import Config, ErrorSecreto
from dogfood.deterministico.generador import defines, generar_test
from dogfood.dominio import Escenario, PasoDeterministico, RecorridoDeterministico
from dogfood.objetivos.android import AndroidObjetivo

FIX = Path(__file__).parent / "fixtures" / "flutter"


def _login() -> Escenario:
    return next(e for e in AndroidObjetivo().escenarios() if e.id == "login-determinista")


def test_integration_test_login():
    t = generar_test(_login(), "integration_test")
    assert "testWidgets" in t
    assert "find.byKey(ValueKey('campo_email'))" in t
    assert "String.fromEnvironment('DOGFOOD_APP_CONTRASENA')" in t
    assert t == (FIX / "login_integration_test.dart").read_text()


def test_patrol_login():
    t = generar_test(_login(), "patrol")
    assert "patrolTest" in t and "$(#boton_entrar).tap()" in t
    assert t == (FIX / "login_patrol.dart").read_text()


def test_escapa_comillas_y_dolar():
    e = Escenario(
        id="x",
        titulo="x",
        objetivo="x",
        criterio_exito="x",
        deterministico=RecorridoDeterministico(
            pasos=[PasoDeterministico(accion="ver_texto", texto="Pagó \"$5\" y 'más'")]
        ),
    )
    assert "find.text('Pagó \"\\$5\" y \\'más\\'')" in generar_test(e, "integration_test")


def test_defines(tmp_path, monkeypatch):
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path))
    raiz = Path(__file__).parent.parent
    rec = _login().deterministico
    assert rec
    rec = rec.model_copy(
        update={"dart_defines": {"FLAVOR": "dev", "TOKEN": "{env:DOGFOOD_APP_TOKEN}"}}
    )
    (tmp_path / "flutter.env").write_text(
        "DOGFOOD_APP_EMAIL=a@b.c\nDOGFOOD_APP_CONTRASENA=s3\nDOGFOOD_APP_TOKEN=t\n"
    )
    assert defines(rec, Config.cargar(raiz)) == {
        "DOGFOOD_APP_EMAIL": "a@b.c",
        "DOGFOOD_APP_CONTRASENA": "s3",
        "FLAVOR": "dev",
        "TOKEN": "t",
    }
    (tmp_path / "flutter.env").write_text("DOGFOOD_APP_EMAIL=a@b.c\n")
    with pytest.raises(ErrorSecreto, match=r"falta DOGFOOD_APP_CONTRASENA en .*\.env"):
        defines(rec, Config.cargar(raiz))


def test_escenarios_de_ejemplo():
    por_id = {e.id: e for e in AndroidObjetivo().escenarios()}
    for id_, motor in [("login-determinista", "integration_test"), ("pago-determinista", "patrol")]:
        e = por_id[id_]
        assert e.motor == motor and e.deterministico and e.driver == "android" and e.contrato
        generar_test(e, motor)  # type: ignore[arg-type]
