import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dogfood.almacen import Almacen
from dogfood.cli import app

pytestmark = pytest.mark.integracion

RUNS = Path("runs")


def test_corrida_real_contra_predicts():
    res = CliRunner().invoke(
        app,
        ["run", "--target", "predicts", "--personas", "1", "--escenarios", "recompra-completa",
         "--sin-publicar", "--seed", "1", "--ref", "master"],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    corrida_id = res.output.strip().splitlines()[-1].split(":")[0]

    almacen = Almacen(RUNS)
    resumen = next(c for c in almacen.listar_corridas() if c.id == corrida_id)
    assert resumen.estado == "ok"

    base = almacen.dir_corrida(corrida_id) / "ejecuciones"
    (dir_ej,) = [d for d in base.iterdir() if d.is_dir()]
    historial = dir_ej / "historial.json"
    assert historial.is_file()
    ej = almacen.ejecucion(dir_ej.name)
    assert ej.pasos
    assert list((dir_ej / "capturas").glob("*.png"))
    assert list((dir_ej / "descargas").glob("*.csv"))

    ps = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=dogfood-predicts"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert ps.stdout.strip() == ""

    print(
        "RESUMEN M1:",
        json.dumps(
            {"duracion_s": ej.duracion_s, "pasos": len(ej.pasos), "costo_usd": resumen.costo_usd,
             "exito": ej.exito, "motivo_juez": ej.motivo_juez},
            ensure_ascii=False,
        ),
    )  # fmt: skip
