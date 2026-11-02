"""Único punto que llama a REA, siempre por su CLI, con la versión fija y `--format json`.

Todo lo que REA imprime pasa por `redactar` antes de escribirse. La redacción es estructural:
los hashes, el base64 de las capturas y los ids de evidencia no se tocan (REA valida su
integridad al comparar), y a los textos redactados se les recalcula el `sha256` y los `bytes`.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from dogfood.reporte.redactar import redactar

VERSION = "6.8.0"
_HEX64 = re.compile(r"[a-f0-9]{64}")
_INTACTOS = {"data_base64", "evidence_id"}


class ErrorRea(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"REA {code}: {message}")
        self.code = code
        self.message = message


def _comando() -> list[str]:
    if shutil.which("rea"):
        return ["rea"]
    return ["npx", "-y", f"rea-agents@{VERSION}"]


def disponible() -> bool:
    return bool(shutil.which("rea") or shutil.which("npx"))


def intacto(clave: str, valor: str) -> bool:
    """Cadenas que son integridad de REA, no contenido: no se redactan ni se normalizan."""
    return clave in _INTACTOS or clave.endswith("sha256") or bool(_HEX64.fullmatch(valor))


def redactar_evidencia(obj: Any, secretos: list[str], clave: str = "") -> Any:
    if isinstance(obj, str):
        return obj if intacto(clave, obj) else redactar(obj, secretos)
    if isinstance(obj, list):
        return [redactar_evidencia(v, secretos, clave) for v in obj]
    if not isinstance(obj, dict):
        return obj
    out = {k: redactar_evidencia(v, secretos, k) for k, v in obj.items()}
    # artefacto de texto: {"sha256", "bytes", "text"} — si cambió, el digest tiene que seguirlo
    if isinstance(obj.get("text"), str) and out["text"] != obj["text"] and "sha256" in obj:
        datos = out["text"].encode()
        out["sha256"] = hashlib.sha256(datos).hexdigest()
        if "bytes" in obj:
            out["bytes"] = len(datos)
    return out


def _correr(args: list[str], *, timeout_s: float, env: dict[str, str] | None = None) -> dict:
    try:
        r = subprocess.run(
            [*_comando(), *args, "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env={**os.environ, **(env or {})},
        )
    except subprocess.TimeoutExpired as exc:
        raise ErrorRea("timeout", f"REA no terminó en {timeout_s:.0f} s") from exc
    except FileNotFoundError as exc:
        raise ErrorRea("no_disponible", "no hay `rea` ni `npx` en el PATH") from exc
    secretos = list((env or {}).values())
    try:
        datos = json.loads(r.stdout)
    except json.JSONDecodeError:
        salida = redactar((r.stderr or r.stdout).strip()[-500:], secretos)
        raise ErrorRea("salida_invalida", f"código {r.returncode}: {salida}") from None
    datos = redactar_evidencia(datos, secretos)
    if isinstance(datos, dict) and "error" in datos:
        raise ErrorRea(str(datos.get("code", "desconocido")), str(datos.get("message", "")))
    if r.returncode != 0:
        raise ErrorRea("codigo_salida", f"REA salió con {r.returncode}")
    return datos


def grabar(
    escenario: dict,
    destino: Path,
    *,
    secretos: dict[str, str] | None = None,
    timeout_s: float = 600,
) -> Path:
    """Graba `escenario` en `destino/` y devuelve la ruta de su `normalized_result.json`.

    `secretos` va de variable de entorno a valor: así REA lee las contraseñas que el escenario
    declara en `secrets`. Las claves que no son de REA (`avisos`) no se le pasan.
    """
    escenario = {k: v for k, v in escenario.items() if k != "avisos"}
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dogfood-rea-") as tmp:
        archivo = Path(tmp) / "escenario.json"
        archivo.write_text(json.dumps(escenario))
        evidencia = _correr(
            ["capture-browser-scenario", str(archivo)], timeout_s=timeout_s, env=secretos
        )
    if "normalized_result" not in evidencia:
        raise ErrorRea("salida_invalida", "la evidencia no trae normalized_result")
    (destino / "evidencia.json").write_text(json.dumps(evidencia))
    nr = destino / "normalized_result.json"
    nr.write_text(json.dumps(evidencia["normalized_result"]))
    return nr


def comparar(antes: Path, despues: Path, reglas: dict, *, timeout_s: float = 300) -> dict:
    """`compare-web-captures` entre dos `normalized_result.json`; devuelve su normalized_result.

    `reglas` son patrones (`normalizacion.reglas`): se expanden a las reglas literales que REA
    acepta con los valores que aparecen en las dos grabaciones.
    """
    from dogfood.rea.normalizacion import politica

    pol = politica(reglas, json.loads(antes.read_text()), json.loads(despues.read_text()))
    with tempfile.TemporaryDirectory(prefix="dogfood-rea-") as tmp:
        norm = Path(tmp) / "normalizacion.json"
        norm.write_text(json.dumps(pol))
        r = _correr(
            ["compare-web-captures", str(antes), str(despues), "--normalization-json", str(norm)],
            timeout_s=timeout_s,
        )
    return r.get("normalized_result", r)
