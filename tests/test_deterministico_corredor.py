import json
import shutil
from pathlib import Path

import pytest

from dogfood import contrato
from dogfood.config import Config
from dogfood.deterministico import ResultadoDeterministico
from dogfood.deterministico.corredor import CorredorFlutter, a_ejecucion
from dogfood.dominio import (
    Escenario,
    Idioma,
    Intencion,
    PasoDeterministico,
    Persona,
    RecorridoDeterministico,
)

FIX = Path(__file__).parent / "fixtures" / "flutter"
CLAVE = "S3cr3t-Clave-9"


def _cfg(tmp_path: Path) -> Config:
    cfg = Config.cargar(Path(__file__).parent.parent)
    cfg.flutter.copia_trabajo = tmp_path / "copias"
    cfg.flutter.sdk = Path("/sdk/bin/flutter")
    cfg.flutter.pub_cache = Path("/sdk/pub-cache")
    cfg._secretos = {"DOGFOOD_APP_CLAVE": CLAVE}
    return cfg


def _escenario(**kw) -> Escenario:
    return Escenario(
        id="login",
        titulo="Login",
        objetivo="Entrar.",
        criterio_exito="Ve el panel.",
        deterministico=RecorridoDeterministico(
            pasos=[
                PasoDeterministico(accion="escribir", key="campo", valor="{env:DOGFOOD_APP_CLAVE}"),
                PasoDeterministico(accion="tocar", key="entrar"),
            ]
        ),
        **kw,
    )


def _app(
    tmp_path: Path,
    pubspec: str = "name: miapp\ndev_dependencies:\n  flutter_test:\n    sdk: flutter\n",
) -> Path:
    app = tmp_path / "app"
    app.mkdir()
    (app / "pubspec.yaml").write_text(pubspec)
    return app


class Fake:
    """Graba (args, cwd, env) y devuelve la salida grabada del comando de test."""

    def __init__(self, salida: str = "", codigo: int = 0, timeout: bool = False):
        self.llamadas: list[tuple[list[str], Path, dict]] = []
        self.salida, self.codigo, self.timeout = salida, codigo, timeout

    async def __call__(self, args, *, cwd, env, timeout_s):
        self.llamadas.append((args, cwd, env))
        if args[0] == "rsync":  # imita el rsync: copia el árbol (sin build/.dart_tool/.git)
            shutil.copytree(
                args[-2],
                args[-1],
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("build", ".dart_tool", ".git"),
            )
            return 0, b"", b""
        if args[1:2] == ["pub"]:
            return 0, b"", b""
        if self.timeout:
            raise TimeoutError
        return self.codigo, self.salida.encode(), b""

    def test(self):
        return next(x for x in self.llamadas if x[0][0] != "rsync" and x[0][1:2] != ["pub"])


async def _correr(tmp_path, fake, herramienta="integration_test", app=None, **kw):
    c = CorredorFlutter(_cfg(tmp_path), fake)
    return await c.correr(
        _escenario(),
        herramienta,
        "emulator-1",
        tmp_path / "run",
        proyecto=app or _app(tmp_path),
        **kw,
    )


async def test_comando_y_entorno(tmp_path):
    fake = Fake((FIX / "flutter_test_ok.jsonl").read_text())
    app = _app(tmp_path)
    r = await _correr(tmp_path, fake, app=app)
    args, cwd, env = fake.test()
    assert args == [
        "/sdk/bin/flutter",
        "test",
        "integration_test/dogfood/login_test.dart",
        "-d",
        "emulator-1",
        "--reporter",
        "json",
        "--dart-define",
        f"DOGFOOD_APP_CLAVE={CLAVE}",
    ]
    assert cwd == tmp_path / "copias" / "app" and cwd != app
    assert env["PUB_CACHE"] == "/sdk/pub-cache" and "/sdk/bin" in env["PATH"]
    assert r.resultado() == "aprobado" and [t.nombre for t in r.tests] == [
        "Login con email y contraseña"
    ]
    assert (tmp_path / "run/deterministico/test.dart").exists() and r.reporte.exists()
    # el test generado vive en la copia y usa el nombre del paquete del pubspec
    assert (
        "package:miapp/main.dart" in (cwd / "integration_test/dogfood/login_test.dart").read_text()
    )
    assert not (app / "integration_test").exists()


async def test_copia_con_rsync_y_pubspec(tmp_path):
    fake = Fake((FIX / "flutter_test_ok.jsonl").read_text())
    app = _app(tmp_path)
    await _correr(tmp_path, fake, app=app)
    rs = fake.llamadas[0][0]
    assert rs[:3] == ["rsync", "-a", "--delete"]
    for ex in ("build/", ".dart_tool/", ".git/"):
        assert rs[rs.index("--exclude", rs.index(ex) - 1) + 1] == ex
    assert rs[-2:] == [f"{app.resolve()}/", f"{tmp_path.resolve()}/copias/app/"]
    assert all(c != app for _, c, _ in fake.llamadas)
    pub = next(a for a, _, _ in fake.llamadas if a[1:2] == ["pub"])
    assert pub[1:] == ["pub", "add", "--dev", "integration_test", "--sdk=flutter"]


async def test_no_agrega_integration_test_si_ya_esta(tmp_path):
    fake = Fake((FIX / "flutter_test_ok.jsonl").read_text())
    app = _app(tmp_path, "name: a\ndev_dependencies:\n  integration_test:\n    sdk: flutter\n")
    await _correr(tmp_path, fake, app=app)
    assert not any(a[1:2] == ["pub"] for a, _, _ in fake.llamadas)


async def test_proyecto_dentro_de_la_copia(tmp_path):
    c = CorredorFlutter(_cfg(tmp_path), Fake())
    with pytest.raises(ValueError):
        await c.copia_de_trabajo(tmp_path / "copias" / "app")
    (tmp_path / "copias").mkdir()
    with pytest.raises(ValueError):
        await c.copia_de_trabajo(tmp_path / "copias" / "x" / "app")


async def test_fallo_con_mensaje(tmp_path):
    r = await _correr(tmp_path, Fake((FIX / "flutter_test_fallo.jsonl").read_text(), 1))
    assert r.resultado() == "fallo"
    assert "Found 0 widgets" in r.tests[0].mensaje
    e = a_ejecucion(r, _persona(), _escenario(), "e1", "android")
    assert "Found 0 widgets" in e.pasos[0].observado and e.estado == "fallo"


async def test_compilacion(tmp_path):
    r = await _correr(tmp_path, Fake((FIX / "flutter_compilacion.txt").read_text(), 1))
    assert r.resultado() == "no_concluyente" and r.motivo == "compilacion"


async def test_timeout(tmp_path):
    r = await _correr(tmp_path, Fake(timeout=True))
    assert r.resultado() == "no_concluyente" and r.motivo == "timeout" and r.codigo_salida is None


async def test_cero_tests(tmp_path):
    r = await _correr(tmp_path, Fake('{"type":"done","success":true,"time":1}\n'))
    assert r.resultado() == "no_concluyente" and r.motivo == "sin_tests"


async def test_sin_dispositivo(tmp_path):
    r = await _correr(tmp_path, Fake("No devices found yet.\n", 1))
    assert r.motivo == "sin_dispositivo"


async def test_patrol(tmp_path):
    fake = Fake((FIX / "patrol_ok.txt").read_text())
    r = await _correr(
        tmp_path,
        fake,
        "patrol",
        app=_app(tmp_path, "name: a\ndev_dependencies:\n  patrol: ^4.0.0\n"),
    )
    args, _, _ = fake.test()
    assert args[:7] == [
        "/mnt/storage/flutter/.pub-cache/bin/patrol",
        "test",
        "--target",
        "integration_test/dogfood/login_test.dart",
        "--device",
        "emulator-1",
        "--dart-define",
    ]
    assert r.resultado() == "aprobado" and r.reporte is None
    assert r.tests[0].nombre == "Comprar creditos"


async def test_patrol_fallo(tmp_path):
    r = await _correr(
        tmp_path,
        Fake((FIX / "patrol_fallo.txt").read_text(), 1),
        "patrol",
        app=_app(tmp_path, "name: a\npatrol:\n  app_name: A\n"),
    )
    assert r.resultado() == "fallo" and "Pago pendiente" in r.tests[0].mensaje
    assert "Total" not in r.tests[0].mensaje


async def test_patrol_sin_patrol(tmp_path):
    fake = Fake()
    r = await _correr(tmp_path, fake, "patrol")
    assert r.motivo == "app_sin_patrol" and r.resultado() == "no_concluyente"
    assert "docs/ops/flutter.md" in r.log.read_text()
    assert all(a[0] == "rsync" for a, _, _ in fake.llamadas)


async def test_contrasena_redactada(tmp_path):
    fake = Fake(f"salida con {CLAVE} adentro\n" + (FIX / "flutter_test_ok.jsonl").read_text())
    r = await _correr(tmp_path, fake)
    log = r.log.read_text()
    assert CLAVE not in log and "***" in log
    assert CLAVE not in r.reporte.read_text()


def _persona() -> Persona:
    return Persona(
        id="p1",
        nombre="Ana",
        email="a@b.test",
        contrasena="x",
        empresa="E",
        rubro="r",
        idioma=Idioma.es,
        destreza=2,
        paciencia=3,
        intencion=Intencion.solo_exportar,
        semilla=1,
    )


async def test_a_ejecucion_contrato(tmp_path):
    async def capturar(destino: Path):
        destino.write_bytes(b"png")
        return destino

    fake = Fake((FIX / "flutter_test_ok.jsonl").read_text())
    r = await _correr(tmp_path, fake, capturar=capturar)
    e = a_ejecucion(r, _persona(), _escenario(), "e1", "android")
    assert (e.motor, e.backend, e.modelo, e.estado, e.exito) == (
        "integration_test",
        "ninguno",
        "integration_test",
        "ok",
        True,
    )
    assert e.motivo_juez.startswith("1 de 1 tests pasaron")
    assert contrato.resultado(e) == "aprobado" == e.resultado
    assert e.pasos[-1].captura and len(e.evidencia_driver) == 2

    sin = r.model_copy(update={"captura_final": None})
    e2 = a_ejecucion(sin, _persona(), _escenario(), "e2", "android")
    assert contrato.resultado(e2) == "no_concluyente"
    assert isinstance(json.loads(e.model_dump_json()), dict)
    assert isinstance(r, ResultadoDeterministico)
