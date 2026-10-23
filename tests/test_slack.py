from datetime import datetime

import httpx
import pytest
import respx

from dogfood.config import Config
from dogfood.dominio import Corrida, Gravedad, Hallazgo, TipoHallazgo
from dogfood.reporte import slack
from dogfood.reporte.issues import ResultadoIssue
from dogfood.reporte.slack import Resumen, avisar

URL = "https://hooks.slack.com/services/T000/B000/abcdefghijklmnop"
SECRETO = "Sup3rSecreta-slack-77"
COMMIT = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"


@pytest.fixture
def config(tmp_path, monkeypatch):
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    (raiz / "dogfood.yaml").write_text("roles: {}\n")
    secretos = tmp_path / "secretos"
    secretos.mkdir()
    (secretos / "slack.env").write_text(f"SLACK_WEBHOOK_URL={URL}\n")
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(secretos))
    return Config.cargar(raiz)


@pytest.fixture
def corrida():
    return Corrida(
        id="c1",
        objetivo="predicts",
        ref="main",
        commit=COMMIT,
        semilla=7,
        inicio=datetime(2026, 1, 1),
        estado="ok",
    )


def hallazgo(gravedad):
    return Hallazgo(
        tipo=TipoHallazgo.friccion,
        gravedad=gravedad,
        pantalla="/x",
        titulo="t",
        descripcion="d",
        semilla=1,
        commit=COMMIT,
    )


def resumen(**kw):
    base = {
        "personas": 4,
        "exitos": 3,
        "hallazgos": [
            hallazgo(Gravedad.critica),
            hallazgo(Gravedad.media),
            hallazgo(Gravedad.media),
        ],
        "issues": [
            ResultadoIssue(
                hallazgo_id="h1",
                huella="x",
                accion="crear",
                publicado=True,
                issue_url="https://github.com/hectorcanaimero/predicts/issues/12",
            ),
            ResultadoIssue(
                hallazgo_id="h2",
                huella="y",
                accion="comentar",
                publicado=True,
                nuevo=False,
                issue_url="https://github.com/hectorcanaimero/predicts/issues/9",
            ),
        ],
        "ruta_reporte": "runs/c1/reporte.html",
        "costo_usd": 1.5,
        "duracion_s": 125,
    }
    base.update(kw)
    return Resumen(**base)


@respx.mock
def test_post_lleva_texto_con_conteos(config, corrida):
    ruta = respx.post(URL).mock(return_value=httpx.Response(200, text="ok"))

    assert avisar(corrida, resumen(), config) is True

    texto = ruta.calls.last.request.read().decode()
    assert "tasa de éxito 75% (3/4)" in texto
    assert "Personas: 4" in texto
    assert "1 crítica · 2 media" in texto
    assert "<https://github.com/hectorcanaimero/predicts/issues/12|#12>" in texto
    assert "runs/c1/reporte.html" in texto
    assert "USD 1.50 · Duración: 2 min 5 s" in texto
    assert "commit a1b2c3d" in texto


@respx.mock
def test_maximo_diez_links(config, corrida):
    issues = [
        ResultadoIssue(
            hallazgo_id=f"h{i}",
            huella=str(i),
            accion="crear",
            issue_url=f"https://github.com/hectorcanaimero/predicts/issues/{i}",
        )
        for i in range(1, 13)
    ]
    ruta = respx.post(URL).mock(return_value=httpx.Response(200))

    avisar(corrida, resumen(issues=issues), config)

    texto = ruta.calls.last.request.read().decode()
    assert texto.count("issues/") == 10
    assert "y 2 más" in texto


@respx.mock
def test_sin_slack_env_no_envia_ni_falla(corrida, monkeypatch, tmp_path, caplog):
    (tmp_path / "dogfood.yaml").write_text("roles: {}\n")
    monkeypatch.setenv("DOGFOOD_CONFIG_DIR", str(tmp_path / "vacio"))
    sin = Config.cargar(tmp_path)
    ruta = respx.post(URL).mock(return_value=httpx.Response(200))

    assert avisar(corrida, resumen(), sin) is False

    assert ruta.call_count == 0
    assert "SLACK_WEBHOOK_URL" in caplog.text


@respx.mock
def test_error_500_se_registra_y_no_rompe(config, corrida, caplog):
    respx.post(URL).mock(return_value=httpx.Response(500, text="internal"))

    assert avisar(corrida, resumen(), config) is False

    assert "HTTP 500" in caplog.text
    assert URL not in caplog.text


@respx.mock
def test_error_de_red_no_rompe(config, corrida):
    respx.post(URL).mock(side_effect=httpx.ConnectError("caído"))

    assert avisar(corrida, resumen(), config) is False


@respx.mock
def test_secreto_plantado_no_aparece(config, corrida):
    ruta = respx.post(URL).mock(return_value=httpx.Response(200))
    corrida.objetivo = f"predicts con {SECRETO}"

    avisar(corrida, resumen(), config, secretos=[SECRETO])

    texto = ruta.calls.last.request.read().decode()
    assert SECRETO not in texto
    assert "«redactado»" in texto


@respx.mock
def test_fuga_detectada_no_envia(config, corrida, monkeypatch):
    ruta = respx.post(URL).mock(return_value=httpx.Response(200))
    monkeypatch.setattr(slack, "redactar", lambda t, s=None: t)
    corrida.objetivo = "token eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl"

    assert avisar(corrida, resumen(), config) is False
    assert ruta.call_count == 0
