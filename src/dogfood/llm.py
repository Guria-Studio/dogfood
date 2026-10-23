"""Clientes LLM por rol contra 9router y registro de uso/costo."""

import logging

import httpx
from browser_use.llm import ChatOpenAI
from pydantic import BaseModel

from dogfood.config import Config
from dogfood.dominio import UsoLlm

log = logging.getLogger("dogfood")
ROLES = ("persona", "juez", "dedupe", "redactor")


def _modelo(cfg: Config, rol: str, indice: int = 0) -> str:
    if rol not in ROLES or rol not in cfg.roles:
        raise ValueError(f"rol desconocido: {rol!r} (válidos: {', '.join(ROLES)})")
    return cfg.roles[rol][indice]


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
        )
        self.usos.append(uso)
        return uso

    def desde_respuesta(self, rol: str, modelo: str, respuesta: dict, **kw) -> UsoLlm:
        """`respuesta` es el JSON de chat/completions (campo `usage`)."""
        u = respuesta.get("usage") or {}
        return self.registrar(
            rol, modelo, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), **kw
        )


async def completar_json[T: BaseModel](
    rol: str,
    prompt: str,
    esquema: type[T],
    cfg: Config | None = None,
    contador: ContadorUso | None = None,
) -> T:
    """Salida estructurada `json_schema`. No usar `tool_choice` forzado: 9router lo rompe."""
    cfg = cfg or Config.cargar()
    modelo = _modelo(cfg, rol)
    cuerpo = {
        "model": modelo,
        "stream": False,  # sin esto algunos modelos devuelven `data: [DONE]` pegado al JSON
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": esquema.__name__,
                "strict": True,
                "schema": esquema.model_json_schema(),
            },
        },
    }
    async with httpx.AsyncClient(timeout=120) as http:
        r = await http.post(
            cfg.secreto("ROUTER_BASE_URL").rstrip("/") + "/chat/completions",
            json=cuerpo,
            headers={"Authorization": f"Bearer {cfg.secreto('ROUTER_API_KEY')}"},
        )
    r.raise_for_status()
    datos = r.json()
    if contador:
        contador.desde_respuesta(rol, modelo, datos)
    return esquema.model_validate_json(datos["choices"][0]["message"]["content"])
