import asyncio
import stat
from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from dogfood.config import Config
from dogfood.drivers.android import Adb
from dogfood.frames import (
    FuenteDeDriver,
    FuenteMjpeg,
    FuenteScreencap,
    FuenteScreenrecord,
    crear_fuente,
)


def img(w, h, color="red") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "JPEG")
    return buf.getvalue()


def png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (1080, 2400), "white").save(buf, "PNG")
    return buf.getvalue()


async def esperar(cond, t=5):
    for _ in range(int(t / 0.02)):
        if cond():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("timeout")


async def test_screencap_reduce_y_cachea():
    llamadas = []

    async def runner(args, *, binario=False):
        llamadas.append(args)
        return png()

    f = FuenteScreencap(Adb(serial="ABC123", runner=runner), fps=2)
    a = await f.frame()
    b = await f.frame()
    assert a == b and len(llamadas) == 1
    assert max(Image.open(BytesIO(a)).size) <= 720
    assert f.intervalo_s == 0.5


def scripts(tmp_path, monkeypatch, ffmpeg=True):
    j1, j2 = img(8, 8, "red"), img(8, 8, "blue")
    (tmp_path / "j.bin").write_bytes(j1 + j2)
    (tmp_path / "h.bin").write_bytes(b"H264FIJO")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for nombre, cuerpo in {
        "adb": f"/bin/cat {tmp_path}/h.bin",
        "ffmpeg": f"/bin/cat > /dev/null; /bin/cat {tmp_path}/j.bin",
    }.items():
        if nombre == "ffmpeg" and not ffmpeg:
            continue
        p = bin_ / nombre
        p.write_text(f"#!/bin/sh\n{cuerpo}\n")
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bin_))
    return j2


async def test_screenrecord_entrega_ultimo_jpeg(tmp_path, monkeypatch):
    j2 = scripts(tmp_path, monkeypatch)
    f = FuenteScreenrecord(Adb(serial="ABC123"), tmp_path / "video", fps=5)
    await f.iniciar()
    try:
        await esperar(lambda: f._jpeg is not None)
        assert await f.frame() == j2
        assert (tmp_path / "video" / "stream-0.h264").read_bytes() == b"H264FIJO"
    finally:
        await f.cerrar()


async def test_screenrecord_sin_ffmpeg_cae_a_screencap(tmp_path, monkeypatch):
    scripts(tmp_path, monkeypatch, ffmpeg=False)
    f = FuenteScreenrecord(Adb(serial="ABC123"), tmp_path / "video")
    await f.iniciar()
    assert isinstance(f._respaldo, FuenteScreencap)
    await f.cerrar()


def multipart(frames, boundary="frame", longitud=True):
    cuerpo = b""
    for fr in frames:
        cab = f"--{boundary}\r\nContent-Type: image/jpeg\r\n"
        if longitud:
            cab += f"Content-Length: {len(fr)}\r\n"
        cuerpo += cab.encode() + b"\r\n" + fr + b"\r\n"
    return cuerpo + f"--{boundary}--\r\n".encode()


@pytest.mark.parametrize("longitud", [True, False])
async def test_mjpeg_devuelve_el_tercero(longitud):
    frames = [img(8, 8, c) for c in ("red", "green", "blue")]
    cuerpo = multipart(frames, longitud=longitud)

    def h(req):
        return httpx.Response(
            200,
            content=cuerpo,
            headers={"content-type": "multipart/x-mixed-replace; boundary=frame"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        f = FuenteMjpeg("http://127.0.0.1:9100", cliente=c)
        await f.iniciar()
        await esperar(lambda: f._jpeg == frames[2])
        await f.cerrar()


def test_mjpeg_rechaza_url_lan():
    with pytest.raises(ValueError):
        FuenteMjpeg("http://192.168.1.4:9100")


async def test_mjpeg_reintenta_tras_desconexion(monkeypatch):
    fr = img(8, 8)
    n = []

    def h(req):
        n.append(1)
        if len(n) == 1:
            raise httpx.ConnectError("caído")
        return httpx.Response(
            200,
            content=multipart([fr]),
            headers={"content-type": "multipart/x-mixed-replace; boundary=frame"},
        )

    real = asyncio.sleep
    monkeypatch.setattr("dogfood.frames.mjpeg.asyncio.sleep", lambda s: real(0.01))
    async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
        f = FuenteMjpeg("http://127.0.0.1:9100", cliente=c)
        await f.iniciar()
        await esperar(lambda: f._jpeg == fr)
        assert len(n) >= 2
        await f.cerrar()


def test_crear_fuente(tmp_path):
    adb = Adb(serial="ABC123", runner=None)
    d = lambda nombre: SimpleNamespace(nombre=nombre, adb=adb)
    cfg = Config(roles={"persona": ["m"], "juez": ["m"]})
    assert isinstance(crear_fuente(cfg, d("web"), {}), FuenteDeDriver)
    assert isinstance(crear_fuente(cfg, d("android"), {}), FuenteScreencap)
    cfg.pantalla.android = "screenrecord"
    assert isinstance(
        crear_fuente(cfg, d("android"), {"carpeta_video": tmp_path}), FuenteScreenrecord
    )
    url = {"mjpeg_url": "http://127.0.0.1:9100"}
    assert isinstance(crear_fuente(cfg, d("ios"), url), FuenteMjpeg)
    assert isinstance(crear_fuente(cfg, d("ios"), {}), FuenteDeDriver)
