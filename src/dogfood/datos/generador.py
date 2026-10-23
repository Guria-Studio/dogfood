"""Ventas sintéticas con verdad conocida: `ventas.csv` limpio + `verdad.json`."""

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from statistics import NormalDist

import numpy as np

from dogfood.datos.perfiles import PERFILES, Perfil
from dogfood.dominio import DatasetSintetico

MIN_COMPRAS = 3
PROP_ABANDONO = 0.10
PROP_POCAS_COMPRAS = 0.15
ENCABEZADOS = ["customer_id", "order_id", "date", "sku", "ean", "product", "qty", "price"]
_NORMAL = NormalDist()


def _intervalos(rng: np.random.Generator, ciclo: float, sigma: float, k: int) -> np.ndarray:
    # ponytail: muestreo estratificado (latin hypercube) del log-normal, así la mediana
    # empírica de pocos intervalos queda cerca de `ciclo`; cada intervalo sigue siendo
    # log-normal(ln ciclo, sigma). Pasar a iid si el oráculo necesita ruido de mediana real.
    u = (rng.permutation(k) + rng.uniform(size=k)) / k
    z = np.array([_NORMAL.inv_cdf(min(max(x, 1e-9), 1 - 1e-9)) for x in u])
    return ciclo * np.exp(sigma * z)


def generar(
    perfil: str | Perfil,
    n_clientes: int,
    semilla: int,
    fecha_max: date,
    meses: int = 12,
    *,
    idioma: str = "pt-BR",
    salida: Path | None = None,
) -> DatasetSintetico:
    p = PERFILES[perfil] if isinstance(perfil, str) else perfil
    rng = np.random.default_rng(semilla)
    span = round(meses * 365 / 12)
    inicio = fecha_max - timedelta(days=span)
    productos = p.productos

    # Elegir clientes que abandonan y pares con pocas compras con cantidades exactas.
    abandonan = set(
        rng.choice(n_clientes, size=round(n_clientes * PROP_ABANDONO), replace=False).tolist()
    )
    elegidos = [
        sorted(rng.choice(len(productos), size=int(rng.integers(1, 7)), replace=False).tolist())
        for _ in range(n_clientes)
    ]
    recompra = [(c, j) for c, js in enumerate(elegidos) for j in js if not productos[j].durable]
    n_pocas = round(len(recompra) * PROP_POCAS_COMPRAS)
    pocas = {recompra[i] for i in rng.choice(len(recompra), size=n_pocas, replace=False)}

    filas: list[tuple[int, int, int, int]] = []  # (día, cliente, producto, qty)
    clientes = []
    for c, js in enumerate(elegidos):
        abandono = None
        fin = span
        if c in abandonan:
            desde = round(span * 0.3)
            dia_ab = int(rng.integers(desde, max(desde + 1, span - 60)))
            abandono = inicio + timedelta(days=dia_ab)
            fin = dia_ab - 1
        qty_base = int(rng.integers(1, 4))
        pares = []
        for j in js:
            prod = productos[j]
            if prod.durable:
                ciclo = None
                dias = [int(rng.integers(0, fin + 1))]
            else:
                ciclo = round(float(rng.uniform(prod.ciclo_min, prod.ciclo_max)), 1)
                if (c, j) in pocas:
                    n = int(rng.integers(1, MIN_COMPRAS))
                    t0 = max(0.0, fin - (n - 1 + rng.uniform()) * ciclo)
                    k = n - 1
                else:
                    t0 = rng.uniform(0, ciclo)
                    k = max(1, math.floor((fin - t0) / ciclo))
                ts = np.concatenate(
                    [[t0], t0 + np.cumsum(_intervalos(rng, ciclo, prod.sigma_log, k))]
                )
                dias = [int(t) for t in ts if t <= fin]
            for d in dias:
                filas.append((d, c, j, qty_base))
            ultima = inicio + timedelta(days=dias[-1])
            proxima = None
            if ciclo is not None and abandono is None:
                proxima = (ultima + timedelta(days=round(ciclo))).isoformat()
            pares.append(
                {
                    "producto_id": prod.id,
                    "sku": prod.sku,
                    "ciclo_real_dias": ciclo,
                    "sigma_log": prod.sigma_log,
                    "n_compras": len(dias),
                    "ultima_compra": ultima.isoformat(),
                    "proxima_compra": proxima,
                    "durable": prod.durable,
                }
            )
        clientes.append(
            {
                "cliente_id": _cliente_id(c),
                "abandono_desde": abandono.isoformat() if abandono else None,
                "pares": pares,
            }
        )

    dataset_id = f"{p.nombre}-{n_clientes}-s{semilla}"
    carpeta = salida or Path("datos") / dataset_id
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_csv = carpeta / "ventas.csv"
    ruta_verdad = carpeta / "verdad.json"

    filas.sort()
    pedidos: dict[tuple[int, int], str] = {}
    with ruta_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(ENCABEZADOS)
        for d, c, j, qty in filas:
            pedido = pedidos.setdefault((d, c), f"P{len(pedidos) + 1:07d}")
            prod = productos[j]
            fecha = (inicio + timedelta(days=d)).isoformat()
            w.writerow(
                [_cliente_id(c), pedido, fecha, prod.sku, prod.ean, prod.nombre(idioma), qty,
                 f"{prod.precio:.2f}"]
            )  # fmt: skip

    verdad = {
        "semilla": semilla,
        "perfil": p.nombre,
        "fecha_max": fecha_max.isoformat(),
        "parametros": {
            "MIN_COMPRAS": MIN_COMPRAS,
            "meses": meses,
            "ventana_desde": inicio.isoformat(),
            "ventana_hasta": fecha_max.isoformat(),
            "idioma": idioma,
        },
        "defectos": [],
        "clientes": clientes,
    }
    ruta_verdad.write_text(json.dumps(verdad, ensure_ascii=False, indent=2) + "\n", "utf-8")

    return DatasetSintetico(
        id=dataset_id,
        perfil=p.nombre,
        ruta_csv=ruta_csv,
        ruta_verdad=ruta_verdad,
        n_clientes=n_clientes,
        n_filas=len(filas),
        semilla=semilla,
    )


def _cliente_id(c: int) -> str:
    return f"C{c + 1:05d}"
