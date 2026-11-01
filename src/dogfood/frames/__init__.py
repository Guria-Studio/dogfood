from typing import Any

from dogfood.config import Config
from dogfood.drivers.base import Driver
from dogfood.frames.base import FuenteDeDriver, FuenteFrames, validar_url_local

__all__ = ["FuenteDeDriver", "FuenteFrames", "crear_fuente", "validar_url_local"]


def crear_fuente(cfg: Config, driver: Driver, parametros: dict[str, Any]) -> FuenteFrames:
    """Elige la fuente según `driver.nombre` y `cfg.pantalla`. Por ahora, siempre el driver (F8.4.T1)."""
    return FuenteDeDriver(driver)
