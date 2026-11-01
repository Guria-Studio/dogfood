"""Cobertura de Semantics de apps Flutter (FR-35, D26): XML de uiautomator / XCUITest y ElementoUI."""

import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence

from dogfood.dominio import CoberturaSemantica
from dogfood.drivers.base import ElementoUI

_CLASES_FLUTTER = ("FlutterView", "FlutterSurfaceView", "FlutterTextureView")
_TIPOS_IOS = ("Button", "TextField", "SecureTextField", "Switch", "Cell", "Link")


def _parsear(xml: str) -> ET.Element | None:
    try:
        return ET.fromstring(xml.lstrip())
    except ET.ParseError:
        return None


def _es_flutter_view(n: ET.Element) -> bool:
    return n.tag == "node" and n.get("class", "").rsplit(".", 1)[-1] in _CLASES_FLUTTER


def es_flutter(xml: str, actividad: str = "") -> bool:
    if "FlutterActivity" in actividad or "io.flutter" in actividad:
        return True
    raiz = _parsear(xml)
    return raiz is not None and any(_es_flutter_view(n) for n in raiz.iter())


def _cobertura(
    interactivos: int, etiquetados: int, con_id: int, nodos: int, flutter: bool, umbral: float
) -> CoberturaSemantica:
    r_et = etiquetados / interactivos if interactivos else 1.0
    r_id = con_id / interactivos if interactivos else 1.0
    return CoberturaSemantica(
        flutter=flutter,
        nodos=nodos,
        interactivos=interactivos,
        etiquetados=etiquetados,
        con_id=con_id,
        ratio_etiqueta=r_et,
        ratio_id=r_id,
        ciega=flutter and (nodos == 0 or r_et < umbral),
    )


def _verdadero(n: ET.Element, attr: str) -> bool:
    return n.get(attr) == "true"


def cobertura_xml(xml: str, *, umbral: float = 0.6, actividad: str = "") -> CoberturaSemantica:
    raiz = _parsear(xml)
    flutter = es_flutter(xml, actividad)
    if raiz is None:
        return _cobertura(0, 0, 0, 0, flutter, umbral)
    if raiz.tag.startswith("XCUIElementType") or raiz.get("type", "").startswith("XCUIElementType"):
        return _cobertura_ios(raiz, flutter, umbral)
    nodos = [n for n in raiz.iter("node")]
    if flutter:
        # solo lo que cuelga del FlutterView (sin contarlo a él)
        vistas = [n for n in nodos if _es_flutter_view(n)]
        nodos = [d for v in vistas for d in v.iter("node") if d is not v]
    ni = ne = nid = 0
    for n in nodos:
        texto = n.get("text", "").strip()
        desc = n.get("content-desc", "").strip()
        interactivo = (
            any(
                _verdadero(n, a) for a in ("clickable", "long-clickable", "checkable", "scrollable")
            )
            or n.get("class", "").endswith("EditText")
            or (_verdadero(n, "focusable") and bool(texto))
        )
        if not interactivo:
            continue
        ni += 1
        ne += bool(texto or desc)
        nid += bool(n.get("resource-id", "").strip())
    return _cobertura(ni, ne, nid, len(nodos), flutter, umbral)


def _cobertura_ios(raiz: ET.Element, flutter: bool, umbral: float) -> CoberturaSemantica:
    nodos = [n for n in raiz.iter() if n.tag.startswith("XCUIElementType")]
    ni = ne = nid = 0
    for n in nodos:
        if n.tag.removeprefix("XCUIElementType") not in _TIPOS_IOS:
            continue
        ni += 1
        label, name = n.get("label", "").strip(), n.get("name", "").strip()
        ne += bool(label or name)
        nid += bool(name) and name != label
    return _cobertura(ni, ne, nid, len(nodos), flutter, umbral)


def cobertura_elementos(
    elementos: Sequence[ElementoUI], *, flutter: bool, umbral: float = 0.6
) -> CoberturaSemantica:
    inter = [e for e in elementos if e.clicable or e.editable]
    ne = sum(bool(e.texto.strip() or e.descripcion.strip()) for e in inter)
    nid = sum(not re.fullmatch(r"e\d+", e.id) for e in inter)
    return _cobertura(len(inter), ne, nid, len(elementos), flutter, umbral)
