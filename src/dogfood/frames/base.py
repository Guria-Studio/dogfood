"""Fuentes de frames (FR-37): de dónde saca la vista en vivo la pantalla del dispositivo."""

from typing import Protocol
from urllib.parse import urlsplit

from dogfood.drivers.base import Driver
from dogfood.web import validar_host


class FuenteFrames(Protocol):
    nombre: str  # "driver" | "screencap" | "screenrecord" | "mjpeg"
    intervalo_s: float  # cada cuánto la pide el emisor de la vista

    async def iniciar(self) -> None: ...
    async def frame(self) -> bytes | None: ...  # último JPEG; nunca espera más de intervalo_s
    async def cerrar(self) -> None: ...


class FuenteDeDriver:
    """`FuenteFrames` sobre `driver.frame()`: 0,2 s en web, 1 s en Android e iOS."""

    nombre = "driver"

    def __init__(self, driver: Driver, intervalo_s: float | None = None):
        self.driver = driver
        self.intervalo_s = intervalo_s or (0.2 if driver.nombre == "web" else 1.0)

    async def iniciar(self) -> None:
        pass

    async def frame(self) -> bytes | None:
        return await self.driver.frame()

    async def cerrar(self) -> None:
        pass


def validar_url_local(url: str) -> str:
    """http(s) con host loopback o Tailscale (100.64.0.0/10); si no, ValueError (NFR-12)."""
    partes = urlsplit(url)
    try:
        if partes.scheme not in ("http", "https") or not partes.hostname:
            raise ValueError
        validar_host(partes.hostname)
    except ValueError:
        raise ValueError(
            f"URL {url!r} no permitida (NFR-12): solo http(s) en 127.0.0.1, localhost, ::1 "
            "o una IP de Tailscale (100.64.0.0/10)"
        ) from None
    return url
