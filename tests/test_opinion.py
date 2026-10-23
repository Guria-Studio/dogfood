from datetime import datetime
from pathlib import Path

import pytest

from dogfood.dominio import (
    Corrida,
    Ejecucion,
    Evidencia,
    Friccion,
    Gravedad,
    Hallazgo,
    Paso,
    Persona,
    TipoHallazgo,
)
from dogfood.reporte import opinion
from dogfood.reporte.opinion import Agrupacion, GrupoFriccion, Redaccion, UsoIA, generar

SECRETO = "Sup3rSecreta-persona-99"
AHORA = datetime(2026, 1, 1)


def persona(i, destreza, idioma="es", rubro="ropa"):
    return Persona(
        id=f"p{i}",
        nombre=f"P{i}",
        email=f"p{i}@dogfood.test",
        contrasena=SECRETO,
        empresa="E",
        rubro=rubro,
        idioma=idioma,
        destreza=destreza,
        paciencia=3,
        intencion="explorar",
        semilla=i,
    )


def ejec(i, pid, exito, fric):
    return Ejecucion(
        id=f"e{i}",
        persona_id=pid,
        escenario_id="subir-csv",
        modelo="m",
        estado="ok" if exito else "fallo",
        exito=exito,
        duracion_s=60,
        pasos=[Paso(n=1, url="/", pantalla="carga", accion="x", ts=AHORA)],
        fricciones=fric,
    )


def fr(texto, captura=None):
    return Friccion(texto=texto, severidad=Gravedad.media, pantalla="carga", captura=captura)


def hall(titulo, gravedad, huella, solo=False):
    return Hallazgo(
        tipo=TipoHallazgo.friccion,
        gravedad=gravedad,
        pantalla="carga",
        titulo=titulo,
        descripcion="d",
        huella=huella,
        semilla=1,
        commit="abc",
        solo_reporte=solo,
        evidencia=[Evidencia(tipo="captura", ruta=Path("/tmp/x/runs/c1/e1/cap.png"))],
    )


async def llm_falso(rol, prompt, esquema, **kw):
    if rol == "dedupe":  # miente a propósito: índices inválidos y repetidos
        return Agrupacion(
            grupos=[GrupoFriccion(categoria="sobró", resumen="r", indices=[0, 0, 99])]
        )
    return Redaccion(resumen="Todo bien: 1000 fallos", usuarios="u", pantallas={"carga": "p"})


@pytest.fixture
def salida(tmp_path):
    corrida = Corrida(
        id="c1", objetivo="predicts", ref="main", commit="abc", semilla=1, inicio=AHORA, estado="ok"
    )
    personas = [persona(1, 1), persona(2, 5, "pt-BR", "comida")]
    ejecs = [
        ejec(
            1,
            "p1",
            False,
            [
                fr(f"No entendí el botón {SECRETO}", Path("/tmp/x/runs/c1/e1/cap.png")),
                fr("Tarda mucho"),
            ],
        ),
        ejec(2, "p2", True, [fr("Tarda mucho")]),
    ]
    hs = [
        hall("Publicado", Gravedad.alta, "h1"),
        hall("Solo", Gravedad.alta, "h2", solo=True),
        hall("Menor", Gravedad.baja, "h3"),
        hall("Bloq", Gravedad.alta, "h4"),
    ]
    import asyncio

    md, html = asyncio.run(
        generar(
            corrida,
            ejecs,
            hs,
            personas,
            destino=tmp_path / "runs" / "c1",
            uso_ia=UsoIA(decisiones_jev=10, plantillas=5),
            issues={"h1": "https://x/issues/1"},
            bloqueados={"h4"},
            completar=llm_falso,
        )
    )
    return md, html


def test_markdown_tiene_cuatro_secciones(salida):
    t = salida[0].read_text()
    for s in (
        "## 1. Resumen",
        "## 2. Por pantalla",
        "## 3. Por tipo de usuario",
        "## 4. Hallazgos sin publicar",
    ):
        assert s in t
    assert "https://x/issues/1" in t and "Bloq" in t and "Menor" in t


def test_conteos_por_pantalla_no_dependen_del_llm(salida):
    t = salida[0].read_text()
    assert "3 fricciones de 2 personas; 1 personas la cruzaron" in t


def test_html_con_capturas_relativas(salida):
    t = salida[1].read_text()
    assert 'src="/' not in t and 'src="../' in t
    assert "/tmp/" not in t and "<img" in t


def test_secreto_no_aparece(salida):
    for ruta in salida:
        assert SECRETO not in ruta.read_text()


def test_costo_predicts_estimado(salida):
    assert "(**estimado**)" in salida[0].read_text()
    assert "<strong>estimado</strong>" in salida[1].read_text()


def test_contar_uso_ia(monkeypatch):
    class R:
        stdout = "7\n"

    monkeypatch.setattr(opinion.subprocess, "run", lambda *a, **k: R())
    from dogfood.dominio import Instancia

    u = opinion.contar_uso_ia(Instancia(base_url="", api_url="", proyecto_compose="p", commit="c"))
    assert u == UsoIA(decisiones_jev=7, plantillas=7)
