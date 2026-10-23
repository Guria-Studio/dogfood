"""Resumen de la corrida en Slack por incoming webhook (FR-21, D11).

`avisar` manda un solo mensaje en español. Sin `SLACK_WEBHOOK_URL` solo avisa en consola;
un fallo del webhook se registra y no tumba la corrida. Todo texto pasa por `redactar`, y
`verificar_limpio` es la última barrera: si aún queda algo que parece secreto, no se envía.
"""

import logging
from collections import Counter

import httpx
from pydantic import BaseModel

from dogfood.config import Config, ErrorSecreto
from dogfood.dominio import Corrida, Gravedad, Hallazgo
from dogfood.reporte.issues import ResultadoIssue
from dogfood.reporte.redactar import redactar, verificar_limpio

log = logging.getLogger("dogfood")

MAX_LINKS = 10
_ETIQUETA = {Gravedad.critica: "crítica", Gravedad.alta: "alta", Gravedad.media: "media"}


class Resumen(BaseModel):
    personas: int
    exitos: int
    hallazgos: list[Hallazgo] = []
    issues: list[ResultadoIssue] = []
    ruta_reporte: str
    costo_usd: float = 0.0
    duracion_s: float = 0.0


def _hallazgos(hallazgos: list[Hallazgo]) -> str:
    cuenta = Counter(h.gravedad for h in hallazgos)
    if not cuenta:
        return "Hallazgos: ninguno"
    partes = [f"{cuenta[g]} {_ETIQUETA.get(g, g.value)}" for g in Gravedad if cuenta[g]]
    return "Hallazgos: " + " · ".join(partes)


def _links(issues: list[ResultadoIssue]) -> list[str]:
    con_url = [i for i in issues if i.accion in ("crear", "comentar") and i.issue_url]
    if not con_url:
        return []
    lineas = [f"Issues nuevos o comentados ({len(con_url)}):"]
    lineas += [f"• <{i.issue_url}|#{i.issue_url.rsplit('/', 1)[-1]}>" for i in con_url[:MAX_LINKS]]
    if len(con_url) > MAX_LINKS:
        lineas.append(f"… y {len(con_url) - MAX_LINKS} más")
    return lineas


def _duracion(segundos: float) -> str:
    minutos, s = divmod(round(segundos), 60)
    return f"{minutos} min {s} s"


def texto(corrida: Corrida, resumen: Resumen) -> str:
    tasa = resumen.exitos / resumen.personas * 100 if resumen.personas else 0
    lineas = [
        f"*Corrida {corrida.id}*: {corrida.objetivo}",
        # el commit va en corto: uno completo lo tomaría `redactar` por token largo
        f"Ref: {corrida.ref} · commit {corrida.commit[:7]}",
        f"Personas: {resumen.personas} · tasa de éxito {tasa:.0f}% ({resumen.exitos}/{resumen.personas})",
        _hallazgos(resumen.hallazgos),
        *_links(resumen.issues),
        f"Reporte en el server: `{resumen.ruta_reporte}`",
        f"Costo: USD {resumen.costo_usd:.2f} · Duración: {_duracion(resumen.duracion_s)}",
    ]
    return "\n".join(lineas)


def avisar(
    corrida: Corrida,
    resumen: Resumen,
    config: Config,
    *,
    secretos: list[str] | None = None,
) -> bool:
    """Envía el resumen; devuelve `True` si Slack respondió 2xx. Nunca lanza por el webhook."""
    try:
        url = config.secreto("SLACK_WEBHOOK_URL")
    except ErrorSecreto as e:
        log.warning("no se envía el resumen a Slack: %s", e)
        return False

    limpio = redactar(texto(corrida, resumen), [url, *(secretos or [])])
    if fugas := verificar_limpio(limpio):
        log.warning("resumen de Slack bloqueado: quedan %d posibles secretos", len(fugas))
        return False

    try:
        httpx.post(url, json={"text": limpio}, timeout=10).raise_for_status()
    except httpx.HTTPStatusError as e:
        log.warning("Slack rechazó el resumen: HTTP %s", e.response.status_code)
        return False
    except httpx.HTTPError as e:
        log.warning("no se pudo enviar el resumen a Slack: %s", type(e).__name__)
        return False
    return True
