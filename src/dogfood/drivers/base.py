"""Protocolo `Driver` (FR-28): lo que el bucle de agente necesita de una plataforma (web, Android)."""

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

from dogfood.dominio import Evidencia


class ElementoUI(BaseModel):
    id: str  # resource-id / selector estable; "e<n>" si no hay
    texto: str = ""
    descripcion: str = ""  # content-desc / aria-label
    clase: str = ""
    bounds: tuple[int, int, int, int]  # x1, y1, x2, y2 en píxeles
    clicable: bool = False
    editable: bool = False

    @property
    def centro(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bounds
        return (x1 + x2) // 2, (y1 + y2) // 2


class Observacion(BaseModel):
    pantalla: str  # URL (web) o actividad (Android)
    elementos: list[ElementoUI]
    texto_visible: str = ""
    captura: Path | None = None  # PNG del paso
    arbol: Path | None = None  # árbol crudo
    ts: datetime


class Accion(BaseModel):
    tipo: Literal[
        "tocar",
        "escribir",
        "deslizar",
        "tecla",
        "navegar",
        "abrir_app",
        "cerrar_app",
        "volver",
        "esperar",
    ]
    elemento: str | None = None  # id de ElementoUI; si no, x/y
    x: int | None = None
    y: int | None = None
    x2: int | None = None
    y2: int | None = None
    texto: str | None = None  # texto, tecla, URL o paquete
    ms: int | None = None


class ResultadoAccion(BaseModel):
    ok: bool
    error: str = ""
    punto: tuple[int, int] | None = None  # dónde se tocó, para la vista


class Driver(Protocol):
    nombre: str  # "web" | "android"

    async def iniciar(self, carpeta: Path) -> None: ...
    async def observar(self, n_paso: int) -> Observacion: ...
    async def actuar(self, accion: Accion) -> ResultadoAccion: ...
    async def frame(self) -> bytes | None: ...  # JPEG para la vista; barato
    async def evidencia(self) -> list[Evidencia]: ...  # consola/red o logcat, video, trace
    async def cerrar(self) -> None: ...


def arbol_a_texto(elementos: Iterable[ElementoUI]) -> str:
    """Una línea por elemento: `[id] Clase "texto" @(x,y) clicable editable`."""
    lineas = []
    for el in elementos:
        clase = el.clase.rsplit(".", 1)[-1]
        x, y = el.centro
        marcas = " clicable" * el.clicable + " editable" * el.editable
        lineas.append(f'[{el.id}] {clase} "{el.texto or el.descripcion}" @({x},{y}){marcas}')
    return "\n".join(lineas)
