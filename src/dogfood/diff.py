"""Diff de comportamiento entre dos refs (F12.1.T2).

Graba con REA los casos que ya pasaron, una vez contra `base` y otra contra `nueva`, y los
compara paso a paso. REA dice qué pasos y artefactos cambiaron (solo con hashes); el detalle
(requests, texto, consola) se saca de las dos grabaciones y se clasifica aquí.
"""

import base64
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit

from dogfood.almacen import Almacen
from dogfood.dominio import Corrida, Ejecucion, Instancia
from dogfood.objetivos.base import Objetivo
from dogfood.rea import adaptador, escenario, normalizacion

ORDEN = {"cambios": 0, "no_alineado": 1, "sin_cambios": 2}
MAX_TEXTO = 500


@dataclass
class CasoGrabar:
    tc: str
    caso_id: str
    titulo: str
    ejecucion: Ejecucion
    contrasena: str = ""


# --- selección de los casos -------------------------------------------------------------------
def seleccionar(raiz: Path, slug: str, casos: str = "alta") -> tuple[list[CasoGrabar], list[str]]:
    """Los casos elegidos que pasaron en las corridas del proyecto, con su última ejecución.

    `casos`: `alta`, `todos` o una lista de TC (`TC001,TC007`). Devuelve también los TC
    elegidos que no pasaron, para avisarlo.
    """
    from dogfood import proyectos
    from dogfood.panel.api_casos import _Datos

    p = proyectos.obtener(slug, raiz)
    if p is None:
        raise KeyError(f"no existe el proyecto {slug!r}")
    datos = _Datos(raiz, p, [])
    lista = {c.strip().upper() for c in casos.split(",") if c.strip()}
    elegidos: list[CasoGrabar] = []
    omitidos: list[str] = []
    almacen = Almacen(raiz)
    for n, caso_id in enumerate(datos.por_caso, 1):
        fila, cid, _ = datos.fila(n, caso_id)
        quiere = (
            fila.prioridad == "alta" if casos == "alta" else casos == "todos" or fila.tc in lista
        )
        if not quiere:
            continue
        if fila.estado != "paso" or not fila.ejecucion_id:
            omitidos.append(fila.tc)
            continue
        persona = datos.personas.get((cid, fila.persona.id), {})
        elegidos.append(
            CasoGrabar(
                fila.tc,
                caso_id,
                fila.nombre,
                almacen.ejecucion(fila.ejecucion_id),
                persona.get("contrasena", ""),
            )
        )
    return elegidos, omitidos


# --- extracción del detalle de una grabación ------------------------------------------------
class _Texto(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lineas: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        self._ignorar += tag in ("script", "style")

    def handle_endtag(self, tag):
        self._ignorar -= tag in ("script", "style") and self._ignorar > 0

    def handle_data(self, data):
        if not self._ignorar and (t := " ".join(data.split())):
            self.lineas.append(t)


def _normalizar(texto: str, patrones: list[dict]) -> str:
    for p in patrones:
        texto = re.sub(p["regex"], p["reemplazo"], texto)
    return texto


def _artefacto(paso: dict, nombre: str) -> Any:
    a = (paso.get("artifacts") or {}).get(nombre) or {}
    return a.get("value") if a.get("state") == "captured" else None


def _pasos(nr: dict, patrones: list[dict]) -> dict[str, dict]:
    """step_id → acción, estado, texto visible, requests {(método, ruta): estado}, errores, captura."""
    por_indice: dict[int, dict] = {}
    salida: dict[str, dict] = {}
    for s in nr.get("steps", []):
        dom = _artefacto(s, "dom") or {}
        t = _Texto()
        t.feed(dom.get("text", ""))
        shot = _artefacto(s, "screenshot") or {}
        salida[s["step_id"]] = {
            "accion": s.get("action", ""),
            "estado": s.get("status", ""),
            "texto": [_normalizar(x, patrones) for x in t.lineas],
            "red": {},
            "consola": [],
            "captura": shot.get("data_base64"),
        }
        por_indice[s["step_index"]] = salida[s["step_id"]]
    for ev in (nr.get("events") or {}).get("items", []):
        paso = por_indice.get(ev.get("step_index"))
        if paso is None:
            continue
        if ev.get("kind") in ("request", "response"):
            ruta = _normalizar(urlsplit(ev["url"]["url"]).path, patrones)
            # ponytail: si la misma request se repite en un paso gana la última respuesta
            if ev["kind"] == "response":
                paso["red"][(ev["method"], ruta)] = ev.get("status")
            else:
                paso["red"].setdefault((ev["method"], ruta), None)
        elif ev.get("kind") == "console" and ev.get("level") == "error":
            paso["consola"].append(_normalizar(ev.get("text", ""), patrones))
    return salida


def _recortar(lineas: list[str]) -> str:
    return "\n".join(lineas)[:MAX_TEXTO]


def _cambios_red(a: dict, d: dict) -> list[dict]:
    out: list[dict] = []
    for (metodo, ruta), antes in a.items():
        if (metodo, ruta) in d and d[(metodo, ruta)] != antes:
            despues = d[(metodo, ruta)]
            alta = despues is not None and despues >= 400 and not (antes and antes >= 400)
            out.append(_red("estado", "alta" if alta else "media", metodo, ruta, antes, despues))
    perdidas = [k for k in a if k not in d]
    nuevas = [k for k in d if k not in a]
    for p in list(perdidas):
        # misma ruta con otro método, o (si es la única) mismo método con otra ruta
        n = next((n for n in nuevas if n[1] == p[1]), None)
        if n is None and len(perdidas) == 1 == len(nuevas) and nuevas[0][0] == p[0]:
            n = nuevas[0]
        if n is None:
            continue
        perdidas.remove(p)
        nuevas.remove(n)
        tipo = "metodo" if n[1] == p[1] else "ruta"
        out.append(_red(tipo, "media", n[0], n[1], f"{p[0]} {p[1]}", f"{n[0]} {n[1]}"))
    for metodo, ruta in perdidas:
        out.append(_red("request_desaparecida", "media", metodo, ruta, a[(metodo, ruta)], None))
    for metodo, ruta in nuevas:
        estado = d[(metodo, ruta)]
        alta = estado is not None and estado >= 400
        out.append(_red("request_nueva", "alta" if alta else "baja", metodo, ruta, None, estado))
    return out


def _red(subtipo, gravedad, metodo, ruta, antes, despues) -> dict:
    return {
        "tipo": "red",
        "subtipo": subtipo,
        "gravedad": gravedad,
        "metodo": metodo,
        "ruta": ruta,
        "antes": antes,
        "despues": despues,
    }


def _motivo_no_alineado(comp: dict, antes: dict, despues: dict) -> str:
    al = comp.get("alignment") or {}
    partes = []
    if al.get("status") != "aligned":
        partes.append(f"REA no pudo alinear los pasos ({al.get('status', 'sin estado')})")
    if al.get("before_only"):
        partes.append(f"solo en base: {', '.join(map(str, al['before_only']))}")
    if al.get("after_only"):
        partes.append(f"solo en nueva: {', '.join(map(str, al['after_only']))}")
    for f in al.get("failures") or []:
        partes.append(str(f.get("reason") or f.get("message") or f) if isinstance(f, dict) else f)
    for lado, pasos in (("base", antes), ("nueva", despues)):
        malos = [k for k, v in pasos.items() if v["estado"] != "completed"]
        if malos:
            partes.append(f"en {lado} no se completó el paso {', '.join(malos)}")
    return "; ".join(partes)


def comparar_caso(antes: dict, despues: dict, comp: dict, patrones: list[dict]) -> dict:
    """Resultado de un caso: `sin_cambios`, `cambios` o `no_alineado`, con sus pasos cambiados."""
    a, d = _pasos(antes, patrones), _pasos(despues, patrones)
    if motivo := _motivo_no_alineado(comp, a, d):
        return {"resultado": "no_alineado", "motivo": motivo, "pasos": []}
    por_paso = {s["step_id"]: s for s in comp.get("steps", [])}
    pasos = []
    for sid, pa in a.items():
        pd = d[sid]
        cambios = _cambios_red(pa["red"], pd["red"])
        quitado = [x for x in pa["texto"] if x not in pd["texto"]]
        puesto = [x for x in pd["texto"] if x not in pa["texto"]]
        if quitado or puesto:
            cambios.append(
                {
                    "tipo": "texto",
                    "gravedad": "media",
                    "antes": _recortar(quitado),
                    "despues": _recortar(puesto),
                }
            )
        cambios += [
            {"tipo": "consola", "gravedad": "media", "texto": t[:MAX_TEXTO]}
            for t in pd["consola"]
            if t not in pa["consola"]
        ]
        diffs = (por_paso.get(sid) or {}).get("artifact_diffs", [])
        if any(x.get("artifact") == "screenshot" and x.get("status") == "changed" for x in diffs):
            cambios.append(
                {"tipo": "visual", "gravedad": "baja", "detalle": "la captura de pantalla difiere"}
            )
        if cambios:
            pasos.append({"step_id": sid, "accion": pa["accion"], "cambios": cambios})
    return {"resultado": "cambios" if pasos else "sin_cambios", "pasos": pasos}


def _guardar_capturas(destino: Path, tc: str, caso: dict, antes: dict, despues: dict) -> None:
    for paso in caso["pasos"]:
        for lado, nr in (("antes", antes), ("despues", despues)):
            s = next((s for s in nr["steps"] if s["step_id"] == paso["step_id"]), None)
            b64 = (_artefacto(s, "screenshot") or {}).get("data_base64") if s else None
            if not b64:
                continue
            ruta = destino / "capturas" / tc / f"{paso['step_id']}-{lado}.png"
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(base64.b64decode(b64))
            paso.setdefault("capturas", {})[lado] = str(ruta.relative_to(destino))


# --- salida ------------------------------------------------------------------------------------
def resumen_md(d: dict) -> str:
    casos = sorted(d["casos"], key=lambda c: (ORDEN[c["resultado"]], c["tc"]))
    con = sum(c["resultado"] == "cambios" for c in casos)
    out = [
        f"# Diff de comportamiento: {d['proyecto']}",
        "",
        f"`{d['base']}` → `{d['nueva']}` ({d['creado']})",
        "",
        f"{con} de {len(casos)} casos con cambios.",
        "",
    ]
    for c in casos:
        out.append(f"## {c['tc']} — {c['titulo']}: {c['resultado'].replace('_', ' ')}")
        out.append("")
        if c.get("motivo"):
            out += [f"Motivo: {c['motivo']}", ""]
        for p in c["pasos"]:
            out.append(f"- Paso `{p['step_id']}` ({p['accion']})")
            for x in p["cambios"]:
                out.append(f"  - **{x['tipo']}** [{x['gravedad']}]: {_describir(x)}")
        if c["pasos"]:
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def _describir(x: dict) -> str:
    if x["tipo"] == "red":
        if x["subtipo"] == "estado":
            return f"{x['metodo']} {x['ruta']}: {x['antes']} → {x['despues']}"
        if x["subtipo"] in ("metodo", "ruta"):
            return f"cambió el {x['subtipo']}: {x['antes']} → {x['despues']}"
        cosa = "request nueva" if x["subtipo"] == "request_nueva" else "request desaparecida"
        estado = x["despues"] if x["subtipo"] == "request_nueva" else x["antes"]
        return f"{cosa} {x['metodo']} {x['ruta']} ({estado})"
    if x["tipo"] == "texto":
        return f"«{x['antes']}» → «{x['despues']}»"
    if x["tipo"] == "consola":
        return f"error nuevo: {x['texto']}"
    return x.get("detalle", "")


# --- orquestación ------------------------------------------------------------------------------
def _grabar_lado(
    lado: str,
    ref: str,
    *,
    objetivo: Objetivo,
    corrida: Corrida,
    casos: list[CasoGrabar],
    destino: Path,
    rea: ModuleType,
    armar: Callable[..., dict],
) -> dict[str, Path | str]:
    """tc → ruta de su normalized_result, o el motivo (str) si el caso no se pudo grabar."""
    instancia: Instancia = objetivo.preparar(ref, corrida.model_copy(update={"ref": ref}))
    try:
        res: dict[str, Path | str] = {}
        for c in casos:
            esc = armar(c.ejecucion, instancia, contrasena=c.contrasena)
            if not esc.get("actions"):
                res[c.tc] = "; ".join(esc.get("avisos") or ["el caso no tiene pasos que repetir"])
                continue
            try:
                res[c.tc] = rea.grabar(
                    esc,
                    destino / "grabaciones" / lado / c.tc,
                    secretos={escenario.VARIABLE_SECRETO: c.contrasena} if c.contrasena else None,
                )
            except adaptador.ErrorRea as e:
                res[c.tc] = f"no se pudo grabar en {lado}: {e}"
        return res
    finally:
        objetivo.destruir(instancia)


def diff(
    *,
    proyecto: str,
    objetivo: Objetivo,
    base: str,
    nueva: str,
    casos: list[CasoGrabar],
    almacen: Almacen,
    rea: ModuleType = adaptador,
    armar: Callable[..., dict] = escenario.desde_ejecucion,
    ahora: datetime | None = None,
) -> dict:
    """Corre el diff, escribe `<runs>/diff-<id>/` y lo guarda en el almacén."""
    ahora = ahora or datetime.now().astimezone()
    did = f"diff-{ahora:%Y%m%d-%H%M%S}"
    destino = almacen.raiz / did
    destino.mkdir(parents=True, exist_ok=True)
    corrida = Corrida(
        id=did,
        objetivo=objetivo.nombre,
        ref=base,
        commit="",
        semilla=0,
        inicio=ahora,
        estado="en_curso",
        parametros={"proyecto": proyecto},
    )
    comun = {
        "objetivo": objetivo,
        "corrida": corrida,
        "casos": casos,
        "destino": destino,
        "rea": rea,
    }
    grabaciones = {
        "base": _grabar_lado("base", base, armar=armar, **comun),
        "nueva": _grabar_lado("nueva", nueva, armar=armar, **comun),
    }
    patrones = normalizacion.reglas(objetivo)["patrones"]
    secretos = [c.contrasena for c in casos if c.contrasena]
    salida = []
    for c in casos:
        a, n = grabaciones["base"][c.tc], grabaciones["nueva"][c.tc]
        meta = {"tc": c.tc, "caso_id": c.caso_id, "titulo": c.titulo}
        if isinstance(a, str) or isinstance(n, str):
            motivo = a if isinstance(a, str) else n
            salida.append({**meta, "resultado": "no_alineado", "motivo": motivo, "pasos": []})
            continue
        try:
            comp = rea.comparar(a, n, normalizacion.reglas(objetivo))
        except adaptador.ErrorRea as e:
            salida.append({**meta, "resultado": "no_alineado", "motivo": str(e), "pasos": []})
            continue
        ra, rn = json.loads(a.read_text()), json.loads(n.read_text())
        caso = comparar_caso(ra, rn, comp, patrones)
        _guardar_capturas(destino, c.tc, caso, ra, rn)
        salida.append({**meta, **caso})
    resultado = adaptador.redactar_evidencia(
        {
            "id": did,
            "proyecto": proyecto,
            "base": base,
            "nueva": nueva,
            "creado": ahora.isoformat(),
            "casos": salida,
        },
        secretos,
    )
    (destino / "diff.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False))
    (destino / "resumen.md").write_text(resumen_md(resultado))
    # las grabaciones crudas no se conservan: solo el diff y las capturas de lo que cambió
    shutil.rmtree(destino / "grabaciones", ignore_errors=True)
    almacen.guardar_diff(resultado)
    return resultado
