import codecs
import csv
import json
import re
from datetime import date

import pytest
from typer.testing import CliRunner

from dogfood.comandos.datos import app
from dogfood.datos.defectos import DEFECTOS, aplicar, defectos_que_rompen_verdad
from dogfood.datos.generador import generar

FMAX = date(2026, 6, 30)


@pytest.fixture
def limpio(tmp_path):
    return generar("farmacia", 60, 7, FMAX, salida=tmp_path / "d").ruta_csv


def _leer(ruta, sep=",", enc="utf-8"):
    with open(ruta, encoding=enc, newline="") as f:
        return list(csv.reader(f, delimiter=sep))


@pytest.mark.parametrize("d", DEFECTOS)
def test_cada_defecto_se_lee(limpio, d):
    sep = {"sep_punto_coma": ";", "sep_tab": "\t"}.get(d, ",")
    enc = {"latin1": "latin-1", "cp1252": "cp1252", "utf8_bom": "utf-8-sig"}.get(d, "utf-8")
    out = aplicar(limpio, [d], 1, grande_mb=0.05)
    filas = _leer(out, sep, enc)
    if d == "vacio":
        assert len(filas) == 1
    else:
        assert len(filas) > 1 and len(filas[0]) >= 8
    if d == "utf8_bom":
        assert out.read_bytes().startswith(codecs.BOM_UTF8)


def test_fecha_dmy(limpio):
    assert any(
        r[2] == "05/03/2026" or re.fullmatch(r"\d\d/\d\d/2026|\d\d/\d\d/2025", r[2])
        for r in _leer(aplicar(limpio, ["fecha_dmy"], 1))[1:]
    )
    base = _leer(limpio)[1]
    d = date.fromisoformat(base[2])
    assert _leer(aplicar(limpio, ["fecha_dmy"], 1))[1][2] == d.strftime("%d/%m/%Y")


def test_ean_cientifico(limpio):
    assert re.fullmatch(r"\d,\d{5}E\+\d\d", _leer(aplicar(limpio, ["ean_cientifico"], 1))[1][4])


def test_duplicados(limpio):
    n = len(_leer(limpio)) - 1
    m = len(_leer(aplicar(limpio, ["duplicados"], 1))) - 1
    assert 0.04 * n <= m - n <= 0.06 * n


def test_vacio_solo_encabezados(limpio):
    assert _leer(aplicar(limpio, ["vacio"], 1)) == [_leer(limpio)[0]]


def test_misma_semilla_mismo_archivo(limpio):
    a = aplicar(limpio, ["duplicados", "ids_vacios", "fecha_con_hora"], 3).read_bytes()
    assert aplicar(limpio, ["duplicados", "ids_vacios", "fecha_con_hora"], 3).read_bytes() == a


def test_verdad_solo_cambia_defectos(limpio):
    v = limpio.parent / "verdad.json"
    antes = json.loads(v.read_text())
    aplicar(limpio, ["latin1", "duplicados", "fecha_mdy"], 1)
    despues = json.loads(v.read_text())
    assert despues.pop("defectos") == ["latin1", "duplicados", "fecha_mdy"]
    antes.pop("defectos")
    assert despues == antes


def test_grande_extiende_verdad(limpio):
    aplicar(limpio, ["grande"], 1, grande_mb=0.05)
    v = json.loads((limpio.parent / "verdad.json").read_text())
    ids = {r[0] for r in _leer(limpio.with_name("ventas_defectos.csv"))[1:]}
    assert ids == {c["cliente_id"] for c in v["clientes"]}


def test_rompen_verdad():
    r = defectos_que_rompen_verdad()
    assert "vacio" in r and not {"ean_sin_ceros", "ids_vacios", "fechas_futuras"} & set(r)


def test_cli_defecto_desconocido(tmp_path):
    r = CliRunner().invoke(
        app,
        [
            "--perfil",
            "farmacia",
            "--clientes",
            "5",
            "--defectos",
            "nope",
            "--salida",
            str(tmp_path),
        ],
    )
    assert r.exit_code != 0 and "latin1" in r.output
