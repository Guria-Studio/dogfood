import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from dogfood import llm
from dogfood.config import Config, ErrorSecreto

CLAVE = "sk-super-secreta-123"
YAML = """
roles: {persona: [m/uno, m/dos], juez: [m/j], dedupe: [m/d], redactor: [m/r]}
precios_usd_por_millon: {m/uno: {entrada: 2.0, salida: 10.0}}
"""


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    (tmp_path / "dogfood.yaml").write_text(YAML)
    d = tmp_path / "cfg"
    d.mkdir()
    (d / "router.env").write_text(
        f"ROUTER_BASE_URL=http://router.test/v1\nROUTER_API_KEY={CLAVE}\n"
    )
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(d))
    return Config.cargar(tmp_path)


def test_secreto_faltante_nombra_archivo_sin_valores(cfg):
    with pytest.raises(ErrorSecreto) as e:
        cfg.secreto("ROUTER_OTRA")
    assert "ROUTER_OTRA" in str(e.value) and "router.env" in str(e.value)
    assert CLAVE not in str(e.value)


def test_repr_no_contiene_api_key(cfg):
    assert CLAVE not in repr(cfg) and CLAVE not in str(cfg)
    assert "***" in repr(cfg)


def test_cliente_persona_usa_primer_modelo(cfg):
    c = llm.cliente_para("persona", cfg=cfg)
    assert c.model == "m/uno"
    assert str(c.base_url).startswith("http://router.test/v1")


def test_contador_calcula_costo_y_avisa_una_vez(cfg, caplog):
    c = llm.ContadorUso(cfg)
    uso = c.registrar("persona", "m/uno", 1_000_000, 100_000)
    assert uso.costo_usd == pytest.approx(3.0)
    assert c.registrar("juez", "m/j", 5, 5).costo_usd == 0
    c.registrar("juez", "m/j", 5, 5)
    assert sum("sin precio" in r.message for r in caplog.records) == 1


class Veredicto(BaseModel):
    ok: bool


@respx.mock
async def test_completar_json_envia_json_schema_y_parsea(cfg):
    ruta = respx.post("http://router.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )
    )
    assert (await llm.completar_json("juez", "hola", Veredicto, cfg=cfg)).ok is True
    cuerpo = json.loads(ruta.calls[0].request.content)
    assert cuerpo["response_format"]["type"] == "json_schema"
    assert "tool_choice" not in cuerpo
