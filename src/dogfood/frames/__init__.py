from pathlib import Path
from typing import Any

from dogfood.config import Config
from dogfood.drivers.base import Driver
from dogfood.frames.android import FuenteScreencap, FuenteScreenrecord
from dogfood.frames.base import FuenteDeDriver, FuenteFrames, validar_url_local
from dogfood.frames.mjpeg import FuenteMjpeg

__all__ = [
    "FuenteDeDriver",
    "FuenteFrames",
    "FuenteMjpeg",
    "FuenteScreencap",
    "FuenteScreenrecord",
    "crear_fuente",
    "validar_url_local",
]


def crear_fuente(cfg: Config, driver: Driver, parametros: dict[str, Any]) -> FuenteFrames:
    """Elige la fuente según `driver.nombre` y `cfg.pantalla`; si no hay una mejor, el driver."""
    if driver.nombre == "android":
        if cfg.pantalla.android == "screencap":
            return FuenteScreencap(driver.adb, cfg.pantalla.fps)  # type: ignore[attr-defined]
        carpeta = Path(parametros.get("carpeta_video") or "video")
        return FuenteScreenrecord(driver.adb, carpeta, cfg.pantalla.fps)  # type: ignore[attr-defined]
    if driver.nombre == "ios" and parametros.get("mjpeg_url"):
        return FuenteMjpeg(parametros["mjpeg_url"])
    return FuenteDeDriver(driver)
