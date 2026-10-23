"""Fricciones de las personas -> hallazgos `friccion` (FR-16). Sin LLM: normalización + similitud de tokens."""

import re
import unicodedata

from dogfood.dominio import (
    ContextoDeteccion,
    Evidencia,
    Friccion,
    Gravedad,
    Hallazgo,
    TipoHallazgo,
)

UMBRAL_SIMILITUD = 0.5
MIN_PERSONAS_MEDIA = 5
_STOPWORDS = frozenset(
    [
        "a",
        "al",
        "algo",
        "con",
        "de",
        "del",
        "e",
        "el",
        "ela",
        "ele",
        "en",
        "es",
        "esta",
        "este",
        "eu",
        "la",
        "las",
        "lo",
        "los",
        "me",
        "mi",
        "muy",
        "na",
        "no",
        "o",
        "os",
        "para",
        "por",
        "que",
        "qual",
        "qué",
        "se",
        "su",
        "um",
        "uma",
        "un",
        "una",
        "y",
    ]
)


def _tokens(texto: str) -> frozenset[str]:
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    plano = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return frozenset(re.findall(r"\w+", plano)) - _STOPWORDS


def _similares(a: frozenset[str], b: frozenset[str]) -> bool:
    # ponytail: coeficiente de solapamiento, sin sinónimos; embeddings si agrupa mal
    if not a or not b:
        return a == b
    return len(a & b) / min(len(a), len(b)) >= UMBRAL_SIMILITUD


def detectar(ctx: ContextoDeteccion) -> list[Hallazgo]:
    # (ejecucion_id, persona_id, friccion)
    items: list[tuple[str, str, Friccion]] = []
    for e in ctx.ejecuciones:
        fricciones = list(e.fricciones)
        if e.estado == "rendido" and not fricciones:
            pantalla = e.pasos[-1].pantalla if e.pasos else "desconocida"
            fricciones = [
                Friccion(
                    texto=e.motivo_juez or "la persona se rindió",
                    severidad=Gravedad.baja,
                    pantalla=pantalla,
                )
            ]
        items += [(e.id, e.persona_id, f) for f in fricciones]

    # grupos: [pantalla, tokens del primero, miembros]
    grupos: list[tuple[str, frozenset[str], list[tuple[str, str, Friccion]]]] = []
    for item in items:
        toks = _tokens(item[2].texto)
        for pantalla, base, miembros in grupos:
            if pantalla == item[2].pantalla and _similares(base, toks):
                miembros.append(item)
                break
        else:
            grupos.append((item[2].pantalla, toks, [item]))

    hallazgos: list[Hallazgo] = []
    for pantalla, toks, miembros in grupos:
        personas = {p for _, p, _ in miembros}
        n = len(personas)
        primera = miembros[0][2]
        h = Hallazgo(
            tipo=TipoHallazgo.friccion,
            gravedad=Gravedad.media if n >= MIN_PERSONAS_MEDIA else Gravedad.baja,
            pantalla=pantalla,
            titulo=f"Fricción en {pantalla}: {primera.texto[:80]}",
            descripcion=f"{n} persona(s) distinta(s) tuvieron esta fricción: {primera.texto}",
            evidencia=[
                Evidencia(tipo="captura", ruta=f.captura) for _, _, f in miembros[:3] if f.captura
            ]
            + [Evidencia(tipo="texto", extracto=f.cita) for _, _, f in miembros[:3] if f.cita],
            ejecucion_id=miembros[0][0],
            semilla=ctx.corrida.semilla,
            commit=ctx.instancia.commit,
            solo_reporte=n < 2,
            ocurrencias=len(miembros),
        )
        h.huella = h.calcular_huella(" ".join(sorted(toks)))
        hallazgos.append(h)
    return hallazgos
