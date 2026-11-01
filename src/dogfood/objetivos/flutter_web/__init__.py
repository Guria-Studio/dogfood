"""Objetivo app Flutter compilada a web (FR-39, D30): sirve `build/web` y la prueba con DriverWeb."""

import asyncio
import threading
from collections.abc import Callable
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dogfood.config import Config
from dogfood.deterministico.corredor import CorredorFlutter, RunnerProceso
from dogfood.dominio import ContextoDeteccion, Corrida, Escenario, Hallazgo, Instancia
from dogfood.escenarios import cargar
from dogfood.web import validar_host


class _Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def _origen(url: str) -> str:
    u = urlsplit(url)
    return f"{u.scheme}://{u.netloc}"


class FlutterWebObjetivo:
    nombre = "flutter_web"

    def __init__(self, cfg: Config | None = None, runner: RunnerProceso | None = None):
        self._cfg = cfg
        self._runner = runner
        self._servidores: dict[str, ThreadingHTTPServer] = {}

    async def _compilar(self, cfg: Config) -> Path:
        # imports locales: el módulo de defines arrastra el generador de tests
        from dogfood.deterministico.generador import defines
        from dogfood.dominio import RecorridoDeterministico

        corredor = CorredorFlutter(cfg, self._runner)
        copia = await corredor.copia_de_trabajo(cfg.flutter.proyecto)
        env = defines(RecorridoDeterministico(dart_defines=cfg.flutter_web.dart_defines), cfg)
        args = [str(cfg.flutter.sdk), "build", "web", "--release", "--no-web-resources-cdn"]
        for k, v in env.items():
            args += ["--dart-define", f"{k}={v}"]
        codigo, _, err = await corredor._correr(args, copia)
        if codigo != 0:
            raise RuntimeError(
                f"flutter build web falló ({codigo}): {err.decode(errors='replace')[-500:]}"
            )
        return copia / "build" / "web"

    def preparar(self, ref: str, corrida: Corrida) -> Instancia:
        cfg = self._cfg or Config.cargar()
        fw = cfg.flutter_web
        host = validar_host(fw.host)
        if fw.build_dir and (fw.build_dir / "index.html").exists():
            build = fw.build_dir
        elif cfg.flutter.proyecto:
            build = asyncio.run(self._compilar(cfg))
        else:
            raise ValueError(
                "Falta `flutter_web.build_dir` (con index.html) o `flutter.proyecto` en dogfood.yaml."
            )
        srv = ThreadingHTTPServer((host, fw.puerto), partial(_Silencioso, directory=str(build)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://{host}:{srv.server_address[1]}/"
        self._servidores[base] = srv
        return Instancia(
            base_url=base,
            api_url="",
            proyecto_compose="",
            commit=ref,
            parametros={
                "flutter": True,
                "build_dir": str(build),
                "umbral_cobertura": cfg.flutter.umbral_cobertura,
                "api_permitidas": list(fw.api_permitidas),
            },
        )

    def destruir(self, instancia: Instancia) -> None:
        if srv := self._servidores.pop(instancia.base_url, None):
            srv.shutdown()
            srv.server_close()

    def url_permitida(self, url: str, instancia: Instancia) -> bool:
        api = instancia.parametros.get("api_permitidas", [])
        permitidos = {_origen(instancia.base_url), *(o.rstrip("/") for o in api)}
        return _origen(url) in permitidos

    def escenarios(self) -> list[Escenario]:
        return cargar(Path(__file__).parent / "escenarios")

    def pantalla(self, url: str) -> str:
        u = urlsplit(url)
        ruta = (u.fragment.split("?")[0] if u.fragment.startswith("/") else u.path).strip("/")
        return ruta or "inicio"

    def verificadores(self) -> list[Callable[[ContextoDeteccion], list[Hallazgo]]]:
        return []

    def logs(self, instancia: Instancia, desde: datetime) -> dict[str, str]:
        return {}
