import json
from datetime import datetime
from pathlib import Path

from dogfood.deteccion.tecnicos import detectar
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    Ejecucion,
    EventoConsola,
    EventoRed,
    Gravedad,
    Instancia,
)
from dogfood.objetivos.predicts import PredictsObjetivo

FIX = Path(__file__).parent / "fixtures" / "corrida-10-red"
T0 = datetime(2026, 11, 1, 12, 52)
API = "http://localhost:18080/api"


def _ctx(ejs):
    corrida = Corrida(
        id="c", objetivo="predicts", ref="r", commit="abc", semilla=1, inicio=T0, estado="ok"
    )
    inst = Instancia(base_url=API, api_url=API, proyecto_compose="p", commit="abc")
    ctx = ContextoDeteccion(corrida, inst, ejs, {}, lambda p: None, {})
    ctx.objetivo = PredictsObjetivo()
    return ctx


def _ej(id_="e", escenario="s", red=(), consola=()):
    return Ejecucion(
        id=id_, persona_id="p", escenario_id=escenario, modelo="m", estado="ok",
        red=list(red), consola=list(consola),
    )  # fmt: skip


def _corrida_10():
    login = {e.id for e in PredictsObjetivo().escenarios() if e.carril == "login_fallido"}
    ejs = []
    for d in sorted(FIX.iterdir()):
        red = [json.loads(x) for x in (d / "red.jsonl").read_text().splitlines()]
        con = [json.loads(x) for x in (d / "consola.jsonl").read_text().splitlines()]
        # E3 y E8 son las ejecuciones del carril login_fallido (los 429 solo salen ahí)
        esc = next(iter(login)) if d.name in ("E3", "E8") else "s"
        ejs.append(
            _ej(d.name, esc, [EventoRed(**x) for x in red], [EventoConsola(**x) for x in con])
        )
    return ejs


def test_corrida_10_solo_queda_el_404_de_calidad():
    hs = detectar(_ctx(_corrida_10()))
    assert len(hs) == 1
    [h] = hs
    assert "/api/datasets/{id}/calidad" in h.titulo and "404" in h.titulo
    assert h.gravedad == Gravedad.media
    assert h.ocurrencias == 5  # E2 (x2), E4, E5, E6


def test_hipotesis_de_carrera_tras_la_subida():
    subida = EventoRed(metodo="POST", url=f"{API}/proyectos/1/datasets", estado=201, ms=5)
    cal = EventoRed(
        metodo="GET",
        url=f"{API}/datasets/01a197d3-31ad-7230-a2b4-f034628e3baa/calidad",
        estado=404,
        ms=5,
    )
    [h] = detectar(_ctx([_ej(red=[subida, cal])]))
    assert "carrera entre la subida y el cálculo de calidad" in h.descripcion
    [h] = detectar(_ctx([_ej(red=[cal])]))
    assert "carrera" not in h.descripcion


def test_500_sigue_alta():
    ev = EventoRed(metodo="GET", url=f"{API}/proyectos/1/datasets", estado=500, ms=5)
    [h] = detectar(_ctx([_ej(red=[ev])]))
    assert h.gravedad == Gravedad.alta


def test_failed_to_load_resource_con_su_red_es_un_hallazgo():
    url = f"{API}/proyectos/1/datasets"
    ev = EventoRed(metodo="GET", url=url, estado=500, ms=5)
    con = EventoConsola(
        nivel="error", url=url,
        texto="Failed to load resource: the server responded with a status of 500 (Internal Server Error)",
    )  # fmt: skip
    hs = detectar(_ctx([_ej(red=[ev], consola=[con])]))
    assert len(hs) == 1 and hs[0].gravedad == Gravedad.alta
