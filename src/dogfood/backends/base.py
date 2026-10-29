"""Protocolo `BackendLlm` (FR-26, FR-27): motor intercambiable que devuelve JSON validado."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class UsoBackend(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache: int = 0
    capturas: int = 0
    duracion_s: float = 0
    costo_usd: float = 0  # lo que se cobra (0 con plan Max)
    costo_equivalente_usd: float = 0  # lo que costaría por API


class ErrorMotor(RuntimeError):
    """Mensaje accionable, sin secretos."""


class BackendLlm(Protocol):
    nombre: str  # "api" | "claude_code"
    modelo: str

    async def completar_json(
        self,
        prompt: str,
        esquema: type[T],
        *,
        imagenes: Sequence[Path] = (),
        sesion: str | None = None,
    ) -> tuple[T, UsoBackend, str | None]: ...  # salida, uso, sesión
