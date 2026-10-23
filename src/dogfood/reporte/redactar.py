"""Redacción de secretos y datos sensibles (NFR-3, NFR-4).

Todo texto que sale de la máquina pasa por `redactar`; `verificar_limpio` es la
última barrera antes de publicar. Las contraseñas de las personas se pasan en
`secretos_conocidos`, junto con los secretos de `config`.
"""

import re

REDACTADO = "«redactado»"

_ENCABEZADOS = re.compile(r"(?i)\b((?:set-cookie|cookie|authorization)\s*:)[^\r\n]*")
_PARAM_URL = re.compile(r"(?i)([?&;](?:token|key|password)=)[^&\s\"'<>]+")
_JWT = re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+")
_SK = re.compile(r"\bsk-[\w-]{8,}")
# hex o base64 de 32+ caracteres; exige un dígito para no atrapar palabras largas.
_LARGO = re.compile(r"(?<![\w+-])(?=[A-Za-z0-9+_-]*\d)[A-Za-z0-9+_-]{32,}={0,2}")
_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
_HOME = re.compile(r"/home/[^\s\"'<>)\]]+")


def _email(m: re.Match) -> str:
    return m.group(0) if m.group(1).lower() == "dogfood.test" else REDACTADO


def redactar(texto: str, secretos_conocidos: list[str] | None = None) -> str:
    # los más largos primero, para que uno contenido en otro no deje restos
    for s in sorted({s for s in (secretos_conocidos or []) if s}, key=len, reverse=True):
        texto = texto.replace(s, REDACTADO)
    texto = _ENCABEZADOS.sub(lambda m: f"{m.group(1)} {REDACTADO}", texto)
    texto = _PARAM_URL.sub(lambda m: m.group(1) + REDACTADO, texto)
    for rx in (_JWT, _SK, _LARGO, _HOME):
        texto = rx.sub(REDACTADO, texto)
    return _EMAIL.sub(_email, texto)


def verificar_limpio(texto: str) -> list[str]:
    """Devuelve lo que aún parece secreto en `texto` (vacío si está limpio)."""
    texto = texto.replace(REDACTADO, "")
    hallazgos = [m.group(0) for rx in (_JWT, _SK, _LARGO, _HOME) for m in rx.finditer(texto)]
    hallazgos += [
        m.group(0) for m in _ENCABEZADOS.finditer(texto) if m.group(0).split(":", 1)[1].strip()
    ]
    hallazgos += [m.group(0) for m in _PARAM_URL.finditer(texto)]
    hallazgos += [
        m.group(0) for m in _EMAIL.finditer(texto) if m.group(1).lower() != "dogfood.test"
    ]
    return hallazgos
