import logging

from dogfood.dominio import ContextoDeteccion, Gravedad, Hallazgo, TipoHallazgo
from dogfood.objetivos import cargar_objetivo

log = logging.getLogger(__name__)


def detectar(ctx: ContextoDeteccion) -> list[Hallazgo]:
    # ContextoDeteccion no trae el objetivo: se carga por nombre. Los tests pueden inyectarlo.
    objetivo = getattr(ctx, "objetivo", None) or cargar_objetivo(ctx.corrida.objetivo)
    hallazgos: list[Hallazgo] = []
    for verificador in objetivo.verificadores():
        try:
            hallazgos.extend(verificador(ctx))
        except Exception as e:
            nombre = f"{verificador.__module__}.{verificador.__qualname__}"
            log.exception("verificador %s falló", nombre)
            hallazgos.append(
                Hallazgo(
                    tipo=TipoHallazgo.tecnico,
                    gravedad=Gravedad.baja,
                    pantalla="dogfood",
                    titulo=f"verificador {nombre} falló ({type(e).__name__})",
                    descripcion=f"{type(e).__name__}: {e}",
                    semilla=ctx.corrida.semilla,
                    commit=ctx.instancia.commit,
                )
            )
    return hallazgos
