"""Auditoría de aislamiento entre empresas en predicts (FR-14).

Con el cliente de una empresa B se intenta leer (y, solo contra un proyecto de prueba, mutar) los
recursos de otra empresa A, enumerando las rutas con parámetro de ruta del OpenAPI de la instancia.
Cualquier respuesta que no sea 401/403/404 y traiga datos de A es un fallo de aislamiento crítico.
"""

import re
from typing import Any

import httpx

from dogfood.dominio import (
    ContextoDeteccion,
    Evidencia,
    Gravedad,
    Hallazgo,
    TipoHallazgo,
)

# Rutas GET que el spec exige probar aunque el OpenAPI no las liste (exportación y stream SSE).
EXTRA_GET = ("/api/analisis/{id}/exportar", "/api/trabajos/{id}/eventos")
# Métodos destructivos: solo se disparan contra el proyecto de auditoría, nunca contra datos en uso.
METODOS_MUTAN = ("PATCH", "DELETE")
# Estados que no revelan datos de A: no son hallazgo.
SIN_DATOS = (401, 403, 404)
_PARAM = re.compile(r"\{[^}]+\}")


def verificar(ctx: ContextoDeteccion) -> list[Hallazgo]:
    empresas = _empresas_con_datos(ctx)
    if len(empresas) < 2:
        return [_no_ejecutada(ctx)]

    (_, cli_a, base_a), (_, cli_b, _) = empresas[0], empresas[1]

    rutas = _rutas_con_parametro(cli_a)
    colecciones = {c for _, _, cols in rutas for c in cols}
    ids_a = _ids_planas(cli_a, base_a, colecciones)
    ids_auditoria = _proyecto_de_auditoria(cli_a)

    hallazgos: list[Hallazgo] = []
    for metodo, plantilla, cols in rutas:
        pool = ids_auditoria if metodo in METODOS_MUTAN else ids_a
        concreto = _sustituir(plantilla, cols, pool)
        if concreto is None:  # falta un id seguro para esa ruta: no se dispara
            continue
        status, datos, extracto = _probar(cli_b, metodo, concreto, plantilla.endswith("/eventos"))
        if status in SIN_DATOS or status >= 500 or not datos:
            continue
        hallazgos.append(_hallazgo_fuga(ctx, metodo, plantilla, status, extracto))
    return hallazgos


def _empresas_con_datos(ctx: ContextoDeteccion) -> list[tuple[str, Any, dict[str, str]]]:
    """Una entrada por empresa distinta (con ejecución) que tenga proyecto, dataset y análisis."""
    vistas: list[tuple[str, Any, dict[str, str]]] = []
    seen: set[str] = set()
    for e in ctx.ejecuciones:
        emp = e.empresa_id
        if not emp or emp in seen:
            continue
        seen.add(emp)
        cli = ctx.cliente_api(e.persona_id)
        base = _ids_base(cli)
        if base is not None:
            vistas.append((emp, cli, base))
    return vistas


def _ids_base(cli: Any) -> dict[str, str] | None:
    """proyecto/dataset/análisis de la empresa, o None si le falta alguno."""
    proyectos = cli.proyectos()
    if not proyectos:
        return None
    pid = str(proyectos[0]["id"])
    datasets = cli.datasets(pid)
    if not datasets:
        return None
    did = str(datasets[0]["id"])
    analisis = cli.analisis_de(did)
    if not analisis:
        return None
    return {"proyectos": pid, "datasets": did, "analisis": str(analisis[0]["id"])}


def _ids_planas(cli: Any, base: dict[str, str], colecciones: set[str]) -> dict[str, str]:
    """Añade a los ids base un id por cada colección plana del OpenAPI (plantillas, trabajos, …)."""
    ids = dict(base)
    for col in colecciones - ids.keys():
        r = cli._http.request(
            "GET", f"/api/{col}"
        )  # ponytail: usa la sesión ya autenticada del cliente
        if r.status_code != 200:
            continue
        cuerpo = _json(r)
        item = cuerpo[0] if isinstance(cuerpo, list) and cuerpo else None
        if isinstance(item, dict) and "id" in item:
            ids[col] = str(item["id"])
    return ids


def _proyecto_de_auditoria(cli: Any) -> dict[str, str]:
    """Crea un proyecto desechable de A; los métodos destructivos solo tocan estos ids."""
    r = cli._http.request("POST", "/api/proyectos", json={"nombre": "auditoria-aislamiento"})
    if r.status_code in (200, 201):
        cuerpo = _json(r)
        if isinstance(cuerpo, dict) and "id" in cuerpo:
            return {"proyectos": str(cuerpo["id"])}
    return {}


def _rutas_con_parametro(cli: Any) -> list[tuple[str, str, list[str]]]:
    """(método, plantilla, colecciones) de cada ruta GET/PATCH/DELETE con parámetro de ruta."""
    r = cli._http.request("GET", "/openapi.json")
    paths = _json(r).get("paths", {}) if r.status_code == 200 else {}
    rutas: list[tuple[str, str, list[str]]] = []
    vistas: set[tuple[str, str]] = set()
    for plantilla in list(paths) + list(EXTRA_GET):
        cols = _colecciones(plantilla)
        if not cols:
            continue
        metodos = [m.upper() for m in paths.get(plantilla, {})] or ["GET"]
        for metodo in metodos:
            if metodo not in ("GET", *METODOS_MUTAN) or (metodo, plantilla) in vistas:
                continue
            vistas.add((metodo, plantilla))
            rutas.append((metodo, plantilla, cols))
    return rutas


def _colecciones(plantilla: str) -> list[str]:
    """Para cada `{param}`, el segmento que lo precede (la colección del recurso)."""
    segs = plantilla.strip("/").split("/")
    return [segs[i - 1] for i, s in enumerate(segs) if _PARAM.fullmatch(s) and i > 0]


def _sustituir(plantilla: str, cols: list[str], pool: dict[str, str]) -> str | None:
    """Sustituye cada `{param}` por el id de A de su colección; None si falta alguno en el pool."""
    faltan = [c for c in cols if c not in pool]
    if faltan:
        return None
    it = iter(cols)
    return _PARAM.sub(lambda _: pool[next(it)], plantilla)


def _probar(cli: Any, metodo: str, ruta: str, es_sse: bool) -> tuple[int, bool, str]:
    """Dispara la petición con B. Devuelve (status, trajo_datos, extracto redactado)."""
    if es_sse:
        with cli._http.stream("GET", ruta, timeout=5) as r:
            if r.status_code in SIN_DATOS or r.status_code >= 500:
                return r.status_code, False, ""
            primer = next((ln for ln in r.iter_lines() if ln.strip()), "")
            return r.status_code, bool(primer), "primer evento SSE (redactado)"
    r = cli._http.request(metodo, ruta, timeout=10)
    if r.status_code in SIN_DATOS or r.status_code >= 500:
        return r.status_code, False, ""
    cuerpo = _json(r)
    return r.status_code, bool(cuerpo), _redactar(cuerpo)


def _redactar(cuerpo: Any) -> str:
    """Extracto que prueba la fuga sin exponer valores de A."""
    if isinstance(cuerpo, dict):
        return "claves: " + ", ".join(sorted(cuerpo)[:10])
    if isinstance(cuerpo, list):
        return f"lista de {len(cuerpo)} elementos"
    return f"{len(str(cuerpo))} bytes de texto"


def _json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError:
        return r.text


def _hallazgo_fuga(
    ctx: ContextoDeteccion, metodo: str, plantilla: str, status: int, extracto: str
) -> Hallazgo:
    firma = f"{metodo} {plantilla}"
    h = Hallazgo(
        tipo=TipoHallazgo.aislamiento,
        gravedad=Gravedad.critica,
        pantalla="aislamiento",
        titulo=f"Empresa B accede a recursos de A: {firma}",
        descripcion=(
            f"Con la sesión de otra empresa, {metodo} {plantilla} devolvió {status} con datos de A. "
            "Fallo de aislamiento entre empresas."
        ),
        evidencia=[Evidencia(tipo="red", extracto=f"{status} · {extracto}")],
        obtenido=str(status),
        esperado="403 o 404",
        semilla=ctx.corrida.semilla,
        commit=ctx.instancia.commit,
    )
    h.huella = h.calcular_huella(firma)
    return h


def _no_ejecutada(ctx: ContextoDeteccion) -> Hallazgo:
    return Hallazgo(
        tipo=TipoHallazgo.regla,
        gravedad=Gravedad.baja,
        pantalla="aislamiento",
        titulo="auditoría de aislamiento no ejecutada",
        descripcion="Hacen falta al menos dos empresas con proyecto, dataset y análisis.",
        semilla=ctx.corrida.semilla,
        commit=ctx.instancia.commit,
    )
