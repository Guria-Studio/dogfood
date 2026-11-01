"""Fuentes de frames de Android: screencap (PNG→JPEG) y screenrecord H.264 + ffmpeg (FR-37)."""

import asyncio
import logging
import shutil
import time
from io import BytesIO
from pathlib import Path

from PIL import Image

from dogfood.drivers.android import Adb, AdbError

log = logging.getLogger("dogfood")

_LIMITE_S = 170  # screenrecord corta solo a los 180 s


def _a_jpeg(png: bytes) -> bytes:
    img = Image.open(BytesIO(png)).convert("RGB")
    img.thumbnail((720, 720))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=60)
    return buf.getvalue()


class FuenteScreencap:
    nombre = "screencap"

    def __init__(self, adb: Adb, fps: float = 2):
        self.adb = adb
        self.intervalo_s = 1 / fps
        self._frame: tuple[float, bytes | None] = (float("-inf"), None)

    async def iniciar(self) -> None:
        pass

    async def frame(self) -> bytes | None:
        ts, cache = self._frame
        if time.monotonic() - ts < self.intervalo_s:
            return cache
        self._frame = (time.monotonic(), cache)  # también limita los reintentos si falla
        try:
            png = await self.adb.ejecutar("exec-out", "screencap", "-p", binario=True)
            jpeg = await asyncio.to_thread(_a_jpeg, png)
        except (AdbError, OSError):
            return cache
        self._frame = (time.monotonic(), jpeg)
        return jpeg

    async def cerrar(self) -> None:
        pass


def _cortar_jpeg(buf: bytearray) -> list[bytes]:
    """Extrae de `buf` los JPEG completos (FF D8 … FF D9); deja el resto."""
    salida = []
    while True:
        ini = buf.find(b"\xff\xd8")
        if ini < 0:
            buf.clear()
            return salida
        fin = buf.find(b"\xff\xd9", ini + 2)
        if fin < 0:
            del buf[:ini]
            return salida
        salida.append(bytes(buf[ini : fin + 2]))
        del buf[: fin + 2]


class FuenteScreenrecord:
    nombre = "screenrecord"

    def __init__(
        self,
        adb: Adb,
        carpeta_video: Path,
        fps: float = 5,
        runner_ffmpeg: str | None = None,
    ):
        self.adb = adb
        self.carpeta_video = carpeta_video
        self.fps = fps
        self.intervalo_s = 1 / fps
        self._ffmpeg = runner_ffmpeg or "ffmpeg"  # binario de ffmpeg
        self._jpeg: bytes | None = None
        self._tarea: asyncio.Task | None = None
        self._procs: list[asyncio.subprocess.Process] = []
        self._respaldo: FuenteScreencap | None = None

    async def iniciar(self) -> None:
        self.carpeta_video.mkdir(parents=True, exist_ok=True)
        if shutil.which(self._ffmpeg) is None:
            self._caer("ffmpeg no está en el PATH")
            return
        self._tarea = asyncio.create_task(self._supervisar())

    def _caer(self, motivo: str) -> None:
        log.warning("screenrecord → screencap: %s", motivo)
        self._respaldo = FuenteScreencap(self.adb, self.fps)
        self.nombre = "screencap"

    async def frame(self) -> bytes | None:
        if self._respaldo:
            return await self._respaldo.frame()
        return self._jpeg

    async def _supervisar(self) -> None:
        n = fallos = 0
        while True:
            try:
                ok = await self._segmento(n)
            except OSError as e:
                log.warning("screenrecord: %s", e)
                ok = False
            fallos = 0 if ok else fallos + 1
            if fallos >= 2:
                self._caer("el proceso murió dos veces seguidas")
                return
            n += 1
            await asyncio.sleep(0.2)

    async def _segmento(self, n: int) -> bool:
        """Un segmento de ≤170 s. True si ffmpeg entregó algún frame y ambos salieron con 0."""
        pipe = asyncio.subprocess.PIPE
        rec = await asyncio.create_subprocess_exec(
            self.adb._bin,
            "-s",
            self.adb.destino,
            "exec-out",
            "screenrecord",
            "--output-format=h264",
            "--time-limit",
            str(_LIMITE_S),
            "-",
            stdout=pipe,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._procs.append(rec)
        ff = await asyncio.create_subprocess_exec(
            self._ffmpeg,
            *("-loglevel", "error", "-f", "h264", "-i", "-"),
            *("-f", "image2pipe", "-c:v", "mjpeg", "-q:v", "7", "-r", str(self.fps), "-"),
            stdin=pipe,
            stdout=pipe,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._procs.append(ff)
        frames = 0

        async def copiar() -> None:
            assert rec.stdout and ff.stdin
            with (self.carpeta_video / f"stream-{n}.h264").open("wb") as f:
                while datos := await rec.stdout.read(65536):
                    f.write(datos)
                    try:
                        ff.stdin.write(datos)
                        await ff.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):
                        ff.stdin.close()  # ffmpeg murió: sigue grabando la evidencia
            try:
                ff.stdin.close()
            except OSError:
                pass

        async def leer() -> None:
            nonlocal frames
            assert ff.stdout
            buf = bytearray()
            while datos := await ff.stdout.read(65536):
                buf += datos
                for jpeg in _cortar_jpeg(buf):
                    self._jpeg = jpeg
                    frames += 1

        try:
            await asyncio.gather(copiar(), leer())
            await asyncio.gather(rec.wait(), ff.wait())
        finally:
            for p in (rec, ff):
                if p.returncode is None:
                    p.kill()
                    await p.wait()
                if p in self._procs:
                    self._procs.remove(p)
        return frames > 0 and rec.returncode == 0 and ff.returncode == 0

    async def cerrar(self) -> None:
        if self._tarea:
            self._tarea.cancel()
            await asyncio.gather(self._tarea, return_exceptions=True)
            self._tarea = None
        for p in self._procs:
            if p.returncode is None:
                p.kill()
        self._procs.clear()
        if self._respaldo:
            await self._respaldo.cerrar()
