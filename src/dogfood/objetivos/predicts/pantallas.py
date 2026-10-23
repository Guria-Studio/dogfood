"""Nombres estables de pantalla, según los archivos de `web/src/routes/` de predicts.

`mensajes`, `productos` y `exportar` son pestañas dentro de resultados, no rutas: sin ruta propia
caen en `resultados`.
"""

import re
from urllib.parse import urlparse

_RUTAS = [
    (r"/login", "login"),
    (r"/registro", "registro"),
    (r"/recuperar", "recuperar"),
    (r"/restablecer", "restablecer"),
    (r"/inicio", "inicio"),
    (r"/proyectos", "proyectos"),
    (r"/proyectos/[^/]+", "proyectos"),
    (r"/proyectos/[^/]+/datasets/nuevo", "subir"),
    (r"/datasets/[^/]+/mapeo", "mapeo"),
    (r"/datasets/[^/]+/calidad", "calidad"),
    (r"/datasets/[^/]+/agente", "agente"),
    (r"/datasets/[^/]+/analisis/nuevo", "analisis"),
    (r"/analisis/[^/]+/progreso", "analisis"),
    (r"/analisis/[^/]+", "resultados"),
    (r"/analisis/[^/]+/universo", "universo"),
    (r"/demo", "demo"),
]


def pantalla(url: str) -> str:
    ruta = urlparse(url).path.rstrip("/") or "/"
    return next((n for patron, n in _RUTAS if re.fullmatch(patron, ruta)), "otra")
