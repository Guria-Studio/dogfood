from importlib import import_module

from dogfood.objetivos.base import Objetivo

OBJETIVOS = {
    "predicts": "dogfood.objetivos.predicts:PredictsObjetivo",
    "android": "dogfood.objetivos.android:AndroidObjetivo",
    "ios": "dogfood.objetivos.ios:IosObjetivo",
    "flutter_web": "dogfood.objetivos.flutter_web:FlutterWebObjetivo",
    "web": "dogfood.objetivos.web:WebObjetivo",
}


def cargar_objetivo(nombre: str, proyecto=None, raiz=None) -> Objetivo:
    """Con un `Proyecto`, los objetivos que se configuran desde él (`desde_proyecto`) lo reciben."""
    if nombre not in OBJETIVOS:
        validos = ", ".join(sorted(OBJETIVOS))
        raise ValueError(f"objetivo desconocido: {nombre!r}. Válidos: {validos}")
    modulo, clase = OBJETIVOS[nombre].split(":")
    cls = getattr(import_module(modulo), clase)
    if proyecto is not None and hasattr(cls, "desde_proyecto"):
        return cls.desde_proyecto(proyecto, **({"raiz": raiz} if raiz else {}))
    return cls()
