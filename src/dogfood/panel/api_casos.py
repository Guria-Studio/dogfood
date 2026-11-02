"""Casos de prueba del proyecto (F11.2.T1): los del plan de cada corrida, con su último resultado.

El ID `TC###` es estable: se numeran por orden de primera aparición en las corridas del proyecto.
Todo texto que viene de la ejecución (motivo, evidencia, sugerencia) pasa por `redactar`.
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from dogfood import proyectos
from dogfood.config import Config
from dogfood.dominio import Hallazgo
from dogfood.panel import api_plan, detalle
from dogfood.panel.api import FriccionVista, PasoVista, _detalle
from dogfood.reporte import sugerencia
from dogfood.reporte.redactar import redactar

Estado = Literal["planeado", "corriendo", "paso", "fallo", "bloqueado", "no_concluyente"]
ESTADOS: tuple[Estado, ...] = Estado.__args__
_DESDE_PLAN: dict[str, Estado] = {
    "pendiente": "planeado",
    "en_curso": "corriendo",
    "exito": "paso",
    "fallo": "fallo",
    "rendido": "bloqueado",
    "no_concluyente": "no_concluyente",
}
_FALLIDOS = {"fallo", "bloqueado", "no_concluyente"}
_GRAVEDAD = {"critica": 0, "alta": 1, "media": 2, "baja": 3}


class PersonaCaso(BaseModel):
    id: str
    nombre: str
    idioma: str
    destreza: int
    iniciales: str


class CasoFila(BaseModel):
    tc: str
    id: str  # escenario:persona, el del plan
    nombre: str
    caso_de_uso: str
    persona: PersonaCaso
    prioridad: Literal["alta", "media"]
    estado: Estado
    fecha: str | None
    falla: str  # una línea; vacía si no falló
    ejecucion_id: str | None


class Grupo(BaseModel):
    caso_de_uso: str
    casos: list[CasoFila]


class ListaCasos(BaseModel):
    conteos: dict[str, int]
    total: int
    grupos: list[Grupo]


class EjecucionHistorial(BaseModel):
    ejecucion_id: str
    corrida_id: str
    estado: Estado
    error: str
    fecha: str


class Verificacion(BaseModel):
    titulo: str
    pantalla: str
    esperado: str
    obtenido: str


class Falla(BaseModel):
    error: str
    hallazgo_id: str | None
    sugerencia: sugerencia.Sugerencia | None  # F10.2.T2, «sugerido por IA»
    prompt: str  # para Claude Code o Cursor, ya redactado


class DetalleCaso(CasoFila):
    objetivo: str
    criterio_exito: str
    pasos: list[PasoVista]
    video: str | None
    ajustes: dict[str, str]
    historial: list[EjecucionHistorial]
    opinion: list[FriccionVista]
    verificaciones: list[Verificacion]
    falla_detalle: Falla | None
    codigo: str | None
    lenguaje_codigo: str | None


def _iniciales(nombre: str) -> str:
    return "".join(p[0].upper() for p in nombre.split()[:2]) or "?"


def _una_linea(texto: str) -> str:
    return next((x.strip() for x in texto.splitlines() if x.strip()), "")


class _Datos:
    """Lo que hace falta leer de las corridas de un proyecto, leído una sola vez por pedido."""

    def __init__(self, raiz: Path, p: proyectos.Proyecto, secretos: list[str]):
        self.raiz = raiz
        with closing(sqlite3.connect(raiz / "dogfood.db")) as con:
            con.row_factory = sqlite3.Row
            corridas = con.execute(
                "SELECT id, COALESCE(fin, inicio) AS fecha FROM corridas"
                " WHERE proyecto = ? OR (proyecto IS NULL AND objetivo = ?) ORDER BY inicio",
                (p.slug, p.objetivo),
            ).fetchall()
            ids = [c["id"] for c in corridas]
            marcas = ",".join("?" * len(ids))
            self.motivos = {
                r["id"]: r["motivo_juez"]
                for r in con.execute(
                    f"SELECT id, motivo_juez FROM ejecuciones WHERE corrida_id IN ({marcas})", ids
                )
            }
        self.fecha = {c["id"]: c["fecha"] for c in corridas}
        self.secretos = list(secretos)
        self.personas: dict[tuple[str, str], dict] = {}
        self.hallazgos: dict[str, list[tuple[str, Hallazgo]]] = {}  # ejecucion_id → [(id, h)]
        # caso → [(corrida, CasoVista)] en orden de corrida; el orden de las claves da el TC
        self.por_caso: dict[str, list[tuple[str, api_plan.CasoVista]]] = {}
        for cid in ids:
            plan = api_plan.casos(raiz, cid)
            if plan is None:
                continue
            ruta = raiz / cid / "personas.json"
            for d in json.loads(ruta.read_text()) if ruta.is_file() else []:
                self.personas[(cid, d["id"])] = d
                self.secretos.append(d.get("contrasena", ""))
            rh = raiz / cid / "hallazgos.json"
            for n, d in enumerate(json.loads(rh.read_text()) if rh.is_file() else [], 1):
                h = Hallazgo.model_validate(d)
                if h.ejecucion_id:
                    self.hallazgos.setdefault(h.ejecucion_id, []).append((f"{cid}-H{n}", h))
            for c in plan:
                self.por_caso.setdefault(c.id, []).append((cid, c))

    def red(self, texto: str) -> str:
        return redactar(texto, self.secretos)

    def principal(self, eid: str | None) -> tuple[str, Hallazgo] | None:
        hs = self.hallazgos.get(eid or "", [])
        return min(hs, key=lambda x: _GRAVEDAD.get(x[1].gravedad.value, 9)) if hs else None

    def falla(self, estado: Estado, eid: str | None) -> str:
        if estado not in _FALLIDOS or eid is None:
            return ""
        motivo = _una_linea(self.motivos.get(eid, ""))
        if not motivo and (h := self.principal(eid)):
            motivo = h[1].titulo
        return self.red(motivo)

    def fila(self, n: int, caso_id: str) -> tuple[CasoFila, str, api_plan.CasoVista]:
        vistas = self.por_caso[caso_id]
        # el último resultado: la corrida más reciente en que el caso empezó; si no, la última
        cid, c = next(((ci, v) for ci, v in reversed(vistas) if v.ejecucion_id), vistas[-1])
        estado = _DESDE_PLAN[c.estado]
        per = self.personas.get((cid, c.persona_id), {})
        nombre = per.get("nombre", c.persona_nombre)
        fila = CasoFila(
            tc=f"TC{n:03d}",
            id=c.id,
            nombre=c.titulo,
            caso_de_uso=c.escenario_id,
            persona=PersonaCaso(
                id=c.persona_id,
                nombre=nombre,
                idioma=str(per.get("idioma", "")),
                destreza=int(per.get("destreza", 0)),
                iniciales=_iniciales(nombre),
            ),
            prioridad=c.prioridad,
            estado=estado,
            fecha=self.fecha.get(cid),
            falla=self.falla(estado, c.ejecucion_id),
            ejecucion_id=c.ejecucion_id,
        )
        return fila, cid, c

    def filas(self) -> list[CasoFila]:
        return [self.fila(n, k)[0] for n, k in enumerate(self.por_caso, 1)]


def _prompt(fila: CasoFila, error: str, h: Hallazgo | None, sug, d: _Datos) -> str:
    evidencia = [h.descripcion, h.obtenido or "", *(e.extracto for e in h.evidencia)] if h else []
    lineas = [
        f"Un test de usuario de dogfood falló: {fila.tc} — {fila.nombre}.",
        "",
        "## Problema",
        error,
        "",
        "## Evidencia (redactada)",
        *[f"- {d.red(x)}" for x in evidencia if x.strip()],
    ]
    if sug:
        lineas += ["", "## Causa probable (sugerida por IA)", d.red(sug.causa)]
        lineas += ["", "## Archivos probables"]
        lineas += [f"- {a.ruta}" + (f":{a.linea}" if a.linea else "") for a in sug.archivos]
        lineas += ["", "## Arreglo sugerido", d.red(sug.cambio)]
    lineas += [
        "",
        "Arregla la causa raíz y verifica reproduciendo el caso con:",
        f"dogfood replay {fila.ejecucion_id}",
    ]
    return "\n".join(lineas)


def _detalle_caso(d: _Datos, p: proyectos.Proyecto, tc: str) -> DetalleCaso:
    claves = list(d.por_caso)
    try:
        n = int(tc.upper().removeprefix("TC"))
        caso_id = claves[n - 1]
    except (ValueError, IndexError):
        raise HTTPException(404, f"el caso {tc!r} no existe") from None
    fila, cid, c = d.fila(n, caso_id)
    vista = (
        _detalle(detalle.datos_ejecucion(d.raiz, fila.ejecucion_id)) if fila.ejecucion_id else None
    )
    hallazgos = d.hallazgos.get(fila.ejecucion_id or "", [])
    historial = [
        EjecucionHistorial(
            ejecucion_id=v.ejecucion_id,
            corrida_id=ci,
            estado=_DESDE_PLAN[v.estado],
            error=d.falla(_DESDE_PLAN[v.estado], v.ejecucion_id),
            fecha=d.fecha.get(ci) or "",
        )
        for ci, v in reversed(d.por_caso[caso_id])
        if v.ejecucion_id
    ]
    falla = None
    if fila.estado in _FALLIDOS and fila.ejecucion_id:
        principal = d.principal(fila.ejecucion_id)
        hid, h = principal if principal else (None, None)
        sug = sugerencia.cargar(d.raiz / cid).get(hid) if hid else None
        error = d.red(d.motivos.get(fila.ejecucion_id, "") or (h.descripcion if h else ""))
        if sug:
            sug = sugerencia.Sugerencia(
                causa=d.red(sug.causa),
                archivos=sug.archivos,
                cambio=d.red(sug.cambio),
                confianza=sug.confianza,
            )
        falla = Falla(
            error=error, hallazgo_id=hid, sugerencia=sug, prompt=_prompt(fila, error, h, sug, d)
        )
    codigo = lenguaje = None
    if fila.ejecucion_id:
        carpeta = d.raiz / cid / "ejecuciones" / fila.ejecucion_id
        for nombre, leng in (("deterministico/test.dart", "dart"), ("test.spec.ts", "typescript")):
            if (carpeta / nombre).is_file():
                codigo, lenguaje = d.red((carpeta / nombre).read_text()), leng
                break
    comp = p.comportamiento
    ajustes = {
        "Viewport": comp.viewport,
        "Concurrencia": str(comp.concurrencia or "por defecto"),
        "Iniciar sesión una vez": "sí" if comp.login_una_vez else "no",
    }
    if vista:
        ajustes |= {"Driver": vista.ejecucion.driver, "Motor": vista.ejecucion.motor}
    return DetalleCaso(
        **fila.model_dump(),
        objetivo=c.objetivo,
        criterio_exito=c.criterio_exito,
        pasos=[
            x.model_copy(
                update={"razonamiento": d.red(x.razonamiento), "observado": d.red(x.observado)}
            )
            for x in (vista.pasos if vista else [])
        ],
        video=vista.video if vista else None,
        ajustes=ajustes,
        historial=historial,
        opinion=[
            f.model_copy(update={"texto": d.red(f.texto), "cita": d.red(f.cita)})
            for fs in (vista.fricciones.values() if vista else [])
            for f in fs
        ],
        verificaciones=[
            Verificacion(
                titulo=d.red(h.titulo),
                pantalla=h.pantalla,
                esperado=d.red(h.esperado or ""),
                obtenido=d.red(h.obtenido or ""),
            )
            for _, h in hallazgos
            if h.esperado is not None or h.obtenido is not None
        ],
        falla_detalle=falla,
        codigo=codigo,
        lenguaje_codigo=lenguaje,
    )


def registrar_api_casos(app: FastAPI, raiz: Path, cfg: Config | None = None) -> None:
    raiz = Path(raiz)

    def datos(slug: str) -> tuple[_Datos, proyectos.Proyecto]:
        p = proyectos.obtener(slug, raiz)
        if p is None:
            raise HTTPException(404, f"el proyecto {slug!r} no existe")
        secretos = list(cfg._secretos.values()) if cfg else []
        return _Datos(raiz, p, secretos), p

    @app.get("/api/proyectos/{slug}/casos", response_model=ListaCasos)
    def api_casos(slug: str, estado: str = "", q: str = "", prioridad: str = ""):
        filas = datos(slug)[0].filas()
        q = q.strip().lower()
        filas = [
            f
            for f in filas
            if (not prioridad or f.prioridad == prioridad)
            and (
                not q
                or any(q in t.lower() for t in (f.tc, f.nombre, f.caso_de_uso, f.persona.nombre))
            )
        ]
        # los conteos no dependen de la pestaña elegida: son los números de las pestañas
        conteos = {e: sum(f.estado == e for f in filas) for e in ESTADOS}
        filas = [f for f in filas if not estado or f.estado == estado]
        grupos: dict[str, list[CasoFila]] = {}
        for f in filas:
            grupos.setdefault(f.caso_de_uso, []).append(f)
        return ListaCasos(
            conteos=conteos,
            total=sum(conteos.values()),
            grupos=[Grupo(caso_de_uso=k, casos=v) for k, v in grupos.items()],
        )

    @app.get("/api/proyectos/{slug}/casos/{tc}", response_model=DetalleCaso)
    def api_caso(slug: str, tc: str):
        d, p = datos(slug)
        return _detalle_caso(d, p, tc)
