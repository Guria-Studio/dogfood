"""El detector del objetivo con los datos de la corrida 20261101-125232-2-85b1 (F10.1.T3).

En esa corrida salió «detector dogfood.deteccion.objetivo.detectar falló» con
`AttributeError: 'ContextoDeteccion' object has no attribute 'objetivo'`: ningún verificador de
predicts llegó a correr. `tests/fixtures/corrida-10/` trae `corrida.json`, `personas.json`
(contraseñas redactadas) y el `historial.json` de cada ejecución. La instancia ya no existe; la
respuesta grabada de la API es la de `logs/api.log`: `POST /api/auth/login` → 404 (dogfood le
hablaba directo a la API, que sirve sus rutas sin `/api`).
"""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx

from dogfood.deteccion import objetivo
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    DatasetSintetico,
    Ejecucion,
    Gravedad,
    Instancia,
    Persona,
)
from dogfood.objetivos.predicts import aislamiento
from dogfood.objetivos.predicts.cliente import ErrorSesion, cliente_para

FIX = Path(__file__).parent / "fixtures" / "corrida-10"
API = "http://localhost:18100"  # el api_url que tenía la corrida


def _ejecuciones() -> list[Ejecucion]:
    out = []
    for f in sorted((FIX / "ejecuciones").glob("E*.json")):
        e = Ejecucion.model_validate_json(f.read_text())
        # runs/<corrida>/ejecuciones/<id>/historial.json → la carpeta de la fixture
        e.ruta_historial = FIX / "ejecuciones" / e.id / "historial.json"
        out.append(e)
    return out


def _ctx(cliente_api=None, ejecuciones=None, grabado=False) -> ContextoDeteccion:
    corrida = Corrida.model_validate_json((FIX / "corrida.json").read_text())
    ejecuciones = ejecuciones or _ejecuciones()
    datasets = {
        d: DatasetSintetico(
            id=d,
            perfil="farmacia",
            ruta_csv=FIX / "datos" / d / "ventas.csv",
            ruta_verdad=FIX / "datos" / d / "verdad.json",
            n_clientes=0,
            n_filas=0,
            semilla=2,
        )
        for d in {e.dataset_id for e in ejecuciones if e.dataset_id}
    }
    instancia = Instancia(
        base_url="http://localhost:18080", api_url=API, proyecto_compose="p", commit=corrida.commit
    )
    return ContextoDeteccion(
        corrida=corrida,
        instancia=instancia,
        ejecuciones=ejecuciones,
        datasets=datasets,
        cliente_api=(lambda p: cliente_para(instancia, p)) if grabado else cliente_api,
        logs={},
    )


@respx.mock(assert_all_called=False)
def test_regresion_contexto_sin_objetivo_ya_no_rompe(respx_mock):
    """El caso exacto: `ContextoDeteccion` real (sin atributo `objetivo`)."""
    respx_mock.post(f"{API}/api/auth/login").respond(404, json={"detail": "Not Found"})
    ctx = _ctx(grabado=True)
    assert not hasattr(ctx, "objetivo")
    hs = objetivo.detectar(ctx)
    assert not [h for h in hs if "falló" in h.titulo]


@respx.mock(assert_all_called=False)
def test_corrida_con_respuestas_grabadas(respx_mock):
    login = respx_mock.post(f"{API}/api/auth/login").respond(404, json={"detail": "Not Found"})
    hs = objetivo.detectar(_ctx(grabado=True))
    # El oráculo sí intentó entrar con la cuenta de cada persona con dataset (antes no llegaba).
    assert login.called
    # Ninguna ejecución confirmó empresa (el login de confirmación también dio 404).
    # Las reglas ahora leen las personas de personas.json y miran el idioma de cada pantalla: las
    # pantallas en portugués de las personas pt-BR («revise o que…») no son mezcla de idiomas.
    assert [h.titulo for h in hs] == ["auditoría de aislamiento no ejecutada"]


def test_regresion_portugues_no_es_espanol():
    from dogfood.objetivos.predicts.reglas import idioma_de_frase

    assert idioma_de_frase("Preenchemos o que conseguimos detectar; revise o que estiver.") != "es"
    assert idioma_de_frase("Envie seu histórico de compras e o predicts estima a compra.") == "pt"
    assert idioma_de_frase("Sube tu historial de compras y predicts estima la compra.") == "es"


def test_verificador_que_lanza_deja_hallazgo_y_los_demas_corren():
    llamados = []

    def bueno(_c):
        llamados.append("bueno")
        return []

    def roto(_c):
        raise KeyError("paths")

    ctx = _ctx(lambda _p: None)
    ctx.objetivo = SimpleNamespace(verificadores=lambda: [bueno, roto, bueno])  # type: ignore[attr-defined]
    hs = objetivo.detectar(ctx)
    assert llamados == ["bueno", "bueno"]
    (h,) = hs
    assert h.gravedad == Gravedad.baja
    assert "roto" in h.titulo and "KeyError" in h.titulo
    assert "detectar falló" not in h.titulo


def test_regresion_aislamiento_pasa_la_persona_y_sobrevive_al_login():
    """Antes `aislamiento` pasaba el `persona_id` (un str) a `cliente_api` y no atrapaba el 401."""
    ejecuciones = _ejecuciones()
    for e, emp in zip(ejecuciones[1:3], ("emp-1", "emp-2"), strict=True):
        e.empresa_id = emp
    recibidos = []

    def cliente_api(persona):
        recibidos.append(persona)
        raise ErrorSesion("POST /auth/login: 401")

    hs = aislamiento.verificar(_ctx(cliente_api, ejecuciones))
    assert all(isinstance(p, Persona) for p in recibidos) and len(recibidos) == 2
    assert [h.titulo for h in hs] == ["auditoría de aislamiento no ejecutada"]


@pytest.mark.parametrize("cuerpo", ["<!doctype html>", {"detail": "Not Found"}])
@respx.mock
def test_aislamiento_openapi_por_el_proxy(respx_mock, cuerpo):
    """Por el proxy del web `/openapi.json` es el index del SPA: se lee `/api/openapi.json` y sus
    rutas (sin `/api`) se prueban con el prefijo."""
    kw = {"text": cuerpo} if isinstance(cuerpo, str) else {"json": cuerpo}
    respx_mock.get(f"{API}/openapi.json").respond(200, **kw)
    respx_mock.get(f"{API}/api/openapi.json").respond(
        200, json={"paths": {"/proyectos/{proyecto_id}": {"get": {}}}}
    )
    rutas = aislamiento._rutas_con_parametro(SimpleNamespace(_http=httpx.Client(base_url=API)))
    assert ("GET", "/api/proyectos/{proyecto_id}", ["proyectos"]) in rutas


def test_fixture_sin_contrasenas():
    assert {p["contrasena"] for p in json.loads((FIX / "personas.json").read_text())} == {
        "redactada"
    }
