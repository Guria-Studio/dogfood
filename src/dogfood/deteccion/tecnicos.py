"""Fallos técnicos (FR-12): red, consola, logs, pantalla en blanco y trabajos colgados.

Cada detector emite hallazgos `tecnico`; los que comparten huella dentro de la corrida se fusionan
en uno con `ocurrencias` y la evidencia sin duplicar.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np
from PIL import Image

from dogfood.dominio import (
    ContextoDeteccion,
    Ejecucion,
    Evidencia,
    Gravedad,
    Hallazgo,
    Persona,
    TipoHallazgo,
)
from dogfood.objetivos.predicts.cliente import ErrorSesion

log = logging.getLogger("dogfood")

TIMEOUT_TRABAJO_S = 300
UMBRAL_PANTALLA_BLANCA = 3.0  # desvío estándar de los píxeles (0-255) bajo el cual es uniforme
_NAVEGACION = ("navegó", "navego", "abrió", "abrio", "goto", "navigate", "go_to_url", "open")
_ESPERA = ("esper", "wait", "timeout", "tard", "colg", "cargando", "loading")

_ID = re.compile(
    r"(?<=/)(?:\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{24,})"
    r"(?=/|$|\?)",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://\S+")
_TS = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")
_EXC = re.compile(r"^(?:[\w.]+\.)?(\w+(?:Error|Exception|Exit|Interrupt|Warning)\w*)\b.*$")
_FRAME = re.compile(r'File "([^"]*[/\\]predicts[/\\][^"]*)", line (\d+), in (\S+)')
_PREFIJO = re.compile(r"^[\w.-]+\s*\|\s?")
_ERROR = re.compile(r"\b(ERROR|CRITICAL)\b")


def detectar(ctx: ContextoDeteccion) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for e in ctx.ejecuciones:
        hallazgos += _red(ctx, e) + _consola(ctx, e) + _en_blanco(ctx, e) + _colgado(ctx, e)
    hallazgos += _logs(ctx)
    return _fusionar(hallazgos)


def _hallazgo(ctx, e, tipo_firma, firma, **kw) -> tuple[Hallazgo, str]:
    h = Hallazgo(
        tipo=TipoHallazgo.tecnico,
        semilla=ctx.corrida.semilla,
        commit=ctx.corrida.commit,
        ejecucion_id=e.id if e else None,
        **kw,
    )
    h.huella = h.calcular_huella(f"{tipo_firma}|{firma}")
    return h, firma


def _fusionar(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    por_huella: dict[str, Hallazgo] = {}
    for h in hallazgos:
        previo = por_huella.get(h.huella)
        if previo is None:
            por_huella[h.huella] = h
            continue
        previo.ocurrencias += h.ocurrencias
        previo.gravedad = max(previo.gravedad, h.gravedad)
        vistas = {(ev.tipo, ev.ruta, ev.extracto) for ev in previo.evidencia}
        for ev in h.evidencia:
            if (ev.tipo, ev.ruta, ev.extracto) not in vistas:
                previo.evidencia.append(ev)
                vistas.add((ev.tipo, ev.ruta, ev.extracto))
    return list(por_huella.values())


# --- red -----------------------------------------------------------------------------------


def normalizar_ruta(url: str) -> str:
    return _ID.sub("{id}", urlparse(url).path)


def _reglas(ctx: ContextoDeteccion) -> list[dict]:
    """Rutas esperadas que declara el objetivo (`rutas_esperadas()`); sin objetivo, ninguna."""
    f = getattr(getattr(ctx, "objetivo", None), "rutas_esperadas", None)
    return list(f()) if f else []


def _carril(ctx: ContextoDeteccion, e: Ejecucion) -> str:
    f = getattr(getattr(ctx, "objetivo", None), "escenarios", None)
    return next((s.carril for s in (f() if f else []) if s.id == e.escenario_id), "normal")


def _regla(reglas, tipo, ctx, e, ruta, estado, login_ok) -> dict | None:
    carril = _carril(ctx, e) if any("carril" in r for r in reglas) else "normal"
    for r in reglas:
        if r.get("tipo", "esperada") != tipo or ruta != r["ruta"] or estado not in r["estados"]:
            continue
        if r.get("carril", carril) == carril and not (r.get("antes_de_login") and login_ok):
            return r
    return None


def _esperado(e: Ejecucion, metodo: str, ruta: str, estado: int) -> bool:
    """`Ejecucion.notas` marca lo esperado: «esperado: 429», opcionalmente con `GET /ruta`."""
    for n in e.notas:
        n = _ID.sub("{id}", n.lower())
        if "esperad" in n and str(estado) in n and (ruta.lower() in n or "/" not in n):
            return True
    return False


def _red(ctx: ContextoDeteccion, e: Ejecucion) -> list[Hallazgo]:
    salida = []
    login_ok = False
    reglas = _reglas(ctx)
    # Un 4xx de validación (422) que la UI mostró como error de formulario y un 404 de lo borrado
    # se excluyen; sin visibilidad de la UI, 422 y 404 se toleran siempre. Un 401 solo antes del login.
    for ev in e.red:
        ruta = normalizar_ruta(ev.url)
        if ev.estado < 400:
            if ev.metodo.upper() == "POST" and ruta.endswith(("/login", "/auth/login")):
                login_ok = True
            continue
        if _regla(reglas, "esperada", ctx, e, ruta, ev.estado, login_ok):
            continue
        carrera = _regla(reglas, "carrera", ctx, e, ruta, ev.estado, login_ok)
        if carrera:
            salida.append(_carrera(ctx, e, ev, ruta, carrera))
            continue
        if ev.estado < 500 and (ev.estado in (404, 422) or (ev.estado == 401 and not login_ok)):
            continue
        if _esperado(e, ev.metodo, ruta, ev.estado):
            continue
        firma = f"{ev.metodo.upper()} {ruta} {ev.estado}"
        h, _ = _hallazgo(
            ctx,
            e,
            "red",
            firma,
            gravedad=Gravedad.alta if ev.estado >= 500 else Gravedad.media,
            pantalla=ruta,
            titulo=f"{ev.metodo.upper()} {ruta} respondió {ev.estado}",
            descripcion=f"La petición {ev.metodo.upper()} {ev.url} devolvió {ev.estado}.",
            evidencia=[Evidencia(tipo="red", extracto=f"{ev.metodo} {ev.url} -> {ev.estado}")],
        )
        salida.append(h)
    return salida


def _carrera(ctx, e: Ejecucion, ev, ruta: str, regla: dict) -> Hallazgo:
    """Un 4xx que el objetivo marca como carrera: gravedad media y, si ocurre justo tras la subida,
    con la hipótesis. ponytail: `red.jsonl` no tiene hora, solo el orden; «primeros segundos» =
    la petición viene después del POST de subida en el orden registrado."""
    firma = f"{ev.metodo.upper()} {ruta} {ev.estado}"
    metodo, subida = regla["tras"]
    i = e.red.index(ev)
    tras = any(
        x.metodo.upper() == metodo and normalizar_ruta(x.url) == subida and x.estado < 400
        for x in e.red[:i]
    )
    desc = f"La petición {ev.metodo.upper()} {ev.url} devolvió {ev.estado}."
    if tras:
        desc += f" Hipótesis: {regla['hipotesis']}."
    return _hallazgo(
        ctx, e, "red", firma, gravedad=Gravedad.media, pantalla=ruta,
        titulo=f"{ev.metodo.upper()} {ruta} respondió {ev.estado}", descripcion=desc,
        evidencia=[Evidencia(tipo="red", extracto=f"{ev.metodo} {ev.url} -> {ev.estado}")],
    )[0]  # fmt: skip


# --- consola -------------------------------------------------------------------------------


def _firma_consola(texto: str) -> str:
    t = _URL.sub("", texto)
    t = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", t, flags=re.IGNORECASE
    )
    t = re.sub(r"\b[0-9a-f]{24,}\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\d+", "", t)
    return " ".join(t.split())


_CARGA = re.compile(r"Failed to load resource.*status of (\d+)")


def _eco_de_red(ctx, e: Ejecucion, ev, reglas) -> bool:
    """«Failed to load resource … status of N» repite una respuesta de red: ya la trató `_red`
    (hallazgo, tolerada o esperada), o es esperada por el objetivo aunque no quede en `e.red`."""
    m = _CARGA.search(ev.texto)
    if not m or not ev.url:
        return False
    ruta, estado = normalizar_ruta(ev.url), int(m[1])
    if _regla(reglas, "esperada", ctx, e, ruta, estado, False):
        return True
    return any(normalizar_ruta(r.url) == ruta and r.estado == estado for r in e.red)


def _consola(ctx: ContextoDeteccion, e: Ejecucion) -> list[Hallazgo]:
    salida = []
    reglas = _reglas(ctx)
    for ev in e.consola:
        if ev.nivel.lower() not in ("error", "pageerror", "exception"):
            continue
        if _eco_de_red(ctx, e, ev, reglas):
            continue
        firma = _firma_consola(ev.texto)
        # ponytail: sin timestamps en EventoConsola, «pantalla muerta» = la ejecución no tuvo
        # pasos después del último evento de consola; solo se sabe si no hubo pasos o si fue el fin.
        muerta = _sin_pasos_despues(e, ev)
        h, _ = _hallazgo(
            ctx,
            e,
            "consola",
            firma,
            gravedad=Gravedad.alta if muerta else Gravedad.media,
            pantalla=urlparse(ev.url).path if ev.url else _pantalla_final(e),
            titulo=f"Error de JavaScript: {firma[:80]}",
            descripcion=f"La consola del navegador registró un error: {ev.texto[:300]}"
            + (" Después no hubo más pasos (pantalla muerta)." if muerta else ""),
            evidencia=[Evidencia(tipo="log", extracto=ev.texto[:500])],
        )
        salida.append(h)
    return salida


def _sin_pasos_despues(e: Ejecucion, ev) -> bool:
    # El último error de consola de una ejecución que no logró su objetivo = la sesión terminó ahí.
    return not e.pasos or (not e.exito and e.consola[-1] is ev)


def _pantalla_final(e: Ejecucion) -> str:
    return e.pasos[-1].pantalla if e.pasos else ""


# --- logs ----------------------------------------------------------------------------------


def _ts(linea: str) -> datetime | None:
    m = _TS.search(linea)
    return datetime.fromisoformat(f"{m[1]} {m[2]}") if m else None


def _logs(ctx: ContextoDeteccion) -> list[Hallazgo]:
    salida = []
    for servicio in ("api", "worker"):
        lineas = [_PREFIJO.sub("", ln) for ln in ctx.logs.get(servicio, "").splitlines()]
        i = 0
        while i < len(lineas):
            ln = lineas[i]
            if ln.startswith("Traceback"):
                j = i + 1
                while j < len(lineas) and (lineas[j][:1] in " \t" or not _EXC.match(lineas[j])):
                    j += 1
                bloque = lineas[i : j + 1]
                ts = next(
                    (t for x in reversed(lineas[max(0, i - 3) : i + 1]) if (t := _ts(x))), None
                )
                salida.append(_hallazgo_log(ctx, servicio, bloque, ts))
                i = j + 1
            elif _ERROR.search(ln):
                if i + 1 < len(lineas) and lineas[i + 1].startswith("Traceback"):
                    i += 1  # la línea ERROR anuncia el traceback que sigue: un solo hallazgo
                    continue
                salida.append(_hallazgo_log(ctx, servicio, [ln], _ts(ln)))
                i += 1
            else:
                i += 1
    return salida


def _hallazgo_log(ctx, servicio: str, bloque: list[str], ts: datetime | None) -> Hallazgo:
    exc = next((m[1] for x in reversed(bloque) if (m := _EXC.match(x))), None)
    frames = [m for x in bloque if (m := _FRAME.search(x))]
    if exc:
        lugar = f"{frames[-1][1].split('predicts', 1)[-1]}:{frames[-1][3]}" if frames else ""
        firma = f"{servicio}|{exc}|{lugar}"
        titulo = f"{exc} en el {servicio}" + (f" ({lugar})" if lugar else "")
    else:
        mensaje = _firma_consola(bloque[0])
        firma, titulo = f"{servicio}|{mensaje}", f"ERROR en el {servicio}: {mensaje[:80]}"
    e = _ejecucion_en(ctx, ts)
    h, _ = _hallazgo(
        ctx,
        e,
        "logs",
        firma,
        gravedad=Gravedad.alta,
        pantalla=f"log:{servicio}",
        titulo=titulo,
        descripcion=f"El log del {servicio} registró un fallo durante la corrida.",
        evidencia=[Evidencia(tipo="log", extracto="\n".join(bloque)[:2000])],
    )
    return h


def _ejecucion_en(ctx: ContextoDeteccion, ts: datetime | None) -> Ejecucion | None:
    if ts is None:
        return None
    for e in ctx.ejecuciones:
        if e.pasos:
            ini, fin = e.pasos[0].ts, e.pasos[-1].ts
            if ini.tzinfo:
                ts = ts.replace(tzinfo=ini.tzinfo)
            if ini <= ts <= fin:
                return e
    return None


# --- pantalla en blanco --------------------------------------------------------------------


def _desvio(ruta: Path) -> float | None:
    try:
        with Image.open(ruta) as im:
            return float(np.asarray(im.convert("L"), dtype=float).std())
    except (OSError, ValueError):
        return None


def _en_blanco(ctx: ContextoDeteccion, e: Ejecucion) -> list[Hallazgo]:
    salida = []
    for i, p in enumerate(e.pasos):
        if p.captura is None or not Path(p.captura).exists():
            continue
        # «después de una navegación»: el paso lleva a otra URL o su acción es navegar
        previo = e.pasos[i - 1].url if i else None
        if not (previo != p.url or any(k in p.accion.lower() for k in _NAVEGACION)):
            continue
        d = _desvio(Path(p.captura))
        if d is None or d >= UMBRAL_PANTALLA_BLANCA:
            continue
        ruta = normalizar_ruta(p.url)
        h, _ = _hallazgo(
            ctx,
            e,
            "blanco",
            ruta,
            gravedad=Gravedad.alta,
            pantalla=p.pantalla,
            titulo="Pantalla en blanco",
            descripcion=f"La captura del paso {p.n} en {ruta} es casi uniforme tras navegar.",
            pasos=[f"{p.n}: {p.accion}"],
            evidencia=[Evidencia(tipo="captura", ruta=Path(p.captura))],
        )
        salida.append(h)
    return salida


# --- trabajo colgado -----------------------------------------------------------------------


def _persona(ctx: ContextoDeteccion, e: Ejecucion) -> Persona | None:
    import json

    for ds in ctx.datasets.values():
        ruta = Path(ds.ruta_verdad).parents[2] / "personas.json"
        if ruta.exists():
            for p in json.loads(ruta.read_text()):
                if p["id"] == e.persona_id:
                    return Persona.model_validate(p)
    return None


def _espero_trabajo(e: Ejecucion) -> bool:
    textos = [f.texto for f in e.fricciones] + e.notas
    return any(any(k in t.lower() for k in _ESPERA) for t in textos)


def _colgado(ctx: ContextoDeteccion, e: Ejecucion) -> list[Hallazgo]:
    if not _espero_trabajo(e) or not e.pasos:
        return []
    fin = e.pasos[-1].ts
    ahora = datetime.now(fin.tzinfo)
    if (ahora - fin).total_seconds() < TIMEOUT_TRABAJO_S:
        return []
    persona = _persona(ctx, e)
    if persona is None:
        return []
    try:
        cliente = ctx.cliente_api(persona)
        try:
            pendientes = [
                a["id"]
                for p in cliente.proyectos()
                for d in cliente.datasets(p["id"])
                for a in cliente.analisis_de(d["id"])
                if a.get("estado") != "listo"
            ]
        finally:
            if hasattr(cliente, "close"):
                cliente.close()
    except (httpx.HTTPError, ErrorSesion) as exc:
        log.warning("técnicos: sin API para %s: %s", persona.id, exc)
        return []
    if not pendientes:
        return []
    h, _ = _hallazgo(
        ctx,
        e,
        "colgado",
        "trabajo_colgado",
        gravedad=Gravedad.alta,
        pantalla=_pantalla_final(e),
        titulo="Trabajo colgado: el análisis no termina",
        descripcion=f"La persona esperó un trabajo y {TIMEOUT_TRABAJO_S}s después el análisis "
        "sigue sin estar listo.",
        evidencia=[
            Evidencia(tipo="texto", extracto=f"análisis sin listo: {', '.join(pendientes)}")
        ],
    )
    return [h]
