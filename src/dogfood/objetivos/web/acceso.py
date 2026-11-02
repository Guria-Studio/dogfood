"""Acceso de las personas a una app `web` (F13.1.T2): registro propio, usuario de prueba o sin login.

La contraseña de `usuario_prueba` vive solo en `~/.config/dogfood/secretos/<slug>.env`. Al agente le
llega como dato sensible de browser-use: el texto lleva `<secret>DOGFOOD_PASSWORD</secret>`, nunca el
valor.
"""

import os
import re
from pathlib import Path

import httpx
from dotenv import dotenv_values

from dogfood.contrato import BLOQUEADO
from dogfood.dominio import Persona

VARIABLE = "DOGFOOD_PASSWORD"
MOTIVO_CONFIRMAR = "la app pide confirmar el email"
AVISO_CONCURRENCIA = "cuenta compartida: la concurrencia del proyecto queda en 1"
_LINK = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)


class ErrorAcceso(ValueError):
    """Mensaje accionable, sin secretos."""


def _ruta_secretos(slug: str) -> Path:
    base = Path(os.environ.get("DOGFOOD_CONFIG_DIR") or Path.home() / ".config" / "dogfood")
    return base / "secretos" / f"{slug}.env"


def contrasena(proyecto) -> str:
    ruta = _ruta_secretos(proyecto.slug)
    valor = dotenv_values(ruta).get(VARIABLE) if ruta.exists() else None
    if not valor:
        raise ErrorAcceso(f"falta {VARIABLE} en {ruta} (acceso.modo=usuario_prueba)")
    return valor


def validar(proyecto) -> None:
    """Falla con un error claro antes de lanzar nada."""
    a = proyecto.acceso
    if a.modo == "usuario_prueba":
        if not a.usuario:
            raise ErrorAcceso(f"el proyecto {proyecto.slug!r} no tiene acceso.usuario")
        contrasena(proyecto)
    elif a.modo == "registro" and a.confirmacion == "mailpit" and not a.mailpit_url:
        raise ErrorAcceso(f"el proyecto {proyecto.slug!r} usa mailpit sin acceso.mailpit_url")


def forzar_concurrencia(proyecto) -> None:
    if proyecto.acceso.modo == "usuario_prueba":
        proyecto.comportamiento.concurrencia = 1


def datos_sensibles(proyecto) -> dict[str, str]:
    return {VARIABLE: contrasena(proyecto)} if proyecto.acceso.modo == "usuario_prueba" else {}


def instrucciones(proyecto) -> str:
    """Cómo entra la persona; vacío si no hay paso de entrada."""
    a = proyecto.acceso
    if a.modo == "sin_login":
        return ""
    if a.modo == "usuario_prueba":
        return "Entra con la cuenta que te indica la tarea; no te registres."
    if a.confirmacion == "mailpit":
        return (
            "Regístrate con el email de la tarea. Si la app pide confirmar el email, "
            "llama a la acción `confirmar_email` y sigue desde ahí."
        )
    if a.confirmacion == "manual":
        return (
            f"Regístrate con el email de la tarea. Si la app pide confirmar el email, "
            f"usa `rendirse` con el motivo exacto «{BLOQUEADO} {MOTIVO_CONFIRMAR}»."
        )
    return "Regístrate con el email de la tarea."


def aplicar(proyecto, persona: Persona) -> None:
    """Deja a la persona lista para entrar según el modo (idempotente)."""
    a = proyecto.acceso
    if a.modo == "usuario_prueba":
        persona.email, persona.contrasena = a.usuario, f"<secret>{VARIABLE}</secret>"
    elif a.modo == "sin_login":
        persona.email = ""
    extra = instrucciones(proyecto)
    if extra and extra not in persona.instrucciones:
        persona.instrucciones = f"{persona.instrucciones}\n{extra}".strip()


def link_de_confirmacion(mailpit_url: str, email: str, cliente=httpx) -> str | None:
    """Primer link del último correo para `email`, desde la API de Mailpit."""
    base = mailpit_url.rstrip("/")
    r = cliente.get(f"{base}/api/v1/search", params={"query": f"to:{email}"}, timeout=10)
    r.raise_for_status()
    mensajes = r.json().get("messages") or []
    if not mensajes:
        return None
    m = cliente.get(f"{base}/api/v1/message/{mensajes[0]['ID']}", timeout=10)
    m.raise_for_status()
    d = m.json()
    hallado = _LINK.search((d.get("Text") or "") + " " + (d.get("HTML") or ""))
    return hallado.group(0) if hallado else None
