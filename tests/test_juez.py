"""El juez reintenta lo transitorio, cae al siguiente modelo y, sin veredicto, no concluye."""

import httpx
import pytest

from dogfood.agente import juez as modulo
from dogfood.agente.juez import JuezNoDisponible, Veredicto, juzgar
from dogfood.backends.base import UsoBackend
from dogfood.config import Config
from dogfood.llm import ContadorUso


def error(codigo: int) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "http://router/chat/completions")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(codigo, request=req))


class Falso:
    nombre = "api"

    def __init__(self, modelo, resultados):
        self.modelo, self.resultados, self.llamadas = modelo, list(resultados), 0

    async def completar_json(self, prompt, esquema, *, imagenes=(), sesion=None):
        self.llamadas += 1
        r = self.resultados[min(self.llamadas, len(self.resultados)) - 1]
        if isinstance(r, Exception):
            raise r
        return r, UsoBackend(tokens_in=7, tokens_out=3), None


OK = Veredicto(exito=True, motivo="cumplido")
CFG = Config(roles={"juez": ["m/a", "m/b"]})


@pytest.fixture(autouse=True)
def sin_espera(monkeypatch):
    esperas: list[float] = []

    async def dormir(s):
        esperas.append(s)

    monkeypatch.setattr(modulo, "_dormir", dormir)
    return esperas


async def test_503_dos_veces_y_luego_responde(sin_espera):
    a = Falso("m/a", [error(503), error(503), OK])
    contador = ContadorUso(CFG)
    v = await juzgar("p", CFG, primero=a, respaldos=[], contador=contador)
    assert v == OK and a.llamadas == 3
    assert sin_espera == [1.0, 2.0]  # backoff exponencial
    assert len(contador.usos) == 2  # los dos fallidos; el éxito lo registra quien armó `primero`


async def test_primer_modelo_siempre_503_responde_el_segundo():
    a, b = Falso("m/a", [error(503)]), Falso("m/b", [OK])
    contador = ContadorUso(CFG)
    v = await juzgar("p", CFG, primero=a, respaldos=[b], contador=contador)
    assert v == OK and a.llamadas == 3 and b.llamadas == 1
    assert [(u.modelo, u.tokens_in) for u in contador.usos][-1] == ("m/b", 7)


async def test_todos_en_503_no_hay_veredicto():
    a, b = Falso("m/a", [error(503)]), Falso("m/b", [error(429)])
    with pytest.raises(JuezNoDisponible):
        await juzgar("p", CFG, primero=a, respaldos=[b])
    assert a.llamadas == b.llamadas == 3


async def test_400_no_se_reintenta():
    a, b = Falso("m/a", [error(400)]), Falso("m/b", [OK])
    v = await juzgar("p", CFG, primero=a, respaldos=[b])
    assert a.llamadas == 1 and v == OK


async def test_timeout_es_transitorio():
    a = Falso("m/a", [httpx.ReadTimeout("lento"), OK])
    assert await juzgar("p", CFG, primero=a, respaldos=[]) == OK and a.llamadas == 2


def test_un_solo_modelo_suma_el_respaldo_fijo():
    cfg = Config(roles={"juez": ["m/a"]})
    assert [b.modelo for b in modulo.modelos_respaldo(cfg, excluir="m/a")] == [modulo.RESPALDO]


async def test_bucle_con_juez_caido_es_no_concluyente(tmp_path, monkeypatch):
    from test_bucle import LOGIN, BackendFalso, DriverFalso, cfg, escenario, persona

    from dogfood.agente.bucle import ejecutar

    monkeypatch.setattr(modulo, "modelos_respaldo", lambda *a, **k: [])
    e = await ejecutar(
        persona(),
        escenario(),
        DriverFalso(),
        BackendFalso(LOGIN),
        Falso("m/j", [error(503)]),
        tmp_path / "e1",
        cfg=cfg(),
    )
    assert e.resultado == "no_concluyente"
    assert e.motivo_juez == "juez no disponible"
