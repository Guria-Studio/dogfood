import asyncio
import sqlite3

import pytest

from dogfood import proyectos
from dogfood.config import Config
from dogfood.corrida import Opciones, correr
from dogfood.dominio import Ejecucion, Escenario, Instancia

BASE = {"slug": "mi-app", "nombre": "Mi app", "tipo": "web", "objetivo": "predicts"}


def test_predicts_se_siembra_solo(tmp_path):
    p = proyectos.obtener("predicts", tmp_path)
    assert p and p.objetivo == "predicts" and p.creado
    assert [x.slug for x in proyectos.listar(tmp_path)] == ["predicts"]


def test_crear_leer_actualizar_borrar(tmp_path):
    p = proyectos.crear(
        BASE | {"entornos": [{"nombre": "stg", "url": "http://s", "predeterminado": True}]},
        tmp_path,
    )
    assert proyectos.obtener("mi-app", tmp_path) == p
    n = proyectos.actualizar(
        "mi-app", {"instrucciones": "sé breve", "comportamiento": {"concurrencia": 2}}, tmp_path
    )
    assert n.instrucciones == "sé breve"
    assert n.comportamiento.concurrencia == 2 and n.comportamiento.viewport == "escritorio"
    assert n.entorno().nombre == "stg"
    assert proyectos.borrar("mi-app", tmp_path) and proyectos.obtener("mi-app", tmp_path) is None
    proyectos.borrar("predicts", tmp_path)
    assert proyectos.listar(tmp_path) == []  # no se vuelve a sembrar


def test_validaciones(tmp_path):
    for malo in ({"slug": "Mal Slug"}, {"tipo": "palm"}, {"objetivo": "nada"}):
        with pytest.raises(ValueError):
            proyectos.crear(BASE | malo, tmp_path)
    proyectos.crear(BASE, tmp_path)
    with pytest.raises(proyectos.ErrorProyecto):
        proyectos.crear(BASE, tmp_path)


def test_el_secreto_no_se_guarda(tmp_path):
    proyectos.crear(
        BASE
        | {
            "acceso": {"usuario": "u", "secreto_ref": "MI_CLAVE", "secreto": "s3creto-xyz"},
            "clave": "s3creto-xyz",
        },
        tmp_path,
    )
    assert b"s3creto-xyz" not in (tmp_path / "dogfood.db").read_bytes()
    assert proyectos.obtener("mi-app", tmp_path).acceso.secreto_ref == "MI_CLAVE"


class Objetivo:
    nombre = "falso"

    def preparar(self, ref, corrida):
        return Instancia(base_url="http://x", api_url="http://x", proyecto_compose="p", commit="c")

    def destruir(self, instancia):
        pass

    def escenarios(self):
        e = Escenario(id="a", titulo="a", objetivo="o", criterio_exito="c")
        return [e]

    def verificadores(self):
        return []

    def logs(self, instancia, desde):
        return {}


def test_corrida_con_slug_usa_los_ajustes(tmp_path, monkeypatch):
    t = {"activas": 0, "max": 0, "instrucciones": set(), "estilo": []}

    async def ejecutar(
        persona, escenario, instancia, dataset, carpeta, llm, juez, *, objetivo, contador
    ):
        t["activas"] += 1
        t["max"] = max(t["max"], t["activas"])
        t["instrucciones"].add(persona.instrucciones)
        t["estilo"].append(persona.estilo)
        t["url"] = instancia.base_url
        await asyncio.sleep(0.01)
        t["activas"] -= 1
        return Ejecucion(
            id=carpeta.name,
            persona_id=persona.id,
            escenario_id="a",
            modelo="m",
            estado="ok",
            exito=True,
        )

    monkeypatch.setattr("dogfood.corrida.navegador.ejecutar", ejecutar)
    proyectos.actualizar(
        "predicts",
        {
            "instrucciones": "usa el menú lateral",
            "comportamiento": {"concurrencia": 2, "viewport": "movil"},
            "entornos": [{"nombre": "stg", "url": "http://stg", "predeterminado": True}],
        },
        tmp_path,
    )
    c = asyncio.run(
        correr(
            Opciones(
                objetivo="predicts",
                raiz=tmp_path,
                personas=6,
                semilla=3,
                llm=object(),
                cfg=Config(roles={"persona": ["m"], "juez": ["m"]}),
                objetivo_obj=Objetivo(),
            )
        )
    )
    assert c.estado.startswith("ok") and t["max"] == 2
    assert t["instrucciones"] == {"usa el menú lateral"} and all("movil" in e for e in t["estilo"])
    assert t["url"] == "http://stg" and c.parametros["proyecto"] == "predicts"
    con = sqlite3.connect(tmp_path / "dogfood.db")
    assert con.execute("SELECT proyecto FROM corridas").fetchone()[0] == "predicts"
