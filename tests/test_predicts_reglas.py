from datetime import datetime

import pytest

from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    DatasetSintetico,
    Ejecucion,
    EventoRed,
    Gravedad,
    Instancia,
    Paso,
    Persona,
)
from dogfood.objetivos.predicts import reglas

AHORA = datetime(2026, 1, 1)
DS = "11111111-aaaa"
AN = "22222222-bbbb"
PT_INGLES = "Esta é a sua lista de clientes do mês. Welcome to the dashboard, your data is ready for review."


def persona(idioma="pt-BR"):
    return Persona(id="p1", nombre="Ana", email="a@x.com", contrasena="x", empresa="E", rubro="r",
                   idioma=idioma, destreza=3, paciencia=3, intencion="explorar", semilla=1)  # fmt: skip


def paso(n, pantalla, accion="ver", texto="", url=None):
    return Paso(n=n, url=url or f"http://x/{pantalla}", pantalla=pantalla, accion=accion,
                texto_visible=texto, ts=AHORA)  # fmt: skip


def ejecucion(pasos=(), red=()):
    return Ejecucion(id="e1", persona_id="p1", escenario_id="s", dataset_id="d", modelo="m",
                     estado="ok", pasos=list(pasos), red=list(red))  # fmt: skip


class Falso:
    def __init__(self, filas=(), mapeo=None):
        self.filas, self._mapeo = list(filas), mapeo or {"columnas": []}

    def resultados(self, analisis_id, tipo):
        return self.filas

    def exportar(self, analisis_id, tipo):
        return b"a,b,c,d,e,f\n"

    def mapeo(self, dataset_id):
        return self._mapeo


def ctx(tmp_path, e, cliente=None, idioma="pt-BR"):
    csv = tmp_path / "ventas.csv"
    csv.write_text(
        "customer_id,order_id,date,sku,ean,product,qty,price\n"
        "C1,P1,2026-01-01,S,E,Jabón,1,1\n"
        + "".join(f"C2,P{i},2026-01-{i + 1:02d},S,E,Jabón,1,1\n" for i in range(3))
    )
    ds = DatasetSintetico(id="d", perfil="p", ruta_csv=csv, ruta_verdad=tmp_path / "v.json",
                          n_clientes=2, n_filas=4, semilla=1)  # fmt: skip
    return ContextoDeteccion(
        corrida=Corrida(id="c", objetivo="predicts", ref="r", commit="x", semilla=1, inicio=AHORA,
                        estado="ok", parametros={"personas": [persona(idioma).model_dump()]}),
        instancia=Instancia(base_url="b", api_url="a", proyecto_compose="p", commit="x",
                            parametros={"MIN_COMPRAS": "3", "CONFIANZA_MAPEO": "0.7"}),
        ejecuciones=[e],
        datasets={"d": ds},
        cliente_api=lambda _p: cliente or Falso(),
        logs={},
    )  # fmt: skip


def fila(cliente="C1", **kw):
    base = {"cliente_id": cliente, "producto_nombre": "Jabón", "fecha_probable": "2026-02-01",
            "fecha_min": "2026-01-30", "fecha_max": "2026-02-03", "n_compras": 2}  # fmt: skip
    return {**base, **kw}


PASOS_RESULTADOS = [paso(1, "resultados", url=f"http://x/analisis/{AN}")]


def test_fecha_para_cliente_de_una_compra_es_alta(tmp_path):
    c = ctx(tmp_path, ejecucion(PASOS_RESULTADOS), Falso([fila("C1"), fila("C2")]))
    hs = [h for h in reglas.verificar(c) if "historia" in h.titulo]
    assert [h.gravedad for h in hs] == [Gravedad.alta]
    assert "C1" in hs[0].descripcion and "C2" not in hs[0].descripcion


def test_fila_sin_fecha_min_es_media(tmp_path):
    c = ctx(tmp_path, ejecucion(PASOS_RESULTADOS), Falso([fila("C2", fecha_min=None)]))
    assert [h.gravedad for h in reglas.verificar(c)] == [Gravedad.media]


def test_filas_completas_no_dan_hallazgos(tmp_path):
    assert reglas.verificar(ctx(tmp_path, ejecucion(PASOS_RESULTADOS), Falso([fila("C2")]))) == []


MAPEO_BAJO = {"columnas": [{"columna": "Cod", "campo": "sku", "confianza": 0.5}],
              "producto_id_tipo": None}  # fmt: skip


def _pasos_mapeo(confirma):
    url = f"http://x/datasets/{DS}/mapeo"
    pasos = [paso(1, "mapeo", url=url)]
    if confirma:
        pasos.append(paso(2, "mapeo", "click Confirmar e iniciar la ingestão", url=url))
    return pasos + [paso(3, "calidad")]


def test_mapeo_bajo_umbral_sin_confirmar_es_alto(tmp_path):
    c = ctx(tmp_path, ejecucion(_pasos_mapeo(False)), Falso(mapeo=MAPEO_BAJO))
    assert [h.gravedad for h in reglas.verificar(c)] == [Gravedad.alta]


def test_mapeo_bajo_umbral_confirmado_no_da_nada(tmp_path):
    c = ctx(tmp_path, ejecucion(_pasos_mapeo(True)), Falso(mapeo=MAPEO_BAJO))
    assert reglas.verificar(c) == []


def test_pantalla_pt_con_parrafo_en_ingles_es_baja(tmp_path):
    e = ejecucion([paso(1, "resultados", texto=PT_INGLES)])
    hs = reglas.verificar(ctx(tmp_path, e))
    assert [h.gravedad for h in hs] == [Gravedad.baja]
    assert "`en`" in hs[0].descripcion and hs[0].pantalla == "resultados"


def test_nombre_de_dataset_no_es_idioma_intruso(tmp_path):
    e = ejecucion([paso(1, "proyectos", texto="Online Retail II\nOnline Retail II")])
    assert reglas.verificar(ctx(tmp_path, e)) == []


def test_peticion_a_mensajeria_es_critica(tmp_path):
    red = [EventoRed(metodo="POST", url="https://api.sendgrid.net/v3/mail/send", estado=200, ms=1)]
    hs = reglas.verificar(ctx(tmp_path, ejecucion(red=red)))
    assert [h.gravedad for h in hs] == [Gravedad.critica]


def test_red_normal_no_da_nada(tmp_path):
    red = [EventoRed(metodo="GET", url="http://localhost:18100/api/yo", estado=200, ms=1)]
    assert reglas.verificar(ctx(tmp_path, ejecucion(red=red))) == []


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        ("Esta é a lista de clientes que você enviou para análise.", "pt"),
        ("Esta es la lista de clientes que usted subió para su análisis.", "es"),
        ("This is the list of customers that you uploaded for your analysis.", "en"),
        ("Online Retail II", None),  # corta: nombre de producto o marca
        ("Nike Air Max 90 Essential", None),
        ("Jabón líquido 500 ml", None),
        ("", None),
    ],
)
def test_idioma_de_frase(frase, esperado):
    assert reglas.idioma_de_frase(frase) == esperado


def test_idiomas_intrusos_ignora_el_idioma_de_la_persona():
    assert reglas.idiomas_intrusos(PT_INGLES, "pt-BR").keys() == {"en"}
    assert reglas.idiomas_intrusos(PT_INGLES, "es").keys() == {"en", "pt"}
    assert reglas.idiomas_intrusos("Online Retail II", "es") == {}


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://api.whatsapp.com/send?phone=1", "api.whatsapp.com"),
        ("https://wa.me/123", "wa.me"),
        ("http://smtp.gmail.com:587/", "smtp.gmail.com"),
        ("https://email.us-east-1.amazonaws.com/", "email.us-east-1.amazonaws.com"),
        ("http://localhost:18100/api/yo", None),
        ("https://notwa.me.example.com/", None),
    ],
)
def test_dominio_de_mensajeria(url, esperado):
    assert reglas.dominio_de_mensajeria(url) == esperado


def test_huella_no_depende_de_los_numeros(tmp_path):
    a = reglas.verificar(ctx(tmp_path, ejecucion(PASOS_RESULTADOS), Falso([fila("C1")])))
    b = reglas.verificar(
        ctx(tmp_path, ejecucion(PASOS_RESULTADOS), Falso([fila("C1", n_compras=9)]))
    )
    assert a[0].huella == b[0].huella != ""


def test_sin_personas_no_evalua_reglas_de_persona(tmp_path):
    c = ctx(tmp_path, ejecucion([paso(1, "resultados", texto=PT_INGLES)]))
    c.corrida.parametros = {}
    assert reglas.verificar(c) == []
