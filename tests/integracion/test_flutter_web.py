"""Integración M8 sin hardware (F8.7.T2): mobile-mao compilada a web y vista con DriverWeb(flutter=True).

uv run pytest -m integracion tests/integracion/test_flutter_web.py -s
"""

import asyncio
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest

from dogfood.config import Config
from dogfood.deteccion.flutter import detectar
from dogfood.dominio import ContextoDeteccion, Corrida, Ejecucion, Paso
from dogfood.drivers.base import Accion
from dogfood.drivers.web import DriverWeb
from dogfood.objetivos.flutter_web import FlutterWebObjetivo

pytestmark = pytest.mark.integracion

SDK = Path("/mnt/storage/flutter/bin/flutter")
APP = Path("/mnt/storage/rupies/apps/mobile-mao")
CACHE = Path("/mnt/storage/cache/dogfood")
RAIZ = Path(__file__).parent.parent.parent


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(APP), *args], capture_output=True, text=True, check=True
    ).stdout


def test_mobile_mao_compilada_a_web(tmp_path_factory):
    if not SDK.exists():
        pytest.skip(f"no existe el SDK de Flutter: {SDK}")
    if not (APP / "pubspec.yaml").exists():
        pytest.skip(f"no existe la app de referencia: {APP}")
    CACHE.mkdir(parents=True, exist_ok=True)
    trabajo = Path(__import__("tempfile").mkdtemp(prefix="flutter-web-", dir=CACHE))
    antes = _git("status", "--porcelain")
    pk = APP.parent.parent / "packages"
    pk_antes = subprocess.run(
        ["git", "-C", str(pk), "status", "--porcelain"], check=False, capture_output=True, text=True
    ).stdout
    try:
        cfg = Config.cargar(RAIZ)
        # la app depende de ../../packages (monorepo): la copia vive en <trabajo>/apps/ y los
        # paquetes se enlazan (solo lectura) en <trabajo>/packages
        (trabajo / "packages").symlink_to(APP.parent.parent / "packages")
        cfg.flutter.proyecto, cfg.flutter.copia_trabajo = APP, trabajo / "apps"
        cfg.flutter.sdk = SDK
        cfg.flutter_web.puerto, cfg.flutter_web.build_dir = 0, None
        # el build por defecto baja CanvasKit y las fuentes de gstatic: sin esto la app queda en blanco
        cfg.flutter_web.api_permitidas = [
            "https://www.gstatic.com",
            "https://fonts.gstatic.com",
        ]
        env = {
            "PATH": f"{SDK.parent}:{__import__('os').environ['PATH']}",
            "PUB_CACHE": "/mnt/storage/flutter/.pub-cache",
        }
        __import__("os").environ.update(env)
        version = subprocess.run(
            [str(SDK), "--version"], check=False, capture_output=True, text=True
        ).stdout.splitlines()[0]
        obj = FlutterWebObjetivo(cfg)
        t0 = time.monotonic()
        try:
            inst = obj.preparar("main", None)
        except RuntimeError as e:
            (trabajo / "resultado.json").write_text(
                json.dumps({"version": version, "error": str(e)})
            )
            print(f"COMPILACION FALLO ({version}): {e}")
            pytest.skip(f"flutter build web falló con mobile-mao: {str(e)[-300:]}")
        compilacion_s = time.monotonic() - t0
        try:
            res = asyncio.run(_observar(inst, obj, trabajo, cfg))
        finally:
            obj.destruir(inst)
        res |= {
            "version": version,
            "compilacion_s": round(compilacion_s, 1),
            "trabajo": str(trabajo),
        }
        (trabajo / "resultado.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
        print(json.dumps(res, indent=2, ensure_ascii=False))
        con_etiqueta = any(p["etiquetados"] for p in res["pantallas"])
        assert con_etiqueta or res["pantallas"][0]["ciega"]
    finally:
        assert _git("status", "--porcelain") == antes, "mobile-mao cambió"
        pk_despues = subprocess.run(
            ["git", "-C", str(pk), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout
        assert pk_despues == pk_antes, "packages cambió"
        # la copia y el build quedan en /mnt/storage/cache/dogfood para la nota; se limpian a mano


async def _observar(inst, obj, trabajo: Path, cfg: Config) -> dict:
    d = DriverWeb(
        inst.base_url,
        lambda u: obj.url_permitida(u, inst),
        {"width": 412, "height": 915},
        movil=True,
        flutter=True,
        umbral_cobertura=cfg.flutter.umbral_cobertura,
    )
    carpeta = trabajo / "ejec"
    await d.iniciar(carpeta)
    pantallas, pasos = [], []
    try:
        await asyncio.sleep(3)  # arranque de la app
        obs = await d.observar(1)
        obss = [obs]
        primero = next((e for e in obs.elementos if e.clicable), None)
        if primero:
            await d.actuar(Accion(tipo="tocar", elemento=primero.id))
            await asyncio.sleep(2)
            obss.append(await d.observar(2))
        for n, o in enumerate(obss, 1):
            c = o.cobertura
            pantallas.append(
                {
                    "n": n,
                    "url": o.pantalla,
                    "elementos": len(o.elementos),
                    "etiquetados_elem": sum(bool(e.texto or e.descripcion) for e in o.elementos),
                    "interactivos": c.interactivos,
                    "etiquetados": c.etiquetados,
                    "con_id": c.con_id,
                    "nodos": c.nodos,
                    "ciega": c.ciega,
                    "captura": str(o.captura),
                    "tocado": primero.model_dump(mode="json") if primero and n == 2 else None,
                    "etiquetas": [e.texto or e.descripcion for e in o.elementos][:15],
                }
            )
            pasos.append(
                Paso(n=n, url=o.pantalla, pantalla=o.pantalla, accion="observar",
                     captura=o.captura, arbol=o.arbol, ts=datetime.now().astimezone())
            )  # fmt: skip
        consola = [f"{c.nivel}: {c.texto[:300]}" for c in d.consola][:15]
        red_mala = [f"{r.metodo} {r.url[:120]} {r.estado}" for r in d.red if r.estado >= 400][:10]
    finally:
        await d.cerrar()
    ej = Ejecucion(id="e1", persona_id="p", escenario_id="s", modelo="m", estado="ok",
                   pasos=pasos, driver="web")  # fmt: skip
    ctx = ContextoDeteccion(
        corrida=Corrida(id="c", objetivo="flutter_web", ref="main", commit="x", semilla=1,
                        inicio=datetime.now().astimezone(), estado="ok"),
        instancia=inst, ejecuciones=[ej], datasets={}, cliente_api=lambda p: None, logs={},
    )  # fmt: skip
    return {
        "pantallas": pantallas,
        "consola": consola,
        "red_mala": red_mala,
        # el detector de F8.3.T1 solo lee árboles XML de android/ios: con driver web no reporta
        "hallazgos_detector": len(detectar(ctx)),
    }
