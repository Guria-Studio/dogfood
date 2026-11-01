"""Publicación de hallazgos como issues de GitHub, deduplicados por huella (FR-17..19, NFR-8, D6, D14).

Todo pasa por `gh` con el `-R` del config. Con `publicar=False` solo se lee (la búsqueda de
duplicados) y se calcula qué se haría; nada se escribe.
"""

import json
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from dogfood.almacen import Almacen
from dogfood.config import Config
from dogfood.dominio import Corrida, Gravedad, Hallazgo
from dogfood.reporte.redactar import redactar, verificar_limpio
from dogfood.reporte.sugerencia import Sugerencia, seccion

MAX_ISSUES_NUEVOS = 15

Accion = Literal["crear", "comentar", "omitido", "bloqueado_por_redaccion", "tope"]


class ResultadoIssue(BaseModel):
    hallazgo_id: str
    huella: str
    accion: Accion
    publicado: bool = False  # False también cuando es `--sin-publicar`
    nuevo: bool = True
    issue_url: str | None = None
    aviso: str = ""


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def titulo(h: Hallazgo) -> str:
    return f"[dogfood][{h.gravedad.value}] {h.pantalla}: {h.titulo}"


def cuerpo(h: Hallazgo, corrida: Corrida, sugerencia: Sugerencia | None = None) -> str:
    """Parte del cuerpo con datos de la corrida: pasa por `redactar`."""
    partes = [h.descripcion, "## Pasos"]
    partes += [f"{i}. {p}" for i, p in enumerate(h.pasos, 1)] or ["(sin pasos registrados)"]
    if h.esperado is not None or h.obtenido is not None:
        partes += ["## Esperado", h.esperado or "—", "## Obtenido", h.obtenido or "—"]
    textos = [e for e in h.evidencia if e.extracto]
    if textos:
        partes.append("## Evidencia")
        partes += [f"**{e.tipo}**\n```\n{e.extracto}\n```" for e in textos]
    if sugerencia:
        partes.append(seccion(sugerencia))
    capturas = [Path(e.ruta).name for e in h.evidencia if e.tipo == "captura" and e.ruta]
    if capturas:
        base = (
            f"runs/{corrida.id}/ejecuciones/{h.ejecucion_id}"
            if h.ejecucion_id
            else f"runs/{corrida.id}"
        )
        partes += ["## Capturas (locales)", *(f"- `{base}/{c}`" for c in capturas)]
    return "\n\n".join(partes)


def pie(h: Hallazgo, hallazgo_id: str, corrida: Corrida) -> str:
    """Datos propios de dogfood (ids, commit, huella); va después de redactar porque un sha1
    de 40 caracteres parece un token y se enmascararía, rompiendo la deduplicación."""
    return "\n\n".join(
        [
            "## Reproducir",
            f"`dogfood replay {hallazgo_id}`",
            f"Commit de predicts: `{h.commit}` · semilla: `{h.semilla}` · corrida: `{corrida.id}`",
            f"<!-- dogfood:huella={h.huella} -->",
        ]
    )


def _comentario(h: Hallazgo, hallazgo_id: str, corrida: Corrida) -> str:
    # solo ids, fecha y commit propios: no lleva datos de la corrida que redactar
    return (
        f"Nueva ocurrencia en la corrida `{corrida.id}` ({corrida.inicio:%Y-%m-%d %H:%M}), "
        f"commit `{h.commit}`: {h.ocurrencias} ocurrencia(s). Replay: `dogfood replay {hallazgo_id}`."
    )


def _buscar(repo: str, huella: str) -> dict | None:
    salida = _gh(
        "issue", "list", "-R", repo, "--label", "dogfood", "--state", "open",
        "--search", f"dogfood:huella={huella} in:body", "--json", "number,url",
    )  # fmt: skip
    encontrados = json.loads(salida or "[]")
    return encontrados[0] if encontrados else None


def publicar(
    hallazgos: list[Hallazgo],
    corrida: Corrida,
    config: Config,
    publicar: bool = True,
    *,
    almacen: Almacen | None = None,
    secretos: list[str] | None = None,
    sugerencias: dict[str, Sugerencia] | None = None,
) -> list[ResultadoIssue]:
    """`hallazgos` en el orden de `Almacen.guardar_hallazgos` (ids `<corrida>-H<n>`).

    `secretos`: contraseñas de las personas; se suman a los secretos del config.
    """
    repo = config.repo_issues
    umbral = Gravedad(config.umbral_publicar)
    tope = getattr(config, "max_issues_nuevos_por_corrida", MAX_ISSUES_NUEVOS)
    conocidos = [*config._secretos.values(), *(secretos or [])]
    etiquetas_listas: set[str] = set()
    nuevos = 0
    resultados = []

    for n, h in enumerate(hallazgos, 1):
        hid = f"{corrida.id}-H{n}"
        r = ResultadoIssue(hallazgo_id=hid, huella=h.huella, accion="omitido")
        resultados.append(r)
        if h.solo_reporte or h.gravedad < umbral:
            continue
        t, c = (
            redactar(titulo(h), conocidos),
            redactar(cuerpo(h, corrida, (sugerencias or {}).get(hid)), conocidos),
        )
        if restos := verificar_limpio(f"{t}\n{c}"):
            r.accion, r.aviso = "bloqueado_por_redaccion", f"{len(restos)} resto(s) sin redactar"
            continue
        c = f"{c}\n\n{pie(h, hid, corrida)}"

        try:
            existente = _buscar(repo, h.huella)
        except (OSError, subprocess.CalledProcessError):
            if publicar:
                raise
            existente = None  # en seco, sin gh o sin repo: se asume nuevo

        if existente:
            r.accion, r.nuevo, r.issue_url = "comentar", False, existente["url"]
            if publicar:
                _gh("issue", "comment", str(existente["number"]), "-R", repo,
                    "--body", _comentario(h, hid, corrida))  # fmt: skip
                r.publicado = True
            continue

        if nuevos >= tope:
            r.accion, r.aviso = "tope", f"tope de {tope} issues nuevos por corrida alcanzado"
            continue
        nuevos += 1
        r.accion = "crear"
        etiquetas = ["dogfood", f"dogfood:{h.tipo.value}", f"gravedad:{h.gravedad.value}"]
        if publicar:
            for e in etiquetas:
                if e not in etiquetas_listas:
                    _gh("label", "create", e, "-R", repo, "--force")
                    etiquetas_listas.add(e)
            args = ["issue", "create", "-R", repo, "--title", t, "--body", c]
            for e in etiquetas:
                args += ["--label", e]
            r.issue_url = _gh(*args).strip()
            r.publicado = True

    if almacen and publicar:
        almacen.marcar_issues(
            corrida.id, [(r.hallazgo_id, r.issue_url, r.nuevo) for r in resultados if r.publicado]
        )
    return resultados
