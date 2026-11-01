"""API del plan de pruebas: los casos de una corrida con el estado de su ejecución."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException

from dogfood.plan import CasoPrueba, PlanPruebas

EstadoCaso = Literal["pendiente", "en_curso", "exito", "fallo", "rendido", "no_concluyente"]
_POR_RESULTADO = {"aprobado": "exito", "fallo": "fallo", "no_concluyente": "no_concluyente"}


class CasoVista(CasoPrueba):
    estado: EstadoCaso
    ejecucion_id: str | None  # la última ejecución empezada; None si el caso sigue pendiente
    duracion_s: float | None


def _estado(fila: sqlite3.Row | None, empezada: bool, corrida_abierta: bool) -> EstadoCaso:
    if fila is None:
        return "en_curso" if empezada and corrida_abierta else "pendiente"
    if fila["estado"] == "rendido":
        return "rendido"
    res = fila["resultado"] or ("aprobado" if fila["exito"] else "fallo")
    return _POR_RESULTADO.get(res, "no_concluyente")


def casos(raiz: Path, corrida_id: str) -> list[CasoVista] | None:
    ruta = raiz / corrida_id / "plan.json"
    if not ruta.is_file():
        return None
    plan = PlanPruebas.model_validate_json(ruta.read_text())
    with closing(sqlite3.connect(raiz / "dogfood.db")) as con:
        con.row_factory = sqlite3.Row
        filas = {
            r["id"]: r
            for r in con.execute(
                "SELECT id, estado, resultado, exito, duracion_s FROM ejecuciones"
                " WHERE corrida_id = ?",
                (corrida_id,),
            )
        }
        c = con.execute("SELECT estado FROM corridas WHERE id = ?", (corrida_id,)).fetchone()
    abierta = c is not None and c[0] == "en_curso"
    dir_ej = raiz / corrida_id / "ejecuciones"
    salida = []
    for caso in plan.casos:
        # ponytail: con --repeat se muestra la última repetición empezada, no un agregado
        empezadas = [i for i in caso.ejecuciones if i in filas or (dir_ej / i).is_dir()]
        eid = empezadas[-1] if empezadas else None
        fila = filas.get(eid) if eid else None
        salida.append(
            CasoVista(
                **caso.model_dump(),
                estado=_estado(fila, eid is not None, abierta),
                ejecucion_id=eid,
                duracion_s=fila["duracion_s"] if fila is not None else None,
            )
        )
    return salida


def registrar_api_plan(app: FastAPI, raiz: Path) -> None:
    @app.get("/api/corridas/{corrida_id}/plan", response_model=list[CasoVista])
    def api_plan(corrida_id: str):
        r = casos(Path(raiz), corrida_id)
        if r is None:
            raise HTTPException(404, f"la corrida {corrida_id!r} no tiene plan")
        return r
