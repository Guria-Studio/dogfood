"""Protocolo guria ↔ nodo iOS (FR-38): `Trabajo` en JSON por stdin; la última línea de stdout es el
`ResultadoTrabajo`; los logs van a stderr."""

from typing import Literal

from pydantic import BaseModel

from dogfood.deterministico import ResultadoDeterministico
from dogfood.dominio import Escenario


class Trabajo(BaseModel):
    id: str
    tipo: Literal["estado", "patrol", "sesion_appium", "cerrar_sesion"]
    udid: str | None = None
    bundle_id: str | None = None
    proyecto: str | None = None  # ruta de la app en el Mac (patrol)
    escenario: Escenario | None = None  # patrol: con su bloque deterministico
    dart_defines: dict[str, str] = {}  # viajan solo por stdin; el nodo no los escribe a disco
    timeout_s: float = 1800


class EstadoNodo(BaseModel):
    xcode: str | None = None
    flutter: str | None = None
    patrol: str | None = None
    appium: bool = False
    dispositivos: list[dict[str, str]] = []  # {udid, nombre, os}


class ResultadoTrabajo(BaseModel):
    id: str
    estado: Literal["ok", "fallo", "error"]
    mensaje: str = ""
    deterministico: ResultadoDeterministico | None = None  # rutas relativas a dir_trabajo/<id>/
    artefactos: list[str] = []
    appium_url: str | None = None
    mjpeg_url: str | None = None
    estado_nodo: EstadoNodo | None = None
