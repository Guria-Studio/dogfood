"""Cuentas de las personas en predicts: credenciales, confirmación del registro y token de
recuperación de contraseña (FR-9, D7, D8)."""

import re
from collections.abc import Callable
from datetime import datetime

import httpx

from dogfood.dominio import Instancia, Persona
from dogfood.objetivos.predicts import entorno

# El token es `secrets.token_urlsafe(32)` (43 caracteres) solo en su línea, igual en los tres
# idiomas de `correo/plantillas/<idioma>/recuperacion.txt`.
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$", re.MULTILINE)


def credenciales(persona: Persona) -> tuple[str, str]:
    return persona.email, persona.contrasena


def confirmar_registro(instancia: Instancia, persona: Persona) -> str | None:
    """`empresa_id` de la cuenta si el login funciona; `None` si el registro no ocurrió."""
    email, contrasena = credenciales(persona)
    with httpx.Client(base_url=instancia.api_url, timeout=30) as http:
        r = http.post("/api/auth/login", json={"email": email, "contrasena": contrasena})
        if r.status_code != 200:
            return None
        r = http.get("/api/auth/yo")
        if r.status_code != 200:
            return None
        return str(r.json()["empresa"]["id"])


def token_recuperacion(instancia: Instancia, email: str, desde: datetime) -> str | None:
    """Token del último «Email (modo dev) a <email>» del log de la API desde `desde`."""
    log = entorno.logs(instancia, desde)["api"]
    # ponytail: el filtro temporal lo hace `docker compose logs --since`, no se parsean fechas
    token = None
    for bloque in log.split("Email (modo dev) a ")[1:]:
        if bloque.split("\n", 1)[0].strip() == email and (m := _TOKEN.search(bloque)):
            token = m.group(0)
    return token


def herramientas_extra(instancia: Instancia, persona: Persona) -> list[Callable[[], str]]:
    """Herramientas extra del agente para el escenario `recuperar-contrasena`.

    Enganche (lo hace F2.4.T1, no `agente/navegador.py`): el ejecutor llama
    `herramientas_extra(instancia, persona)` solo en ese escenario y registra cada función
    devuelta como herramienta del agente, con el nombre y docstring de la función.
    """
    inicio = datetime.now().astimezone()

    def pedir_token_recuperacion() -> str:
        """Devuelve el token del email de recuperación (pídelo después de solicitarlo)."""
        return token_recuperacion(instancia, persona.email, inicio) or "no llegó ningún email"

    return [pedir_token_recuperacion]
