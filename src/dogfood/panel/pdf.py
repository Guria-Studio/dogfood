"""Reporte compartible de una corrida: datos JSON para la página «Reporte» y su PDF (Playwright)."""

import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from dogfood.config import Config
from dogfood.panel import consultas, detalle
from dogfood.panel.api_plan import HallazgoVista, _hallazgos

MAX_CITAS = 3


class CasoFallido(BaseModel):
    ejecucion_id: str
    titulo: str
    persona: str
    resultado: str
    miniatura: str | None


class Cita(BaseModel):
    texto: str
    cita: str
    severidad: str


class OpinionPantalla(BaseModel):
    pantalla: str
    total: int
    citas: list[Cita]


class Reporte(BaseModel):
    hallazgos: list[HallazgoVista]
    fallidos: list[CasoFallido]
    opiniones: list[OpinionPantalla]


def datos_reporte(raiz: Path, corrida_id: str, repo: str = "") -> Reporte:
    filas = [f for f in consultas.ejecuciones(raiz) if f.corrida_id == corrida_id]
    fallidos: list[CasoFallido] = []
    por_pantalla: dict[str, list[Cita]] = {}
    for f in filas:
        try:
            d = detalle.datos_ejecucion(raiz, f.id)
        except (HTTPException, OSError, ValueError, StopIteration):
            continue  # historial o personas ausentes/corruptos: el reporte sigue sin esa ejecución
        for pantalla, fs in d["fricciones"].items():
            por_pantalla.setdefault(pantalla, []).extend(
                Cita(texto=x["f"].texto, cita=x["f"].cita, severidad=x["f"].severidad.value)
                for x in fs
            )
        if f.resultado != "aprobado":
            capturas = [p["captura"] for p in d["pasos"] if p["captura"]]
            fallidos.append(
                CasoFallido(
                    ejecucion_id=f.id,
                    titulo=f.escenario_id,
                    persona=f.persona_nombre or f.persona_id,
                    resultado=f.resultado,
                    miniatura=capturas[-1] if capturas else None,
                )
            )
    opiniones = [
        OpinionPantalla(
            pantalla=p, total=len(cs), citas=[c for c in cs if c.cita][:MAX_CITAS] or cs[:MAX_CITAS]
        )
        for p, cs in sorted(por_pantalla.items(), key=lambda kv: -len(kv[1]))
    ]
    return Reporte(
        hallazgos=_hallazgos(raiz, corrida_id, repo), fallidos=fallidos, opiniones=opiniones
    )


def generar_pdf(url: str) -> bytes:
    """Abre `url` en Chromium sin cabeza y devuelve el PDF (A4, con fondos)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        try:
            pagina = navegador.new_page()
            pagina.goto(url, wait_until="networkidle")
            # la página marca data-listo cuando ya pintó los datos
            pagina.wait_for_selector("[data-reporte-listo]", timeout=15000)
            return pagina.pdf(format="A4", print_background=True)
        finally:
            navegador.close()


def registrar_pdf(app: FastAPI, raiz: Path, cfg: Config | None = None) -> None:
    repo = cfg.repo_issues if cfg else ""

    def existe(corrida_id: str) -> None:
        with closing(consultas._con(raiz)) as con:
            try:
                fila = con.execute("SELECT 1 FROM corridas WHERE id = ?", (corrida_id,)).fetchone()
            except sqlite3.Error:
                fila = None
        if fila is None:
            raise HTTPException(404, f"la corrida {corrida_id!r} no existe")

    @app.get("/api/corridas/{corrida_id}/reporte", response_model=Reporte)
    def api_reporte(corrida_id: str):
        existe(corrida_id)
        return datos_reporte(Path(raiz), corrida_id, repo)

    @app.get("/api/corridas/{corrida_id}/reporte.pdf")
    def api_reporte_pdf(corrida_id: str, request: Request):
        existe(corrida_id)
        base = str(request.base_url).rstrip("/")
        pdf = generar_pdf(f"{base}/corridas/{corrida_id}/reporte")
        return Response(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="reporte-{corrida_id}.pdf"'},
        )
