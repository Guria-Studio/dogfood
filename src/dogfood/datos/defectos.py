"""Defectos de mundo real sobre un `ventas.csv` limpio (FR-6).

`aplicar` escribe un CSV nuevo junto al limpio y solo toca `verdad.json` para anotar `defectos`
(y, con `grande`, para extender `clientes` con los clones). El orden de aplicación es fijo e
independiente del orden pedido: primero los defectos de filas (grande, duplicados, ids_vacios,
fechas_futuras), luego los de formato de campo (fecha, decimal, ean), columnas_extra, encabezados,
vacio y por último separador y codificación al escribir. Entre defectos excluyentes
(separador, codificación, fecha, encabezados) gana el primero de cada grupo.
"""

import copy
import csv
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

SEPARADORES = {"sep_punto_coma": ";", "sep_tab": "\t"}
CODIFICACIONES = {"latin1": "latin-1", "cp1252": "cp1252", "utf8_bom": "utf-8-sig"}
FECHAS = ("fecha_dmy", "fecha_mdy", "fecha_con_hora")
EAN = ("ean_cientifico", "ean_sin_ceros")
ENCABEZADOS = {
    "encabezados_pt": ["cliente", "pedido", "data", "sku", "ean", "produto", "quantidade", "preco"],
    "encabezados_es": [
        "cliente",
        "pedido",
        "fecha",
        "sku",
        "ean",
        "producto",
        "cantidad",
        "precio",
    ],
    "sin_encabezados": None,
}
OTROS = ("decimal_coma", "duplicados", "ids_vacios", "fechas_futuras", "columnas_extra")
DEFECTOS = (
    *SEPARADORES,
    *CODIFICACIONES,
    *FECHAS,
    "decimal_coma",
    *EAN,
    *ENCABEZADOS,
    "duplicados",
    "ids_vacios",
    "fechas_futuras",
    "columnas_extra",
    "grande",
    "vacio",
)
PROP_DUPLICADOS = 0.05
PROP_IDS_VACIOS = 0.02
PROP_FECHAS_FUTURAS = 0.01
_BASURA = ["N/A", "??", "-", "ver obs.", "#REF!", "x"]


def defectos_que_rompen_verdad() -> list[str]:
    """Defectos tras los cuales el oráculo NO debe comparar números.

    - `vacio`: no hay ventas, no hay nada que predecir.
    - `fecha_mdy`: `03/05/2026` es indistinguible de `dd/mm`; las fechas quedan ambiguas.
    - `ean_cientifico`: `7,89123E+12` pierde dígitos del EAN, no se puede reconstruir.
    Siguen siendo comparables: `ean_sin_ceros` (se recupera rellenando a 13), `ids_vacios` (solo
    1-2 % de filas anónimas), `fechas_futuras` (1 % fuera de rango, descartables), `duplicados`
    (filas idénticas), `grande` (la verdad se extiende con los clones) y el resto de formato.
    """
    return ["vacio", "fecha_mdy", "ean_cientifico"]


def _primero(defectos: list[str], grupo) -> str | None:
    return next((d for d in defectos if d in grupo), None)


def _elegir(rng: np.random.Generator, n: int, prop: float) -> list[int]:
    if n == 0:
        return []
    return sorted(rng.choice(n, size=min(n, max(1, round(n * prop))), replace=False).tolist())


def _grande(filas, clientes, mb):
    """Repite clientes con otro id hasta `mb` MB; clona también su verdad."""
    base = sum(len(",".join(f)) + 1 for f in filas)
    if not filas or base == 0:
        return filas, clientes
    originales = list(dict.fromkeys(f[0] for f in filas))
    por_cliente = {c: [f for f in filas if f[0] == c] for c in originales}
    verdad_por_id = {c["cliente_id"]: c for c in clientes}
    n, k, total = len(originales), 0, base
    nuevas, nuevos_clientes = [], []
    while total < mb * 1_000_000:
        orig = originales[k % n]
        nuevo = f"C{n + k + 1:05d}"
        for f in por_cliente[orig]:
            g = [nuevo, f"G{k + 1}-{f[1]}", *f[2:]]
            nuevas.append(g)
            total += len(",".join(g)) + 1
        if orig in verdad_por_id:
            c = copy.deepcopy(verdad_por_id[orig])
            c["cliente_id"] = nuevo
            nuevos_clientes.append(c)
        k += 1
    return filas + nuevas, clientes + nuevos_clientes


def aplicar(csv_limpio: Path, defectos: list[str], semilla: int, *, grande_mb: float = 5.0) -> Path:
    invalidos = [d for d in defectos if d not in DEFECTOS]
    if invalidos:
        raise ValueError(
            f"defectos desconocidos: {', '.join(invalidos)}; válidos: {', '.join(DEFECTOS)}"
        )
    rng = np.random.default_rng(semilla)
    ruta_verdad = csv_limpio.parent / "verdad.json"
    verdad = json.loads(ruta_verdad.read_text("utf-8"))
    with csv_limpio.open(encoding="utf-8", newline="") as f:
        encabezado, *filas = list(csv.reader(f))

    if "grande" in defectos:
        filas, verdad["clientes"] = _grande(filas, verdad["clientes"], grande_mb)
    if "duplicados" in defectos:
        extra = _elegir(rng, len(filas), PROP_DUPLICADOS)
        for i in reversed(extra):
            filas.insert(i + 1, list(filas[i]))
    if "ids_vacios" in defectos:
        for i in _elegir(rng, len(filas), PROP_IDS_VACIOS):
            filas[i][0] = ""
    if "fechas_futuras" in defectos:
        fmax = date.fromisoformat(verdad["fecha_max"])
        for i in _elegir(rng, len(filas), PROP_FECHAS_FUTURAS):
            filas[i][2] = (fmax + timedelta(days=int(rng.integers(30, 365)))).isoformat()

    fecha = _primero(defectos, FECHAS)
    for f in filas:
        if fecha:
            d = date.fromisoformat(f[2])
            f[2] = {
                "fecha_dmy": d.strftime("%d/%m/%Y"),
                "fecha_mdy": d.strftime("%m/%d/%Y"),
                "fecha_con_hora": f"{d.isoformat()} {int(rng.integers(8, 21)):02d}:"
                f"{int(rng.integers(60)):02d}:{int(rng.integers(60)):02d}",
            }[fecha]
        if "decimal_coma" in defectos:
            f[7] = f[7].replace(".", ",")
        if "ean_cientifico" in defectos:
            f[4] = f"{int(f[4]):.5E}".replace(".", ",")
        elif "ean_sin_ceros" in defectos:
            f[4] = f[4].lstrip("0")
        if "columnas_extra" in defectos:
            f += ["", _BASURA[int(rng.integers(len(_BASURA)))]]

    if "columnas_extra" in defectos:
        encabezado += ["extra_1", "notas"]
    nombres = ENCABEZADOS.get(_primero(defectos, ENCABEZADOS) or "", encabezado)
    if nombres is not None:
        encabezado = nombres + encabezado[len(nombres) :]
    salida = [encabezado, *filas] if _primero(defectos, ENCABEZADOS) != "sin_encabezados" else filas
    if "vacio" in defectos:
        salida = salida[:1] if salida is not filas else []

    sep = SEPARADORES.get(_primero(defectos, SEPARADORES) or "", ",")
    enc = CODIFICACIONES.get(_primero(defectos, CODIFICACIONES) or "", "utf-8")
    destino = csv_limpio.with_name(f"{csv_limpio.stem}_defectos{csv_limpio.suffix}")
    with destino.open("w", encoding=enc, errors="replace", newline="") as f:
        csv.writer(f, delimiter=sep, lineterminator="\n").writerows(salida)

    verdad["defectos"] = list(defectos)
    ruta_verdad.write_text(json.dumps(verdad, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return destino
