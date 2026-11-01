"""Plan de pruebas: un caso de prueba por asignación (escenario × persona)."""

from typing import Literal

from pydantic import BaseModel

from dogfood import escenarios as esc
from dogfood.dominio import DatosEscenario, Escenario, Persona

# Recorridos de dinero o datos: si fallan, el usuario pierde trabajo o plata.
SUPERFICIES_ALTA = {"registro", "subir", "analisis", "exportar"}

ROLES = {
    "analisis_completo": "Analista",
    "explorar": "Usuario curioso",
    "solo_exportar": "Usuario apurado",
    "confundirse": "Usuario confundido",
    "romper": "Usuario que intenta romperla",
}


class CasoPrueba(BaseModel):
    id: str
    titulo: str
    escenario_id: str
    persona_id: str
    persona_nombre: str
    objetivo: str
    criterio_exito: str
    prioridad: Literal["alta", "media"]
    superficies: list[str]
    datos: DatosEscenario | None = None
    ejecuciones: list[str] = []  # ids de las ejecuciones de este caso (una por repetición)


class PlanPruebas(BaseModel):
    objetivo: str
    semilla: int
    casos: list[CasoPrueba]
    avisos: list[str] = []


def prioridad(e: Escenario) -> Literal["alta", "media"]:
    return "alta" if SUPERFICIES_ALTA & set(e.superficies) else "media"


def _titulo(p: Persona, e: Escenario) -> str:
    accion = e.titulo[:1].lower() + e.titulo[1:]
    if e.datos and e.datos.defectos:
        accion += f" (CSV con {', '.join(e.datos.defectos)})"
    return f"{ROLES.get(p.intencion.value, 'Usuario')} de {p.rubro}, {p.idioma.value}, {accion}"


def plan_de(objetivo: str, semilla: int, asignacion: esc.Asignacion) -> PlanPruebas:
    return PlanPruebas(
        objetivo=objetivo,
        semilla=semilla,
        avisos=list(getattr(asignacion, "avisos", [])),
        casos=[
            CasoPrueba(
                id=f"{e.id}:{p.id}",
                titulo=_titulo(p, e),
                escenario_id=e.id,
                persona_id=p.id,
                persona_nombre=p.nombre,
                objetivo=e.objetivo.strip(),
                criterio_exito=e.criterio_exito.strip(),
                prioridad=prioridad(e),
                superficies=e.superficies,
                datos=e.datos,
            )
            for p, e in asignacion
        ],
    )


def armar_plan(
    objetivo: str, personas: list[Persona], escenarios: list[Escenario], semilla: int
) -> PlanPruebas:
    return plan_de(objetivo, semilla, esc.asignar(personas, escenarios, semilla))
