"""Personas deterministas por semilla, sin LLM (FR-8, D5)."""

import random
import re
import string
import unicodedata

from dogfood.dominio import Idioma, Intencion, Persona
from dogfood.personas.nombres import APELLIDOS, EMPRESAS, NOMBRES, RUBROS

DOMINIO = "dogfood.test"
RASGOS = [
    "apurado",
    "lee_todo",
    "faltas_ortografia",
    "movil",
    "cambia_de_opinion",
    "curioso",
    "desconfiado",
]


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", ".", base.lower()).strip(".")


def _contrasena(rng: random.Random) -> str:
    clases = [string.ascii_lowercase, string.ascii_uppercase, string.digits, "!#$%&*?"]
    chars = [rng.choice(c) for c in clases] + [rng.choice("".join(clases)) for _ in range(12)]
    rng.shuffle(chars)
    return "".join(chars)


def _reparto(n: int, idiomas: dict[str, float]) -> list[str]:
    """Lista de idiomas con conteos exactos (método del resto mayor)."""
    total = sum(idiomas.values())
    cuotas = {k: n * v / total for k, v in idiomas.items()}
    conteos = {k: int(c) for k, c in cuotas.items()}
    resto = sorted(cuotas, key=lambda k: cuotas[k] - conteos[k], reverse=True)
    for k in resto[: n - sum(conteos.values())]:
        conteos[k] += 1
    return [k for k, c in conteos.items() for _ in range(c)]


def generar(n: int, semilla: int, idiomas: dict[str, float] | None = None) -> list[Persona]:
    idiomas = idiomas or {"pt-BR": 0.5, "es": 0.5}
    for k in idiomas:
        Idioma(k)  # falla si el idioma no existe
    rng = random.Random(semilla)
    langs = _reparto(n, idiomas)
    intenciones = list(Intencion)
    ints = [intenciones[i % len(intenciones)] for i in range(n)]
    rng.shuffle(langs)
    rng.shuffle(ints)
    personas = []
    for i in range(n):
        lang = langs[i]
        sub = random.Random(f"{semilla}:{i}")
        nombre = f"{sub.choice(NOMBRES[lang])} {sub.choice(APELLIDOS[lang])}"
        rubro = sub.choice(RUBROS)
        empresa = EMPRESAS[lang][rubro].format(a=sub.choice(APELLIDOS[lang]))
        k = sub.randint(0, 3)
        estilo = sorted(sub.sample(RASGOS, k))
        personas.append(
            Persona(
                id=f"P{i + 1:03d}",
                nombre=nombre,
                email=f"{_slug(nombre)}.{i + 1}@{DOMINIO}",
                contrasena=_contrasena(sub),
                empresa=empresa,
                rubro=rubro,
                idioma=Idioma(lang),
                destreza=sub.randint(1, 5),
                paciencia=sub.randint(1, 5),
                intencion=ints[i],
                estilo=estilo,
                semilla=sub.randrange(2**31),
            )
        )
    return personas
