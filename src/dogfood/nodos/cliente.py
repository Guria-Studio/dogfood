"""Cliente del nodo iOS (FR-38, NFR-12): estado y trabajos por SSH, artefactos por rsync, túnel -L.

Sin shell: todo se lanza con `asyncio.create_subprocess_exec`. Los `dart_defines` viajan solo por stdin.
"""

import asyncio
import re
import shlex
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Self

from pydantic import ValidationError

from dogfood.config import Nodo
from dogfood.deterministico.corredor import a_ejecucion
from dogfood.dominio import Ejecucion, Escenario, Persona
from dogfood.nodos.protocolo import EstadoNodo, ResultadoTrabajo, Trabajo
from dogfood.web import validar_host

Runner = Callable[..., Awaitable[tuple[int, bytes, bytes]]]
Lanzador = Callable[[Sequence[str]], Awaitable["asyncio.subprocess.Process"]]

_USUARIO = re.compile(r"^[a-z_][a-z0-9_.-]*$")
_AYUDA_SSH = "configura la clave SSH y Tailscale; ver docs/ops/ios-nodo-mac.md"
_FALLOS_SSH = (
    "permission denied",
    "could not resolve",
    "connection refused",
    "connection timed out",
    "operation timed out",
    "no route to host",
    "network is unreachable",
    "host is down",
    "connection closed",
)


class ErrorNodo(RuntimeError):
    """Fallo al hablar con el nodo; el mensaje dice qué hacer."""


async def runner_subprocess(
    args: Sequence[str], *, entrada: bytes | None = None, timeout_s: float = 60
) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE if entrada is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(entrada), timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode if proc.returncode is not None else -1, out, err


async def _lanzar(args: Sequence[str]) -> "asyncio.subprocess.Process":
    return await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )


class Tunel:
    """Proceso `ssh -N -L …`; `cerrar()` lo termina. También sirve como `async with`."""

    def __init__(self, proc: "asyncio.subprocess.Process", puertos: list[int]):
        self.proc = proc
        self.puertos = puertos

    async def cerrar(self) -> None:
        if self.proc.returncode is None:
            try:
                self.proc.terminate()
            except ProcessLookupError:
                pass
        await self.proc.wait()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.cerrar()


class ClienteNodo:
    def __init__(
        self,
        nombre: str,
        nodo: Nodo,
        runner: Runner | None = None,
        lanzador: Lanzador | None = None,
    ):
        validar_host(nodo.host)  # revalida aunque el Nodo se haya armado con model_construct
        if not _USUARIO.match(nodo.usuario):
            raise ValueError(f"usuario SSH {nodo.usuario!r} no válido (^[a-z_][a-z0-9_.-]*$)")
        self.nombre = nombre
        self.nodo = nodo
        self.runner: Runner = runner or runner_subprocess
        self.lanzador: Lanzador = lanzador or _lanzar

    @property
    def _destino(self) -> str:
        return f"{self.nodo.usuario}@{self.nodo.host}"

    def _ssh(self, *extra: str) -> list[str]:
        return [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-p",
            str(self.nodo.puerto_ssh),
            *extra,
        ]

    def _comando(self, *sub: str) -> list[str]:
        return [*self._ssh(self._destino), *shlex.split(self.nodo.comando), *sub]

    @staticmethod
    def _revisar(codigo: int, err: bytes) -> None:
        texto = err.decode(errors="replace")
        bajo = texto.lower()
        if "command not found" in bajo or codigo == 127:
            raise ErrorNodo("instala dogfood en el Mac (comando no encontrado en el nodo)")
        if "permission denied" in bajo or (codigo == 255 and any(f in bajo for f in _FALLOS_SSH)):
            raise ErrorNodo(f"nodo inalcanzable o sin acceso: {_AYUDA_SSH}")

    async def _correr(
        self, args: list[str], entrada: bytes | None, timeout_s: float
    ) -> tuple[int, bytes, bytes]:
        try:
            return await self.runner(args, entrada=entrada, timeout_s=timeout_s)
        except TimeoutError as e:
            raise ErrorNodo(f"el nodo no respondió en {timeout_s:.0f} s") from e

    @staticmethod
    def _ultima_linea(out: bytes) -> str:
        lineas = [x for x in out.decode(errors="replace").splitlines() if x.strip()]
        return lineas[-1] if lineas else ""

    @staticmethod
    def _cola(err: bytes, n: int = 5) -> str:
        return "\n".join(err.decode(errors="replace").strip().splitlines()[-n:])

    async def estado(self) -> EstadoNodo:
        codigo, out, err = await self._correr(self._comando("estado", "--json"), None, 60)
        self._revisar(codigo, err)
        try:
            return EstadoNodo.model_validate_json(self._ultima_linea(out))
        except ValidationError as e:
            raise ErrorNodo(f"el nodo no devolvió un estado válido: {self._cola(err)}") from e

    async def enviar(self, trabajo: Trabajo, carpeta: Path) -> ResultadoTrabajo:
        limite = trabajo.timeout_s + 60
        codigo, out, err = await self._correr(
            self._comando("ejecutar"), trabajo.model_dump_json().encode(), limite
        )
        self._revisar(codigo, err)
        try:
            resultado = ResultadoTrabajo.model_validate_json(self._ultima_linea(out))
        except ValidationError as e:
            raise ErrorNodo(
                f"el nodo no devolvió un resultado JSON válido (código {codigo}): {self._cola(err)}"
            ) from e
        carpeta.mkdir(parents=True, exist_ok=True)
        origen = f"{self._destino}:{self.nodo.dir_trabajo}/{trabajo.id}/"
        rsh = f"ssh -p {self.nodo.puerto_ssh} -o BatchMode=yes"
        codigo, _, err = await self._correr(
            ["rsync", "-a", "-e", rsh, origen, f"{carpeta}/"], None, 300
        )
        if codigo != 0:
            self._revisar(codigo, err)
            raise ErrorNodo(f"rsync falló (código {codigo}): {self._cola(err)}")
        return resultado

    async def tunel(self, puertos: Sequence[int]) -> Tunel:
        lista = [int(p) for p in puertos]
        fwd = [x for p in lista for x in ("-L", f"127.0.0.1:{p}:127.0.0.1:{p}")]
        args = self._ssh("-N", "-o", "ExitOnForwardFailure=yes", *fwd, self._destino)
        return Tunel(await self.lanzador(args), lista)


def a_ejecucion_ios(
    resultado: ResultadoTrabajo,
    persona: Persona,
    escenario: Escenario,
    ejecucion_id: str,
    carpeta: Path,
) -> Ejecucion:
    det = resultado.deterministico
    if det is None:
        return Ejecucion(
            id=ejecucion_id,
            persona_id=persona.id,
            escenario_id=escenario.id,
            modelo="ios",
            estado="error",
            motivo_juez=resultado.mensaje or f"el nodo terminó con estado {resultado.estado}",
            driver="ios",
            backend="ninguno",
            resultado="no_concluyente",
            notas=[resultado.mensaje] if resultado.mensaje else [],
        )

    def _abs(p: Path | None) -> Path | None:
        return p if p is None or p.is_absolute() else carpeta / p

    det = det.model_copy(
        update={
            "log": _abs(det.log),
            "reporte": _abs(det.reporte),
            "captura_final": _abs(det.captura_final),
        }
    )
    return a_ejecucion(det, persona, escenario, ejecucion_id, "ios")
