"""Drivers de plataforma: `web` (Playwright) y `android` (ADB)."""

from dogfood.drivers.base import (
    Accion,
    Driver,
    ElementoUI,
    Observacion,
    ResultadoAccion,
    arbol_a_texto,
)

__all__ = ["Accion", "Driver", "ElementoUI", "Observacion", "ResultadoAccion", "arbol_a_texto"]
