"""Objetivo app Flutter compilada a web (FR-39). Stub: lo implementa F8.7.T1."""

from collections.abc import Callable
from datetime import datetime

from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia

_PENDIENTE = "el objetivo flutter_web todavía no está implementado (lo implementa F8.7.T1)"


class FlutterWebObjetivo:
    nombre = "flutter_web"

    def preparar(self, ref: str, corrida: Corrida) -> Instancia:
        raise NotImplementedError(_PENDIENTE)

    def destruir(self, instancia: Instancia) -> None:
        raise NotImplementedError(_PENDIENTE)

    def url_permitida(self, url: str, instancia: Instancia) -> bool:
        return False

    def escenarios(self) -> list[Escenario]:
        return []

    def pantalla(self, url: str) -> str:
        return url

    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]:
        return []

    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]:
        return {}
