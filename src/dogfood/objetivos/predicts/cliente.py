"""Cliente HTTP de la API de predicts. Stub: lo llena la tarea de cuentas y cliente (F1.2)."""

from typing import Any


class PredictsCliente:
    def __init__(self, api_url: str, *args: Any, **kwargs: Any) -> None:
        self.api_url = api_url

    def __getattr__(self, nombre: str) -> Any:
        raise NotImplementedError(f"PredictsCliente.{nombre} lo implementa una tarea posterior")
