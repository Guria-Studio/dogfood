"""API de la base de conocimiento: Markdown de docs/ayuda y docs/ops, sin base de datos."""

import re
import unicodedata
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_SECCIONES = ("empezar", "guias", "referencia")
_MAX = 20


class DocAyuda(BaseModel):
    slug: str
    titulo: str
    seccion: str
    orden: int
    pantallas: list[str]


class DocCompleto(BaseModel):
    doc: DocAyuda
    markdown: str


class Resultado(BaseModel):
    slug: str
    titulo: str
    fragmento: str
    puntaje: int


def _norm(texto: str) -> str:
    """Minúsculas y sin acentos, con la misma longitud (para ubicar fragmentos)."""
    return "".join(
        c if len(d := unicodedata.normalize("NFD", c)) == 1 else d[0] for c in texto.lower()
    )


def _parsear(slug: str, texto: str) -> tuple[DocAyuda, str]:
    meta: dict = {}
    cuerpo = texto
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?", texto, re.DOTALL)
    if m:
        try:
            cargado = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            cargado = None
        if isinstance(cargado, dict):
            meta, cuerpo = cargado, texto[m.end() :]
    h1 = re.search(r"^#\s+(.+)$", cuerpo, re.MULTILINE)
    try:
        orden = int(meta.get("orden", 100))
    except (TypeError, ValueError):
        orden = 100
    doc = DocAyuda(
        slug=slug,
        titulo=str(meta.get("titulo") or (h1.group(1).strip() if h1 else slug)),
        seccion=str(meta.get("seccion", "guias")),
        orden=orden,
        pantallas=[str(p) for p in meta.get("pantallas") or []],
    )
    return doc, texto if not m or not meta else cuerpo


class _Indice:
    def __init__(self, raiz_repo: Path) -> None:
        self.carpetas = [(raiz_repo / "docs" / "ayuda", ""), (raiz_repo / "docs" / "ops", "ops-")]
        self.firma: tuple = ()
        self.docs: dict[str, tuple[DocAyuda, str]] = {}

    def _archivos(self) -> list[tuple[Path, str]]:
        return [
            (p, pref + p.stem)
            for carpeta, pref in self.carpetas
            if carpeta.is_dir()
            for p in sorted(carpeta.glob("*.md"))
        ]

    def obtener(self) -> dict[str, tuple[DocAyuda, str]]:
        archivos = self._archivos()
        firma = tuple((p, p.stat().st_mtime_ns) for p, _ in archivos)
        if firma != self.firma:
            self.docs = {
                slug: _parsear(slug, p.read_text(encoding="utf-8")) for p, slug in archivos
            }
            self.firma = firma
        return self.docs

    def lista(self) -> list[DocAyuda]:
        docs = [d for d, _ in self.obtener().values()]
        pos = {s: i for i, s in enumerate(_SECCIONES)}
        return sorted(docs, key=lambda d: (pos.get(d.seccion, len(pos)), d.orden, d.slug))


def _buscar(docs: dict[str, tuple[DocAyuda, str]], q: str) -> list[Resultado]:
    q = _norm(q.strip())
    if len(q) < 2:
        return []
    salida = []
    for doc, md in docs.values():
        cuerpo = _norm(md)
        encabezados = " ".join(re.findall(r"^#+\s+(.*)$", cuerpo, re.MULTILINE))
        puntaje = 3 * (q in _norm(doc.titulo)) + 2 * (q in encabezados) + (q in cuerpo)
        if not puntaje:
            continue
        i = cuerpo.find(q)
        ini = max(0, i - 80) if i >= 0 else 0
        frag = " ".join(md[ini : ini + 160].split())
        salida.append(Resultado(slug=doc.slug, titulo=doc.titulo, fragmento=frag, puntaje=puntaje))
    salida.sort(key=lambda r: (-r.puntaje, r.slug))
    return salida[:_MAX]


def registrar_ayuda(app: FastAPI, raiz_repo: Path) -> None:
    indice = _Indice(Path(raiz_repo))

    @app.get("/api/ayuda", response_model=list[DocAyuda])
    def listar(pantalla: str = ""):
        return [d for d in indice.lista() if not pantalla or pantalla in d.pantallas]

    # /buscar antes de /{slug}: si no, «buscar» sería un slug
    @app.get("/api/ayuda/buscar", response_model=list[Resultado])
    def buscar(q: str = ""):
        return _buscar(indice.obtener(), q)

    @app.get("/api/ayuda/{slug}", response_model=DocCompleto)
    def documento(slug: str):
        # el slug es clave del índice: lo que no esté ahí (incluidos «/» y «..») da 404
        encontrado = indice.obtener().get(slug)
        if encontrado is None:
            raise HTTPException(404, f"documento {slug!r} no existe")
        return DocCompleto(doc=encontrado[0], markdown=encontrado[1])
