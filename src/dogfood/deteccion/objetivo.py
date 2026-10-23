import logging

from dogfood.dominio import ContextoDeteccion, Hallazgo

log = logging.getLogger(__name__)


def detectar(ctx: ContextoDeteccion) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for verificador in ctx.objetivo.verificadores():  # type: ignore[attr-defined]
        try:
            hallazgos.extend(verificador(ctx))
        except Exception:
            log.exception("verificador %s falló", getattr(verificador, "__qualname__", verificador))
    return hallazgos
