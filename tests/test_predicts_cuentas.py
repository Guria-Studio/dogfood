from datetime import UTC, datetime

import httpx
import pytest
import respx

from dogfood.dominio import Instancia, Persona
from dogfood.objetivos.predicts import cuentas, entorno

TOKEN = "aB3_-" * 8 + "xyz"  # 43 caracteres
LOG = f"""api-1  | INFO otra cosa
api-1  | Email (modo dev) a ana@x.test
Asunto: Recuperá tu contraseña

Recibimos un pedido para restablecer tu contraseña en predicts.

Usá este código para elegir una nueva contraseña. Vence en 1 hora y solo se puede usar una vez:

{TOKEN}

Si no fuiste vos, podés ignorar este email.
"""
DESDE = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def instancia():
    return Instancia(base_url="http://w", api_url="http://api", proyecto_compose="p", commit="c")


@pytest.fixture
def persona():
    return Persona(
        id="p1", nombre="Ana", email="ana@x.test", contrasena="secreta", empresa="E",
        rubro="r", idioma="es", destreza=3, paciencia=3, intencion="explorar", semilla=1,
    )  # fmt: skip


def _logs(monkeypatch, texto):
    monkeypatch.setattr(entorno, "logs", lambda inst, desde: {"api": texto, "worker": ""})


def test_extrae_token(monkeypatch, instancia):
    _logs(monkeypatch, LOG)
    assert cuentas.token_recuperacion(instancia, "ana@x.test", DESDE) == TOKEN


def test_none_si_email_no_aparece_o_no_hay_logs_desde(monkeypatch, instancia):
    _logs(monkeypatch, LOG)
    assert cuentas.token_recuperacion(instancia, "otra@x.test", DESDE) is None
    _logs(monkeypatch, "")  # --since no devuelve nada anterior a `desde`
    assert cuentas.token_recuperacion(instancia, "ana@x.test", DESDE) is None


def test_confirmar_registro(instancia, persona):
    with respx.mock:
        respx.post("http://api/api/auth/login").mock(return_value=httpx.Response(200, json={}))
        respx.get("http://api/api/auth/yo").mock(
            return_value=httpx.Response(200, json={"empresa": {"id": "emp-1"}})
        )
        assert cuentas.confirmar_registro(instancia, persona) == "emp-1"
    with respx.mock:
        respx.post("http://api/api/auth/login").mock(return_value=httpx.Response(401))
        assert cuentas.confirmar_registro(instancia, persona) is None


def test_credenciales_estable(persona):
    assert (
        cuentas.credenciales(persona) == cuentas.credenciales(persona) == ("ana@x.test", "secreta")
    )


def test_herramienta(monkeypatch, instancia, persona):
    _logs(monkeypatch, LOG)
    (pedir,) = cuentas.herramientas_extra(instancia, persona)
    assert pedir() == TOKEN
