import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from dogfood.almacen import Almacen
from dogfood.dominio import Corrida, Ejecucion, Evidencia, Hallazgo, Paso, Persona
from dogfood.panel.app import crear_app_panel
from dogfood.plan import CasoPrueba, PlanPruebas
from dogfood.reporte import sugerencia

SECRETO = "sk-plantado1234567890abcdef"
CONTRASENA = "hunter2-pw"


def _persona(pid, nombre):
    return Persona(
        id=pid, nombre=nombre, email=f"{pid}@dogfood.example.com", contrasena=CONTRASENA,
        empresa="E", rubro="r", idioma="es", destreza=2, paciencia=3, intencion="explorar",
        semilla=1,
    )  # fmt: skip


def _caso(esc, pid, nombre, prioridad, ejecuciones):
    return CasoPrueba(
        id=f"{esc}:{pid}", titulo=f"{nombre} hace {esc}", escenario_id=esc, persona_id=pid,
        persona_nombre=nombre, objetivo=f"Lograr {esc}", criterio_exito="ve el resultado",
        prioridad=prioridad, superficies=[], ejecuciones=ejecuciones,
    )  # fmt: skip


def _ej(a, eid, pid, esc, res, motivo=""):
    a.guardar_ejecucion(
        "c1",
        Ejecucion(
            id=eid, persona_id=pid, escenario_id=esc, modelo="m", estado="ok", resultado=res,
            exito=res == "aprobado", motivo_juez=motivo, duracion_s=3,
            pasos=[Paso(n=1, url="http://app/", pantalla="/subir", accion="clic",
                        ts=datetime(2026, 1, 1))],
        ),
    )  # fmt: skip


@pytest.fixture
def cliente(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(
        Corrida(id="c1", objetivo="predicts", ref="main", commit="abc", semilla=1,
                inicio=datetime(2026, 1, 1), estado="completa", parametros={"proyecto": "predicts"})
    )  # fmt: skip
    a.guardar_personas("c1", [_persona("p1", "Ana Pérez"), _persona("p2", "Beto")])
    _ej(a, "c1-E1", "p1", "subir", "aprobado")
    _ej(a, "c1-E2", "p2", "subir", "fallo", f"No apareció la tabla.\nToken {SECRETO}")
    _ej(a, "c1-E3", "p1", "exportar", "fallo", "")
    plan = PlanPruebas(
        objetivo="predicts",
        semilla=1,
        casos=[
            _caso("subir", "p1", "Ana Pérez", "alta", ["c1-E1"]),
            _caso("subir", "p2", "Beto", "alta", ["c1-E2"]),
            _caso("exportar", "p1", "Ana Pérez", "media", ["c1-E3"]),
            _caso("login", "p2", "Beto", "media", ["c1-E4"]),  # nunca empezó
        ],
    )
    (tmp_path / "c1" / "plan.json").write_text(plan.model_dump_json())
    hallazgo = Hallazgo(
        tipo="logica", gravedad="alta", pantalla="/subir", titulo="La tabla no carga",
        descripcion="El endpoint devolvió 500", ejecucion_id="c1-E2", semilla=1, commit="abc",
        esperado="12 filas", obtenido="0 filas",
        evidencia=[Evidencia(tipo="log", extracto=f"Authorization: Bearer x\nkey={SECRETO} pw={CONTRASENA}")],
    )  # fmt: skip
    a.guardar_hallazgos("c1", [hallazgo])
    sugerencia.guardar(
        tmp_path / "c1",
        {
            "c1-H1": sugerencia.Sugerencia(
                causa="El parser no acepta comas", cambio="Normalizar el separador",
                archivos=[sugerencia.ArchivoProbable(ruta="api/subir.py", linea=42)],
            )
        },
    )  # fmt: skip
    return TestClient(crear_app_panel(tmp_path))


def _casos(r):
    return [c for g in r["grupos"] for c in g["casos"]]


def test_conteos_coinciden_con_los_casos(cliente):
    r = cliente.get("/api/proyectos/predicts/casos").json()
    casos = _casos(r)
    assert [c["tc"] for c in casos] == ["TC001", "TC002", "TC003", "TC004"]
    assert r["total"] == len(casos) == sum(r["conteos"].values())
    for estado, n in r["conteos"].items():
        assert n == sum(c["estado"] == estado for c in casos)
    assert r["conteos"]["fallo"] == 2
    assert [g["caso_de_uso"] for g in r["grupos"]] == ["subir", "exportar", "login"]
    ana = casos[0]
    assert ana["persona"] == {"id": "p1", "nombre": "Ana Pérez", "idioma": "es", "destreza": 2,
                              "iniciales": "AP"}  # fmt: skip
    assert ana["ejecucion_id"] == "c1-E1" and ana["fecha"] and ana["falla"] == ""
    assert casos[3]["estado"] == "planeado" and casos[3]["ejecucion_id"] is None


def test_filtros(cliente):
    r = cliente.get("/api/proyectos/predicts/casos?estado=fallo").json()
    casos = _casos(r)
    assert {c["tc"] for c in casos} == {"TC002", "TC003"}
    assert all(c["estado"] == "fallo" for c in casos)
    assert r["conteos"]["paso"] == 1  # las pestañas siguen contando todo
    # una línea, del motivo del juez o, si no hay, del hallazgo principal; redactada
    assert casos[0]["falla"] == "No apareció la tabla."
    assert casos[1]["falla"] == ""  # sin motivo ni hallazgo
    assert [
        c["tc"] for c in _casos(cliente.get("/api/proyectos/predicts/casos?q=beto").json())
    ] == [
        "TC002",
        "TC004",
    ]
    r = cliente.get("/api/proyectos/predicts/casos?prioridad=media").json()
    assert {c["tc"] for c in _casos(r)} == {"TC003", "TC004"}
    assert cliente.get("/api/proyectos/nada/casos").status_code == 404


def test_detalle_del_caso_fallido(cliente):
    d = cliente.get("/api/proyectos/predicts/casos/TC002").json()
    assert d["objetivo"] == "Lograr subir" and d["criterio_exito"] == "ve el resultado"
    assert [p["pantalla"] for p in d["pasos"]] == ["/subir"]
    assert d["historial"][0]["ejecucion_id"] == "c1-E2"
    assert d["verificaciones"] == [
        {
            "titulo": "La tabla no carga",
            "pantalla": "/subir",
            "esperado": "12 filas",
            "obtenido": "0 filas",
        }
    ]
    assert "Viewport" in d["ajustes"] and d["codigo"] is None
    f = d["falla_detalle"]
    assert f["sugerencia"]["causa"] == "El parser no acepta comas"
    assert "dogfood replay c1-E2" in f["prompt"]
    assert "api/subir.py:42" in f["prompt"]
    assert "El endpoint devolvió 500" in f["prompt"]
    # el secreto plantado en la evidencia y el motivo no llega al prompt ni a la respuesta
    assert SECRETO not in json.dumps(d) and CONTRASENA not in json.dumps(d)
    assert "«redactado»" in f["prompt"]
    assert cliente.get("/api/proyectos/predicts/casos/TC001").json()["falla_detalle"] is None
    assert cliente.get("/api/proyectos/predicts/casos/TC999").status_code == 404
    assert cliente.get("/api/proyectos/predicts/casos/TC004").json()["pasos"] == []
