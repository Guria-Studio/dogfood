from importlib import import_module

from dogfood.objetivos.base import Objetivo

OBJETIVOS = {
    "predicts": "dogfood.objetivos.predicts:PredictsObjetivo",
    "android": "dogfood.objetivos.android:AndroidObjetivo",
}


def cargar_objetivo(nombre: str) -> Objetivo:
    if nombre not in OBJETIVOS:
        validos = ", ".join(sorted(OBJETIVOS))
        raise ValueError(f"objetivo desconocido: {nombre!r}. Válidos: {validos}")
    modulo, clase = OBJETIVOS[nombre].split(":")
    return getattr(import_module(modulo), clase)()
