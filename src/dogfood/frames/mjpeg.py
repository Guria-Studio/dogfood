"""Fuente de frames sobre un stream MJPEG (multipart/x-mixed-replace), p. ej. WebDriverAgent :9100."""

import asyncio
import logging
import re

import httpx

from dogfood.frames.base import validar_url_local

log = logging.getLogger("dogfood")


def _boundary(content_type: str) -> bytes:
    m = re.search(r'boundary="?([^";]+)"?', content_type)
    return (b"--" + m.group(1).encode()) if m else b"--"


def _partes(buf: bytearray, delim: bytes) -> list[bytes]:
    """Extrae de `buf` las partes completas; deja en `buf` lo que falta."""
    salida = []
    while True:
        ini = buf.find(delim)
        if ini < 0:
            del buf[: max(0, len(buf) - len(delim))]
            return salida
        cab_ini = ini + len(delim)
        fin_cab = buf.find(b"\r\n\r\n", cab_ini)
        if fin_cab < 0:
            del buf[:ini]
            return salida
        cuerpo = fin_cab + 4
        m = re.search(rb"content-length:\s*(\d+)", bytes(buf[cab_ini:fin_cab]), re.IGNORECASE)
        if m:
            fin = cuerpo + int(m.group(1))
            if len(buf) < fin:
                del buf[:ini]
                return salida
        else:
            fin = buf.find(delim, cuerpo)
            if fin < 0:
                del buf[:ini]
                return salida
        salida.append(bytes(buf[cuerpo:fin]).rstrip(b"\r\n"))
        del buf[:fin]


class FuenteMjpeg:
    nombre = "mjpeg"
    intervalo_s = 0.2

    def __init__(self, url: str, cliente: httpx.AsyncClient | None = None):
        self.url = validar_url_local(url)
        self._cliente = cliente
        self._propio = cliente is None
        self._jpeg: bytes | None = None
        self._tarea: asyncio.Task | None = None

    async def iniciar(self) -> None:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(timeout=httpx.Timeout(10, read=None))
        self._tarea = asyncio.create_task(self._bucle())

    async def frame(self) -> bytes | None:
        return self._jpeg

    async def _bucle(self) -> None:
        assert self._cliente
        espera = 0.5
        while True:
            try:
                async with self._cliente.stream("GET", self.url) as r:
                    r.raise_for_status()
                    delim = _boundary(r.headers.get("content-type", ""))
                    buf = bytearray()
                    async for trozo in r.aiter_bytes():
                        buf += trozo
                        for parte in _partes(buf, delim):
                            if parte:
                                self._jpeg = parte
                                espera = 0.5
            except httpx.HTTPError as e:
                log.warning("mjpeg %s: %s; reintento en %.1f s", self.url, e, espera)
            await asyncio.sleep(espera)
            espera = min(espera * 2, 10)

    async def cerrar(self) -> None:
        if self._tarea:
            self._tarea.cancel()
            await asyncio.gather(self._tarea, return_exceptions=True)
            self._tarea = None
        if self._propio and self._cliente:
            await self._cliente.aclose()
            self._cliente = None
