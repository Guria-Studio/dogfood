"""Corredor de Patrol e `integration_test` (FR-36): copia de trabajo, ejecución y mapeo al contrato."""

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from dogfood.config import Config
from dogfood.deterministico import Herramienta, ResultadoDeterministico, ResultadoTest
from dogfood.deterministico.generador import defines as resolver_defines
from dogfood.deterministico.generador import generar_test
from dogfood.dominio import Ejecucion, Escenario, Evidencia, Paso, Persona, Plataforma

RunnerProceso = Callable[..., Awaitable[tuple[int, bytes, bytes]]]

INSTRUCCION_PATROL = (
    "La app no está preparada para Patrol: agrega `patrol` a dev_dependencies y el bloque "
    "`patrol:` al pubspec.yaml de la app (ver docs/ops/flutter.md) o usa `motor: integration_test`."
)
_COMPILACION = re.compile(
    r"Error:|Gradle task assembleDebug failed|Xcode build failed|Compilation failed"
)
_SIN_DISPOSITIVO = re.compile(r"No devices found|No supported devices connected")
# ✅ nombre (archivo) / ❌ nombre (archivo); el resumen («✅ Successful: 1») no termina en «)».
_PATROL = re.compile(r"^\s*([✅❌])\s+(.+?)\s+\(([^()]+)\)\s*$")


async def _runner_real(
    args: list[str], *, cwd: Path, env: dict[str, str], timeout_s: float
) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout_s)
    except (TimeoutError, asyncio.CancelledError):
        if proc.returncode is None:
            proc.kill()
        raise
    return proc.returncode or 0, out, err


def _pubspec(copia: Path) -> dict:
    p = copia / "pubspec.yaml"
    return (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}


def _deps_path(app: Path) -> list[Path]:
    """Directorios de las dependencias `path:` de la app, recursivo y sin ciclos."""
    vistos: dict[Path, None] = {}
    pendientes = [app]
    while pendientes:
        d = pendientes.pop()
        p = d / "pubspec.yaml"
        pub = (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}
        for seccion in ("dependencies", "dev_dependencies", "dependency_overrides"):
            for spec in (pub.get(seccion) or {}).values():
                ruta = spec.get("path") if isinstance(spec, dict) else None
                if not ruta:
                    continue
                dep = (d / str(ruta)).resolve()
                if not dep.is_dir():
                    raise FileNotFoundError(f"la dependencia path: {ruta} ({dep}) no existe")
                if dep != app and dep not in vistos:
                    vistos[dep] = None
                    pendientes.append(dep)
    return list(vistos)


def _parsear_flutter(texto: str) -> tuple[list[ResultadoTest], list[dict]]:
    eventos: list[dict] = []
    for ln in texto.splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if isinstance(e, dict):
            eventos.append(e)
    nombres: dict[int, tuple[str, int]] = {}
    errores: dict[int, str] = {}
    tests: list[ResultadoTest] = []
    for e in eventos:
        tipo = e.get("type")
        if tipo == "testStart":
            t = e["test"]
            nombres[t["id"]] = (t.get("name", ""), e.get("time", 0))
        elif tipo == "error":
            errores.setdefault(e.get("testID"), str(e.get("error", "")).strip())
        elif tipo == "testDone" and not e.get("hidden"):
            nombre, t0 = nombres.get(e["testID"], (f"test {e['testID']}", 0))
            if e.get("skipped"):
                estado = "saltado"
            else:
                estado = {"success": "ok", "failure": "fallo"}.get(e.get("result"), "error")
            tests.append(
                ResultadoTest(
                    nombre=nombre,
                    estado=estado,
                    ms=max(0, e.get("time", 0) - t0),
                    mensaje=errores.get(e["testID"], "") if estado in ("fallo", "error") else "",
                )
            )
    return tests, eventos


def _parsear_patrol(texto: str) -> list[ResultadoTest]:
    tests: list[ResultadoTest] = []
    for ln in texto.splitlines():
        if "Test summary" in ln:
            break  # lo que sigue es el resumen, no detalle de un fallo
        if m := _PATROL.match(ln):
            tests.append(
                ResultadoTest(nombre=m.group(2), estado="ok" if m.group(1) == "✅" else "fallo")
            )
        elif tests and tests[-1].estado == "fallo" and ln.strip():
            tests[-1].mensaje = (tests[-1].mensaje + "\n" + ln.strip())[:500].strip()
    return tests


class CorredorFlutter:
    def __init__(self, cfg: Config, runner: RunnerProceso | None = None):
        self.cfg = cfg
        self._runner = runner or _runner_real

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PUB_CACHE"] = str(self.cfg.flutter.pub_cache)
        env["PATH"] = f"{self.cfg.flutter.sdk.parent}{os.pathsep}{env.get('PATH', '')}"
        return env

    async def _correr(self, args: list[str], cwd: Path, timeout_s: float | None = None):
        return await self._runner(
            args, cwd=cwd, env=self._env(), timeout_s=timeout_s or self.cfg.flutter.timeout_s
        )

    async def copia_de_trabajo(self, proyecto: Path) -> Path:
        """Copia la app y los paquetes `path:` externos (monorepo) conservando la disposición."""
        origen = proyecto.expanduser().resolve()
        base = self.cfg.flutter.copia_trabajo.expanduser().resolve()
        raiz = base / origen.name
        externos = [d for d in _deps_path(origen) if not d.is_relative_to(origen)]
        if externos:
            comun = Path(os.path.commonpath([origen, *externos]))
            raiz_origen = comun
            destino = raiz / origen.relative_to(comun)
        else:
            raiz_origen, destino = origen, raiz
        for o in [origen, *externos]:
            if base in (o, *o.parents) or o in raiz.parents or o == raiz:
                raise ValueError(f"el proyecto {o} y la copia de trabajo {raiz} se solapan")
        base.mkdir(parents=True, exist_ok=True)
        copiados: list[Path] = []
        for o in [origen, *sorted(externos)]:
            if any(o.is_relative_to(c) for c in copiados):
                continue  # ya viaja dentro de otra carpeta copiada
            copiados.append(o)
            d = destino if o == origen else raiz / o.relative_to(raiz_origen)
            d.parent.mkdir(parents=True, exist_ok=True)
            codigo, _, err = await self._correr(
                [
                    "rsync",
                    "-a",
                    "--delete",
                    "--exclude",
                    "build/",
                    "--exclude",
                    ".dart_tool/",
                    "--exclude",
                    ".git/",
                    f"{o}/",
                    f"{d}/",
                ],
                base,
            )
            if codigo:
                raise RuntimeError(
                    f"rsync falló ({codigo}): {err.decode(errors='replace').strip()}"
                )
        return destino

    def comando(
        self, herramienta: Herramienta, test: Path, dispositivo: str, defines: dict[str, str]
    ) -> list[str]:
        d = [x for k, v in defines.items() for x in ("--dart-define", f"{k}={v}")]
        if herramienta == "patrol":
            return [
                str(self.cfg.flutter.patrol),
                "test",
                "--target",
                str(test),
                "--device",
                dispositivo,
                *d,
            ]
        return [
            str(self.cfg.flutter.sdk),
            "test",
            str(test),
            "-d",
            dispositivo,
            "--reporter",
            "json",
            *d,
        ]

    async def correr(
        self,
        escenario: Escenario,
        herramienta: Herramienta,
        dispositivo: str,
        carpeta: Path,
        *,
        proyecto: Path | None = None,
        capturar: Callable[[Path], Awaitable[Path | None]] | None = None,
    ) -> ResultadoDeterministico:
        proyecto = proyecto or self.cfg.flutter.proyecto
        if proyecto is None:
            raise ValueError("falta `flutter.proyecto` (o el argumento `proyecto`)")
        if not escenario.deterministico:
            raise ValueError(f"el escenario {escenario.id!r} no tiene bloque `deterministico`")
        rec = escenario.deterministico
        det = carpeta / "deterministico"
        det.mkdir(parents=True, exist_ok=True)
        log = det / "salida.log"

        copia = await self.copia_de_trabajo(proyecto)
        pub = _pubspec(copia)
        dev = pub.get("dev_dependencies") or {}
        if herramienta == "patrol" and "patrol" not in dev and "patrol" not in pub:
            log.write_text(INSTRUCCION_PATROL + "\n")
            return ResultadoDeterministico(
                herramienta=herramienta, codigo_salida=-1, motivo="app_sin_patrol", log=log
            )
        if herramienta == "integration_test" and "integration_test" not in dev:
            await self._correr(
                [
                    str(self.cfg.flutter.sdk),
                    "pub",
                    "add",
                    "--dev",
                    "integration_test",
                    "--sdk=flutter",
                ],
                copia,
            )

        defs = resolver_defines(rec, self.cfg)
        if rec.archivo:
            rel = Path(rec.archivo)
            origen_test = copia / rel
            texto_test = origen_test.read_text() if origen_test.exists() else ""
        else:
            rel = Path("integration_test/dogfood") / f"{escenario.id}_test.dart"
            texto_test = generar_test(escenario, herramienta, str(pub.get("name") or "app"))
            (copia / rel).parent.mkdir(parents=True, exist_ok=True)
            (copia / rel).write_text(texto_test)
        (det / "test.dart").write_text(texto_test)

        args = self.comando(herramienta, rel, dispositivo, defs)
        timeout = False
        try:
            codigo, out, err = await self._correr(args, copia)
            texto = out.decode(errors="replace") + err.decode(errors="replace")
        except TimeoutError:
            codigo, texto, timeout = None, "", True
        for v in sorted((v for v in defs.values() if v), key=len, reverse=True):
            texto = texto.replace(v, "***")
        log.write_text(texto)

        reporte = None
        if herramienta == "integration_test":
            tests, eventos = _parsear_flutter(texto)
            reporte = det / "reporte.json"
            reporte.write_text(json.dumps(eventos, ensure_ascii=False))
        else:
            tests = _parsear_patrol(texto)

        motivo = ""
        if timeout:
            motivo = "timeout"
        elif not any(t.estado == "fallo" for t in tests):
            if _COMPILACION.search(texto):
                motivo = "compilacion"
            elif _SIN_DISPOSITIVO.search(texto) or re.search(
                rf"(?i)device\W+{re.escape(dispositivo)}\W+not found", texto
            ):
                motivo = "sin_dispositivo"
            elif not tests:
                motivo = "sin_tests"

        final = None
        if capturar:
            (carpeta / "capturas").mkdir(parents=True, exist_ok=True)
            final = await capturar(carpeta / "capturas" / "final.png")
        return ResultadoDeterministico(
            herramienta=herramienta,
            codigo_salida=codigo,
            tests=tests,
            motivo=motivo,
            log=log,
            reporte=reporte,
            captura_final=final,
        )


def a_ejecucion(
    r: ResultadoDeterministico,
    persona: Persona,
    escenario: Escenario,
    ejecucion_id: str,
    driver: Plataforma,
) -> Ejecucion:
    res = r.resultado()
    ahora = datetime.now(UTC)
    if r.tests:
        pasos = [
            Paso(
                n=i,
                url="",
                pantalla="",
                accion=t.nombre,
                ts=ahora,
                observado=f"{t.estado}: {t.mensaje}" if t.mensaje else t.estado,
            )
            for i, t in enumerate(r.tests, 1)
        ]
    else:
        pasos = [
            Paso(
                n=1,
                url="",
                pantalla="",
                accion=r.herramienta,
                ts=ahora,
                observado=f"sin resultados: {r.motivo or 'sin_tests'}",
            )
        ]
    pasos[-1].captura = r.captura_final
    ok = [t for t in r.tests if t.estado == "ok"]
    evidencia = [Evidencia(tipo="log", ruta=r.log)]
    if r.reporte:
        evidencia.append(Evidencia(tipo="log", ruta=r.reporte))
    return Ejecucion(
        id=ejecucion_id,
        persona_id=persona.id,
        escenario_id=escenario.id,
        modelo=r.herramienta,
        estado={"aprobado": "ok", "fallo": "fallo"}.get(res, "error"),  # type: ignore[arg-type]
        pasos=pasos,
        exito=res == "aprobado",
        motivo_juez=(
            f"{len(ok)} de {len(r.tests)} tests pasaron: {', '.join(t.nombre for t in ok)}"
            if res == "aprobado"
            else ""
        ),
        driver=driver,
        motor=r.herramienta,
        backend="ninguno",
        resultado=res,
        evidencia_driver=evidencia,
    )


__all__ = ["CorredorFlutter", "RunnerProceso", "a_ejecucion"]
