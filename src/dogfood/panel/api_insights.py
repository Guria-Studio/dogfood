"""Insights del proyecto (F11.2.T3): qué arreglar primero, tendencia y cobertura por caso de uso.

Reutiliza `_Datos` de api_casos: mismos TC###, mismos estados y la misma redacción de secretos.
"""

import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dogfood import proyectos
from dogfood.config import Config
from dogfood.dominio import Hallazgo
from dogfood.panel import detalle
from dogfood.panel.api_casos import _DESDE_PLAN, _FALLIDOS, _GRAVEDAD, Estado, _Datos


class IssueInsight(BaseModel):
    huella: str
    titulo: str
    ruta: str  # pantalla del hallazgo
    gravedad: str
    casos: list[str]  # TC### afectados


class Regresion(BaseModel):
    tc: str
    nombre: str
    ref: str  # ref@commit de la corrida en que volvió a fallar


class PuntoTendencia(BaseModel):
    corrida_id: str
    fecha: str
    pasaron: int
    total: int
    tasa: float
    costo_usd: float


class FriccionPantalla(BaseModel):
    pantalla: str
    n: int
    citas: list[str]


class Oraculo(BaseModel):
    correctas: int  # ejecuciones sin ningún número equivocado
    equivocadas: int  # hallazgos con esperado/obtenido


class UsoCobertura(BaseModel):
    caso_de_uso: str
    estado: str  # cubierto | planeado | brecha
    ultimos: list[Estado]  # resultado en cada una de las últimas corridas
    casos: int
    pasaron: int
    fallaron: int
    bloqueados: int
    porcentaje: int
    ultima: str | None


class Insights(BaseModel):
    corrida_id: str | None
    casos_fallaron: int
    prompt: str
    pasaron: int
    total: int
    abiertos: int
    arreglados: int
    regresiones: list[Regresion]
    tendencia: list[PuntoTendencia]
    issues: list[IssueInsight]
    friccion: list[FriccionPantalla]
    oraculo: Oraculo
    cobertura: list[UsoCobertura]


def _insights(raiz: Path, p: proyectos.Proyecto, secretos: list[str]) -> Insights:
    d = _Datos(raiz, p, secretos)
    with closing(sqlite3.connect(raiz / "dogfood.db")) as con:
        con.row_factory = sqlite3.Row
        meta = {
            r["id"]: r
            for r in con.execute(
                'SELECT id, ref, "commit", costo_usd FROM corridas'
                " WHERE proyecto = ? OR (proyecto IS NULL AND objetivo = ?)",
                (p.slug, p.objetivo),
            )
        }
    tc = {caso: f"TC{n:03d}" for n, caso in enumerate(d.por_caso, 1)}
    # corrida → {caso → vista}, en orden de inicio; solo las que tienen plan
    por_corrida: dict[str, dict] = {}
    for caso, vistas in d.por_caso.items():
        for cid, v in vistas:
            por_corrida.setdefault(cid, {})[caso] = v
    orden = [c for c in d.fecha if c in por_corrida]
    vacio = Insights(
        corrida_id=None, casos_fallaron=0, prompt="", pasaron=0, total=0, abiertos=0, arreglados=0,
        regresiones=[], tendencia=[], issues=[], friccion=[], oraculo=Oraculo(correctas=0, equivocadas=0),
        cobertura=[],
    )  # fmt: skip
    if not orden:
        return vacio

    def estado(v) -> Estado:
        return _DESDE_PLAN[v.estado]

    def huellas(cid: str) -> dict[str, list[tuple[str, Hallazgo]]]:
        """huella → [(caso, hallazgo)] de la corrida; sin los que solo van al reporte."""
        eje = {v.ejecucion_id: caso for caso, v in por_corrida[cid].items() if v.ejecucion_id}
        salida: dict[str, list[tuple[str, Hallazgo]]] = {}
        for e, caso in eje.items():
            for _, h in d.hallazgos.get(e, []):
                if h.huella and not h.solo_reporte:
                    salida.setdefault(h.huella, []).append((caso, h))
        return salida

    ultima = orden[-1]
    previa = orden[-2] if len(orden) > 1 else None
    hs, hs_previa = huellas(ultima), (huellas(previa) if previa else {})
    vistas = por_corrida[ultima]

    issues = []
    for huella, pares in hs.items():
        h = min((x[1] for x in pares), key=lambda x: _GRAVEDAD.get(x.gravedad.value, 9))
        casos = sorted({tc[c] for c, _ in pares})
        issues.append(
            IssueInsight(
                huella=huella, titulo=d.red(h.titulo), ruta=h.pantalla,
                gravedad=h.gravedad.value, casos=casos,
            )
        )  # fmt: skip
    issues.sort(key=lambda i: -len(i.casos))

    def ref(cid: str) -> str:
        m = meta.get(cid)
        return f"{m['ref']}@{m['commit'][:7]}" if m else cid

    regresiones = []
    for caso, v in vistas.items():
        if estado(v) not in _FALLIDOS:
            continue
        antes = next(
            (
                estado(x)
                for c, x in reversed(d.por_caso[caso])
                if c in orden[:-1] and x.ejecucion_id
            ),
            None,
        )
        if antes == "paso":
            regresiones.append(Regresion(tc=tc[caso], nombre=v.titulo, ref=ref(ultima)))

    fallidos = [(c, v) for c, v in vistas.items() if estado(v) in _FALLIDOS]
    prompt = ""
    if fallidos:
        lineas = [
            f"{len(fallidos)} casos de usuario de dogfood fallaron en la corrida {ultima}"
            + f" ({ref(ultima)}). Arregla estas causas:",
        ]
        for n, i in enumerate(issues, 1):
            lineas += [
                "",
                f"## {n}. {i.titulo} ({i.gravedad}) — {i.ruta}",
                f"Casos: {', '.join(i.casos)}",
            ]
            for caso, h in hs[i.huella][:1]:
                lineas += [d.red(h.descripcion)] + (
                    [f"Esperado: {d.red(h.esperado)}"] if h.esperado else []
                )
                lineas += [f"Obtenido: {d.red(h.obtenido)}"] if h.obtenido else []
        con_issue = {c for ps in hs.values() for c, _ in ps}
        sueltos = [(c, v) for c, v in fallidos if c not in con_issue]
        for c, v in sueltos:
            lineas += [
                "",
                f"## {tc[c]} — {v.titulo}",
                d.falla(estado(v), v.ejecucion_id) or "sin motivo",
            ]
        lineas += ["", "Verifica cada caso con:"]
        lineas += [f"dogfood replay {v.ejecucion_id}" for _, v in fallidos if v.ejecucion_id]
        prompt = "\n".join(lineas)

    # fricción y oráculo de la última corrida
    por_pantalla: dict[str, list[str]] = {}
    equivocadas = con_error = 0
    for v in vistas.values():
        if not v.ejecucion_id:
            continue
        for pantalla, fs in detalle.datos_ejecucion(raiz, v.ejecucion_id)["fricciones"].items():
            por_pantalla.setdefault(pantalla, []).extend(
                d.red(f["f"].cita or f["f"].texto) for f in fs
            )
        malos = [h for _, h in d.hallazgos.get(v.ejecucion_id, []) if h.esperado is not None]
        equivocadas += len(malos)
        con_error += bool(malos)
    friccion = [
        FriccionPantalla(pantalla=k, n=len(c), citas=c[:3])
        for k, c in sorted(por_pantalla.items(), key=lambda x: -len(x[1]))[:5]
    ]
    ejecutadas = sum(bool(v.ejecucion_id) for v in vistas.values())

    tendencia = []
    for cid in orden[-10:]:
        vs = por_corrida[cid].values()
        n = sum(estado(v) == "paso" for v in vs)
        tendencia.append(
            PuntoTendencia(
                corrida_id=cid, fecha=d.fecha[cid] or "", pasaron=n, total=len(vs),
                tasa=n / len(vs) if vs else 0, costo_usd=meta[cid]["costo_usd"] if cid in meta else 0,
            )
        )  # fmt: skip

    filas: dict[str, list] = {}
    for f in d.filas():
        filas.setdefault(f.caso_de_uso, []).append(f)
    cobertura = []
    for uso, fs in filas.items():
        cuenta = Counter(f.estado for f in fs)
        ids = {f.id for f in fs}
        ultimos = []
        for cid in orden[-5:]:
            est = {estado(v) for c, v in por_corrida[cid].items() if c in ids}
            ultimos.append(
                "fallo" if est & {"fallo", "no_concluyente"} else "bloqueado" if "bloqueado" in est
                else "paso" if "paso" in est else "planeado"
            )  # fmt: skip
        pasaron = cuenta["paso"]
        cobertura.append(
            UsoCobertura(
                caso_de_uso=uso,
                estado="cubierto"
                if pasaron == len(fs)
                else "planeado"
                if cuenta["planeado"] == len(fs)
                else "brecha",
                ultimos=ultimos,
                casos=len(fs),
                pasaron=pasaron,
                fallaron=cuenta["fallo"] + cuenta["no_concluyente"],
                bloqueados=cuenta["bloqueado"],
                porcentaje=round(100 * pasaron / len(fs)),
                ultima=max((f.fecha for f in fs if f.fecha), default=None),
            )
        )

    return Insights(
        corrida_id=ultima, casos_fallaron=len(fallidos),
        prompt=prompt, pasaron=sum(estado(v) == "paso" for v in vistas.values()), total=len(vistas),
        abiertos=len(hs), arreglados=len(hs_previa.keys() - hs.keys()), regresiones=regresiones,
        tendencia=tendencia, issues=issues, friccion=friccion,
        oraculo=Oraculo(correctas=ejecutadas - con_error, equivocadas=equivocadas),
        cobertura=cobertura,
    )  # fmt: skip


def registrar_api_insights(app: FastAPI, raiz: Path, cfg: Config | None = None) -> None:
    raiz = Path(raiz)

    @app.get("/api/proyectos/{slug}/insights", response_model=Insights)
    def api_insights(slug: str):
        p = proyectos.obtener(slug, raiz)
        if p is None:
            raise HTTPException(404, f"el proyecto {slug!r} no existe")
        return _insights(raiz, p, list(cfg._secretos.values()) if cfg else [])
