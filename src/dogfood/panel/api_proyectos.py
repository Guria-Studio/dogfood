"""API de proyectos: lista con el último resultado, alta, lectura, cambios y baja."""

import os
from pathlib import Path
from typing import Annotated

import httpx
from dotenv import dotenv_values
from fastapi import Body, FastAPI, Header, HTTPException

from dogfood import actividad, proyectos
from dogfood.config import Config


def _archivo_secreto(slug: str) -> Path:
    base = Path(os.environ.get("DOGFOOD_CONFIG_DIR") or Path.home() / ".config" / "dogfood")
    return base / f"slack-{slug}.env"


def _var_webhook(slug: str) -> str:
    return "SLACK_WEBHOOK_URL_" + slug.upper().replace("-", "_")


def _webhook(slug: str) -> str | None:
    return dotenv_values(_archivo_secreto(slug)).get(_var_webhook(slug)) or None


def _guardar_webhook(slug: str, url: str) -> None:
    ruta = _archivo_secreto(slug)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    previo = {k: v for k, v in dotenv_values(ruta).items() if k != _var_webhook(slug) and v}
    previo[_var_webhook(slug)] = url
    ruta.touch(mode=0o600)
    ruta.write_text("".join(f"{k}={v}\n" for k, v in previo.items()))


def registrar_api_proyectos(app: FastAPI, raiz: Path, cfg: Config | None = None) -> None:
    raiz = Path(raiz)

    def exigir(x_dogfood: str | None) -> None:
        if x_dogfood != "1":  # un formulario de otro sitio no puede poner este header
            raise HTTPException(403, "falta el header X-Dogfood: 1")

    def validar(f):
        try:
            return f()
        except ValueError as exc:  # incluye ValidationError y ErrorProyecto
            raise HTTPException(400, str(exc).replace("\n", " ")) from None

    def uno(slug: str) -> proyectos.Proyecto:
        p = proyectos.obtener(slug, raiz)
        if p is None:
            raise HTTPException(404, f"el proyecto {slug!r} no existe")
        return p

    @app.get("/api/proyectos")
    def listar():
        return [
            p.model_dump(mode="json") | {"ultimos": proyectos.ultimos_resultados(p, raiz)}
            for p in proyectos.listar(raiz)
        ]

    @app.post("/api/proyectos", status_code=201)
    def crear(
        datos: Annotated[dict, Body()],
        x_dogfood: str | None = Header(default=None),
        autor: str | None = Header(default=None, alias="X-Dogfood-Autor"),
    ):
        exigir(x_dogfood)
        p = validar(lambda: proyectos.crear(datos, raiz))
        actividad.registrar(raiz, p.slug, "proyecto_creado", p.nombre, autor or "panel")
        return p.model_dump(mode="json")

    @app.get("/api/proyectos/{slug}")
    def leer(slug: str):
        p = uno(slug)
        return p.model_dump(mode="json") | {"ultimos": proyectos.ultimos_resultados(p, raiz)}

    @app.patch("/api/proyectos/{slug}")
    def cambiar(
        slug: str,
        cambios: Annotated[dict, Body()],
        x_dogfood: str | None = Header(default=None),
        autor: str | None = Header(default=None, alias="X-Dogfood-Autor"),
    ):
        exigir(x_dogfood)
        uno(slug)
        notif = cambios.get("notificaciones")
        if isinstance(notif, dict) and "slack_webhook" in notif:
            # El webhook es un secreto: va al archivo de secretos, nunca a la base ni a la API.
            notif = cambios["notificaciones"] = dict(notif)
            url = str(notif.pop("slack_webhook") or "").strip()
            if url:
                if not url.startswith("https://"):
                    raise HTTPException(400, "el webhook de Slack debe ser una URL https")
                _guardar_webhook(slug, url)
                notif["slack"] = True
        p = validar(lambda: proyectos.actualizar(slug, cambios, raiz))
        campos = ", ".join(sorted(cambios))
        actividad.registrar(raiz, slug, "ajuste_cambiado", campos, autor or "panel")
        return p.model_dump(mode="json")

    @app.post("/api/proyectos/{slug}/slack/probar")
    def probar_slack(slug: str, x_dogfood: str | None = Header(default=None)):
        exigir(x_dogfood)
        uno(slug)
        url = _webhook(slug)
        if not url:
            raise HTTPException(400, "este proyecto no tiene webhook de Slack guardado")
        try:
            r = httpx.post(url, json={"text": f"dogfood: prueba de aviso del proyecto {slug}"})
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Slack no aceptó el aviso ({type(exc).__name__})") from None
        return {"ok": True}

    @app.get("/api/proyectos/{slug}/actividad")
    def ver_actividad(slug: str):
        uno(slug)
        return actividad.listar(raiz, slug)

    @app.get("/api/proyectos/{slug}/fuentes")
    def fuentes(slug: str):
        p = uno(slug)
        docs = Path.cwd() / "docs"
        archivos = [*sorted((docs / "prd").glob("*.md")), *sorted((docs / "ops").glob("*.md"))]
        lista = [
            {
                "tipo": "prd" if a.parent.name == "prd" else "docs",
                "nombre": a.name,
                "ruta": str(a.relative_to(Path.cwd())),
            }
            for a in archivos
        ]
        if p.repo_codigo:
            lista.append({"tipo": "repo", "nombre": p.repo_codigo, "ruta": p.repo_codigo})
        return lista  # ponytail: las exploraciones aún no se guardan; se suman cuando existan

    @app.delete("/api/proyectos/{slug}")
    def borrar(
        slug: str,
        cuerpo: Annotated[dict | None, Body()] = None,
        x_dogfood: str | None = Header(default=None),
    ):
        exigir(x_dogfood)
        uno(slug)
        if (cuerpo or {}).get("confirmar") != slug:
            raise HTTPException(400, 'confirma con el slug en el cuerpo: {"confirmar": "<slug>"}')
        proyectos.borrar(slug, raiz)
        _archivo_secreto(slug).unlink(missing_ok=True)
        return {"borrado": slug}
