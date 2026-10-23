"""Reporte de opinión de usuarios (FR-20): `reporte.md` y `reporte.html` en español.

Los conteos salen de los datos de entrada; el LLM solo agrupa fricciones (rol `dedupe`) y
redacta párrafos (rol `redactor`) a partir de datos ya agregados. Todo texto pasa por `redactar`.
"""

import json
import os
import subprocess
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from dogfood.config import Config
from dogfood.dominio import Corrida, Ejecucion, Gravedad, Hallazgo, Instancia, Persona, UsoLlm
from dogfood.llm import completar_json
from dogfood.reporte import consistencia, modelos
from dogfood.reporte.redactar import REDACTADO, redactar, verificar_limpio

CATEGORIAS = ("no se entendió", "frustró", "sobró")
_SIN_REDACTAR = {"captura", "capturas", "ruta"}  # rutas relativas: no son texto de usuario

Completar = Callable[..., Awaitable[Any]]


class GrupoFriccion(BaseModel):
    categoria: str
    resumen: str
    indices: list[int]


class Agrupacion(BaseModel):
    grupos: list[GrupoFriccion]


class Redaccion(BaseModel):
    resumen: str = ""
    usuarios: str = ""
    pantallas: dict[str, str] = {}


class UsoIA(BaseModel):
    decisiones_jev: int = 0
    plantillas: int = 0


def contar_uso_ia(instancia: Instancia) -> UsoIA:
    """Cuenta filas de `decisiones_jev` y `plantillas_mensaje` en el Postgres de la instancia.

    Hay que llamarla antes de destruir la instancia (D12).
    """

    def contar(tabla: str) -> int:
        cmd = ["docker", "compose", "-p", instancia.proyecto_compose, "exec", "-T", "postgres"]
        cmd += ["psql", "-U", "predicts", "-d", "predicts", "-tAc", f"SELECT count(*) FROM {tabla}"]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(r.stdout.strip())

    return UsoIA(decisiones_jev=contar("decisiones_jev"), plantillas=contar("plantillas_mensaje"))


def _costo_unitario() -> dict[str, float]:
    """`costo_unitario_predicts: {decision_jev, plantilla}` (USD) en dogfood.yaml; 0 si falta."""
    ruta = Path("dogfood.yaml")
    cfg = (yaml.safe_load(ruta.read_text()) if ruta.exists() else None) or {}
    return cfg.get("costo_unitario_predicts") or {}


def _limpiar(obj: Any, secretos: list[str]) -> Any:
    if isinstance(obj, str):
        return redactar(obj, secretos)
    if isinstance(obj, list):
        return [_limpiar(x, secretos) for x in obj]
    if isinstance(obj, dict):
        return {k: v if k in _SIN_REDACTAR else _limpiar(v, secretos) for k, v in obj.items()}
    return obj


def _rel(ruta: Path | None, destino: Path) -> str | None:
    if ruta is None:
        return None
    return Path(os.path.relpath(Path(ruta).resolve(), destino.resolve())).as_posix()


async def _agrupar(
    pantalla: str, fric: list[tuple[str, Any]], completar: Completar
) -> list[GrupoFriccion]:
    """Agrupa con el rol `dedupe`; lo no asignado (o si el LLM falla) queda como grupos sueltos."""
    textos = [{"i": i, "texto": f.texto} for i, (_, f) in enumerate(fric)]
    prompt = (
        f"Agrupa las fricciones de usuarios de la pantalla «{pantalla}» que dicen lo mismo. "
        f"Categorías: {', '.join(CATEGORIAS)}. Responde con `indices` de la lista.\n"
        + json.dumps(textos, ensure_ascii=False)
    )
    try:
        grupos = (await completar("dedupe", prompt, Agrupacion)).grupos
    except Exception:  # noqa: BLE001 - el reporte sale igual, sin agrupar
        grupos = []
    vistos: set[int] = set()
    salida = []
    for g in grupos:
        idx = [i for i in dict.fromkeys(g.indices) if 0 <= i < len(fric) and i not in vistos]
        vistos.update(idx)
        if idx:
            cat = g.categoria if g.categoria in CATEGORIAS else "frustró"
            salida.append(GrupoFriccion(categoria=cat, resumen=g.resumen, indices=idx))
    salida += [
        GrupoFriccion(categoria="frustró", resumen=fric[i][1].texto, indices=[i])
        for i in range(len(fric))
        if i not in vistos
    ]
    return salida


async def _pantallas(
    ejecs: list[Ejecucion], destino: Path, completar: Completar
) -> list[dict[str, Any]]:
    por: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    funciono: dict[str, set[str]] = defaultdict(set)
    for e in ejecs:
        for f in e.fricciones:
            por[f.pantalla].append((e.persona_id, f))
        if e.exito:
            for p in e.pasos:
                funciono[p.pantalla].add(e.persona_id)
    filas = []
    for pantalla in sorted(por.keys() | funciono.keys()):
        fric = por.get(pantalla, [])
        grupos = []
        for g in await _agrupar(pantalla, fric, completar) if fric else []:
            miembros = [fric[i] for i in g.indices]
            capt = next((_rel(f.captura, destino) for _, f in miembros if f.captura), None)
            grupos.append(
                {
                    "categoria": g.categoria,
                    "resumen": g.resumen,
                    "personas": len({p for p, _ in miembros}),
                    "citas": list(dict.fromkeys(f.cita or f.texto for _, f in miembros))[:3],
                    "captura": capt,
                }
            )
        filas.append(
            {
                "pantalla": pantalla,
                "fricciones": len(fric),
                "personas_con_friccion": len({p for p, _ in fric}),
                "personas_exito": len(funciono.get(pantalla, ())),
                "grupos": grupos,
            }
        )
    return filas


def _segmento(ejecs, personas, clave: Callable[[Persona], str]) -> list[dict[str, Any]]:
    por_id = {p.id: p for p in personas}
    acc: dict[str, list[Ejecucion]] = defaultdict(list)
    for e in ejecs:
        if e.persona_id in por_id:
            acc[clave(por_id[e.persona_id])].append(e)
    return [
        {
            "grupo": g,
            "personas": len({e.persona_id for e in es}),
            "ejecuciones": len(es),
            "exito_pct": round(100 * sum(e.exito for e in es) / len(es)),
            "fricciones": sum(len(e.fricciones) for e in es),
        }
        for g, es in sorted(acc.items())
    ]


def _hallazgo(h: Hallazgo, destino: Path, issues: dict[str, str]) -> dict[str, Any]:
    return {
        "titulo": h.titulo,
        "gravedad": h.gravedad.value,
        "tipo": h.tipo.value,
        "pantalla": h.pantalla,
        "issue": issues.get(h.huella),
        "capturas": [
            _rel(ev.ruta, destino) for ev in h.evidencia if ev.tipo == "captura" and ev.ruta
        ],
    }


async def generar(
    corrida: Corrida,
    ejecuciones: list[Ejecucion],
    hallazgos: list[Hallazgo],
    personas: list[Persona],
    *,
    destino: Path | None = None,
    cfg: Config | None = None,
    costo_dogfood_usd: float = 0.0,
    uso_ia: UsoIA | None = None,
    usos: list[UsoLlm] | None = None,
    issues: dict[str, str] | None = None,
    bloqueados: set[str] | None = None,
    completar: Completar = completar_json,
) -> tuple[Path, Path]:
    """Escribe `reporte.md` y `reporte.html` en `destino` (por defecto `runs/<corrida.id>`).

    `issues` mapea huella → URL del issue; `bloqueados` son las huellas que `publicar` no pudo
    publicar por redacción; `uso_ia` viene de `contar_uso_ia` (tomado antes de destruir la instancia).
    """
    destino = Path(destino or Path("runs") / corrida.id)
    destino.mkdir(parents=True, exist_ok=True)
    issues, bloqueados = issues or {}, bloqueados or set()
    secretos = [p.contrasena for p in personas]
    umbral = Gravedad(cfg.umbral_publicar) if cfg else Gravedad.media

    escenarios = defaultdict(list)
    for e in ejecuciones:
        escenarios[e.escenario_id].append(e)
    unit = _costo_unitario()
    uso = uso_ia or UsoIA()
    costo_predicts = uso.decisiones_jev * unit.get("decision_jev", 0.0) + uso.plantillas * unit.get(
        "plantilla", 0.0
    )

    def pub(h: Hallazgo) -> bool:
        return not h.solo_reporte and h.gravedad >= umbral and h.huella not in bloqueados

    datos = {
        "corrida": {
            "id": corrida.id,
            "objetivo": corrida.objetivo,
            "ref": corrida.ref,
            "commit": corrida.commit,
        },
        "n_personas": len(personas),
        "escenarios": [
            {
                "id": s,
                "ejecuciones": len(es),
                "exito_pct": round(100 * sum(e.exito for e in es) / len(es)),
            }
            for s, es in sorted(escenarios.items())
        ],
        "por_gravedad": dict(Counter(h.gravedad.value for h in hallazgos)),
        "por_tipo": dict(Counter(h.tipo.value for h in hallazgos)),
        "hallazgos": [_hallazgo(h, destino, issues) for h in hallazgos if h.huella in issues],
        "duracion_min": round(sum(e.duracion_s for e in ejecuciones) / 60, 1),
        "costo_dogfood_usd": round(costo_dogfood_usd, 4),
        "uso_ia": uso.model_dump(),
        "costo_predicts_usd": round(costo_predicts, 4),
        "pantallas": await _pantallas(ejecuciones, destino, completar),
        "por_destreza": _segmento(
            ejecuciones, personas, lambda p: "baja (1-2)" if p.destreza <= 2 else "alta (3-5)"
        ),
        "por_idioma": _segmento(ejecuciones, personas, lambda p: p.idioma.value),
        "por_rubro": _segmento(ejecuciones, personas, lambda p: p.rubro),
        "solo_reporte": [_hallazgo(h, destino, issues) for h in hallazgos if h.solo_reporte],
        "bajo_umbral": [
            _hallazgo(h, destino, issues)
            for h in hallazgos
            if not h.solo_reporte and h.gravedad < umbral
        ],
        "bloqueados": [_hallazgo(h, destino, issues) for h in hallazgos if h.huella in bloqueados],
        "umbral": umbral.value,
        "modelos": modelos.tabla(ejecuciones, hallazgos, usos or []),
        "consistencia": consistencia.seccion(ejecuciones, hallazgos),
    }
    datos = _limpiar(datos, secretos)

    # el LLM solo redacta párrafos a partir de datos ya agregados; los conteos no pasan por él
    try:
        prompt = (
            "Redacta en español, sin inventar cifras, los párrafos de un reporte de opinión de "
            "usuarios a partir de estos datos agregados: `resumen`, `usuarios` y `pantallas` "
            "(pantalla → párrafo).\n" + json.dumps(datos, ensure_ascii=False, default=str)
        )
        redaccion = await completar("redactor", prompt, Redaccion)
    except Exception:  # noqa: BLE001 - sin párrafos el reporte sigue siendo útil
        redaccion = Redaccion()
    datos["redaccion"] = _limpiar(redaccion.model_dump(), secretos)

    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "plantillas"),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )
    ruta_md, ruta_html = destino / "reporte.md", destino / "reporte.html"
    for ruta, plantilla in ((ruta_md, "reporte.md.j2"), (ruta_html, "reporte.html.j2")):
        texto = env.get_template(plantilla).render(**datos)
        # última barrera: lo que aún parezca secreto se tapa en el archivo final
        for resto in sorted(set(verificar_limpio(texto)), key=len, reverse=True):
            texto = texto.replace(resto, REDACTADO)
        ruta.write_text(texto, encoding="utf-8")
    return ruta_md, ruta_html
