"""Sección «Consistencia» (FR-repeat, NFR-8): tasa de éxito con Wilson 95 %, desvío de pasos e inestables."""

from collections import defaultdict
from statistics import pstdev

from dogfood.dominio import Ejecucion, Evidencia, Gravedad, Hallazgo

Z = 1.96
_BAJA = {
    Gravedad.critica: Gravedad.alta,
    Gravedad.alta: Gravedad.media,
    Gravedad.media: Gravedad.baja,
}


def wilson(exitos: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = exitos / n
    den = 1 + Z**2 / n
    centro = (p + Z**2 / (2 * n)) / den
    mitad = Z * ((p * (1 - p) / n + Z**2 / (4 * n**2)) ** 0.5) / den
    return max(0.0, centro - mitad), min(1.0, centro + mitad)


def _apariciones(
    h: Hallazgo, por_id: dict[str, Ejecucion], n_de: dict[str, int]
) -> tuple[str, int]:
    e = por_id.get(h.ejecucion_id or "")
    if not e:
        return "", 0
    # ponytail: la deduplicación solo conserva la primera ejecución; se asume una aparición por ocurrencia
    return e.escenario_id, min(h.ocurrencias, n_de[e.escenario_id])


def marcar_inestables(hallazgos: list[Hallazgo], ejecuciones: list[Ejecucion]) -> None:
    """Los hallazgos presentes en menos de la mitad de las repeticiones: evidencia `inestable`, un nivel menos."""
    por_id = {e.id: e for e in ejecuciones}
    n_de: dict[str, int] = defaultdict(int)
    for e in ejecuciones:
        n_de[e.escenario_id] += 1
    for h in hallazgos:
        esc, k = _apariciones(h, por_id, n_de)
        if esc and 2 * k < n_de[esc] and not esta_marcado(h):
            h.evidencia.append(
                Evidencia(tipo="texto", extracto=f"inestable: {k} de {n_de[esc]} repeticiones")
            )
            h.gravedad = _BAJA.get(h.gravedad, h.gravedad)


def esta_marcado(h: Hallazgo) -> bool:
    return any(ev.tipo == "texto" and ev.extracto.startswith("inestable") for ev in h.evidencia)


def _fila(es: list[Ejecucion], hallazgos: list[Hallazgo], por_id, n_de) -> dict:
    n, ok = len(es), sum(e.exito for e in es)
    bajo, alto = wilson(ok, n)
    ids = {e.id for e in es}
    todas = algunas = 0
    for h in hallazgos:
        if h.ejecucion_id in ids:
            if _apariciones(h, por_id, n_de)[1] >= n:
                todas += 1
            else:
                algunas += 1
    return {
        "ejecuciones": n,
        "exitos": ok,
        "tasa": round(ok / n, 2),
        "wilson_bajo": round(bajo, 2),
        "wilson_alto": round(alto, 2),
        "desvio_pasos": round(pstdev([len(e.pasos) for e in es]), 2),
        "en_todas": todas,
        "inestables": algunas,
    }


def seccion(ejecuciones: list[Ejecucion], hallazgos: list[Hallazgo]) -> list[dict]:
    """Una fila por escenario, con `por_modelo` si hay más de un modelo."""
    por_id = {e.id: e for e in ejecuciones}
    n_de: dict[str, int] = defaultdict(int)
    por: dict[str, list[Ejecucion]] = defaultdict(list)
    for e in ejecuciones:
        n_de[e.escenario_id] += 1
        por[e.escenario_id].append(e)
    filas = []
    for s, es in sorted(por.items()):
        fila = {"escenario": s, **_fila(es, hallazgos, por_id, n_de)}
        modelos = sorted({e.modelo for e in es})
        fila["por_modelo"] = (
            [
                {"modelo": m, **_fila([e for e in es if e.modelo == m], hallazgos, por_id, n_de)}
                for m in modelos
            ]
            if len(modelos) > 1
            else []
        )
        filas.append(fila)
    return filas
