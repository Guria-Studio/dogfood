"""Clientes LLM por rol contra 9router y registro de uso/costo."""

import logging

from browser_use.llm import ChatOpenAI
from pydantic import BaseModel

from dogfood.backends.api import BackendApi
from dogfood.backends.base import BackendLlm
from dogfood.backends.claude_code import BackendClaudeCode
from dogfood.config import Config
from dogfood.dominio import UsoLlm

log = logging.getLogger("dogfood")
ROLES = ("persona", "juez", "dedupe", "redactor")


def _modelo(cfg: Config, rol: str, indice: int = 0) -> str:
    if rol not in ROLES or rol not in cfg.roles:
        raise ValueError(f"rol desconocido: {rol!r} (válidos: {', '.join(ROLES)})")
    return cfg.roles[rol][indice]


def modelos_para(rol: str, cfg: Config | None = None) -> list[str]:
    cfg = cfg or Config.cargar()
    _modelo(cfg, rol)  # valida el rol
    return list(cfg.roles[rol])


def indice_modelo(rol: str, n: int, semilla: int, cfg: Config) -> int:
    """Índice del modelo de la ejecución `n`. Solo `persona` rota; el resto (juez) usa el primero."""
    if rol != "persona" or cfg.asignacion_modelos != "rotar":
        return 0
    return (semilla + n) % len(modelos_para(rol, cfg))


def cliente_para(rol: str, indice: int = 0, cfg: Config | None = None) -> ChatOpenAI:
    cfg = cfg or Config.cargar()
    return ChatOpenAI(
        model=_modelo(cfg, rol, indice),
        base_url=cfg.secreto("ROUTER_BASE_URL"),
        api_key=cfg.secreto("ROUTER_API_KEY"),
    )


class ContadorUso:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._avisados: set[str] = set()
        self.usos: list[UsoLlm] = []  # todo lo registrado, para guardarlo en el almacén

    def registrar(
        self,
        rol: str,
        modelo: str,
        tokens_in: int,
        tokens_out: int,
        ejecucion_id: str | None = None,
        backend: str = "api",
        costo_equivalente_usd: float | None = None,
    ) -> UsoLlm:
        precio = self.cfg.precios_usd_por_millon.get(modelo)
        if precio is None:
            if modelo not in self._avisados:
                self._avisados.add(modelo)
                log.warning("modelo sin precio: %s (costo 0)", modelo)
            costo = 0.0
        else:
            costo = (tokens_in * precio.entrada + tokens_out * precio.salida) / 1_000_000
        uso = UsoLlm(
            rol=rol,
            modelo=modelo,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            costo_usd=costo,
            ejecucion_id=ejecucion_id,
            backend=backend,
            costo_equivalente_usd=costo if costo_equivalente_usd is None else costo_equivalente_usd,
        )
        self.usos.append(uso)
        return uso

    def desde_respuesta(self, rol: str, modelo: str, respuesta: dict, **kw) -> UsoLlm:
        """`respuesta` es el JSON de chat/completions (campo `usage`)."""
        u = respuesta.get("usage") or {}
        return self.registrar(
            rol, modelo, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), **kw
        )


def backend_para(
    rol: str,
    cfg: Config | None = None,
    indice: int = 0,
    contador: ContadorUso | None = None,
) -> BackendLlm:
    cfg = cfg or Config.cargar()
    motor = cfg.motores[rol]
    if motor == "api":
        return BackendApi(_modelo(cfg, rol, indice), cfg, contador, rol=rol)
    if motor == "claude_code":
        modelo = cfg.claude_code.modelos.get(rol) or _modelo(cfg, rol, indice)
        return BackendClaudeCode(modelo, cfg)
    raise ValueError(f"motor desconocido para {rol!r}: {motor!r} (válidos: api, claude_code)")


async def completar_json[T: BaseModel](
    rol: str,
    prompt: str,
    esquema: type[T],
    cfg: Config | None = None,
    contador: ContadorUso | None = None,
) -> T:
    """Salida estructurada `json_schema` por la API (el motor de `cfg.motores` no aplica aquí)."""
    cfg = cfg or Config.cargar()
    backend = BackendApi(_modelo(cfg, rol), cfg, contador, rol=rol)
    salida, _, _ = await backend.completar_json(prompt, esquema)
    return salida
