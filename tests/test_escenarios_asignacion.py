import json
from pathlib import Path

from dogfood import escenarios as m
from dogfood.dominio import Escenario, Persona

CARPETA = Path(m.__file__).parent / "objetivos" / "predicts" / "escenarios"
FIX = Path(__file__).parent / "fixtures" / "personas-corrida-10.json"


def esc(i: str, intenciones: list[str], dmin: int = 1) -> Escenario:
    return Escenario(
        id=i, titulo=i, objetivo="x", criterio_exito="x",
        persona_compatible={"intencion": intenciones, "destreza_min": dmin},
    )  # fmt: skip


def pers(i: str, intencion: str, destreza: int = 3) -> Persona:
    return Persona(
        id=i, nombre="N", email=f"{i}@x.com", contrasena="x", empresa="E", rubro="farmacia",
        idioma="es", destreza=destreza, paciencia=3, intencion=intencion, semilla=1,
    )  # fmt: skip


def test_corrida_de_10_personas() -> None:
    personas = [Persona(**d) for d in json.loads(FIX.read_text("utf-8"))]
    escs = m.cargar(CARPETA)
    for semilla in range(20):
        r = m.asignar(personas, escs, semilla)
        assert len(r) == 10
        assert {e.id for _, e in r} == {e.id for e in escs}
        assert not r.avisos
        assert {"P004", "P008"} <= set(r.notas)  # solo_exportar: ningún escenario


def test_caso_adverso_del_greedy() -> None:
    # el greedy viejo daba A a la primera libre (p1) y B quedaba sin cubrir
    escs = [esc("a", ["explorar", "romper"]), esc("b", ["explorar"])]
    r = m.asignar([pers("p1", "explorar"), pers("p2", "romper")], escs, 0)
    assert {e.id for _, e in r} == {"a", "b"}
    assert not r.avisos


def test_escenario_sin_compatibles_avisa() -> None:
    r = m.asignar([pers("p1", "explorar")], [esc("a", ["explorar"]), esc("z", ["romper"])], 0)
    assert r.avisos == ["escenario z sin personas compatibles"]
    assert len(r) == 1


def test_misma_semilla_misma_asignacion() -> None:
    personas = [Persona(**d) for d in json.loads(FIX.read_text("utf-8"))]
    escs = m.cargar(CARPETA)
    ids = lambda r: [(p.id, e.id) for p, e in r]
    assert ids(m.asignar(personas, escs, 5)) == ids(m.asignar(personas, escs, 5))
