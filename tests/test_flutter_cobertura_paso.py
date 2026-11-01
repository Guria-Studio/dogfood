from datetime import datetime

from test_bucle import DriverFalso, correr, decision

from dogfood.deteccion.flutter import detectar
from dogfood.dominio import (
    CoberturaSemantica,
    ContextoDeteccion,
    Corrida,
    Ejecucion,
    Gravedad,
    Instancia,
    Paso,
    TipoHallazgo,
)

AHORA = datetime(2026, 1, 1)
CIEGA = CoberturaSemantica(flutter=True, nodos=0, ciega=True)


def _paso(**kw):
    return Paso(n=1, url="#/sign-in", pantalla="sign-in", accion="x", ts=AHORA, **kw)


def _ctx(driver, pasos):
    e = Ejecucion(
        id="e", persona_id="p", escenario_id="s", modelo="m", estado="ok", pasos=pasos,
        driver=driver,
    )  # fmt: skip
    return ContextoDeteccion(
        corrida=Corrida(
            id="c", objetivo="o", ref="r", commit="x", semilla=1, inicio=AHORA, estado="ok"
        ),
        instancia=Instancia(base_url="b", api_url="a", proyecto_compose="p", commit="x"),
        ejecuciones=[e],
        datasets={},
        cliente_api=lambda _p: None,
        logs={},
    )


def test_paso_viejo_sin_cobertura_carga():
    d = _paso().model_dump(mode="json")
    d.pop("cobertura")
    assert Paso.model_validate(d).cobertura is None


async def test_bucle_guarda_la_cobertura(tmp_path):
    class Ciego(DriverFalso):
        async def observar(self, n):
            return (await super().observar(n)).model_copy(update={"cobertura": CIEGA})

    e, *_ = await correr(tmp_path, [decision(terminado=True)], driver=Ciego())
    assert e.pasos and all(p.cobertura == CIEGA for p in e.pasos)


def test_web_ciega_da_hallazgo_y_sin_cobertura_no():
    hs = detectar(_ctx("web", [_paso(cobertura=CIEGA), _paso(cobertura=CIEGA)]))
    assert len(hs) == 1
    assert hs[0].tipo == TipoHallazgo.accesibilidad and hs[0].gravedad == Gravedad.media
    assert detectar(_ctx("web", [_paso()])) == []
