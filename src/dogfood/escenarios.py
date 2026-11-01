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


class Asignacion(list):
    """Lista de (persona, escenario) con `avisos` y `notas` (persona.id -> nota)."""

    def __init__(self, pares=()):
        super().__init__(pares)
        self.avisos: list[str] = []
        self.notas: dict[str, str] = {}


def _distancia(persona: Persona, esc: Escenario) -> int:
    c = esc.persona_compatible
    return (1 if c.intencion and persona.intencion not in c.intencion else 0) + max(
        0, c.destreza_min - persona.destreza
    )


def asignar(personas: list[Persona], escenarios: list[Escenario], semilla: int) -> Asignacion:
    """Asigna un escenario a toda persona y cubre cuantos escenarios se pueda.

    Causa de la corrida 20261101-125232-2-85b1 (10 personas, 8 ejecuciones): (1) P004 y P008
    tienen intención `solo_exportar`, que ningún YAML de predicts admite, y la versión anterior
    dejaba fuera a quien no tuviera escenario compatible; (2) `plantillas-mensaje` y
    `ofertas-con-lista` exigen `analisis_completo` con destreza >= 3 y solo P006 lo cumple, así
    que una de las dos no puede cubrirse con esas personas; (3) el greedy fijaba a la primera
    candidata libre sin reasignar, así que podía dejar escenarios sin cubrir.

    Ahora: matching bipartito máximo (caminos aumentantes, Kuhn) escenario-persona; el resto
    de personas va al compatible menos cubierto y, si no hay ninguno, al más cercano (priorizando escenarios aún sin cubrir) por
    intención/destreza, con una nota. Un escenario sin cubrir genera un aviso.
    """
    rng = random.Random(semilla)
    pers = sorted(personas, key=lambda p: p.id)
    escs = sorted(escenarios, key=lambda e: e.id)
    rng.shuffle(pers)
    cand = {e.id: [p for p in pers if _compatible(p, e)] for e in escs}
    dueno: dict[str, Escenario] = {}  # persona.id -> escenario del matching

    def aumentar(e: Escenario, vistas: set[str]) -> bool:
        for p in cand[e.id]:
            if p.id in vistas:
                continue
            vistas.add(p.id)
            previo = dueno.get(p.id)
            if previo is None or aumentar(previo, vistas):
                dueno[p.id] = e
                return True
        return False

    for e in sorted(escs, key=lambda e: len(cand[e.id])):  # los más escasos primero
        aumentar(e, set())

    res = Asignacion()
    cuenta = {e.id: 0 for e in escs}
    for e in dueno.values():
        cuenta[e.id] += 1
    elegido = dict(dueno)
    # sobrantes: primero un escenario aún sin cubrir (compatible si hay; si no, el más cercano
    # con una nota); sin descubiertos, el compatible menos cubierto o el más cercano.
    sobrantes = [p for p in pers if p.id not in elegido]
    sobrantes.sort(key=lambda p: not compatibles(p, escs))  # estable: compatibles primero
    for p in sobrantes if escs else []:
        libres = [e for e in escs if cuenta[e.id] == 0]
        c = compatibles(p, libres or escs)
        if c:
            e = min(c, key=lambda e: (cuenta[e.id], e.id))
        else:
            e = min(libres or escs, key=lambda e: (_distancia(p, e), cuenta[e.id], e.id))
            res.notas[p.id] = f"sin escenario compatible; asignado el más cercano ({e.id})"
        elegido[p.id] = e
        cuenta[e.id] += 1

    for e in escs:
        if cuenta[e.id] == 0:
            res.avisos.append(
                f"escenario {e.id} sin personas compatibles"
                if not cand[e.id]
                else f"escenario {e.id} sin cubrir: sus personas compatibles cubren otros escenarios"
            )
    res.extend((p, elegido[p.id]) for p in sorted(personas, key=lambda p: p.id) if p.id in elegido)
    return res
