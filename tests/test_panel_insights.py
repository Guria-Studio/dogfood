from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from dogfood.almacen import Almacen
from dogfood.dominio import Corrida, Ejecucion, Hallazgo, Paso, Persona
from dogfood.panel.app import crear_app_panel
from dogfood.plan import CasoPrueba, PlanPruebas

PERSONA = Persona(
    id="p1", nombre="Ana", email="a@x.com", contrasena="pw", empresa="E", rubro="r", idioma="es",
    destreza=2, paciencia=3, intencion="explorar", semilla=1,
)  # fmt: skip


def _corrida(a, tmp, cid, dia, ref, commit, resultados, hallazgos):
    """resultados: {escenario: aprobado|fallo}; hallazgos: [(escenario, huella, titulo)]."""
    a.nueva_corrida(
        Corrida(id=cid, objetivo="predicts", ref=ref, commit=commit, semilla=1,
                inicio=datetime(2026, 1, dia), estado="completa", parametros={"proyecto": "predicts"})
    )  # fmt: skip
    a.guardar_personas(cid, [PERSONA])
    casos = []
    for esc, res in resultados.items():
        eid = f"{cid}-{esc}"
        a.guardar_ejecucion(
            cid,
            Ejecucion(id=eid, persona_id="p1", escenario_id=esc, modelo="m", estado="ok",
                      resultado=res, exito=res == "aprobado", motivo_juez="", duracion_s=1,
                      pasos=[Paso(n=1, url="http://a/", pantalla="/", accion="x", ts=datetime(2026, 1, dia))]),
        )  # fmt: skip
        casos.append(
            CasoPrueba(id=f"{esc}:p1", titulo=f"Caso {esc}", escenario_id=esc, persona_id="p1",
                       persona_nombre="Ana", objetivo="o", criterio_exito="c", prioridad="alta",
                       superficies=[], ejecuciones=[eid])
        )  # fmt: skip
    (tmp / cid / "plan.json").write_text(
        PlanPruebas(objetivo="predicts", semilla=1, casos=casos).model_dump_json()
    )
    a.guardar_hallazgos(
        cid,
        [
            Hallazgo(tipo="logica", gravedad="alta", pantalla=f"/{esc}", titulo=t, descripcion=f"causa {t}",
                     ejecucion_id=f"{cid}-{esc}", semilla=1, commit=commit, huella=h)
            for esc, h, t in hallazgos
        ],
    )  # fmt: skip


@pytest.fixture
def cliente(tmp_path):
    a = Almacen(tmp_path)
    # c1: a pasa, b y c fallan (huellas HB y HC). c2: a falla (regresión), b sigue, c pasa (HC desaparece)
    _corrida(a, tmp_path, "c1", 1, "main", "aaa1111", {"a": "aprobado", "b": "fallo", "c": "fallo"},
             [("b", "HB", "Tabla vacía"), ("c", "HC", "Botón muerto")])  # fmt: skip
    _corrida(a, tmp_path, "c2", 2, "main", "bbb2222", {"a": "fallo", "b": "fallo", "c": "aprobado"},
             [("b", "HB", "Tabla vacía"), ("a", "HA", "Sesión caduca")])  # fmt: skip
    return TestClient(crear_app_panel(tmp_path))


def test_regresion_y_arreglado(cliente):
    r = cliente.get("/api/proyectos/predicts/insights").json()
    assert r["corrida_id"] == "c2" and (r["pasaron"], r["total"]) == (1, 3)
    assert r["regresiones"] == [{"tc": "TC001", "nombre": "Caso a", "ref": "main@bbb2222"}]
    assert r["abiertos"] == 2 and r["arreglados"] == 1  # HC ya no aparece
    assert [p["total"] for p in r["tendencia"]] == [3, 3]


def test_issues_por_huella_y_prompt(cliente):
    r = cliente.get("/api/proyectos/predicts/insights").json()
    assert {i["huella"]: i["casos"] for i in r["issues"]} == {"HB": ["TC002"], "HA": ["TC001"]}
    assert r["casos_fallaron"] == 2
    for causa in ("Tabla vacía", "Sesión caduca"):
        assert causa in r["prompt"]
    assert "dogfood replay c2-a" in r["prompt"] and "dogfood replay c2-b" in r["prompt"]
    assert {c["caso_de_uso"]: c["estado"] for c in r["cobertura"]} == {
        "a": "brecha", "b": "brecha", "c": "cubierto",
    }  # fmt: skip


def test_una_sola_corrida(tmp_path):
    a = Almacen(tmp_path)
    _corrida(a, tmp_path, "c1", 1, "main", "aaa1111", {"a": "fallo"}, [("a", "HA", "Roto")])
    r = TestClient(crear_app_panel(tmp_path)).get("/api/proyectos/predicts/insights").json()
    assert len(r["tendencia"]) == 1 and r["arreglados"] == 0 and r["regresiones"] == []


def test_proyecto_inexistente(cliente):
    assert cliente.get("/api/proyectos/nada/insights").status_code == 404
