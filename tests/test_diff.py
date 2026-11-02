import json
import shutil
from pathlib import Path

import pytest

from dogfood import diff as motor
from dogfood.almacen import Almacen
from dogfood.dominio import Ejecucion, Instancia

FIX = Path(__file__).parent / "fixtures" / "rea"
SECRETO = "contraseña-plantada-123"


class ReaFalso:
    """Devuelve las grabaciones y comparaciones de tests/fixtures/rea/<TC>/."""

    def grabar(self, escenario, destino, *, secretos=None):
        destino.mkdir(parents=True)
        nr = destino / "normalized_result.json"
        shutil.copy(FIX / destino.name / f"{destino.parent.name}.json", nr)
        return nr

    def comparar(self, antes, despues, reglas):
        return json.loads((FIX / antes.parent.name / "comparacion.json").read_text())


class ObjetivoFalso:
    nombre = "falso"

    def __init__(self):
        self.vivas: list[str] = []
        self.refs: list[str] = []

    def preparar(self, ref, corrida):
        self.refs.append(ref)
        self.vivas.append(ref)
        return Instancia(base_url="http://x", api_url="http://x", proyecto_compose=ref, commit=ref)

    def destruir(self, instancia):
        self.vivas.remove(instancia.proyecto_compose)


def _caso(tc):
    e = Ejecucion(id=f"e-{tc}", persona_id="p", escenario_id="s", modelo="m", estado="ok")
    return motor.CasoGrabar(tc, f"s:{tc}", f"Caso {tc}", e, SECRETO)


@pytest.fixture
def correr(tmp_path):
    def _correr(tcs):
        obj = ObjetivoFalso()
        almacen = Almacen(tmp_path / "runs")
        d = motor.diff(
            proyecto="predicts",
            objetivo=obj,
            base="master",
            nueva="pr-1",
            casos=[_caso(t) for t in tcs],
            almacen=almacen,
            rea=ReaFalso(),
            armar=lambda e, i, contrasena="": {"actions": [{"step_id": "a"}]},
        )
        assert obj.vivas == [] and obj.refs == ["master", "pr-1"]
        return d, almacen, tmp_path / "runs" / d["id"]

    return _correr


def _caso_de(d, tc):
    return next(c for c in d["casos"] if c["tc"] == tc)


def test_201_a_422_es_cambio_de_red_alto_en_el_paso_correcto(correr):
    d, _, carpeta = correr(["TC001"])
    c = _caso_de(d, "TC001")
    assert c["resultado"] == "cambios"
    # el GET /api/datasets/123 no cambió: el id es ruido
    (paso,) = c["pasos"]
    assert paso["step_id"] == "p002-1"
    red = [x for x in paso["cambios"] if x["tipo"] == "red"]
    assert red == [
        {
            "tipo": "red",
            "subtipo": "estado",
            "gravedad": "alta",
            "metodo": "POST",
            "ruta": "/api/datasets",
            "antes": 201,
            "despues": 422,
        }
    ]
    assert {x["tipo"] for x in paso["cambios"]} == {"red", "texto", "visual"}
    for lado in ("antes", "despues"):
        assert (carpeta / paso["capturas"][lado]).read_bytes().startswith(b"\x89PNG")


def test_request_nueva_y_request_desaparecida(correr):
    d, *_ = correr(["TC002"])
    pasos = {
        p["step_id"]: [x for x in p["cambios"] if x["tipo"] == "red"]
        for p in _caso_de(d, "TC002")["pasos"]
    }
    (perdida,) = pasos["p001-1"]
    assert (perdida["subtipo"], perdida["ruta"]) == ("request_desaparecida", "/api/a")
    (nueva,) = pasos["p002-1"]
    assert (nueva["subtipo"], nueva["gravedad"], nueva["despues"]) == ("request_nueva", "alta", 404)
    assert nueva["ruta"] == "/api/datasets/«id»/calidad"


def test_dos_grabaciones_iguales_dan_sin_cambios(correr):
    d, *_ = correr(["TC003"])
    assert _caso_de(d, "TC003") == {
        "tc": "TC003",
        "caso_id": "s:TC003",
        "titulo": "Caso TC003",
        "resultado": "sin_cambios",
        "pasos": [],
    }


def test_pasos_que_no_se_alinean(correr):
    d, *_ = correr(["TC004"])
    c = _caso_de(d, "TC004")
    assert c["resultado"] == "no_alineado"
    assert "p001-1" in c["motivo"] and "base" in c["motivo"]


def test_resumen_lista_primero_los_casos_con_cambios(correr):
    d, _, carpeta = correr(["TC003", "TC004", "TC001"])
    resumen = (carpeta / "resumen.md").read_text()
    orden = [resumen.index(f"## {tc}") for tc in ("TC001", "TC004", "TC003")]
    assert orden == sorted(orden)
    assert "1 de 3 casos con cambios" in resumen
    assert "POST /api/datasets: 201 → 422" in resumen
    assert json.loads((carpeta / "diff.json").read_text())["id"] == d["id"]


def test_el_diff_queda_en_la_base_y_se_lee_de_vuelta(correr):
    d, almacen, _ = correr(["TC001", "TC003"])
    assert almacen.diff(d["id"]) == d
    (fila,) = almacen.listar_diffs("predicts")
    assert (fila["id"], fila["total"], fila["con_cambios"]) == (d["id"], 2, 1)
    assert almacen.listar_diffs("otro") == []
    with pytest.raises(KeyError):
        almacen.diff("no-existe")


def test_el_diff_no_guarda_secretos(correr):
    d, *_ = correr(["TC001"])
    assert SECRETO not in json.dumps(d)
