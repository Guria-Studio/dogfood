"""Detalle de una ejecución: paso a paso con evidencia, video, opinión y «Crear issue» (FR-32, FR-33)."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

from dogfood.config import Config
from dogfood.dominio import (
    Corrida,
    Ejecucion,
    EventoConsola,
    EventoRed,
    Gravedad,
    Paso,
    Persona,
    TipoHallazgo,
)
from dogfood.panel import consultas, issue

# Nunca se sirven aunque estén dentro de la raíz: la base y las personas llevan contraseñas.
_PROHIBIDOS = ("dogfood.db", "personas.json")


def _jsonl(ruta: Path, modelo) -> list:
    if not ruta.is_file():
        return []
    return [modelo.model_validate_json(x) for x in ruta.read_text().splitlines() if x.strip()]


def _url(ruta: Path | None, raiz: Path, carpeta: Path) -> str | None:
    """URL de `/archivos/` para un archivo de la ejecución, o None si no está bajo `raiz`."""
    if ruta is None:
        return None
    p = Path(ruta)
    for candidato in (p, raiz / p, carpeta / "capturas" / p.name, carpeta / p.name):
        try:
            return "/archivos/" + candidato.resolve().relative_to(raiz.resolve()).as_posix()
        except ValueError:
            continue
    return None


def _cargar(raiz: Path, ejecucion_id: str) -> tuple[Ejecucion, Corrida, Persona, Path]:
    with consultas._con(raiz) as con:
        fila = con.execute(
            "SELECT corrida_id FROM ejecuciones WHERE id = ?", (ejecucion_id,)
        ).fetchone()
    if fila is None:
        raise HTTPException(404, f"ejecución {ejecucion_id!r} no existe")
    cdir = raiz / fila["corrida_id"]
    carpeta = cdir / "ejecuciones" / ejecucion_id
    e = Ejecucion.model_validate_json((carpeta / "historial.json").read_text())
    corrida = Corrida.model_validate_json((cdir / "corrida.json").read_text())
    persona = next(
        Persona.model_validate(p)
        for p in json.loads((cdir / "personas.json").read_text())
        if p["id"] == e.persona_id
    )
    return e, corrida, persona, carpeta


def registrar_rutas(app: FastAPI, plantillas: Jinja2Templates, raiz: Path) -> None:
    @app.get("/ejecuciones/{ejecucion_id}")
    def ejecucion(request: Request, ejecucion_id: str):
        e, corrida, persona, carpeta = _cargar(raiz, ejecucion_id)
        pasos: list[Paso] = _jsonl(carpeta / "pasos.jsonl", Paso) or e.pasos
        red: list[EventoRed] = _jsonl(carpeta / "red.jsonl", EventoRed) or e.red
        consola: list[EventoConsola] = _jsonl(carpeta / "consola.jsonl", EventoConsola) or e.consola
        logcat = carpeta / "logcat.txt"
        lineas = logcat.read_text(errors="replace").splitlines() if logcat.is_file() else []
        graves = [x for x in lineas if x.startswith("E/") or "FATAL" in x]
        vistas = [
            {
                "p": p,
                "captura": _url(p.captura, raiz, carpeta),
                # ponytail: los eventos no llevan marca de tiempo; se asocian por URL del paso
                "consola": [c for c in consola if c.url and c.url == p.url],
                "red": [r for r in red if p.url and r.url == p.url],
            }
            for p in pasos
        ]
        por_pantalla: dict[str, list] = {}
        for f in e.fricciones:
            por_pantalla.setdefault(f.pantalla, []).append(
                {"f": f, "captura": _url(f.captura, raiz, carpeta)}
            )
        return plantillas.TemplateResponse(
            request,
            "ejecucion.html",
            {
                "e": e,
                "corrida": corrida,
                "persona": persona,
                "pasos": vistas,
                "consola": consola,
                "red": red,
                "logcat": "\n".join((graves or lineas)[-40:]),
                "video": _url(e.video, raiz, carpeta),
                "trace": _url(e.trace, raiz, carpeta),
                "fricciones": por_pantalla,
                "etiquetas": consultas.ETIQUETAS,
                "resultado": e.resultado or ("aprobado" if e.exito else "fallo"),
                "tipos": [t.value for t in TipoHallazgo],
                "gravedades": [g.value for g in Gravedad],
            },
        )

    @app.post("/ejecuciones/{ejecucion_id}/issue")
    def crear_issue(
        request: Request,
        ejecucion_id: str,
        tipo: TipoHallazgo = TipoHallazgo.tecnico,
        gravedad: Gravedad = Gravedad.media,
    ):
        e, corrida, persona, carpeta = _cargar(raiz, ejecucion_id)
        cfg = getattr(request.app.state, "cfg", None) or Config.cargar()
        try:
            r = issue.publicar_issue(e, persona, corrida, cfg, carpeta, tipo, gravedad)
        except Exception as exc:  # gh sin sesión, sin repo, sin red
            raise HTTPException(502, f"no se pudo publicar: {exc}") from exc
        return {"url": r.issue_url, "accion": r.accion, "aviso": r.aviso}

    @app.get("/archivos/{ruta:path}")
    def archivo(ruta: str):
        base = raiz.resolve()
        rel = Path(ruta)
        if rel.is_absolute() or ".." in rel.parts or rel.name.startswith(_PROHIBIDOS):
            raise HTTPException(404)
        destino = (base / rel).resolve()  # sigue enlaces simbólicos
        if not destino.is_relative_to(base) or not destino.is_file():
            raise HTTPException(404)
        return FileResponse(destino)
