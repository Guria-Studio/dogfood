"""Lo que corre en el Mac (FR-38): estado del nodo y ejecución de `Trabajo`s. Solo loopback."""

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
from collections.abc import Callable
from pathlib import Path

import httpx

from dogfood.config import Config, Flutter
from dogfood.deterministico.corredor import CorredorFlutter, RunnerProceso, _runner_real
from dogfood.nodos.protocolo import EstadoNodo, ResultadoTrabajo, Trabajo

APPIUM_URL = "http://127.0.0.1:4723"
MJPEG_URL = "http://127.0.0.1:9100"
ESPERA_APPIUM_S = 30.0
_DISPOSITIVO = re.compile(r"^(.+?) \(([\d.]+)\) \(([0-9A-Fa-f-]+)\)\s*$")


async def _salida(runner: RunnerProceso, args: list[str]) -> str | None:
    """stdout del comando, o None si no existe o falla (nunca lanza)."""
    try:
        codigo, out, _ = await runner(args, cwd=Path.cwd(), env=dict(os.environ), timeout_s=30)
    except (OSError, TimeoutError):
        return None
    return out.decode(errors="replace") if codigo == 0 else None


def parsear_xctrace(texto: str) -> list[dict[str, str]]:
    """Solo la sección «== Devices ==» y sin simuladores: `{udid, nombre, os}`."""
    r, activa = [], False
    for ln in texto.splitlines():
        if ln.startswith("=="):
            activa = ln.strip("= ").lower() == "devices"
        elif activa and "Simulator" not in ln and (m := _DISPOSITIVO.match(ln.strip())):
            r.append({"udid": m.group(3), "nombre": m.group(1), "os": m.group(2)})
    return r


async def appium_responde(cliente: httpx.AsyncClient | None = None) -> bool:
    try:
        if cliente:
            return (await cliente.get(f"{APPIUM_URL}/status", timeout=2)).is_success
        async with httpx.AsyncClient(timeout=2) as c:
            return (await c.get(f"{APPIUM_URL}/status")).is_success
    except httpx.HTTPError:
        return False


async def estado_nodo(
    runner: RunnerProceso, cliente: httpx.AsyncClient | None = None
) -> EstadoNodo:
    xcode = await _salida(runner, ["xcodebuild", "-version"])
    xctrace = await _salida(runner, ["xcrun", "xctrace", "list", "devices"])
    patrol = await _salida(runner, ["patrol", "--version"])
    flutter = await _salida(runner, ["flutter", "--version", "--machine"])
    version = None
    if flutter:
        try:
            version = json.loads(flutter).get("frameworkVersion")
        except (ValueError, AttributeError):
            pass
    m = re.search(r"Xcode\s+(\S+)", xcode or "")
    return EstadoNodo(
        xcode=m.group(1) if m else None,
        flutter=version,
        patrol=(patrol or "").strip().splitlines()[0] if (patrol or "").strip() else None,
        appium=await appium_responde(cliente),
        dispositivos=parsear_xctrace(xctrace or ""),
    )


def _arrancar_appium(log: Path) -> int:
    with log.open("ab") as f:
        p = subprocess.Popen(
            ["appium", "--address", "127.0.0.1", "--port", "4723"],
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return p.pid


def _corredor_por_defecto(trabajo: Trabajo, dir_trabajo: Path, runner: RunnerProceso):
    cfg = Config(
        roles={},
        flutter=Flutter(
            sdk=Path(shutil.which("flutter") or "/opt/homebrew/bin/flutter"),
            patrol=Path(shutil.which("patrol") or "patrol"),
            copia_trabajo=dir_trabajo / "copia",
            timeout_s=trabajo.timeout_s,
        ),
    )
    cfg._secretos.update(trabajo.dart_defines)  # solo en memoria
    return CorredorFlutter(cfg, runner)


async def ejecutar(
    trabajo: Trabajo,
    dir_trabajo: Path,
    runner: RunnerProceso | None = None,
    corredor: CorredorFlutter | None = None,
    *,
    cliente: httpx.AsyncClient | None = None,
    arrancar: Callable[[Path], int] = _arrancar_appium,
    matar: Callable[[int], None] = lambda pid: os.kill(pid, signal.SIGTERM),
    espera_s: float = ESPERA_APPIUM_S,
) -> ResultadoTrabajo:
    runner = runner or _runner_real
    carpeta = dir_trabajo / trabajo.id
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        if trabajo.tipo == "estado":
            return ResultadoTrabajo(
                id=trabajo.id, estado="ok", estado_nodo=await estado_nodo(runner, cliente)
            )
        if trabajo.tipo == "patrol":
            if not (trabajo.proyecto and trabajo.udid and trabajo.escenario):
                return ResultadoTrabajo(
                    id=trabajo.id, estado="error", mensaje="patrol pide proyecto, udid y escenario"
                )
            corredor = corredor or _corredor_por_defecto(trabajo, dir_trabajo, runner)
            r = await corredor.correr(
                trabajo.escenario, "patrol", trabajo.udid, carpeta, proyecto=Path(trabajo.proyecto)
            )
            for campo in ("log", "reporte", "captura_final"):
                ruta = getattr(r, campo)
                if ruta:
                    setattr(r, campo, ruta.relative_to(carpeta) if ruta.is_absolute() else ruta)
            res = r.resultado()
            return ResultadoTrabajo(
                id=trabajo.id,
                estado="ok" if res == "aprobado" else "fallo",
                mensaje=res + (f": {r.motivo}" if r.motivo else ""),
                deterministico=r,
                artefactos=sorted(
                    str(p.relative_to(carpeta)) for p in carpeta.rglob("*") if p.is_file()
                ),
            )
        pid_archivo = dir_trabajo / "appium.pid"
        if trabajo.tipo == "sesion_appium":
            if not await appium_responde(cliente):
                pid_archivo.write_text(str(arrancar(dir_trabajo / "appium.log")))
                loop = asyncio.get_running_loop()
                limite = loop.time() + espera_s
                while not await appium_responde(cliente):
                    if loop.time() > limite:
                        return ResultadoTrabajo(
                            id=trabajo.id,
                            estado="error",
                            mensaje=f"Appium no respondió en {espera_s:g} s (ver appium.log)",
                        )
                    await asyncio.sleep(0.5)
            return ResultadoTrabajo(
                id=trabajo.id, estado="ok", appium_url=APPIUM_URL, mjpeg_url=MJPEG_URL
            )
        # cerrar_sesion: solo el Appium que arrancó este nodo
        if not pid_archivo.exists():
            return ResultadoTrabajo(id=trabajo.id, estado="ok", mensaje="Appium no era del nodo")
        try:
            matar(int(pid_archivo.read_text().strip()))
        except (ProcessLookupError, ValueError):
            pass
        pid_archivo.unlink(missing_ok=True)
        return ResultadoTrabajo(id=trabajo.id, estado="ok", mensaje="Appium detenido")
    except Exception as e:  # noqa: BLE001  # el protocolo siempre devuelve un resultado
        return ResultadoTrabajo(id=trabajo.id, estado="error", mensaje=f"{type(e).__name__}: {e}")
