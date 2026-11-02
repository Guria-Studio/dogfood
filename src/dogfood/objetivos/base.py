from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from dogfood.dominio import (
    ContextoDeteccion,
    Corrida,
    Escenario,
    Hallazgo,
    Instancia,
    Persona,
)


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


class GanchosOpcionales(Protocol):
    """Métodos que un objetivo puede tener o no: la corrida los busca con `getattr` y, si faltan,
    usa el valor neutro que dice cada uno."""

    def confirmar_registro(self, persona: Persona, instancia: Instancia) -> str | None:
        """Tras cada ejecución: id de la cuenta creada (`Ejecucion.empresa_id`). Neutro: no se llama."""
        ...

    def preparar_escenario(
        self, escenario: Escenario, persona: Persona, instancia: Instancia
    ) -> dict[str, Any]:
        """Argumentos extra del agente para ese escenario (p. ej. `herramientas_extra`). Neutro: {}."""
        ...

    def cliente_api(self, instancia: Instancia, persona: Persona) -> Any:
        """Cliente HTTP de la app con la sesión de la persona (`ContextoDeteccion.cliente_api`).
        Neutro: None."""
        ...

    def repo(self) -> Path | None:
        """Código de la app, para las sugerencias de arreglo. Neutro: None."""
        ...

    def contar_uso_ia(self, instancia: Instancia) -> Any:
        """Uso de IA de la app para la opinión. Neutro: `reporte.opinion.contar_uso_ia`."""
        ...
