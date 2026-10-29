"""Arma y publica el issue de una ejecución desde el panel (FR-33), con la redacción y la
deduplicación por huella de `reporte/issues.py`."""

from pathlib import Path

from dogfood.config import Config
from dogfood.dominio import (
    Corrida,
    Ejecucion,
    Evidencia,
    Gravedad,
    Hallazgo,
    Paso,
    Persona,
    TipoHallazgo,
)
from dogfood.reporte import issues
from dogfood.reporte.redactar import redactar

_MAX_LINEAS = 20


def _paso_fallo(e: Ejecucion) -> Paso | None:
    distintos = [p for p in e.pasos if p.esperado and p.observado and p.esperado != p.observado]
    return (distintos or e.pasos or [None])[-1]


def _extractos(e: Ejecucion, carpeta: Path | None) -> list[Evidencia]:
    salida = []
    if e.consola:
        lineas = [f"[{c.nivel}] {c.texto}" for c in e.consola[-_MAX_LINEAS:]]
        salida.append(Evidencia(tipo="log", extracto="\n".join(lineas)))
    if e.red:
        malas = [r for r in e.red if r.estado >= 400] or e.red
        lineas = [f"{r.metodo} {r.url} -> {r.estado} ({r.ms:.0f} ms)" for r in malas[-_MAX_LINEAS:]]
        salida.append(Evidencia(tipo="red", extracto="\n".join(lineas)))
    logcat = carpeta / "logcat.txt" if carpeta else None
    if logcat and logcat.is_file():
        lineas = logcat.read_text(errors="replace").splitlines()
        graves = [x for x in lineas if x.startswith("E/") or "FATAL" in x]
        salida.append(Evidencia(tipo="log", extracto="\n".join((graves or lineas)[-_MAX_LINEAS:])))
    return salida


def construir_hallazgo(
    e: Ejecucion,
    corrida: Corrida,
    carpeta: Path | None = None,
    tipo: TipoHallazgo = TipoHallazgo.tecnico,
    gravedad: Gravedad = Gravedad.media,
) -> Hallazgo:
    base = f"runs/{corrida.id}/ejecuciones/{e.id}"
    p = _paso_fallo(e)
    descripcion = [
        f"Recorrido `{e.escenario_id}`: {e.resultado or ('aprobado' if e.exito else 'fallo')}. "
        f"{e.motivo_juez}".strip()
    ]
    if e.video:
        descripcion.append(f"Video (local): `{base}/video/{e.video.name}`")
    if e.trace:
        descripcion.append(
            f"Trace (local): `{base}/trace.zip` (`uv run playwright show-trace {base}/trace.zip`)"
        )
    descripcion.append(f"Replay: `dogfood replay {e.id}`")
    evidencia = _extractos(e, carpeta)
    evidencia += [Evidencia(tipo="captura", ruta=x.captura) for x in e.pasos if x.captura]
    h = Hallazgo(
        tipo=tipo,
        gravedad=gravedad,
        pantalla=p.pantalla if p else "—",
        titulo=f"{e.escenario_id} terminó en {e.resultado or ('aprobado' if e.exito else 'fallo')}",
        descripcion="\n\n".join(descripcion),
        pasos=[f"{x.accion} ({x.pantalla})" for x in e.pasos],
        evidencia=evidencia,
        esperado=p.esperado or None if p else None,
        obtenido=p.observado or None if p else None,
        ejecucion_id=e.id,
        semilla=corrida.semilla,
        commit=corrida.commit,
    )
    h.huella = h.calcular_huella(f"{e.escenario_id}|{p.n if p else 0}")
    return h


def _secretos(persona: Persona, cfg: Config | None) -> list[str]:
    propios = [persona.email, persona.contrasena, persona.empresa]
    return [*propios, *(cfg._secretos.values() if cfg else [])]


def armar_issue(
    ejecucion: Ejecucion,
    persona: Persona,
    corrida: Corrida,
    cfg: Config | None = None,
    carpeta: Path | None = None,
    tipo: TipoHallazgo = TipoHallazgo.tecnico,
    gravedad: Gravedad = Gravedad.media,
) -> tuple[str, str]:
    """Título y cuerpo ya redactados, con el formato de *Issue publicado*."""
    h = construir_hallazgo(ejecucion, corrida, carpeta, tipo, gravedad)
    conocidos = _secretos(persona, cfg)
    cuerpo = redactar(issues.cuerpo(h, corrida), conocidos)
    # el pie (huella, commit) va sin redactar: un sha1 parece un token (ver issues.pie)
    return (
        redactar(issues.titulo(h), conocidos),
        f"{cuerpo}\n\n{issues.pie(h, f'{corrida.id}-H1', corrida)}",
    )


def publicar_issue(
    ejecucion: Ejecucion,
    persona: Persona,
    corrida: Corrida,
    cfg: Config,
    carpeta: Path | None = None,
    tipo: TipoHallazgo = TipoHallazgo.tecnico,
    gravedad: Gravedad = Gravedad.media,
) -> issues.ResultadoIssue:
    h = construir_hallazgo(ejecucion, corrida, carpeta, tipo, gravedad)
    [r] = issues.publicar(
        [h],
        corrida,
        cfg,
        secretos=[persona.contrasena, persona.email, persona.empresa],
    )
    return r
