"""Servidor de la vista en vivo: página + WebSocket alimentado por el BusVivo."""

import asyncio
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from dogfood.eventos import BusVivo, EventoVivo, Suscripcion
from dogfood.web import crear_app_base, validar_host

_AQUI = Path(__file__).parent


def crear_app_vista(bus: BusVivo) -> FastAPI:
    app, plantillas = crear_app_base("En vivo", _AQUI / "plantillas")
    app.mount("/vista-estatico", StaticFiles(directory=_AQUI / "estatico"), name="vista")
    # ejecucion_id -> {tipo: último evento}; el servidor guarda esto para los clientes tardíos
    estado: dict[str, dict[str, EventoVivo]] = {}

    def registrar(ev: EventoVivo) -> None:
        if ev.tipo == "inicio":
            estado[ev.ejecucion_id] = {}
        ejec = estado.setdefault(ev.ejecucion_id, {})
        if ev.tipo == "fin":
            ejec.pop("frame", None)
            ejec.pop("paso", None)
        ejec[ev.tipo] = ev

    # Suscripción permanente que registra de forma síncrona: no necesita tarea ni lifespan.
    class _Registro(Suscripcion):
        def _entregar(self, ev: EventoVivo) -> None:
            registrar(ev)

    bus._suscripciones.add(_Registro(bus, 1))

    @app.get("/")
    async def pagina(request: Request):
        return plantillas.TemplateResponse(request, "vista.html")

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        # Suscribirse antes de leer el estado: no se pierde nada entre ambos.
        sub = bus.suscribir(max_cola=100)
        try:
            for ejec in list(estado.values()):
                for tipo in ("inicio", "paso", "frame", "fin"):
                    if tipo in ejec:
                        await websocket.send_text(ejec[tipo].model_dump_json())
            async for ev in sub:
                await websocket.send_text(ev.model_dump_json())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sub.close()

    return app


async def iniciar_vista(bus: BusVivo, host: str, puerto: int) -> asyncio.Task:
    config = uvicorn.Config(crear_app_vista(bus), host=validar_host(host), port=puerto)
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # corre dentro de la corrida, no es el proceso
    return asyncio.create_task(server.serve())
