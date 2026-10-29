"""Contrato de resultado (FR-30): única fuente de verdad de aprobado / fallo / no concluyente."""

from typing import Literal

from dogfood.dominio import Ejecucion

Resultado = Literal["aprobado", "fallo", "no_concluyente"]


def resultado(e: Ejecucion) -> Resultado:
    hay_evidencia = any(p.captura for p in e.pasos)
    if e.estado == "error" or not hay_evidencia or (e.exito and not e.motivo_juez):
        return "no_concluyente"
    return "aprobado" if e.exito else "fallo"
