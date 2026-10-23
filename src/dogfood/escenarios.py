"""Carga de escenarios YAML y asignación determinista de escenarios a personas."""

import random
from pathlib import Path

import yaml
from pydantic import ValidationError

from dogfood.dominio import Escenario, Persona


def cargar(carpeta: Path) -> list[Escenario]:
    """Valida cada `*.yaml` de la carpeta; el error nombra el archivo y el campo."""
    salida = []
    for ruta in sorted(Path(carpeta).glob("*.yaml")):
        try:
            salida.append(Escenario.model_validate(yaml.safe_load(ruta.read_text("utf-8"))))
        except (ValidationError, yaml.YAMLError) as e:
            campos = (
                ", ".join(".".join(map(str, err["loc"])) or "?" for err in e.errors())
                if isinstance(e, ValidationError)
                else "yaml inválido"
            )
            raise ValueError(f"{ruta.name}: campo(s) {campos}: {e}") from e
    return salida


def _compatible(persona: Persona, esc: Escenario) -> bool:
    c = esc.persona_compatible
    return persona.destreza >= c.destreza_min and (
        not c.intencion or persona.intencion in c.intencion
    )


def compatibles(persona: Persona, escenarios: list[Escenario]) -> list[Escenario]:
    return [e for e in escenarios if _compatible(persona, e)]


def asignar(
    personas: list[Persona], escenarios: list[Escenario], semilla: int
) -> list[tuple[Persona, Escenario]]:
    """Cubre primero cada escenario (el de menos candidatas primero) y reparte el resto
    por rotación. Personas sin escenario compatible quedan fuera.
    """
    rng = random.Random(semilla)
    pers = sorted(personas, key=lambda p: p.id)
    escs = sorted(escenarios, key=lambda e: e.id)
    rng.shuffle(pers)
    libres = list(pers)
    elegido: dict[str, Escenario] = {}
    cuenta = {e.id: 0 for e in escs}
    # ponytail: greedy, no matching óptimo; puede dejar un escenario sin cubrir en casos adversos
    for e in sorted(escs, key=lambda e: sum(_compatible(p, e) for p in pers)):
        p = next((p for p in libres if _compatible(p, e)), None)
        if p:
            libres.remove(p)
            elegido[p.id] = e
            cuenta[e.id] += 1
    for p in libres:
        cand = compatibles(p, escs)
        if cand:
            e = min(cand, key=lambda e: cuenta[e.id])
            elegido[p.id] = e
            cuenta[e.id] += 1
    return [(p, elegido[p.id]) for p in sorted(personas, key=lambda p: p.id) if p.id in elegido]
