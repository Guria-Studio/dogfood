"""Configuración: `dogfood.yaml` + secretos de `~/.config/dogfood/*.env`. Nunca imprime un secreto."""

import logging
import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field, PrivateAttr, field_validator

from dogfood.dominio import Plataforma
from dogfood.web import validar_host

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


class Motores(BaseModel):
    """Motor por rol: `api` | `claude_code`. `llm.backend_para` valida el valor."""

    persona: str = "api"
    juez: str = "api"
    dedupe: str = "api"
    redactor: str = "api"

    def __getitem__(self, rol: str) -> str:
        return getattr(self, rol)


class ClaudeCode(BaseModel):
    modelos: dict[str, str] = Field(default_factory=dict)
    mcp_config: Path | None = None
    timeout_s: float = 180


class Agente(BaseModel):
    max_capturas_por_paso: int = Field(default=1, ge=0)
    resolucion_max: int = Field(default=1024, gt=0)


class Driver(BaseModel):
    tipo: Plataforma = "web"
    serial: str | None = None
    host_puerto: str | None = None
    paquete: str | None = None
    actividad: str | None = None
    apk: Path | None = None
    nodo: str | None = None  # ios: nombre en `nodos`
    udid: str | None = None  # ios
    bundle_id: str | None = None  # ios


class Pantalla(BaseModel):
    android: Literal["screencap", "screenrecord"] = "screencap"
    fps: float = Field(default=2, gt=0)


class Flutter(BaseModel):
    sdk: Path = Path("/mnt/storage/flutter/bin/flutter")
    patrol: Path = Path("/mnt/storage/flutter/.pub-cache/bin/patrol")
    pub_cache: Path = Path("/mnt/storage/flutter/.pub-cache")
    proyecto: Path | None = None  # raíz de la app Flutter (solo lectura)
    copia_trabajo: Path = Path("/mnt/storage/cache/dogfood/flutter")
    umbral_cobertura: float = Field(default=0.6, ge=0, le=1)
    timeout_s: float = Field(default=1800, gt=0)

    @field_validator("copia_trabajo", mode="after")
    @classmethod
    def _expandir(cls, v: Path) -> Path:
        return v.expanduser()


class FlutterWeb(BaseModel):
    build_dir: Path | None = (
        None  # build/web ya compilado; si no, se compila desde flutter.proyecto
    )
    host: str = "127.0.0.1"
    puerto: int = 7480
    api_permitidas: list[str] = []  # orígenes que la app web puede llamar
    dart_defines: dict[str, str] = {}

    _host = field_validator("host")(validar_host)


class Nodo(BaseModel):
    """Nodo iOS (Mac) al que se mandan trabajos por SSH: solo loopback o Tailscale (NFR-12)."""

    host: str
    usuario: str
    puerto_ssh: int = 22
    comando: str = "dogfood nodo"  # en el PATH del Mac
    dir_trabajo: str = "~/dogfood-nodo"  # ruta en el Mac: no se expande aquí
    proyectos: dict[str, str] = {}  # nombre → ruta de la app en el Mac

    _host = field_validator("host")(validar_host)


class Servidor(BaseModel):
    """Host y puerto de una app web local: solo 127.0.0.1 o una IP de Tailscale (NFR-10)."""

    host: str = "127.0.0.1"
    puerto: int


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
    motores: Motores = Field(default_factory=Motores)
    claude_code: ClaudeCode = Field(default_factory=ClaudeCode)
    agente: Agente = Field(default_factory=Agente)
    driver: Driver = Field(default_factory=Driver)
    vista: Servidor = Field(default_factory=lambda: Servidor(puerto=7460))
    panel: Servidor = Field(default_factory=lambda: Servidor(puerto=7470))
    pantalla: Pantalla = Field(default_factory=Pantalla)
    flutter: Flutter = Field(default_factory=Flutter)
    flutter_web: FlutterWeb = Field(default_factory=FlutterWeb)
    nodos: dict[str, Nodo] = Field(default_factory=dict)
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
