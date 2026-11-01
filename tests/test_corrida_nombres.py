"""Regresión: `correr` importaba localmente otro `cliente_para` (el de predicts) y sombreaba al de
`dogfood.llm`, así que `llm_de` fallaba con NameError en una corrida real (sin `op.llm`)."""

import ast
from pathlib import Path

from dogfood import corrida


def _nombres_locales(func: ast.AST) -> set[str]:
    nombres = set()
    for nodo in ast.walk(func):
        if isinstance(nodo, ast.ImportFrom | ast.Import):
            nombres |= {a.asname or a.name.split(".")[0] for a in nodo.names}
    return nombres


def test_correr_no_sombrea_cliente_para_de_llm():
    arbol = ast.parse(Path(corrida.__file__).read_text())
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.AsyncFunctionDef | ast.FunctionDef) and nodo.name == "correr":
            assert "cliente_para" not in _nombres_locales(nodo)
            return
    raise AssertionError("no encontré correr()")
