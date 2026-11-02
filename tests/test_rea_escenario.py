import json

import pytest

from dogfood.dominio import Ejecucion, Instancia
from dogfood.rea import escenario

CONTRASENA = "Clave-Secreta-99"


@pytest.fixture(autouse=True)
def sin_playwright(monkeypatch):
    monkeypatch.setattr(escenario, "chromium", lambda: "/ms-playwright/chrome")


def _el(tag, **attrs):
    ax = attrs.pop("ax_name", None)
    return {"node_name": tag.upper(), "attributes": attrs, "ax_name": ax}


def _paso(url, acciones, elementos):
    return {
        "model_output": {"action": acciones},
        "state": {"url": url, "interacted_element": elementos},
        "result": [],
    }


ORIGEN = "http://localhost:18080"
HISTORIA = [
    _paso(
        f"{ORIGEN}/login",
        [
            {"input": {"index": 12, "text": "ana@dogfood.example.com", "clear": True}},
            {"input": {"index": 13, "text": CONTRASENA, "clear": True}},
            {"send_keys": {"keys": "Enter"}},
        ],
        [_el("input", name="email", type="email"), _el("input", id="clave", type="password"), None],
    ),
    _paso(
        f"{ORIGEN}/proyectos",
        [{"click": {"index": 157}}, {"navigate": {"url": f"{ORIGEN}/proyectos/7?tab=datos"}}],
        [_el("button", ax_name="Nuevo proyecto"), None],
    ),
]


def _ejecucion(tmp_path, historia, estado="ok"):
    ruta = tmp_path / "historial.json"
    ruta.write_text(json.dumps({"history": historia}))
    return Ejecucion(
        id="C-E1", persona_id="P1", escenario_id="e", modelo="m", estado=estado,
        ruta_historial=ruta,
    )  # fmt: skip


INSTANCIA = Instancia(
    base_url="http://127.0.0.1:28080", api_url="http://127.0.0.1:28080", proyecto_compose="x",
    commit="abc",
)  # fmt: skip


def test_historial_se_traduce_a_escenario_valido(tmp_path):
    esc = escenario.desde_ejecucion(
        _ejecucion(tmp_path, HISTORIA), INSTANCIA, contrasena=CONTRASENA
    )
    assert esc["browser"] == {"mode": "launch", "executable_path": "/ms-playwright/chrome"}
    assert esc["start_url"] == {"url": "http://127.0.0.1:28080"}
    assert esc["avisos"] == []
    a = esc["actions"]
    assert [x["action"] for x in a] == ["fill", "fill", "press", "click", "goto"]
    assert all(x["timeout_ms"] > 0 for x in a)
    assert len({x["step_id"] for x in a}) == len(a)
    assert a[0]["locator"] == {"kind": "css", "selector": 'input[name="email"]'}
    assert a[0]["value"] == {"source": "literal", "value": "ana@dogfood.example.com"}
    assert a[2]["locator"] == {"kind": "css", "selector": "#clave"}
    assert a[2]["key"] == "Enter"
    assert a[3]["locator"] == {"kind": "role", "role": "button", "name": "Nuevo proyecto"}
    # la URL grabada se reescribe a la instancia aislada
    assert a[4]["destination"] == {"url": "http://127.0.0.1:28080/proyectos/7?tab=datos"}


def test_la_contrasena_va_como_secreto_y_no_literal(tmp_path):
    esc = escenario.desde_ejecucion(
        _ejecucion(tmp_path, HISTORIA), INSTANCIA, contrasena=CONTRASENA
    )
    assert esc["actions"][1]["value"] == {"source": "secret", "secret_id": "contrasena"}
    assert esc["secrets"] == [
        {"secret_id": "contrasena", "environment_variable": "DOGFOOD_REA_CONTRASENA"}
    ]
    assert CONTRASENA not in json.dumps(esc)


def test_un_campo_password_es_secreto_aunque_no_se_sepa_la_contrasena(tmp_path):
    esc = escenario.desde_ejecucion(_ejecucion(tmp_path, HISTORIA), INSTANCIA)
    assert esc["actions"][1]["value"]["source"] == "secret"


def test_una_accion_no_traducible_corta_el_escenario_con_su_aviso(tmp_path):
    historia = [
        HISTORIA[0],
        _paso(f"{ORIGEN}/proyectos", [{"upload_file": {"index": 3, "path": "/x.csv"}}], [None]),
        HISTORIA[1],
    ]
    esc = escenario.desde_ejecucion(_ejecucion(tmp_path, historia), INSTANCIA)
    assert len(esc["actions"]) == 3
    assert esc["avisos"] == [
        "escenario cortado en el paso 2: la acción 'upload_file' no tiene equivalente en REA"
    ]


def test_un_click_sin_locator_o_fuera_de_la_app_corta(tmp_path):
    sin_loc = [_paso(f"{ORIGEN}/", [{"click": {"index": 1}}], [_el("div")])]
    esc = escenario.desde_ejecucion(_ejecucion(tmp_path, sin_loc), INSTANCIA)
    assert esc["actions"] == [] and "paso 1" in esc["avisos"][0]
    fuera = [_paso(f"{ORIGEN}/", [{"navigate": {"url": "https://google.com/"}}], [None])]
    esc = escenario.desde_ejecucion(_ejecucion(tmp_path, fuera), INSTANCIA)
    assert esc["actions"] == [] and "google.com" in esc["avisos"][0]


def test_done_termina_sin_aviso(tmp_path):
    historia = [*HISTORIA, _paso(f"{ORIGEN}/", [{"done": {"text": "listo"}}], [None])]
    esc = escenario.desde_ejecucion(_ejecucion(tmp_path, historia), INSTANCIA)
    assert esc["avisos"] == [] and len(esc["actions"]) == 5


def test_sin_historial_de_browser_use_avisa(tmp_path):
    e = _ejecucion(tmp_path, [])
    e.ruta_historial.write_text(e.model_dump_json())  # el almacén guarda la Ejecucion ahí
    esc = escenario.desde_ejecucion(e, INSTANCIA)
    assert esc["actions"] == [] and "historial de browser-use" in esc["avisos"][0]


def test_una_ejecucion_no_exitosa_no_se_graba(tmp_path):
    with pytest.raises(ValueError):
        escenario.desde_ejecucion(_ejecucion(tmp_path, HISTORIA, estado="fallo"), INSTANCIA)
