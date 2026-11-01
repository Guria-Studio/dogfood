import asyncio

import pytest
from typer.testing import CliRunner

from dogfood.cli import app
from dogfood.comandos import android as cmd
from dogfood.drivers import adb_red
from dogfood.drivers.android import Adb, AdbError


def fake(respuestas=None):
    llamadas = []

    def runner(args, *, interactivo=False):
        llamadas.append((list(args), interactivo))
        for clave, resp in (respuestas or {}).items():
            if clave in " ".join(args):
                return resp
        return 0, ""

    runner.llamadas = llamadas
    return runner


def test_emparejar_interactivo_y_valida():
    r = fake()
    adb_red.emparejar("100.101.102.103:37099", r)
    assert r.llamadas == [(["pair", "100.101.102.103:37099"], True)]
    r2 = fake()
    with pytest.raises(AdbError):
        adb_red.emparejar("192.168.0.10:37099", r2)
    assert r2.llamadas == []


def test_conectar_ok_y_fallo():
    r = fake(
        {
            "get-state": (0, "device"),
            "ro.product.model": (0, "Pixel 7"),
            "ro.build.version.release": (0, "14"),
            "connect": (0, "connected to x"),
        }
    )
    d = adb_red.conectar("100.64.1.2:5555", r)
    assert (d.modelo, d.android) == ("Pixel 7", "14")
    with pytest.raises(AdbError) as e:
        adb_red.conectar("100.64.1.2:5555", fake({"connect": (0, "failed to connect to x")}))
    assert "dogfood android emparejar" in str(e.value) and "docs/ops/android.md" in str(e.value)


SALIDA = (
    "List of devices attached\nABC123\tdevice usb:1 model:Pixel_7\n"
    "100.64.1.2:5555\tdevice model:Pixel_7\n192.168.1.20:5555\tdevice\n"
)


def test_listar():
    por = {d.serial: d.permitido for d in adb_red.listar(fake({"devices": (0, SALIDA)}))}
    assert por == {"ABC123": True, "100.64.1.2:5555": True, "192.168.1.20:5555": False}


def test_servidor_local():
    ss = "LISTEN 0 4096 {}:5037 0.0.0.0:*"
    assert adb_red.servidor_local_ok(lambda: ss.format("127.0.0.1"))[0]
    ok, msg = adb_red.servidor_local_ok(lambda: ss.format("0.0.0.0"))
    assert not ok and "adb kill-server" in msg


def adb_con(fallos, serial=None, hp="100.64.1.2:5555"):
    llamadas = []
    pendientes = list(fallos)

    async def runner(args, *, binario=False):
        llamadas.append(args)
        if args[0] not in ("connect", "get-state") and pendientes:
            raise AdbError(pendientes.pop(0))
        return b"device" if args[0] == "get-state" else b"ok"

    return Adb(serial=serial, host_puerto=hp, runner=runner), llamadas


def test_reconexion():
    adb, ll = adb_con(["error: device offline"])
    assert asyncio.run(adb.ejecutar("shell", "ls")) == b"ok"
    assert [c[0] for c in ll] == ["shell", "connect", "get-state", "shell"]
    adb, _ = adb_con(["device offline", "device offline"])
    with pytest.raises(AdbError, match="Tailscale"):
        asyncio.run(adb.ejecutar("shell", "ls"))
    adb, ll = adb_con(["device offline"], serial="ABC123", hp=None)
    with pytest.raises(AdbError):
        asyncio.run(adb.ejecutar("shell", "ls"))
    assert len(ll) == 1


def test_cli(monkeypatch):
    cli = CliRunner()
    assert "android" in cli.invoke(app, ["--help"]).output
    monkeypatch.setattr(cmd, "_runner", fake({"devices": (0, SALIDA)}))
    monkeypatch.setattr(adb_red, "_ss_real", lambda: "LISTEN 0 1 127.0.0.1:5037 0.0.0.0:*")
    r = cli.invoke(app, ["android", "estado"])
    assert (
        r.exit_code == 0 and "✅ 100.64.1.2:5555" in r.output and "⛔ 192.168.1.20:5555" in r.output
    )
