import httpx
import pytest
import respx

from dogfood.dominio import Instancia, Persona
from dogfood.objetivos.predicts.cliente import ErrorSesion, PredictsCliente, cliente_para

API = "http://api"


@respx.mock
def test_login_guarda_cookie_y_la_envia_en_yo():
    respx.post(f"{API}/api/auth/login").respond(200, headers={"set-cookie": "sid=abc; Path=/"})
    yo = respx.get(f"{API}/api/auth/yo").respond(200, json={"empresa": {"id": "e1"}})
    c = PredictsCliente(API)
    c.login("a@x.test", "pw")
    assert c.yo() == {"empresa": {"id": "e1"}}
    assert "sid=abc" in yo.calls[0].request.headers["cookie"]


@respx.mock
def test_resultados_sigue_la_paginacion():
    def pagina(request):
        p = int(request.url.params["pagina"])
        filas = [{"n": i} for i in range((p - 1) * 2, min(p * 2, 5))]
        return httpx.Response(
            200, json={"pagina": p, "tam_pagina": 2, "total": 5, "resultados": filas}
        )

    ruta = respx.get(f"{API}/api/analisis/a1/resultados").mock(side_effect=pagina)
    c = PredictsCliente(API)
    assert [f["n"] for f in c.resultados("a1", "riesgo", tam_pagina=2)] == [0, 1, 2, 3, 4]
    assert ruta.call_count == 3
    assert len(c.resultados("a1", "riesgo", todas_las_paginas=False, tam_pagina=2)) == 2


@respx.mock
def test_401_da_error_sesion():
    respx.get(f"{API}/api/proyectos").respond(401)
    with pytest.raises(ErrorSesion):
        PredictsCliente(API).proyectos()


@respx.mock
def test_get_crudo_devuelve_estado_en_403():
    respx.get(f"{API}/api/datasets/x").respond(403, json={"error": "prohibido"})
    respx.get(f"{API}/api/texto").respond(200, text="hola")
    c = PredictsCliente(API)
    assert c.get_crudo("/api/datasets/x") == (403, {"error": "prohibido"})
    assert c.get_crudo("/api/texto") == (200, "hola")


@respx.mock
def test_cliente_para_hace_login_con_las_credenciales():
    login = respx.post(f"{API}/api/auth/login").respond(200)
    inst = Instancia(base_url="http://w", api_url=API, proyecto_compose="p", commit="c")
    persona = Persona(
        id="p1", nombre="Ana", email="ana@x.test", contrasena="secreta", empresa="E",
        rubro="r", idioma="es", destreza=3, paciencia=3, intencion="explorar", semilla=1,
    )  # fmt: skip
    cliente_para(inst, persona)
    assert login.calls[0].request.content == b'{"email":"ana@x.test","contrasena":"secreta"}'
