from collections.abc import Callable

from dogfood.deteccion import flutter, friccion, objetivo, tecnicos
from dogfood.dominio import ContextoDeteccion, Gravedad, Hallazgo, TipoHallazgo

DETECTORES: list[Callable[[ContextoDeteccion], list[Hallazgo]]] = [
    tecnicos.detectar,
    friccion.detectar,
    objetivo.detectar,
    flutter.detectar,
]


def ejecutar_detectores(ctx: ContextoDeteccion) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for detector in DETECTORES:
        try:
            hallazgos.extend(detector(ctx))
        except Exception as e:  # noqa: BLE001 - un detector roto no frena a los demás
            nombre = f"{detector.__module__}.{detector.__qualname__}"
            hallazgos.append(
                Hallazgo(
                    tipo=TipoHallazgo.tecnico,
                    gravedad=Gravedad.baja,
                    pantalla="dogfood",
                    titulo=f"detector {nombre} falló",
                    descripcion=f"{type(e).__name__}: {e}",
                    semilla=ctx.corrida.semilla,
                    commit=ctx.instancia.commit,
                )
            )
    return hallazgos
