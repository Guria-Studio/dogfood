import json
import os
import stat
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import BaseModel

from dogfood import llm
from dogfood.backends.api import BackendApi
from dogfood.backends.base import ErrorMotor
from dogfood.backends.claude_code import BackendClaudeCode
from dogfood.config import Config

RAIZ = Path(__file__).resolve().parents[1]
YAML = """
roles: {persona: [m/uno, m/dos], juez: [m/j], dedupe: [m/d], redactor: [m/r]}
precios_usd_por_millon: {m/uno: {entrada: 2.0, salida: 10.0}}
motores: {persona: claude_code, juez: api}
claude_code: {modelos: {persona: sonnet}, timeout_s: 5}
"""


class Veredicto(BaseModel):
    ok: bool


SALIDA = {
    "result": "",
    "structured_output": {"ok": True},
    "session_id": "sesion-1",
    "is_error": False,
    "total_cost_usd": 0.05,
    "usage": {
        "input_tokens": 10,
        "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 5,
        "output_tokens": 7,
    },
}


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    (tmp_path / "dogfood.yaml").write_text(YAML)
    d = tmp_path / "cfg"
    d.mkdir()
    (d / "router.env").write_text("ROUTER_BASE_URL=http://router.test/v1\nROUTER_API_KEY=k\n")
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(d))
    return Config.cargar(tmp_path)


@pytest.fixture
def claude(tmp_path, monkeypatch):
    """Instala un `claude` falso; devuelve (fijar_salida, args_recibidos, cwd_recibido)."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    salida = tmp_path / "salida.txt"
    args = tmp_path / "args.json"
    cwd = tmp_path / "cwd.txt"
    script = bin_ / "claude"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"json.dump(sys.argv[1:], open({str(args)!r}, 'w'))\n"
        f"open({str(cwd)!r}, 'w').write(os.getcwd())\n"
        f"sys.stdout.write(open({str(salida)!r}).read())\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    salida.write_text(json.dumps(SALIDA))

    def fijar(texto: str):
        salida.write_text(texto)

    return fijar, lambda: json.loads(args.read_text()), lambda: Path(cwd.read_text())


async def test_claude_code_devuelve_salida_sesion_y_uso(cfg, claude):
    r, uso, sesion = await BackendClaudeCode("sonnet", cfg).completar_json("hola", Veredicto)
    assert r == Veredicto(ok=True) and sesion == "sesion-1"
    assert (uso.tokens_in, uso.tokens_cache, uso.tokens_out) == (10, 105, 7)
    assert uso.costo_usd == 0 and uso.costo_equivalente_usd == 0.05


async def test_argumentos(cfg, claude):
    _, args, _ = claude
    b = BackendClaudeCode("sonnet", cfg)
    await b.completar_json("hola", Veredicto)
    a = args()
    assert "-p" in a and "--strict-mcp-config" in a and "--mcp-config" not in a
    assert a[a.index("--output-format") + 1] == "json"
    assert a[a.index("--model") + 1] == "sonnet"
    assert json.loads(a[a.index("--json-schema") + 1]) == Veredicto.model_json_schema()
    assert "--resume" not in a
    await b.completar_json("hola", Veredicto, sesion="abc")
    a = args()
    assert a[a.index("--resume") + 1] == "abc"


async def test_imagenes_por_ruta_y_add_dir(cfg, claude, tmp_path):
    _, args, _ = claude
    img = tmp_path / "caps" / "p1.png"
    img.parent.mkdir()
    img.write_bytes(b"x")
    _, uso, _ = await BackendClaudeCode("sonnet", cfg).completar_json(
        "mira", Veredicto, imagenes=[img]
    )
    a = args()
    assert str(img) in a[a.index("-p") + 1] and uso.capturas == 1
    assert a[a.index("--allowedTools") + 1] == "Read"
    assert a[a.index("--add-dir") + 1] == str(img.parent)


async def test_cwd_fuera_del_repo(cfg, claude):
    _, _, cwd = claude
    await BackendClaudeCode("sonnet", cfg).completar_json("hola", Veredicto)
    assert RAIZ not in (cwd(), *cwd().parents)


async def test_sin_claude_en_path(cfg, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ErrorMotor, match="instala Claude Code"):
        await BackendClaudeCode("sonnet", cfg).completar_json("hola", Veredicto)


async def test_sin_sesion(cfg, claude):
    fijar, _, _ = claude
    fijar(json.dumps({"is_error": True, "result": "Not logged in · Please run /login"}))
    with pytest.raises(ErrorMotor, match="/login con la cuenta del plan Max"):
        await BackendClaudeCode("sonnet", cfg).completar_json("hola", Veredicto)


async def test_respuesta_invalida(cfg, claude):
    fijar, _, _ = claude
    fijar(json.dumps({"structured_output": {"otro": 1}, "session_id": "s"}))
    with pytest.raises(ErrorMotor, match="otro"):
        await BackendClaudeCode("sonnet", cfg).completar_json("hola", Veredicto)


async def test_result_como_json_de_respaldo(cfg, claude):
    fijar, _, _ = claude
    fijar(json.dumps({"result": '{"ok": false}', "session_id": "s"}))
    r, _, _ = await BackendClaudeCode("sonnet", cfg).completar_json("hola", Veredicto)
    assert r.ok is False


async def test_timeout(cfg, claude, monkeypatch):
    cfg.claude_code.timeout_s = 0.2
    bin_ = Path(os.environ["PATH"].split(os.pathsep)[0])
    (bin_ / "claude").write_text("#!/bin/sh\nexec sleep 5\n")
    with pytest.raises(ErrorMotor, match="0.2 s"):
        await BackendClaudeCode("sonnet", cfg).completar_json("hola", Veredicto)


@respx.mock
async def test_api_manda_imagenes_y_cuenta_capturas(cfg, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"png")
    ruta = respx.post("http://router.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0},
            },
        )
    )
    contador = llm.ContadorUso(cfg)
    b = BackendApi("m/uno", cfg, contador, rol="persona")
    r, uso, sesion = await b.completar_json("mira", Veredicto, imagenes=[img])
    partes = json.loads(ruta.calls[0].request.content)["messages"][0]["content"]
    assert partes[1]["type"] == "image_url"
    assert partes[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert uso.capturas == 1 and uso.costo_usd == pytest.approx(2.0) and sesion is None
    assert contador.usos[0].backend == "api" and r.ok


def test_backend_para_elige_motor(cfg):
    assert isinstance(llm.backend_para("persona", cfg), BackendClaudeCode)
    assert llm.backend_para("persona", cfg).modelo == "sonnet"
    b = llm.backend_para("juez", cfg)
    assert isinstance(b, BackendApi) and b.modelo == "m/j"
    cfg.motores.juez = "otro"
    with pytest.raises(ValueError, match="api, claude_code"):
        llm.backend_para("juez", cfg)


def test_backend_claude_code_modelo_de_roles_si_falta(cfg):
    cfg.claude_code.modelos = {}
    assert llm.backend_para("persona", cfg, indice=1).modelo == "m/dos"


@respx.mock
async def test_completar_json_mismo_cuerpo(cfg):
    ruta = respx.post("http://router.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok": true}'}}]}
        )
    )
    assert (await llm.completar_json("juez", "hola", Veredicto, cfg)) == Veredicto(ok=True)
    cuerpo = json.loads(ruta.calls[0].request.content)
    assert cuerpo == {
        "model": "m/j",
        "stream": False,
        "messages": [{"role": "user", "content": "hola"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "Veredicto",
                "strict": True,
                "schema": Veredicto.model_json_schema(),
            },
        },
    }
