import subprocess

import httpx
import pytest
from typer.testing import CliRunner

from dogfood.cli import app

pytestmark = pytest.mark.integracion


def test_env_up_salud_y_down():
    r = CliRunner()
    try:
        res = r.invoke(app, ["env", "up", "--target", "predicts", "--ref", "master"])
        assert res.exit_code == 0, res.output
        assert httpx.get("http://localhost:18080/api/salud", timeout=10).status_code == 200
    finally:
        res = r.invoke(app, ["env", "down", "--target", "predicts"])
        assert res.exit_code == 0, res.output
    ps = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=dogfood-predicts"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert ps.stdout.strip() == ""
