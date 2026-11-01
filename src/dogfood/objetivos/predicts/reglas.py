"""Reglas propias de predicts (FR-15), de «Reglas que no se negocian» de su CONTEXTO.md.

Las personas salen de `ctx.corrida.parametros["personas"]` (lista de `Persona` serializadas); sin
ellas no hay cliente de API ni idioma, y las reglas que los necesitan no se evalúan.
"""

import csv
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import httpx

from dogfood.dominio import (
    ContextoDeteccion,
    Ejecucion,
    Gravedad,
    Hallazgo,
    Persona,
    TipoHallazgo,
)
from dogfood.objetivos.predicts.cliente import ErrorSesion

_ID = r"([0-9A-Fa-f][0-9A-Fa-f-]{7,})"
_DATASET_MAPEO = re.compile(rf"/datasets/{_ID}/mapeo")
_ANALISIS = re.compile(rf"/analisis/{_ID}")

# Dominios de mensajería: coincide el dominio o cualquier subdominio.
DOMINIOS_MENSAJERIA = (
    "whatsapp.com", "whatsapp.net", "wa.me", "sendgrid.net", "sendgrid.com", "mailgun.net",
    "mailgun.org", "mailchimp.com", "mandrillapp.com", "postmarkapp.com", "sparkpostmail.com",
    "resend.com", "brevo.com", "sendinblue.com", "mailjet.com", "twilio.com",
)  # fmt: skip
PUERTOS_SMTP = {25, 465, 587, 2525}

_PALABRAS = {
    "pt": [
        # «o» y «se» también son del español: quedan en _COMUNES y no cuentan (F10.1.T3: «revise
        # o que…» salía como español). «e» (y) es solo del portugués.
        "o",
        "e",
        "se",
        "não",
        "você",
        "uma",
        "um",
        "uns",
        "para",
        "com",
        "os",
        "as",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "é",
        "são",
        "está",
        "seu",
        "sua",
        "ao",
        "pelo",
        "mais",
        "mas",
        "ou",
        "ser",
        "foi",
        "tem",
        "nos",
        "já",
        "também",
        "quando",
        "isso",
        "este",
        "esta",
        "nesta",
        "cada",
        "sem",
        "sobre",
        "ainda",
    ],
    "es": [
        "no",
        "usted",
        "una",
        "un",
        "unos",
        "para",
        "con",
        "los",
        "las",
        "del",
        "el",
        "es",
        "son",
        "está",
        "su",
        "sus",
        "al",
        "más",
        "pero",
        "o",
        "se",
        "lo",
        "como",
        "tu",
        "tus",
        "ya",
        "también",
        "cuando",
        "eso",
        "este",
        "esta",
        "cada",
        "sin",
        "sobre",
        "aún",
        "por",
        "y",
    ],
    "en": [
        "the",
        "and",
        "of",
        "to",
        "is",
        "are",
        "you",
        "your",
        "for",
        "with",
        "this",
        "that",
        "in",
        "on",
        "it",
        "be",
        "as",
        "at",
        "by",
        "from",
        "or",
        "not",
        "has",
        "have",
        "will",
        "can",
        "when",
        "each",
        "without",
        "about",
        "still",
        "an",
        "was",
        "were",
    ],
}
_COMUNES = set.intersection(*(set(v) for v in _PALABRAS.values())) | (
    set(_PALABRAS["pt"]) & set(_PALABRAS["es"])
)
_PALABRAS = {k: set(v) - _COMUNES for k, v in _PALABRAS.items()}
_IDIOMA_PERSONA = {"pt-BR": "pt", "es": "es"}
MIN_PALABRAS_FRASE = 4  # frases cortas son nombres de producto o marca («Online Retail II»)
MIN_ACIERTOS = 2


def idioma_de_frase(frase: str) -> str | None:
    """Idioma (`pt`, `es`, `en`) con más palabras frecuentes en `frase`; `None` si no hay claro."""
    palabras = re.findall(r"[^\W\d_]+", frase.lower())
    if len(palabras) < MIN_PALABRAS_FRASE:
        return None
    puntaje = {k: sum(p in v for p in palabras) for k, v in _PALABRAS.items()}
    mejor = max(puntaje, key=lambda k: puntaje[k])
    segundo = sorted(puntaje.values())[-2]
    return mejor if puntaje[mejor] >= MIN_ACIERTOS and puntaje[mejor] > segundo else None


def idiomas_intrusos(texto: str, idioma_persona: str) -> dict[str, str]:
    """`{idioma: primera frase}` de las frases de `texto` en otro idioma que `idioma_persona`."""
    propio = _IDIOMA_PERSONA.get(idioma_persona, idioma_persona)
    intrusos: dict[str, str] = {}
    for frase in re.split(r"(?<=[.!?])\s+|\n+", texto):
        idioma = idioma_de_frase(frase)
        if idioma and idioma != propio:
            intrusos.setdefault(idioma, frase.strip())
    return intrusos


def dominio_de_mensajeria(url: str) -> str | None:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    if host.startswith(("smtp.", "smtp-")) or u.port in PUERTOS_SMTP:
        return host
    es = any(host == d or host.endswith("." + d) for d in DOMINIOS_MENSAJERIA)
    return host if es or re.fullmatch(r"email(-smtp)?\.[\w-]+\.amazonaws\.com", host) else None


def conteo_compras(ruta_csv) -> dict[tuple[str, str], int]:
    """Días distintos de compra por (cliente, producto) en el CSV subido."""
    dias: dict[tuple[str, str], set[str]] = defaultdict(set)
    with open(ruta_csv, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            dias[(r.get("customer_id", ""), r.get("product", ""))].add(r.get("date", ""))
    return {k: len(v) for k, v in dias.items()}


def filas_exportadas(contenido: bytes) -> list[dict]:
    """Filas del export de recordatorios con las claves de recompra, sea cual sea el idioma."""
    texto = contenido.decode("utf-8-sig")
    sep = ";" if texto.split("\n", 1)[0].count(";") > texto.split("\n", 1)[0].count(",") else ","
    lector = csv.reader(io.StringIO(texto), delimiter=sep)
    next(lector, None)  # el orden de las columnas es fijo; los nombres cambian con el idioma
    return [
        {
            "cliente_id": f[0],
            "producto_nombre": f[2],
            "fecha_probable": f[3] or None,
            "fecha_min": f[4] or None,
            "fecha_max": f[5] or None,
        }
        for f in lector
        if len(f) >= 6
    ]


def sin_historia(
    filas: list[dict], conteo: dict[tuple[str, str], int], min_compras: int
) -> list[dict]:
    """Filas con `fecha_probable` cuyo cliente tiene menos de `min_compras` compras en el CSV."""
    return [
        f
        for f in filas
        if f.get("fecha_probable")
        and (n := conteo.get((f["cliente_id"], f.get("producto_nombre", "")))) is not None
        and n < min_compras
    ]


def sin_evidencia(filas: list[dict]) -> list[dict]:
    return [
        f for f in filas if any(f.get(c) is None for c in ("n_compras", "fecha_min", "fecha_max"))
    ]


def mapeo_bajo_umbral(mapeo: dict, umbral: float) -> list[str]:
    bajo = [c["columna"] for c in mapeo.get("columnas", []) if c["confianza"] < umbral]
    tipo = mapeo.get("producto_id_tipo")
    if tipo and tipo.get("origen") == "jev" and tipo["confianza"] < umbral:
        bajo.append("producto_id_tipo")
    return bajo


def confirmo_mapeo(e: Ejecucion) -> bool:
    return any(p.pantalla == "mapeo" and "confirm" in p.accion.lower() for p in e.pasos)


def aplico_mapeo(e: Ejecucion) -> bool:
    # ponytail: «aplicado» = hay pasos en una pantalla posterior al mapeo; no se parsea la red
    vio = False
    for p in e.pasos:
        vio = vio or p.pantalla == "mapeo"
        if vio and p.pantalla not in ("mapeo", "subir"):
            return True
    return False


def _id_en_pasos(e: Ejecucion, patron: re.Pattern) -> str | None:
    return next((m.group(1) for p in e.pasos if (m := patron.search(p.url))), None)


def _hallazgo(
    ctx: ContextoDeteccion, e: Ejecucion | None, gravedad: Gravedad, pantalla: str, titulo: str,
    descripcion: str, firma: str, esperado: str | None = None, obtenido: str | None = None,
) -> Hallazgo:  # fmt: skip
    h = Hallazgo(
        tipo=TipoHallazgo.regla,
        gravedad=gravedad,
        pantalla=pantalla,
        titulo=titulo,
        descripcion=descripcion,
        esperado=esperado,
        obtenido=obtenido,
        ejecucion_id=e.id if e else None,
        semilla=ctx.corrida.semilla,
        commit=ctx.instancia.commit,
    )
    h.huella = h.calcular_huella(firma)
    return h


def _personas(ctx: ContextoDeteccion) -> dict[str, Persona]:
    """De `corrida.parametros["personas"]` o, si no están (la corrida real no las pone ahí), del
    `personas.json` de la corrida: `runs/<corrida>/ejecuciones/<id>/historial.json` → `runs/<corrida>`.
    """
    lista = ctx.corrida.parametros.get("personas")
    if not lista:
        rutas = [Path(e.ruta_historial).parents[2] for e in ctx.ejecuciones if e.ruta_historial]
        rutas += [Path(ds.ruta_verdad).parents[2] for ds in ctx.datasets.values()]
        archivo = next((r / "personas.json" for r in rutas if (r / "personas.json").exists()), None)
        lista = json.loads(archivo.read_text()) if archivo else []
    return {p.id: p for p in (Persona.model_validate(x) for x in lista)}


def _umbral(ctx: ContextoDeteccion, nombre: str, defecto: float) -> float:
    return float(ctx.instancia.parametros.get(nombre, defecto))


def _regla_datos(ctx, e, persona, min_compras, umbral_mapeo) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    cliente = ctx.cliente_api(persona)
    analisis = _id_en_pasos(e, _ANALISIS)
    if analisis and (ds := ctx.datasets.get(e.dataset_id or "")):
        filas = cliente.resultados(analisis, "recompra")
        fuentes = {
            "recompra": filas,
            "export": filas_exportadas(cliente.exportar(analisis, "recordatorios")),
        }
        conteo = conteo_compras(ds.ruta_csv)
        for fuente, rows in fuentes.items():
            malas = sin_historia(rows, conteo, min_compras)
            if malas:
                m = malas[0]
                out.append(
                    _hallazgo(
                        ctx, e, Gravedad.alta, "resultados",
                        f"predicción sin historia suficiente ({fuente})",
                        f"{len(malas)} filas con `fecha_probable` para clientes con menos de "
                        f"{min_compras} compras en el CSV subido. Ejemplo: cliente "
                        f"{m['cliente_id']}, producto {m.get('producto_nombre')}.",
                        f"historia insuficiente|{fuente}",
                        esperado=f"sin fecha_probable con menos de {min_compras} compras",
                        obtenido=f"fecha_probable {m['fecha_probable']}",
                    )
                )  # fmt: skip
        malas = sin_evidencia(filas)
        if malas:
            campos = sorted(
                c
                for c in ("n_compras", "fecha_min", "fecha_max")
                if any(f.get(c) is None for f in malas)
            )
            out.append(
                _hallazgo(
                    ctx, e, Gravedad.media, "resultados", "recompra sin evidencia o incertidumbre",
                    f"{len(malas)} filas de recompra sin {', '.join(campos)}.",
                    "evidencia|" + ",".join(campos),
                    esperado="n_compras, fecha_min y fecha_max no nulos",
                    obtenido="nulos en " + ", ".join(campos),
                )
            )  # fmt: skip
    dataset = _id_en_pasos(e, _DATASET_MAPEO)
    if dataset and not confirmo_mapeo(e) and aplico_mapeo(e):
        bajo = mapeo_bajo_umbral(cliente.mapeo(dataset), umbral_mapeo)
        if bajo:
            out.append(
                _hallazgo(
                    ctx, e, Gravedad.alta, "mapeo", "mapeo de Jev bajo el umbral sin confirmar",
                    f"Sugerencias con confianza menor que {umbral_mapeo} ({', '.join(bajo)}) "
                    "se aplicaron sin paso de confirmación de la persona.",
                    "jev bajo el umbral",
                    esperado="la persona confirma las sugerencias bajo el umbral",
                    obtenido="aplicadas sin paso de confirmación",
                )
            )  # fmt: skip
    return out


def verificar(ctx: ContextoDeteccion) -> list[Hallazgo]:
    personas = _personas(ctx)
    min_compras = int(_umbral(ctx, "MIN_COMPRAS", 3))
    umbral_mapeo = _umbral(ctx, "CONFIANZA_MAPEO", 0.7)
    hallazgos: list[Hallazgo] = []
    mensajeria: dict[str, int] = defaultdict(int)
    for e in ctx.ejecuciones:
        persona = personas.get(e.persona_id)
        if persona:
            try:
                hallazgos += _regla_datos(ctx, e, persona, min_compras, umbral_mapeo)
            except (httpx.HTTPError, ErrorSesion):
                pass  # sin API no hay datos que verificar; los fallos de red los reporta `tecnicos`
            vistos: set[tuple[str, str]] = set()
            for p in e.pasos:
                for idioma, frase in idiomas_intrusos(p.texto_visible, persona.idioma).items():
                    if (p.pantalla, idioma) in vistos:
                        continue
                    vistos.add((p.pantalla, idioma))
                    hallazgos.append(
                        _hallazgo(
                            ctx, e, Gravedad.baja, p.pantalla, "mezcla de idiomas en la pantalla",
                            f"La persona usa {persona.idioma} y la pantalla muestra texto en "
                            f"`{idioma}`: «{frase[:120]}».",
                            f"idioma intruso|{idioma}",
                        )
                    )  # fmt: skip
        for r in e.red:
            if host := dominio_de_mensajeria(r.url):
                mensajeria[host] += 1
    for host, n in mensajeria.items():
        hallazgos.append(
            _hallazgo(
                ctx, None, Gravedad.critica, "red", "el sistema envió o intentó enviar mensajes",
                f"{n} peticiones a `{host}` durante la corrida; el MVP solo sugiere y exporta.",
                f"mensajería|{host}",
                esperado="ninguna petición a dominios de mensajería",
                obtenido=f"{n} peticiones a {host}",
            )
        )  # fmt: skip
    return hallazgos
