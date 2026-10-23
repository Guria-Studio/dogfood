from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

from dogfood.deteccion.tecnicos import detectar
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    Ejecucion,
    EventoConsola,
    EventoRed,
    Gravedad,
    Instancia,
    Paso,
)

FIX = Path(__file__).parent / "fixtures" / "logs"
T0 = datetime(2026, 10, 23, 18, 0, 0)


def _paso(n, url="http://x/app", captura=None, accion="clic"):
    return Paso(
        n=n, url=url, pantalla="inicio", accion=accion, captura=captura,
        ts=T0 + timedelta(seconds=10 * n),
    )  # fmt: skip


def _ej(**kw):
    base = {"id": "e1", "persona_id": "p1", "escenario_id": "s", "modelo": "m"}
    base |= {"estado": "ok", "pasos": [_paso(1)]}
    return Ejecucion(**{**base, **kw})


def _ctx(ejs, logs=None):
    corrida = Corrida(
        id="c", objetivo="predicts", ref="r", commit="abc", semilla=1, inicio=T0, estado="ok"
    )
    inst = Instancia(
        base_url="http://x", api_url="http://x/api", proyecto_compose="p", commit="abc"
    )
    return ContextoDeteccion(corrida, inst, ejs, {}, lambda p: None, logs or {})


def _red(estado, url="http://x/api/proyectos/12/datasets", metodo="GET"):
    return EventoRed(metodo=metodo, url=url, estado=estado, ms=5)


def test_500_alto_con_ruta_normalizada():
    [h] = detectar(_ctx([_ej(red=[_red(500)])]))
    assert h.gravedad == Gravedad.alta
    assert "/api/proyectos/{id}/datasets" in h.titulo


def test_dos_500_distinto_id_una_huella():
    red = [
        _red(500, "http://x/api/proyectos/1/datasets"),
        _red(500, "http://x/api/proyectos/2/datasets"),
    ]
    [h] = detectar(_ctx([_ej(red=red)]))
    assert h.ocurrencias == 2
    assert len(h.evidencia) == 2


def test_429_esperado_no_genera_nada():
    e = _ej(red=[_red(429)], notas=["esperado: 429 en /api/proyectos/12/datasets"])
    assert detectar(_ctx([e])) == []
    assert detectar(_ctx([_ej(red=[_red(429)])]))[0].gravedad == Gravedad.media


def test_4xx_tolerados():
    red = [_red(401), _red(404), _red(422, metodo="POST")]
    assert detectar(_ctx([_ej(red=red)])) == []


def test_traceback_worker():
    logs = {"worker": (FIX / "worker.log").read_text()}
    hs = detectar(_ctx([_ej(pasos=[_paso(1), _paso(2), _paso(10)])], logs))
    [h] = hs
    assert "ZeroDivisionError" in h.titulo
    assert "recompra.py" in h.descripcion + h.titulo + h.huella or "modelo/recompra.py" in h.titulo
    assert h.gravedad == Gravedad.alta
    assert h.ejecucion_id == "e1"


def test_captura_blanca(tmp_path):
    png = tmp_path / "b.png"
    Image.new("RGB", (100, 80), "white").save(png)
    e = _ej(pasos=[_paso(1, captura=png, accion="navegó a /analisis")])
    [h] = detectar(_ctx([e]))
    assert h.titulo == "Pantalla en blanco"
    assert h.gravedad == Gravedad.alta


def test_console_error_al_final_es_alto():
    ev = EventoConsola(nivel="error", texto="TypeError 42 en http://x/a.js", url="http://x/app")
    [h] = detectar(_ctx([_ej(consola=[ev], estado="fallo")]))
    assert h.gravedad == Gravedad.alta
    [h] = detectar(_ctx([_ej(consola=[ev], exito=True)]))
    assert h.gravedad == Gravedad.media
