"""Modelos de dominio: el contrato compartido por todas las fases. Sin lógica de negocio."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_TEXTO_VISIBLE = 4000

Plataforma = Literal["web", "android", "ios"]


class Idioma(StrEnum):
    pt_BR = "pt-BR"
    es = "es"


class Intencion(StrEnum):
    analisis_completo = "analisis_completo"
    explorar = "explorar"
    solo_exportar = "solo_exportar"
    confundirse = "confundirse"
    romper = "romper"


class Gravedad(StrEnum):
    """Ordenable por severidad: `critica > alta > media > baja`."""

    critica = "critica"
    alta = "alta"
    media = "media"
    baja = "baja"

    @property
    def rango(self) -> int:
        return _RANGO_GRAVEDAD[self]

    def __lt__(self, otro: object) -> bool:
        if not isinstance(otro, Gravedad):
            return NotImplemented
        return self.rango < otro.rango

    def __le__(self, otro: object) -> bool:
        if not isinstance(otro, Gravedad):
            return NotImplemented
        return self.rango <= otro.rango

    def __gt__(self, otro: object) -> bool:
        if not isinstance(otro, Gravedad):
            return NotImplemented
        return self.rango > otro.rango

    def __ge__(self, otro: object) -> bool:
        if not isinstance(otro, Gravedad):
            return NotImplemented
        return self.rango >= otro.rango


_RANGO_GRAVEDAD = {Gravedad.baja: 0, Gravedad.media: 1, Gravedad.alta: 2, Gravedad.critica: 3}


class TipoHallazgo(StrEnum):
    tecnico = "tecnico"
    logica = "logica"
    aislamiento = "aislamiento"
    regla = "regla"
    friccion = "friccion"
    accesibilidad = "accesibilidad"


class Persona(BaseModel):
    id: str
    nombre: str
    email: str
    contrasena: str
    empresa: str
    rubro: str
    idioma: Idioma
    destreza: int = Field(ge=1, le=5)
    paciencia: int = Field(ge=1, le=5)
    intencion: Intencion
    estilo: list[str] = []
    semilla: int


class CompatibilidadPersona(BaseModel):
    intencion: list[Intencion] = []
    destreza_min: int = Field(default=1, ge=1, le=5)


class DatosEscenario(BaseModel):
    perfil: str
    clientes: int = Field(gt=0)
    defectos: list[str] = []


class ContratoRecorrido(BaseModel):
    estado_inicial: str = ""
    acciones: list[str] = []
    resultado_esperado: str = ""
    evidencia_requerida: list[str] = []


class PasoDeterministico(BaseModel):
    accion: Literal["tocar", "escribir", "esperar_texto", "ver_texto", "deslizar", "volver"]
    key: str | None = None  # ValueKey / Semantics(identifier:) del widget
    texto: str | None = None  # texto visible a buscar
    valor: str | None = None  # lo que se escribe; "{env:NOMBRE}" → String.fromEnvironment
    timeout_s: float = 10


class RecorridoDeterministico(BaseModel):
    archivo: str | None = None  # test existente, relativo a la raíz de la app
    pasos: list[PasoDeterministico] = []  # si no hay archivo, se genera
    dart_defines: dict[str, str] = {}  # literales o "{env:NOMBRE}" (secretos de ~/.config/dogfood)


class CoberturaSemantica(BaseModel):
    flutter: bool = False
    nodos: int = 0  # nodos de la app (bajo FlutterView, o todos si no es Flutter)
    interactivos: int = 0  # clicables, editables, enfocables o desplazables
    etiquetados: int = 0  # interactivos con texto o content-desc/label
    con_id: int = 0  # interactivos con resource-id / identifier estable
    ratio_etiqueta: float = 1.0  # etiquetados / interactivos (1.0 si no hay interactivos)
    ratio_id: float = 1.0
    ciega: bool = False  # flutter y (nodos == 0 o ratio_etiqueta < umbral)


class Escenario(BaseModel):
    id: str
    titulo: str
    superficies: list[str] = []
    persona_compatible: CompatibilidadPersona = CompatibilidadPersona()
    datos: DatosEscenario | None = None
    objetivo: str
    criterio_exito: str
    max_pasos: int = Field(default=60, gt=0)
    carril: Literal["normal", "login_fallido"] = "normal"
    contrato: ContratoRecorrido | None = None
    driver: Plataforma = "web"
    motor: Literal["browser_use", "bucle", "patrol", "integration_test"] | None = None
    deterministico: RecorridoDeterministico | None = None


class DatasetSintetico(BaseModel):
    id: str
    perfil: str
    ruta_csv: Path
    ruta_verdad: Path
    defectos: list[str] = []
    n_clientes: int
    n_filas: int
    semilla: int


class Paso(BaseModel):
    n: int
    url: str
    pantalla: str
    accion: str
    captura: Path | None = None
    texto_visible: str = ""
    ts: datetime
    razonamiento: str = ""
    paso_contrato: str = ""
    esperado: str = ""
    observado: str = ""
    arbol: Path | None = None
    punto: tuple[int, int] | None = None

    @field_validator("texto_visible")
    @classmethod
    def _recortar(cls, v: str) -> str:
        return v[:MAX_TEXTO_VISIBLE]


class EventoRed(BaseModel):
    metodo: str
    url: str
    estado: int
    ms: float


class EventoConsola(BaseModel):
    nivel: str
    texto: str
    url: str = ""


class Friccion(BaseModel):
    texto: str
    severidad: Gravedad
    pantalla: str
    captura: Path | None = None
    cita: str = ""


class Evidencia(BaseModel):
    tipo: Literal["captura", "log", "red", "csv", "texto", "video", "trace"]
    ruta: Path | None = None
    extracto: str = ""


class MetricasEjecucion(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    capturas: int = 0
    costo_usd: float = 0.0
    costo_equivalente_usd: float = 0.0


class Ejecucion(BaseModel):
    id: str
    persona_id: str
    escenario_id: str
    dataset_id: str | None = None
    modelo: str
    estado: Literal["ok", "fallo", "rendido", "error"]
    pasos: list[Paso] = []
    red: list[EventoRed] = []
    consola: list[EventoConsola] = []
    fricciones: list[Friccion] = []
    descargas: list[Path] = []
    exito: bool = False
    motivo_juez: str = ""
    duracion_s: float = 0.0
    ruta_historial: Path | None = None
    empresa_id: str | None = None
    notas: list[str] = []
    driver: Plataforma = "web"
    motor: str = "browser_use"
    backend: str = "api"
    resultado: Literal["aprobado", "fallo", "no_concluyente"] | None = None
    metricas: MetricasEjecucion = Field(default_factory=MetricasEjecucion)
    video: Path | None = None
    trace: Path | None = None
    evidencia_driver: list[Evidencia] = []


class Hallazgo(BaseModel):
    tipo: TipoHallazgo
    gravedad: Gravedad
    pantalla: str
    titulo: str
    descripcion: str
    pasos: list[str] = []
    evidencia: list[Evidencia] = []
    esperado: str | None = None
    obtenido: str | None = None
    huella: str = ""
    ejecucion_id: str | None = None
    semilla: int
    commit: str
    solo_reporte: bool = False
    ocurrencias: int = 1

    def calcular_huella(self, firma: str) -> str:
        """sha1 de `tipo|pantalla|firma`; la firma ya viene normalizada por el detector."""
        return hashlib.sha1(f"{self.tipo}|{self.pantalla}|{firma}".encode()).hexdigest()


class UsoLlm(BaseModel):
    rol: str
    modelo: str
    tokens_in: int
    tokens_out: int
    costo_usd: float
    ejecucion_id: str | None = None
    backend: str = "api"
    costo_equivalente_usd: float = 0.0


class Corrida(BaseModel):
    id: str
    objetivo: str
    ref: str
    commit: str
    semilla: int
    inicio: datetime
    fin: datetime | None = None
    estado: str
    parametros: dict[str, Any] = {}
    version_app: str | None = None


class Instancia(BaseModel):
    base_url: str
    api_url: str
    proyecto_compose: str
    commit: str
    parametros: dict[str, Any] = {}


@dataclass
class ContextoDeteccion:
    corrida: Corrida
    instancia: Instancia
    ejecuciones: list[Ejecucion]
    datasets: dict[str, DatasetSintetico]
    cliente_api: Callable[[Persona], Any]  # persona -> cliente HTTP del objetivo
    logs: dict[str, str]
