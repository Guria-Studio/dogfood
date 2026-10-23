"""Configuración: `dogfood.yaml` + secretos de `~/.config/dogfood/*.env`. Nunca imprime un secreto."""

import logging
import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field, PrivateAttr

log = logging.getLogger("dogfood")

# Qué archivo de secretos corresponde a cada prefijo de variable (para el mensaje de error).
_ARCHIVO_POR_PREFIJO = {"ROUTER_": "router.env", "SLACK_": "slack.env"}


class ErrorSecreto(RuntimeError):
    pass


class Precio(BaseModel):
    entrada: float
    salida: float


class Tolerancias(BaseModel):
    ciclo_relativo_max: float = 0.25
    pares_ok_min: float = 0.80
    compras_min_par: int = 6
    mae_dias_delta: int = 1


class Config(BaseModel):
    roles: dict[str, list[str]]
    precios_usd_por_millon: dict[str, Precio] = Field(default_factory=dict)
    asignacion_modelos: Literal["rotar", "primero"] = "primero"
    concurrencia: int = 5
    tope_usd: float | None = None
    umbral_publicar: str = "media"
    repo_issues: str = ""
    canal_slack: str | None = None
    memoria_libre_min_gb: float = 2
    tolerancias: Tolerancias = Field(default_factory=Tolerancias)
    _dir_secretos: Path = PrivateAttr(default_factory=Path)
    _secretos: dict[str, str] = PrivateAttr(default_factory=dict)

    @classmethod
    def cargar(cls, raiz: Path | None = None) -> "Config":
        raiz = raiz or Path.cwd()
        ruta = raiz / "dogfood.yaml"
        if not ruta.exists():
            ruta = raiz / "dogfood.example.yaml"
            log.warning("no existe dogfood.yaml; uso %s", ruta.name)
        cfg = cls.model_validate(yaml.safe_load(ruta.read_text()))
        cfg._dir_secretos = Path(
            os.environ.get("DOGFOOD_CONFIG_DIR") or Path.home() / ".config" / "dogfood"
        )
        for env in sorted(cfg._dir_secretos.glob("*.env")):
            for k, v in dotenv_values(env).items():
                if v is not None:
                    cfg._secretos.setdefault(k, v)
        return cfg

    def secreto(self, nombre: str) -> str:
        valor = self._secretos.get(nombre)
        if not valor:
            archivo = next(
                (a for p, a in _ARCHIVO_POR_PREFIJO.items() if nombre.startswith(p)), "predicts.env"
            )
            raise ErrorSecreto(f"falta {nombre} en {self._dir_secretos / archivo}")
        return valor

    def __repr__(self) -> str:
        claves = ", ".join(f"{k}=***" for k in sorted(self._secretos))
        return f"Config(roles={self.roles}, concurrencia={self.concurrencia}, secretos[{claves}])"

    __str__ = __repr__
