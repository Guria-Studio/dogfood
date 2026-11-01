"""El juez decide si la persona cumplió el `criterio_exito` (FR-16), sin que un 503 cuente como fallo.

Reintenta lo transitorio (5xx, 429, timeouts) con backoff, prueba los demás modelos del rol `juez`
y, si ninguno responde, lanza `JuezNoDisponible`: la ejecución queda `no_concluyente`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

import httpx
from pydantic import BaseModel

from dogfood.backends.api import BackendApi
from dogfood.backends.base import BackendLlm, UsoBackend
from dogfood.config import Config
from dogfood.llm import ContadorUso

log = logging.getLogger("dogfood")

INTENTOS = 3
TOPE_ESPERA_S = 30.0
RESPALDO = "ag/gemini-3.8-flash"
MOTIVO_NO_DISPONIBLE = "juez no disponible"


class Veredicto(BaseModel):
    exito: bool
    motivo: str


class JuezNoDisponible(RuntimeError):
    """Todos los modelos del juez fallaron: no hay veredicto, ni a favor ni en contra."""


def transitorio(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        c = exc.response.status_code
        return c == 429 or c >= 500
    return isinstance(
        exc, httpx.TransportError | TimeoutError
    )  # httpx.TimeoutException ⊂ Transport


async def _dormir(s: float) -> None:  # los tests lo reemplazan
    await asyncio.sleep(s)


def modelos_respaldo(cfg: Config | None, excluir: str | None = None) -> list[BackendLlm]:
    """Los demás modelos del rol `juez`; si el rol tiene uno solo, el respaldo fijo."""
    if cfg is None:
        return []
    modelos = list(cfg.roles.get("juez", []))
    if len(modelos) <= 1:
        modelos.append(RESPALDO)
    return [BackendApi(m, cfg, None, rol="juez") for m in dict.fromkeys(modelos) if m != excluir]


async def juzgar(
    prompt: str,
    cfg: Config | None,
    *,
    primero: BackendLlm | None = None,
    respaldos: Sequence[BackendLlm] | None = None,
    contador: ContadorUso | None = None,
    ejecucion_id: str | None = None,
    al_uso: Callable[[UsoBackend], None] | None = None,
) -> Veredicto:
    """`primero` es el backend ya armado del motor (si no, el primer modelo del rol).

    Cada intento va a `contador` como `UsoLlm` (los fallidos, con 0 tokens). Los éxitos de
    `primero` los registra quien lo armó; los de los respaldos, aquí.
    """
    if primero is None:
        candidatos = [(b, True) for b in modelos_respaldo(cfg)]
    else:
        extra = respaldos if respaldos is not None else modelos_respaldo(cfg, primero.modelo)
        candidatos = [(primero, False), *[(b, True) for b in extra]]
    ultimo: BaseException | None = None
    for backend, registra_exito in candidatos:
        for intento in range(1, INTENTOS + 1):
            try:
                v, uso, _ = await backend.completar_json(prompt, Veredicto)
            except Exception as exc:  # noqa: BLE001 - cualquier fallo del modelo pasa al siguiente
                ultimo = exc
                log.warning("juez %s intento %d: %r", backend.modelo, intento, exc)
                if contador:
                    contador.registrar("juez", backend.modelo, 0, 0, ejecucion_id)
                if not transitorio(exc):
                    break
                if intento < INTENTOS:
                    await _dormir(min(TOPE_ESPERA_S, 2.0 ** (intento - 1)))
                continue
            if al_uso:
                al_uso(uso)
            if contador and registra_exito:
                contador.registrar(
                    "juez", backend.modelo, uso.tokens_in, uso.tokens_out, ejecucion_id
                )
            return v
    raise JuezNoDisponible(MOTIVO_NO_DISPONIBLE) from ultimo


class DesdeLlamable:
    """Adapta `juez(prompt, esquema)` (el motor navegador) a `BackendLlm`; su uso lo registra quien lo armó."""

    nombre = "api"

    def __init__(self, fn: Callable[[str, type[Veredicto]], Awaitable[Veredicto]], modelo: str):
        self.fn, self.modelo = fn, modelo

    async def completar_json(self, prompt, esquema, *, imagenes=(), sesion=None):
        return await self.fn(prompt, esquema), UsoBackend(), None
