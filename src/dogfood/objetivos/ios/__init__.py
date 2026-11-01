"""Objetivo iOS en el nodo Mac (FR-38). Stub: lo implementa F8.6.T4."""

from collections.abc import Callable
from datetime import datetime

from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia

_PENDIENTE = "el objetivo ios todavía no está implementado (lo implementa F8.6.T4)"


class IosObjetivo:
    nombre = "ios"

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
