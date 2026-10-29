from datetime import datetime

from dogfood.almacen import VERSION_ESQUEMA, Almacen
from dogfood.dominio import Corrida, Ejecucion, Gravedad, Hallazgo, TipoHallazgo, UsoLlm


def _corrida(id="c1"):
    return Corrida(
        id=id,
        objetivo="predicts",
        ref="main",
        commit="abc",
        semilla=1,
        inicio=datetime(2026, 1, 1),
        estado="en_curso",
    )


def _ej(id):
    return Ejecucion(id=id, persona_id="p1", escenario_id="e1", modelo="m", estado="ok")


def _h(titulo, ej="x1"):
    return Hallazgo(
        tipo=TipoHallazgo.tecnico,
        gravedad=Gravedad.alta,
        pantalla="mapeo",
        titulo=titulo,
        descripcion="d",
        semilla=1,
        commit="abc",
        ejecucion_id=ej,
    )


def test_nueva_corrida_crea_carpeta_y_fila(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(_corrida())
    for sub in ("datos", "ejecuciones", "logs"):
        assert (tmp_path / "c1" / sub).is_dir()
    assert (tmp_path / "c1" / "corrida.json").exists()
    assert [r.id for r in a.listar_corridas()] == ["c1"]


def test_ejecuciones_y_hallazgos(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(_corrida())
    a.guardar_ejecucion("c1", _ej("x1"))
    a.guardar_ejecucion("c1", _ej("x2"))
    ids = a.guardar_hallazgos("c1", [_h("a"), _h("b"), _h("c")])
    assert a.listar_corridas()[0].n_hallazgos == 3
    assert a.hallazgo(ids[1]).titulo == "b"
    assert a.ejecucion("x2").id == "x2"


def test_registrar_uso_suma_costo(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(_corrida())
    for c in (0.25, 0.5):
        a.registrar_uso(
            UsoLlm(rol="agente", modelo="m", tokens_in=1, tokens_out=1, costo_usd=c), "c1"
        )
    assert a.listar_corridas()[0].costo_usd == 0.75
    a.cerrar_corrida("c1", "ok", 0.75)
    assert a.listar_corridas()[0].estado == "ok"


def test_reabrir_conserva_datos_y_version(tmp_path):
    a = Almacen(tmp_path)
    a.nueva_corrida(_corrida())
    b = Almacen(tmp_path)
    assert [r.id for r in b.listar_corridas()] == ["c1"]
    import sqlite3

    assert (
        sqlite3.connect(tmp_path / "dogfood.db").execute("PRAGMA user_version").fetchone()[0]
        == VERSION_ESQUEMA
    )
