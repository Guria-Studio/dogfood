"""Objetivo Android genérico (NFR-9, FR-29): cualquier app instalada en un dispositivo por ADB."""

import asyncio
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from dogfood.config import Config
from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia
from dogfood.drivers.android import Adb, AdbError, DriverAndroid, Runner
from dogfood.escenarios import cargar

_AYUDA = (
    "Conecta el dispositivo por USB (depuración USB activa) o por Tailscale con "
    "`adb pair <ip-tailscale>:<puerto>` y `adb connect <ip-tailscale>:<puerto>`. "
    "Detalles en docs/ops/android.md."
)


class AndroidObjetivo:
    nombre = "android"

    def __init__(self, cfg: Config | None = None, runner: Runner | None = None):
        self._cfg = cfg
        self._runner = runner

    def _adb(self, serial: str | None, host_puerto: str | None) -> Adb:
        return Adb(serial, host_puerto, runner=self._runner)

    async def _preparar(self, ref: str) -> Instancia:
        cfg = self._cfg or Config.cargar()
        d = cfg.driver
        if not d.paquete:
            raise ValueError("Falta `driver.paquete` en dogfood.yaml (paquete de la app Android).")
        adb = self._adb(d.serial, d.host_puerto)  # valida el destino antes de llamar a adb
        try:
            await adb.conectar()
            estado = (await adb.ejecutar("get-state")).decode(errors="replace").strip()
            if estado != "device":
                raise AdbError(f"get-state = {estado!r}, se esperaba 'device'")
        except AdbError as e:
            raise RuntimeError(f"Sin dispositivo Android ({adb.destino}): {e}. {_AYUDA}") from e
        driver = DriverAndroid(adb, d.paquete)
        if d.apk:
            await driver.instalar(Path(d.apk))
        parametros = (
            {"host_puerto": adb.conexion} if adb.conexion else {"serial": adb.destino}
        ) | {"paquete": d.paquete, "version_app": await driver.version_app()}
        return Instancia(
            base_url=f"android://{d.paquete}",
            api_url="",
            proyecto_compose="",
            commit=ref,
            parametros=parametros,
        )

    def preparar(self, ref: str, corrida: Corrida) -> Instancia:
        return asyncio.run(self._preparar(ref))

    def _adb_de(self, instancia: Instancia) -> Adb:
        p = instancia.parametros
        return self._adb(p.get("serial"), p.get("host_puerto"))

    def destruir(self, instancia: Instancia) -> None:
        adb, paquete = self._adb_de(instancia), instancia.parametros["paquete"]

        async def limpiar() -> None:  # nunca desinstala
            await adb.ejecutar("shell", "am", "force-stop", paquete)
            await adb.ejecutar("shell", "pm", "clear", paquete)

        asyncio.run(limpiar())

    def url_permitida(self, url: str, instancia: Instancia) -> bool:
        base = instancia.base_url
        return url == base or url.startswith(base + "/")

    def escenarios(self) -> list[Escenario]:
        return cargar(Path(__file__).parent / "escenarios")

    def pantalla(self, url: str) -> str:
        resto = url.removeprefix("android://")
        paquete, _, actividad = resto.partition("/")
        return actividad.removeprefix(paquete)

    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]:
        return []

    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]:
        adb = self._adb_de(instancia)
        salida = asyncio.run(adb.ejecutar("logcat", "-d"))
        return {"logcat": salida.decode(errors="replace")}
