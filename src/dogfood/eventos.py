"""Eventos en vivo (FR-31): pub/sub en proceso que nunca frena a la corrida (NFR-11)."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EventoVivo(BaseModel):
    corrida_id: str
    ejecucion_id: str
    tipo: Literal["inicio", "paso", "frame", "fin"]
    n_paso: int = 0
    persona: str = ""
    escenario: str = ""
    paso_contrato: str = ""
    razonamiento: str = ""
    accion: str = ""
    punto: tuple[int, int] | None = None
    resultado: str | None = None
    frame_jpeg_b64: str | None = None
    ts: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class Suscripcion:
    """Cola acotada de un suscriptor; si se llena, se descarta el evento más viejo."""

    def __init__(self, bus: "BusVivo", max_cola: int):
        self._bus = bus
        self.cola: asyncio.Queue[EventoVivo] = asyncio.Queue(maxsize=max_cola)

    def _entregar(self, ev: EventoVivo) -> None:
        if self.cola.full():
            self.cola.get_nowait()
        self.cola.put_nowait(ev)

    def close(self) -> None:
        self._bus._suscripciones.discard(self)

    def __aiter__(self) -> AsyncIterator[EventoVivo]:
        return self

    async def __anext__(self) -> EventoVivo:
        return await self.cola.get()


class BusVivo:
    activo = True

    def __init__(self) -> None:
        self._suscripciones: set[Suscripcion] = set()

    def publicar(self, ev: EventoVivo) -> None:
        """Nunca bloquea: llamar desde el mismo loop que los suscriptores."""
        for s in list(self._suscripciones):
            s._entregar(ev)

    def suscribir(self, max_cola: int = 50) -> Suscripcion:
        s = Suscripcion(self, max_cola)
        self._suscripciones.add(s)
        return s


class _BusNulo(BusVivo):
    activo = False

    def publicar(self, ev: EventoVivo) -> None:
        pass


BUS_NULO: BusVivo = _BusNulo()
