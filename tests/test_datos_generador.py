import csv
import hashlib
import json
from collections import defaultdict
from datetime import date
from itertools import pairwise
from statistics import median

import pytest
from typer.testing import CliRunner

from dogfood.cli import app
from dogfood.datos.generador import generar
from dogfood.datos.perfiles import PERFILES, ean13_valido

FECHA_MAX = date(2026, 6, 30)


def _sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module", params=sorted(PERFILES))
def dataset(request, tmp_path_factory):
    ds = generar(request.param, 300, 7, FECHA_MAX, salida=tmp_path_factory.mktemp(request.param))
    filas = list(csv.DictReader(ds.ruta_csv.open(encoding="utf-8")))
    verdad = json.loads(ds.ruta_verdad.read_text("utf-8"))
    fechas = defaultdict(list)
    for f in filas:
        fechas[f["customer_id"], f["sku"]].append(date.fromisoformat(f["date"]))
    return ds, filas, verdad, fechas


def test_misma_semilla_mismos_bytes(tmp_path):
    a = generar("farmacia", 200, 42, FECHA_MAX, salida=tmp_path / "a")
    b = generar("farmacia", 200, 42, FECHA_MAX, salida=tmp_path / "b")
    c = generar("farmacia", 200, 43, FECHA_MAX, salida=tmp_path / "c")
    assert _sha(a.ruta_csv) == _sha(b.ruta_csv) != _sha(c.ruta_csv)
    assert _sha(a.ruta_verdad) == _sha(b.ruta_verdad)


def test_catalogos():
    for p in PERFILES.values():
        assert 20 <= len(p.productos) <= 60
        assert 0 < p.proporcion_durables < 0.5
        for prod in p.productos:
            assert ean13_valido(prod.ean)
            assert 0.15 <= prod.sigma_log <= 0.4
            assert p.ciclo_min <= prod.ciclo_min <= prod.ciclo_max <= p.ciclo_max


def test_formato_csv(dataset):
    ds, filas, _, _ = dataset
    primera = ds.ruta_csv.read_text("utf-8").splitlines()[0]
    assert primera == "customer_id,order_id,date,sku,ean,product,qty,price"
    assert len(filas) == ds.n_filas


def test_mediana_cerca_del_ciclo_real(dataset):
    _, _, verdad, fechas = dataset
    ok = total = 0
    for cli in verdad["clientes"]:
        for par in cli["pares"]:
            if par["n_compras"] < 8:
                continue
            ds = sorted(fechas[cli["cliente_id"], par["sku"]])
            m = median((b - a).days for a, b in pairwise(ds))
            total += 1
            ok += abs(m - par["ciclo_real_dias"]) <= 0.15 * par["ciclo_real_dias"]
    assert total > 0 and ok / total >= 0.85


def test_pocas_compras_y_n_compras(dataset):
    _, _, verdad, fechas = dataset
    pares = [(c, p) for c in verdad["clientes"] for p in c["pares"]]
    pocas = [p for _, p in pares if not p["durable"] and p["n_compras"] < 3]
    assert len(pocas) >= 0.15 * sum(not p["durable"] for _, p in pares) - 1
    for c, p in pares:
        dias = fechas[c["cliente_id"], p["sku"]]
        assert len(dias) == p["n_compras"]
        if p["n_compras"] < 3:
            assert len(set(dias)) < 3


def test_abandono(dataset):
    _, _, verdad, fechas = dataset
    abandonan = [c for c in verdad["clientes"] if c["abandono_desde"]]
    assert len(abandonan) == round(0.1 * len(verdad["clientes"]))
    for c in abandonan:
        desde = date.fromisoformat(c["abandono_desde"])
        for p in c["pares"]:
            assert max(fechas[c["cliente_id"], p["sku"]]) < desde


def test_ean_y_fecha_max(dataset):
    _, filas, _, _ = dataset
    assert all(ean13_valido(f["ean"]) for f in filas)
    assert max(date.fromisoformat(f["date"]) for f in filas) <= FECHA_MAX


def test_cli(tmp_path):
    r = CliRunner().invoke(
        app,
        ["datos", "--perfil", "cafe", "--clientes", "20", "--seed", "1", "--salida", str(tmp_path)],
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "ventas.csv").exists() and (tmp_path / "verdad.json").exists()


def test_cli_defectos_f2():
    r = CliRunner().invoke(
        app, ["datos", "--perfil", "cafe", "--clientes", "5", "--defectos", "bom"]
    )
    assert r.exit_code == 2 and "disponible en F2" in r.output
