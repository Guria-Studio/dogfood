import importlib
import tomllib
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("modulo", ["browser_use", "playwright", "typer", "jinja2", "numpy"])
def test_dependencias_importan(modulo: str) -> None:
    importlib.import_module(modulo)


def test_config_ejemplo_tiene_los_cuatro_roles() -> None:
    cfg = yaml.safe_load((RAIZ / "dogfood.example.yaml").read_text())
    assert set(cfg["roles"]) == {"persona", "juez", "dedupe", "redactor"}
    assert all(cfg["roles"][r] for r in cfg["roles"])


def test_marcador_integracion_registrado() -> None:
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text())
    marcadores = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert any(m.startswith("integracion:") for m in marcadores)
