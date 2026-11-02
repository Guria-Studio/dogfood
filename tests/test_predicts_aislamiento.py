from datetime import datetime

import httpx
import respx

from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    Ejecucion,
    Gravedad,
    Instancia,
    TipoHallazgo,
)
from dogfood.objetivos.predicts import aislamiento
from dogfood.objetivos.predicts.cliente import PredictsCliente

API = "http://api"

OPENAPI = {
    "paths": {
        "/api/proyectos": {"get": {}, "post": {}},  # sin parámetro: se ignora
        "/api/proyectos/{proyecto_id}": {"get": {}, "patch": {}, "delete": {}},
        "/api/datasets/{dataset_id}": {"get": {}},
        "/api/plantillas/{plantilla_id}": {"get": {}},
        "/api/analisis/{id}/exportar": {"get": {}},
        "/api/trabajos/{id}/eventos": {"get": {}},
    }
}


def _ctx(empresas: list[str]) -> ContextoDeteccion:
    """ctx con una ejecución por empresa; cada persona_id mapea a su propio cliente."""
    clientes = {f"persona-{e}": PredictsCliente(API) for e in empresas}
    ejecuciones = [
        Ejecucion(
            id=f"eje-{e}",
            persona_id=f"persona-{e}",
            escenario_id="s",
            modelo="m",
            estado="ok",
            dataset_id="ds-A",
            empresa_id=e,
        )
        for e in empresas
    ]
    return ContextoDeteccion(
        corrida=Corrida(
            id="r",
            objetivo="predicts",
            ref="main",
            commit="c",
            semilla=7,
            inicio=datetime.now(),
            estado="x",
        ),
        instancia=Instancia(base_url="http://w", api_url=API, proyecto_compose="p", commit="c"),
        ejecuciones=ejecuciones,
        datasets={},
        cliente_api=lambda pid: clientes[pid],
        logs={},
    )


def _inventario_de_a(m: respx.Router) -> None:
    """Listas con las que A entrega sus ids al juntar el inventario (paso 1) y OpenAPI."""
    m.get(f"{API}/openapi.json").respond(200, json=OPENAPI)
    m.get(f"{API}/api/proyectos").respond(200, json=[{"id": "proj-A"}])
    m.get(f"{API}/api/proyectos/proj-A/datasets").respond(200, json=[{"id": "ds-A"}])
    m.get(f"{API}/api/datasets/ds-A/analisis").respond(200, json=[{"id": "an-A"}])
    m.get(f"{API}/api/plantillas").respond(200, json=[{"id": "tpl-A"}])
    m.get(f"{API}/api/trabajos").respond(200, json=[{"id": "job-A"}])
    m.post(f"{API}/api/proyectos").respond(201, json={"id": "proj-audit"})


def _probes_404(m: respx.Router, rutas: list[str]) -> None:
    for ruta in rutas:
        m.route(url=f"{API}{ruta}").respond(404)


def test_todas_404_no_dan_hallazgos():
    with respx.mock(assert_all_called=False) as m:
        _inventario_de_a(m)
        _probes_404(
            m,
            [
                "/api/proyectos/proj-A",
                "/api/datasets/ds-A",
                "/api/plantillas/tpl-A",
                "/api/analisis/an-A/exportar",
                "/api/trabajos/job-A/eventos",
                "/api/proyectos/proj-audit",
            ],
        )
        assert aislamiento.verificar(_ctx(["A", "B"])) == []


def test_200_con_datos_da_hallazgo_critico_con_ruta_normalizada():
    with respx.mock(assert_all_called=False) as m:
        _inventario_de_a(m)
        # B logra leer el proyecto de A: fuga.
        m.get(f"{API}/api/proyectos/proj-A").respond(
            200, json={"id": "proj-A", "nombre": "secreto"}
        )
        _probes_404(
            m,
            [
                "/api/datasets/ds-A",
                "/api/plantillas/tpl-A",
                "/api/analisis/an-A/exportar",
                "/api/trabajos/job-A/eventos",
                "/api/proyectos/proj-audit",
            ],
        )
        hallazgos = aislamiento.verificar(_ctx(["A", "B"]))

    assert len(hallazgos) == 1
    h = hallazgos[0]
    assert h.tipo == TipoHallazgo.aislamiento
    assert h.gravedad == Gravedad.critica
    assert "GET /api/proyectos/{proyecto_id}" in h.titulo  # ruta normalizada, no proj-A
    assert "proj-A" not in h.titulo and "proj-A" not in h.evidencia[0].extracto
    assert h.huella


def test_delete_solo_contra_el_proyecto_de_auditoria():
    with respx.mock(assert_all_called=False) as m:
        _inventario_de_a(m)
        _probes_404(
            m,
            [
                "/api/proyectos/proj-A",
                "/api/datasets/ds-A",
                "/api/plantillas/tpl-A",
                "/api/analisis/an-A/exportar",
                "/api/trabajos/job-A/eventos",
            ],
        )
        # PATCH/DELETE solo pueden tocar el proyecto de auditoría; proj-A NO está mockeado para
        # esos métodos, así que un intento contra él haría fallar el test (respx no lo resuelve).
        patch = m.patch(f"{API}/api/proyectos/proj-audit").respond(404)
        delete = m.delete(f"{API}/api/proyectos/proj-audit").respond(404)

        aislamiento.verificar(_ctx(["A", "B"]))

        assert delete.called and patch.called
        for llamada in m.calls:
            if llamada.request.method == "DELETE":
                assert llamada.request.url.path == "/api/proyectos/proj-audit"


def test_sse_primer_evento_con_datos_es_hallazgo():
    with respx.mock(assert_all_called=False) as m:
        _inventario_de_a(m)
        _probes_404(
            m,
            [
                "/api/proyectos/proj-A",
                "/api/datasets/ds-A",
                "/api/plantillas/tpl-A",
                "/api/analisis/an-A/exportar",
                "/api/proyectos/proj-audit",
            ],
        )
        m.get(f"{API}/api/trabajos/job-A/eventos").mock(
            return_value=httpx.Response(200, text="data: progreso\n\n")
        )
        hallazgos = aislamiento.verificar(_ctx(["A", "B"]))

    assert [h.titulo for h in hallazgos] == [
        "Empresa B accede a recursos de A: GET /api/trabajos/{id}/eventos"
    ]


def test_una_sola_empresa_da_hallazgo_no_ejecutada():
    with respx.mock(assert_all_called=False) as m:
        _inventario_de_a(m)
        hallazgos = aislamiento.verificar(_ctx(["A"]))

    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == TipoHallazgo.regla
    assert hallazgos[0].gravedad == Gravedad.baja
    assert "no ejecutada" in hallazgos[0].titulo


def test_422_de_validacion_no_es_fuga():
    """Regresión (corrida 20261101-210205): un 422 `{"detail": [...]}` es un error de validación
    de FastAPI, no datos de A; salía como 3 fugas críticas falsas."""
    with respx.mock(assert_all_called=False) as m:
        _inventario_de_a(m)
        m.get(f"{API}/api/analisis/an-A/exportar").respond(
            422, json={"detail": [{"loc": ["query", "formato"], "msg": "Field required"}]}
        )
        _probes_404(
            m,
            [
                "/api/proyectos/proj-A",
                "/api/datasets/ds-A",
                "/api/plantillas/tpl-A",
                "/api/trabajos/job-A/eventos",
                "/api/proyectos/proj-audit",
            ],
        )
        assert aislamiento.verificar(_ctx(["A", "B"])) == []
