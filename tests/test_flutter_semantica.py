from datetime import datetime
from pathlib import Path

from dogfood.deteccion.flutter import detectar
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    Ejecucion,
    Gravedad,
    Instancia,
    Paso,
    TipoHallazgo,
)
from dogfood.drivers.base import ElementoUI
from dogfood.flutter.semantica import cobertura_elementos, cobertura_xml, es_flutter

F = Path(__file__).parent / "fixtures" / "flutter"
AHORA = datetime(2026, 1, 1)


def leer(n):
    return (F / n).read_text()


def test_es_flutter():
    assert es_flutter(leer("login_etiquetado.xml"))
    assert es_flutter(leer("login_ciego.xml"))
    assert not es_flutter(leer("nativo.xml"))
    assert es_flutter("", "br.com.x/io.flutter.embedding.android.FlutterActivity")


def test_cobertura_etiquetado_y_ciego():
    c = cobertura_xml(leer("login_etiquetado.xml"))
    assert c.flutter and not c.ciega
    assert (c.interactivos, c.etiquetados) == (4, 4)
    assert c.con_id >= 1
    ciega = cobertura_xml(leer("login_ciego.xml"))
    assert ciega.ciega and ciega.nodos == 0


def test_nativo_nunca_ciego():
    c = cobertura_xml(leer("nativo.xml"))
    assert not c.flutter and not c.ciega
    assert c.interactivos == 2 and c.etiquetados == 0


def test_xcuitest():
    c = cobertura_xml(leer("xcuitest_login.xml"), actividad="io.flutter")
    assert c.interactivos == 4 and c.etiquetados == 4
    assert c.con_id == 2 and not c.ciega


def test_cobertura_elementos_ids_e12():
    els = [ElementoUI(id="e12", texto="Entrar", bounds=(0, 0, 1, 1), clicable=True)]
    c = cobertura_elementos(els, flutter=True)
    assert c.interactivos == 1 and c.etiquetados == 1 and c.con_id == 0


def _ctx(tmp_path, xmls, driver="android"):
    ejecs = []
    for i, xml in enumerate(xmls):
        arbol = tmp_path / f"a{i}.xml"
        arbol.write_text(xml)
        paso = Paso(
            n=1,
            url="Login",
            pantalla="Login",
            accion="x",
            ts=AHORA,
            captura=tmp_path / f"c{i}.png",
            arbol=arbol,
        )
        ejecs.append(
            Ejecucion(
                id=f"e{i}",
                persona_id="p",
                escenario_id="s",
                modelo="m",
                estado="ok",
                pasos=[paso, paso],
                driver=driver,
            )
        )
    return ContextoDeteccion(
        corrida=Corrida(
            id="c", objetivo="o", ref="r", commit="x", semilla=1, inicio=AHORA, estado="ok"
        ),
        instancia=Instancia(base_url="b", api_url="a", proyecto_compose="p", commit="x"),
        ejecuciones=ejecs,
        datasets={},
        cliente_api=lambda _p: None,
        logs={},
    )


def test_detector_ciega_una_vez(tmp_path):
    hs = detectar(_ctx(tmp_path, [leer("login_ciego.xml")] * 2))
    assert len(hs) == 1
    h = hs[0]
    assert h.tipo == TipoHallazgo.accesibilidad and h.gravedad == Gravedad.media
    assert h.titulo == "pantalla sin Semantics: Login"
    assert any(e.tipo == "captura" for e in h.evidencia)
    assert "0 interactivos" in h.descripcion


def test_detector_sin_ids(tmp_path):
    xml = leer("login_etiquetado.xml").replace("campo_email", "").replace("btn_entrar", "")
    hs = detectar(_ctx(tmp_path, [xml]))
    assert len(hs) == 1 and hs[0].gravedad == Gravedad.baja


def test_detector_etiquetado_con_ids_y_web(tmp_path):
    assert detectar(_ctx(tmp_path, [leer("login_etiquetado.xml")])) == []
    assert detectar(_ctx(tmp_path, [leer("login_ciego.xml")], driver="web")) == []
