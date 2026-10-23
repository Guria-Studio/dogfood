from pathlib import Path

import pytest

from dogfood import escenarios as m
from dogfood.dominio import Persona

CARPETA = Path(m.__file__).parent / "objetivos" / "predicts" / "escenarios"


def persona(i: int, **c) -> Persona:
    base = {
        "id": f"p{i}", "nombre": "N", "email": f"p{i}@x.com", "contrasena": "x", "empresa": "E", "rubro": "farmacia",
        "idioma": "es", "destreza": 5, "paciencia": 3, "intencion": "analisis_completo", "semilla": i,
    }  # fmt: skip
    return Persona(**{**base, **c})


def test_todos_los_yaml_de_predicts_cargan() -> None:
    assert len(m.cargar(CARPETA)) == 10


def test_sin_criterio_exito_nombra_el_archivo(tmp_path: Path) -> None:
    (tmp_path / "roto.yaml").write_text("id: a\ntitulo: A\nobjetivo: algo\n")
    with pytest.raises(ValueError, match=r"roto\.yaml.*criterio_exito"):
        m.cargar(tmp_path)


def test_asignar_es_determinista() -> None:
    escs, pers = m.cargar(CARPETA), [persona(i) for i in range(10)]
    ids = lambda r: [(p.id, e.id) for p, e in r]
    assert ids(m.asignar(pers, escs, 7)) == ids(m.asignar(pers, escs, 7))


def test_diez_personas_cubren_diez_escenarios() -> None:
    escs = m.cargar(CARPETA)
    # intención/destreza que encajan con todo no existe en el YAML real: se relajan
    for e in escs:
        e.persona_compatible.intencion, e.persona_compatible.destreza_min = [], 1
    r = m.asignar([persona(i) for i in range(10)], escs, 1)
    assert {e.id for _, e in r} == {e.id for e in escs}


def test_login_fallido_tiene_su_carril() -> None:
    e = {e.id: e for e in m.cargar(CARPETA)}["login-fallido"]
    assert e.carril == "login_fallido"
