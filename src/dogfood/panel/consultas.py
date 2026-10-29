"""Consultas de solo lectura sobre `runs/dogfood.db` (esquema v2) y las carpetas de corrida."""

import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel

from dogfood.dominio import ContratoRecorrido
from dogfood.objetivos import cargar_objetivo

RESULTADOS = ("aprobado", "fallo", "no_concluyente")
ETIQUETAS = {"aprobado": "aprobado", "fallo": "falló", "no_concluyente": "no concluyente"}
_RES = "COALESCE(e.resultado, CASE WHEN e.exito THEN 'aprobado' ELSE 'fallo' END)"
# Filtro -> expresión SQL; `resultado` y `version` caen a los valores de esquema v1.
_FILTROS = {
    "recorrido": "e.escenario_id",
    "resultado": _RES,
    "version": 'COALESCE(c.version_app, c."commit")',
    "persona": "e.persona_id",
    "driver": "e.driver",
    "motor": "e.motor",
}
_SELECT = f"""
    SELECT e.id, e.corrida_id, c.inicio AS fecha, COALESCE(c.version_app, c."commit") AS version,
           e.persona_id, json_extract(p.json, '$.nombre') AS persona_nombre,
           json_extract(p.json, '$.idioma') AS persona_idioma, e.escenario_id, e.driver, e.motor,
           e.backend, e.modelo, {_RES} AS resultado, e.duracion_s, e.pasos,
           COALESCE(e.tokens_in, 0) + COALESCE(e.tokens_out, 0) AS tokens,
           COALESCE(e.capturas, 0) AS capturas, COALESCE(e.costo_usd, 0) AS costo_usd,
           COALESCE(e.costo_equivalente_usd, 0) AS costo_equivalente_usd
    FROM ejecuciones e JOIN corridas c ON c.id = e.corrida_id
    LEFT JOIN personas p ON p.corrida_id = e.corrida_id AND p.id = e.persona_id
"""


class FilaEjecucion(BaseModel):
    id: str
    corrida_id: str
    fecha: str
    version: str
    persona_id: str
    persona_nombre: str | None
    persona_idioma: str | None
    escenario_id: str
    driver: str
    motor: str
    backend: str
    modelo: str
    resultado: str
    duracion_s: float
    pasos: int
    tokens: int
    capturas: int
    costo_usd: float
    costo_equivalente_usd: float


class ResumenCorridaPanel(BaseModel):
    id: str
    objetivo: str
    ref: str
    version: str
    estado: str
    inicio: str
    fin: str | None
    n_personas: int
    ejecuciones: int
    por_resultado: dict[str, int]
    costo_usd: float
    costo_equivalente_usd: float


class FilaComparacion(BaseModel):
    motor: str
    backend: str
    modelo: str
    ejecuciones: int
    aprobadas: int
    fallidas: int
    no_concluyentes: int
    tasa_aprobacion: float
    tokens: int
    costo_usd: float
    costo_equivalente_usd: float


class Recorrido(BaseModel):
    id: str
    titulo: str
    driver: str
    contrato: ContratoRecorrido | None
    por_resultado: dict[str, int]


def _con(raiz: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"{(Path(raiz) / 'dogfood.db').resolve().as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def ejecuciones(raiz: Path, filtros: dict[str, str] | None = None) -> list[FilaEjecucion]:
    donde, args = [], []
    for k, v in (filtros or {}).items():
        if v and k in _FILTROS:
            donde.append(f"{_FILTROS[k]} = ?")
            args.append(v)
    sql = _SELECT + (" WHERE " + " AND ".join(donde) if donde else "")
    with closing(_con(raiz)) as con:
        return [
            FilaEjecucion(**dict(r))
            for r in con.execute(sql + " ORDER BY c.inicio DESC, e.id", args)
        ]


def opciones_filtro(raiz: Path) -> dict[str, list[tuple[str, str]]]:
    """Valores posibles de cada filtro como `(valor, etiqueta)`."""
    filas = ejecuciones(raiz)
    salida: dict[str, list[tuple[str, str]]] = {}
    for filtro, campo in (
        ("recorrido", "escenario_id"),
        ("resultado", "resultado"),
        ("version", "version"),
        ("driver", "driver"),
        ("motor", "motor"),
    ):
        valores = sorted({getattr(f, campo) for f in filas})
        salida[filtro] = [(v, ETIQUETAS.get(v, v)) for v in valores]
    personas = {f.persona_id: f for f in filas}
    salida["persona"] = sorted(
        (i, f"{f.persona_nombre or i} ({f.persona_idioma or '?'})") for i, f in personas.items()
    )
    return salida


def corrida(raiz: Path, corrida_id: str) -> ResumenCorridaPanel | None:
    with closing(_con(raiz)) as con:
        c = con.execute(
            'SELECT id, objetivo, ref, COALESCE(version_app, "commit") AS version, estado, inicio,'
            " fin, n_personas FROM corridas WHERE id = ?",
            (corrida_id,),
        ).fetchone()
    if c is None:
        return None
    filas = [f for f in ejecuciones(raiz) if f.corrida_id == corrida_id]
    return ResumenCorridaPanel(
        **dict(c),
        ejecuciones=len(filas),
        por_resultado={r: sum(f.resultado == r for f in filas) for r in RESULTADOS},
        costo_usd=sum(f.costo_usd for f in filas),
        costo_equivalente_usd=sum(f.costo_equivalente_usd for f in filas),
    )


def comparacion_motores(raiz: Path, corrida_id: str) -> list[FilaComparacion]:
    grupos: dict[tuple[str, str, str], list[FilaEjecucion]] = {}
    for f in ejecuciones(raiz):
        if f.corrida_id == corrida_id:
            grupos.setdefault((f.motor, f.backend, f.modelo), []).append(f)
    salida = []
    for (motor, backend, modelo), fs in sorted(grupos.items()):
        n = len(fs)
        cuenta = {r: sum(f.resultado == r for f in fs) for r in RESULTADOS}
        salida.append(
            FilaComparacion(
                motor=motor,
                backend=backend,
                modelo=modelo,
                ejecuciones=n,
                aprobadas=cuenta["aprobado"],
                fallidas=cuenta["fallo"],
                no_concluyentes=cuenta["no_concluyente"],
                tasa_aprobacion=cuenta["aprobado"] / n,
                tokens=sum(f.tokens for f in fs) // n,
                costo_usd=sum(f.costo_usd for f in fs) / n,
                costo_equivalente_usd=sum(f.costo_equivalente_usd for f in fs) / n,
            )
        )
    return salida


def recorridos(raiz: Path, objetivo: str = "predicts") -> list[Recorrido]:
    cuenta: dict[str, dict[str, int]] = {}
    for f in ejecuciones(raiz):
        por = cuenta.setdefault(f.escenario_id, dict.fromkeys(RESULTADOS, 0))
        por[f.resultado] += 1
    return [
        Recorrido(
            id=e.id,
            titulo=e.titulo,
            driver=e.driver,
            contrato=e.contrato,
            por_resultado=cuenta.get(e.id, dict.fromkeys(RESULTADOS, 0)),
        )
        for e in cargar_objetivo(objetivo).escenarios()
    ]
