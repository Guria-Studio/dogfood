"""Motor `claude_code`: `claude -p` como subproceso con la sesión del plan Max."""

import asyncio
import json
import os
import shutil
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dogfood.backends.base import ErrorMotor, UsoBackend
from dogfood.config import Config

T = TypeVar("T", bound=BaseModel)

SIN_CLAUDE = "No se encontró `claude` en el PATH: instala Claude Code y ejecuta `claude` para iniciar sesión."
SIN_SESION = (
    "Claude Code no está autenticado: ejecuta `claude` y luego /login con la cuenta del plan Max."
)
_MARCAS_SESION = ("not logged in", "invalid api key", "/login", "please run /login")


def _sin_sesion(texto: str) -> bool:
    t = texto.lower()
    return any(m in t for m in _MARCAS_SESION)


class BackendClaudeCode:
    nombre = "claude_code"

    def __init__(self, modelo: str, cfg: Config):
        self.modelo = modelo
        self.cfg = cfg

    async def completar_json(
        self,
        prompt: str,
        esquema: type[T],
        *,
        imagenes: Sequence[Path] = (),
        sesion: str | None = None,
    ) -> tuple[T, UsoBackend, str | None]:
        cc = self.cfg.claude_code
        binario = shutil.which("claude")
        if binario is None:
            raise ErrorMotor(SIN_CLAUDE)
        rutas = [Path(p).resolve() for p in imagenes]
        dirs = sorted({str(p.parent) for p in rutas})
        if rutas:
            prompt += "\n\nImágenes (léelas con la herramienta Read):\n" + "\n".join(
                f"- {p}" for p in rutas
            )
        args = [
            binario,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(esquema.model_json_schema()),
            "--model",
            self.modelo,
            "--strict-mcp-config",
            "--allowedTools",
            "Read",
        ]
        if dirs:
            args += ["--add-dir", *dirs]
        if cc.mcp_config:
            args += ["--mcp-config", str(cc.mcp_config)]
        if sesion:
            args += ["--resume", sesion]
        t0 = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="dogfood-claude-") as cwd:  # nunca el repo
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=cwd,
                env=os.environ.copy(),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), cc.timeout_s)
            except TimeoutError:
                proc.kill()
                await proc.wait()
                raise ErrorMotor(
                    f"`claude -p` superó el tiempo límite de {cc.timeout_s:g} s"
                ) from None
        texto = out.decode(errors="replace")
        try:
            datos = json.loads(texto)
        except ValueError:
            datos = None
        if not isinstance(datos, dict):
            if _sin_sesion(texto + err.decode(errors="replace")):
                raise ErrorMotor(SIN_SESION)
            raise ErrorMotor(
                f"`claude -p` no devolvió JSON (código {proc.returncode}): {texto[:300]}"
            )
        resultado = datos.get("result")
        if datos.get("is_error") or (isinstance(resultado, str) and _sin_sesion(resultado)):
            if _sin_sesion(str(resultado)):
                raise ErrorMotor(SIN_SESION)
            raise ErrorMotor(f"`claude -p` falló: {str(resultado)[:300]}")
        bruto = datos.get("structured_output")
        if bruto is None:
            bruto = resultado
        try:
            salida = (
                esquema.model_validate_json(bruto)
                if isinstance(bruto, str)
                else esquema.model_validate(bruto)
            )
        except ValidationError:
            raise ErrorMotor(
                f"La respuesta no valida contra {esquema.__name__}: {str(bruto)[:300]}"
            ) from None
        u = datos.get("usage") or {}
        cache = u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        uso = UsoBackend(
            tokens_in=u.get("input_tokens", 0),
            tokens_out=u.get("output_tokens", 0),
            tokens_cache=cache,
            capturas=len(rutas),
            duracion_s=time.monotonic() - t0,
            costo_usd=0,  # plan Max
            costo_equivalente_usd=datos.get("total_cost_usd", 0) or 0,
        )
        return salida, uso, datos.get("session_id")
