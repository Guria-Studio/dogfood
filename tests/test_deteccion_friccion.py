import logging
from datetime import datetime
from types import SimpleNamespace

from dogfood.deteccion import friccion, objetivo
from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    Ejecucion,
    Friccion,
    Gravedad,
    Instancia,
    Paso,
)

AHORA = datetime(2026, 1, 1)


def fr(texto, pantalla="mapeo"):
    return Friccion(texto=texto, severidad=Gravedad.baja, pantalla=pantalla)


def ej(i, fricciones=(), estado="ok", pasos=(), motivo=""):
    return Ejecucion(id=f"e{i}", persona_id=f"p{i}", escenario_id="s", modelo="m", estado=estado,
                     fricciones=list(fricciones), pasos=list(pasos), motivo_juez=motivo)  # fmt: skip


def ctx(ejecuciones, obj=None):
    c = ContextoDeteccion(
        corrida=Corrida(
            id="c", objetivo="predicts", ref="r", commit="x", semilla=1, inicio=AHORA, estado="ok"
        ),
        instancia=Instancia(base_url="b", api_url="a", proyecto_compose="p", commit="x"),
        ejecuciones=ejecuciones,
        datasets={},
        cliente_api=lambda _p: None,
        logs={},
    )
    c.objetivo = obj  # type: ignore[attr-defined]
    return c


def test_cinco_personas_gravedad_media():
    hs = friccion.detectar(ctx([ej(i, [fr("No sé qué columna es el SKU")]) for i in range(5)]))
    assert len(hs) == 1
    assert hs[0].gravedad == Gravedad.media and not hs[0].solo_reporte and hs[0].ocurrencias == 5


def test_dos_personas_baja_publicable():
    hs = friccion.detectar(ctx([ej(i, [fr("no encuentro el botón")]) for i in range(2)]))
    assert hs[0].gravedad == Gravedad.baja and not hs[0].solo_reporte


def test_una_persona_solo_reporte():
    hs = friccion.detectar(ctx([ej(1, [fr("no encuentro el botón")])]))
    assert len(hs) == 1 and hs[0].solo_reporte


def test_textos_parecidos_se_agrupan_y_pantallas_distintas_no():
    hs = friccion.detectar(
        ctx(
            [
                ej(1, [fr("no entiendo qué es SKU")]),
                ej(2, [fr("qué significa sku??")]),
                ej(3, [fr("qué significa sku??", "otra")]),
            ]
        )
    )
    assert sorted(h.ocurrencias for h in hs) == [1, 2]


def test_rendido_sin_friccion_genera_sintetica():
    p = Paso(n=1, url="u", pantalla="subida", accion="click", ts=AHORA)
    hs = friccion.detectar(
        ctx([ej(1, estado="rendido", pasos=[p], motivo="no pude subir el archivo")])
    )
    assert len(hs) == 1 and hs[0].pantalla == "subida" and "no pude subir" in hs[0].descripcion


def test_objetivo_llama_a_todos_los_verificadores(caplog):
    llamados = []

    def bueno(c):
        llamados.append("bueno")
        return [friccion.detectar(ctx([ej(1, [fr("x")])]))[0]]

    def roto(c):
        raise ValueError("boom")

    obj = SimpleNamespace(verificadores=lambda: [roto, bueno, bueno])
    with caplog.at_level(logging.ERROR):
        hs = objetivo.detectar(ctx([], obj))
    assert llamados == ["bueno", "bueno"] and len(hs) == 3  # + el hallazgo de `roto` (F10.1.T3)
    assert "roto" in caplog.text
