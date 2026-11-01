"""Objetivo iOS en el nodo Mac (FR-38): Appium por túnel SSH hacia un iPhone real."""

import asyncio
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dogfood.config import Config
from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia
from dogfood.escenarios import cargar
from dogfood.nodos.cliente import ClienteNodo
from dogfood.nodos.protocolo import Trabajo

_AYUDA = "Ver docs/ops/ios-nodo-mac.md."


class IosObjetivo:
    nombre = "ios"

    def __init__(self, cfg: Config | None = None, cliente: ClienteNodo | None = None):
        self._cfg = cfg
        self._cliente = cliente
        self._tunel = None

    def _cliente_de(self, cfg: Config) -> ClienteNodo:
        if self._cliente:
            return self._cliente
        nombre = cfg.driver.nodo
        if not nombre or nombre not in cfg.nodos:
            raise ValueError(
                f"Falta `driver.nodo` (o no está en `nodos`) en dogfood.yaml: {nombre!r}. {_AYUDA}"
            )
        return ClienteNodo(nombre, cfg.nodos[nombre])

    async def _preparar(self) -> Instancia:
        cfg = self._cfg or Config.cargar()
        cliente = self._cliente_de(cfg)
        d = cfg.driver
        if not d.udid or not d.bundle_id:
            raise ValueError(f"Faltan `driver.udid` o `driver.bundle_id` en dogfood.yaml. {_AYUDA}")
        estado = await cliente.estado()
        if not estado.xcode:
            raise RuntimeError(f"El nodo no tiene Xcode instalado. {_AYUDA}")
        if d.udid not in {x["udid"] for x in estado.dispositivos}:
            raise RuntimeError(f"El iPhone {d.udid} no aparece en el nodo. {_AYUDA}")
        self._tunel = await cliente.tunel([4723, 9100])
        try:
            r = await cliente.enviar(
                Trabajo(id=f"sesion-{uuid4().hex[:8]}", tipo="sesion_appium", udid=d.udid),
                Path("/tmp/dogfood-nodo-sesion"),  # ponytail: artefactos de la sesión se descartan
            )
            if r.estado != "ok" or not r.appium_url:
                raise RuntimeError(f"El nodo no abrió Appium: {r.mensaje}. {_AYUDA}")
        except BaseException:
            await self._tunel.cerrar()
            self._tunel = None
            raise
        return Instancia(
            base_url=f"ios://{d.bundle_id}",
            api_url="",
            proyecto_compose="",
            commit="",
            parametros={
                "nodo": d.nodo,
                "udid": d.udid,
                "bundle_id": d.bundle_id,
                "appium_url": r.appium_url,
                "mjpeg_url": r.mjpeg_url or "",
                "version_app": "",  # ponytail: mobile: appInfo necesita sesión; la abre DriverIos
            },
        )

    def preparar(self, ref: str, corrida: Corrida) -> Instancia:
        i = asyncio.run(self._preparar())
        i.commit = ref
        return i

    def destruir(self, instancia: Instancia) -> None:
        async def cerrar() -> None:
            cfg = self._cfg or Config.cargar()
            try:
                if p := instancia.parametros:
                    await self._cliente_de(cfg).enviar(
                        Trabajo(
                            id=f"cerrar-{uuid4().hex[:8]}",
                            tipo="cerrar_sesion",
                            udid=p.get("udid"),
                        ),
                        Path("/tmp/dogfood-nodo-sesion"),
                    )
            finally:
                if self._tunel:
                    await self._tunel.cerrar()
                    self._tunel = None

        asyncio.run(cerrar())

    def url_permitida(self, url: str, instancia: Instancia) -> bool:
        base = instancia.base_url
        return url == base or url.startswith(base + "/")

    def escenarios(self) -> list[Escenario]:
        return cargar(Path(__file__).parent / "escenarios")

    def pantalla(self, url: str) -> str:
        _paquete, _, resto = url.removeprefix("ios://").partition("/")
        return resto

    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]:
        return []

    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]:
        return {}
