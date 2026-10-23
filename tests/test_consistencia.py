import asyncio
from datetime import datetime
from pathlib import Path

from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import (
    Corrida,
    Ejecucion,
    Escenario,
    Gravedad,
    Hallazgo,
    Instancia,
    TipoHallazgo,
)
from dogfood.reporte.consistencia import marcar_inestables, wilson
from dogfood.reporte.opinion import Agrupacion, Redaccion, generar


class Objetivo:
    nombre = "falso"

    def preparar(self, ref, corrida):
        return Instancia(base_url="http://x", api_url="http://x", proyecto_compose="p", commit="c")

    def destruir(self, instancia):
        pass

    def escenarios(self):
        return [
            Escenario(
                id=i, titulo=i, objetivo="o", criterio_exito="c",
                datos={"perfil": "farmacia", "clientes": 20},
            )
            for i in "ab"
        ]  # fmt: skip

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


def test_repeat_3_con_2_asignaciones_da_6_ejecuciones_con_emails_distintos(tmp_path, monkeypatch):
    vistos = []

    async def ejecutar(
        persona, escenario, instancia, ds, carpeta, llm, juez, *, objetivo, contador
    ):
        vistos.append((persona.id, escenario.id, persona.email))
        return Ejecucion(
            id=carpeta.name, persona_id=persona.id, escenario_id=escenario.id, modelo="m",
            estado="ok", exito=True,
        )  # fmt: skip

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]})
    asyncio.run(
        correr(
            Opciones(
                raiz=tmp_path, cfg=cfg, objetivo_obj=Objetivo(), llm=object(), semilla=7,
                personas=2, escenarios=["a"], repeat=3, sin_publicar=True,
            )
        )
    )  # fmt: skip
    assert len(vistos) == 6
    assert len({v[2] for v in vistos}) == 6
    for k in (1, 2, 3):
        assert sum(f"+r{k}@" in v[2] for v in vistos) == 2


def test_wilson_2_de_3():
    bajo, alto = wilson(2, 3)
    assert round(2 / 3, 2) == 0.67
    assert (round(bajo, 2), round(alto, 2)) == (0.21, 0.94)


def _ejecs(n=3):
    return [
        Ejecucion(id=f"e{i}", persona_id="p", escenario_id="s", modelo="m",
                  estado="ok", exito=i < 2)
        for i in range(n)
    ]  # fmt: skip


def _hall(ocurrencias):
    return Hallazgo(
        tipo=TipoHallazgo.friccion, gravedad=Gravedad.alta, pantalla="x", titulo="t",
        descripcion="d", huella="h", ejecucion_id="e0", ocurrencias=ocurrencias,
        semilla=1, commit="c",
    )  # fmt: skip


def test_hallazgo_en_1_de_3_es_inestable_y_baja_gravedad():
    h = _hall(1)
    marcar_inestables([h], _ejecs())
    assert h.gravedad == Gravedad.media
    assert any("inestable" in ev.extracto for ev in h.evidencia)


def test_hallazgo_en_2_de_3_no_cambia():
    h = _hall(2)
    marcar_inestables([h], _ejecs())
    assert h.gravedad == Gravedad.alta and not h.evidencia


def test_reporte_incluye_consistencia(tmp_path):
    async def falso(rol, prompt, esquema):
        return Agrupacion(grupos=[]) if esquema is Agrupacion else Redaccion()

    corrida = Corrida(
        id="c", objetivo="o", ref="main", commit="c", semilla=1,
        inicio=datetime.now().astimezone(), estado="ok",
    )  # fmt: skip
    md, html = asyncio.run(
        generar(corrida, _ejecs(), [_hall(1)], [], destino=tmp_path, completar=falso)
    )
    assert "Consistencia" in Path(md).read_text()
    assert "Consistencia" in Path(html).read_text()
