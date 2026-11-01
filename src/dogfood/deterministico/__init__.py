"""Motor determinista (FR-36): tests Patrol / `integration_test` generados o existentes."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from dogfood.contrato import Resultado

Herramienta = Literal["patrol", "integration_test"]


class ResultadoTest(BaseModel):
    nombre: str
    estado: Literal["ok", "fallo", "error", "saltado"]
    ms: int = 0
    mensaje: str = ""


class ResultadoDeterministico(BaseModel):
    herramienta: Herramienta
    codigo_salida: int | None  # None = timeout
    tests: list[ResultadoTest] = []
    motivo: str = ""  # compilacion | sin_dispositivo | timeout | sin_tests | app_sin_patrol
    log: Path
    reporte: Path | None = None
    captura_final: Path | None = None

    def resultado(self) -> Resultado:
        """aprobado: código 0, ≥1 test y todos ok; fallo: algún test en fallo; resto no_concluyente."""
        if any(t.estado == "fallo" for t in self.tests):
            return "fallo"
        todos_ok = self.tests and all(t.estado == "ok" for t in self.tests)
        if self.codigo_salida == 0 and todos_ok and not self.motivo:
            return "aprobado"
        return "no_concluyente"
