from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia


class Objetivo(Protocol):
    nombre: str

    def preparar(self, ref: str, corrida: Corrida) -> Instancia:
        """Levanta la instancia y espera a que esté sana."""
        ...

    def destruir(self, instancia: Instancia) -> None: ...

    def url_permitida(self, url: str, instancia: Instancia) -> bool: ...

    def escenarios(self) -> list[Escenario]: ...

    def pantalla(self, url: str) -> str:
        """Nombre de pantalla para una URL: "mapeo", "calidad", …"""
        ...

    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]: ...

    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]:
        """servicio → texto"""
        ...
