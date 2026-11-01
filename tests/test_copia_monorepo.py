"""Copia de trabajo de un monorepo: rsync falso que copia con shutil."""

import hashlib
import shutil
from pathlib import Path

import pytest
import yaml

from dogfood.config import Config
from dogfood.deterministico.corredor import CorredorFlutter


async def _rsync(args, *, cwd, env, timeout_s):
    ori, dst = Path(args[-2]), Path(args[-1])
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(ori, dst, ignore=shutil.ignore_patterns("build", ".dart_tool", ".git"))
    return 0, b"", b""


def _cfg(tmp_path: Path) -> Config:
    cfg = Config.cargar(Path(__file__).parent.parent)
    cfg.flutter.copia_trabajo = tmp_path / "copias"
    return cfg


def _pkg(d: Path, deps: str = "") -> None:
    d.mkdir(parents=True)
    (d / "pubspec.yaml").write_text(f"name: {d.name}\n{deps}")
    (d / "lib.dart").write_text(d.name)


def _monorepo(tmp_path: Path) -> Path:
    m = tmp_path / "mono"
    _pkg(m / "apps/app_a", "dependencies:\n  core:\n    path: ../../packages/core\n")
    _pkg(m / "packages/core", "dependencies:\n  util:\n    path: ../util\n")
    _pkg(m / "packages/util")
    return m


def _hash(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.rglob("*")):
        h.update(str(f.relative_to(d)).encode())
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


async def test_monorepo_conserva_disposicion(tmp_path):
    m = _monorepo(tmp_path)
    antes = _hash(m)
    r = await CorredorFlutter(_cfg(tmp_path), _rsync).copia_de_trabajo(m / "apps/app_a")
    copia = tmp_path.resolve() / "copias" / "app_a"
    assert r == copia / "apps/app_a"
    assert (copia / "packages/core/lib.dart").exists()
    assert (copia / "packages/util/lib.dart").exists()
    for dep in yaml.safe_load((r / "pubspec.yaml").read_text())["dependencies"].values():
        assert (r / dep["path"]).resolve().is_dir()
        assert (r / dep["path"]).resolve().is_relative_to(copia)
    assert _hash(m) == antes
    assert not any(p.is_symlink() for p in copia.rglob("*"))


async def test_path_inexistente(tmp_path):
    app = tmp_path / "app"
    _pkg(app, "dependencies:\n  x:\n    path: ../no_existe\n")
    with pytest.raises(FileNotFoundError, match="no_existe"):
        await CorredorFlutter(_cfg(tmp_path), _rsync).copia_de_trabajo(app)


async def test_sin_path_externos(tmp_path):
    app = tmp_path / "app"
    _pkg(app, "dependencies:\n  flutter:\n    sdk: flutter\n")
    r = await CorredorFlutter(_cfg(tmp_path), _rsync).copia_de_trabajo(app)
    assert r == tmp_path.resolve() / "copias" / "app"
    assert (r / "lib.dart").exists()
