"""Reglas de normalización para que el diff de REA no salga lleno de ruido.

REA solo acepta reglas literales (`match` exacto → `replacement`), así que las reglas de dogfood
son patrones y `politica` los expande con los valores que aparecen en las dos grabaciones.
"""

import re
from typing import Any

from dogfood.rea.adaptador import intacto

ARTEFACTOS = ["action_state", "dom", "accessibility", "url", "history", "storage", "events"]

PATRONES = [
    {"id": "jwt", "regex": r"\beyJ[\w-]+\.[\w-]+\.[\w-]+", "reemplazo": "«token»"},
    {
        "id": "uuid",
        "regex": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "reemplazo": "«uuid»",
    },
    # hex o base64 de 24+ caracteres con al menos un dígito: tokens, sesiones, hashes
    {
        "id": "token",
        "regex": r"(?<![\w+-])(?=[A-Za-z0-9+_-]*\d)[A-Za-z0-9+_-]{24,}={0,2}",
        "reemplazo": "«token»",
    },
    {
        "id": "fecha_iso",
        "regex": r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?",
        "reemplazo": "«fecha»",
    },
    {"id": "fecha", "regex": r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "reemplazo": "«fecha»"},
    {"id": "email", "regex": r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "reemplazo": "«email»"},
    # ponytail: el literal "/12" también calza dentro de "/123"; se aplican los más largos primero
    {"id": "id_ruta", "regex": r"/\d+(?=[/?#]|$)", "reemplazo": "/«id»"},
]


def reglas(objetivo: Any = None) -> dict:
    """Las reglas por defecto más las del objetivo (`reglas_diff()`, opcional)."""
    extra = objetivo.reglas_diff() if hasattr(objetivo, "reglas_diff") else []
    return {"patrones": [*PATRONES, *extra]}


def _cadenas(obj: Any, clave: str = ""):
    if isinstance(obj, str):
        if not intacto(clave, obj):
            yield obj
    elif isinstance(obj, list):
        for v in obj:
            yield from _cadenas(v, clave)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _cadenas(v, k)


def politica(reglas: dict, *grabaciones: dict) -> dict:
    """Política literal de REA (`{"rules": [...]}`) con cada valor que calzó algún patrón."""
    textos = [s for g in grabaciones for s in _cadenas(g)]
    vistos: dict[str, dict] = {}
    for p in reglas.get("patrones", []):
        rx = re.compile(p["regex"])
        for t in textos:
            for m in rx.finditer(t):
                vistos.setdefault(m.group(0), p)
    rules = [
        {
            "rule_id": f"{p['id']}-{i}",
            "artifacts": p.get("artefactos", ARTEFACTOS),
            "match": valor,
            "replacement": p["reemplazo"],
        }
        for i, (valor, p) in enumerate(sorted(vistos.items(), key=lambda kv: -len(kv[0])))
    ]
    return {"rules": rules}
