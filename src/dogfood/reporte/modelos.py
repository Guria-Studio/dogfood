"""Tabla comparativa por modelo de persona para la sección «Modelos» del reporte."""

from collections import defaultdict

from dogfood.dominio import Ejecucion, Hallazgo, UsoLlm


def tabla(
    ejecuciones: list[Ejecucion], hallazgos: list[Hallazgo], usos: list[UsoLlm]
) -> list[dict]:
    por: dict[str, list[Ejecucion]] = defaultdict(list)
    for e in ejecuciones:
        por[e.modelo].append(e)
    modelo_de = {e.id: e.modelo for e in ejecuciones}
    # ponytail: un hallazgo deduplicado solo conserva su primera ejecución; si hace falta, guardar todas
    halló: dict[str, set[str]] = defaultdict(set)
    for h in hallazgos:
        if h.ejecucion_id in modelo_de:
            halló[h.huella].add(modelo_de[h.ejecucion_id])
    tokens: dict[str, int] = defaultdict(int)
    costo: dict[str, float] = defaultdict(float)
    for u in usos:  # solo el rol persona: el juez es común a todos
        if u.rol == "persona":
            tokens[u.modelo] += u.tokens_in + u.tokens_out
            costo[u.modelo] += u.costo_usd
    filas = []
    for m, es in sorted(por.items()):
        n = len(es)
        filas.append(
            {
                "modelo": m,
                "ejecuciones": n,
                "exito_pct": round(100 * sum(e.exito for e in es) / n),
                "pasos_prom": round(sum(len(e.pasos) for e in es) / n, 1),
                "fricciones_por_ejecucion": round(sum(len(e.fricciones) for e in es) / n, 2),
                "hallazgos_unicos": sum(1 for ms in halló.values() if ms == {m}),
                "tokens_por_ejecucion": round(tokens[m] / n),
                "costo_por_ejecucion_usd": round(costo[m] / n, 4),
            }
        )
    return filas
