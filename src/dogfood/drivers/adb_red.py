"""ADB sobre Tailscale (FR-34, NFR-10): emparejar, conectar, listar y revisar el servidor local."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from dogfood.drivers.android import AdbError, validar_destino

Runner = Callable[
    ..., tuple[int, str]
]  # (args: list[str], *, interactivo: bool = False) -> (código, salida)
RunnerSs = Callable[[], str]

_AYUDA = "docs/ops/android.md"


def runner_real(args: list[str], *, interactivo: bool = False) -> tuple[int, str]:
    if (
        interactivo
    ):  # hereda stdin/stdout: el código de emparejado lo escribe la persona en el prompt de adb
        return subprocess.run(["adb", *args], check=False).returncode, ""
    p = subprocess.run(["adb", *args], capture_output=True, text=True, check=False)
    return p.returncode, (p.stdout + p.stderr).strip()


def _ss_real() -> str:
    return subprocess.run(["ss", "-ltn"], capture_output=True, text=True, check=False).stdout


@dataclass
class DispositivoAdb:
    serial: str
    estado: str = ""
    modelo: str = ""
    android: str = ""
    permitido: bool = True
    motivo: str = ""


def emparejar(host_puerto: str, runner: Runner = runner_real) -> None:
    """Corre `adb pair` interactivo. Nunca recibe ni lee el código de 6 dígitos."""
    try:
        validar_destino(None, host_puerto)
    except ValueError as e:
        raise AdbError(str(e)) from None
    codigo, _ = runner(["pair", host_puerto], interactivo=True)
    if codigo:
        raise AdbError(
            f"adb pair {host_puerto} falló ({codigo}). Revisa IP, puerto y código; ver {_AYUDA}."
        )


def _prop(runner: Runner, hp: str, prop: str) -> str:
    codigo, salida = runner(["-s", hp, "shell", "getprop", prop])
    return salida.strip() if codigo == 0 else ""


def conectar(host_puerto: str, runner: Runner = runner_real) -> DispositivoAdb:
    try:
        validar_destino(None, host_puerto)
    except ValueError as e:
        raise AdbError(str(e)) from None
    codigo, salida = runner(["connect", host_puerto])
    if codigo or "failed to connect" in salida or "unable to connect" in salida:
        raise AdbError(
            f"No se pudo conectar a {host_puerto}: {salida}. Si el celular no está emparejado, "
            f"corre `dogfood android emparejar {host_puerto}` (puerto de emparejado) y mira {_AYUDA}."
        )
    codigo, estado = runner(["-s", host_puerto, "get-state"])
    if codigo or estado.strip() != "device":
        raise AdbError(
            f"{host_puerto}: get-state = {estado.strip()!r}, se esperaba 'device'. Ver {_AYUDA}."
        )
    return DispositivoAdb(
        serial=host_puerto,
        estado="device",
        modelo=_prop(runner, host_puerto, "ro.product.model"),
        android=_prop(runner, host_puerto, "ro.build.version.release"),
    )


def desconectar(host_puerto: str | None, runner: Runner = runner_real) -> None:
    runner(["disconnect", *([host_puerto] if host_puerto else [])])


def listar(runner: Runner = runner_real) -> list[DispositivoAdb]:
    codigo, salida = runner(["devices", "-l"])
    if codigo:
        raise AdbError(f"adb devices falló ({codigo}): {salida}")
    lista = []
    for linea in salida.splitlines():
        partes = linea.split()
        if len(partes) < 2 or partes[0] == "List" or partes[0].startswith("*"):
            continue
        d = DispositivoAdb(serial=partes[0], estado=partes[1])
        d.modelo = next((p[6:] for p in partes[2:] if p.startswith("model:")), "")
        try:
            validar_destino(d.serial, None)
        except ValueError as e:
            d.permitido, d.motivo = False, str(e)
        lista.append(d)
    return lista


def servidor_local_ok(runner_ss: RunnerSs | None = None) -> tuple[bool, str]:
    """El servidor adb (5037) debe escuchar solo en loopback (NFR-10)."""
    abiertas = []
    for linea in (runner_ss or _ss_real)().splitlines():
        partes = linea.split()
        local = partes[3] if len(partes) > 3 else ""
        host, _, puerto = local.rpartition(":")
        if puerto == "5037" and host not in ("127.0.0.1", "[::1]"):
            abiertas.append(local)
    if abiertas:
        return False, (
            f"El servidor adb escucha en {', '.join(abiertas)}, abierto a la red. "
            "Corre `adb kill-server` y no uses `adb -a`."
        )
    return True, "El servidor adb escucha solo en loopback."
