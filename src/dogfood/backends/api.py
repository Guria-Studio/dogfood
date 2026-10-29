"""Motor `api`: chat/completions de 9router con salida estructurada `json_schema`."""

import base64
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import httpx
from pydantic import BaseModel

from dogfood.backends.base import UsoBackend
from dogfood.config import Config

if TYPE_CHECKING:
    from dogfood.llm import ContadorUso

T = TypeVar("T", bound=BaseModel)


class BackendApi:
    nombre = "api"

    def __init__(
        self,
        modelo: str,
        cfg: Config,
        contador: "ContadorUso | None" = None,
        *,
        rol: str = "",
    ):
        self.modelo = modelo
        self.cfg = cfg
        self.contador = contador
        self.rol = rol

    async def completar_json(
        self,
        prompt: str,
        esquema: type[T],
        *,
        imagenes: Sequence[Path] = (),
        sesion: str | None = None,  # la API no guarda sesión: el bucle reenvía el contexto
    ) -> tuple[T, UsoBackend, str | None]:
        """No usar `tool_choice` forzado: 9router lo rompe."""
        if imagenes:
            contenido: str | list[dict] = [{"type": "text", "text": prompt}] + [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(Path(p).read_bytes()).decode()
                    },
                }
                for p in imagenes
            ]
        else:
            contenido = prompt
        cuerpo = {
            "model": self.modelo,
            "stream": False,  # sin esto algunos modelos devuelven `data: [DONE]` pegado al JSON
            "messages": [{"role": "user", "content": contenido}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": esquema.__name__,
                    "strict": True,
                    "schema": esquema.model_json_schema(),
                },
            },
        }
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=120) as http:
            r = await http.post(
                self.cfg.secreto("ROUTER_BASE_URL").rstrip("/") + "/chat/completions",
                json=cuerpo,
                headers={"Authorization": f"Bearer {self.cfg.secreto('ROUTER_API_KEY')}"},
            )
        r.raise_for_status()
        datos = r.json()
        u = datos.get("usage") or {}
        t_in, t_out = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        if self.contador:
            self.contador.registrar(self.rol, self.modelo, t_in, t_out, backend="api")
        precio = self.cfg.precios_usd_por_millon.get(self.modelo)
        costo = (t_in * precio.entrada + t_out * precio.salida) / 1_000_000 if precio else 0.0
        uso = UsoBackend(
            tokens_in=t_in,
            tokens_out=t_out,
            capturas=len(imagenes),
            duracion_s=time.monotonic() - t0,
            costo_usd=costo,
            costo_equivalente_usd=costo,
        )
        salida = esquema.model_validate_json(datos["choices"][0]["message"]["content"])
        return salida, uso, None
