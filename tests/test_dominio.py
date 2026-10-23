from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from dogfood.dominio import (
    MAX_TEXTO_VISIBLE,
    Corrida,
    DatasetSintetico,
    Ejecucion,
    Escenario,
    EventoConsola,
    EventoRed,
    Evidencia,
    Friccion,
    Gravedad,
    Hallazgo,
    Idioma,
    Instancia,
    Intencion,
    Paso,
    Persona,
    TipoHallazgo,
    UsoLlm,
)

# Copia literal del ejemplo de *Interfaces → Escenario YAML* en docs/arch/001-usuarios-agenticos.md
ESCENARIO_YAML = """
id: recompra-completa
titulo: Análisis de recompra completo
superficies: [registro, subir, mapeo, calidad, analisis, resultados, exportar]
persona_compatible: {intencion: [analisis_completo, explorar], destreza_min: 1}
datos: {perfil: farmacia, clientes: 300, defectos: []}
objetivo: >
  Crea una cuenta, sube el CSV de ventas, confirma el mapeo, corre un análisis de
  recompra y descarga el CSV de recordatorios.
criterio_exito: Se descargó un CSV de recordatorios con al menos una fila.
max_pasos: 60
carril: normal            # normal | login_fallido
"""

AHORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def persona(**cambios) -> Persona:
    datos = {
        "id": "p1",
        "nombre": "Ana Souza",
        "email": "ana@dogfood.test",
        "contrasena": "x",
        "empresa": "Farmácia Ana",
        "rubro": "farmacia",
        "idioma": Idioma.pt_BR,
        "destreza": 3,
        "paciencia": 2,
        "intencion": Intencion.explorar,
        "estilo": ["impaciente"],
        "semilla": 7,
    }
    return Persona(**(datos | cambios))


def hallazgo(**cambios) -> Hallazgo:
    datos = {
        "tipo": TipoHallazgo.tecnico,
        "gravedad": Gravedad.alta,
        "pantalla": "mapeo",
        "titulo": "500 al confirmar",
        "descripcion": "d",
        "pasos": ["subir", "confirmar"],
        "evidencia": [Evidencia(tipo="red", extracto="POST /api/x 500")],
        "semilla": 7,
        "commit": "abc",
    }
    return Hallazgo(**(datos | cambios))


def test_persona_destreza_fuera_de_rango() -> None:
    with pytest.raises(ValidationError):
        persona(destreza=6)


def test_gravedad_ordenable() -> None:
    assert Gravedad.alta > Gravedad.media
    assert Gravedad.critica > Gravedad.alta > Gravedad.media > Gravedad.baja
    assert max([Gravedad.baja, Gravedad.critica, Gravedad.media]) is Gravedad.critica


def test_escenario_desde_yaml_de_la_arquitectura() -> None:
    e = Escenario.model_validate(yaml.safe_load(ESCENARIO_YAML))
    assert e.carril == "normal"
    assert e.persona_compatible.intencion == [Intencion.analisis_completo, Intencion.explorar]
    assert e.datos is not None and e.datos.clientes == 300
    with pytest.raises(ValidationError):
        Escenario.model_validate(yaml.safe_load(ESCENARIO_YAML) | {"carril": "otro"})


def test_huella_estable() -> None:
    h = hallazgo()
    assert h.calcular_huella("POST /api/{id} 500") == hallazgo().calcular_huella(
        "POST /api/{id} 500"
    )
    otro = hallazgo(tipo=TipoHallazgo.logica)
    assert h.calcular_huella("f") != otro.calcular_huella("f")


def test_texto_visible_recortado() -> None:
    p = Paso(n=1, url="u", pantalla="s", accion="a", texto_visible="x" * 5000, ts=AHORA)
    assert len(p.texto_visible) == MAX_TEXTO_VISIBLE


def _instancias() -> list[BaseModel]:
    paso = Paso(n=1, url="http://x/", pantalla="inicio", accion="click", captura=Path("c.png"),
                texto_visible="hola", ts=AHORA)  # fmt: skip
    friccion = Friccion(texto="no entiendo", severidad=Gravedad.media, pantalla="mapeo", cita="?")
    return [
        persona(),
        Escenario.model_validate(yaml.safe_load(ESCENARIO_YAML)),
        DatasetSintetico(
            id="d1",
            perfil="farmacia",
            ruta_csv=Path("v.csv"),
            ruta_verdad=Path("verdad.json"),
            defectos=["latin1"],
            n_clientes=3,
            n_filas=10,
            semilla=7,
        ),
        paso,
        EventoRed(metodo="GET", url="http://x/api", estado=500, ms=12.5),
        EventoConsola(nivel="error", texto="boom", url="http://x/"),
        friccion,
        Ejecucion(
            id="e1",
            persona_id="p1",
            escenario_id="recompra-completa",
            dataset_id="d1",
            modelo="m",
            estado="rendido",
            pasos=[paso],
            red=[EventoRed(metodo="GET", url="u", estado=404, ms=1)],
            consola=[EventoConsola(nivel="warn", texto="t")],
            fricciones=[friccion],
            descargas=[Path("r.csv")],
            exito=True,
            motivo_juez="ok",
            duracion_s=3.2,
            ruta_historial=Path("historial.json"),
            empresa_id="emp",
            notas=["429 esperado"],
        ),
        hallazgo(
            esperado="200",
            obtenido="500",
            huella="h",
            ejecucion_id="e1",
            solo_reporte=True,
            ocurrencias=2,
        ),
        UsoLlm(
            rol="juez", modelo="m", tokens_in=10, tokens_out=5, costo_usd=0.01, ejecucion_id="e1"
        ),
        Corrida(
            id="c1",
            objetivo="predicts",
            ref="main",
            commit="abc",
            semilla=7,
            inicio=AHORA,
            fin=AHORA,
            estado="ok",
            parametros={"concurrencia": 5},
        ),
        Instancia(
            base_url="http://x",
            api_url="http://x/api",
            proyecto_compose="p",
            commit="abc",
            parametros={"MIN_COMPRAS": 3},
        ),
    ]


@pytest.mark.parametrize("modelo", _instancias(), ids=lambda m: type(m).__name__)
def test_ida_y_vuelta_json(modelo: BaseModel) -> None:
    assert type(modelo).model_validate_json(modelo.model_dump_json()) == modelo
