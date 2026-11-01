from pathlib import Path

from test_bucle import (
    LOGIN,
    DriverFalso,
    cfg,
    correr,
)
from test_driver_android import Falso

from dogfood.dominio import CoberturaSemantica
from dogfood.drivers.android import Adb, DriverAndroid
from dogfood.drivers.base import ElementoUI, Observacion

FIX = Path(__file__).parent / "fixtures" / "flutter"


async def observar(tmp_path, nombre):
    falso = Falso(ui=(FIX / nombre).read_bytes())
    d = DriverAndroid(Adb("S", runner=falso), "br.com.rupies.profissional")
    await d.iniciar(tmp_path)
    return await d.observar(1)


async def test_flutter_etiquetado(tmp_path):
    obs = await observar(tmp_path, "login_etiquetado.xml")
    assert obs.cobertura.flutter and not obs.cobertura.ciega
    assert {"E-mail", "Senha", "Entrar"} <= {e.texto for e in obs.elementos}


async def test_nativo_sin_cobertura(tmp_path):
    assert (await observar(tmp_path, "nativo.xml")).cobertura is None


def elementos5():
    return [
        ElementoUI(id=f"e{i}", texto=f"t{i}", bounds=(0, i * 50, 100, i * 50 + 40), clicable=True)
        for i in range(5)
    ]


class DriverCiego(DriverFalso):
    def __init__(self, ciega):
        super().__init__(elementos=elementos5())
        self.ciega = ciega

    async def observar(self, n):
        o = await super().observar(n)
        return Observacion(
            **{**o.model_dump(), "cobertura": CoberturaSemantica(flutter=True, ciega=self.ciega)}
        )


async def test_ciega_lleva_imagen_y_texto(tmp_path):
    _, _, backend, _ = await correr(tmp_path, LOGIN, driver=DriverCiego(True))
    ll = backend.llamadas[0]
    assert len(ll["imagenes"]) == 1 and "no expone Semantics" in ll["prompt"]
    assert "1080x2400" in ll["prompt"]


async def test_no_ciega_sin_imagen(tmp_path):
    _, _, backend, _ = await correr(tmp_path, LOGIN, driver=DriverCiego(False))
    assert backend.llamadas[0]["imagenes"] == []
    assert "Semantics" not in backend.llamadas[0]["prompt"]


async def test_ciega_sin_capturas_por_config(tmp_path):
    e, _, backend, _ = await correr(tmp_path, LOGIN, driver=DriverCiego(True), c=cfg(0))
    assert backend.llamadas[0]["imagenes"] == []
    assert "pantalla ciega sin captura por configuración" in e.pasos[0].observado
