"""Traduce el historial de browser-use de una ejecución exitosa a un escenario de REA.

Es el mismo historial que repite `agente/replay.py`. Cada acción de browser-use se vuelve un paso
de REA con un locator CSS o de rol; si una no se puede traducir, el escenario se corta ahí y queda
el motivo en `avisos` (el adaptador no se lo pasa a REA).
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from urllib.parse import urlsplit, urlunsplit

from dogfood.dominio import Ejecucion, Instancia

TIMEOUT_MS = 15000
SECRETO = "contrasena"
VARIABLE_SECRETO = "DOGFOOD_REA_CONTRASENA"
CAPTURA = {
    "after_each_step": ["screenshot", "dom", "url"],
    "events": ["console", "page-errors", "network"],
}
_ID_CSS = re.compile(r"[A-Za-z][\w-]*")
_ROL_IMPLICITO = {"button": "button", "a": "link", "select": "combobox", "textarea": "textbox"}
_ROL_INPUT = {
    "submit": "button",
    "button": "button",
    "checkbox": "checkbox",
    "radio": "radio",
    "search": "searchbox",
}


@cache
def chromium() -> str:
    """El Chromium de Playwright; en un hilo aparte porque el API sync no corre dentro de asyncio."""

    def ruta() -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return p.chromium.executable_path

    with ThreadPoolExecutor(1) as ex:
        return ex.submit(ruta).result()


def _locator(el: dict | None) -> dict | None:
    if not el:
        return None
    attrs = el.get("attributes") or {}
    tag = (el.get("node_name") or "").lower()
    if v := attrs.get("data-testid"):
        return {"kind": "css", "selector": f"[data-testid={json.dumps(v)}]"}
    if (v := attrs.get("id")) and _ID_CSS.fullmatch(v):
        return {"kind": "css", "selector": f"#{v}"}
    if v := attrs.get("name"):
        return {"kind": "css", "selector": f"{tag or '*'}[name={json.dumps(v)}]"}
    rol = attrs.get("role") or (
        _ROL_INPUT.get(attrs.get("type", "text"), "textbox")
        if tag == "input"
        else _ROL_IMPLICITO.get(tag)
    )
    nombre = el.get("ax_name") or attrs.get("aria-label")
    if rol and nombre:
        return {"kind": "role", "role": rol, "name": nombre}
    return None


def _origen(url: str) -> str:
    return urlsplit(url).netloc


def desde_ejecucion(ejecucion: Ejecucion, instancia: Instancia, *, contrasena: str = "") -> dict:
    """Escenario de REA para repetir `ejecucion` contra `instancia`.

    La contraseña (la de la persona, o lo que se escriba en un campo `password`) va como secreto
    `contrasena`, leído de `DOGFOOD_REA_CONTRASENA`: nunca queda literal en el escenario.
    """
    if ejecucion.estado != "ok":
        raise ValueError(f"la ejecución {ejecucion.id} no fue exitosa ({ejecucion.estado})")
    acciones: list[dict] = []
    avisos: list[str] = []
    usa_secreto = False
    destino = urlsplit(instancia.base_url)

    datos = (
        json.loads(ejecucion.ruta_historial.read_text())
        if ejecucion.ruta_historial and ejecucion.ruta_historial.exists()
        else {}
    )
    historia = datos.get("history") if isinstance(datos, dict) else None
    if not historia:
        avisos.append(f"la ejecución {ejecucion.id} no tiene historial de browser-use")
    urls = [h.get("state", {}).get("url", "") for h in historia or []]
    propio = next((_origen(u) for u in urls if u.startswith("http")), None)

    ultimo: dict | None = None
    cortado = False
    for n, h in enumerate(historia or [], start=1):
        salida = h.get("model_output") or {}
        elementos = h.get("state", {}).get("interacted_element") or []
        for i, accion in enumerate(salida.get("action") or []):
            if not accion:
                continue
            nombre, params = next(iter(accion.items()))
            params = params or {}
            el = elementos[i] if i < len(elementos) else None
            paso = {"step_id": f"p{n:03d}-{i + 1}", "timeout_ms": TIMEOUT_MS}
            motivo = ""
            if nombre == "done":
                cortado = True
                break
            if nombre in ("navigate", "go_to_url"):
                u = urlsplit(params.get("url", ""))
                if u.netloc and u.netloc != propio:
                    motivo = f"navega fuera de la app ({u.netloc})"
                else:
                    url = urlunsplit((destino.scheme, destino.netloc, u.path, u.query, u.fragment))
                    paso |= {"action": "goto", "wait_until": "load", "destination": {"url": url}}
            elif nombre in ("click", "click_element_by_index"):
                if (loc := _locator(el)) is None:
                    motivo = "click sin un elemento con locator CSS o de rol"
                else:
                    paso |= {"action": "click", "locator": loc}
            elif nombre in ("input", "input_text"):
                texto = params.get("text", "")
                es_secreto = (contrasena and texto == contrasena) or (
                    ((el or {}).get("attributes") or {}).get("type") == "password"
                )
                if (loc := _locator(el)) is None:
                    motivo = "input sin un elemento con locator CSS o de rol"
                else:
                    usa_secreto |= bool(es_secreto)
                    valor = (
                        {"source": "secret", "secret_id": SECRETO}
                        if es_secreto
                        else {"source": "literal", "value": texto}
                    )
                    paso |= {"action": "fill", "locator": loc, "value": valor}
            elif nombre == "send_keys":
                loc = ultimo or {"kind": "css", "selector": "body"}
                paso |= {"action": "press", "locator": loc, "key": params.get("keys", "")}
            elif nombre == "wait":
                ms = int(float(params.get("seconds", 1)) * 1000)
                paso |= {"action": "wait_for_timeout", "duration_ms": ms}
                paso["timeout_ms"] = ms + TIMEOUT_MS
            else:
                motivo = f"la acción {nombre!r} no tiene equivalente en REA"
            if motivo:
                avisos.append(f"escenario cortado en el paso {n}: {motivo}")
                cortado = True
                break
            ultimo = paso.get("locator", ultimo)
            acciones.append(paso)
        if cortado:
            break

    escenario = {
        "browser": {"mode": "launch", "executable_path": chromium()},
        "command_timeout_ms": 60000,
        "start_url": {"url": instancia.base_url},
        "capture": CAPTURA,
        "actions": acciones,
        "avisos": avisos,
    }
    if usa_secreto:
        escenario["secrets"] = [{"secret_id": SECRETO, "environment_variable": VARIABLE_SECRETO}]
    return escenario
