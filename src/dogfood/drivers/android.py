"""Driver Android (FR-28, FR-29): ADB + UIAutomator, sin shell local y solo por USB, localhost o Tailscale."""

import asyncio
import contextlib
import ipaddress
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from dogfood.dominio import Evidencia
from dogfood.drivers.base import Accion, ElementoUI, Observacion, ResultadoAccion

Runner = Callable[..., Awaitable[bytes]]  # (args: list[str], *, binario: bool) -> bytes

_SERIAL = re.compile(r"^[A-Za-z0-9._-]+$")
_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
_ESPECIALES = set("&;|<>()$`\\\"'*?~#!{}[]")
_SEGMENTO_S = 170
_UI_REMOTO = "/sdcard/dogfood-ui.xml"


class AdbError(RuntimeError):
    pass


def validar_destino(serial: str | None, host_puerto: str | None) -> str:
    """Devuelve el destino ADB si es USB, localhost o Tailscale; si no, lanza ValueError (NFR-10)."""
    if host_puerto is None and serial and ":" in serial:
        host_puerto, serial = serial, None
    if host_puerto:
        host, _, puerto = host_puerto.rpartition(":")
        if not puerto.isdigit() or not 0 < int(puerto) < 65536:
            raise ValueError(
                f"Destino ADB inválido {host_puerto!r}: falta un puerto válido (host:puerto)."
            )
        if host != "localhost":
            try:
                ip = ipaddress.ip_address(host)
            except ValueError:
                raise ValueError(
                    f"Destino ADB inválido {host_puerto!r}: se espera una IP."
                ) from None
            if not (ip == ipaddress.ip_address("127.0.0.1") or ip in _TAILSCALE):
                raise ValueError(
                    f"Destino ADB {host_puerto!r} rechazado (NFR-10): ADB no se expone fuera de USB, "
                    "127.0.0.1/localhost o una IP de Tailscale (100.64.0.0/10)."
                )
        return host_puerto
    if serial and _SERIAL.match(serial):
        return serial
    raise ValueError(
        "Falta el destino ADB: indica un serial USB o host:puerto (localhost o Tailscale)."
    )


def escapar_texto(texto: str) -> str:
    """Escapa un texto para `adb shell input text`: espacios como %s y especiales del shell con barra."""
    return "".join("%s" if c == " " else "\\" + c if c in _ESPECIALES else c for c in texto)


class Adb:
    def __init__(
        self,
        serial: str | None = None,
        host_puerto: str | None = None,
        runner: Runner | None = None,
        binario: str = "adb",
    ):
        self.destino = validar_destino(serial, host_puerto)
        self.conexion = (
            host_puerto if host_puerto else (serial if serial and ":" in serial else None)
        )
        self._bin = binario
        self._runner = runner or self._runner_real

    async def _runner_real(self, args: list[str], *, binario: bool = False) -> bytes:
        prefijo = [] if args and args[0] == "connect" else ["-s", self.destino]
        proc = await asyncio.create_subprocess_exec(
            self._bin,
            *prefijo,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await proc.communicate()
        except asyncio.CancelledError:
            if proc.returncode is None:
                proc.kill()
            raise
        if proc.returncode:
            raise AdbError(
                f"adb {' '.join(args)} falló ({proc.returncode}): {err.decode(errors='replace').strip()}"
            )
        return out

    async def ejecutar(self, *args: str, binario: bool = False) -> bytes:
        return await self._runner(list(args), binario=binario)

    async def conectar(self) -> None:
        if not self.conexion:
            return
        await self.ejecutar("connect", self.conexion)
        estado = (await self.ejecutar("get-state")).decode(errors="replace").strip()
        if estado != "device":
            raise AdbError(f"{self.conexion}: get-state = {estado!r}, se esperaba 'device'")


def _parsear_bounds(texto: str) -> tuple[int, int, int, int] | None:
    m = _BOUNDS.fullmatch(texto)
    return tuple(int(g) for g in m.groups()) if m else None  # type: ignore[return-value]


def parsear_arbol(xml: str) -> list[ElementoUI]:
    elementos = []
    for i, nodo in enumerate(ET.fromstring(xml).iter("node")):
        a = nodo.attrib
        bounds = _parsear_bounds(a.get("bounds", ""))
        texto, desc, rid = a.get("text", ""), a.get("content-desc", ""), a.get("resource-id", "")
        clicable = a.get("clickable") == "true"
        if bounds is None or not (texto or desc or rid or clicable):
            continue
        clase = a.get("class", "")
        elementos.append(
            ElementoUI(
                id=rid or f"e{i}",
                texto=texto,
                descripcion=desc,
                clase=clase,
                bounds=bounds,
                clicable=clicable,
                editable="EditText" in clase,
            )
        )
    return elementos


class DriverAndroid:
    nombre = "android"

    def __init__(self, adb: Adb, paquete: str, actividad: str | None = None):
        self.adb = adb
        self.paquete = paquete
        self.actividad = actividad
        self.espera_cierre = 1.0  # s entre SIGINT a screenrecord y bajar el mp4
        self._carpeta: Path | None = None
        self._elementos: dict[str, ElementoUI] = {}
        self._grabacion: asyncio.Task | None = None
        self._segmentos: list[int] = []
        self._frame: tuple[float, bytes | None] = (float("-inf"), None)

    async def iniciar(self, carpeta: Path) -> None:
        self._carpeta = carpeta
        for sub in ("capturas", "arboles", "video"):
            (carpeta / sub).mkdir(parents=True, exist_ok=True)
        await self.adb.conectar()
        await self.adb.ejecutar("logcat", "-c")
        self._grabacion = asyncio.create_task(self._grabar())

    async def _grabar(self) -> None:
        n = 0
        while True:
            self._segmentos.append(n)
            ini = time.monotonic()
            try:
                await self.adb.ejecutar(
                    "shell",
                    "screenrecord",
                    "--time-limit",
                    str(_SEGMENTO_S),
                    f"/sdcard/dogfood-{n}.mp4",
                )
            except AdbError:
                return
            if time.monotonic() - ini < 5:  # screenrecord no está grabando: no reintentar en bucle
                return
            n += 1

    async def _actividad(self) -> str:
        for cmd, patron in (
            (("dumpsys", "activity", "activities"), r"mResumedActivity.*?\su\d+\s+(\S+)"),
            (("dumpsys", "window"), r"mCurrentFocus=Window\{\S+ u\d+ (\S+?)\}"),
        ):
            try:
                salida = (await self.adb.ejecutar("shell", *cmd)).decode(errors="replace")
            except AdbError:
                continue
            if m := re.search(patron, salida):
                return m.group(1)
        return ""

    async def _volcar_arbol(self) -> str:
        for _ in range(2):
            try:
                await self.adb.ejecutar("shell", "uiautomator", "dump", _UI_REMOTO)
                xml = (await self.adb.ejecutar("exec-out", "cat", _UI_REMOTO)).decode(
                    errors="replace"
                )
                if "<node" in xml:
                    return xml
            except AdbError:
                pass
        return ""

    async def observar(self, n_paso: int) -> Observacion:
        assert self._carpeta is not None, "llama a iniciar() antes de observar()"
        captura = self._carpeta / "capturas" / f"paso-{n_paso:03d}.png"
        captura.write_bytes(await self.adb.ejecutar("exec-out", "screencap", "-p", binario=True))
        xml = await self._volcar_arbol()
        arbol = None
        elementos: list[ElementoUI] = []
        if xml:
            arbol = self._carpeta / "arboles" / f"paso-{n_paso:03d}.xml"
            arbol.write_text(xml, encoding="utf-8")
            try:
                elementos = parsear_arbol(xml)
            except ET.ParseError:
                elementos = []
        self._elementos = {e.id: e for e in elementos}
        return Observacion(
            pantalla=await self._actividad(),
            elementos=elementos,
            texto_visible="\n".join(e.texto for e in elementos if e.texto),
            captura=captura,
            arbol=arbol,
            ts=datetime.now(),
        )

    def _punto(self, a: Accion) -> tuple[int, int]:
        if a.elemento is not None:
            el = self._elementos.get(a.elemento)
            if el is None:
                raise LookupError(f"El elemento {a.elemento!r} no existe en la última observación.")
            return el.centro
        if a.x is None or a.y is None:
            raise ValueError("Falta el elemento o las coordenadas x/y.")
        return a.x, a.y

    async def actuar(self, accion: Accion) -> ResultadoAccion:
        sh = self.adb.ejecutar
        try:
            punto = None
            match accion.tipo:
                case "tocar":
                    punto = self._punto(accion)
                    await sh("shell", "input", "tap", str(punto[0]), str(punto[1]))
                case "escribir":
                    if accion.texto is None:
                        raise ValueError("Falta el texto a escribir.")
                    if accion.elemento is not None:
                        punto = self._punto(accion)
                        await sh("shell", "input", "tap", str(punto[0]), str(punto[1]))
                    await sh("shell", "input", "text", escapar_texto(accion.texto))
                case "deslizar":
                    punto = self._punto(accion)
                    if accion.x2 is None or accion.y2 is None:
                        raise ValueError("Falta x2/y2 para deslizar.")
                    await sh(
                        "shell", "input", "swipe", str(punto[0]), str(punto[1]),
                        str(accion.x2), str(accion.y2), str(accion.ms or 300),
                    )  # fmt: skip
                case "volver":
                    await sh("shell", "input", "keyevent", "KEYCODE_BACK")
                case "tecla":
                    if not accion.texto:
                        raise ValueError("Falta la tecla (p. ej. KEYCODE_ENTER).")
                    await sh("shell", "input", "keyevent", accion.texto)
                case "abrir_app":
                    paquete = accion.texto or self.paquete
                    if self.actividad and not accion.texto:
                        await sh("shell", "am", "start", "-n", f"{paquete}/{self.actividad}")
                    else:
                        await sh(
                            "shell", "monkey", "-p", paquete, "-c", "android.intent.category.LAUNCHER", "1"
                        )  # fmt: skip
                case "cerrar_app":
                    await sh("shell", "am", "force-stop", accion.texto or self.paquete)
                case "esperar":
                    await asyncio.sleep((accion.ms or 1000) / 1000)
                case _:
                    raise ValueError(f"Acción {accion.tipo!r} no soportada en Android.")
        except (AdbError, LookupError, ValueError) as e:
            return ResultadoAccion(ok=False, error=str(e))
        return ResultadoAccion(ok=True, punto=punto)

    async def instalar(self, apk: Path) -> None:
        await self.adb.ejecutar("install", "-r", str(apk))

    async def version_app(self) -> str:
        salida = await self.adb.ejecutar("shell", "dumpsys", "package", self.paquete)
        m = re.search(r"versionName=(\S+)", salida.decode(errors="replace"))
        return m.group(1) if m else ""

    async def frame(self) -> bytes | None:
        ts, cache = self._frame
        if time.monotonic() - ts < 1:
            return cache
        self._frame = (time.monotonic(), cache)  # también limita los reintentos si falla
        try:
            png = await self.adb.ejecutar("exec-out", "screencap", "-p", binario=True)
            jpeg = await asyncio.to_thread(_a_jpeg, png)
        except (AdbError, OSError):
            return cache
        self._frame = (time.monotonic(), jpeg)
        return jpeg

    async def _detener_grabacion(self) -> None:
        tarea, self._grabacion = self._grabacion, None
        if tarea is None:
            return
        try:
            await self.adb.ejecutar("shell", "pkill", "-2", "screenrecord")  # cierra bien el mp4
        except AdbError:
            pass
        await asyncio.sleep(self.espera_cierre)
        tarea.cancel()
        await asyncio.gather(tarea, return_exceptions=True)

    async def evidencia(self) -> list[Evidencia]:
        assert self._carpeta is not None, "llama a iniciar() antes de evidencia()"
        await self._detener_grabacion()
        salida: list[Evidencia] = []
        videos = []
        for n in self._segmentos:
            destino = self._carpeta / "video" / f"dogfood-{n}.mp4"
            try:
                await self.adb.ejecutar("pull", f"/sdcard/dogfood-{n}.mp4", str(destino))
            except AdbError:
                continue
            videos.append(destino)
            await self.adb.ejecutar("shell", "rm", "-f", f"/sdcard/dogfood-{n}.mp4")
        try:
            pid = (await self.adb.ejecutar("shell", "pidof", self.paquete)).decode().split()
        except AdbError:
            pid = []
        args = ["logcat", "-d", "-v", "brief"] + ([f"--pid={pid[0]}"] if pid else [])
        try:
            texto = (await self.adb.ejecutar(*args)).decode(errors="replace")
        except AdbError:
            texto = ""
        lineas = texto.splitlines()
        if not pid:  # sin proceso (¿murió?): solo lo del paquete y los crashes
            lineas = [
                l for l in lineas if self.paquete in l or "FATAL" in l or "AndroidRuntime" in l
            ]
        log = self._carpeta / "logcat.txt"
        log.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        errores = [l for l in lineas if l.startswith("E/") or "FATAL" in l]
        salida.append(Evidencia(tipo="log", ruta=log, extracto="\n".join(errores[-20:])))
        salida.extend(Evidencia(tipo="video", ruta=v) for v in videos)
        return salida

    async def cerrar(self) -> None:
        with contextlib.suppress(Exception):  # cerrar nunca lanza si el dispositivo ya no está
            await self._detener_grabacion()


def _a_jpeg(png: bytes) -> bytes:
    img = Image.open(BytesIO(png)).convert("RGB")
    img.thumbnail((720, 720))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=60)
    return buf.getvalue()
