"""Página «Dispositivos» del panel: pantalla en vivo de los Android y nodos iOS (FR-37)."""

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

from dogfood.config import Config
from dogfood.drivers import adb_red
from dogfood.drivers.android import Adb, AdbError
from dogfood.frames import FuenteFrames, FuenteMjpeg, FuenteScreencap

_MJPEG_IOS = "http://127.0.0.1:9100"  # WebDriverAgent por el túnel SSH del nodo (NFR-12)


def registrar_rutas(
    app: FastAPI,
    plantillas: Jinja2Templates,
    raiz: Path,
    cfg: Config | None = None,
    fuentes: dict[str, FuenteFrames] | None = None,
    runner_adb: adb_red.Runner | None = None,
) -> None:
    def tarjetas() -> list[dict]:
        lista = []
        try:
            androides = adb_red.listar(runner_adb) if runner_adb else adb_red.listar()
        except (
            AdbError,
            OSError,
        ):  # sin adb instalado o servidor caído: solo se muestran los nodos
            androides = []
        for d in androides:
            lista.append(
                {
                    "id": d.serial,
                    "nombre": d.modelo or d.serial,
                    "plataforma": "android",
                    "estado": d.estado,
                    "permitido": d.permitido,
                    "motivo": d.motivo,
                }
            )
        for nombre, nodo in (cfg.nodos if cfg else {}).items():
            lista.append(
                {
                    "id": f"ios-{nombre}",
                    "nombre": f"{nombre} ({nodo.usuario}@{nodo.host})",
                    "plataforma": "ios",
                    "estado": "configurado",
                    "permitido": True,
                    "motivo": "",
                }
            )
        return lista

    @app.get("/dispositivos")
    def dispositivos(request: Request):
        return plantillas.TemplateResponse(request, "dispositivos.html", {"tarjetas": tarjetas()})

    @app.get("/dispositivos/{id:path}/mjpeg")
    def mjpeg(id: str):
        t = next((t for t in tarjetas() if t["id"] == id and t["permitido"]), None)
        if t is None:
            raise HTTPException(404, f"dispositivo {id!r} no existe o no está permitido")
        if fuentes and id in fuentes:
            fuente = fuentes[id]
        elif t["plataforma"] == "android":
            fuente = FuenteScreencap(Adb(serial=id, runner=None))
        else:
            fuente = FuenteMjpeg(_MJPEG_IOS)

        async def emitir():
            ultimo = None
            try:
                await fuente.iniciar()
                while True:
                    jpeg = await fuente.frame()
                    if jpeg and jpeg != ultimo:
                        ultimo = jpeg
                        yield (
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(jpeg)).encode()
                            + b"\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        )
                    await asyncio.sleep(fuente.intervalo_s)
            finally:  # el cliente se fue (cancelación) o falló la fuente
                await asyncio.shield(fuente.cerrar())

        return StreamingResponse(emitir(), media_type="multipart/x-mixed-replace; boundary=frame")
